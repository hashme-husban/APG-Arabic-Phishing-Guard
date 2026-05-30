from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.models import AnalysisResult, ThreatIndicator

logger = logging.getLogger("apg.intelligence_memory")

_ALLOWED_TYPES = {"domain", "url_hash", "sender", "entity", "signal", "path"}
_SENSITIVE_KEYWORDS = {
    "otp",
    "password",
    "passwd",
    "passcode",
    "token",
    "secret",
    "cookie",
    "session",
    "authorization",
    "auth",
    "credential",
    "pin",
}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _looks_like_otp_or_secret(value: str) -> bool:
    compact = re.sub(r"\s+", "", value or "")
    if re.fullmatch(r"\d{4,8}", compact):
        return True
    lowered = value.lower()
    return any(f"{keyword}=" in lowered or f"{keyword}:" in lowered for keyword in _SENSITIVE_KEYWORDS)


def _split_url(value: str):
    text = value.strip()
    if not re.match(r"(?i)^[a-z][a-z0-9+.-]*://", text):
        text = f"http://{text}"
    return urlsplit(text)


def _normalized_url_without_query(value: str) -> str:
    parsed = _split_url(value)
    scheme = (parsed.scheme or "http").lower()
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, f"{host}{port}", path or "/", "", ""))


def normalize_indicator_value(indicator_type: str, value: Any) -> str:
    indicator_type = _as_text(indicator_type).lower()
    raw = _as_text(value)
    if indicator_type not in _ALLOWED_TYPES or not raw:
        return ""
    if indicator_type == "domain":
        try:
            parsed = _split_url(raw)
            return (parsed.hostname or raw).lower().strip(".")
        except Exception:
            return raw.lower().strip(".")
    if indicator_type == "url_hash":
        return _normalized_url_without_query(raw)
    if indicator_type == "path":
        try:
            parsed = _split_url(raw)
            path = re.sub(r"/{2,}", "/", parsed.path or "/")
            return path[:240].lower()
        except Exception:
            return raw.split("?", 1)[0].split("#", 1)[0].lower()[:240]
    if _looks_like_otp_or_secret(raw):
        return ""
    if indicator_type in {"sender", "entity", "signal"}:
        return re.sub(r"\s+", " ", raw).lower()[:240]
    return raw.lower()[:240]


def hash_indicator_value(value: Any) -> str:
    normalized = _as_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sanitize_display_value(indicator_type: str, value: Any) -> str:
    indicator_type = _as_text(indicator_type).lower()
    normalized = normalize_indicator_value(indicator_type, value)
    if not normalized:
        return ""
    if indicator_type == "url_hash":
        return normalized[:500]
    if indicator_type == "path":
        return normalized.split("?", 1)[0].split("#", 1)[0][:240]
    if indicator_type == "sender":
        if "@" in normalized:
            local, _, domain = normalized.partition("@")
            return f"{local[:2]}***@{domain}"[:240]
        if re.fullmatch(r"\+?\d[\d\s-]{6,}", normalized):
            return f"{normalized[:3]}***{normalized[-2:]}"[:80]
    return normalized[:240]


def record_indicator(
    db: Session,
    indicator_type: str,
    value: Any,
    *,
    risk_score: int | None = None,
    classification: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ThreatIndicator | None:
    try:
        indicator_type = _as_text(indicator_type).lower()
        normalized = normalize_indicator_value(indicator_type, value)
        if indicator_type not in _ALLOWED_TYPES or not normalized:
            return None
        value_hash = hash_indicator_value(normalized)
        display_value = sanitize_display_value(indicator_type, normalized)
        now = datetime.utcnow()
        item = (
            db.query(ThreatIndicator)
            .filter(
                ThreatIndicator.indicator_type == indicator_type,
                ThreatIndicator.value_hash == value_hash,
            )
            .first()
        )
        if item:
            item.seen_count += 1
            item.last_seen = now
            item.display_value = display_value or item.display_value
        else:
            item = ThreatIndicator(
                indicator_type=indicator_type,
                value_hash=value_hash,
                display_value=display_value,
                first_seen=now,
                last_seen=now,
                seen_count=1,
            )
            db.add(item)
        if risk_score is not None:
            item.max_risk_score = max(item.max_risk_score or 0, int(risk_score))
        if classification:
            item.last_classification = str(classification)[:30]
        if source:
            item.last_source = str(source)[:80]
        if tags:
            item.tags_json = sorted({str(tag)[:60] for tag in tags if str(tag).strip()})[:12]
        if metadata:
            item.metadata_json = {
                str(k)[:50]: str(v)[:160]
                for k, v in metadata.items()
                if v is not None and not _looks_like_otp_or_secret(str(v))
            }
        return item
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("intelligence_memory record_indicator skipped: %s", type(exc).__name__)
        return None


def _url_candidates(context: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    result = context.get("analysis_result")
    if getattr(result, "detected_url", None):
        urls.append(result.detected_url)
    for url in context.get("extra_urls") or []:
        if url:
            urls.append(str(url))
    debug = context.get("debug") or {}
    url_rep = debug.get("url_reputation") or {}
    for finding in url_rep.get("findings") or []:
        for key in ("url", "normalized_url", "final_url"):
            if finding.get(key):
                urls.append(str(finding[key]))
    return list(dict.fromkeys(urls))


def _record_url_indicators(db: Session, url: str, base: dict[str, Any]) -> None:
    try:
        parsed = _split_url(url)
        host = (parsed.hostname or "").lower().strip(".")
        if host:
            record_indicator(db, "domain", host, **base)
        clean_url = _normalized_url_without_query(url)
        if clean_url:
            record_indicator(db, "url_hash", clean_url, **base)
        if parsed.path and parsed.path not in {"", "/"}:
            record_indicator(db, "path", parsed.path, **base)
    except Exception:
        return


def record_analysis_indicators(
    db: Session,
    analysis_result_or_context: AnalysisResult | dict[str, Any],
    *,
    source: str,
) -> None:
    try:
        if isinstance(analysis_result_or_context, dict):
            context = analysis_result_or_context
            result = context.get("analysis_result")
        else:
            result = analysis_result_or_context
            context = {"analysis_result": result}
        if result is None:
            return
        base = {
            "risk_score": getattr(result, "risk_score", None),
            "classification": getattr(result, "classification", None),
            "source": source,
        }
        for url in _url_candidates(context):
            _record_url_indicators(db, url, base)
        sender = context.get("sender")
        if sender:
            record_indicator(db, "sender", sender, **base)
        debug = context.get("debug") or {}
        for entity in debug.get("entities") or []:
            record_indicator(db, "entity", entity, **base)
        for key in ("claimed_entity", "sender_entity", "domain_entity"):
            entity = debug.get(key)
            if entity:
                record_indicator(db, "entity", entity, **base)
        for signal in getattr(result, "matched_signals", []) or []:
            if isinstance(signal, dict):
                name = signal.get("name") or signal.get("id")
            else:
                name = str(signal)
            if name:
                record_indicator(db, "signal", name, **base)
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("intelligence_memory record_analysis skipped: %s", type(exc).__name__)


def cleanup_old_indicators(db: Session, *, retention_days: int, dry_run: bool = True) -> dict[str, Any]:
    retention_days = int(retention_days)
    if retention_days < 7:
        raise ValueError("retention_days must be at least 7")
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    query = db.query(ThreatIndicator).filter(ThreatIndicator.last_seen < cutoff)
    matched_count = query.count()
    deleted_count = 0
    if not dry_run and matched_count:
        deleted_count = query.delete(synchronize_session=False)
    return {
        "dry_run": bool(dry_run),
        "retention_days": retention_days,
        "cutoff_date": cutoff,
        "matched_count": matched_count,
        "deleted_count": deleted_count,
    }
