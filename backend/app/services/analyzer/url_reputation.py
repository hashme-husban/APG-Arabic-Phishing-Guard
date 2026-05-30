from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from .schemas import ProviderVerdict, Signal, URLFinding, URLReputationResult

URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)[^\s<>()\[\]{}\"']+|"
    r"\b(?:bit\.ly|tinyurl\.com|t\.co|rb\.gy|cutt\.ly|ow\.ly|goo\.gl|rebrand\.ly)/[^\s<>()\[\]{}\"']+"
)

SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "rb.gy",
    "cutt.ly",
    "ow.ly",
    "goo.gl",
    "rebrand.ly",
}
SUSPICIOUS_TLDS = {"xyz", "top", "click", "site", "online", "live", "rest", "cam", "work", "support", "quest", "gq", "tk", "ml", "cfd"}
BRAND_TERMS = {"bank", "paypal", "whatsapp", "facebook", "apple", "google", "secure", "login", "verify", "بنك", "واتساب"}
ACTION_URL_WORDS = {"login", "verify", "secure", "update", "confirm", "account", "bank", "otp", "signin", "auth", "wallet", "payment"}


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,،؛:)]}")
        if url not in urls:
            urls.append(url)
    return urls


def normalize_url(url: str) -> str:
    value = (url or "").strip()
    if value and not re.match(r"(?i)^https?://", value):
        value = f"http://{value}"
    parsed = parse.urlsplit(value)
    host = (parsed.hostname or "").lower().strip(".")
    scheme = parsed.scheme.lower() or "http"
    path = parsed.path or ""
    query = f"?{parsed.query}" if parsed.query else ""
    return parse.urlunsplit((scheme, host, path, query[1:] if query else "", ""))


def extract_domain(url: str) -> str:
    try:
        parsed = parse.urlsplit(normalize_url(url))
        return (parsed.hostname or "").lower().strip(".")
    except Exception:
        return ""


@dataclass
class _CacheEntry:
    expires_at: float
    result: URLFinding


class URLReputationService:
    def __init__(self) -> None:
        self.enabled = os.getenv("URL_REPUTATION_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.timeout_seconds = float(os.getenv("URL_REPUTATION_TIMEOUT_SECONDS", "4") or "4")
        self.cache_ttl = int(float(os.getenv("URL_REPUTATION_CACHE_TTL_HOURS", "12") or "12") * 3600)
        self._cache: dict[str, _CacheEntry] = {}

    def check_urls(self, urls: list[str], mock_verdicts: dict[str, Any] | None = None) -> URLReputationResult:
        unique = []
        for url in urls or []:
            if url and url not in unique:
                unique.append(url)
        findings = [self.check_url(url, mock_verdicts=mock_verdicts) for url in unique]
        return URLReputationResult(findings=findings, enabled=self.enabled, cache_status=self.cache_status())

    def check_url(self, url: str, mock_verdicts: dict[str, Any] | None = None) -> URLFinding:
        normalized = normalize_url(url)
        domain = extract_domain(normalized)
        cache_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > now and not mock_verdicts:
            return cached.result

        local_signals = self._local_signals(normalized, domain)
        provider_verdicts = self._mock_provider_verdicts(normalized, domain, mock_verdicts)
        final_url = None
        if not provider_verdicts and self.enabled:
            final_url, redirect_signal = self._expand_short_url(normalized, domain)
            if redirect_signal:
                local_signals.append(redirect_signal)
            checked_url = final_url or normalized
            provider_verdicts = [
                self._google_safe_browsing(checked_url),
                self._phishtank(checked_url),
                self._virustotal(checked_url),
                self._urlscan(checked_url),
            ]
        elif not self.enabled and not provider_verdicts:
            provider_verdicts = [ProviderVerdict("all", "skipped", "unknown", {"reason": "disabled"})]

        verdict, score = self._fuse(local_signals, provider_verdicts)
        finding = URLFinding(
            url=url,
            normalized_url=normalized,
            domain=domain,
            final_url=final_url,
            local_signals=local_signals,
            provider_verdicts=provider_verdicts,
            verdict=verdict,
            score=score,
        )
        if not mock_verdicts:
            self._cache[cache_key] = _CacheEntry(now + self.cache_ttl, finding)
        return finding

    def status(self) -> dict[str, Any]:
        return {
            "url_reputation_enabled": self.enabled,
            "providers_configured": self.providers_configured(),
            "cache_status": self.cache_status(),
            "cache_items": len(self._cache),
            "cache_ttl_hours": round(self.cache_ttl / 3600, 2),
        }

    def providers_configured(self) -> dict[str, bool]:
        return {
            "google_safe_browsing": bool(os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")),
            "virustotal": bool(os.getenv("VIRUSTOTAL_API_KEY")),
            "urlscan": bool(os.getenv("URLSCAN_API_KEY")),
            "phishtank": bool(os.getenv("PHISHTANK_API_KEY")),
        }

    def cache_status(self) -> str:
        if not self._cache:
            return "empty"
        now = time.time()
        live = sum(1 for entry in self._cache.values() if entry.expires_at > now)
        return f"memory:{live}/{len(self._cache)}"

    def _local_signals(self, url: str, domain: str) -> list[Signal]:
        signals: list[Signal] = []
        parsed = parse.urlsplit(url)
        path_query = f"{domain} {parsed.path} {parsed.query}".lower()
        if parsed.scheme == "http":
            signals.append(Signal("insecure_http_url", "suspicious", 42, "الرابط يستخدم HTTP وليس HTTPS.", domain))
        if domain in SHORTENER_DOMAINS:
            signals.append(Signal("shortened_url", "suspicious", 62, "الرابط مختصر وقد يخفي الوجهة الحقيقية.", domain))
        if domain.startswith("xn--") or ".xn--" in domain:
            signals.append(Signal("punycode_domain", "suspicious", 72, "النطاق يستخدم Punycode وقد يحاكي اسما موثوقا.", domain))
        try:
            ipaddress.ip_address(domain)
            signals.append(Signal("ip_address_url", "suspicious", 70, "الرابط يستخدم عنوان IP بدلا من نطاق واضح.", domain))
        except ValueError:
            pass
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        if tld in SUSPICIOUS_TLDS:
            signals.append(Signal("suspicious_tld", "suspicious", 62, "امتداد النطاق يرتبط كثيرا بحملات احتيالية.", domain))
        if len(domain.split(".")) >= 4:
            signals.append(Signal("many_subdomains", "suspicious", 54, "النطاق يحتوي على نطاقات فرعية كثيرة قد تخفي الوجهة.", domain))
        if any(word in path_query for word in ACTION_URL_WORDS):
            signals.append(Signal("suspicious_url_words", "suspicious", 56, "الرابط يحتوي كلمات مرتبطة بالدخول أو التحقق أو تحديث الحساب.", domain))
        registered = ".".join(domain.split(".")[-2:]) if "." in domain else domain
        if any(term in path_query for term in BRAND_TERMS) and not any(term in registered for term in BRAND_TERMS):
            signals.append(Signal("misleading_brand_in_url", "suspicious", 66, "الرابط يذكر علامة أو جهة حساسة خارج النطاق الأساسي.", domain))
        # Numeric digit substitution typosquatting (e.g., absh3r, sab1c, ahl1-bank)
        sld = domain.split(".")[-2] if domain.count(".") >= 1 else domain
        if re.search(r"[a-z][0-9]|[0-9][a-z]", sld):
            signals.append(Signal("numeric_domain_typosquat", "suspicious", 60, "النطاق يحتوي أرقاماً بدل حروف — مؤشر على انتحال اسم موقع موثوق.", domain))
        # Subdomain impersonation: trusted brand in subdomain of untrusted domain
        # e.g., inbank.alahli.com.evil.com  → real domain is evil.com
        parts = domain.split(".")
        if len(parts) >= 4:
            real_registered = ".".join(parts[-2:])
            subdomain_str = ".".join(parts[:-2]).lower()
            if any(term in subdomain_str for term in BRAND_TERMS):
                signals.append(Signal("brand_in_subdomain", "suspicious", 68, "النطاق يضع علامة موثوقة في النطاق الفرعي لإخفاء الوجهة الحقيقية.", domain))
        return signals

    def _expand_short_url(self, url: str, domain: str) -> tuple[str | None, Signal | None]:
        if domain not in SHORTENER_DOMAINS:
            return None, None
        try:
            opener = request.build_opener(_NoRedirectHandler)
            req = request.Request(url, method="HEAD", headers={"User-Agent": "APG-URL-Reputation/5.0"})
            opener.open(req, timeout=min(self.timeout_seconds, 2.0))
        except error.HTTPError as exc:
            location = exc.headers.get("Location")
            if location:
                return parse.urljoin(url, location), None
        except Exception:
            return None, Signal("short_url_expand_failed", "context", 0, "تعذر توسيع الرابط المختصر ضمن المهلة المحددة.", domain)
        return None, None

    def _mock_provider_verdicts(self, url: str, domain: str, mock_verdicts: dict[str, Any] | None) -> list[ProviderVerdict]:
        if not mock_verdicts:
            return []
        raw = mock_verdicts.get(url) or mock_verdicts.get(domain) or mock_verdicts.get("*")
        if raw is None:
            return [ProviderVerdict("mock", "skipped", "unknown")]
        if isinstance(raw, str):
            return [ProviderVerdict("mock", "ok", raw)]
        if isinstance(raw, dict):
            verdict = str(raw.get("verdict", raw.get("status", "unknown"))).lower()
            providers = raw.get("providers")
            if isinstance(providers, list):
                return [ProviderVerdict(str(p.get("provider", "mock")), str(p.get("status", "ok")), str(p.get("verdict", verdict)), dict(p)) for p in providers if isinstance(p, dict)]
            return [ProviderVerdict("mock", "ok", verdict, raw)]
        return [ProviderVerdict("mock", "error", "unknown", {"raw": str(raw)})]

    def _google_safe_browsing(self, url: str) -> ProviderVerdict:
        key = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")
        if not key:
            return ProviderVerdict("google_safe_browsing", "skipped")
        endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={parse.quote(key)}"
        body = {
            "client": {"clientId": "apg", "clientVersion": "5.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}],
            },
        }
        try:
            data = self._json_request(endpoint, body=body)
            return ProviderVerdict("google_safe_browsing", "ok", "malicious" if data.get("matches") else "clean", data)
        except Exception as exc:
            return ProviderVerdict("google_safe_browsing", "error", "unknown", error=str(exc))

    def _virustotal(self, url: str) -> ProviderVerdict:
        # Lazy import avoids circular dependency (virustotal_service imports
        # normalize_url/extract_domain helpers from this module).
        from app.services.virustotal_service import get_virustotal_service
        vt = get_virustotal_service()
        result = vt.check_url(url)

        if result.status == "skipped":
            return ProviderVerdict("virustotal", "skipped")
        if result.status in ("error", "rate_limited", "quota_exceeded", "no_data"):
            # Non-OK statuses must have zero risk effect.
            return ProviderVerdict("virustotal", result.status, "unknown",
                                   {"status": result.status})

        # Map engine counts → verdict used by _fuse() for score calculation.
        # Thresholds:
        #   malicious >= 3  → strong signal  (verdict: malicious  → score 98)
        #   malicious 1-2   → moderate       (verdict: suspicious → score 68+)
        #   suspicious >= 2 → small/moderate (verdict: suspicious → score 68+)
        #   suspicious == 1 → weak signal    (verdict: unknown    → neutral, no reduction)
        #   else            → clean          (verdict: clean      → score -4)
        if result.malicious >= 3:
            verdict = "malicious"
        elif result.malicious >= 1 or result.suspicious >= 2:
            verdict = "suspicious"
        elif result.suspicious == 1:
            verdict = "unknown"
        else:
            verdict = "clean"

        return ProviderVerdict("virustotal", "ok", verdict, {
            "stats": result.raw_stats,
            "malicious": result.malicious,
            "suspicious": result.suspicious,
            "harmless": result.harmless,
            "undetected": result.undetected,
            "total": result.total,
            "risk_delta": result.risk_delta,
            "arabic_reason": result.arabic_reason,
            "url_host": result.url_host,
        })

    def _urlscan(self, url: str) -> ProviderVerdict:
        key = os.getenv("URLSCAN_API_KEY")
        if not key:
            return ProviderVerdict("urlscan", "skipped")
        try:
            query = parse.urlencode({"q": f'page.url:"{url}"'})
            data = self._json_request(f"https://urlscan.io/api/v1/search/?{query}", headers={"API-Key": key})
            verdicts = []
            for item in data.get("results", [])[:5]:
                verdicts.append(item.get("verdicts", {}).get("overall", {}))
            if any(v.get("malicious") for v in verdicts):
                verdict = "malicious"
            elif any(v.get("score", 0) >= 50 or v.get("suspicious") for v in verdicts):
                verdict = "suspicious"
            else:
                verdict = "clean" if verdicts else "unknown"
            return ProviderVerdict("urlscan", "ok", verdict, {"verdicts": verdicts})
        except Exception as exc:
            return ProviderVerdict("urlscan", "error", "unknown", error=str(exc))

    def _phishtank(self, url: str) -> ProviderVerdict:
        key = os.getenv("PHISHTANK_API_KEY")
        if not key:
            return ProviderVerdict("phishtank", "skipped")
        try:
            body = parse.urlencode({"url": url, "format": "json", "app_key": key}).encode()
            data = self._json_request("https://checkurl.phishtank.com/checkurl/", raw_body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
            results = data.get("results", {})
            verdict = "malicious" if results.get("valid") and results.get("in_database") else "clean"
            return ProviderVerdict("phishtank", "ok", verdict, results)
        except Exception as exc:
            return ProviderVerdict("phishtank", "error", "unknown", error=str(exc))

    def _json_request(self, url: str, body: dict[str, Any] | None = None, raw_body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        payload = raw_body if raw_body is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        req_headers = {"User-Agent": "APG-URL-Reputation/5.0", **(headers or {})}
        if body is not None:
            req_headers["Content-Type"] = "application/json"
        req = request.Request(url, data=payload, headers=req_headers)
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8", "replace") or "{}")

    def _fuse(self, local_signals: list[Signal], providers: list[ProviderVerdict]) -> tuple[str, int]:
        if any(p.verdict == "malicious" for p in providers if p.status == "ok"):
            return "malicious", 98
        if any(p.verdict == "suspicious" for p in providers if p.status == "ok"):
            return "suspicious", max(68, max((s.weight for s in local_signals), default=0))
        local_score = max((s.weight for s in local_signals), default=0)
        if local_score >= 62:
            return "suspicious", local_score
        clean_count = sum(1 for p in providers if p.status == "ok" and p.verdict == "clean")
        # Threshold raised from 50 → 62: a confirmed-clean provider verdict now
        # overrides weak local heuristics (http=42, payment-words=56, etc.).
        # Signals at 62+ (shortened URL, suspicious TLD, punycode, IP, brand) are
        # strong enough to remain "suspicious" even when VT reports clean.
        if clean_count and local_score < 62:
            return "clean", max(5, local_score)
        return "unknown", local_score


class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None
