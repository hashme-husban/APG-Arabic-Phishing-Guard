from __future__ import annotations

import re

from .normalizer import contains_any, n_terms
from .schemas import EntityResult, Signal
from .url_reputation import extract_domain, extract_urls

PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)")

OTP_TERMS = n_terms([
    "otp", "2fa", "verification code", "auth code",
    "رمز التحقق", "رمز تحقق", "كود التحقق", "رمز الدخول", "كود الدخول",
    "رمز التفعيل", "رمز المصادقة", "رمز واتساب", "الكود", "رقم التحقق", "الرمز المكون",
    # Additional OTP/code patterns
    "الرمز الذي وصلك", "الرمز اللي وصلك", "الكود اللي وصلك",
    "الرمز الذي استقبلته", "الرمز اللي استقبلته", "الكود الذي استقبلته",
    "رمز التحويل", "رمز الاستلام", "رمز الدفع",
    "كود التفعيل", "رمز التفعيل",
    # Crypto / wallet
    "seed phrase", "عبارة الاسترداد", "عباره الاسترداد", "مفتاح المحفظة",
    # Token
    "token", "رمز token",
])
PASSWORD_TERMS = n_terms([
    "كلمة المرور", "كلمه المرور", "كلمة مرور", "الباسورد", "باسورد",
    "password", "passcode",
    # Additional
    "كلمة السر", "كلمه السر", "بيانات دخول", "بيانات الدخول",
    "معلومات الدخول", "معلومات دخول",
    # Security questions
    "اسئله الامان", "اجابات الامان", "اسئلة الامان", "إجابات أسئلة الأمان",
])
PIN_TERMS = n_terms([
    "pin", "الرقم السري", "الرمز السري", "رقم سري", "الرقم السري للبطاقة",
    # Possessive and dialect forms
    "رقمك السري", "رمزك السري", "رقمه السري", "الرقم السري الخاص بك",
])
CARD_TERMS = n_terms([
    "رقم البطاقة", "البطاقة", "بطاقتك", "بطاقتك البنكية",
    "بيانات البطاقة", "بطاقة بنكية", "بيانات بنكية",
    "رقم الحساب", "iban", "الايبان", "card number", "card details",
    # Additional
    "تفاصيل البطاقة", "معلومات البطاقة", "تاريخ انتهاء البطاقة",
    "تاريخ الانتهاء",
])
CVV_TERMS = n_terms(["cvv", "cvc", "رمز البطاقة"])
BANK_TERMS = n_terms(["بنك", "البنك", "مصرف", "حسابك البنكي", "حساب بنكي", "بنكي", "بنكية", "bank"])
ACCOUNT_TERMS = n_terms(["حساب", "حسابك", "الحساب", "account"])
MONEY_TERMS = n_terms(["رصيد", "حوالة", "تحويل", "راتب", "خصم", "ايداع", "إيداع", "دفع", "سحب", "عملية شراء", "ملفك المالي", "الملف المالي", "مالي", "purchase", "balance", "transaction", "debited", "credited"])
WHATSAPP_TERMS = n_terms(["واتساب", "وتساب", "whatsapp"])
LINK_TERMS = n_terms(["رابط", "الرابط", "اضغط", "افتح الرابط", "ادخل عبر الرابط", "click", "link", "open"])


class EntityExtractor:
    def extract(
        self,
        raw_text: str,
        normalized: str,
        *,
        source: str = "manual",
        sender: str = "",
        sender_name: str = "",
        package_name: str = "",
        source_app: str = "",
        extra_urls: list[str] | None = None,
        is_known_contact: bool | None = None,
        sender_trust: str = "unknown",
    ) -> tuple[EntityResult, list[Signal]]:
        urls = extract_urls(raw_text) + extract_urls(normalized)
        for url in extra_urls or []:
            value = str(url or "").strip()
            if value:
                urls.append(value)
        urls = self._dedupe(urls)
        domains = self._dedupe([extract_domain(url) for url in urls if extract_domain(url)])
        phones = self._dedupe(PHONE_RE.findall(raw_text or ""))
        entities: set[str] = set()
        signals: list[Signal] = []

        checks = [
            ("otp", OTP_TERMS, "تم رصد رمز تحقق ككيان حساس، وهذا لا يكفي وحده لتصنيف الرسالة كخطرة."),
            ("password", PASSWORD_TERMS, "تم رصد كلمة مرور ككيان حساس."),
            ("pin", PIN_TERMS, "تم رصد رقم سري ككيان حساس."),
            ("card", CARD_TERMS, "تم رصد بيانات بطاقة أو حساب ككيان حساس."),
            ("cvv", CVV_TERMS, "تم رصد CVV/CVC ككيان حساس."),
            ("bank", BANK_TERMS, "تذكر الرسالة جهة مالية أو بنكا."),
            ("account", ACCOUNT_TERMS, "تذكر الرسالة حسابا أو ملفا للمستخدم."),
            ("money_transaction", MONEY_TERMS, "تذكر الرسالة عملية مالية أو رصيدا."),
            ("whatsapp", WHATSAPP_TERMS, "تذكر الرسالة واتساب."),
        ]
        for name, terms, explanation in checks:
            if contains_any(normalized, terms):
                entities.add(name)
                signals.append(Signal(f"entity_{name}", "entity", 0, explanation, name))
        if "iban" in normalized:
            entities.add("iban")
        link_reference = contains_any(normalized, LINK_TERMS)
        if link_reference:
            signals.append(Signal("link_reference", "entity", 0, "تحتوي الرسالة على إشارة إلى رابط أو ضغط.", "link"))
        for domain in domains:
            signals.append(Signal("detected_url", "entity", 0, "تم استخراج رابط من الرسالة لتحليل سمعته وخصائصه.", domain))

        return (
            EntityResult(
                entities=entities,
                urls=urls,
                domains=domains,
                phones=phones,
                link_reference=link_reference,
                source=source,
                sender=sender,
                sender_name=sender_name,
                source_app=source_app,
                package_name=package_name,
                is_known_contact=is_known_contact,
                sender_trust=sender_trust,
            ),
            signals,
        )

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            value = (item or "").strip()
            if value and value not in seen:
                seen.add(value)
                output.append(value)
        return output
