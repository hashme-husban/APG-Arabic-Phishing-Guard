"""
APG — VirusTotal URL Reputation Service

Dedicated VirusTotal API v3 client with its own config, in-memory cache,
and error handling.  Imported lazily by URLReputationService._virustotal()
to avoid circular imports.

Environment variables:
  VIRUSTOTAL_ENABLED          true / false  (default: true when API key is set)
  VIRUSTOTAL_API_KEY          your VT API key
  VIRUSTOTAL_TIMEOUT_SECONDS  per-request timeout (default: 4)
  VIRUSTOTAL_CACHE_TTL_SECONDS  result TTL in seconds (default: 86400 = 24 h)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib import error as _urllib_error, parse as _urllib_parse, request as _urllib_request


# ── helpers (no imports from url_reputation to avoid circular dependency) ──────

def _extract_domain(url: str) -> str:
    try:
        normalized = url.strip()
        if not normalized.lower().startswith(("http://", "https://")):
            normalized = f"http://{normalized}"
        return (_urllib_parse.urlsplit(normalized).hostname or "").lower().strip(".")
    except Exception:
        return ""


# ── result dataclass ────────────────────────────────────────────────────────────

@dataclass
class VirusTotalResult:
    """
    Output of a single VirusTotal URL check.

    status:
      "ok"             — VT responded with analysis stats
      "skipped"        — disabled or no API key
      "no_data"        — VT responded but no analysis stats yet
      "error"          — network or unexpected error
      "rate_limited"   — HTTP 429
      "quota_exceeded" — HTTP 429 with quota body, or HTTP 401/403

    risk_delta:
      Suggested score contribution for matched_signals reporting.
      Always 0 when status is not "ok".
    """
    status: str
    malicious: int = 0
    suspicious: int = 0
    harmless: int = 0
    undetected: int = 0
    total: int = 0
    risk_delta: int = 0
    arabic_reason: str = ""
    url_host: str = ""
    raw_stats: dict[str, Any] = field(default_factory=dict)


# ── risk-delta scoring ──────────────────────────────────────────────────────────

def _compute_risk_delta(malicious: int, suspicious: int, harmless: int) -> tuple[int, str]:
    """
    Map VT engine counts to (risk_delta, arabic_reason).

    risk_delta values (for matched_signals reporting only — actual score
    impact flows through the existing ProviderVerdict / _fuse() path):
      +35  multiple malicious engines (strong signal)
      +20  one or two malicious engines (moderate)
      +12  suspicious >= 2, no malicious (small/moderate)
      + 6  suspicious == 1, no malicious (small)
      - 2  clean/harmless, no flags (very slight reduction)
        0  no data
    """
    if malicious >= 3:
        return 35, "تم فحص الرابط عبر VirusTotal وظهرت مؤشرات خطورة من عدة محركات أمنية."
    if malicious in (1, 2):
        return 20, "أشار عدد من محركات VirusTotal إلى أن الرابط قد يكون خبيثاً أو مشبوهاً."
    if suspicious >= 2:
        return 12, "تم العثور على إشارات اشتباه مرتبطة بالرابط عبر VirusTotal."
    if suspicious == 1:
        return 6, "رصد أحد محركات VirusTotal إشارة اشتباه خفيفة مرتبطة بالرابط."
    if harmless > 0 and malicious == 0 and suspicious == 0:
        return -2, (
            "لم يتم العثور على سجل خطير للرابط في VirusTotal، "
            "لكن محتوى الرسالة ما زال يحتوي على مؤشرات حساسة."
        )
    return 0, ""


# ── in-memory cache entry ───────────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    expires_at: float
    result: VirusTotalResult


# ── service ─────────────────────────────────────────────────────────────────────

class VirusTotalService:
    """
    Standalone VirusTotal URL reputation client.

    Reads its own env-var config; uses its own in-memory cache so that
    VIRUSTOTAL_CACHE_TTL_SECONDS can be tuned independently of the shared
    URL reputation cache.
    """

    def __init__(self) -> None:
        api_key = os.getenv("VIRUSTOTAL_API_KEY", "").strip()
        enabled_raw = os.getenv("VIRUSTOTAL_ENABLED", "").strip().lower()
        if enabled_raw in ("false", "0", "no", "off"):
            self.enabled = False
        else:
            # Default: enabled when key is present
            self.enabled = bool(api_key)
        self.api_key = api_key
        self.timeout = float(os.getenv("VIRUSTOTAL_TIMEOUT_SECONDS", "4") or "4")
        self.cache_ttl = int(os.getenv("VIRUSTOTAL_CACHE_TTL_SECONDS", "86400") or "86400")
        self._cache: dict[str, _CacheEntry] = {}

    # ── public API ──────────────────────────────────────────────────────────────

    def check_url(self, url: str) -> VirusTotalResult:
        """
        Check a URL with VirusTotal.

        Never raises — all errors are surfaced as VirusTotalResult.status.
        risk_delta is 0 when status is not "ok".
        """
        domain = _extract_domain(url)
        if not self.enabled or not self.api_key:
            return VirusTotalResult(status="skipped", url_host=domain)

        cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > now:
            return cached.result

        result = self._query(url, domain)

        if result.status == "ok":
            self._cache[cache_key] = _CacheEntry(now + self.cache_ttl, result)
        return result

    def status(self) -> dict[str, Any]:
        now = time.time()
        live = sum(1 for e in self._cache.values() if e.expires_at > now)
        return {
            "virustotal_enabled": self.enabled,
            "virustotal_key_set": bool(self.api_key),
            "virustotal_timeout_seconds": self.timeout,
            "virustotal_cache_ttl_seconds": self.cache_ttl,
            "virustotal_cache_items": len(self._cache),
            "virustotal_cache_live": live,
        }

    # ── private ─────────────────────────────────────────────────────────────────

    def _query(self, url: str, domain: str) -> VirusTotalResult:
        url_id = base64.urlsafe_b64encode(url.encode("utf-8")).decode().strip("=")
        endpoint = f"https://www.virustotal.com/api/v3/urls/{url_id}"
        req = _urllib_request.Request(
            endpoint,
            headers={
                "x-apikey": self.api_key,
                "User-Agent": "APG-VirusTotal/1.0",
                "Accept": "application/json",
            },
        )
        try:
            with _urllib_request.urlopen(req, timeout=self.timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except _urllib_error.HTTPError as exc:
            if exc.code == 429:
                body = ""
                try:
                    body = exc.read().decode("utf-8", "ignore")
                except Exception:
                    pass
                if "quota" in body.lower():
                    return VirusTotalResult(status="quota_exceeded", url_host=domain)
                return VirusTotalResult(status="rate_limited", url_host=domain)
            if exc.code in (401, 403):
                return VirusTotalResult(status="quota_exceeded", url_host=domain)
            return VirusTotalResult(status="error", url_host=domain)
        except Exception:
            return VirusTotalResult(status="error", url_host=domain)

        stats: dict[str, Any] = (
            raw.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        )
        if not stats:
            return VirusTotalResult(status="no_data", url_host=domain)

        malicious = int(stats.get("malicious") or 0)
        suspicious = int(stats.get("suspicious") or 0)
        harmless = int(stats.get("harmless") or 0)
        undetected = int(stats.get("undetected") or 0)
        total = malicious + suspicious + harmless + undetected
        risk_delta, arabic_reason = _compute_risk_delta(malicious, suspicious, harmless)

        return VirusTotalResult(
            status="ok",
            malicious=malicious,
            suspicious=suspicious,
            harmless=harmless,
            undetected=undetected,
            total=total,
            risk_delta=risk_delta,
            arabic_reason=arabic_reason,
            url_host=domain,
            raw_stats=stats,
        )


# ── module-level singleton ──────────────────────────────────────────────────────

_service: VirusTotalService | None = None


def get_virustotal_service() -> VirusTotalService:
    global _service
    if _service is None:
        _service = VirusTotalService()
    return _service
