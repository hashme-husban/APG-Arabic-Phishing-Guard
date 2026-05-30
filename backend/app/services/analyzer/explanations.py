from __future__ import annotations

from .normalizer import dedupe
from .schemas import RuleResult

DEFAULT_SAFE_EXPLANATION = "لا توجد مؤشرات خطيرة واضحة في الرسالة."
DEFAULT_SUSPICIOUS_EXPLANATION = "الرسالة تحتاج حذرا لأنها تجمع مؤشرات غير كافية للجزم بالخطر."
DEFAULT_DANGEROUS_EXPLANATION = "الرسالة تحتوي دليلا قويا على تصيّد أو طلب بيانات حساسة."


def reasons_for(classification: str, rule_result: RuleResult) -> list[str]:
    if classification == "dangerous":
        reasons = [DEFAULT_DANGEROUS_EXPLANATION]
        reasons.extend(s.explanation_ar for s in rule_result.signals if s.type == "danger")
    elif classification == "suspicious":
        reasons = [s.explanation_ar for s in rule_result.signals if s.type == "suspicious"]
    else:
        reasons = [s.explanation_ar for s in rule_result.signals if s.type == "safe"]
    if not reasons:
        reasons = [DEFAULT_SAFE_EXPLANATION if classification == "safe" else DEFAULT_SUSPICIOUS_EXPLANATION]
    return dedupe(reasons)[:8]


def recommendation_for(classification: str) -> str:
    if classification == "dangerous":
        return "لا تفتح الرابط ولا تشارك رمز OTP أو كلمة المرور أو رقم البطاقة أو CVV. تحقق من الجهة عبر التطبيق أو الموقع الرسمي فقط."
    if classification == "suspicious":
        return "تحقق من المصدر الرسمي قبل فتح أي رابط أو مشاركة أي بيانات."
    return "لا توجد مؤشرات خطيرة واضحة. للإجراءات الحساسة استخدم القنوات الرسمية فقط."
