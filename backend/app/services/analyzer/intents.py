from __future__ import annotations

import re

from .entities import ACCOUNT_TERMS, BANK_TERMS, CARD_TERMS, CVV_TERMS, LINK_TERMS, MONEY_TERMS, OTP_TERMS, PASSWORD_TERMS, PIN_TERMS, WHATSAPP_TERMS
from .normalizer import contains_any, first_match, n_terms
from .schemas import EntityResult, IntentResult

REQUEST_TERMS = n_terms([
    "ارسل", "أرسل", "ارسال", "شارك", "ادخل", "أدخل", "تدخل", "ادخال", "اكتب", "قدم", "زودنا",
    "صورلي", "صور", "اعطني", "أعطني", "اعطيني", "أعطيني", "ابعث", "ابعت", "ابعتلي", "هات",
    "دز", "دزلنا", "دزلي", "عطني", "عطيني",
    # Gulf/Levantine dialects
    "شاركنا", "شاركيني", "ابعتيه", "ابعتيني", "ابعته", "دزه", "دزيه", "دزلي", "ورجيني",
    "هاتلي", "عطيه", "عطيني", "زودني", "زودنا",
    "يرجى ادخال", "يرجى ارسال", "يطلب منك", "يطالبك", "سجل الدخول", "سجل",
    "send", "share", "enter", "provide", "submit",
    # Transfer/forward verbs often used in OTP theft scripts
    "حول", "حوّل", "حوّله", "حوله", "احال", "أحال", "إحالة", "احالة",
    "ابعته", "ابعثه", "ابعت الرمز", "ارسل الرمز", "شارك الرمز",
    "افصح", "أفصح", "كشف", "اكشف", "أكشف",
    # Conjugations used in conditional-threat phrasing ("إن لم ترسل رمز التحقق...")
    "ترسل", "تشارك", "تعطي", "تدخل", "تزود",
])
# Indirect / need-phrasing credential requests (no imperative verb)
INDIRECT_NEED_TERMS = n_terms([
    "لاتمام", "لاستكمال", "لاكمال", "لاستيفاء",
    "المطلوب", "مطلوب", "نحتاج", "نحتاج منك",
    "بدي", "بدنا", "محتاج", "يلزم", "لازم", "ضروري",
    "كلمة مرورك مطلوبة", "بياناتك مطلوبة",
])
QUESTION_CODE_TERMS = n_terms([
    "شو رمز", "ما هو رمز", "كم رمز", "ايش رمز", "ما الرمز",
    "الرمز اللي وصلك", "رمز واتساب اللي وصلك",
    "شو الكود", "ايش الكود", "وين الكود", "ما الكود اللي وصلك",
    "كيف الرمز", "وين الرمز",
])
NEGATION_TERMS = n_terms(["لا", "لن", "لا تقم", "لا تشارك", "لا تفصح", "لا تعط", "لا تعطي", "لا ترسل", "لا تدخل", "لا تضغط", "لن يطلب", "ما ترسل", "ممنوع", "do not", "don't", "never"])
DO_NOT_SHARE_TERMS = n_terms([
    "لا تشاركه", "لا تشارك", "لا تفصح", "لا تعطه", "لا تعطيه", "لا ترسل", "لا تزود", "لا تخبر",
    "لن يطلب البنك", "البنك لن يطلب", "ما تعطي", "ما ترسل", "ما تشارك",
    "do not share", "never share", "do not disclose",
])
AWARENESS_TERMS = n_terms([
    "رسالة توعوية", "نصيحة أمنية", "احذر من", "لا تضغط",
    "الروابط المشبوهة", "لن يطلب البنك", "البنك لن يطلب", "لا يطلب", "لا تطلب",
    "فهي احتيال", "هي احتيال", "هذه احتيال", "رسالة احتيال", "لا تستجب",
    "رسائل احتيالية", "هذا احتيال", "100% احتيال",
    "من اساليب الاحتيال", "مثال على", "نموذج احتيال",
    "اعلم انه محتال", "اعلم أنه محتال", "يحاول سرقة",
    # Explicit fraud declarations (not pretext phrases a scammer would use)
    "هذه رسالة توعية", "رسالة تحذيرية", "تحذير أمني",
])
BENIGN_BANKING_TERMS = n_terms(["تم خصم", "خصم مبلغ", "تم إيداع", "تم ايداع", "تمت عملية", "عملية شراء", "تم الدفع", "تم السحب", "تم سحب", "تم تنفيذ حوالة", "تم استلام حوالة", "الرصيد", "الرصيد المتاح", "رصيد حسابك", "عملية ناجحة", "تمت العملية بنجاح"])
BENIGN_OTP_TERMS = n_terms(["رمز التحقق الخاص بك", "رمز الدخول لمرة واحدة", "كود التحقق الخاص بك", "رمزك هو", "رمزك للدخول", "your otp", "your verification code"])
WHATSAPP_STATUS_TERMS = n_terms(["جاري التحقق من واتساب", "تم التحقق من واتساب", "واتساب: جاري التحقق", "واتساب يتحقق", "يتحقق من رقم الهاتف", "whatsapp verification in progress", "whatsapp verifying", "whatsapp verification"])
UPDATE_TERMS = n_terms(["حدث بياناتك", "حدث بيانات حسابك", "تحديث بياناتك", "تحديث بيانات حسابك", "تحديث بيانات", "لتحديث بيانات", "تحديث معلومات الحساب", "تفعيل الحساب", "تفعيل حساب", "تفعيل البطاقة", "فعل حسابك", "توثيق الحساب"])
THREAT_TERMS = n_terms([
    "عاجل", "فورا", "فوراً", "آخر فرصة", "اخر فرصة", "تعليق", "إيقاف", "ايقاف",
    "حظر", "اغلاق", "إغلاق", "موقوف", "خلال 24", "تجنب إيقاف", "تجنب ايقاف",
    "مؤقتا", "الآن", "الان", "urgent", "immediately", "now", "blocked", "suspended", "closed",
    # Additional urgency patterns
    "سيتعطل", "ستتعطل", "سيتجمد", "ستتجمد", "تجميد", "محتجز",
    "انتهاء المهله", "انتهاء الفرصه", "قبل الانتهاء",
    "خلال ساعه", "خلال ساعتين", "ساعة فقط", "دقيقة فقط",
    "48 ساعه", "48 ساعة",
    "اشعار نهائي", "إشعار نهائي", "انذار نهائي",
    "نشاط غير مصرح", "محاولة مشبوهه", "دخول مشبوه",
])
LOGIN_TERMS = n_terms([
    "سجل الدخول", "تسجيل الدخول", "الدخول الآن", "الدخول الان",
    "ادخل كلمة المرور", "تدخل كلمة المرور", "enter password", "login now",
    "تسجيل دخول", "دخول مشبوه", "محاولة دخول",
])
AMBIGUOUS_FINANCIAL_TERMS = n_terms([
    "نشاط غير معتاد", "محاولة دخول", "راجع حسابك", "مراجعة حسابك",
    "حالة الحساب", "تحديث مهم", "بحاجة إلى مراجعة", "تحقق من النشاط",
    "تأكيد الحساب", "تاكيد الحساب", "تأكيد بيانات", "تأكيد بياناتك",
    "تاكيد بياناتك", "التأكد من بيانات", "التاكد من بيانات",
    "تحديث معلومات الحساب",
    # Additional patterns
    "مشكله في حسابك", "مشكلة في حسابك", "تنبيه امني",
    "معامله غير معتاده", "معاملة غير معتادة",
    "توثيق الحساب", "توثيق حسابك",
    "تاهلت للحصول", "لاستمرار الخدمه", "تاكيد هويتك",
    "يجب تحديث", "يجب التحديث",
])


class IntentDetector:
    def detect(self, normalized: str, entities: EntityResult) -> IntentResult:
        result = IntentResult()
        text = normalized or ""
        sensitive_terms = OTP_TERMS + PASSWORD_TERMS + PIN_TERMS + CARD_TERMS + CVV_TERMS

        if contains_any(text, AWARENESS_TERMS) or contains_any(text, DO_NOT_SHARE_TERMS):
            result.intents.add("educational_awareness")
            result.awareness = True
        if contains_any(text, BENIGN_OTP_TERMS) or (contains_any(text, OTP_TERMS) and contains_any(text, DO_NOT_SHARE_TERMS)):
            result.intents.add("otp_delivery")
        if contains_any(text, WHATSAPP_STATUS_TERMS):
            result.intents.add("informational_notification")
            result.intents.add("otp_delivery")
        if contains_any(text, BENIGN_BANKING_TERMS):
            result.intents.add("bank_transaction")
        if contains_any(text, UPDATE_TERMS):
            result.intents.add("account_update")
        if contains_any(text, THREAT_TERMS):
            result.intents.add("threat_urgency")
            result.threat_urgency = True
        if (contains_any(text, AMBIGUOUS_FINANCIAL_TERMS) and entities.has_bank_or_account) or ("تأكيد بياناتك" in text or "تاكيد بياناتك" in text or "ملفك المالي" in text):
            result.intents.add("ambiguous_financial_notice")
        if contains_any(text, LOGIN_TERMS) and entities.has_bank_or_account:
            result.intents.add("account_login")
        if entities.has_link_surface and (contains_any(text, LINK_TERMS) or contains_any(text, UPDATE_TERMS) or entities.has_bank_or_account):
            result.intents.add("url_action_request")
        if entities.has_bank_or_account and not result.intents:
            result.intents.add("informational_notification")

        request_evidence = self._sensitive_request_evidence(text, sensitive_terms)
        # Second pass: indirect/need-phrasing credential requests (no imperative verb)
        if not request_evidence:
            request_evidence = self._indirect_request_evidence(text, sensitive_terms)
        question_evidence = first_match(text, QUESTION_CODE_TERMS)
        if question_evidence and (contains_any(text, OTP_TERMS) or contains_any(text, WHATSAPP_TERMS) or "رمز" in text):
            request_evidence = question_evidence
            result.otp_request = True

        if request_evidence:
            result.dangerous_text_request = True
            result.credential_request = True
            result.intents.add("sensitive_data_request")
            result.evidence["sensitive_request"] = request_evidence
            if contains_any(text, OTP_TERMS) or result.otp_request:
                result.otp_request = True
                result.intents.add("credential_harvesting")
            if contains_any(text, PASSWORD_TERMS + PIN_TERMS):
                result.password_request = True
                result.intents.add("credential_harvesting")
            if contains_any(text, CARD_TERMS + CVV_TERMS):
                result.card_data_request = True
                result.intents.add("credential_harvesting")

        if entities.has_link_surface and (result.credential_request or (result.has("account_update") and (entities.has_bank_or_account or result.threat_urgency))):
            result.url_account_action = True
            result.intents.add("url_action_request")

        if not result.intents:
            result.intents.add("casual" if not entities.has_sensitive_entity and not entities.has_bank_or_account else "unknown")
        return result

    def _sensitive_request_evidence(self, text: str, sensitive_terms: list[str]) -> str:
        for term in REQUEST_TERMS:
            if not term:
                continue
            for match in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text):
                if self._has_local_negation(text, match.start()):
                    continue
                start = max(0, match.start() - 55)
                end = min(len(text), match.end() + 65)
                window = text[start:end]
                if contains_any(window, sensitive_terms):
                    return window.strip()
                if ("بيانات" in window or "معلومات" in window) and contains_any(window, BANK_TERMS + ACCOUNT_TERMS):
                    return window.strip()
        return ""

    def _indirect_request_evidence(self, text: str, sensitive_terms: list[str]) -> str:
        """
        Detect credential requests expressed without an imperative verb.
        Patterns: purpose phrase + sensitive term, or colon-list of sensitive data.
        """
        # Pattern 1: purpose/need phrase followed by sensitive term nearby
        for term in INDIRECT_NEED_TERMS:
            if not term or term not in text:
                continue
            idx = text.find(term)
            if self._has_local_negation(text, idx):
                continue
            window = text[max(0, idx - 10):min(len(text), idx + len(term) + 90)]
            if contains_any(window, sensitive_terms):
                return window.strip()
        # Pattern 2: colon-delimited credential list — "لإتمام: رقم البطاقة + CVV"
        # ONLY fires when the pre-colon text itself contains an indirect-need term,
        # preventing false positives on "الأحوال المدنية:", "القاعدة الذهبية:", "Telegram:", etc.
        for m in re.finditer(r"([^:\n]{3,60})[:]\s*(.{5,120})", text):
            pre_colon = m.group(1)
            segment = m.group(2)
            if not contains_any(pre_colon, INDIRECT_NEED_TERMS):
                continue
            if self._has_local_negation(text, m.start()):
                continue
            if contains_any(segment, sensitive_terms):
                return (pre_colon + ": " + segment[:80]).strip()
        return ""

    @staticmethod
    def _has_local_negation(text: str, index: int) -> bool:
        prefix = text[max(0, index - 40):index]
        # Truncate at the last hard sentence boundary so "لا" in a previous
        # sentence never negates a request verb in the next sentence.
        last_boundary = max(
            (prefix.rfind(c) for c in (".", "!", "?", "؟", "؛", "\n")),
            default=-1,
        )
        if last_boundary >= 0:
            prefix = prefix[last_boundary + 1:]
        tokens = [t for t in re.split(r"[\s،,.؛:!?؟\-—()\[\]\"']+", prefix) if t]
        tail_tokens = tokens[-6:]
        tail_str = " ".join(tail_tokens)
        # Multi-word negations (e.g., "لا تشارك", "لن يطلب") — substring match is fine
        # Single-word negations (e.g., "لا", "لن") — require exact token match
        # to avoid matching لا embedded in compound words like لاختراق, لاستلامها
        for neg in NEGATION_TERMS:
            if not neg:
                continue
            if " " in neg:
                if neg in tail_str:
                    return True
            else:
                if neg in tail_tokens:
                    return True
        return bool(re.search(r"(?i)(do not|don't|never)\s*$", prefix))
