# -*- coding: utf-8 -*-
"""
APG Behavioral Phishing Detector

Detects implicit phishing patterns in Arabic messages by matching phrase
groups loaded from app/data/ar_behavioral_phrases.json.

Design principles
-----------------
  - Phrase data is loaded once via an lru_cache singleton; never re-read per
    request.
  - Arabic normalization: remove tatweel, strip diacritics (explicit Unicode
    hex ranges only — avoids editor/codec issues), unify alef variants, e->h,
    collapse whitespace, lowercase.
  - Diacritics regex uses explicit Unicode escape sequences throughout so the
    compiled regex is identical regardless of file encoding or editor code page.
  - The detector is ADVISORY for weak signals; Rule A / C (account-takeover +
    URL and payment phishing + URL) produce dangerous_intent / critical evidence
    so the policy engine's 70-cap is lifted and the score reaches block range.
  - Safe reductions (safe_guardrail / safe_service) are suppressed when
    intents.dangerous_text_request is True.
  - VirusTotal precedence is preserved: policy Phase-1 Rule-1 fires on
    url_intel.verdict == "malicious" before any evidence scoring.

Fusion rules
------------
  account_state + action + url      -> account_takeover_flow  +85  dangerous/critical
  account_state + action + urgency  -> account_takeover_flow  +30  suspicious/high
  payment/card action   + url       -> payment_phishing_flow  +85  dangerous/critical
  urgency + action  (no above)      -> urgency_action signal  +15  suspicious/medium
  safe_guardrail hit (no danger)    -> safe_awareness_context -15  safe/info
  safe_service   hit (no danger)    -> safe_service_context   -10  safe/info
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schemas import Evidence

# ─── Data file path ───────────────────────────────────────────────────────────

_PHRASE_FILE = (
    Path(__file__).parent.parent.parent / "data" / "ar_behavioral_phrases.json"
)

# ─── Arabic normalization ─────────────────────────────────────────────────────
# ALL Arabic ranges expressed as \u hex escapes so the regex compiles
# identically on every platform, editor, and console code page.
#
# Diacritics-only ranges (do NOT include U+0621-U+064A Arabic letters):
#   U+0610-U+061A  Arabic sign marks
#   U+064B-U+065F  Arabic diacritics (fathatan … wavy hamza below)
#   U+0670         Arabic letter superscript alef
#   U+06D6-U+06ED  Arabic small high/low decorative marks
_DIACRITICS_RE = re.compile(
    "[ؐ-ًؚ-ٰٟۖ-ۭ]"
)
_TATWEEL_RE = re.compile("ـ+")    # U+0640 tatweel / kashida
_ALEF_MAP = str.maketrans({
    "أ": "ا",  # أ -> ا
    "إ": "ا",  # إ -> ا
    "آ": "ا",  # آ -> ا
    "ٱ": "ا",  # ٱ -> ا
    "ة": "ه",  # ة -> ه
    "ى": "ي",  # ى -> ي
})
_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Normalize Arabic text for phrase matching."""
    v = (text or "").strip()
    if not v:
        return ""
    v = _DIACRITICS_RE.sub("", v)
    v = _TATWEEL_RE.sub("", v)
    v = v.translate(_ALEF_MAP)
    v = _WS_RE.sub(" ", v)
    return v.strip().lower()


# ─── Phrase data singleton ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_phrases() -> dict[str, list[str]]:
    """Load and normalize phrase lists from JSON — called once at startup."""
    raw = json.loads(_PHRASE_FILE.read_text(encoding="utf-8"))
    base_keys = (
        "account_state_terms_ar",
        "action_terms_ar",
        "urgency_terms_ar",
        "safe_guardrail_terms_ar",
        "safe_service_patterns_ar",
    )
    family_keys = (
        "account_takeover_terms_ar",
        "otp_theft_terms_ar",
        "password_theft_terms_ar",
        "payment_fee_terms_ar",
        "wallet_freeze_terms_ar",
        "delivery_customs_terms_ar",
        "fake_government_terms_ar",
        "bank_kyc_update_terms_ar",
        "whatsapp_takeover_terms_ar",
        "social_account_terms_ar",
        "prize_reward_scam_terms_ar",
        "subscription_suspension_terms_ar",
        "safe_promo_terms_ar",
        "safe_receipt_terms_ar",
        "safe_awareness_terms_ar",
    )
    keys = base_keys + family_keys
    return {
        k: [n for n in (_norm(p) for p in raw.get(k, [])) if n]
        for k in keys
    }


# ─── Payment / card / wallet action keywords ─────────────────────────────────
# Subset of action_terms that signal financial-data phishing specifically.
# These keywords are checked against action_hits to trigger Rule C.
# Use _norm() so the set is consistent with phrase normalization.

_PAYMENT_KEYWORDS_RAW = (
    "بيانات البطاقة",  # بيانات البطاقة
    "رقم البطاقة",                    # رقم البطاقة
    "رمز البطاقة",                    # رمز البطاقة
    "أدخل رمز التحقق", # أدخل رمز التحقق
    "أرسل رمز التحقق", # أرسل رمز التحقق
    "شارك رمز التفعيل", # شارك رمز التفعيل
    "أرسل الكود",                          # أرسل الكود
    "رد برسالة تحتوي الرمز",  # رد برسالة تحتوي الرمز
    "رد بالكود",                                # رد بالكود
    "أدخل كلمة المرور", # أدخل كلمة المرور
    "غير كلمة المرور",  # غير كلمة المرور
    "أكد عملية الدفع",  # أكد عملية الدفع
    "ادفع الرسوم",                    # ادفع الرسوم
    "سدد الفاتورة",               # سدد الفاتورة
    "أكمل الدفع",                          # أكمل الدفع
    "أعد محاولة الدفع", # أعد محاولة الدفع
    "ادفع رسوم",                                # ادفع رسوم
    "ادفع عبر",                                      # ادفع عبر
    "ادفع من هنا",                         # ادفع من هنا
    "تأكيد الرقم السري",  # تأكيد الرقم السري
    "تاكيد pin",                                               # تاكيد pin
    "تاكيد الرقم السري", # تاكيد الرقم السري (normalized)
    "ادخل ايبان",                          # ادخل ايبان
    "فعل الصرف",                                # فعل الصرف
    "يرجى دفع",                              # يرجى دفع
    "ادفع من",                                    # ادفع من (short form)
    "الدفع الفوري",               # الدفع الفوري
    "الدفع قبل",                          # الدفع قبل [deadline]
)

_PAYMENT_KEYWORDS: frozenset[str] = frozenset(
    _norm(t) for t in _PAYMENT_KEYWORDS_RAW if _norm(t)
)


def _has_payment_action(action_hits: list[str]) -> bool:
    return any(h in _PAYMENT_KEYWORDS for h in action_hits)


_FAMILY_KEYS: tuple[str, ...] = (
    "account_takeover_terms_ar",
    "otp_theft_terms_ar",
    "password_theft_terms_ar",
    "payment_fee_terms_ar",
    "wallet_freeze_terms_ar",
    "delivery_customs_terms_ar",
    "fake_government_terms_ar",
    "bank_kyc_update_terms_ar",
    "whatsapp_takeover_terms_ar",
    "social_account_terms_ar",
    "prize_reward_scam_terms_ar",
    "subscription_suspension_terms_ar",
    "safe_promo_terms_ar",
    "safe_receipt_terms_ar",
    "safe_awareness_terms_ar",
)


def _family_has(family_hits: dict[str, list[str]], *keys: str) -> bool:
    return any(bool(family_hits.get(key)) for key in keys)


def _first_family_hit(family_hits: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        hits = family_hits.get(key) or []
        if hits:
            return hits[0]
    return ""


_FAMILY_ACTION_MARKERS_RAW: tuple[str, ...] = (
    "تحديث",
    "تفعيل",
    "تأكيد",
    "تاكيد",
    "مراجعة",
    "مراجعه",
    "تحقق",
    "استكمال",
    "تصديق",
    "ادخل",
    "أدخل",
    "ارسل",
    "أرسل",
    "انقل",
    "سجل",
    "ادفع",
    "سدد",
    "استلم",
    "استلام",
)

_FAMILY_ACTION_MARKERS: tuple[str, ...] = tuple(
    n for n in (_norm(p) for p in _FAMILY_ACTION_MARKERS_RAW) if n
)


def _has_family_action(family_hits: dict[str, list[str]]) -> bool:
    return any(
        marker in hit
        for hits in family_hits.values()
        for hit in hits
        for marker in _FAMILY_ACTION_MARKERS
    )


def _add_family_evidence(
    evidence: list[Evidence],
    *,
    ev_id: str,
    category: str,
    severity: str,
    score_delta: int,
    confidence: float,
    matched_text: str,
    explanation_ar: str,
    explanation_en: str,
) -> int:
    evidence.append(Evidence(
        id=ev_id,
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        score_delta=score_delta,
        confidence=confidence,
        matched_text=matched_text,
        explanation_ar=explanation_ar,
        explanation_en=explanation_en,
    ))
    return score_delta


_PSYCHOLOGICAL_PRESSURE_RAW: dict[str, tuple[str, ...]] = {
    "urgency": (
        "فوراً", "فورا", "عاجل", "الآن", "الان", "خلال دقائق",
        "خلال 10 دقائق", "before midnight", "immediately", "urgent",
    ),
    "fear_threat": (
        "سيتم إغلاق حسابك", "سيتم اغلاق حسابك", "حسابك معرض للإغلاق",
        "حسابك معرض للاغلاق", "تم تعليق حسابك", "سيتم إيقاف الخدمة",
        "سيتم ايقاف الخدمة", "لتجنب الإيقاف", "لتجنب الايقاف",
        "unauthorized access", "account suspended", "account locked",
    ),
    "reward_lure": (
        "ربحت", "جائزة", "جوائز", "هدية", "مكافأة", "مكافاه",
        "free gift", "prize", "reward",
    ),
    "authority_support": (
        "الدعم الفني", "خدمة العملاء", "فريق الأمان", "فريق الامان",
        "security team", "support center",
    ),
}

_PSYCHOLOGICAL_PRESSURE: dict[str, tuple[str, ...]] = {
    key: tuple(n for n in (_norm(p) for p in values) if n)
    for key, values in _PSYCHOLOGICAL_PRESSURE_RAW.items()
}

_PSYCHOLOGICAL_EXPLANATIONS: dict[str, tuple[str, str]] = {
    "urgency": (
        "behavioral_psychological_urgency",
        "الرسالة تستخدم استعجالًا لدفعك لاتخاذ إجراء.",
    ),
    "fear_threat": (
        "behavioral_psychological_fear_threat",
        "الرسالة تستخدم تهديدًا بإغلاق الحساب أو الخدمة.",
    ),
    "reward_lure": (
        "behavioral_psychological_reward_lure",
        "الرسالة تستخدم إغراءً بجائزة أو مكافأة.",
    ),
    "authority_support": (
        "behavioral_psychological_authority_support",
        "الرسالة تنتحل أسلوب الدعم أو فريق الأمان.",
    ),
}

_PSYCHOLOGICAL_BASE_SCORES = {
    "urgency": 24,
    "fear_threat": 34,
    "reward_lure": 28,
    "authority_support": 26,
}


def _pressure_hits(normed: str, group: str) -> list[str]:
    hits = [p for p in _PSYCHOLOGICAL_PRESSURE[group] if p in normed]
    if group == "urgency" and re.search(r"\bخلال\s+\d+\s+دق", normed):
        hits.append("خلال دقائق")
    return hits


def _add_psychological_pressure_evidence(
    evidence: list[Evidence],
    pressure_hits: dict[str, list[str]],
    *,
    has_url: bool,
    has_credential_request: bool,
    has_known_entity: bool,
    has_payment_context: bool,
    safe_context: bool,
    dangerous_text_request: bool,
) -> int:
    if safe_context and not dangerous_text_request:
        return 0

    active_groups = [group for group, hits in pressure_hits.items() if hits]
    if not active_groups:
        return 0

    context_count = sum([
        has_url,
        has_credential_request,
        has_known_entity,
        has_payment_context,
    ])
    has_context = context_count > 0
    score_delta = 0

    for group in active_groups:
        ev_id, explanation_ar = _PSYCHOLOGICAL_EXPLANATIONS[group]
        score = _PSYCHOLOGICAL_BASE_SCORES[group] if has_context else 0
        severity = "medium" if score >= 30 else "low" if score > 0 else "info"
        confidence = 0.72 if has_context else 0.55
        score_delta += score
        evidence.append(Evidence(
            id=ev_id,
            category="suspicious_context",
            severity=severity,  # type: ignore[arg-type]
            score_delta=score,
            confidence=confidence,
            matched_text=pressure_hits[group][0],
            explanation_ar=explanation_ar,
            explanation_en=(
                "Message uses psychological pressure language; treated as "
                "advisory unless combined with URL, credential, known-entity, "
                "or payment context."
            ),
        ))

    if len(active_groups) >= 2 and context_count >= 2:
        score_delta += 58
        evidence.append(Evidence(
            id="behavioral_psychological_pressure_combo",
            category="suspicious_context",
            severity="high",
            score_delta=58,
            confidence=0.82,
            matched_text=", ".join(pressure_hits[group][0] for group in active_groups[:3]),
            explanation_ar=(
                "الرسالة تجمع أكثر من أسلوب ضغط نفسي مع رابط أو طلب حساس أو جهة معروفة."
            ),
            explanation_en=(
                "Multiple psychological pressure patterns appear together with "
                "URL, credential, known-entity, or payment context."
            ),
        ))

    return score_delta


# ─── Main detector ────────────────────────────────────────────────────────────

def detect_behavioral_phishing(
    text: str,
    has_url: bool = False,
    dangerous_text_request: bool = False,
    has_credential_request: bool = False,
    has_known_entity: bool = False,
    has_payment_context: bool = False,
    safe_context: bool = False,
) -> dict[str, Any]:
    """
    Analyse *text* for behavioural phishing patterns.

    Parameters
    ----------
    text                   : raw (un-normalized) message text
    has_url                : True if any URL / link surface was detected by
                             the URL intelligence layer
    dangerous_text_request : value of intents.dangerous_text_request — when
                             True, safe reductions are suppressed

    Returns
    -------
    {
      "account_state_hits":   list[str],
      "action_hits":          list[str],
      "urgency_hits":         list[str],
      "safe_guardrail_hits":  list[str],
      "safe_service_hits":    list[str],
      "behavioral_flags": {
          "account_takeover_flow":  bool,
          "payment_phishing_flow":  bool,
          "safe_awareness_context": bool,
          "safe_service_context":   bool,
      },
      "score_delta":  int,
      "evidence":     list[Evidence],
    }
    """
    phrases = _load_phrases()
    normed = _norm(text)

    # ── Phase 1: match each group ─────────────────────────────────────────────
    acct_hits    = [p for p in phrases["account_state_terms_ar"]   if p in normed]
    action_hits  = [p for p in phrases["action_terms_ar"]          if p in normed]
    urgency_hits = [p for p in phrases["urgency_terms_ar"]         if p in normed]
    guard_hits   = [p for p in phrases["safe_guardrail_terms_ar"]  if p in normed]
    svc_hits     = [p for p in phrases["safe_service_patterns_ar"] if p in normed]
    family_hits = {
        key: [p for p in phrases.get(key, []) if p in normed]
        for key in _FAMILY_KEYS
    }
    psychological_hits = {
        group: _pressure_hits(normed, group)
        for group in _PSYCHOLOGICAL_PRESSURE
    }

    # ── Phase 2: fusion logic ─────────────────────────────────────────────────
    score_delta = 0
    evidence: list[Evidence] = []

    account_takeover = False
    payment_phishing = False
    safe_awareness   = False
    safe_service     = False

    # Rule A — account-takeover: problem-state + action + URL
    # Uses dangerous_intent/critical so the policy engine's 70-cap is lifted.
    if acct_hits and action_hits and has_url:
        account_takeover = True
        score_delta += 85
        evidence.append(Evidence(
            id="behavioral_account_takeover_url",
            category="dangerous_intent",
            severity="critical",
            score_delta=85,
            confidence=0.85,
            matched_text=acct_hits[0],
            explanation_ar=(
                "تظهر الرسالة نمطاً سلوكياً "
                "لتصيد الحسابات: "
                "مشكلة في الحساب مع طلب إجراء عبر رابط."
            ),
            explanation_en=(
                "Message exhibits account-takeover phishing pattern: "
                "account problem + action request + URL."
            ),
        ))

    # Rule B — account-takeover: problem-state + action + urgency (no URL)
    elif acct_hits and action_hits and urgency_hits:
        account_takeover = True
        score_delta += 30
        evidence.append(Evidence(
            id="behavioral_account_takeover_urgency",
            category="suspicious_context",
            severity="high",
            score_delta=30,
            confidence=0.78,
            matched_text=urgency_hits[0],
            explanation_ar=(
                "تظهر الرسالة نمطاً سلوكياً "
                "لتصيد الحسابات: "
                "مشكلة في الحساب مع طلب إجراء واستعجال."
            ),
            explanation_en=(
                "Message exhibits account-takeover phishing pattern: "
                "account problem + action request + urgency."
            ),
        ))

    # Rule C — payment phishing: payment-specific action + URL (independent of acct)
    # Uses dangerous_intent/critical so the policy engine's 70-cap is lifted.
    if not account_takeover and _has_payment_action(action_hits) and has_url:
        payment_phishing = True
        score_delta += 85
        evidence.append(Evidence(
            id="behavioral_payment_phishing",
            category="dangerous_intent",
            severity="critical",
            score_delta=85,
            confidence=0.83,
            matched_text=action_hits[0] if action_hits else "",
            explanation_ar=(
                "تظهر الرسالة نمطاً سلوكياً "
                "لتصيد بيانات الدفع: "
                "طلب إدخال بيانات بطاقة أو رمز تحقق عبر رابط."
            ),
            explanation_en=(
                "Message exhibits payment phishing pattern: "
                "card / verification-code action + URL."
            ),
        ))

    has_otp_family = _family_has(family_hits, "otp_theft_terms_ar")
    has_password_family = _family_has(family_hits, "password_theft_terms_ar")
    has_payment_family = _family_has(family_hits, "payment_fee_terms_ar")
    has_sensitive_family = has_otp_family or has_password_family
    has_any_action = bool(
        action_hits
        or has_credential_request
        or has_payment_family
        or _has_family_action(family_hits)
    )

    # V2 family rules: controlled combinations only. Broad family hits are not
    # scored alone; they require URL/link surface and action/payment/sensitive
    # context unless a direct credential request already exists.
    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "account_takeover_terms_ar")
        and has_url
        and has_any_action
    ):
        account_takeover = True
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_account_takeover_v2",
            category="dangerous_intent",
            severity="critical",
            score_delta=85,
            confidence=0.84,
            matched_text=_first_family_hit(family_hits, "account_takeover_terms_ar"),
            explanation_ar="الرسالة تجمع حالة حساب مقلقة مع طلب إجراء عبر رابط.",
            explanation_en="Account-state risk context is combined with an action request and link surface.",
        )

    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "wallet_freeze_terms_ar")
        and has_url
        and has_any_action
    ):
        account_takeover = True
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_wallet_freeze_reactivation",
            category="dangerous_intent",
            severity="critical",
            score_delta=85,
            confidence=0.84,
            matched_text=_first_family_hit(family_hits, "wallet_freeze_terms_ar"),
            explanation_ar="الرسالة تجمع تجميد محفظة أو حوالة مع طلب إعادة تفعيل عبر رابط.",
            explanation_en="Wallet/fund freeze context is combined with an action request and link surface.",
        )

    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "bank_kyc_update_terms_ar")
        and has_url
        and has_any_action
    ):
        account_takeover = True
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_bank_kyc_update",
            category="dangerous_intent",
            severity="critical",
            score_delta=85,
            confidence=0.84,
            matched_text=_first_family_hit(family_hits, "bank_kyc_update_terms_ar"),
            explanation_ar="الرسالة تطلب تحديث بيانات بنكية أو اعرف عميلك عبر رابط.",
            explanation_en="Bank/KYC update context is combined with an action request and link surface.",
        )

    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "whatsapp_takeover_terms_ar", "social_account_terms_ar")
        and (has_sensitive_family or has_credential_request or has_url)
        and has_any_action
    ):
        account_takeover = True
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_whatsapp_social_takeover",
            category="dangerous_intent",
            severity="critical",
            score_delta=85,
            confidence=0.84,
            matched_text=_first_family_hit(
                family_hits, "whatsapp_takeover_terms_ar", "social_account_terms_ar"
            ),
            explanation_ar="الرسالة تجمع سياق واتساب أو حساب اجتماعي مع طلب رمز أو تحقق.",
            explanation_en="WhatsApp/social-account context is combined with credential or verification action.",
        )

    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "delivery_customs_terms_ar")
        and has_url
        and (has_payment_family or _has_payment_action(action_hits))
    ):
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_delivery_customs_fee",
            category="suspicious_context",
            severity="high",
            score_delta=68,
            confidence=0.80,
            matched_text=_first_family_hit(family_hits, "delivery_customs_terms_ar"),
            explanation_ar="الرسالة تربط شحنة أو تخليصاً جمركياً برسوم أو دفع عبر رابط.",
            explanation_en="Delivery/customs context is combined with fee/payment request and link surface.",
        )

    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "fake_government_terms_ar")
        and has_url
        and (has_payment_family or has_any_action)
    ):
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_fake_government_payment",
            category="suspicious_context",
            severity="high",
            score_delta=68,
            confidence=0.80,
            matched_text=_first_family_hit(family_hits, "fake_government_terms_ar"),
            explanation_ar="الرسالة تستخدم سياق خدمة أو رسوم حكومية مع رابط إجراء.",
            explanation_en="Government-service context is combined with payment/action request and link surface.",
        )

    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "prize_reward_scam_terms_ar")
        and has_url
        and (has_payment_family or has_credential_request or has_any_action)
    ):
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_prize_reward_phishing",
            category="suspicious_context",
            severity="high",
            score_delta=68,
            confidence=0.78,
            matched_text=_first_family_hit(family_hits, "prize_reward_scam_terms_ar"),
            explanation_ar="الرسالة تربط جائزة أو مكافأة بطلب إجراء أو دفع عبر رابط.",
            explanation_en="Prize/reward lure is combined with payment, credential, or action link context.",
        )

    if (
        not (account_takeover or payment_phishing)
        and not (safe_context and not dangerous_text_request)
        and _family_has(family_hits, "subscription_suspension_terms_ar")
        and has_url
        and has_any_action
    ):
        score_delta += _add_family_evidence(
            evidence,
            ev_id="behavioral_subscription_suspension",
            category="suspicious_context",
            severity="high",
            score_delta=62,
            confidence=0.77,
            matched_text=_first_family_hit(family_hits, "subscription_suspension_terms_ar"),
            explanation_ar="الرسالة تربط إيقاف خدمة أو اشتراك بطلب إجراء عبر رابط.",
            explanation_en="Subscription/service suspension context is combined with action and link surface.",
        )

    # Rule D — urgency + action partial signal (no stronger pattern matched)
    if urgency_hits and action_hits and not (account_takeover or payment_phishing):
        score_delta += 15
        evidence.append(Evidence(
            id="behavioral_urgency_action",
            category="suspicious_context",
            severity="medium",
            score_delta=15,
            confidence=0.65,
            matched_text=urgency_hits[0],
            explanation_ar=(
                "توجد مؤشرات ضغط أو استعجال مرتبطة بطلب إجراء."
            ),
            explanation_en=(
                "Message combines urgency signals with an action request."
            ),
        ))

    # Rule E — safe guardrail (reduce score, suppressed when danger active)
    score_delta += _add_psychological_pressure_evidence(
        evidence,
        psychological_hits,
        has_url=has_url,
        has_credential_request=has_credential_request,
        has_known_entity=has_known_entity,
        has_payment_context=has_payment_context,
        safe_context=safe_context,
        dangerous_text_request=dangerous_text_request,
    )

    if guard_hits and not dangerous_text_request:
        safe_awareness = True
        score_delta -= 15
        evidence.append(Evidence(
            id="behavioral_safe_guardrail",
            category="safe_context",
            severity="info",
            score_delta=-15,
            confidence=0.85,
            matched_text=guard_hits[0],
            explanation_ar=(
                "تبدو الرسالة توعوية أو خدمية ولا تطلب مشاركة بيانات حساسة."
            ),
            explanation_en=(
                "Message contains safety guardrail phrases — appears to be "
                "an awareness or informational message."
            ),
        ))

    # Rule F — safe service context (reduce score, suppressed when danger active)
    if svc_hits and not dangerous_text_request and not account_takeover and not payment_phishing:
        safe_service = True
        score_delta -= 10
        evidence.append(Evidence(
            id="behavioral_safe_service",
            category="safe_context",
            severity="info",
            score_delta=-10,
            confidence=0.80,
            matched_text=svc_hits[0],
            explanation_ar=(
                "تبدو الرسالة توعوية أو خدمية ولا تطلب مشاركة بيانات حساسة."
            ),
            explanation_en=(
                "Message matches safe service notification patterns."
            ),
        ))

    return {
        "account_state_hits":  acct_hits,
        "action_hits":         action_hits,
        "urgency_hits":        urgency_hits,
        "behavioral_family_hits": family_hits,
        "psychological_pressure_hits": psychological_hits,
        "safe_guardrail_hits": guard_hits,
        "safe_service_hits":   svc_hits,
        "behavioral_flags": {
            "account_takeover_flow":  account_takeover,
            "payment_phishing_flow":  payment_phishing,
            "psychological_pressure": any(psychological_hits.values()),
            "safe_awareness_context": safe_awareness,
            "safe_service_context":   safe_service,
        },
        "score_delta": score_delta,
        "evidence":    evidence,
    }
