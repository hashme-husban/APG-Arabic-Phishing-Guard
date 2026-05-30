"""
APG Entity Policy Engine

Inspects entity_intelligence (from ClaimedEntityExtractor) against active
message intents, URL reputation, and the full entity record from jo_entities.json
to produce:
  - Entity-specific Evidence items (injected into the evidence list BEFORE
    the policy engine's Phase 1 block check)
  - entity_policy_violations: list[str] of violation labels (debug output)

VT precedence guarantee
-----------------------
  Rule 1 (forbidden requests) is an additive dangerous_intent evidence item.
  It ENRICHES explanations / matched_signals but does NOT alter or bypass the
  existing block rules — Phase 1 fires on intents flags directly, independent
  of the evidence list, so VirusTotal malicious URL → block still fires first.

  Rule 3 (official domain alignment, a safe_context benefit) is fully
  suppressed when url_intel.verdict is "malicious" or "suspicious", when
  brand_impersonation is detected, or when URL deception flags are set.
  This means a VT-confirmed malicious URL can NEVER be made safe by entity
  alignment.

Unknown / missing entity
------------------------
  No evidence or violations are generated when entity_intelligence has no
  matched entities.  Unknown senders / domains are not penalised by this layer.
"""
from __future__ import annotations

from typing import Any

from app.services.analyzer.schemas import IntentResult
from app.services.entity_registry import get_registry
from .schemas import Evidence, URLIntelligence

# ─── Forbidden-request → IntentResult flag mapping ────────────────────────────
# Maps every distinct value that appears in jo_entities.json "forbidden_requests"
# arrays to the corresponding IntentResult boolean flag.

_FORBIDDEN_TO_FLAG: dict[str, str] = {
    # OTP / verification codes
    "otp_code":                   "otp_request",
    "bank_otp_code":              "otp_request",   # telecom variant
    # Passwords / PINs
    "password":                   "password_request",
    "sanad_password":             "password_request",
    "online_banking_password":    "password_request",
    "bank_password":              "password_request",
    "wallet_password":            "password_request",
    "wallet_pin":                 "password_request",
    "account_pin":                "password_request",
    # Card / payment data
    "cvv":                        "card_data_request",
    "card_number":                "card_data_request",
    "card_pin":                   "card_data_request",
    # Generic credentials
    "secure_key":                 "credential_request",
    "recovery_code":              "credential_request",
    "two_factor_backup_code":     "credential_request",
    "transfer_code":              "credential_request",
}

_SAFE_AWARENESS_INTENTS: frozenset[str] = frozenset({
    "security_advice",
    "otp_code",
})

_SAFE_AWARENESS_HINTS: tuple[str, ...] = (
    "لا يطلب",
    "لا تطلب",
    "لا تشارك",
    "لا ترسل",
    "لا تدخل",
    "لا تعطي",
    "لا تزود",
    "احذر",
    "يحذر",
    "تنبيه",
    "نصيحة",
    "توعية",
    "تذكير",
    "beware",
    "never share",
    "never enter",
    "do not share",
    "do not enter",
    "does not ask",
    "reminds",
)

_DIRECT_COMMAND_HINTS: tuple[str, ...] = (
    "أرسل",
    "ارسل",
    "أدخل",
    "ادخل",
    "زودنا",
    "send",
    "enter",
)

_OTP_DIRECT_REQUEST_HINTS: tuple[str, ...] = (
    "أرسل رمز",
    "ارسل رمز",
    "أرسل كود",
    "ارسل كود",
    "زودنا برمز",
    "زودنا بالكود",
    "زودنا بكود",
    "أدخل رمز",
    "ادخل رمز",
    "أدخل كود",
    "ادخل كود",
    "رمز الدخول",
    "كود الدخول",
    "رمز التحقق",
    "كود التحقق",
    "كود واتساب",
    "رمز واتساب",
    "send otp",
    "send code",
    "enter code",
    "otp code",
)

_PASSWORD_DIRECT_REQUEST_HINTS: tuple[str, ...] = (
    "أدخل كلمة المرور",
    "ادخل كلمة المرور",
    "أدخل كلمه المرور",
    "ادخل كلمه المرور",
    "أدخل كلمة السر",
    "ادخل كلمة السر",
    "أدخل كلمه السر",
    "ادخل كلمه السر",
    "أدخل كلمة سر",
    "ادخل كلمة سر",
    "أدخل كلمه سر",
    "ادخل كلمه سر",
    "كلمة المرور",
    "كلمه المرور",
    "كلمة السر",
    "كلمه السر",
    "كلمة سر",
    "كلمه سر",
    "password",
)

_CARD_DIRECT_REQUEST_HINTS: tuple[str, ...] = (
    "cvv",
    "cvc",
    "رقم البطاقة",
    "بيانات البطاقة",
    "رمز البطاقة",
    "card number",
    "card data",
)


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    folded = (text or "").casefold()
    return any(hint.casefold() in folded for hint in hints)


def _is_safe_awareness_context(
    text: str,
    intents: IntentResult,
    message_intent: str,
) -> bool:
    folded = (text or "").casefold()
    has_safe_context = (
        message_intent in _SAFE_AWARENESS_INTENTS
        or intents.awareness
        or bool(intents.safe_context)
        or _contains_any(text, _SAFE_AWARENESS_HINTS)
    )
    if not has_safe_context:
        return False
    if any(
        hint in folded
        for hint in (
            "do not enter",
            "do not share",
            "never enter",
            "never share",
            "does not ask",
        )
    ):
        return True
    if _contains_any(text, _DIRECT_COMMAND_HINTS):
        return False
    return _contains_any(text, _SAFE_AWARENESS_HINTS)


def _direct_forbidden_request_detected(forbidden: str, text: str) -> bool:
    if forbidden in {"otp_code", "bank_otp_code"}:
        return _contains_any(text, _OTP_DIRECT_REQUEST_HINTS)
    if forbidden in {
        "password",
        "sanad_password",
        "online_banking_password",
        "bank_password",
        "wallet_password",
        "wallet_pin",
        "account_pin",
    }:
        return _contains_any(text, _PASSWORD_DIRECT_REQUEST_HINTS)
    if forbidden in {"cvv", "card_number", "card_pin"}:
        return _contains_any(text, _CARD_DIRECT_REQUEST_HINTS)
    if forbidden in {"secure_key", "recovery_code", "two_factor_backup_code", "transfer_code"}:
        return (
            _contains_any(text, _OTP_DIRECT_REQUEST_HINTS)
            or _contains_any(text, _PASSWORD_DIRECT_REQUEST_HINTS)
        )
    return False

# ─── Human-readable entity type labels (Arabic) ───────────────────────────────

_ENTITY_TYPE_AR: dict[str, str] = {
    "bank":                   "جهة مالية أو بنك",
    "telecom":                "شركة اتصالات",
    "government":             "جهة حكومية",
    "e_wallet":               "محفظة إلكترونية",
    "payment_gateway":        "بوابة دفع إلكتروني",
    "payment_network":        "شبكة دفع",
    "social_platform":        "منصة اجتماعية",
    "streaming_subscription": "منصة اشتراكات",
    "technology":             "شركة تقنية",
    "insurance":              "شركة تأمين",
    "ecommerce":              "متجر إلكتروني",
    "retail":                 "متجر أو تجزئة",
    "utilities":              "خدمة عامة",
    "delivery_logistics":     "خدمة توصيل",
    "ride_hailing":           "تطبيق مواصلات",
    "financial":              "جهة مالية",
}


# ─── Candidate entity collector ───────────────────────────────────────────────

def _unique_candidates(entity_intelligence: dict[str, Any]) -> list[dict[str, Any]]:
    """Return unique entity match dicts from all slots, deduped by entity_id."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for key in ("claimed_entity", "sender_entity", "domain_entity", "alias_entity"):
        e = entity_intelligence.get(key)
        if e and e.get("entity_id") and e["entity_id"] not in seen:
            seen.add(e["entity_id"])
            out.append(e)
    return out


# ─── Rule helpers ─────────────────────────────────────────────────────────────

def _forbidden_request_evidence(
    entity_match: dict[str, Any],
    intents: IntentResult,
    normalized_text: str = "",
    message_intent: str = "unknown",
) -> tuple[Evidence | None, str | None]:
    """
    Check whether *entity_match* has forbidden_requests that overlap with active
    intents.  Returns (Evidence, violation_id) or (None, None).
    """
    entity_id = entity_match.get("entity_id", "")
    entity_type = entity_match.get("entity_type", "")
    entity_name = entity_match.get("entity_name", "")

    registry = get_registry()
    full = registry.get_entity(entity_id)
    if not full:
        return None, None

    if _is_safe_awareness_context(normalized_text, intents, message_intent):
        return None, None

    triggered: list[str] = []
    for forbidden in full.get("forbidden_requests", []):
        flag = _FORBIDDEN_TO_FLAG.get(forbidden)
        flag_triggered = bool(flag and getattr(intents, flag, False))
        direct_triggered = _direct_forbidden_request_detected(forbidden, normalized_text)
        if flag_triggered or direct_triggered:
            if forbidden not in triggered:
                triggered.append(forbidden)

    if not triggered:
        return None, None

    type_ar = _ENTITY_TYPE_AR.get(entity_type, entity_type)
    viol_id = f"entity_policy_forbidden_{entity_id}"

    ev = Evidence(
        id=viol_id,
        category="dangerous_intent",
        severity="critical",
        score_delta=90,
        confidence=0.93,
        matched_text=entity_name,
        explanation_ar=(
            f"تدّعي الرسالة أنها من {type_ar} ({entity_name}) "
            "وتطلب رمز تحقق أو بيانات حساسة، وهذا يخالف سياسة الجهة."
        ),
        explanation_en=(
            f"Message claims to be from {entity_name} ({entity_type}) "
            "and requests sensitive data that this entity type is forbidden to request."
        ),
        extra={"entity_id": entity_id, "triggered_forbidden": triggered},
    )
    return ev, viol_id


# ─── Main evaluation function ─────────────────────────────────────────────────

def evaluate_entity_policy(
    entity_intelligence: dict[str, Any],
    intents: IntentResult,
    url_intel: URLIntelligence,
    message_intent: str = "unknown",
    normalized_text: str = "",
) -> tuple[list[Evidence], list[str]]:
    """
    Evaluate entity-aware policy rules.

    Returns:
      evidence   — Evidence items to be appended to the main evidence list
                   BEFORE the policy engine's Phase 1 block check.
      violations — Stable string labels for debug output
                   (exposed as entity_policy_violations in the response).

    Parameters
    ----------
    entity_intelligence : output of ClaimedEntityExtractor.extract()
    intents             : output of ActionDetectorAdapter.detect()
    url_intel           : output of URLIntelligenceAnalyzer.analyze()
    message_intent      : consumer-friendly intent label (detect_message_intent)
    """
    evidence: list[Evidence] = []
    violations: list[str] = []

    if not entity_intelligence:
        return evidence, violations

    # ── Rule 1: Forbidden sensitive request ───────────────────────────────────
    # Check every unique matched entity.  This covers:
    #   • The authoritative claimed entity (sender/domain/alias by priority)
    #   • The "impersonated" entity when an alias conflict is present
    #     (e.g. sender=Zain but text claims Etihad Bank → also check Etihad Bank)
    seen_violations: set[str] = set()
    for candidate in _unique_candidates(entity_intelligence):
        ev, viol_id = _forbidden_request_evidence(
            candidate,
            intents,
            normalized_text=normalized_text,
            message_intent=message_intent,
        )
        if ev and viol_id and viol_id not in seen_violations:
            seen_violations.add(viol_id)
            evidence.append(ev)
            violations.append(viol_id)

    # ── Rule 2: Entity conflict evidence ─────────────────────────────────────
    sender_e = entity_intelligence.get("sender_entity")
    domain_e = entity_intelligence.get("domain_entity")
    domain_candidate_ids = set(entity_intelligence.get("domain_entity_ids") or [])
    alias_e = entity_intelligence.get("alias_entity")
    domain_conflict = entity_intelligence.get("domain_conflict", False)
    alias_conflict = entity_intelligence.get("alias_conflict", False)

    # Rule 2a: sender → domain conflict (URL belongs to a different org)
    if domain_conflict and sender_e and domain_e:
        sender_name = sender_e.get("entity_name", "")
        domain_name = domain_e.get("entity_name", "")
        viol_id = "entity_conflict_sender_domain"
        violations.append(viol_id)
        evidence.append(Evidence(
            id=viol_id,
            category="suspicious_context",
            severity="high",
            score_delta=55,
            confidence=0.85,
            matched_text=f"{sender_name} / {domain_name}",
            explanation_ar=(
                "يوجد تعارض بين هوية المرسل والجهة المذكورة في الرسالة."
            ),
            explanation_en=(
                f"Sender claims to be {sender_name} but the URL domain "
                f"belongs to {domain_name} — identity mismatch."
            ),
            extra={
                "sender_entity_id": sender_e.get("entity_id"),
                "domain_entity_id": domain_e.get("entity_id"),
            },
        ))

    # Rule 2b: sender → alias/text conflict (message text mentions a different org)
    if alias_conflict and sender_e and alias_e and not domain_conflict:
        sender_name = sender_e.get("entity_name", "")
        alias_name = alias_e.get("entity_name", "")
        viol_id = "entity_conflict_sender_text"
        violations.append(viol_id)
        evidence.append(Evidence(
            id=viol_id,
            category="suspicious_context",
            severity="medium",
            score_delta=45,
            confidence=0.78,
            matched_text=f"{sender_name} / {alias_name}",
            explanation_ar=(
                "يوجد تعارض بين هوية المرسل والجهة المذكورة في الرسالة."
            ),
            explanation_en=(
                f"Sender is identified as {sender_name} but the message "
                f"text claims to be from {alias_name}."
            ),
            extra={
                "sender_entity_id": sender_e.get("entity_id"),
                "alias_entity_id": alias_e.get("entity_id"),
            },
        ))

    # ── Rule 3: Official domain alignment (positive safe signal) ─────────────
    # Suppressed entirely when VT says malicious/suspicious or any URL deception
    # flag is set.  This ensures VT malicious verdict is NEVER overridden.
    claimed = entity_intelligence.get("claimed_entity")
    claimed_id = claimed.get("entity_id") if claimed else None
    if (
        claimed
        and domain_e
        and (
            claimed_id == domain_e.get("entity_id")
            or claimed_id in domain_candidate_ids
        )
        and domain_e.get("match_source") == "domain"
        and url_intel.verdict not in ("malicious", "suspicious")
        and not url_intel.brand_impersonation
        and not url_intel.ip_url_detected
        and not url_intel.punycode_detected
        and not url_intel.suspicious_tld
    ):
        entity_name = claimed.get("entity_name", "")
        evidence.append(Evidence(
            id="entity_official_domain_alignment",
            category="safe_context",
            severity="info",
            score_delta=-8,
            confidence=0.82,
            matched_text=domain_e.get("entity_id", ""),
            explanation_ar=(
                "الرابط يتبع النطاق الرسمي للجهة المذكورة، "
                "ولم تظهر مؤشرات خطورة من فحص الرابط."
            ),
            explanation_en=(
                f"URL domain matches the official domain of {entity_name} "
                "with no reputation threat signals detected."
            ),
        ))

    return evidence, violations
