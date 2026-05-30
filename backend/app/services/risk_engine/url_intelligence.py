"""
APG Risk Intelligence Engine v1 — URL Intelligence

Wraps the v5 URLReputationService and converts its output into the richer
URLIntelligence dataclass used by the risk engine.

Design principles:
  - URL checking is delegated entirely to the proven v5 service (same provider
    integrations, SSRF protection, cache, signal detection).
  - This module converts the v5 URLFinding / URLReputationResult output into
    structured Evidence items used by the evidence builder and policy engine.
  - Privacy notes are added when external providers were consulted.
  - Link-reference text (e.g., "اضغط على الرابط" without an actual URL) is
    detected and surfaced as has_link_reference.
"""
from __future__ import annotations

import re
from typing import Any
from urllib import parse

from app.services.analyzer.normalizer import contains_any, n_terms
from app.services.analyzer.url_reputation import (
    URLReputationService as _URLReputationService,
    extract_domain,
    extract_urls,
)
from app.services.entity_registry import get_registry
from .schemas import Evidence, URLIntelligence

# Normalised link-reference terms (no explicit URL, just a pointer)
_LINK_REFERENCE_TERMS = n_terms([
    "رابط", "الرابط", "اضغط", "افتح الرابط", "ادخل عبر الرابط",
    "اضغط هنا", "انقر هنا", "click", "link", "open",
    "الرابط أدناه", "الرابط التالي",
])

# Map from v5 signal name → boolean flag on URLIntelligence
_FLAG_SIGNALS = {
    "shortened_url": "shortener_detected",
    "ip_address_url": "ip_url_detected",
    "punycode_domain": "punycode_detected",
    "suspicious_tld": "suspicious_tld",
    "misleading_brand_in_url": "brand_impersonation",
}

_LOGIN_VERIFICATION_WORDS = {
    "login",
    "signin",
    "sign-in",
    "verify",
    "verification",
    "secure",
    "security",
    "update",
    "confirm",
    "auth",
    "account",
    "validate",
    "unlock",
    "recover",
    "reset",
    "support",
    "helpdesk",
}

_PAYMENT_BANKING_WORDS = {
    "pay",
    "payment",
    "billing",
    "invoice",
    "wallet",
    "bank",
    "card",
    "visa",
    "master",
    "iban",
    "transfer",
}

_BRAND_ACTION_WORDS = _LOGIN_VERIFICATION_WORDS | _PAYMENT_BANKING_WORDS | {
    "claim",
    "delivery",
    "fee",
    "prize",
    "suspend",
    "limited",
}

_MODERATE_TLDS = {
    "xyz",
    "top",
    "shop",
    "click",
    "live",
    "support",
    "icu",
    "site",
    "online",
    "info",
    "net",
    "win",
}

_SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "cutt.ly",
    "t.co",
    "shorturl.at",
    "is.gd",
    "rebrand.ly",
    "ow.ly",
}

_KNOWN_BRANDS: dict[str, tuple[str, ...]] = {
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com"),
    "paypal": ("paypal.com", "py.pl"),
    "apple": ("apple.com", "icloud.com"),
    "google": ("google.com", "google.jo", "gmail.com", "forms.gle"),
    "whatsapp": ("whatsapp.com", "wa.me"),
    "amazon": ("amazon.com", "amazon.ae", "amazon.sa"),
    "aramex": ("aramex.com",),
    "dhl": ("dhl.com",),
    "fedex": ("fedex.com",),
    "zain": ("zain.jo", "zain.com", "zain.com.sa", "zaincash.jo", "zaincashjo.com"),
    "orange": ("orange.jo", "digital.orange.jo", "coursat.orange.jo", "orangecodingacademy.com"),
    "umniah": ("umniah.com", "umn.jo"),
    "stc": ("stc.com.sa", "stc.com.kw", "stc.com.bh", "my.stc", "my.stc.com.sa"),
    "arab-bank": ("arabbank.jo",),
    "cairo-amman-bank": ("cab.jo", "cairoammanbank.com"),
    "payoneer": ("payoneer.com",),
}

_BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "instagram": ("instagram", "insta", "انستغرام", "انستجرام", "إنستغرام"),
    "facebook": ("facebook", "fb", "فيسبوك", "فيس بوك"),
    "paypal": ("paypal", "pay pal", "باي بال", "بايبال"),
    "apple": ("apple", "icloud", "ابل", "آبل"),
    "google": ("google", "gmail", "جوجل", "غوغل", "قوقل"),
    "whatsapp": ("whatsapp", "whats app", "واتساب", "واتس اب", "واتسآب"),
    "amazon": ("amazon", "امازون", "أمازون"),
    "aramex": ("aramex", "ارامكس", "أرامكس"),
    "dhl": ("dhl", "دي اتش ال", "دي إتش إل"),
    "fedex": ("fedex", "fed ex", "فيديكس"),
    "zain": ("zain", "zain jo", "زين"),
    "orange": ("orange", "orange jo", "اورنج", "أورنج"),
    "umniah": ("umniah", "umnia", "امنية", "أمنية"),
    "stc": ("stc", "اس تي سي", "إس تي سي"),
    "arab-bank": ("arab bank", "arabbank", "البنك العربي"),
    "cairo-amman-bank": (
        "cairo amman bank",
        "cairoammanbank",
        "cairo amman",
        "cab",
        "بنك القاهرة عمان",
    ),
    "payoneer": ("payoneer", "بايونير"),
}

_TRUSTED_DOMAINS = {
    official
    for official_domains in _KNOWN_BRANDS.values()
    for official in official_domains
}


def _registry_domain_candidates(domain: str) -> list[dict[str, Any]]:
    return get_registry().find_entities_by_domain(domain)


def _registry_entity_ids_for_domain(domain: str) -> set[str]:
    return {
        candidate.get("entity_id", "")
        for candidate in _registry_domain_candidates(domain)
        if candidate.get("entity_id")
    }


def registry_brand_candidates_count() -> int:
    """Return registry entities with official domains available to URL brand checks."""
    registry = get_registry()
    return sum(
        1
        for entity in getattr(registry, "_entities", [])
        if entity.get("official_domains")
    )


def _normalize_claim_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub("[\u0640]", "", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    return text


def _registered_domain(domain: str) -> str:
    parts = [p for p in (domain or "").lower().strip(".").split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    return ".".join(parts[-2:])


def _is_same_or_subdomain(domain: str, official: str) -> bool:
    domain = (domain or "").lower().strip(".")
    official = (official or "").lower().strip(".")
    return bool(domain and official and (domain == official or domain.endswith(f".{official}")))


def _is_trusted_domain(domain: str) -> bool:
    return (
        any(_is_same_or_subdomain(domain, official) for official in _TRUSTED_DOMAINS)
        or bool(_registry_domain_candidates(domain))
    )


def _url_parts(url: str, domain: str) -> tuple[str, str, str]:
    parsed = parse.urlsplit(url if re.match(r"(?i)^https?://", url or "") else f"http://{url}")
    host = (parsed.hostname or domain or "").lower().strip(".")
    path_query = f"{parsed.path} {parsed.query}".lower()
    domain_text = host.replace(".", "-").lower()
    return host, domain_text, path_query


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t}


def _brand_alias_in_text(brand: str, text: str) -> bool:
    normalized = _normalize_claim_text(text)
    ascii_tokens = _tokens(normalized)
    for alias in _BRAND_ALIASES.get(brand, (brand,)):
        norm_alias = _normalize_claim_text(alias)
        alias_tokens = _tokens(norm_alias)
        if alias_tokens:
            if all(token in ascii_tokens for token in alias_tokens):
                return True
            compact_alias = "".join(alias_tokens)
            compact_text = "".join(ascii_tokens)
            if compact_alias and compact_alias in compact_text:
                return True
        elif norm_alias and re.search(
            r"\b" + re.escape(norm_alias) + r"\b", normalized
        ):
            # Word-boundary guard: prevents short Arabic brand names (e.g. زين)
            # from matching as substrings inside longer Arabic words (e.g. المميزين).
            return True
    return False


def _brand_hit_in_surface(text: str) -> str | None:
    for brand in _KNOWN_BRANDS:
        if _brand_alias_in_text(brand, text):
            return brand
    return None


def _registry_surface_text(host: str, path_query: str, message_text: str) -> tuple[tuple[str, str], ...]:
    host_surface = (host or "").replace(".", " ").replace("-", " ")
    return (
        ("domain", host_surface),
        ("url_path", path_query or ""),
        ("message_text", message_text or ""),
    )


def _registry_claimed_brand(
    host: str,
    path_query: str,
    message_text: str,
) -> tuple[str | None, bool, str]:
    registry = get_registry()
    official_candidate_ids = _registry_entity_ids_for_domain(host)
    if official_candidate_ids:
        first = _registry_domain_candidates(host)[0]
        return first.get("entity_id"), True, "domain"

    for source, text in _registry_surface_text(host, path_query, message_text):
        match = registry.find_entity_by_alias(text)
        if match.get("matched") and match.get("entity_id"):
            entity_id = match["entity_id"]
            source_name = "domain" if source == "domain" else f"registry_{source}"
            return entity_id, entity_id in official_candidate_ids, source_name

    return None, False, ""


def _has_word(tokens: set[str], words: set[str]) -> bool:
    return bool(tokens & words)


def _looks_random(label: str) -> bool:
    label = (label or "").lower()
    if len(label) < 18:
        return False
    letters = re.sub(r"[^a-z0-9]", "", label)
    if len(letters) < 18:
        return False
    digit_count = sum(ch.isdigit() for ch in letters)
    vowel_count = sum(ch in "aeiou" for ch in letters)
    return digit_count >= 5 or vowel_count / max(len(letters), 1) < 0.22


def _brand_hit(domain: str) -> tuple[str | None, bool]:
    domain_text = (domain or "").lower().replace(".", "-")
    registered = _registered_domain(domain).replace(".", "-")
    labels = domain_text.split("-")
    for brand, official_domains in _KNOWN_BRANDS.items():
        brand_tokens = brand.split("-")
        brand_present = (
            brand in domain_text
            or all(token in labels for token in brand_tokens)
            or _brand_alias_in_text(brand, domain_text)
        )
        if not brand_present:
            continue
        official = any(_is_same_or_subdomain(domain, d) for d in official_domains)
        starts_with_brand = registered.startswith(brand.replace("-", ""))
        return brand, official or starts_with_brand and any(
            _is_same_or_subdomain(domain, d) for d in official_domains
        )
    return None, False


def _claimed_brand(
    host: str,
    path_query: str,
    message_text: str,
) -> tuple[str | None, bool, str]:
    brand, official = _brand_hit(host)
    if brand:
        return brand, official, "domain"

    for source, text in (("url_path", path_query), ("message_text", message_text)):
        brand = _brand_hit_in_surface(text)
        if brand:
            official = any(_is_same_or_subdomain(host, d) for d in _KNOWN_BRANDS[brand])
            return brand, official, source

    return _registry_claimed_brand(host, path_query, message_text)


def _evidence(
    evidence_id: str,
    severity: str,
    score_delta: int,
    confidence: float,
    matched_text: str,
    explanation_ar: str,
    explanation_en: str | None = None,
) -> Evidence:
    return Evidence(
        id=evidence_id,
        category="dangerous_intent" if severity == "critical" else "suspicious_context",
        severity=severity,  # type: ignore[arg-type]
        score_delta=score_delta,
        confidence=confidence,
        matched_text=matched_text,
        explanation_ar=explanation_ar,
        explanation_en=explanation_en,
    )


def _extra_url_evidence(
    url: str,
    domain: str,
    message_text: str = "",
) -> tuple[list[Evidence], dict[str, bool]]:
    host, domain_text, path_query = _url_parts(url, domain)
    trusted = _is_trusted_domain(host)
    domain_tokens = _tokens(domain_text)
    path_tokens = _tokens(path_query)
    all_tokens = domain_tokens | path_tokens
    registered = _registered_domain(host)
    sld = registered.split(".")[0] if registered else host.split(".")[0]
    tld = host.rsplit(".", 1)[-1] if "." in host else ""

    phishing_word = _has_word(all_tokens, _LOGIN_VERIFICATION_WORDS)
    payment_word = _has_word(all_tokens, _PAYMENT_BANKING_WORDS)
    brand_action_word = _has_word(all_tokens | _tokens(message_text), _BRAND_ACTION_WORDS)
    domain_phishing_word = _has_word(domain_tokens, _LOGIN_VERIFICATION_WORDS)
    suspicious_tld = tld in _MODERATE_TLDS
    shortener = host in _SHORTENER_DOMAINS
    brand, official_brand, brand_source = _claimed_brand(host, path_query, message_text)
    brand_impersonation = bool(brand and not official_brand)
    if brand_source == "registry_message_text" and not brand_action_word:
        brand_impersonation = False

    out: list[Evidence] = []
    flags = {
        "shortener_detected": shortener,
        "suspicious_tld": suspicious_tld,
        "brand_impersonation": brand_impersonation,
    }

    if trusted:
        return out, flags

    if phishing_word:
        out.append(_evidence(
            "url_login_verification_keywords",
            "low",
            34,
            0.72,
            host,
            "الرابط يحتوي كلمات مرتبطة بتسجيل الدخول أو التحقق.",
            "URL contains login, verification, security, or account-action words.",
        ))

    if payment_word:
        out.append(_evidence(
            "url_payment_banking_keywords",
            "low",
            36,
            0.72,
            host,
            "الرابط يحتوي كلمات مرتبطة بالدفع أو الخدمات البنكية.",
            "URL contains payment or banking words.",
        ))

    if suspicious_tld:
        out.append(_evidence(
            "url_moderate_suspicious_tld",
            "low",
            32,
            0.64,
            host,
            "الرابط يستخدم نطاقًا يحتاج تحققًا إضافيًا.",
            "URL uses a TLD that merits extra verification.",
        ))

    if shortener:
        out.append(_evidence(
            "url_shortener_moderate",
            "low",
            38,
            0.70,
            host,
            "الرابط يستخدم خدمة اختصار روابط.",
            "URL uses a link shortener.",
        ))

    hyphen_count = sld.count("-")
    too_many_subdomains = len(host.split(".")) >= 4
    random_label = _looks_random(sld)
    if hyphen_count >= 3 or too_many_subdomains or random_label:
        out.append(_evidence(
            "url_unusual_structure",
            "low",
            35,
            0.68,
            host,
            "بنية الرابط غير معتادة وتحتاج تحققًا.",
            "URL structure is unusual and needs verification.",
        ))

    if brand_impersonation and (domain_phishing_word or phishing_word or payment_word):
        out.append(_evidence(
            "url_brand_phishing_combo",
            "critical",
            88,
            0.90,
            host,
            "النطاق يجمع اسم جهة معروفة مع كلمات تحقق أو أمان.",
            "Known entity appears with login, verification, update, or payment wording outside its official domain.",
        ))
    elif brand_impersonation and suspicious_tld:
        out.append(_evidence(
            "url_brand_suspicious_tld",
            "high",
            74,
            0.82,
            host,
            "الرابط يحاول تقليد جهة معروفة ويستخدم نطاقاً يحتاج تحققاً إضافياً.",
            "Known entity appears outside its official domain on a suspicious TLD.",
        ))
    elif brand_impersonation and shortener:
        out.append(_evidence(
            "url_brand_shortener",
            "high",
            72,
            0.80,
            host,
            "الرابط يذكر جهة معروفة عبر رابط مختصر، ولا يمكن مطابقة النطاق الرسمي مباشرة.",
            "Known entity appears with a URL shortener, hiding the destination domain.",
        ))
    elif brand_impersonation and brand_source != "domain" and brand_action_word:
        out.append(_evidence(
            "url_claimed_brand_domain_mismatch",
            "high",
            76,
            0.84,
            host,
            "اسم الجهة المذكورة لا يطابق النطاق.",
            "Message or URL path claims a known entity, but the host is not an official domain for that entity.",
        ))
    elif brand_impersonation:
        out.append(_evidence(
            "url_brand_impersonation",
            "medium",
            58,
            0.78,
            host,
            "النطاق يذكر جهة معروفة خارج نطاقها الرسمي.",
            "Domain mentions a known brand outside its official domain.",
        ))

    weak_signal_count = sum([
        phishing_word,
        payment_word,
        suspicious_tld,
        shortener,
        hyphen_count >= 3,
        too_many_subdomains,
        random_label,
    ])
    if weak_signal_count >= 3 and (phishing_word or payment_word):
        out.append(_evidence(
            "url_compound_suspicious_patterns",
            "medium",
            64,
            0.78,
            host,
            "بنية الرابط غير معتادة وتحتاج تحققًا.",
            "Multiple URL-level suspicious patterns appear together.",
        ))

    return out, flags


def _trusted_only_suppressed_signals(finding: Any) -> bool:
    if not _is_trusted_domain(getattr(finding, "domain", "")):
        return False
    suppressible = {
        "suspicious_url_words",
        "misleading_brand_in_url",
        "brand_in_subdomain",
    }
    positive_signals = [
        s.name
        for s in getattr(finding, "local_signals", [])
        if getattr(s, "weight", 0) > 0
    ]
    return bool(positive_signals) and all(name in suppressible for name in positive_signals)


def _effective_verdict(url_result: Any) -> str:
    provider_verdicts = [
        p.verdict
        for finding in getattr(url_result, "findings", [])
        for p in getattr(finding, "provider_verdicts", [])
        if getattr(p, "status", "") == "ok"
    ]
    if "malicious" in provider_verdicts:
        return "malicious"
    if "suspicious" in provider_verdicts:
        return "suspicious"
    if getattr(url_result, "verdict", "unknown") != "suspicious":
        return getattr(url_result, "verdict", "unknown")

    findings = getattr(url_result, "findings", [])
    if findings and all(_trusted_only_suppressed_signals(f) for f in findings):
        return "clean" if "clean" in provider_verdicts else "unknown"
    return getattr(url_result, "verdict", "unknown")


def _signal_to_evidence(signal: Any, domain: str) -> Evidence:
    """Convert a v5 Signal into an Evidence item for the risk engine."""
    weight = signal.weight
    explanation_ar = signal.explanation_ar
    if signal.name == "suspicious_tld":
        weight = min(weight, 32)
        explanation_ar = "الرابط يستخدم نطاقًا يحتاج تحققًا إضافيًا."
    elif signal.name == "shortened_url":
        weight = min(weight, 38)
        explanation_ar = "الرابط يستخدم خدمة اختصار روابط."

    if signal.type == "danger":
        category: str = "dangerous_intent"
        severity: str = "critical" if weight >= 90 else "high"
    elif signal.type in {"suspicious", "warning"}:
        category = "suspicious_context"
        severity = "high" if weight >= 70 else "medium" if weight >= 50 else "low"
    elif signal.type == "safe":
        category = "safe_context"
        severity = "info"
    else:
        category = "url"
        severity = "info"

    return Evidence(
        id=f"url_{signal.name}",
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        score_delta=weight,
        confidence=0.85,
        matched_text=signal.evidence or domain,
        explanation_ar=explanation_ar,
        explanation_en=None,
    )


def _provider_verdict_to_evidence(pv: Any, domain: str) -> "Evidence | None":
    """
    Convert a ProviderVerdict (status=="ok") into an Evidence item.

    VirusTotal verdicts are handled specially to:
      - Use engine-count-aware Arabic reasons from the VT service
      - Include stats in Evidence.extra so they flow into matched_signals
    All other providers use the generic fallback.
    """
    if pv.provider == "virustotal":
        details: dict = pv.details or {}
        # Arabic reason provided by virustotal_service._compute_risk_delta();
        # fall back to generic text when missing (e.g. mock verdicts).
        if pv.verdict == "malicious":
            arabic = (
                details.get("arabic_reason")
                or "تم فحص الرابط عبر VirusTotal وظهرت مؤشرات خطورة من عدة محركات أمنية."
            )
            extra = {
                "type": "url_reputation",
                "provider": "virustotal",
                "malicious_count": details.get("malicious", 0),
                "suspicious_count": details.get("suspicious", 0),
                "harmless_count": details.get("harmless", 0),
                "undetected_count": details.get("undetected", 0),
                "risk_delta": details.get("risk_delta", 0),
                "url_host": details.get("url_host", domain),
            }
            return Evidence(
                id="url_virustotal_malicious",
                category="dangerous_intent",
                severity="critical",
                score_delta=98,
                confidence=0.95,
                matched_text=details.get("url_host", domain),
                explanation_ar=arabic,
                explanation_en="VirusTotal flagged this URL as malicious.",
                extra=extra,
            )
        if pv.verdict == "suspicious":
            arabic = (
                details.get("arabic_reason")
                or "تم العثور على إشارات اشتباه مرتبطة بالرابط عبر VirusTotal."
            )
            extra = {
                "type": "url_reputation",
                "provider": "virustotal",
                "malicious_count": details.get("malicious", 0),
                "suspicious_count": details.get("suspicious", 0),
                "harmless_count": details.get("harmless", 0),
                "undetected_count": details.get("undetected", 0),
                "risk_delta": details.get("risk_delta", 0),
                "url_host": details.get("url_host", domain),
            }
            return Evidence(
                id="url_virustotal_suspicious",
                category="suspicious_context",
                severity="high",
                score_delta=68,
                confidence=0.80,
                matched_text=details.get("url_host", domain),
                explanation_ar=arabic,
                extra=extra,
            )
        if pv.verdict == "clean":
            arabic = (
                details.get("arabic_reason")
                or "لم يتم العثور على سجل خطير للرابط في VirusTotal، "
                   "لكن محتوى الرسالة ما زال يحتوي على مؤشرات حساسة."
            )
            extra = {
                "type": "url_reputation",
                "provider": "virustotal",
                "malicious_count": details.get("malicious", 0),
                "suspicious_count": details.get("suspicious", 0),
                "harmless_count": details.get("harmless", 0),
                "undetected_count": details.get("undetected", 0),
                "risk_delta": details.get("risk_delta", 0),
                "url_host": details.get("url_host", domain),
            }
            return Evidence(
                id="url_virustotal_clean",
                category="safe_context",
                severity="info",
                score_delta=-4,
                confidence=0.70,
                matched_text=details.get("url_host", domain),
                explanation_ar=arabic,
                extra=extra,
            )
        # suspicious == 1, malicious == 0 → weak positive signal (never reduces risk)
        if pv.verdict == "unknown" and details.get("suspicious", 0) == 1 and details.get("malicious", 0) == 0:
            arabic = (
                details.get("arabic_reason")
                or "رصد أحد محركات VirusTotal إشارة اشتباه خفيفة مرتبطة بالرابط."
            )
            return Evidence(
                id="url_virustotal_weak_suspicious",
                category="suspicious_context",
                severity="low",
                score_delta=15,
                confidence=0.45,
                matched_text=details.get("url_host", domain),
                explanation_ar=arabic,
                extra={
                    "type": "url_reputation",
                    "provider": "virustotal",
                    "malicious_count": 0,
                    "suspicious_count": 1,
                    "harmless_count": details.get("harmless", 0),
                    "undetected_count": details.get("undetected", 0),
                    "risk_delta": details.get("risk_delta", 6),
                    "url_host": details.get("url_host", domain),
                },
            )
        # no-data / truly unknown from VT — no evidence, no risk effect
        return None

    # Generic fallback for all other providers
    if pv.verdict == "malicious":
        return Evidence(
            id=f"provider_{pv.provider}_malicious",
            category="dangerous_intent",
            severity="critical",
            score_delta=98,
            confidence=0.97,
            matched_text=domain,
            explanation_ar=f"مزود {pv.provider} أشار إلى أن الرابط خبيث أو تصيدي.",
            explanation_en=f"Provider {pv.provider} flagged URL as malicious.",
        )
    if pv.verdict == "suspicious":
        return Evidence(
            id=f"provider_{pv.provider}_suspicious",
            category="suspicious_context",
            severity="high",
            score_delta=68,
            confidence=0.80,
            matched_text=domain,
            explanation_ar=f"مزود {pv.provider} أشار إلى أن الرابط مشبوه.",
        )
    if pv.verdict == "clean":
        return Evidence(
            id=f"provider_{pv.provider}_clean",
            category="safe_context",
            severity="info",
            score_delta=-4,
            confidence=0.70,
            matched_text=domain,
            explanation_ar=f"مزود {pv.provider} لم يرصد مؤشراً خبيثاً معروفاً للرابط.",
        )
    return None


class URLIntelligenceAnalyzer:
    """
    Analyses URLs found in a message and returns a rich URLIntelligence object.

    Reuses the v5 URLReputationService for all provider calls and local
    heuristics; this class only translates the output format.
    """

    def __init__(self) -> None:
        self._service = _URLReputationService()

    def analyze(
        self,
        raw_text: str,
        normalized_text: str,
        extra_urls: list[str] | None = None,
        mock_verdicts: dict[str, Any] | None = None,
    ) -> URLIntelligence:
        # ── 1. Extract URLs ────────────────────────────────────────────────
        urls: list[str] = []
        seen: set[str] = set()
        for url in extract_urls(raw_text) + extract_urls(normalized_text):
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        for url in extra_urls or []:
            url = (url or "").strip()
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        link_reference = contains_any(normalized_text, _LINK_REFERENCE_TERMS)

        if not urls and not link_reference:
            return URLIntelligence()

        # ── 2. Check reputation ────────────────────────────────────────────
        url_result = self._service.check_urls(urls, mock_verdicts=mock_verdicts)

        primary_url = urls[0] if urls else None
        primary_domain = extract_domain(primary_url) if primary_url else None

        # ── 3. Convert signals → Evidence + set boolean flags ──────────────
        local_evidence: list[Evidence] = []
        flags: dict[str, bool] = {k: False for k in _FLAG_SIGNALS.values()}
        privacy_notes: list[str] = []

        for finding in url_result.findings:
            trusted_domain = _is_trusted_domain(finding.domain)
            signal_names = {s.name for s in finding.local_signals}
            for signal in finding.local_signals:
                if trusted_domain and signal.name in {
                    "suspicious_url_words",
                    "misleading_brand_in_url",
                    "brand_in_subdomain",
                }:
                    continue
                ev = _signal_to_evidence(signal, finding.domain)
                local_evidence.append(ev)
                flag_name = _FLAG_SIGNALS.get(signal.name)
                if flag_name:
                    flags[flag_name] = True

            extra_evidence, extra_flags = _extra_url_evidence(
                finding.normalized_url or finding.url,
                finding.domain,
                raw_text,
            )
            for ev in extra_evidence:
                if ev.id == "url_moderate_suspicious_tld" and "suspicious_tld" in signal_names:
                    continue
                if ev.id == "url_shortener_moderate" and "shortened_url" in signal_names:
                    continue
                local_evidence.append(ev)
            for flag_name, value in extra_flags.items():
                if flag_name in flags:
                    flags[flag_name] = flags[flag_name] or value

            # Provider verdict evidence
            for pv in finding.provider_verdicts:
                if pv.status == "ok":
                    ev = _provider_verdict_to_evidence(pv, finding.domain)
                    if ev is not None:
                        local_evidence.append(ev)
                # Add privacy note for real (non-mock) external checks
                if pv.status == "ok" and pv.provider not in {"mock", "all"}:
                    note = "تم إرسال الرابط إلى مزودي التحقق الخارجيين."
                    if note not in privacy_notes:
                        privacy_notes.append(note)

        return URLIntelligence(
            extracted_urls=urls,
            primary_url=primary_url,
            primary_domain=primary_domain,
            has_url=bool(urls),
            has_link_reference=link_reference,
            verdict=_effective_verdict(url_result),
            provider_verdicts=[p.__dict__ for f in url_result.findings for p in f.provider_verdicts],
            local_evidence=local_evidence,
            shortener_detected=flags["shortener_detected"],
            ip_url_detected=flags["ip_url_detected"],
            punycode_detected=flags["punycode_detected"],
            suspicious_tld=flags["suspicious_tld"],
            brand_impersonation=flags["brand_impersonation"],
            privacy_notes=privacy_notes,
        )

    def check_url_direct(self, url: str, mock_verdicts: dict[str, Any] | None = None) -> dict[str, Any]:
        """Passthrough for admin URL check endpoint."""
        return self._service.check_url(url, mock_verdicts=mock_verdicts).__dict__  # type: ignore[attr-defined]
