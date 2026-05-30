"""
APG Risk Intelligence Engine v1 — Action Detector

Wraps the v5 IntentDetector.  Returns the v5 IntentResult which carries:
  - otp_request, password_request, card_data_request, credential_request
  - dangerous_text_request
  - threat_urgency, awareness
  - safe_context (set by context detector)
  - intents set (named intents)
  - evidence dict (matched text evidence)

The context detector (ContextDetector from v5) is also applied here so that
safe_context gets set before the policy engine reads IntentResult.
"""
from __future__ import annotations

import re

from app.services.analyzer.contexts import ContextDetector as _ContextDetector
from app.services.analyzer.intents import IntentDetector as _IntentDetector
from app.services.analyzer.schemas import EntityResult, IntentResult


_OTP_CODE_RE = re.compile(r"(?<!\d)(?:\d{4,8}|\d{3}[- ]\d{3})(?!\d)")

_AWARENESS_HINTS = (
    "لا تعطي",
    "ما تعطي",
    "لن نطلب منك",
    "لا تدخل بياناتك",
    "قد ينتحل المحتالون",
    "القنوات الرسمية",
    "نصيحة:",
    "نصيحة أمنية",
    "فعّل المصادقة الثنائية",
    "فعل المصادقة الثنائية",
    "محاولة احتيال",
    "أبلغ البنك",
    "ابلغ البنك",
    "تأكد من أن الموقع رسمي",
    "تاكد من ان الموقع رسمي",
    "رسالة مشبوهة أبلغ",
    "رسالة مشبوهة ابلغ",
    "الجرائم الإلكترونية",
    "الجرائم الالكترونية",
)

_BANK_STATEMENT_HINTS = (
    "كشف حساب",
    "المبلغ المستحق",
    "تاريخ الاستحقاق",
)

# Extended awareness — patterns clearly indicating security education, not a threat
_EXTENDED_AWARENESS_HINTS = (
    "صفحات وهمية",          # fake pages
    "تنتحل اسم",             # impersonating the name of
    "محاولات الاحتيال",      # fraud attempts
    "الاحتيال والاختراق",    # fraud and hacking
    "روابط غير موثوقة",      # untrustworthy links
    "ينتحل المحتالون",        # scammers impersonate
    "روابط مشبوهة",           # suspicious links
    "احتيال إلكتروني",        # electronic fraud
)

# OTP delivery phrases — when present alongside an OTP code, indicate delivery not request
_OTP_DELIVERY_PHRASES = (
    "رمز التأكيد",       # confirmation code
    "رمز التحقق",        # verification code
    "رمز التفعيل",       # activation code
    "رمز الدخول",        # access code
    "رمز الحماية",       # security code
    "رمز تعريفك",        # your identity code
    "كود التفعيل",       # activation code (kwd variant)
    "رمزك على",          # your code on <platform>
    "رمز التسجيل",       # registration code
)

# Service notification — telecom/service status messages
_SERVICE_NOTIF_HINTS = (
    "صيانة دورية",
    "صيانة مجدولة",
    "صيانة مؤقتة",       # temporary maintenance
    "صيانة طارئة",       # emergency maintenance
    "صيانة شبكة",        # network maintenance
    "اعمال صيانة",       # maintenance work
    "اعمال الصيانة",     # the maintenance work
    "استنفدت",           # data exhausted
    "استنفذت",
    "تم فصل اشتراكك",
    "فصل اشتراكك",
    "رصيد كافي لتجديد",
    "لا يوجد لديك رصيد كافي",
    "ينتهي اشتراكك",
    "لديك مكالمات لم يتم",
    "لديك مكالمات لم يرد",
    "مكالمات لم يتم استلامها",
    "مكالمات لم يرد عليها",
    "تسجيل نجاح",
    "تم التسجيل",
    "تسجيلك معنا",       # your registration with us
    "زيادة سرعة",        # speed increase
    "تقديراً لولائك",    # in appreciation of your loyalty
    "تقديرا لولائك",     # (unvocalized)
    "ترقية مجانية",      # free upgrade
    "حُدِّث",            # was updated
    "تم تحديث",          # was updated (prefix)
    "تم تفعيل",          # was activated
    "تم ايقاف",          # was deactivated
    "تم إيقاف",          # was deactivated
    "انقطاع مؤقت",       # temporary outage
    "انقطاع في الخدمة",  # service outage
    "خدمة الإنترنت",     # internet service (status notice)
    "خدمة الانترنت",     # internet service (unvocalized)
)

# Subscription notice — welcome/allocation messages
_SUBSCRIPTION_REQUIRED = ("حصلت على",)
_SUBSCRIPTION_DATA = ("جيجا", "دقائق دولية", "رسائل محلية", "رقمك هو", "U5G", "GB")

# Government notice — official government announcements
_GOV_NOTICE_HINTS = (
    "التعداد السكاني",
    "دائرة الإحصاءات",
    "دائرة الاحصاءات",
    "وزارة العدل",
    "تصريح الحج",
    "مكافحة المخدرات",
    "الرقم المجاني 117",
    "واجب وطني",
    "امر الدفع رقم",    # payment order number (gov receipt) — plain alef matches normalizer output
)

# Survey / feedback — customer satisfaction requests
_SURVEY_HINTS = (
    "استبيان",
    "رضاكم",
    "رضاك عن",
    "رضى الزبائن",
    "رضا الزبائن",
    "تقييم تجربتك",
    "تقييم خدمتنا",
)

# Promotional — offer/bundle/event messages
_PROMO_INDICATORS = (
    "خصم",           # discount
    "عروض",          # offers
    "باقة",          # package/bundle
    "اشترك الآن",
    "اشترك الان",
    "احجز",          # book/reserve
    "مجاناً",
    "مجانا",
    "مهرجان",        # festival
    "هاكثون",        # hackathon
    "أكاديمية",      # academy
    "اكاديمية",      # academy (normalized)
    "ورشة عمل",      # workshop
    "بطولة",         # championship
    "دوري",          # league
    "ريال بس",       # just X riyals
    "بدل",           # instead of (price comparison)
    "لفترة محدودة",  # limited time
    "فرصة ربح",      # chance to win
    "السحب",         # raffle/draw
    "صوّت",          # vote
    "صوت",           # vote (unvocalized)
    "التوفير",       # savings
    "وفّر",          # save (money)
    "وفر",           # save (unvocalized)
    "سعر خاص",       # special price
    "عرض خاص",       # special offer
    "تسجيل الآن",    # register now
    "تسجيل الان",    # register now (unvocalized)
    "التسجيل مجاني", # free registration
    "حضور مجاني",    # free attendance
    "ادعوك",         # I invite you
    "ندعوك",         # we invite you
    "انضم إلينا",    # join us
    "انضم الينا",    # join us (unvocalized)
    "جوائز",         # prizes
    "قسيمة",         # voucher/coupon
    "كوبون",         # coupon
)


class ActionDetectorAdapter:
    """
    Detects requested actions (and negations) from normalized text, then
    applies context rules (awareness / OTP delivery / bank transaction /
    app-verification safe contexts).
    """

    def __init__(self) -> None:
        self._intents = _IntentDetector()
        self._context = _ContextDetector()

    def detect(self, normalized: str, entities: EntityResult) -> IntentResult:
        """
        Run intent detection followed by context detection.

        Context detection may set intents.safe_context and add safe signals
        that the policy engine uses for safe-cap decisions.
        """
        intents = self._intents.detect(normalized, entities)
        # Context detector mutates intents.safe_context in place and returns
        # additional signals — we discard those signals here because the
        # evidence builder re-derives them from the IntentResult.
        self._context.apply(intents, entities)
        self._apply_risk_engine_stabilizers(normalized or "", intents)
        return intents

    @staticmethod
    def _apply_risk_engine_stabilizers(text: str, intents: IntentResult) -> None:
        """
        Narrow context refinements for Risk Engine v1 stabilization.
        """
        if _OTP_CODE_RE.search(text) and intents.has("otp_delivery"):
            intents.intents.add("otp_code_delivery")

        # Primary awareness hints (original set)
        if any(hint in text for hint in _AWARENESS_HINTS):
            intents.intents.add("educational_awareness")
            intents.awareness = True
            intents.safe_context = intents.safe_context or "educational_awareness"

        # Extended awareness — clear security-education patterns
        if any(hint in text for hint in _EXTENDED_AWARENESS_HINTS):
            intents.intents.add("educational_awareness")
            intents.awareness = True
            intents.safe_context = intents.safe_context or "educational_awareness"

        # OTP delivery without explicit "do not share" — recognise delivery phrases
        # Only set safe_context when no dangerous request is active.
        # Note: otp_request guard removed — v5 sets otp_request even for delivery msgs.
        if (
            _OTP_CODE_RE.search(text)
            and any(phrase in text for phrase in _OTP_DELIVERY_PHRASES)
            and not intents.dangerous_text_request
        ):
            intents.intents.add("otp_code_delivery")
            intents.intents.add("otp_delivery")
            if not intents.safe_context:
                intents.safe_context = "otp_delivery"

        if all(hint in text for hint in _BANK_STATEMENT_HINTS):
            intents.card_data_request = False
            if not (intents.otp_request or intents.password_request):
                intents.credential_request = False
                intents.dangerous_text_request = False
                intents.intents.discard("sensitive_data_request")
                intents.intents.discard("credential_harvesting")
                intents.evidence.pop("sensitive_request", None)
            intents.intents.add("bank_transaction")

        # ── Official safe context detection ───────────────────────────────────
        # These intents feed into classify_message for fine-grained categories.
        # All are gated on no dangerous_text_request so they never mask phishing.

        if not intents.dangerous_text_request:
            # Government notice
            if any(hint in text for hint in _GOV_NOTICE_HINTS):
                intents.intents.add("government_notice_context")

            # Survey / customer feedback
            if any(hint in text for hint in _SURVEY_HINTS):
                intents.intents.add("survey_context")

            # Subscription welcome / allocation notice
            if (
                any(hint in text for hint in _SUBSCRIPTION_REQUIRED)
                and any(data in text for data in _SUBSCRIPTION_DATA)
            ):
                intents.intents.add("subscription_notice_context")

            # Service notification (telecom/service status)
            if any(hint in text for hint in _SERVICE_NOTIF_HINTS):
                intents.intents.add("service_notification_context")

            # Promotional message (1 indicator is sufficient for clear promo terms)
            _promo_hits = sum(1 for p in _PROMO_INDICATORS if p in text)
            if _promo_hits >= 1:
                intents.intents.add("promotional_context")
