"""
APG Risk Intelligence Engine v1 — Message Intent Detector

Classifies the *purpose* of a message independently of its security
classification.  Unlike message_category (which is security-first),
message_intent describes what the message is communicating or trying to do.

Priority order (highest → lowest):
  credential_phishing > financial_phishing > suspicious_link >
  otp_code > security_advice > payment_notice > transactional >
  survey_feedback > service_notice > advertisement > normal > unknown

Rules are deterministic and keyword-based — no external calls, no model
inference.  The action_detector's already-detected intents are the primary
source; this module adds only the payment-specific patterns that are not
already captured upstream.
"""
from __future__ import annotations

from app.services.analyzer.schemas import EntityResult, IntentResult
from .schemas import MessageCategory, URLIntelligence

# ── Payment-specific indicators ───────────────────────────────────────────────
# These are past-tense payment confirmation phrases not covered by the
# action_detector's promotional/service/bank-transaction hint lists.
# Include both Arabic (hamza-stripped / normalized) and common variants.
_PAYMENT_STRONG_HINTS: tuple[str, ...] = (
    "تم دفع مبلغ",
    "تم استلام مبلغ",
    "تم الدفع",
    "تم تحصيل",
    "امر الدفع",        # أمر الدفع → normalised (alef hamza stripped)
    "أمر الدفع",        # raw form — kept for non-normalised callers
    "ايفواتيركم",       # eFawateerCom — normalised
    "اي فواتيركم",      # spaced form
    "إي فواتيركم",      # raw form
    "وصلت دفعة",
    "وصلت دفعه",        # ة→ه normalised form
    "المبلغ المدفوع",
    "وصل مالي",         # financial remittance notification
)

# ── Security-advice indicators ────────────────────────────────────────────────
# Both ة (raw) and ه (normalised) forms are included because some normalizers
# convert ta-marbuta (ة) to ha (ه).  Any single match is sufficient given the
# dangerous_text_request guard in the caller.
_SECURITY_ADVICE_HINTS: tuple[str, ...] = (
    # Negation / warning phrases — strong indicators (raw and normalised forms)
    "يرجى عدم مشاركة",      # please do not share (explicit phrase in test E)
    "يرجى عدم مشاركه",      # ة→ه form
    "عدم مشاركة",            # do not share (gerund)
    "عدم مشاركه",            # ة→ه form
    "لا تشارك",              # don't share
    "لا تعطي",               # don't give
    "ما تعطي",               # don't give (dialect)
    "لن نطلب منك",           # we will never ask you for
    # Fraud / phishing education
    "صفحات وهمية",           # fake pages (ة form)
    "صفحات وهميه",           # ة→ه form
    "محاولات الاحتيال",      # fraud attempts
    "محاولة احتيال",          # fraud attempt (ة form)
    "محاوله احتيال",          # ة→ه form
    "روابط غير موثوقة",      # untrustworthy links (ة form)
    "روابط غير موثوقه",      # ة→ه form
    "روابط مشبوهة",          # suspicious links (ة form)
    "روابط مشبوهه",          # ة→ه form
    "الاحتيال والاختراق",    # fraud and hacking
    "احتيال الكتروني",       # electronic fraud (normalised hamza)
    "احتيال إلكتروني",       # electronic fraud (raw)
    "تنبيه امني",            # security warning (normalised hamza)
    "تنبيه أمني",            # security warning (raw)
    # Banking/OTP protection warnings
    "معلومات بنكية",         # banking information (ة form) — in advisory context
    "معلومات بنكيه",         # ة→ه form
)

# ── Advertisement indicators (direct text fallback) ───────────────────────────
# Used when upstream promotional_context intent is not set (e.g. normalizer
# converts ة→ه so "لفترة محدودة" becomes "لفتره محدوده" and the upstream hint
# list no longer matches).
#
# Strong: 1 match → advertisement.
# Weak:   2+ matches required to avoid false positives on single ambiguous words
#         like "متجر" (store) or "سحب" (draw).
_ADVERTISEMENT_STRONG: tuple[str, ...] = (
    "لفترة محدودة",   # limited time (ة form)
    "لفتره محدوده",   # ة→ه normalised form
    "لفترة محدوده",   # mixed form
    "لفتره محدودة",   # mixed form
    "تخفيضات",        # discounts (no ة, safe)
    "اشترك الآن",     # subscribe now
    "اشترك الان",     # subscribe now (normalised hamza)
)

_ADVERTISEMENT_WEAK: tuple[str, ...] = (
    "خصم",            # discount
    "عروض",           # offers
    "متجر",           # store / shop
    "اشترك",          # subscribe
    "اربح",           # win
    "سحب",            # draw / raffle
    "فرصة",           # opportunity (ة form)
    "فرصه",           # ة→ه normalised form
    "تخفيض",          # discount (singular)
    "عرض خاص",        # special offer
    "سعر خاص",        # special price
    "مجانا",          # free
    "مجاناً",         # free
    "جوائز",          # prizes
    "قسيمة",          # voucher / coupon (ة form)
    "قسيمه",          # ة→ه form
    "كوبون",          # coupon
    "ندعوك",          # we invite you
    "ادعوك",          # I invite you
    "انضم",           # join
)


def detect_message_intent(
    entities: EntityResult,
    intents: IntentResult,
    url_intel: URLIntelligence,
    message_category: MessageCategory,
    normalized_text: str,
) -> tuple[str, float]:
    """
    Return (message_intent, intent_confidence).

    Guaranteed to return a value; never raises.

    message_intent values:
      credential_phishing  — message explicitly requests credentials (OTP, password, card)
      financial_phishing   — malicious/suspicious URL targeting financial context
      suspicious_link      — suspicious URL or brand impersonation without credential request
      otp_code             — legitimate OTP delivery (code provided, do-not-share implied)
      security_advice      — message warns user about phishing / fraud / not sharing data
      payment_notice       — payment confirmation or receipt
      transactional        — bank/financial status notification (no specific payment event)
      survey_feedback      — customer satisfaction survey or feedback request
      service_notice       — service maintenance, outage, subscription, telecom notice
      advertisement        — promotional / marketing / offer message
      normal               — casual or purely informational message
      unknown              — cannot be classified with sufficient confidence
    """
    text = normalized_text or ""

    # ── 1. Credential phishing ────────────────────────────────────────────────
    # Message explicitly requests OTP, password, card, or credentials.
    # Safety rule: this wins over any other classification — always.
    if intents.dangerous_text_request:
        return "credential_phishing", 0.97

    # ── 2. Financial phishing (malicious URL + financial entity) ─────────────
    # Malicious URL check is separate so financial context sharpens the label.
    if url_intel.verdict == "malicious":
        if entities.has_bank_or_account:
            return "financial_phishing", 0.95
        return "suspicious_link", 0.92

    # ── 3. Brand impersonation ────────────────────────────────────────────────
    if url_intel.brand_impersonation:
        return "suspicious_link", 0.88

    # ── 4. Suspicious URL (not fully malicious) ───────────────────────────────
    if url_intel.verdict == "suspicious":
        if entities.has_bank_or_account:
            return "financial_phishing", 0.78
        return "suspicious_link", 0.72

    # ── 5. OTP code delivery ──────────────────────────────────────────────────
    # Must come BEFORE security_advice so that "رمز التفعيل…لا تشارك" returns
    # otp_code rather than security_advice.
    if (
        intents.has("otp_code_delivery")
        or intents.has("otp_delivery")
        or message_category in ("otp_delivery", "app_verification")
    ) and not intents.dangerous_text_request:
        return "otp_code", 0.93

    # ── 6. Security advice ────────────────────────────────────────────────────
    # Check both the existing awareness flag AND the extended hint list so that
    # messages like "يرجى عدم مشاركة رمز OTP" are captured even when the
    # upstream IntentDetector does not set intents.awareness.
    # Both ة and ه forms are in _SECURITY_ADVICE_HINTS to survive normalizers
    # that convert ta-marbuta (ة) to ha (ه).
    _has_advice_hint = any(hint in text for hint in _SECURITY_ADVICE_HINTS)
    if (intents.awareness or _has_advice_hint) and not intents.dangerous_text_request:
        return "security_advice", 0.90

    # ── 7. Payment notice ─────────────────────────────────────────────────────
    # Strong past-tense payment confirmation phrases.
    if any(hint in text for hint in _PAYMENT_STRONG_HINTS):
        return "payment_notice", 0.88

    # ── 8. Transactional / financial notification ─────────────────────────────
    if (
        intents.has("bank_transaction")
        or message_category in ("bank_transaction", "transactional", "government_notice", "payment_receipt")
    ):
        return "transactional", 0.83

    # ── 9. Survey / customer feedback ────────────────────────────────────────
    if intents.has("survey_context") or message_category == "survey":
        return "survey_feedback", 0.88

    # ── 10. Service / subscription / maintenance notice ──────────────────────
    if (
        intents.has("service_notification_context")
        or intents.has("subscription_notice_context")
        or message_category in ("service_notification", "subscription_notice")
    ):
        return "service_notice", 0.87

    # ── 11. Advertisement / promotional ──────────────────────────────────────
    # Primary: upstream intent flag or message_category (fast path).
    # Fallback: direct text scan using _ADVERTISEMENT_STRONG / _ADVERTISEMENT_WEAK.
    # This catches cases where upstream promotional_context was not set because
    # the normalizer changed ة→ه in hint strings like "لفترة محدودة".
    _strong_promo = any(h in text for h in _ADVERTISEMENT_STRONG)
    _weak_promo_hits = sum(1 for h in _ADVERTISEMENT_WEAK if h in text)
    if (
        intents.has("promotional_context")
        or message_category == "promotional"
        or _strong_promo
        or _weak_promo_hits >= 2
    ):
        return "advertisement", 0.85

    # ── 12. Normal / informational ────────────────────────────────────────────
    if (
        message_category == "casual"
        or intents.has("casual")
        or intents.has("informational_notification")
    ):
        return "normal", 0.78

    # ── 13. Suspicious link fallback (URL present, no cleaner label matched) ──
    if url_intel.has_link_surface and message_category == "link_action":
        return "suspicious_link", 0.55

    return "unknown", 0.40
