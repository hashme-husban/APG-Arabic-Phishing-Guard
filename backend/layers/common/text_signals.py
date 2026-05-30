from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

ARABIC_DIACRITICS_REGEX = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]")
TATWEEL_REGEX = re.compile(r"\u0640+")
MULTISPACE_REGEX = re.compile(r"\s+")
ZERO_WIDTH_REGEX = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069]")

ARABIC_DIGIT_MAP = str.maketrans(
    {
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
    }
)


def normalize_arabic_digits(text: str) -> str:
    return (text or "").translate(ARABIC_DIGIT_MAP)


def normalize_loose_text(text: str) -> str:
    text = normalize_arabic_digits(text or "")
    text = ZERO_WIDTH_REGEX.sub(" ", text)
    text = ARABIC_DIACRITICS_REGEX.sub("", text)
    text = TATWEEL_REGEX.sub("", text)

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    text = re.sub(r"[^\w\s@.+\-/]", " ", text, flags=re.UNICODE)
    text = MULTISPACE_REGEX.sub(" ", text).strip().lower()
    return text


class TextSignalAnalyzer:
    """Deterministic Arabic/English security-text heuristics.

    These signals serve two goals:
    1) provide graceful fallback when ML models or artifacts are unavailable;
    2) enrich explanations with concrete human-readable evidence.
    """

    CATEGORY_PATTERNS: Dict[str, List[re.Pattern[str]]] = {
        "urgency": [
            re.compile(r"\b(urgent|immediately|asap|now|final notice|last warning|act now|within hours)\b", re.IGNORECASE),
            re.compile(r"\b(عاجل|فورا|فورًا|حالًا|الان|الآن|اخير تحذير|تحذير نهائي|بشكل عاجل|خلال ساعات|الرجاء فوراً)\b", re.IGNORECASE),
        ],
        "threat": [
            re.compile(r"\b(suspend|suspended|blocked|disabled|locked|terminated|closed|restricted|deactivated)\b", re.IGNORECASE),
            re.compile(r"\b(ايقاف|إيقاف|تعطيل|حظر|تعليق|تجميد|تقييد|اغلاق|إغلاق|قفل|تم تقييد|تعطيل الحساب)\b", re.IGNORECASE),
        ],
        "credential_request": [
            re.compile(r"\b(password|passcode|login|signin|user ?name|credentials?|cvv|security code|atm|atm code|atm pin|debit card|bank card|card code|card pin|account number|security question)\b", re.IGNORECASE),
            re.compile(r"\b(كلمه ?المرور|كلمة ?المرور|تسجيل ?الدخول|بيانات ?الدخول|بيانات ?حسابك|رقم ?الحساب|رقم ?البطاقه|رقم ?البطاقة|رمز ?البطاقه|رمز ?البطاقة|رمز ?بطاقة ?الصراف|رقم ?بطاقة ?الصراف|كود ?الصراف|الرقم ?السري|pin|cvv)\b", re.IGNORECASE),
        ],
        "otp_request": [
            re.compile(r"\b(otp|one[- ]time code|verification code|pin code|sms code|2fa code|auth code)\b", re.IGNORECASE),
            re.compile(r"\b(otp|رمز ?التحقق|رمز ?تفعيل|كود ?التفعيل|كود ?التحقق|رقم ?التحقق|رمز ?otp|pin|رمز ?المصادقه|رمز ?المصادقة)\b", re.IGNORECASE),
        ],
        "payment_request": [
            re.compile(r"\b(payment|invoice|refund|transfer|bank|wallet|card|billing|charge|settlement|account)\b", re.IGNORECASE),
            re.compile(r"\b(دفع|فاتوره|فاتورة|تحويل|بنكي|بنك|محفظه|محفظة|بطاقه|بطاقة|رسوم|سداد|مبلغ|استرداد|حساب)\b", re.IGNORECASE),
        ],
        "action_link": [
            re.compile(r"\b(click|open|visit|follow the link|tap|review link|verify here|update here|use the link|complete verification)\b", re.IGNORECASE),
            re.compile(r"\b(اضغط|افتح|افتح الرابط|راجع الرابط|من خلال الرابط|الدخول عبر الرابط|حدث بياناتك|تحقق هنا|الرابط|استخدم الرابط|اكمل التحقق)\b", re.IGNORECASE),
        ],
        "authority_impersonation": [
            re.compile(r"\b(bank|government|ministry|university|paypal|apple|google|facebook|meta|whatsapp|telegram|amazon|microsoft)\b", re.IGNORECASE),
            re.compile(r"\b(بنك|وزاره|وزارة|حكومه|حكومة|جامعه|جامعة|ابل|غوغل|جوجل|فيسبوك|واتساب|تلغرام|تيليجرام|بريد|امازون|مايكروسوفت)\b", re.IGNORECASE),
        ],
        "remote_contact": [
            re.compile(r"\b(contact us|call us|reply now|chat with us|whatsapp us|telegram us|call immediately)\b", re.IGNORECASE),
            re.compile(r"\b(تواصل معنا|اتصل بنا|اتصل على|ارسل لنا|راسلنا|واتساب|تلغرام|تيليجرام|اتصل فورا|رد الان|رد الآن)\b", re.IGNORECASE),
        ],
        "attachment_or_app": [
            re.compile(r"\b(attachment|attached|download|document|pdf|apk|exe|zip|install app|update app)\b", re.IGNORECASE),
            re.compile(r"\b(مرفق|مرفقه|تحميل|تنزيل|مستند|وثيقه|وثيقة|pdf|apk|zip|تثبيت ?التطبيق|تحديث ?التطبيق)\b", re.IGNORECASE),
        ],
        "prize_or_refund": [
            re.compile(r"\b(prize|winner|refund|claim now|cashback|gift|reward)\b", re.IGNORECASE),
            re.compile(r"\b(جائزه|جائزة|ربحت|فزت|استرداد|استلام|مطالبه|مطالبة|هديه|هدية|كاش ?باك|مكافأة|مكافاه)\b", re.IGNORECASE),
        ],
        "safe_context": [
            re.compile(r"\b(reminder|schedule|meeting|semester|portal|tracking number|receipt|delivery update|class|appointment)\b", re.IGNORECASE),
            re.compile(r"\b(تذكير|جدول|موعد|اجتماع|الفصل القادم|بوابه الجامعه|بوابة الجامعة|رقم التتبع|ايصال|إيصال|تحديث التوصيل|شحنه|شحنة|المحاضرة|الحصة)\b", re.IGNORECASE),
        ],
    }

    CATEGORY_REASONS: Dict[str, str] = {
        "urgency": "The message uses urgency language.",
        "threat": "The message threatens suspension, blocking, or account loss.",
        "credential_request": "The message asks for credentials or card/security details.",
        "otp_request": "The message asks for an OTP or verification code.",
        "payment_request": "The message discusses payments, banking, or money movement.",
        "action_link": "The message pushes the user toward a link or immediate action.",
        "authority_impersonation": "The text appears to impersonate an institution or trusted service.",
        "remote_contact": "The message tries to move the interaction to a reply/chat/call channel.",
        "attachment_or_app": "The message references a document, app, or downloadable file.",
        "prize_or_refund": "The message mentions a prize, refund, or reward claim.",
        "safe_context": "The text also contains benign reminder or routine-service wording.",
    }

    def _contains(self, patterns: Iterable[re.Pattern[str]], raw_text: str, normalized_text: str) -> bool:
        for pattern in patterns:
            if pattern.search(raw_text) or pattern.search(normalized_text):
                return True
        return False

    def detect_categories(self, raw_text: str, normalized_text: Optional[str] = None) -> Set[str]:
        raw_text = raw_text or ""
        normalized_text = normalized_text or normalize_loose_text(raw_text)
        detected: Set[str] = set()
        for category, patterns in self.CATEGORY_PATTERNS.items():
            if self._contains(patterns, raw_text, normalized_text):
                detected.add(category)
        if re.search(r"(?:https?://|www\.|hxxp|\[\.\]|\b[a-z0-9-]+\.[a-z]{2,}\b)", raw_text, re.IGNORECASE):
            detected.add("action_link")
        return detected

    def analyze(
        self,
        raw_text: str,
        normalized_text: Optional[str] = None,
        channel: str = "",
        claimed_entity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw_text = (raw_text or "").strip()
        normalized_text = normalized_text or normalize_loose_text(raw_text)
        categories = self.detect_categories(raw_text, normalized_text)

        score = 0.18
        reasons: List[str] = []
        flags: List[str] = []

        weights = {
            "urgency": 0.07,
            "threat": 0.10,
            "credential_request": 0.22,
            "otp_request": 0.24,
            "payment_request": 0.12,
            "action_link": 0.14,
            "authority_impersonation": 0.08,
            "remote_contact": 0.08,
            "attachment_or_app": 0.12,
            "prize_or_refund": 0.10,
            "safe_context": -0.10,
        }

        for category in sorted(categories):
            score += weights.get(category, 0.0)
            reason = self.CATEGORY_REASONS.get(category)
            if reason:
                reasons.append(reason)
            flags.append(category.upper())

        if {"urgency", "action_link", "otp_request"}.issubset(categories):
            score += 0.18
            reasons.append("Urgency, link pressure, and OTP language appear together, which is a strong phishing pattern.")
            flags.append("OTP_LINK_PRESSURE")

        if {"urgency", "threat", "action_link"}.issubset(categories):
            score += 0.14
            reasons.append("The message combines urgency, threat language, and a call to action.")
            flags.append("THREAT_URGENCY_ACTION")

        if "credential_request" in categories and "action_link" in categories:
            score += 0.12
            reasons.append("Credential collection is paired with a link or immediate action request.")
            flags.append("CREDENTIAL_LINK_COMBO")

        if "credential_request" in categories and "payment_request" in categories:
            score += 0.16
            reasons.append("The message requests card or banking details, which is a high-risk social-engineering pattern.")
            flags.append("CARD_OR_BANKING_DETAILS_REQUEST")

        if "authority_impersonation" in categories and ({"credential_request", "otp_request", "payment_request"} & categories):
            score += 0.10
            reasons.append("The message appears to imitate a trusted entity while asking for sensitive action.")
            flags.append("IMPERSONATION_SENSITIVE_REQUEST")

        sector = str((claimed_entity or {}).get("sector", "")).strip().lower()
        if sector in {"bank", "payment", "wallet", "government"} and ({"action_link", "credential_request", "otp_request", "payment_request"} & categories):
            score += 0.08
            reasons.append(f"The claimed sector ({sector}) is sensitive and the message requests risky user action.")
            flags.append("SENSITIVE_SECTOR_REQUEST")

        if "safe_context" in categories and not ({"credential_request", "otp_request", "threat", "urgency"} & categories):
            score -= 0.05

        token_count = len([token for token in normalized_text.split() if token])
        if token_count < 4:
            score = (0.88 * score) + (0.12 * 0.5)
            reasons.append("The message is short, so text-only certainty is limited.")
            flags.append("SHORT_TEXT")

        score = max(0.0, min(1.0, score))
        if score >= 0.72:
            label = "phishing"
        elif score <= 0.32:
            label = "safe"
        else:
            label = "suspicious"

        confidence = 0.48 + min(0.24, len(categories) * 0.05) + min(0.20, abs(score - 0.5) * 0.40)
        if token_count < 4:
            confidence -= 0.06
        if channel in {"email", "messaging", "sms"}:
            confidence += 0.02
        confidence = max(0.0, min(0.95, confidence))

        if not reasons:
            reasons.append("No strong deterministic text signal was detected.")

        return {
            "risk_score": round(score, 6),
            "component_label": label,
            "confidence": round(confidence, 6),
            "categories": sorted(categories),
            "flags": sorted(set(flags)),
            "reasons": reasons[:8],
            "token_count": token_count,
        }
