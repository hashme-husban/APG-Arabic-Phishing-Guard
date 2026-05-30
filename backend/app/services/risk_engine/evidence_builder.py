"""
APG Risk Intelligence Engine v1 — Evidence Builder

Converts the outputs of all detection subsystems into a unified, structured
Evidence list.  Detectors PRODUCE evidence; they do NOT decide the final
score.  That is the policy engine's job.

Each piece of evidence carries:
  - A stable id (used for deduplication and policy lookups)
  - category / severity (for filtering in the UI)
  - score_delta (advisory contribution; policy engine may override)
  - matched_text (what triggered it)
  - explanation_ar / explanation_en

Evidence from:
  1. Entity detection  → category="entity", severity="info", score_delta=0
  2. Safe context      → category="safe_context", score_delta=0..12
  3. Dangerous intent  → category="dangerous_intent", score_delta=85..98
  4. Suspicious ctx    → category="suspicious_context", score_delta=40..70
  5. URL analysis      → delegated to URLIntelligence.local_evidence
  6. Sender trust      → delegated to SenderAssessment.evidence
  7. AI advisory       → delegated to AIAssessment.evidence
"""
from __future__ import annotations

from app.services.analyzer.schemas import EntityResult, IntentResult
from .schemas import Evidence, URLIntelligence, SenderAssessment, AIAssessment

# ── Entity-level evidence (informational; score_delta = 0) ────────────────────

_ENTITY_LABELS: dict[str, tuple[str, str]] = {
    "otp":               ("entity_otp",       "تم رصد رمز تحقق (OTP) — وحده لا يكفي لتصنيف الرسالة."),
    "password":          ("entity_password",   "تم رصد إشارة لكلمة مرور — وحده لا يكفي لتصنيف الرسالة."),
    "pin":               ("entity_pin",        "تم رصد إشارة لرقم سري — وحده لا يكفي لتصنيف الرسالة."),
    "card":              ("entity_card",       "تم رصد إشارة لبيانات بطاقة — وحده لا يكفي لتصنيف الرسالة."),
    "cvv":               ("entity_cvv",        "تم رصد إشارة لـ CVV/CVC — وحده لا يكفي لتصنيف الرسالة."),
    "bank":              ("entity_bank",       "تذكر الرسالة جهة مالية أو بنكاً."),
    "account":           ("entity_account",    "تذكر الرسالة حساباً أو ملفاً للمستخدم."),
    "money_transaction": ("entity_money",      "تذكر الرسالة عملية مالية أو رصيداً."),
    "whatsapp":          ("entity_whatsapp",   "تذكر الرسالة واتساب."),
    "iban":              ("entity_iban",       "تذكر الرسالة رقم IBAN — كيان مالي حساس."),
}


def build_entity_evidence(entities: EntityResult) -> list[Evidence]:
    out: list[Evidence] = []
    for ent in sorted(entities.entities):
        if ent in _ENTITY_LABELS:
            eid, explanation = _ENTITY_LABELS[ent]
            out.append(Evidence(
                id=eid,
                category="entity",
                severity="info",
                score_delta=0,
                confidence=0.95,
                matched_text=ent,
                explanation_ar=explanation,
            ))
    if entities.urls:
        out.append(Evidence(
            id="entity_url_detected",
            category="entity",
            severity="info",
            score_delta=0,
            confidence=0.99,
            matched_text=entities.urls[0],
            explanation_ar="تم استخراج رابط من الرسالة لتحليل سمعته.",
        ))
    if entities.link_reference and not entities.urls:
        out.append(Evidence(
            id="entity_link_reference",
            category="entity",
            severity="info",
            score_delta=0,
            confidence=0.80,
            matched_text="",
            explanation_ar="تحتوي الرسالة على إشارة إلى رابط أو ضغط.",
        ))
    return out


# ── Safe-context evidence ─────────────────────────────────────────────────────

def build_safe_context_evidence(intents: IntentResult) -> list[Evidence]:
    out: list[Evidence] = []
    # Awareness evidence: always add when awareness=True, even if dangerous_text_request=True
    # (the dangerous phrase is a quoted phishing example, not an actual request to the reader)
    if intents.has("educational_awareness") or intents.awareness:
        out.append(Evidence(
            id="safe_awareness_message",
            category="safe_context",
            severity="info",
            score_delta=-10,
            confidence=0.90,
            matched_text=intents.safe_context or "",
            explanation_ar="الرسالة توعوية تحذر من مشاركة البيانات الحساسة ولا تطلبها.",
            explanation_en="Security awareness message — warns against sharing sensitive data.",
        ))
    if intents.has("otp_delivery") and not intents.dangerous_text_request:
        out.append(Evidence(
            id="safe_otp_delivery",
            category="safe_context",
            severity="info",
            score_delta=-8,
            confidence=0.88,
            matched_text="",
            explanation_ar="الرسالة تبدو رمز تحقق معلوماتياً مع تنبيه بعدم مشاركته.",
            explanation_en="OTP delivery with do-not-share instruction.",
        ))
    if intents.has("bank_transaction") and not intents.dangerous_text_request:
        out.append(Evidence(
            id="safe_bank_transaction",
            category="safe_context",
            severity="info",
            score_delta=-8,
            confidence=0.88,
            matched_text="",
            explanation_ar="الرسالة تبدو إشعار عملية مالية ولا تطلب إجراء أو بيانات حساسة.",
            explanation_en="Bank transaction notification — no action or data requested.",
        ))
    if intents.has("informational_notification") and not intents.dangerous_text_request:
        out.append(Evidence(
            id="safe_informational",
            category="safe_context",
            severity="info",
            score_delta=-6,
            confidence=0.82,
            matched_text="",
            explanation_ar="الرسالة تبدو إشعاراً معلوماتياً لا يطلب إجراء حساساً.",
        ))
    return out


# ── Dangerous-intent evidence ─────────────────────────────────────────────────

def build_dangerous_intent_evidence(intents: IntentResult) -> list[Evidence]:
    out: list[Evidence] = []
    evidence_text = intents.evidence.get("sensitive_request", "")

    if intents.otp_request:
        out.append(Evidence(
            id="danger_otp_request",
            category="suspicious_context",
            severity="medium",
            score_delta=42,
            confidence=0.76,
            matched_text=evidence_text,
            explanation_ar=(
                "الرسالة تطلب إرسال أو مشاركة رمز التحقق (OTP). "
                "هذا مؤشر تصيّد قوي جداً — لا تشارك أي رمز تحقق مع أي شخص."
            ),
            explanation_en="Message requests OTP/verification code — strong phishing indicator.",
        ))

    if intents.password_request:
        out.append(Evidence(
            id="danger_password_request",
            category="dangerous_intent",
            severity="critical",
            score_delta=92,
            confidence=0.95,
            matched_text=evidence_text,
            explanation_ar="الرسالة تطلب إرسال كلمة المرور أو الرقم السري.",
            explanation_en="Message requests password or PIN.",
        ))

    if intents.card_data_request:
        out.append(Evidence(
            id="danger_card_request",
            category="dangerous_intent",
            severity="critical",
            score_delta=96,
            confidence=0.96,
            matched_text=evidence_text,
            explanation_ar="الرسالة تطلب بيانات بطاقة أو CVV/CVC أو تفاصيل بنكية.",
            explanation_en="Message requests card/CVV/banking details.",
        ))

    if intents.credential_request and not (
        intents.otp_request or intents.password_request or intents.card_data_request
    ):
        out.append(Evidence(
            id="danger_credential_request",
            category="dangerous_intent",
            severity="high",
            score_delta=88,
            confidence=0.90,
            matched_text=evidence_text,
            explanation_ar="الرسالة تطلب بيانات حساسة أو معلومات حساب.",
            explanation_en="Message requests sensitive credentials or account details.",
        ))

    return out


# ── Suspicious-context evidence ───────────────────────────────────────────────

def build_suspicious_context_evidence(
    intents: IntentResult,
    entities: EntityResult,
    url_intel: URLIntelligence,
    modality: str = "text_with_url",
) -> list[Evidence]:
    out: list[Evidence] = []

    if intents.credential_request and url_intel.has_link_surface:
        out.append(Evidence(
            id="suspicious_credential_link",
            category="dangerous_intent",
            severity="critical",
            score_delta=95,
            confidence=0.95,
            matched_text=url_intel.primary_url or "",
            explanation_ar="تجمع الرسالة بين طلب بيانات حساسة ورابط — مؤشر تصيّد بالغ الخطورة.",
            explanation_en="Credential request combined with a URL — phishing indicator.",
        ))

    if url_intel.has_link_surface and intents.has("account_update") and intents.threat_urgency:
        out.append(Evidence(
            id="suspicious_url_urgency_account",
            category="suspicious_context",
            severity="high",
            score_delta=90,
            confidence=0.88,
            matched_text=url_intel.primary_url or "",
            explanation_ar="تجمع الرسالة بين استعجال وتحديث حساب عبر رابط أو ضغط.",
        ))
    elif url_intel.has_link_surface and intents.has("account_update"):
        out.append(Evidence(
            id="suspicious_url_account_update",
            category="suspicious_context",
            severity="medium",
            score_delta=62,
            confidence=0.78,
            matched_text=url_intel.primary_url or "",
            explanation_ar="تطلب الرسالة تحديث حساب عبر رابط دون دليل كافٍ على أنها رسمية.",
        ))
    elif url_intel.has_link_surface and entities.has_bank_or_account and modality != "url_only":
        # Skip for url_only: the bank/account entity was extracted from the URL
        # path itself (not from message text), so the combination is not suspicious.
        out.append(Evidence(
            id="suspicious_financial_link",
            category="suspicious_context",
            severity="medium",
            score_delta=60,
            confidence=0.75,
            matched_text=url_intel.primary_url or "",
            explanation_ar="تجمع الرسالة بين سياق مالي ورابط أو طلب ضغط.",
        ))

    if intents.has("ambiguous_financial_notice"):
        out.append(Evidence(
            id="suspicious_ambiguous_financial",
            category="suspicious_context",
            severity="medium",
            score_delta=48,
            confidence=0.72,
            matched_text="",
            explanation_ar=(
                "الرسالة تتعلق بحساب أو نشاط مالي بصياغة غير حاسمة "
                "وتحتاج تحقق من المصدر الرسمي."
            ),
        ))

    if intents.threat_urgency and entities.has_bank_or_account and not intents.dangerous_text_request:
        out.append(Evidence(
            id="suspicious_urgent_account",
            category="suspicious_context",
            severity="medium",
            score_delta=58,
            confidence=0.76,
            matched_text="",
            explanation_ar="تستخدم الرسالة استعجالاً أو تهديداً في سياق حساب أو بنك.",
        ))

    # Generic urgency without bank entity — still suspicious when combined with link
    if (
        intents.threat_urgency
        and not entities.has_bank_or_account
        and not intents.dangerous_text_request
        and url_intel.has_link_surface
    ):
        out.append(Evidence(
            id="suspicious_urgency_link",
            category="suspicious_context",
            severity="low",
            score_delta=42,
            confidence=0.68,
            matched_text="",
            explanation_ar="تجمع الرسالة بين استعجال وضغط على رابط دون سياق موثوق.",
        ))

    if (
        intents.threat_urgency
        and (intents.has("account_login") or "password" in entities.entities or "pin" in entities.entities)
    ):
        weight = 90 if ("password" in entities.entities or "pin" in entities.entities) else 78
        out.append(Evidence(
            id="suspicious_threat_login",
            category="suspicious_context",
            severity="high",
            score_delta=weight,
            confidence=0.87,
            matched_text="",
            explanation_ar="تجمع الرسالة بين تهديد للحساب وطلب دخول أو إشارة لكلمة مرور.",
        ))

    return out


# ── Full evidence list builder ────────────────────────────────────────────────

def build_all_evidence(
    entities: EntityResult,
    intents: IntentResult,
    url_intel: URLIntelligence,
    sender: SenderAssessment,
    ai: AIAssessment,
    modality: str = "text_with_url",
) -> list[Evidence]:
    """
    Assemble all evidence from every subsystem.

    Order matters for user-facing display (most critical first), but the
    policy engine applies its own precedence rules independent of order.
    """
    all_ev: list[Evidence] = []

    # 1. Dangerous intent (highest priority for display)
    all_ev.extend(build_dangerous_intent_evidence(intents))

    # 2. Suspicious context
    all_ev.extend(build_suspicious_context_evidence(intents, entities, url_intel, modality))

    # 3. URL local evidence
    all_ev.extend(url_intel.local_evidence)

    # 4. Sender evidence
    all_ev.extend(sender.evidence)

    # 5. Safe context
    all_ev.extend(build_safe_context_evidence(intents))

    # 6. Entity-level (informational)
    all_ev.extend(build_entity_evidence(entities))

    # 7. AI advisory
    all_ev.extend(ai.evidence)

    # Deduplicate by id (keep first occurrence)
    seen: set[str] = set()
    deduped: list[Evidence] = []
    for ev in all_ev:
        if ev.id not in seen:
            seen.add(ev.id)
            deduped.append(ev)

    return deduped
