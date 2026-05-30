"""
APG Risk Intelligence Engine v1 — Explanation Builder

Produces Arabic (and optionally English) user-facing explanations based on
the PolicyDecision and evidence list.

Rules:
  - Block verdict → specific reason based on attack type.
  - Safe verdict  → positive confirmation or safe-context reason.
  - Suspicious    → most relevant suspicious signal explanation.
  - Fallback for every case to avoid empty explanations.
"""
from __future__ import annotations

from .schemas import Evidence, MessageCategory, PolicyDecision

# ─── Primary reason strings ────────────────────────────────────────────────────

_BLOCK_REASONS: dict[str, str] = {
    "otp_theft": (
        "الرسالة تطلب إرسال أو مشاركة رمز التحقق. "
        "لا تشارك أي رمز تحقق مع أي شخص مهما ادّعى."
    ),
    "password_theft": (
        "الرسالة تطلب كلمة المرور أو الرقم السري. "
        "لا تُرسل كلمة مرورك لأي جهة عبر الرسائل."
    ),
    "card_theft": (
        "الرسالة تطلب بيانات البطاقة البنكية أو CVV. "
        "لا تُرسل أي بيانات بنكية عبر الرسائل."
    ),
    "bank_account_takeover": (
        "الرسالة تحتوي رابطاً لتحديث أو تأكيد حسابك البنكي مع إيحاء بالإلحاح. "
        "لا تفتح الرابط — تحقق مباشرة عبر التطبيق الرسمي."
    ),
    "malicious_url": (
        "تم رصد الرابط في قواعد بيانات تصيّد أو برمجيات خبيثة. "
        "لا تفتح الرابط وأبلغ عن الرسالة."
    ),
    "credential_harvesting": (
        "الرسالة تطلب بيانات حساسة عبر رابط. "
        "هذا نمط تصيّد كلاسيكي — لا تفتح الرابط ولا تُدخل أي بيانات."
    ),
    "brand_impersonation": (
        "الرابط يحاكي جهة موثوقة لكنه ليس من نطاقها الرسمي. "
        "لا تثق برابط لمجرد أنه يذكر اسم البنك أو الجهة."
    ),
    "social_engineering": (
        "الرسالة تطلب معلومات حساسة بأسلوب تلاعب اجتماعي. "
        "تحقق من الجهة عبر القنوات الرسمية فقط."
    ),
    "unknown": (
        "الرسالة تحتوي مؤشرات خطر واضحة. "
        "لا تتخذ أي إجراء حتى تتحقق من المصدر الرسمي."
    ),
}

_SAFE_REASONS: dict[str, str] = {
    "awareness": "الرسالة توعوية تحذر من مشاركة البيانات الحساسة ولا تطلبها.",
    "otp_delivery": (
        "الرسالة تحتوي رمز تحقق مع تنبيه بعدم مشاركته. "
        "هذا نمط مشروع من جهات التحقق."
    ),
    "transactional": (
        "الرسالة تبدو إشعار عملية مالية مكتملة. "
        "لا توجد مؤشرات تطلب إجراء أو بيانات حساسة."
    ),
    "app_verification": (
        "الرسالة تبدو حالة تحقق من تطبيق (مثل واتساب). "
        "لا توجد طلب مشاركة رمز أو فتح رابط."
    ),
    "casual": "لا توجد مؤشرات خطيرة. الرسالة تبدو محادثة عادية.",
    "unknown": "لا توجد مؤشرات خطيرة واضحة في الرسالة.",
}

_SUSPICIOUS_DEFAULT = (
    "الرسالة تحتاج حذراً — تجمع مؤشرات غير كافية للجزم بالخطر لكن يستحسن التحقق."
)

_RECOMMENDATION: dict[str, str] = {
    "block": (
        "لا تفتح الرابط ولا تشارك رمز OTP أو كلمة المرور أو رقم البطاقة أو CVV. "
        "تحقق من الجهة عبر التطبيق أو الموقع الرسمي فقط."
    ),
    "warn": (
        "لا تضغط على الرابط ولا تُدخل أي بيانات. "
        "تحقق من المصدر الرسمي قبل أي إجراء."
    ),
    "caution": "تحقق من المصدر الرسمي قبل فتح أي رابط أو مشاركة أي بيانات.",
    "allow": "لا توجد مؤشرات خطيرة واضحة. للإجراءات الحساسة استخدم القنوات الرسمية فقط.",
}


def build_primary_reason(
    decision: PolicyDecision,
    evidence: list[Evidence],
    category: str,
) -> str:
    """Return the most relevant Arabic reason for the final verdict."""
    if decision.verdict == "block":
        return _BLOCK_REASONS.get(decision.attack_type, _BLOCK_REASONS["unknown"])

    if decision.verdict == "allow":
        # Intent-based cap reason takes priority — it explains WHY the score
        # was reduced despite advisory signals suggesting risk.
        if decision.cap_reason_ar:
            return decision.cap_reason_ar
        # Prefer safe-context evidence explanation
        for ev in evidence:
            if ev.category == "safe_context" and ev.explanation_ar:
                return ev.explanation_ar
        return _SAFE_REASONS.get(category, _SAFE_REASONS["unknown"])

    # warn / caution — use most-severe suspicious evidence
    critical = [e for e in evidence if e.category in ("suspicious_context", "dangerous_intent") and e.score_delta > 0]
    critical.sort(key=lambda e: e.score_delta, reverse=True)
    if critical and critical[0].explanation_ar:
        return critical[0].explanation_ar
    return _SUSPICIOUS_DEFAULT


def build_recommendation(verdict: str) -> str:
    return _RECOMMENDATION.get(verdict, _RECOMMENDATION["allow"])


def build_user_action_explanation(user_action: str) -> str:
    """Return a short Arabic description of the user_action code."""
    return {
        "no_action_needed": "لا إجراء مطلوب.",
        "do_not_share_code": "لا تشارك رمز التحقق أو الرقم السري مع أي شخص.",
        "do_not_click_link": "لا تضغط على الرابط.",
        "verify_from_official_app": "تحقق عبر التطبيق أو الموقع الرسمي فقط.",
        "contact_bank_directly": "اتصل بالبنك مباشرة عبر الأرقام الرسمية.",
        "report_message": "أبلغ عن هذه الرسالة كمحاولة احتيال.",
    }.get(user_action, "تحقق من المصدر الرسمي.")
