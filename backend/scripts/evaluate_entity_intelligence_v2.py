"""
APG Phase 5.1 - Entity Intelligence v2 Evaluation
=================================================

Registry quality audit plus synthetic entity-intelligence regression cases.
This script is read-only evaluation tooling; it does not modify scoring,
matching, policy, sandbox, behavioral, or mobile code.

Usage:
  cd backend
  python scripts/evaluate_entity_intelligence_v2.py

Exit codes:
  0  entity cases PASS and registry gate has no blocking gaps
  1  one or more entity cases FAIL or blocking registry gaps are present
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.entity_registry import _norm, _strip_domain, get_registry  # noqa: E402
from app.services.risk_engine.entity_policy import _FORBIDDEN_TO_FLAG  # noqa: E402
from app.services.risk_engine.service import RiskEngineV1Service  # noqa: E402
from app.services.risk_engine.url_intelligence import (  # noqa: E402
    _KNOWN_BRANDS,
    registry_brand_candidates_count,
)


DATA_FILE = BACKEND_DIR / "app" / "data" / "entities" / "jo_entities.json"
_SVC = RiskEngineV1Service()

_VERDICT_RANK = {
    "allow": 0,
    "caution": 1,
    "warn": 2,
    "block": 3,
}

_COMMON_ALIAS_RISK = {
    "زين",
    "سند",
    "أية",
    "اية",
    "aya",
    "cab",
    "boj",
    "gam",
    "moh",
    "psd",
    "ssc",
    "moj",
    "cdd",
    "moi",
}

_GENERIC_SENDER_WORDS = {
    "support",
    "service",
    "customs",
    "security",
    "help",
    "info",
    "admin",
    "bank",
    "gov",
}

_AR_LETTERS_RE = re.compile(r"[\u0621-\u064A]")


@dataclass(frozen=True)
class EntityCase:
    case_id: int
    family: str
    expected: str
    text: str
    sender_name: str = ""
    sender: str = ""
    extra_urls: list[str] = field(default_factory=list)
    min_verdict: str | None = None
    max_verdict: str | None = None
    expected_claimed: str | None = None
    expected_sender: str | None = None
    expected_domain: str | None = None
    forbidden_claimed: set[str] = field(default_factory=set)
    forbidden_sender: set[str] = field(default_factory=set)
    forbidden_domain: set[str] = field(default_factory=set)
    required_evidence_any: set[str] = field(default_factory=set)
    forbidden_evidence: set[str] = field(default_factory=set)
    required_policy_trace_any: set[str] = field(default_factory=set)
    max_sender_trust: str | None = None
    note: str = ""


CASES: list[EntityCase] = [
    # A. Official alignment safe cases
    EntityCase(1, "official_alignment", "safe", "تنبيه: تم تحديث خدمات زين عبر الرابط الرسمي https://jo.zain.com/offers", sender_name="Zain", max_verdict="warn", expected_claimed="zain_jordan", expected_sender="zain_jordan", expected_domain="zain_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(2, "official_alignment", "low", "راجع تفاصيل حسابك من الموقع الرسمي https://arabbank.jo", max_verdict="warn", expected_claimed="arab_bank", expected_domain="arab_bank", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(3, "official_alignment", "safe", "إشعار خدمة من أورنج: تفاصيل الباقات على https://orange.jo", sender_name="Orange", max_verdict="warn", expected_claimed="orange_jordan", expected_sender="orange_jordan", expected_domain="orange_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(4, "official_alignment", "safe", "عرض رسمي على الباقات من زين بدون طلب بيانات https://jo.zain.com/offers", sender_name="Zain", max_verdict="warn", expected_claimed="zain_jordan", forbidden_evidence={"danger_password_request", "danger_otp_request"}),
    EntityCase(5, "official_alignment", "low", "تم استلام دفعة في حسابك لدى البنك العربي ولا يلزم أي إجراء https://arabbank.jo", sender_name="ArabBank", max_verdict="warn", expected_claimed="arab_bank"),
    EntityCase(6, "official_alignment", "safe", "توعية من سند: لا تشارك كلمة المرور أو رمز التحقق مع أي شخص https://sanad.gov.jo", sender_name="Sanad", max_verdict="warn", expected_claimed="sanad_jordan", forbidden_evidence={"danger_password_request", "danger_otp_request"}),
    EntityCase(7, "official_alignment", "low", "تم دفع الفاتورة بنجاح عبر إي فواتيركم https://efawateercom.jo", sender_name="eFAWATEERcom", max_verdict="warn", expected_claimed="efawateercom"),
    EntityCase(8, "official_alignment", "safe", "تذكير: شحنتك قيد التوصيل من أرامكس https://aramex.com", sender_name="Aramex", max_verdict="warn", expected_claimed="aramex"),
    EntityCase(9, "official_alignment", "safe", "إشعار أمني من البنك العربي: البنك لا يطلب كلمة المرور عبر الرسائل https://arabbank.jo", sender_name="ArabBank", max_verdict="warn", expected_claimed="arab_bank", forbidden_evidence={"danger_password_request"}),
    EntityCase(10, "official_alignment", "safe", "إعلان رسمي من أمانة عمان عن خدمات إلكترونية https://ammancity.gov.jo", sender_name="GAM", max_verdict="warn", expected_claimed="greater_amman_municipality"),

    # B. Mismatch / impersonation cases
    EntityCase(11, "mismatch_impersonation", "suspicious", "البنك العربي يطلب مراجعة الحساب من الرابط https://arab-bank-login.test", min_verdict="caution", expected_claimed="arab_bank", required_evidence_any={"url_brand_phishing_combo", "url_claimed_brand_domain_mismatch", "url_brand_impersonation", "url_brand_suspicious_tld"}),
    EntityCase(12, "mismatch_impersonation", "suspicious", "زين: سجل دخولك لتأكيد الحساب https://zain-login-review.test", min_verdict="caution", expected_claimed="zain_jordan", required_evidence_any={"url_claimed_brand_domain_mismatch", "url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(13, "mismatch_impersonation", "suspicious", "الجمارك الأردنية تطلب دفع رسوم الشحنة https://customs-fee.test", min_verdict="caution", expected_claimed="jordan_customs"),
    EntityCase(14, "mismatch_impersonation", "suspicious", "البريد الأردني: ادفع رسوم إعادة التوصيل https://jordanpost-fee.test", min_verdict="caution", expected_claimed="jordan_post"),
    EntityCase(15, "mismatch_impersonation", "dangerous", "زين كاش: أعد تفعيل المحفظة من الرابط https://zaincash-reactivate.test", min_verdict="warn", expected_claimed="zain_cash"),
    EntityCase(16, "mismatch_impersonation", "suspicious", "Sender is ArabBank but link points to Orange official site https://orange.jo", sender_name="ArabBank", min_verdict="caution", expected_sender="arab_bank", expected_domain="orange_jordan", required_evidence_any={"entity_conflict_sender_domain"}),
    EntityCase(17, "mismatch_impersonation", "suspicious", "Zain message with Arab Bank official domain https://arabbank.jo", sender_name="Zain", min_verdict="caution", expected_sender="zain_jordan", expected_domain="arab_bank", required_evidence_any={"entity_conflict_sender_domain"}),
    EntityCase(18, "mismatch_impersonation", "caution", "بنك الاتحاد يطلب مراجعة الحساب https://etihad-bank-review.test", min_verdict="caution", expected_claimed="bank_al_etihad"),
    EntityCase(19, "mismatch_impersonation", "suspicious", "Orange: update your login from https://orange-login.test", min_verdict="caution", expected_claimed="orange_jordan"),
    EntityCase(20, "mismatch_impersonation", "suspicious", "DHL: ادفع رسوم التوصيل من الرابط https://dhl-fee.test", min_verdict="caution", expected_claimed="dhl"),

    # C. Forbidden request cases
    EntityCase(21, "forbidden_request", "dangerous", "البنك العربي يطلب إدخال كلمة المرور لتحديث الحساب", min_verdict="block", expected_claimed="arab_bank", required_evidence_any={"entity_policy_forbidden_arab_bank", "danger_password_request"}),
    EntityCase(22, "forbidden_request", "dangerous", "Arab Bank: send OTP code to confirm your account", min_verdict="block", expected_claimed="arab_bank", required_evidence_any={"entity_policy_forbidden_arab_bank", "danger_otp_request"}),
    EntityCase(23, "forbidden_request", "dangerous", "زين تطلب رمز التحقق لإعادة تفعيل الخط", min_verdict="warn", expected_claimed="zain_jordan"),
    EntityCase(24, "forbidden_request", "dangerous", "زين كاش: أدخل رقم PIN وكلمة مرور المحفظة", min_verdict="block", expected_claimed="zain_cash", required_evidence_any={"entity_policy_forbidden_zain_cash", "danger_password_request"}),
    EntityCase(25, "forbidden_request", "dangerous", "سند يطلب رقم البطاقة و CVV لتفعيل الحساب", min_verdict="caution", expected_claimed="sanad_jordan"),
    EntityCase(26, "forbidden_request", "dangerous", "البريد الأردني يطلب CVV لدفع رسوم التوصيل", min_verdict="warn", expected_claimed="jordan_post"),
    EntityCase(27, "forbidden_request", "dangerous", "بنك القاهرة عمان يطلب إدخال كلمة المرور من الرسالة", min_verdict="block", expected_claimed="cairo_amman_bank", required_evidence_any={"entity_policy_forbidden_cairo_amman_bank", "danger_password_request"}),
    EntityCase(28, "forbidden_request", "dangerous", "Orange Jordan يطلب إدخال CVV لتحديث الباقة", min_verdict="block", expected_claimed="orange_jordan", required_evidence_any={"entity_policy_forbidden_orange_jordan", "danger_card_request"}),
    EntityCase(29, "forbidden_request", "dangerous", "PayPal يطلب إدخال كلمة المرور ورمز التحقق من الرابط https://paypal-secure.test", min_verdict="block", expected_claimed="paypal", required_evidence_any={"danger_password_request", "danger_otp_request"}),
    EntityCase(30, "forbidden_request", "dangerous", "الجمارك الأردنية تطلب رقم البطاقة لدفع رسوم جمركية", min_verdict="warn", expected_claimed="jordan_customs"),

    # D. Safe awareness quoting dangerous terms
    EntityCase(31, "safe_awareness", "safe", "تنبيه من زين: لا تشارك رمز التحقق مع أي شخص", sender_name="Zain", max_verdict="warn", expected_claimed="zain_jordan", forbidden_evidence={"danger_otp_request", "entity_policy_forbidden_zain_jordan"}),
    EntityCase(32, "safe_awareness", "safe", "البنك العربي لا يطلب كلمة المرور أو رمز التحقق عبر الرسائل", sender_name="ArabBank", max_verdict="warn", expected_claimed="arab_bank", forbidden_evidence={"danger_password_request", "danger_otp_request", "entity_policy_forbidden_arab_bank"}),
    EntityCase(33, "safe_awareness", "safe", "أورنج تحذر من رسائل الجوائز المزيفة ولا تطلب كود التحقق", sender_name="Orange", max_verdict="warn", expected_claimed="orange_jordan", forbidden_evidence={"danger_otp_request"}),
    EntityCase(34, "safe_awareness", "safe", "الجمارك الأردنية تنبه: احذر من روابط تطلب دفع رسوم مجهولة", sender_name="Jordan Customs", max_verdict="warn", expected_claimed="jordan_customs", forbidden_evidence={"behavioral_payment_phishing"}),
    EntityCase(35, "safe_awareness", "safe", "سند: لا ترسل كلمة المرور لأي شخص واستخدم التطبيق الرسمي فقط", sender_name="Sanad", max_verdict="warn", expected_claimed="sanad_jordan", forbidden_evidence={"danger_password_request", "entity_policy_forbidden_sanad_jordan"}),
    EntityCase(36, "safe_awareness", "safe", "البريد الأردني لا يطلب CVV عبر الرسائل", sender_name="JordanPost", max_verdict="warn", expected_claimed="jordan_post", forbidden_evidence={"danger_card_request", "entity_policy_forbidden_jordan_post"}),
    EntityCase(37, "safe_awareness", "safe", "وزارة الصحة: لا تدخل بيانات البطاقة في روابط مجهولة", sender_name="MOH", max_verdict="warn", expected_claimed="ministry_of_health_jo", forbidden_evidence={"danger_card_request"}),
    EntityCase(38, "safe_awareness", "safe", "الأمن العام يحذر من رسائل تطلب رمز التحقق", sender_name="PSD", max_verdict="warn", expected_claimed="public_security_directorate_jo", forbidden_evidence={"danger_otp_request"}),
    EntityCase(39, "safe_awareness", "safe", "Bank of Jordan reminds you: do not enter your password in links", sender_name="BOJ", max_verdict="warn", expected_claimed="bank_of_jordan", forbidden_evidence={"danger_password_request", "entity_policy_forbidden_bank_of_jordan"}),
    EntityCase(40, "safe_awareness", "safe", "Cairo Amman Bank: never share OTP with callers", sender_name="CAB", max_verdict="warn", expected_claimed="cairo_amman_bank", forbidden_evidence={"danger_otp_request"}),

    # E. Arabic alias substring regressions
    EntityCase(41, "alias_substring", "safe", "عرض حصري لعملائنا المميزين بدون تسجيل دخول", max_verdict="caution", forbidden_claimed={"zain_jordan"}, forbidden_evidence={"entity_policy_forbidden_zain_jordan"}),
    EntityCase(42, "alias_substring", "safe", "هذا سند قبض داخلي ولا توجد روابط أو طلب بيانات", max_verdict="caution", forbidden_claimed={"sanad_jordan"}),
    EntityCase(43, "alias_substring", "safe", "هل لديك أية ملاحظات على الخدمة؟", max_verdict="caution", forbidden_claimed={"aya_epayment_services"}),
    EntityCase(44, "alias_substring", "safe", "The cabinet update was published today", max_verdict="caution", forbidden_claimed={"cairo_amman_bank"}),
    EntityCase(45, "alias_substring", "safe", "The object was stored safely in the lab", max_verdict="caution", forbidden_claimed={"bank_of_jordan"}),
    EntityCase(46, "alias_substring", "safe", "A game night invitation for the team", max_verdict="caution", forbidden_claimed={"greater_amman_municipality"}),
    EntityCase(47, "alias_substring", "safe", "Mohammad sent the meeting notes", max_verdict="caution", forbidden_claimed={"ministry_of_health_jo"}),
    EntityCase(48, "alias_substring", "safe", "Please read the psd design file tomorrow", max_verdict="caution", forbidden_claimed={"public_security_directorate_jo"}),
    EntityCase(49, "alias_substring", "safe", "سندويشة جاهزة للاستلام من المطعم", max_verdict="caution", forbidden_claimed={"sanad_jordan"}),
    EntityCase(50, "alias_substring", "safe", "هذه اية من النص التعليمي ولا يوجد طلب بيانات", max_verdict="caution", forbidden_claimed={"aya_epayment_services"}),

    # F. Sender spoofing cases
    EntityCase(51, "sender_spoofing", "suspicious", "ادخل كلمة المرور لتحديث الحساب https://arab-bank-secure.test", sender_name="ArabBankSecure", min_verdict="warn", forbidden_sender={"arab_bank"}, max_sender_trust="unknown"),
    EntityCase(52, "sender_spoofing", "caution", "راجع حسابك من الرابط https://zain-support.test", sender_name="ZAIN-FAKE", min_verdict="caution", forbidden_sender={"zain_jordan"}, max_sender_trust="unknown"),
    EntityCase(53, "sender_spoofing", "suspicious", "البنك العربي يطلب تحديث الحساب https://arab-bank-review.test", sender_name="UNKNOWN", min_verdict="caution", expected_claimed="arab_bank", max_sender_trust="unknown"),
    EntityCase(54, "sender_spoofing", "suspicious", "Bank al Etihad login review https://bankaletihad-login.test", sender_name="BankAlEtihad-Verify", min_verdict="caution", expected_claimed="bank_al_etihad", forbidden_sender={"bank_al_etihad"}, max_sender_trust="unknown"),
    EntityCase(55, "sender_spoofing", "caution", "أدخل رمز التحقق لإتمام الطلب", sender_name="ZainCash-OTP", min_verdict="caution", forbidden_sender={"zain_cash"}, max_sender_trust="unknown"),
    EntityCase(56, "sender_spoofing", "suspicious", "Orange verification link https://orange-login.test", sender_name="ORANGE-ALERT", min_verdict="caution", expected_claimed="orange_jordan", forbidden_sender={"orange_jordan"}, max_sender_trust="unknown"),
    EntityCase(57, "sender_spoofing", "caution", "Customs fee request https://customs-payment.test", sender_name="Jordan Customs Help", min_verdict="caution", expected_claimed="jordan_customs", forbidden_sender={"jordan_customs"}, max_sender_trust="unknown"),
    EntityCase(58, "sender_spoofing", "suspicious", "Sanad password reset https://sanad-login.test", sender_name="SANAD-SUPPORT", min_verdict="caution", expected_claimed="sanad_jordan", forbidden_sender={"sanad_jordan"}, max_sender_trust="unknown"),
    EntityCase(59, "sender_spoofing", "caution", "PSD verification request https://psd-alert.test", sender_name="PSD-Verify", expected_claimed="public_security_directorate_jo", forbidden_sender={"public_security_directorate_jo"}, max_sender_trust="unknown"),
    EntityCase(60, "sender_spoofing", "suspicious", "MOH payment update https://moh-fee.test", sender_name="MOH-Notice", expected_claimed="ministry_of_health_jo", forbidden_sender={"ministry_of_health_jo"}, max_sender_trust="unknown"),

    # G. Registry vs URL brand consistency / entity gaps, not failed only because URL known brands are smaller.
    EntityCase(61, "registry_url_consistency", "caution", "Bank of Jordan account update https://bankofjordan-login.test", min_verdict="caution", expected_claimed="bank_of_jordan"),
    EntityCase(62, "registry_url_consistency", "caution", "Capital Bank يطلب مراجعة الحساب https://capitalbank-review.test", min_verdict="caution", expected_claimed="capital_bank"),
    EntityCase(63, "registry_url_consistency", "caution", "Umniah: update your account https://umniah-login.test", min_verdict="caution", expected_claimed="umniah"),
    EntityCase(64, "registry_url_consistency", "caution", "Miyahuna bill payment notice https://miyahuna-fee.test", expected_claimed="miyahuna"),
    EntityCase(65, "registry_url_consistency", "caution", "SmartBuy order issue https://smartbuy-login.test", min_verdict="caution", expected_claimed="smartbuy_jordan"),
    EntityCase(66, "registry_url_consistency", "caution", "CliQ transfer confirmation https://cliq-confirm.test", min_verdict="caution", expected_claimed="cliq_jordan"),
    EntityCase(67, "registry_url_consistency", "caution", "Dinarak wallet update https://dinarak-update.test", min_verdict="caution", expected_claimed="dinarak"),
    EntityCase(68, "registry_url_consistency", "caution", "Noon account review https://noon-login.test", min_verdict="caution", expected_claimed="noon"),
    EntityCase(69, "registry_url_consistency", "safe", "Google security advice: do not share your password https://google.com", sender_name="Google", max_verdict="warn", expected_claimed="google"),
    EntityCase(70, "registry_url_consistency", "safe", "Amazon order shipped successfully https://amazon.com", sender_name="Amazon", max_verdict="warn", expected_claimed="amazon"),

    # Additional safe / low-risk registry coverage
    EntityCase(71, "official_alignment", "safe", "تم تجديد اشتراكك في شاهد بنجاح https://shahid.mbc.net", sender_name="Shahid", max_verdict="warn", expected_claimed="shahid"),
    EntityCase(72, "official_alignment", "safe", "تمت رحلة كريم بنجاح ولا يلزم إجراء https://careem.com", sender_name="Careem", max_verdict="warn", expected_claimed="careem"),
    EntityCase(73, "official_alignment", "safe", "إشعار فاتورة مياهونا بدون طلب بيانات https://miyahuna.jo", sender_name="Miyahuna", max_verdict="warn", expected_claimed="miyahuna"),
    EntityCase(74, "official_alignment", "safe", "تم استلام طلبك من طلبات https://talabat.com", sender_name="Talabat", max_verdict="warn", expected_claimed="talabat_jordan"),
    EntityCase(75, "safe_awareness", "safe", "Meta تحذر من رسائل تطلب رمز الدخول ولا تطلبه عبر الدردشة", sender_name="Meta", max_verdict="warn", expected_claimed="meta", forbidden_evidence={"danger_otp_request"}),
    EntityCase(76, "safe_awareness", "safe", "WhatsApp: لا تشارك كود واتساب مع أي شخص", sender_name="WhatsApp", max_verdict="warn", expected_claimed="whatsapp", forbidden_evidence={"danger_otp_request"}),
    EntityCase(77, "forbidden_request", "dangerous", "Facebook يطلب رمز الدخول لاستعادة الحساب", min_verdict="warn", expected_claimed="facebook", required_evidence_any={"entity_policy_forbidden_facebook", "danger_otp_request"}),
    EntityCase(78, "forbidden_request", "dangerous", "Instagram يطلب كلمة المرور لتوثيق الحساب", min_verdict="block", expected_claimed="instagram", required_evidence_any={"entity_policy_forbidden_instagram", "danger_password_request"}),
    EntityCase(79, "mismatch_impersonation", "suspicious", "Aramex: pay delivery fee https://aramex-fee.test", min_verdict="caution", expected_claimed="aramex", required_evidence_any={"url_claimed_brand_domain_mismatch", "url_brand_impersonation", "behavioral_delivery_customs_fee", "behavioral_payment_phishing"}),
    EntityCase(80, "mismatch_impersonation", "suspicious", "PayPal account limited, login now https://paypal-login.test", min_verdict="caution", expected_claimed="paypal", required_evidence_any={"url_claimed_brand_domain_mismatch", "url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(81, "sender_precision", "safe", "تنبيه رسمي من زين بدون طلب بيانات", sender_name="Zain", max_verdict="warn", expected_claimed="zain_jordan", expected_sender="zain_jordan"),
    EntityCase(82, "sender_precision", "safe", "إشعار من البنك العربي لا يلزم أي إجراء", sender_name="ArabBank", max_verdict="warn", expected_claimed="arab_bank", expected_sender="arab_bank"),
    EntityCase(83, "sender_precision", "safe", "Cairo Amman Bank notice, no action required", sender_name="CAB", max_verdict="warn", expected_claimed="cairo_amman_bank", expected_sender="cairo_amman_bank"),
    EntityCase(84, "sender_precision", "safe", "وزارة الصحة تنبيه توعوي بدون روابط", sender_name="MOH", max_verdict="warn", expected_claimed="ministry_of_health_jo", expected_sender="ministry_of_health_jo"),

    # H. Duplicate official domain policy
    EntityCase(85, "duplicate_domain_policy", "safe", "Zain Cash official wallet notice https://jo.zain.com/offers", max_verdict="warn", expected_claimed="zain_cash", expected_domain="zain_cash", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"entity_conflict_sender_domain"}),
    EntityCase(86, "duplicate_domain_policy", "safe", "Zain Jordan official service notice https://jo.zain.com/offers", max_verdict="warn", expected_claimed="zain_jordan", expected_domain="zain_jordan", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"entity_conflict_sender_domain"}),
    EntityCase(87, "duplicate_domain_policy", "safe", "Orange Money official wallet notice https://orange.jo", max_verdict="warn", expected_claimed="orange_money_jordan", expected_domain="orange_money_jordan", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"entity_conflict_sender_domain"}),
    EntityCase(88, "duplicate_domain_policy", "safe", "Orange Jordan official service notice https://orange.jo", max_verdict="warn", expected_claimed="orange_jordan", expected_domain="orange_jordan", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"entity_conflict_sender_domain"}),
    EntityCase(89, "duplicate_domain_policy", "safe", "Civil Defense official notice https://psd.gov.jo", max_verdict="warn", expected_claimed="civil_defense_directorate_jo", expected_domain="civil_defense_directorate_jo", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"entity_conflict_sender_domain"}),
    EntityCase(90, "duplicate_domain_policy", "safe", "Public Security Directorate official notice https://psd.gov.jo", max_verdict="warn", expected_claimed="public_security_directorate_jo", expected_domain="public_security_directorate_jo", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"entity_conflict_sender_domain"}),
    EntityCase(91, "duplicate_domain_policy", "safe", "Jordan Post MyJoBox service notice https://myjobox.jo", max_verdict="warn", expected_claimed="jordan_post", expected_domain="jordan_post", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"entity_conflict_sender_domain"}),
    EntityCase(92, "duplicate_domain_policy", "suspicious", "Arab Bank notice from Zain domain https://jo.zain.com/offers", sender_name="ArabBank", min_verdict="caution", expected_claimed="arab_bank", expected_sender="arab_bank", required_evidence_any={"entity_conflict_sender_domain"}),
    EntityCase(93, "duplicate_domain_policy", "suspicious", "Zain Cash fake reactivation https://zaincash-reactivate.test", min_verdict="caution", expected_claimed="zain_cash", required_evidence_any={"url_brand_impersonation", "url_claimed_brand_domain_mismatch", "url_brand_phishing_combo"}),
    EntityCase(94, "duplicate_domain_policy", "safe", "Zain official service notice https://jo.zain.com/offers", sender_name="ZAIN-FAKE", max_verdict="warn", expected_claimed="zain_jordan", expected_domain="zain_jordan", forbidden_sender={"zain_jordan"}, max_sender_trust="unknown"),

    # I. Registry-backed URL brand bridge
    EntityCase(95, "registry_url_brand_bridge", "suspicious", "Bank of Jordan login https://bankofjordan-login.test", min_verdict="caution", expected_claimed="bank_of_jordan", required_evidence_any={"url_brand_phishing_combo"}),
    EntityCase(96, "registry_url_brand_bridge", "safe", "Capital Bank official notice https://capitalbank.jo", max_verdict="warn", expected_claimed="capital_bank", expected_domain="capital_bank", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"url_brand_impersonation", "url_claimed_brand_domain_mismatch", "url_brand_phishing_combo"}),
    EntityCase(97, "registry_url_brand_bridge", "suspicious", "Capital Bank update https://capitalbank-login.test", min_verdict="caution", expected_claimed="capital_bank", required_evidence_any={"url_brand_phishing_combo"}),
    EntityCase(98, "registry_url_brand_bridge", "safe", "Dinarak wallet notice https://dinarak.com", max_verdict="warn", expected_claimed="dinarak", expected_domain="dinarak", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(99, "registry_url_brand_bridge", "suspicious", "Dinarak wallet update https://dinarak-update.test", min_verdict="caution", expected_claimed="dinarak", required_evidence_any={"url_brand_phishing_combo"}),
    EntityCase(100, "registry_url_brand_bridge", "suspicious", "Jordan Customs fee https://customs-fee.test", min_verdict="caution", expected_claimed="jordan_customs", required_evidence_any={"url_brand_impersonation", "url_claimed_brand_domain_mismatch", "url_brand_phishing_combo"}),
    EntityCase(101, "registry_url_brand_bridge", "safe", "Jordan Customs official notice https://customs.gov.jo", max_verdict="warn", expected_claimed="jordan_customs", expected_domain="jordan_customs", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(102, "registry_url_brand_bridge", "suspicious", "Jordan Post fee https://jordanpost-fee.test", min_verdict="caution", expected_claimed="jordan_post", required_evidence_any={"url_brand_impersonation", "url_claimed_brand_domain_mismatch", "url_brand_phishing_combo"}),
    EntityCase(103, "registry_url_brand_bridge", "suspicious", "SmartBuy payment https://smartbuy-payment.test", min_verdict="caution", expected_claimed="smartbuy_jordan", required_evidence_any={"url_brand_phishing_combo"}),
    EntityCase(104, "registry_url_brand_bridge", "safe", "SmartBuy official promo https://smartbuy-me.com", max_verdict="warn", expected_claimed="smartbuy_jordan", expected_domain="smartbuy_jordan", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(105, "registry_url_brand_bridge", "suspicious", "Sanad login https://sanad-login.test", min_verdict="caution", expected_claimed="sanad_jordan", required_evidence_any={"url_brand_phishing_combo"}),
    EntityCase(106, "registry_url_brand_bridge", "safe", "Sanad official notice https://sanad.gov.jo", max_verdict="warn", expected_claimed="sanad_jordan", expected_domain="sanad_jordan", required_evidence_any={"entity_official_domain_alignment"}, forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(107, "registry_url_brand_bridge", "suspicious", "Miyahuna bill https://miyahuna-fee.test", min_verdict="caution", expected_claimed="miyahuna", required_evidence_any={"url_brand_impersonation", "url_claimed_brand_domain_mismatch", "url_brand_phishing_combo"}),
    EntityCase(108, "registry_url_brand_bridge", "safe", "The object was stored safely https://object-login.test", max_verdict="caution", forbidden_claimed={"bank_of_jordan"}, forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(109, "registry_url_brand_bridge", "safe", "Project game test page https://projectgametest-login.test", max_verdict="caution", forbidden_claimed={"greater_amman_municipality"}, forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(110, "registry_url_brand_bridge", "safe", "عرض خاص لعملائنا المميزين https://promo-login.test", max_verdict="caution", forbidden_claimed={"zain_jordan"}, forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(111, "registry_url_brand_bridge", "safe", "Unknown Brand update https://unknown-login.test", max_verdict="caution", forbidden_evidence={"url_brand_impersonation", "url_brand_phishing_combo"}),
    EntityCase(112, "registry_url_brand_bridge", "safe", "MyJoBox service notice https://jordanpost.com.jo", max_verdict="warn", expected_claimed="jordan_post", expected_domain="jordan_post", forbidden_evidence={"entity_conflict_sender_domain", "url_brand_impersonation"}),
    EntityCase(113, "registry_url_brand_bridge", "suspicious", "Telegram login https://telegram-login.test", min_verdict="caution", expected_claimed="telegram", required_evidence_any={"url_brand_phishing_combo"}),
    EntityCase(114, "registry_url_brand_bridge", "suspicious", "TikTok verification https://tiktok-verify.test", min_verdict="caution", expected_claimed="tiktok", required_evidence_any={"url_brand_phishing_combo"}),

    # ── Healthcare batch 1 ─────────────────────────────────────────────────────
    # J. Royal Medical Services
    EntityCase(115, "official_alignment", "safe", "إشعار من الخدمات الطبية الملكية: موعدك موثق على الرابط الرسمي https://rms.gov.jo", sender_name="RMS", max_verdict="warn", expected_claimed="royal_medical_services_jo", expected_domain="royal_medical_services_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(116, "mismatch_impersonation", "suspicious", "الخدمات الطبية الملكية: راجع ملفك الطبي من الرابط https://rms-patient.test", min_verdict="caution", expected_claimed="royal_medical_services_jo"),
    EntityCase(117, "forbidden_request", "dangerous", "الخدمات الطبية الملكية تطلب كلمة المرور لمراجعة ملفك الطبي", min_verdict="block", expected_claimed="royal_medical_services_jo", required_evidence_any={"entity_policy_forbidden_royal_medical_services_jo", "danger_password_request"}),
    EntityCase(118, "safe_awareness", "safe", "الخدمات الطبية الملكية: لا تشارك كلمة المرور أو رمز التحقق مع أي شخص", sender_name="RMS", max_verdict="warn", expected_claimed="royal_medical_services_jo", forbidden_evidence={"entity_policy_forbidden_royal_medical_services_jo"}),
    EntityCase(119, "alias_substring", "safe", "تم توزيع الخدمات الملكية في المناطق العسكرية بشكل منظم", max_verdict="caution", forbidden_claimed={"royal_medical_services_jo"}),
    EntityCase(120, "sender_spoofing", "suspicious", "راجع نتائجك الطبية من الرابط https://rms-results.test", sender_name="RMS-Support", forbidden_sender={"royal_medical_services_jo"}, max_sender_trust="unknown"),

    # K. King Hussein Cancer Center
    EntityCase(121, "official_alignment", "safe", "مركز الحسين للسرطان: موعدك القادم مؤكد على الرابط الرسمي https://khcc.jo", sender_name="KHCC", max_verdict="warn", expected_claimed="king_hussein_cancer_center", expected_domain="king_hussein_cancer_center", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(122, "mismatch_impersonation", "suspicious", "مركز الحسين للسرطان: راجع نتائجك من الرابط https://khcc-portal.test", min_verdict="caution", expected_claimed="king_hussein_cancer_center"),
    EntityCase(123, "forbidden_request", "dangerous", "مركز الحسين للسرطان يطلب كلمة المرور لمراجعة نتائجك الطبية", min_verdict="block", expected_claimed="king_hussein_cancer_center", required_evidence_any={"entity_policy_forbidden_king_hussein_cancer_center", "danger_password_request"}),
    EntityCase(124, "safe_awareness", "safe", "مركز الحسين للسرطان: لا تدخل بيانات بطاقتك في أي رابط غير الموقع الرسمي", sender_name="KHCC", max_verdict="warn", expected_claimed="king_hussein_cancer_center", forbidden_evidence={"entity_policy_forbidden_king_hussein_cancer_center"}),
    EntityCase(125, "alias_substring", "safe", "درس الطلاب موضوع المركز الحسيني في التاريخ الأردني", max_verdict="caution", forbidden_claimed={"king_hussein_cancer_center"}),
    EntityCase(126, "sender_spoofing", "suspicious", "نتائجك التحليلية جاهزة للاستلام https://khcc-results.test", sender_name="KHCC-Alert", forbidden_sender={"king_hussein_cancer_center"}, max_sender_trust="unknown"),

    # L. Jordan University Hospital
    EntityCase(127, "official_alignment", "safe", "مستشفى الجامعة الأردنية: موعدك مؤكد على الرابط الرسمي https://juh.jo", sender_name="JUH", max_verdict="warn", expected_claimed="jordan_university_hospital", expected_domain="jordan_university_hospital", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(128, "mismatch_impersonation", "suspicious", "مستشفى الجامعة الأردنية: ادفع رسوم الفحص من الرابط https://juh-payment.test", min_verdict="caution", expected_claimed="jordan_university_hospital"),
    EntityCase(129, "forbidden_request", "dangerous", "مستشفى الجامعة الأردنية يطلب رمز التحقق لتسجيل الدخول وتأكيد البيانات", min_verdict="block", expected_claimed="jordan_university_hospital", required_evidence_any={"entity_policy_forbidden_jordan_university_hospital", "danger_otp_request"}),
    EntityCase(130, "safe_awareness", "safe", "مستشفى الجامعة الأردنية: لا تشارك كود التحقق مع أي جهة", sender_name="JUH", max_verdict="warn", expected_claimed="jordan_university_hospital", forbidden_evidence={"entity_policy_forbidden_jordan_university_hospital"}),
    EntityCase(131, "alias_substring", "safe", "وظائف شاغرة في إدارة المستشفيات الجامعية العربية المتخصصة", max_verdict="caution", forbidden_claimed={"jordan_university_hospital"}),
    EntityCase(132, "sender_spoofing", "suspicious", "استكمل تسجيلك الطبي من الرابط https://juh-login.test", sender_name="JUH-Support", forbidden_sender={"jordan_university_hospital"}, max_sender_trust="unknown"),

    # M. Specialty Hospital
    EntityCase(133, "official_alignment", "safe", "مستشفى التخصصي: تأكيد موعدك على الرابط الرسمي https://specialty-hospital.com", sender_name="Specialty Hospital", max_verdict="warn", expected_claimed="specialty_hospital_jo", expected_domain="specialty_hospital_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(134, "mismatch_impersonation", "suspicious", "مستشفى التخصصي: تحديث معلوماتك من الرابط https://specialty-hosp.test", min_verdict="caution", expected_claimed="specialty_hospital_jo"),
    EntityCase(135, "forbidden_request", "dangerous", "مستشفى التخصصي يطلب كلمة المرور لتأكيد هويتك ومراجعة ملفك الطبي", min_verdict="block", expected_claimed="specialty_hospital_jo", required_evidence_any={"entity_policy_forbidden_specialty_hospital_jo", "danger_password_request"}),
    EntityCase(136, "safe_awareness", "safe", "مستشفى التخصصي: احذر من رسائل تطلب بيانات البطاقة البنكية", sender_name="Specialty Hospital", max_verdict="warn", expected_claimed="specialty_hospital_jo", forbidden_evidence={"entity_policy_forbidden_specialty_hospital_jo"}),
    EntityCase(137, "alias_substring", "safe", "نقدم خدمات تخصصية متميزة في التدريب والتطوير المهني", max_verdict="caution", forbidden_claimed={"specialty_hospital_jo"}),
    EntityCase(138, "sender_spoofing", "suspicious", "موعدك القادم في المستشفى يحتاج تأكيداً https://specialty-hosp-login.test", sender_name="Specialty-Alert", forbidden_sender={"specialty_hospital_jo"}, max_sender_trust="unknown"),

    # N. Istishari Hospital
    EntityCase(139, "official_alignment", "safe", "مستشفى الاستشاري: موعدك مؤكد على الرابط الرسمي https://istishari.com", sender_name="Istishari Hospital", max_verdict="warn", expected_claimed="istishari_hospital_jo", expected_domain="istishari_hospital_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(140, "mismatch_impersonation", "suspicious", "مستشفى الاستشاري: أدخل بياناتك من الرابط https://istishari-portal.test", min_verdict="caution", expected_claimed="istishari_hospital_jo"),
    EntityCase(141, "forbidden_request", "dangerous", "مستشفى الاستشاري يطلب كلمة المرور لإتمام حجزك الطبي الإلكتروني", min_verdict="block", expected_claimed="istishari_hospital_jo", required_evidence_any={"entity_policy_forbidden_istishari_hospital_jo", "danger_password_request"}),
    EntityCase(142, "safe_awareness", "safe", "مستشفى الاستشاري: لا تشارك بيانات دخولك مع أي طرف ثالث", sender_name="Istishari Hospital", max_verdict="warn", expected_claimed="istishari_hospital_jo", forbidden_evidence={"entity_policy_forbidden_istishari_hospital_jo"}),
    EntityCase(143, "alias_substring", "safe", "قدم العميل طلباً استشارياً لمناقشة المشروع المقترح للتطوير", max_verdict="caution", forbidden_claimed={"istishari_hospital_jo"}),
    EntityCase(144, "sender_spoofing", "suspicious", "تأكيد موعدك الطبي من الرابط https://istishari-booking.test", sender_name="Istishari-Support", forbidden_sender={"istishari_hospital_jo"}, max_sender_trust="unknown"),

    # O. Abdali Hospital
    EntityCase(145, "official_alignment", "safe", "مستشفى عبدالي: تأكيد حجزك على الرابط الرسمي https://abdali-hospital.com", sender_name="Abdali Hospital", max_verdict="warn", expected_claimed="abdali_hospital_jo", expected_domain="abdali_hospital_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(146, "mismatch_impersonation", "suspicious", "مستشفى عبدالي: حدّث وراجع بياناتك الطبية من الرابط https://abdali-hospital-login.test", min_verdict="caution", expected_claimed="abdali_hospital_jo"),
    EntityCase(147, "forbidden_request", "dangerous", "مستشفى عبدالي يطلب رمز التحقق OTP لتأكيد دفعة الخدمات الطبية", min_verdict="warn", expected_claimed="abdali_hospital_jo", required_evidence_any={"entity_policy_forbidden_abdali_hospital_jo", "danger_otp_request"}),
    EntityCase(148, "safe_awareness", "safe", "مستشفى عبدالي: لا تشارك رمز التحقق مع أي شخص", sender_name="Abdali Hospital", max_verdict="warn", expected_claimed="abdali_hospital_jo", forbidden_evidence={"entity_policy_forbidden_abdali_hospital_jo"}),
    EntityCase(149, "alias_substring", "safe", "مشروع عبدالي يضم محلات تجارية وفندقاً فاخراً وسط عمان", max_verdict="caution", forbidden_claimed={"abdali_hospital_jo"}),
    EntityCase(150, "sender_spoofing", "suspicious", "حجزك في المستشفى يحتاج تأكيداً من الرابط https://abdali-confirm.test", sender_name="Abdali-Med", forbidden_sender={"abdali_hospital_jo"}, max_sender_trust="unknown"),

    # P. Al Khalidi Hospital
    EntityCase(151, "official_alignment", "safe", "مستشفى الخالدي: موعدك محدد على الرابط الرسمي https://khalidihospital.com", sender_name="Al Khalidi Hospital", max_verdict="warn", expected_claimed="al_khalidi_hospital_jo", expected_domain="al_khalidi_hospital_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(152, "mismatch_impersonation", "suspicious", "مستشفى الخالدي: حدّث بياناتك من الرابط https://khalidi-hosp.test", min_verdict="caution", expected_claimed="al_khalidi_hospital_jo"),
    EntityCase(153, "forbidden_request", "dangerous", "مستشفى الخالدي يطلب CVV ورقم البطاقة لتسوية فاتورة الفحص الطبي", min_verdict="warn", expected_claimed="al_khalidi_hospital_jo", required_evidence_any={"entity_policy_forbidden_al_khalidi_hospital_jo", "danger_card_request"}),
    EntityCase(154, "safe_awareness", "safe", "مستشفى الخالدي: لا تدخل بيانات البطاقة في روابط مجهولة", sender_name="Al Khalidi Hospital", max_verdict="warn", expected_claimed="al_khalidi_hospital_jo", forbidden_evidence={"entity_policy_forbidden_al_khalidi_hospital_jo"}),
    EntityCase(155, "alias_substring", "safe", "طريق الخالدية الشمالي يربط أحياء عمان المختلفة بالمناطق الصناعية", max_verdict="caution", forbidden_claimed={"al_khalidi_hospital_jo"}),
    EntityCase(156, "sender_spoofing", "suspicious", "فاتورتك الطبية جاهزة للدفع من الرابط https://khalidi-billing.test", sender_name="Khalidi-Hospital-Pay", forbidden_sender={"al_khalidi_hospital_jo"}, max_sender_trust="unknown"),

    # Q. Arab Medical Center
    EntityCase(157, "official_alignment", "safe", "المركز الطبي العربي: موعدك مؤكد على الرابط الرسمي https://arabmedicalcenter.jo", sender_name="Arab Medical Center", max_verdict="warn", expected_claimed="arab_medical_center_jo", expected_domain="arab_medical_center_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(158, "mismatch_impersonation", "suspicious", "المركز الطبي العربي: راجع وحدّث بياناتك من الرابط https://arab-medical-center.test", min_verdict="caution", expected_claimed="arab_medical_center_jo"),
    EntityCase(159, "forbidden_request", "dangerous", "المركز الطبي العربي يطلب كلمة المرور لمراجعة ملفك الطبي عبر الرسالة", min_verdict="block", expected_claimed="arab_medical_center_jo", required_evidence_any={"entity_policy_forbidden_arab_medical_center_jo", "danger_password_request"}),
    EntityCase(160, "safe_awareness", "safe", "المركز الطبي العربي: لا تشارك بيانات دخولك مع أي جهة", sender_name="Arab Medical Center", max_verdict="warn", expected_claimed="arab_medical_center_jo", forbidden_evidence={"entity_policy_forbidden_arab_medical_center_jo"}),
    EntityCase(161, "alias_substring", "safe", "تم تطوير مركز التميز العربي الجديد في مجال البحث والتطوير", max_verdict="caution", forbidden_claimed={"arab_medical_center_jo"}),
    EntityCase(162, "sender_spoofing", "suspicious", "نتائج فحصك جاهزة من الرابط https://arab-medical-results.test", sender_name="AMC-Notify", forbidden_sender={"arab_medical_center_jo"}, max_sender_trust="unknown"),

    # R. Biolab Jordan
    EntityCase(163, "official_alignment", "safe", "بايولاب: نتائج تحاليلك جاهزة على الرابط الرسمي https://biolab.com.jo", sender_name="Biolab", max_verdict="warn", expected_claimed="biolab_jordan", expected_domain="biolab_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(164, "mismatch_impersonation", "suspicious", "بايولاب: راجع نتائجك من الرابط https://biolab-results.test", min_verdict="caution", expected_claimed="biolab_jordan"),
    EntityCase(165, "forbidden_request", "dangerous", "بايولاب تطلب رمز التحقق لعرض نتائجك التحليلية وتأكيد الهوية", min_verdict="warn", expected_claimed="biolab_jordan", required_evidence_any={"entity_policy_forbidden_biolab_jordan", "danger_otp_request"}),
    EntityCase(166, "safe_awareness", "safe", "بايولاب: لا يطلب منك إدخال كلمة المرور أو بيانات الحساب عبر الرسائل", sender_name="Biolab", max_verdict="warn", expected_claimed="biolab_jordan", forbidden_evidence={"entity_policy_forbidden_biolab_jordan"}),
    EntityCase(167, "alias_substring", "safe", "تم توظيف موظفين جدد في المختبرات البيولوجية والعلمية الوطنية", max_verdict="caution", forbidden_claimed={"biolab_jordan"}),
    EntityCase(168, "sender_spoofing", "suspicious", "نتائجك جاهزة للاستلام من الرابط https://biolab-jo.test", sender_name="Biolab-Alert", min_verdict="caution", expected_claimed="biolab_jordan", forbidden_sender={"biolab_jordan"}, max_sender_trust="unknown"),

    # S. MedLabs Jordan
    EntityCase(169, "official_alignment", "safe", "ميدلابس: تحاليلك جاهزة على الرابط الرسمي https://medlabs.com", sender_name="MedLabs", max_verdict="warn", expected_claimed="medlabs_jordan", expected_domain="medlabs_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(170, "mismatch_impersonation", "suspicious", "ميدلابس: حمّل نتائجك من الرابط https://medlabs-portal.test", min_verdict="caution", expected_claimed="medlabs_jordan"),
    EntityCase(171, "forbidden_request", "dangerous", "ميدلابس تطلب كلمة المرور لعرض نتائجك التحليلية وتأكيد بيانات حسابك", min_verdict="block", expected_claimed="medlabs_jordan", required_evidence_any={"entity_policy_forbidden_medlabs_jordan", "danger_password_request"}),
    EntityCase(172, "safe_awareness", "safe", "ميدلابس: لا تدخل بيانات البطاقة في أي رابط غير الموقع الرسمي", sender_name="MedLabs", max_verdict="warn", expected_claimed="medlabs_jordan", forbidden_evidence={"entity_policy_forbidden_medlabs_jordan"}),
    EntityCase(173, "alias_substring", "safe", "يستخدم الأطباء في العيادات المختبرات الطبية الحديثة للتشخيص", max_verdict="caution", forbidden_claimed={"medlabs_jordan"}),
    EntityCase(174, "sender_spoofing", "suspicious", "نتائج تحاليلك متاحة الآن من الرابط https://medlabs-jo.test", sender_name="MedLabs-Alert", min_verdict="caution", expected_claimed="medlabs_jordan", forbidden_sender={"medlabs_jordan"}, max_sender_trust="unknown"),

    # ── Education/University batch 1 ───────────────────────────────────────────
    # T. University of Jordan
    EntityCase(175, "official_alignment", "safe", "الجامعة الأردنية: تسجيل الفصل الدراسي على الرابط الرسمي https://ju.edu.jo", sender_name="University of Jordan", max_verdict="warn", expected_claimed="university_of_jordan", expected_domain="university_of_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(176, "mismatch_impersonation", "suspicious", "الجامعة الأردنية: حدّث بياناتك من الرابط https://ju-portal.test", min_verdict="caution", expected_claimed="university_of_jordan"),
    EntityCase(177, "forbidden_request", "dangerous", "الجامعة الأردنية تطلب كلمة المرور لتجديد تسجيل الطالب الإلكتروني", min_verdict="block", expected_claimed="university_of_jordan", required_evidence_any={"entity_policy_forbidden_university_of_jordan", "danger_password_request"}),
    EntityCase(178, "safe_awareness", "safe", "الجامعة الأردنية: لا تشارك كلمة المرور أو رمز الاسترداد مع أي جهة", sender_name="University of Jordan", max_verdict="warn", expected_claimed="university_of_jordan", forbidden_evidence={"entity_policy_forbidden_university_of_jordan"}),
    EntityCase(179, "alias_substring", "safe", "قامت جامعة الدول العربية بعقد اجتماع للوزراء في القاهرة", max_verdict="caution", forbidden_claimed={"university_of_jordan"}),
    EntityCase(180, "sender_spoofing", "suspicious", "تسجيلك في الفصل الدراسي يحتاج مراجعة https://ju-register.test", sender_name="UJ-System", forbidden_sender={"university_of_jordan"}, max_sender_trust="unknown"),

    # U. Jordan University of Science and Technology
    EntityCase(181, "official_alignment", "safe", "جامعة العلوم والتكنولوجيا الأردنية: التسجيل على الرابط الرسمي https://just.edu.jo", sender_name="JUST", max_verdict="warn", expected_claimed="just_jordan", expected_domain="just_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(182, "mismatch_impersonation", "suspicious", "جامعة العلوم والتكنولوجيا الأردنية: حدّث حسابك من الرابط https://just-portal.test", min_verdict="caution", expected_claimed="just_jordan"),
    EntityCase(183, "forbidden_request", "dangerous", "JUST يطلب كلمة المرور لتأكيد قبول الطالب وإتمام التسجيل", min_verdict="block", expected_claimed="just_jordan", required_evidence_any={"entity_policy_forbidden_just_jordan", "danger_password_request"}),
    EntityCase(184, "safe_awareness", "safe", "جامعة العلوم والتكنولوجيا الأردنية: لا تشارك بيانات دخولك مع أي جهة", sender_name="JUST", max_verdict="warn", expected_claimed="just_jordan", forbidden_evidence={"entity_policy_forbidden_just_jordan"}),
    EntityCase(185, "alias_substring", "safe", "تهتم المؤسسات الحكومية بدعم العلوم والتكنولوجيا في القطاع الأردني", max_verdict="caution", forbidden_claimed={"just_jordan"}),
    EntityCase(186, "sender_spoofing", "suspicious", "حسابك الجامعي يحتاج تحديثاً عاجلاً https://just-login.test", sender_name="JUST-Admin", forbidden_sender={"just_jordan"}, max_sender_trust="unknown"),

    # V. Yarmouk University
    EntityCase(187, "official_alignment", "safe", "جامعة اليرموك: التسجيل الجديد على الرابط الرسمي https://yu.edu.jo", sender_name="Yarmouk University", max_verdict="warn", expected_claimed="yarmouk_university", expected_domain="yarmouk_university", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(188, "mismatch_impersonation", "suspicious", "جامعة اليرموك: تحديث بياناتك من الرابط https://yarmouk-portal.test", min_verdict="caution", expected_claimed="yarmouk_university"),
    EntityCase(189, "forbidden_request", "dangerous", "جامعة اليرموك تطلب كلمة المرور لتجديد بيانات الطالب في النظام", min_verdict="block", expected_claimed="yarmouk_university", required_evidence_any={"entity_policy_forbidden_yarmouk_university", "danger_password_request"}),
    EntityCase(190, "safe_awareness", "safe", "جامعة اليرموك: لا تشارك كلمة مرور البوابة الجامعية مع أي شخص", sender_name="Yarmouk University", max_verdict="warn", expected_claimed="yarmouk_university", forbidden_evidence={"entity_policy_forbidden_yarmouk_university"}),
    EntityCase(191, "alias_substring", "safe", "تقع منطقة اليرموك في دمشق وتمتد على مساحة واسعة من المدينة", max_verdict="caution", forbidden_claimed={"yarmouk_university"}),
    EntityCase(192, "sender_spoofing", "suspicious", "فاتورة الرسوم الجامعية متاحة الآن https://yarmouk-fees.test", sender_name="Yarmouk-Uni", forbidden_sender={"yarmouk_university"}, max_sender_trust="unknown"),

    # W. Al-Balqa Applied University
    EntityCase(193, "official_alignment", "safe", "جامعة البلقاء التطبيقية: التسجيل الفصلي على الرابط الرسمي https://bau.edu.jo", sender_name="BAU", max_verdict="warn", expected_claimed="balqa_applied_university", expected_domain="balqa_applied_university", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(194, "mismatch_impersonation", "suspicious", "جامعة البلقاء التطبيقية: راجع حسابك من الرابط https://bau-portal.test", min_verdict="caution", expected_claimed="balqa_applied_university"),
    EntityCase(195, "forbidden_request", "dangerous", "جامعة البلقاء تطلب كلمة المرور لتحديث بيانات الطالب في البوابة", min_verdict="block", expected_claimed="balqa_applied_university", required_evidence_any={"entity_policy_forbidden_balqa_applied_university", "danger_password_request"}),
    EntityCase(196, "safe_awareness", "safe", "جامعة البلقاء التطبيقية: لا تدخل بيانات الدخول في روابط مجهولة", sender_name="BAU", max_verdict="warn", expected_claimed="balqa_applied_university", forbidden_evidence={"entity_policy_forbidden_balqa_applied_university"}),
    EntityCase(197, "alias_substring", "safe", "تقع منطقة البلقاء في وسط الأردن وتضم مدناً جميلة كثيرة", max_verdict="caution", forbidden_claimed={"balqa_applied_university"}),
    EntityCase(198, "sender_spoofing", "suspicious", "رسوم الفصل الدراسي في جامعة البلقاء https://bau-fees.test", sender_name="BAU-Notify", min_verdict="caution", expected_claimed="balqa_applied_university", forbidden_sender={"balqa_applied_university"}, max_sender_trust="unknown"),

    # X. The Hashemite University
    EntityCase(199, "official_alignment", "safe", "الجامعة الهاشمية: التسجيل مفتوح على الرابط الرسمي https://hu.edu.jo", sender_name="Hashemite University", max_verdict="warn", expected_claimed="hashemite_university", expected_domain="hashemite_university", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(200, "mismatch_impersonation", "suspicious", "الجامعة الهاشمية: تحديث بياناتك من الرابط https://hu-portal.test", min_verdict="caution", expected_claimed="hashemite_university"),
    EntityCase(201, "forbidden_request", "dangerous", "الجامعة الهاشمية تطلب كلمة المرور لاستعادة حساب الطالب في البوابة", min_verdict="block", expected_claimed="hashemite_university", required_evidence_any={"entity_policy_forbidden_hashemite_university", "danger_password_request"}),
    EntityCase(202, "safe_awareness", "safe", "الجامعة الهاشمية: لا تشارك رمز الاسترداد أو كلمة المرور مع أي جهة", sender_name="Hashemite University", max_verdict="warn", expected_claimed="hashemite_university", forbidden_evidence={"entity_policy_forbidden_hashemite_university"}),
    EntityCase(203, "alias_substring", "safe", "المؤسسة الهاشمية للدراسات الإسلامية تعقد ندوة علمية دولية", max_verdict="caution", forbidden_claimed={"hashemite_university"}),
    EntityCase(204, "sender_spoofing", "suspicious", "موعد دفع الرسوم الجامعية قادم https://hashemite-fees.test", sender_name="HU-Jordan-Admin", forbidden_sender={"hashemite_university"}, max_sender_trust="unknown"),

    # Y. Mutah University
    EntityCase(205, "official_alignment", "safe", "جامعة مؤتة: التسجيل الفصلي على الرابط الرسمي https://mutah.edu.jo", sender_name="Mutah University", max_verdict="warn", expected_claimed="mutah_university", expected_domain="mutah_university", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(206, "mismatch_impersonation", "suspicious", "جامعة مؤتة: راجع حسابك الجامعي من الرابط https://mutah-portal.test", min_verdict="caution", expected_claimed="mutah_university"),
    EntityCase(207, "forbidden_request", "dangerous", "جامعة مؤتة تطلب كلمة المرور لتجديد الاشتراك في البوابة الجامعية", min_verdict="block", expected_claimed="mutah_university", required_evidence_any={"entity_policy_forbidden_mutah_university", "danger_password_request"}),
    EntityCase(208, "safe_awareness", "safe", "جامعة مؤتة: لا تشارك كلمة مرور البوابة الجامعية مع أي جهة خارجية", sender_name="Mutah University", max_verdict="warn", expected_claimed="mutah_university", forbidden_evidence={"entity_policy_forbidden_mutah_university"}),
    EntityCase(209, "alias_substring", "safe", "تاريخ موقعة مؤتة يعود إلى عهد الخلافة الإسلامية المبكرة", max_verdict="caution", forbidden_claimed={"mutah_university"}),
    EntityCase(210, "sender_spoofing", "suspicious", "فاتورة الرسوم الدراسية في جامعة مؤتة https://mutah-fees.test", sender_name="Mutah-Admin", forbidden_sender={"mutah_university"}, max_sender_trust="unknown"),

    # Z. German Jordanian University
    EntityCase(211, "official_alignment", "safe", "الجامعة الألمانية الأردنية: تسجيل الفصل على الرابط الرسمي https://gju.edu.jo", sender_name="GJU", max_verdict="warn", expected_claimed="german_jordanian_university", expected_domain="german_jordanian_university", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(212, "mismatch_impersonation", "suspicious", "الجامعة الألمانية الأردنية: تحديث حسابك من الرابط https://gju-portal.test", min_verdict="caution", expected_claimed="german_jordanian_university"),
    EntityCase(213, "forbidden_request", "dangerous", "الجامعة الألمانية الأردنية تطلب كلمة المرور لتجديد تسجيل الطالب", min_verdict="block", expected_claimed="german_jordanian_university", required_evidence_any={"entity_policy_forbidden_german_jordanian_university", "danger_password_request"}),
    EntityCase(214, "safe_awareness", "safe", "الجامعة الألمانية الأردنية: لا تشارك بيانات حسابك الجامعي مع أي طرف", sender_name="GJU", max_verdict="warn", expected_claimed="german_jordanian_university", forbidden_evidence={"entity_policy_forbidden_german_jordanian_university"}),
    EntityCase(215, "alias_substring", "safe", "التعاون الأكاديمي الألماني الأردني يشمل مجالات متعددة من التطوير", max_verdict="caution", forbidden_claimed={"german_jordanian_university"}),
    EntityCase(216, "sender_spoofing", "suspicious", "موعد تسديد رسومك في الجامعة الألمانية https://gju-fees.test", sender_name="GJU-Admin", forbidden_sender={"german_jordanian_university"}, max_sender_trust="unknown"),

    # AA. Princess Sumaya University for Technology
    EntityCase(217, "official_alignment", "safe", "جامعة الأميرة سمية للتكنولوجيا: التسجيل على الرابط الرسمي https://psut.edu.jo", sender_name="PSUT", max_verdict="warn", expected_claimed="princess_sumaya_university", expected_domain="princess_sumaya_university", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(218, "mismatch_impersonation", "suspicious", "PSUT: راجع حسابك من الرابط https://psut-portal.test", min_verdict="caution", expected_claimed="princess_sumaya_university"),
    EntityCase(219, "forbidden_request", "dangerous", "جامعة الأميرة سمية للتكنولوجيا تطلب كلمة المرور لتجديد قبول الطالب", min_verdict="block", expected_claimed="princess_sumaya_university", required_evidence_any={"entity_policy_forbidden_princess_sumaya_university", "danger_password_request"}),
    EntityCase(220, "safe_awareness", "safe", "جامعة الأميرة سمية للتكنولوجيا: لا تشارك بيانات الدخول مع أي طرف", sender_name="PSUT", max_verdict="warn", expected_claimed="princess_sumaya_university", forbidden_evidence={"entity_policy_forbidden_princess_sumaya_university"}),
    EntityCase(221, "alias_substring", "safe", "حضرت سمية حفل التخرج مع عائلتها وأصدقائها المقربين", max_verdict="caution", forbidden_claimed={"princess_sumaya_university"}),
    EntityCase(222, "sender_spoofing", "suspicious", "رسوم الجامعة تحتاج إلى سداد من الرابط https://psut-fees.test", sender_name="PSUT-Notify", forbidden_sender={"princess_sumaya_university"}, max_sender_trust="unknown"),

    # AB. Applied Science Private University
    EntityCase(223, "official_alignment", "safe", "جامعة العلوم التطبيقية الخاصة: التسجيل الفصلي على الرابط الرسمي https://asu.edu.jo", sender_name="ASU Jordan", max_verdict="warn", expected_claimed="applied_science_university_jo", expected_domain="applied_science_university_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(224, "mismatch_impersonation", "suspicious", "جامعة العلوم التطبيقية الخاصة: تحديث بياناتك من الرابط https://asu-portal.test", min_verdict="caution", expected_claimed="applied_science_university_jo"),
    EntityCase(225, "forbidden_request", "dangerous", "جامعة العلوم التطبيقية تطلب كلمة المرور لاستعادة حساب الطالب الجامعي", min_verdict="block", expected_claimed="applied_science_university_jo", required_evidence_any={"entity_policy_forbidden_applied_science_university_jo", "danger_password_request"}),
    EntityCase(226, "safe_awareness", "safe", "جامعة العلوم التطبيقية الخاصة: لا تشارك رمز الاسترداد مع أي طرف", sender_name="ASU Jordan", max_verdict="warn", expected_claimed="applied_science_university_jo", forbidden_evidence={"entity_policy_forbidden_applied_science_university_jo"}),
    EntityCase(227, "alias_substring", "safe", "تُعنى مؤسسات العلوم التطبيقية بتطوير المهارات العملية للطلاب", max_verdict="caution", forbidden_claimed={"applied_science_university_jo"}),
    EntityCase(228, "sender_spoofing", "suspicious", "رسوم الفصل الدراسي مستحقة الدفع https://asu-fees.test", sender_name="ASU-Jordan-Admin", forbidden_sender={"applied_science_university_jo"}, max_sender_trust="unknown"),

    # AC. Philadelphia University Jordan
    EntityCase(229, "official_alignment", "safe", "جامعة فيلادلفيا: التسجيل مفتوح على الرابط الرسمي https://philadelphia.edu.jo", sender_name="Philadelphia University", max_verdict="warn", expected_claimed="philadelphia_university_jo", expected_domain="philadelphia_university_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(230, "mismatch_impersonation", "suspicious", "جامعة فيلادلفيا: تحديث معلوماتك من الرابط https://philadelphia-portal.test", min_verdict="caution", expected_claimed="philadelphia_university_jo"),
    EntityCase(231, "forbidden_request", "dangerous", "جامعة فيلادلفيا تطلب كلمة المرور لاستكمال التسجيل الجامعي الإلكتروني", min_verdict="block", expected_claimed="philadelphia_university_jo", required_evidence_any={"entity_policy_forbidden_philadelphia_university_jo", "danger_password_request"}),
    EntityCase(232, "safe_awareness", "safe", "جامعة فيلادلفيا: لا تشارك كلمة مرور الحساب الجامعي مع أي جهة خارجية", sender_name="Philadelphia University", max_verdict="warn", expected_claimed="philadelphia_university_jo", forbidden_evidence={"entity_policy_forbidden_philadelphia_university_jo"}),
    EntityCase(233, "alias_substring", "safe", "يحلم كثير من الطلاب بزيارة مدينة فيلادلفيا التاريخية في الولايات المتحدة", max_verdict="caution", forbidden_claimed={"philadelphia_university_jo"}),
    EntityCase(234, "sender_spoofing", "suspicious", "دفع رسوم الجامعة مستحق الآن https://philadelphia-fees.test", sender_name="Philadelphia-Admin", forbidden_sender={"philadelphia_university_jo"}, max_sender_trust="unknown"),

    # ── Government batch 1 ────────────────────────────────────────────────────

    # AD. Ministry of Finance Jordan
    EntityCase(235, "official_alignment", "safe", "وزارة المالية: إشعار استرداد ضريبي على الرابط الرسمي https://mof.gov.jo", sender_name="MOF", max_verdict="warn", expected_claimed="ministry_of_finance_jo", expected_domain="ministry_of_finance_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(236, "mismatch_impersonation", "suspicious", "وزارة المالية: استرداد ضريبي متاح من الرابط https://mof-refund.test", min_verdict="caution", expected_claimed="ministry_of_finance_jo"),
    EntityCase(237, "forbidden_request", "dangerous", "وزارة المالية تطلب كلمة المرور لتسجيل الدخول وإتمام طلب الخدمة الحكومية", min_verdict="block", expected_claimed="ministry_of_finance_jo", required_evidence_any={"entity_policy_forbidden_ministry_of_finance_jo", "danger_password_request"}),
    EntityCase(238, "safe_awareness", "safe", "وزارة المالية: لا تشارك كلمة المرور أو أي بيانات مصرفية عبر الرسائل القصيرة", sender_name="MOF", max_verdict="warn", expected_claimed="ministry_of_finance_jo", forbidden_evidence={"entity_policy_forbidden_ministry_of_finance_jo"}),
    EntityCase(239, "alias_substring", "safe", "قدمت الموازنة المالية الوطنية تحليلاً شاملاً لمؤشرات التنمية الاقتصادية", max_verdict="caution", forbidden_claimed={"ministry_of_finance_jo"}),
    EntityCase(240, "sender_spoofing", "suspicious", "استرداد ضريبي بانتظارك من الرابط https://mof-tax.test", sender_name="MOF-Refund", forbidden_sender={"ministry_of_finance_jo"}, max_sender_trust="unknown"),

    # AE. Ministry of Education Jordan
    EntityCase(241, "official_alignment", "safe", "وزارة التربية والتعليم: نتائج التوجيهي متاحة على الرابط الرسمي https://moe.gov.jo", sender_name="MOE Jordan", max_verdict="warn", expected_claimed="ministry_of_education_jo", expected_domain="ministry_of_education_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(242, "mismatch_impersonation", "suspicious", "وزارة التربية: نتائج الامتحانات من الرابط https://moe-results.test", min_verdict="caution", expected_claimed="ministry_of_education_jo"),
    EntityCase(243, "forbidden_request", "dangerous", "وزارة التربية والتعليم تطلب كلمة المرور للوصول إلى نتائج امتحانات التوجيهي", min_verdict="block", expected_claimed="ministry_of_education_jo", required_evidence_any={"entity_policy_forbidden_ministry_of_education_jo", "danger_password_request"}),
    EntityCase(244, "safe_awareness", "safe", "وزارة التربية والتعليم: لا يطلب منك أي موظف كلمة المرور أو رمز التحقق", sender_name="MOE Jordan", max_verdict="warn", expected_claimed="ministry_of_education_jo", forbidden_evidence={"entity_policy_forbidden_ministry_of_education_jo"}),
    EntityCase(245, "alias_substring", "safe", "تعمل مؤسسات التربية والتعليم الخاصة على تطوير المناهج الدراسية الحديثة", max_verdict="caution", forbidden_claimed={"ministry_of_education_jo"}),
    EntityCase(246, "sender_spoofing", "suspicious", "نتائج التوجيهي جاهزة للعرض من الرابط https://moe-tawjihi.test", sender_name="MOE-Results", forbidden_sender={"ministry_of_education_jo"}, max_sender_trust="unknown"),

    # AF. Ministry of Labor Jordan
    EntityCase(247, "official_alignment", "safe", "وزارة العمل: تجديد تصريح العمل على الرابط الرسمي https://mol.gov.jo", sender_name="MOL Jordan", max_verdict="warn", expected_claimed="ministry_of_labor_jo", expected_domain="ministry_of_labor_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(248, "mismatch_impersonation", "suspicious", "وزارة العمل: تحديث بيانات التوظيف من الرابط https://mol-update.test", min_verdict="caution", expected_claimed="ministry_of_labor_jo"),
    EntityCase(249, "forbidden_request", "dangerous", "وزارة العمل تطلب كلمة المرور لتحديث ملف التوظيف وتجديد التصاريح", min_verdict="block", expected_claimed="ministry_of_labor_jo", required_evidence_any={"entity_policy_forbidden_ministry_of_labor_jo", "danger_password_request"}),
    EntityCase(250, "safe_awareness", "safe", "وزارة العمل: لا تشارك بيانات حسابك أو رمز التحقق مع أي جهة غير رسمية", sender_name="MOL Jordan", max_verdict="warn", expected_claimed="ministry_of_labor_jo", forbidden_evidence={"entity_policy_forbidden_ministry_of_labor_jo"}),
    EntityCase(251, "alias_substring", "safe", "تعكف لجان العمل والتوظيف على مراجعة معايير التوظيف في القطاع الخاص", max_verdict="caution", forbidden_claimed={"ministry_of_labor_jo"}),
    EntityCase(252, "sender_spoofing", "suspicious", "تصريح عملك يحتاج تجديداً فورياً https://mol-permit.test", sender_name="MOL-Notify", forbidden_sender={"ministry_of_labor_jo"}, max_sender_trust="unknown"),

    # AG. Telecommunications Regulatory Commission Jordan
    EntityCase(253, "official_alignment", "safe", "هيئة تنظيم الاتصالات: إشعار رسمي متاح على https://trc.gov.jo", sender_name="TRC Jordan", max_verdict="warn", expected_claimed="telecommunications_regulatory_commission_jo", expected_domain="telecommunications_regulatory_commission_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(254, "mismatch_impersonation", "suspicious", "هيئة الاتصالات: تحديث بيانات خطك من الرابط https://trc-verify.test", min_verdict="caution", expected_claimed="telecommunications_regulatory_commission_jo"),
    EntityCase(255, "forbidden_request", "dangerous", "هيئة الاتصالات تطلب كلمة المرور لتأكيد هوية المشترك ومنع إيقاف الخط", min_verdict="block", expected_claimed="telecommunications_regulatory_commission_jo", required_evidence_any={"entity_policy_forbidden_telecommunications_regulatory_commission_jo", "danger_password_request"}),
    EntityCase(256, "safe_awareness", "safe", "هيئة تنظيم الاتصالات: لا تشارك رمز التحقق أو كلمة المرور مع أي شخص", sender_name="TRC Jordan", max_verdict="warn", expected_claimed="telecommunications_regulatory_commission_jo", forbidden_evidence={"entity_policy_forbidden_telecommunications_regulatory_commission_jo"}),
    EntityCase(257, "alias_substring", "safe", "تعمل هيئات الاتصالات الدولية على تطوير معايير التنظيم الرقمي العالمي", max_verdict="caution", forbidden_claimed={"telecommunications_regulatory_commission_jo"}),
    EntityCase(258, "sender_spoofing", "suspicious", "خطك يواجه إيقافاً فورياً إذا لم تتحقق من الرابط https://trc-sim.test", sender_name="TRC-Alert", forbidden_sender={"telecommunications_regulatory_commission_jo"}, max_sender_trust="unknown"),

    # AH. Jordan Food and Drug Administration
    EntityCase(259, "official_alignment", "safe", "هيئة الغذاء والدواء: إشعار رسمي من الهيئة على https://jfda.gov.jo", sender_name="JFDA", max_verdict="warn", expected_claimed="jordan_food_drug_administration", expected_domain="jordan_food_drug_administration", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(260, "mismatch_impersonation", "suspicious", "هيئة الغذاء والدواء: تسجيل منتجك من الرابط https://jfda-register.test", min_verdict="caution", expected_claimed="jordan_food_drug_administration"),
    EntityCase(261, "forbidden_request", "dangerous", "هيئة الغذاء والدواء تطلب كلمة المرور للوصول إلى بوابة التسجيل الإلكتروني", min_verdict="block", expected_claimed="jordan_food_drug_administration", required_evidence_any={"entity_policy_forbidden_jordan_food_drug_administration", "danger_password_request"}),
    EntityCase(262, "safe_awareness", "safe", "هيئة الغذاء والدواء: لا يطلب منك إدخال كلمة المرور أو بيانات الدفع عبر الرسائل", sender_name="JFDA", max_verdict="warn", expected_claimed="jordan_food_drug_administration", forbidden_evidence={"entity_policy_forbidden_jordan_food_drug_administration"}),
    EntityCase(263, "alias_substring", "safe", "تقوم هيئات الغذاء والدواء الإقليمية بمراجعة معايير سلامة الغذاء سنوياً", max_verdict="caution", forbidden_claimed={"jordan_food_drug_administration"}),
    EntityCase(264, "sender_spoofing", "suspicious", "منتجك يحتاج إلى تحديث تسجيل فوري https://jfda-drug.test", sender_name="JFDA-Alert", forbidden_sender={"jordan_food_drug_administration"}, max_sender_trust="unknown"),

    # AI. Jordan Securities Commission
    EntityCase(265, "official_alignment", "safe", "هيئة الأوراق المالية: إشعار حساب الاستثمار متاح على https://jsc.gov.jo", sender_name="JSC Jordan", max_verdict="warn", expected_claimed="jordan_securities_commission", expected_domain="jordan_securities_commission", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(266, "mismatch_impersonation", "suspicious", "هيئة الأوراق المالية: تحقق من حسابك الاستثماري https://jsc-login.test", min_verdict="caution", expected_claimed="jordan_securities_commission"),
    EntityCase(267, "forbidden_request", "dangerous", "هيئة الأوراق المالية تطلب كلمة المرور لتأكيد هوية المستثمر واسترداد أرباحه", min_verdict="block", expected_claimed="jordan_securities_commission", required_evidence_any={"entity_policy_forbidden_jordan_securities_commission", "danger_password_request"}),
    EntityCase(268, "safe_awareness", "safe", "هيئة الأوراق المالية: لا يطلب منك أي ممثل رسمي كلمة المرور أو بيانات الحساب", sender_name="JSC Jordan", max_verdict="warn", expected_claimed="jordan_securities_commission", forbidden_evidence={"entity_policy_forbidden_jordan_securities_commission"}),
    EntityCase(269, "alias_substring", "safe", "تصدر هيئات الأوراق المالية الدولية تقارير دورية حول أسواق رأس المال", max_verdict="caution", forbidden_claimed={"jordan_securities_commission"}),
    EntityCase(270, "sender_spoofing", "suspicious", "أرباح استثمارية جاهزة للسحب من الرابط https://jsc-profits.test", sender_name="JSC-Invest", forbidden_sender={"jordan_securities_commission"}, max_sender_trust="unknown"),

    # AJ. National Information Technology Center Jordan
    EntityCase(271, "official_alignment", "safe", "المركز الوطني لتكنولوجيا المعلومات: الخدمة الحكومية متاحة على https://nitc.gov.jo", sender_name="NITC Jordan", max_verdict="warn", expected_claimed="national_information_technology_center_jo", expected_domain="national_information_technology_center_jo", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(272, "mismatch_impersonation", "suspicious", "المركز الوطني لتكنولوجيا المعلومات: تحديث بياناتك الرقمية https://nitc-portal.test", min_verdict="caution", expected_claimed="national_information_technology_center_jo"),
    EntityCase(273, "forbidden_request", "dangerous", "المركز الوطني لتكنولوجيا المعلومات يطلب كلمة المرور لتفعيل الهوية الرقمية", min_verdict="block", expected_claimed="national_information_technology_center_jo", required_evidence_any={"entity_policy_forbidden_national_information_technology_center_jo", "danger_password_request"}),
    EntityCase(274, "safe_awareness", "safe", "المركز الوطني لتكنولوجيا المعلومات: لا تدخل كلمة مرور البوابة عبر أي رسالة نصية", sender_name="NITC Jordan", max_verdict="warn", expected_claimed="national_information_technology_center_jo", forbidden_evidence={"entity_policy_forbidden_national_information_technology_center_jo"}),
    EntityCase(275, "alias_substring", "safe", "تعتمد مراكز التكنولوجيا الوطنية على بنية تحتية رقمية متطورة لدعم التحول", max_verdict="caution", forbidden_claimed={"national_information_technology_center_jo"}),
    EntityCase(276, "sender_spoofing", "suspicious", "تفعيل هويتك الرقمية الحكومية مطلوب https://nitc-id.test", sender_name="NITC-Gov", forbidden_sender={"national_information_technology_center_jo"}, max_sender_trust="unknown"),

    # AK. Jordan Investment Commission
    EntityCase(277, "official_alignment", "safe", "هيئة الاستثمار الأردنية: إتمام تسجيل الأعمال على الرابط الرسمي https://jic.gov.jo", sender_name="JIC Jordan", max_verdict="warn", expected_claimed="jordan_investment_commission", expected_domain="jordan_investment_commission", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(278, "mismatch_impersonation", "suspicious", "هيئة الاستثمار الأردنية: تحديث بيانات شركتك من الرابط https://jic-update.test", min_verdict="caution", expected_claimed="jordan_investment_commission"),
    EntityCase(279, "forbidden_request", "dangerous", "هيئة الاستثمار الأردنية تطلب كلمة المرور لاستكمال تسجيل المشروع الاستثماري", min_verdict="block", expected_claimed="jordan_investment_commission", required_evidence_any={"entity_policy_forbidden_jordan_investment_commission", "danger_password_request"}),
    EntityCase(280, "safe_awareness", "safe", "هيئة الاستثمار الأردنية: لا يطلب منك أي موظف كلمة المرور عبر الهاتف أو الرسائل", sender_name="JIC Jordan", max_verdict="warn", expected_claimed="jordan_investment_commission", forbidden_evidence={"entity_policy_forbidden_jordan_investment_commission"}),
    EntityCase(281, "alias_substring", "safe", "تشجع هيئات الاستثمار الإقليمية على تطوير بيئة الأعمال في المنطقة العربية", max_verdict="caution", forbidden_claimed={"jordan_investment_commission"}),
    EntityCase(282, "sender_spoofing", "suspicious", "تسجيل مشروعك يحتاج موافقة فورية https://jic-business.test", sender_name="JIC-Invest", forbidden_sender={"jordan_investment_commission"}, max_sender_trust="unknown"),

    # ── Delivery / Logistics batch 1 ─────────────────────────────────────────

    # AL. FedEx
    EntityCase(283, "official_alignment", "safe", "FedEx: تتبع طردك على الرابط الرسمي https://fedex.com", sender_name="FedEx", max_verdict="warn", expected_claimed="fedex", expected_domain="fedex", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(284, "mismatch_impersonation", "suspicious", "FedEx: طردك بانتظار التسليم أكد بياناتك من الرابط https://fedex-verify.test", min_verdict="caution", expected_claimed="fedex"),
    EntityCase(285, "forbidden_request", "dangerous", "FedEx يطلب كلمة المرور للدخول إلى حساب تتبع طردك وإتمام التسليم", min_verdict="block", expected_claimed="fedex", required_evidence_any={"entity_policy_forbidden_fedex", "danger_password_request"}),
    EntityCase(286, "safe_awareness", "safe", "FedEx: لا يطلب منك إدخال بيانات البطاقة لإتمام التوصيل عبر الرسائل النصية", sender_name="FedEx", max_verdict="warn", expected_claimed="fedex", forbidden_evidence={"entity_policy_forbidden_fedex"}),
    EntityCase(287, "alias_substring", "safe", "تتميز خدمات الشحن الدولية بسرعة التوصيل وتنوع خيارات التتبع المتاحة", max_verdict="caution", forbidden_claimed={"fedex"}),
    EntityCase(288, "sender_spoofing", "suspicious", "طردك من FedEx يحتاج تأكيد عنوان التسليم https://fedex-redeliver.test", sender_name="FedEx-Support", forbidden_sender={"fedex"}, max_sender_trust="unknown"),

    # AM. UPS
    EntityCase(289, "official_alignment", "safe", "UPS: تتبع شحنتك على الرابط الرسمي https://ups.com", sender_name="UPS", max_verdict="warn", expected_claimed="ups", expected_domain="ups", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(290, "mismatch_impersonation", "suspicious", "UPS: شحنتك بانتظار التسليم أكد عنوانك من الرابط https://ups-verify.test", min_verdict="caution", expected_claimed="ups"),
    EntityCase(291, "forbidden_request", "dangerous", "UPS يطلب كلمة المرور لتأكيد هوية صاحب الشحنة وإتمام التسليم", min_verdict="block", expected_claimed="ups", required_evidence_any={"entity_policy_forbidden_ups", "danger_password_request"}),
    EntityCase(292, "safe_awareness", "safe", "UPS: لا يطلب منك أي موظف بيانات البطاقة الائتمانية أو رمز التحقق للتسليم", sender_name="UPS", max_verdict="warn", expected_claimed="ups", forbidden_evidence={"entity_policy_forbidden_ups"}),
    EntityCase(293, "alias_substring", "safe", "توفر شركات التوصيل الدولية خدمات شحن سريعة من مختلف أنحاء العالم", max_verdict="caution", forbidden_claimed={"ups"}),
    EntityCase(294, "sender_spoofing", "suspicious", "شحنتك من UPS تحتاج تأكيد موعد التسليم https://ups-delivery.test", sender_name="UPS-Alerts", forbidden_sender={"ups"}, max_sender_trust="unknown"),

    # AN. Fetchr
    EntityCase(295, "official_alignment", "safe", "Fetchr: تتبع طلبك على الرابط الرسمي https://fetchr.com", sender_name="Fetchr", max_verdict="warn", expected_claimed="fetchr", expected_domain="fetchr", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(296, "mismatch_impersonation", "suspicious", "Fetchr: طردك بانتظار التسليم ادفع رسوم التحرير https://fetchr-fee.test", min_verdict="caution", expected_claimed="fetchr"),
    EntityCase(297, "forbidden_request", "dangerous", "Fetchr تطلب كلمة المرور للدخول إلى حساب تتبع طلبك وتأكيد التسليم", min_verdict="block", expected_claimed="fetchr", required_evidence_any={"entity_policy_forbidden_fetchr", "danger_password_request"}),
    EntityCase(298, "safe_awareness", "safe", "Fetchr: لا تشارك بيانات بطاقتك مع أي رسالة تدّعي أنها من فيتشر", sender_name="Fetchr", max_verdict="warn", expected_claimed="fetchr", forbidden_evidence={"entity_policy_forbidden_fetchr"}),
    EntityCase(299, "alias_substring", "safe", "خدمات التوصيل السريع المتاحة في المنطقة تشمل عدة شركات ناشئة متخصصة", max_verdict="caution", forbidden_claimed={"fetchr"}),
    EntityCase(300, "sender_spoofing", "suspicious", "طردك من Fetchr يحتاج تأكيد عنوان التسليم https://fetchr-redeliver.test", sender_name="Fetchr-Alert", forbidden_sender={"fetchr"}, max_sender_trust="unknown"),

    # AO. iMile Delivery
    EntityCase(301, "official_alignment", "safe", "iMile: تتبع شحنتك على الرابط الرسمي https://imile.com", sender_name="iMile", max_verdict="warn", expected_claimed="imile_delivery", expected_domain="imile_delivery", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(302, "mismatch_impersonation", "suspicious", "آي مايل: طردك محتجز وادفع رسوم التسليم من https://imile-fee.test", min_verdict="caution", expected_claimed="imile_delivery"),
    EntityCase(303, "forbidden_request", "dangerous", "آي مايل للتوصيل تطلب كلمة المرور للدخول إلى حساب التتبع وتأكيد التسليم", min_verdict="block", expected_claimed="imile_delivery", required_evidence_any={"entity_policy_forbidden_imile_delivery", "danger_password_request"}),
    EntityCase(304, "safe_awareness", "safe", "iMile: لا يطلب منك إدخال بيانات البطاقة أو رمز التحقق عبر الرسائل", sender_name="iMile", max_verdict="warn", expected_claimed="imile_delivery", forbidden_evidence={"entity_policy_forbidden_imile_delivery"}),
    EntityCase(305, "alias_substring", "safe", "تغطي شركات التوصيل الذكية مساحات جغرافية واسعة بكفاءة عالية", max_verdict="caution", forbidden_claimed={"imile_delivery"}),
    EntityCase(306, "sender_spoofing", "suspicious", "شحنتك من آي مايل تحتاج تأكيد موعد التسليم https://imile-delivery.test", sender_name="iMile-Express", forbidden_sender={"imile_delivery"}, max_sender_trust="unknown"),

    # AP. Shipa Delivery
    EntityCase(307, "official_alignment", "safe", "Shipa Delivery: تتبع طردك على الرابط الرسمي https://shipadelivery.com", sender_name="Shipa", max_verdict="warn", expected_claimed="shipa_delivery", expected_domain="shipa_delivery", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(308, "mismatch_impersonation", "suspicious", "شيبا للتوصيل: طردك محتجز ادفع رسوم الجمارك https://shipa-customs.test", min_verdict="caution", expected_claimed="shipa_delivery"),
    EntityCase(309, "forbidden_request", "dangerous", "Shipa تطلب كلمة المرور للتحقق من هوية المستلم وإتمام عملية التسليم", min_verdict="block", expected_claimed="shipa_delivery", required_evidence_any={"entity_policy_forbidden_shipa_delivery", "danger_password_request"}),
    EntityCase(310, "safe_awareness", "safe", "Shipa Delivery: لا تشارك رقم بطاقتك مع أي رسالة تدّعي أنها من شيبا", sender_name="Shipa", max_verdict="warn", expected_claimed="shipa_delivery", forbidden_evidence={"entity_policy_forbidden_shipa_delivery"}),
    EntityCase(311, "alias_substring", "safe", "تتوسع شركات التوصيل الإقليمية في أسواق المنطقة بشكل ملحوظ", max_verdict="caution", forbidden_claimed={"shipa_delivery"}),
    EntityCase(312, "sender_spoofing", "suspicious", "طردك من Shipa بانتظار التسليم أكد عنوانك https://shipa-redeliver.test", sender_name="Shipa-Deliver", forbidden_sender={"shipa_delivery"}, max_sender_trust="unknown"),

    # AQ. Bosta
    EntityCase(313, "official_alignment", "safe", "Bosta: تتبع شحنتك على الرابط الرسمي https://bosta.co", sender_name="Bosta", max_verdict="warn", expected_claimed="bosta_mena", expected_domain="bosta_mena", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(314, "mismatch_impersonation", "suspicious", "بوسطة: طردك محتجز ادفع رسوم التوصيل من الرابط https://bosta-fee.test", min_verdict="caution", expected_claimed="bosta_mena"),
    EntityCase(315, "forbidden_request", "dangerous", "Bosta تطلب كلمة المرور للدخول إلى حساب التتبع وتأكيد عنوان التسليم", min_verdict="block", expected_claimed="bosta_mena", required_evidence_any={"entity_policy_forbidden_bosta_mena", "danger_password_request"}),
    EntityCase(316, "safe_awareness", "safe", "Bosta: لا يطلب منك إدخال بيانات البطاقة أو أي معلومات مالية عبر الرسائل", sender_name="Bosta", max_verdict="warn", expected_claimed="bosta_mena", forbidden_evidence={"entity_policy_forbidden_bosta_mena"}),
    EntityCase(317, "alias_substring", "safe", "خدمات البريد والبوسطة التقليدية لا تزال مستخدمة في بعض المناطق النائية", max_verdict="caution", forbidden_claimed={"bosta_mena"}),
    EntityCase(318, "sender_spoofing", "suspicious", "شحنتك من Bosta جاهزة للتسليم أكد عنوانك https://bosta-deliver.test", sender_name="Bosta-Express", forbidden_sender={"bosta_mena"}, max_sender_trust="unknown"),

    # AO. AliExpress
    EntityCase(319, "official_alignment", "safe", "AliExpress: طلبك قيد الشحن يمكنك التتبع من الرابط الرسمي https://aliexpress.com", sender_name="AliExpress", max_verdict="warn", expected_claimed="aliexpress", expected_domain="aliexpress", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(320, "mismatch_impersonation", "suspicious", "AliExpress: مشكلة في التسليم أكد عنوانك من https://aliexpress-delivery.test", min_verdict="caution", expected_claimed="aliexpress"),
    EntityCase(321, "forbidden_request", "dangerous", "AliExpress يطلب كلمة المرور للتحقق من هويتك ومعالجة طلب الاسترداد", min_verdict="block", expected_claimed="aliexpress", required_evidence_any={"entity_policy_forbidden_aliexpress", "danger_password_request"}),
    EntityCase(322, "safe_awareness", "safe", "AliExpress: لا يطلب منك إدخال كلمة المرور أو بيانات بطاقتك عبر الرسائل النصية", sender_name="AliExpress", max_verdict="warn", expected_claimed="aliexpress", forbidden_evidence={"entity_policy_forbidden_aliexpress"}),
    EntityCase(323, "alias_substring", "safe", "تتنوع خدمات الشراء عبر الإنترنت وتوفر منصات متعددة لعمليات البيع والشراء", max_verdict="caution", forbidden_claimed={"aliexpress"}),
    EntityCase(324, "sender_spoofing", "suspicious", "طلبك من AliExpress معلق بسبب بيانات ناقصة أكد هويتك https://aliexpress-verify.test", sender_name="AliExpress-Support", forbidden_sender={"aliexpress"}, max_sender_trust="unknown"),

    # AP. Namshi
    EntityCase(325, "official_alignment", "safe", "نمشي: طلبك في الطريق إليك تتبع الشحنة من الرابط الرسمي https://namshi.com", sender_name="Namshi", max_verdict="warn", expected_claimed="namshi", expected_domain="namshi", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(326, "mismatch_impersonation", "suspicious", "نمشي: فرصة عرض انتهت جدد معلومات الدفع من https://namshi-offer.test", min_verdict="caution", expected_claimed="namshi"),
    EntityCase(327, "forbidden_request", "dangerous", "نمشي تطلب كلمة المرور لإعادة تعيين حسابك وتفعيل العرض الخاص", min_verdict="block", expected_claimed="namshi", required_evidence_any={"entity_policy_forbidden_namshi", "danger_password_request"}),
    EntityCase(328, "safe_awareness", "safe", "نمشي: لا تشارك كلمة المرور الخاصة بك مع أي شخص حتى وإن ادعى أنه من فريق الدعم", sender_name="Namshi", max_verdict="warn", expected_claimed="namshi", forbidden_evidence={"entity_policy_forbidden_namshi"}),
    EntityCase(329, "alias_substring", "safe", "تتميز منصات التسوق الإلكترونية الحديثة بتوفير تجربة تسوق سلسة ومريحة للمستخدمين", max_verdict="caution", forbidden_claimed={"namshi"}),
    EntityCase(330, "sender_spoofing", "suspicious", "طلبك من نمشي يحتاج مراجعة بيانات الدفع زوروا الرابط https://namshi-cs.test", sender_name="Namshi-Support", forbidden_sender={"namshi"}, max_sender_trust="unknown"),

    # AQ. Max Fashion
    EntityCase(331, "official_alignment", "safe", "Max Fashion: طلبك جاهز للاستلام من المتجر زوروا https://max-fashion.com", sender_name="MaxFashion", max_verdict="warn", expected_claimed="max_fashion_mena", expected_domain="max_fashion_mena", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(332, "mismatch_impersonation", "suspicious", "ماكس للأزياء: فرصة حصرية انتهاء خصومات سارع للتسجيل من https://max-fashion-offer.test", min_verdict="caution", expected_claimed="max_fashion_mena"),
    EntityCase(333, "forbidden_request", "dangerous", "ماكس للأزياء تطلب كلمة المرور للتحقق من هويتك وتأكيد استرداد المبلغ", min_verdict="block", expected_claimed="max_fashion_mena", required_evidence_any={"entity_policy_forbidden_max_fashion_mena", "danger_password_request"}),
    EntityCase(334, "safe_awareness", "safe", "ماكس للأزياء: لا يطلب منك إدخال كلمة المرور أو رمز التحقق عبر الرسائل النصية", sender_name="MaxFashion", max_verdict="warn", expected_claimed="max_fashion_mena", forbidden_evidence={"entity_policy_forbidden_max_fashion_mena"}),
    EntityCase(335, "alias_substring", "safe", "تتنوع خدمات التجزئة الحديثة لتشمل قطاعات متعددة من المنتجات الاستهلاكية", max_verdict="caution", forbidden_claimed={"max_fashion_mena"}),
    EntityCase(336, "sender_spoofing", "suspicious", "عرض حصري من ماكس للأزياء اضغط هنا للحصول على الخصم https://max-fashion-promo.test", sender_name="MaxFashion-Promo", forbidden_sender={"max_fashion_mena"}, max_sender_trust="unknown"),

    # AR. Wolt
    EntityCase(337, "official_alignment", "safe", "Wolt: طلبك قيد التحضير يمكنك تتبعه من الرابط الرسمي https://wolt.com", sender_name="Wolt", max_verdict="warn", expected_claimed="wolt_jordan", expected_domain="wolt_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(338, "mismatch_impersonation", "suspicious", "Wolt: مشكلة في الدفع أعد تأكيد بياناتك من https://wolt-pay.test", min_verdict="caution", expected_claimed="wolt_jordan"),
    EntityCase(339, "forbidden_request", "dangerous", "Wolt يطلب كلمة المرور للتحقق من هويتك وإعادة تفعيل حسابك", min_verdict="block", expected_claimed="wolt_jordan", required_evidence_any={"entity_policy_forbidden_wolt_jordan", "danger_password_request"}),
    EntityCase(340, "safe_awareness", "safe", "Wolt: لا يطلب منك إدخال كلمة المرور أو بيانات بطاقتك عبر الرسائل النصية", sender_name="Wolt", max_verdict="warn", expected_claimed="wolt_jordan", forbidden_evidence={"entity_policy_forbidden_wolt_jordan"}),
    EntityCase(341, "alias_substring", "safe", "تشتهر أدوات المطبخ الحديثة بجودتها العالية وقدرتها على تيسير مهام الطهي والإعداد", max_verdict="caution", forbidden_claimed={"wolt_jordan"}),
    EntityCase(342, "sender_spoofing", "suspicious", "طلبك من Wolt معلق بسبب مشكلة في التحقق تواصل معنا https://wolt-support.test", sender_name="Wolt-Service", forbidden_sender={"wolt_jordan"}, max_sender_trust="unknown"),

    # AS. Temu
    EntityCase(343, "official_alignment", "safe", "Temu: طلبك تم تأكيده وسيصلك قريباً تتبع من الرابط الرسمي https://temu.com", sender_name="TEMU", max_verdict="warn", expected_claimed="temu", expected_domain="temu", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(344, "mismatch_impersonation", "suspicious", "Temu: مشكلة في شحنتك تحتاج تأكيد البيانات من https://temu-deliver.test", min_verdict="caution", expected_claimed="temu"),
    EntityCase(345, "forbidden_request", "dangerous", "Temu يطلب كلمة المرور للتحقق من حسابك وإتمام عملية الشحن المعلقة", min_verdict="block", expected_claimed="temu", required_evidence_any={"entity_policy_forbidden_temu", "danger_password_request"}),
    EntityCase(346, "safe_awareness", "safe", "Temu: لا يطلب منك إدخال كلمة المرور أو بيانات بطاقتك عبر الرسائل النصية", sender_name="TEMU", max_verdict="warn", expected_claimed="temu", forbidden_evidence={"entity_policy_forbidden_temu"}),
    EntityCase(347, "alias_substring", "safe", "تتميز تقنيات الاتصال الحديثة بقدرتها على نقل البيانات بسرعة وكفاءة عالية", max_verdict="caution", forbidden_claimed={"temu"}),
    EntityCase(348, "sender_spoofing", "suspicious", "طلبك من Temu معلق بسبب مشكلة في التحقق تواصل معنا https://temu-support.test", sender_name="Temu-Support", forbidden_sender={"temu"}, max_sender_trust="unknown"),

    # AT. American Express
    EntityCase(349, "official_alignment", "safe", "American Express: تم معالجة معاملتك راجع التفاصيل على الرابط الرسمي https://americanexpress.com", sender_name="Amex", max_verdict="warn", expected_claimed="american_express", expected_domain="american_express", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(350, "mismatch_impersonation", "suspicious", "American Express: نشاط مشبوه في حسابك تحقق من الرابط https://amex-secure.test", min_verdict="caution", expected_claimed="american_express"),
    EntityCase(351, "forbidden_request", "dangerous", "أمريكان إكسبريس يطلب كلمة المرور للتحقق من هويتك وتأمين حسابك", min_verdict="block", expected_claimed="american_express", required_evidence_any={"entity_policy_forbidden_american_express", "danger_password_request"}),
    EntityCase(352, "safe_awareness", "safe", "أمريكان إكسبريس: لا يطلب منك مشاركة كلمة المرور أو بيانات بطاقتك عبر الرسائل", sender_name="Amex", max_verdict="warn", expected_claimed="american_express", forbidden_evidence={"entity_policy_forbidden_american_express"}),
    EntityCase(353, "alias_substring", "safe", "تشتهر الجامعات الدولية بتقديم برامج أكاديمية متنوعة تغطي مختلف التخصصات والمجالات العلمية", max_verdict="caution", forbidden_claimed={"american_express"}),
    EntityCase(354, "sender_spoofing", "suspicious", "بطاقتك من أمريكان إكسبريس معلقة بسبب نشاط مشبوه تواصل عبر https://amex-verify.test", sender_name="AmericanExpress-Alert", forbidden_sender={"american_express"}, max_sender_trust="unknown"),

    # AU. UnionPay
    EntityCase(355, "official_alignment", "safe", "UnionPay: تم إتمام معاملتك تفاصيل الاستفسار على الرابط الرسمي https://unionpayintl.com", sender_name="UnionPay", max_verdict="warn", expected_claimed="union_pay", expected_domain="union_pay", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(356, "mismatch_impersonation", "suspicious", "UnionPay: مراجعة ضرورية لبطاقتك تحقق عبر الرابط https://unionpay-verify.test", min_verdict="caution", expected_claimed="union_pay"),
    EntityCase(357, "forbidden_request", "dangerous", "يونيون باي يطلب كلمة المرور لإعادة تفعيل بطاقتك وتأكيد هويتك", min_verdict="block", expected_claimed="union_pay", required_evidence_any={"entity_policy_forbidden_union_pay", "danger_password_request"}),
    EntityCase(358, "safe_awareness", "safe", "يونيون باي: لا تشارك كلمة المرور أو بيانات بطاقتك مع أي جهة تدعي تمثيل الشبكة", sender_name="UnionPay", max_verdict="warn", expected_claimed="union_pay", forbidden_evidence={"entity_policy_forbidden_union_pay"}),
    EntityCase(359, "alias_substring", "safe", "تتنوع المشاريع الثقافية والفنية وتسهم في تعزيز الهوية الوطنية وصون التراث الإنساني المشترك", max_verdict="caution", forbidden_claimed={"union_pay"}),
    EntityCase(360, "sender_spoofing", "suspicious", "بطاقتك يونيون باي تحتاج تحديث بياناتك من الرابط https://unionpay-update.test", sender_name="UnionPay-Service", forbidden_sender={"union_pay"}, max_sender_trust="unknown"),

    # AV. Checkout.com
    EntityCase(361, "official_alignment", "safe", "Checkout.com: تم معالجة الدفعة بنجاح تفاصيل المعاملة على https://checkout.com", sender_name="Checkout", max_verdict="warn", expected_claimed="checkout_com", expected_domain="checkout_com", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(362, "mismatch_impersonation", "suspicious", "Checkout.com: مشكلة في معالجة دفعتك تحتاج تأكيداً من https://checkout-verify.test", min_verdict="caution", expected_claimed="checkout_com"),
    EntityCase(363, "forbidden_request", "dangerous", "تشيك أوت يطلب كلمة المرور لإعادة تفعيل حساب التاجر وإتمام الدفعات المعلقة", min_verdict="block", expected_claimed="checkout_com", required_evidence_any={"entity_policy_forbidden_checkout_com", "danger_password_request"}),
    EntityCase(364, "safe_awareness", "safe", "Checkout.com: لا يطلب منك مشاركة كلمة المرور أو بيانات بطاقتك عبر الرسائل النصية", sender_name="Checkout", max_verdict="warn", expected_claimed="checkout_com", forbidden_evidence={"entity_policy_forbidden_checkout_com"}),
    EntityCase(365, "alias_substring", "safe", "تتيح أنظمة المدفوعات الحديثة عمليات الشراء السريعة وتعزز تجربة المستخدم الرقمية", max_verdict="caution", forbidden_claimed={"checkout_com"}),
    EntityCase(366, "sender_spoofing", "suspicious", "دفعتك عبر تشيك أوت محتجزة تأكد من بياناتك على https://checkout-payment.test", sender_name="Checkout-Pay", forbidden_sender={"checkout_com"}, max_sender_trust="unknown"),

    # AW. Telr
    EntityCase(367, "official_alignment", "safe", "Telr: تم إتمام عملية الدفع بنجاح راجع تفاصيل معاملتك على https://telr.com", sender_name="Telr", max_verdict="warn", expected_claimed="telr", expected_domain="telr", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(368, "mismatch_impersonation", "suspicious", "Telr: دفعة معلقة تحتاج مراجعة سريعة أكد بياناتك من https://telr-secure.test", min_verdict="caution", expected_claimed="telr"),
    EntityCase(369, "forbidden_request", "dangerous", "تيلر يطلب كلمة المرور للتحقق من هوية التاجر وتأكيد الدفعات المعلقة", min_verdict="block", expected_claimed="telr", required_evidence_any={"entity_policy_forbidden_telr", "danger_password_request"}),
    EntityCase(370, "safe_awareness", "safe", "Telr: لا يطلب منك مشاركة كلمة المرور أو بيانات الدفع عبر الرسائل القصيرة", sender_name="Telr", max_verdict="warn", expected_claimed="telr", forbidden_evidence={"entity_policy_forbidden_telr"}),
    EntityCase(371, "alias_substring", "safe", "تقدم شركات معالجة الدفعات حلولاً متكاملة للتجار عبر الإنترنت في المنطقة", max_verdict="caution", forbidden_claimed={"telr"}),
    EntityCase(372, "sender_spoofing", "suspicious", "دفعتك عبر تيلر معلقة بسبب بيانات ناقصة أكد هويتك من https://telr-pay.test", sender_name="Telr-Alert", forbidden_sender={"telr"}, max_sender_trust="unknown"),

    # AX. HyperPay
    EntityCase(373, "official_alignment", "safe", "HyperPay: تم إتمام عملية الدفع بنجاح راجع تفاصيل معاملتك على https://hyperpay.com", sender_name="HyperPay", max_verdict="warn", expected_claimed="hyperpay", expected_domain="hyperpay", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(374, "mismatch_impersonation", "suspicious", "هايبر باي: دفعة في انتظار التأكيد راجع معلوماتك من https://hyperpay-verify.test", min_verdict="caution", expected_claimed="hyperpay"),
    EntityCase(375, "forbidden_request", "dangerous", "هايبر باي يطلب كلمة المرور للتحقق من هوية المستخدم وإتمام الدفعة المعلقة", min_verdict="block", expected_claimed="hyperpay", required_evidence_any={"entity_policy_forbidden_hyperpay", "danger_password_request"}),
    EntityCase(376, "safe_awareness", "safe", "HyperPay: لا يطلب منك إدخال كلمة المرور أو أرقام بطاقتك عبر الرسائل النصية", sender_name="HyperPay", max_verdict="warn", expected_claimed="hyperpay", forbidden_evidence={"entity_policy_forbidden_hyperpay"}),
    EntityCase(377, "alias_substring", "safe", "يتيح التعليم الإلكتروني فرص التعلم لشريحة واسعة من الطلاب في مختلف مناطق العالم الحديثة", max_verdict="caution", forbidden_claimed={"hyperpay"}),
    EntityCase(378, "sender_spoofing", "suspicious", "دفعتك من هايبر باي تحتاج مراجعة أكد بياناتك من https://hyperpay-confirm.test", sender_name="HyperPay-CS", forbidden_sender={"hyperpay"}, max_sender_trust="unknown"),

    # AY. Samsung Pay
    EntityCase(379, "official_alignment", "safe", "Samsung Pay: تم إتمام دفعتك بنجاح راجع تفاصيل المعاملة على https://samsung.com", sender_name="Samsung", max_verdict="warn", expected_claimed="samsung_pay", expected_domain="samsung_pay", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(380, "mismatch_impersonation", "suspicious", "Samsung Pay: محفظتك بحاجة لتحديث أكد بياناتك من https://samsung-pay-update.test", min_verdict="caution", expected_claimed="samsung_pay"),
    EntityCase(381, "forbidden_request", "dangerous", "سامسونج باي يطلب كلمة المرور لإعادة تفعيل المحفظة وتأكيد هويتك", min_verdict="block", expected_claimed="samsung_pay", required_evidence_any={"entity_policy_forbidden_samsung_pay", "danger_password_request"}),
    EntityCase(382, "safe_awareness", "safe", "Samsung Pay: لا يطلب منك إدخال كلمة المرور أو رمز التحقق عبر الرسائل النصية", sender_name="Samsung", max_verdict="warn", expected_claimed="samsung_pay", forbidden_evidence={"entity_policy_forbidden_samsung_pay"}),
    EntityCase(383, "alias_substring", "safe", "تتطور تقنيات الهواتف الذكية وتقدم تجربة مستخدم أكثر سلاسة وأماناً للجميع", max_verdict="caution", forbidden_claimed={"samsung_pay"}),
    EntityCase(384, "sender_spoofing", "suspicious", "محفظتك سامسونج باي تحتاج تأكيد بياناتك على الرابط https://samsung-pay-verify.test", sender_name="Samsung-Pay-Support", forbidden_sender={"samsung_pay"}, max_sender_trust="unknown"),

    # AZ. InDrive
    EntityCase(385, "official_alignment", "safe", "InDrive: رحلتك تم تأكيدها راجع التفاصيل على الرابط الرسمي https://indrive.com", sender_name="InDrive", max_verdict="warn", expected_claimed="indrive", expected_domain="indrive", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(386, "mismatch_impersonation", "suspicious", "InDrive: مشكلة في حسابك تحتاج مراجعة أكد بياناتك من https://indrive-verify.test", min_verdict="caution", expected_claimed="indrive"),
    EntityCase(387, "forbidden_request", "dangerous", "إن درايف يطلب كلمة المرور للتحقق من هوية السائق وإعادة تفعيل الحساب", min_verdict="block", expected_claimed="indrive", required_evidence_any={"entity_policy_forbidden_indrive", "danger_password_request"}),
    EntityCase(388, "safe_awareness", "safe", "InDrive: لا يطلب منك إدخال كلمة المرور أو بيانات بطاقتك عبر الرسائل القصيرة", sender_name="InDrive", max_verdict="warn", expected_claimed="indrive", forbidden_evidence={"entity_policy_forbidden_indrive"}),
    EntityCase(389, "alias_substring", "safe", "تتوفر خدمات النقل الذكي في معظم المدن الكبرى وتعتمد على التكنولوجيا الحديثة", max_verdict="caution", forbidden_claimed={"indrive"}),
    EntityCase(390, "sender_spoofing", "suspicious", "رحلتك من إن درايف تحتاج تأكيد بياناتك من https://indrive-account.test", sender_name="InDrive-Support", forbidden_sender={"indrive"}, max_sender_trust="unknown"),

    # BA. Yango
    EntityCase(391, "official_alignment", "safe", "Yango: رحلتك تم تأكيدها تتبع التفاصيل من الرابط الرسمي https://yango.com", sender_name="Yango", max_verdict="warn", expected_claimed="yango_jordan", expected_domain="yango_jordan", required_evidence_any={"entity_official_domain_alignment"}),
    EntityCase(392, "mismatch_impersonation", "suspicious", "Yango: حسابك بحاجة لمراجعة عاجلة أكد بياناتك من https://yango-verify.test", min_verdict="caution", expected_claimed="yango_jordan"),
    EntityCase(393, "forbidden_request", "dangerous", "يانغو يطلب كلمة المرور لإعادة تفعيل حساب السائق وتأكيد معلومات التسجيل", min_verdict="block", expected_claimed="yango_jordan", required_evidence_any={"entity_policy_forbidden_yango_jordan", "danger_password_request"}),
    EntityCase(394, "safe_awareness", "safe", "Yango: لا يطلب منك مشاركة كلمة المرور أو بيانات بطاقتك عبر الرسائل النصية", sender_name="Yango", max_verdict="warn", expected_claimed="yango_jordan", forbidden_evidence={"entity_policy_forbidden_yango_jordan"}),
    EntityCase(395, "alias_substring", "safe", "تعتمد مدن الشرق الأوسط على خدمات التنقل الحضري لتيسير التنقل بين المناطق", max_verdict="caution", forbidden_claimed={"yango_jordan"}),
    EntityCase(396, "sender_spoofing", "suspicious", "رحلتك مع يانغو تحتاج تحديث بيانات حسابك من https://yango-account.test", sender_name="Yango-Service", forbidden_sender={"yango_jordan"}, max_sender_trust="unknown"),
]


_PHASE_7_5_ENTITY_CASE_SPECS = [
    {
        "id": "king_abdullah_university_hospital",
        "label": "King Abdullah University Hospital",
        "domain": "kauh.edu.jo",
        "fake": "kauh-portal",
        "spoof": "KAUH-Portal",
        "topic": "موعد طبي",
        "nonmatch": "Research teams study hospital appointment workflows without naming any institution.",
        "expect_domain": True,
    },
    {
        "id": "prince_hamzah_hospital",
        "label": "Prince Hamzah Hospital",
        "domain": "moh.gov.jo",
        "fake": "princehamzah-results",
        "spoof": "PrinceHamzah-Alert",
        "topic": "نتائج مختبر",
        "nonmatch": "The prince attended a public health lecture about hospital quality.",
        "expect_domain": False,
    },
    {
        "id": "islamic_hospital_jo",
        "label": "Islamic Hospital",
        "domain": "islamic-hospital.org",
        "fake": "islamic-hospital-bill",
        "spoof": "IslamicHospital-Notify",
        "topic": "فاتورة طبية",
        "nonmatch": "Islamic art history is discussed in a university seminar.",
        "expect_domain": True,
    },
    {
        "id": "jordan_hospital",
        "label": "Jordan Hospital",
        "domain": "jordan-hospital.com",
        "fake": "jordan-hospital-file",
        "spoof": "JordanHospital-Service",
        "topic": "ملف مريض",
        "nonmatch": "Jordan hospitality students prepared a public service presentation.",
        "expect_domain": True,
    },
    {
        "id": "amman_hospital",
        "label": "Amman Hospital",
        "domain": "ammanhospital.com",
        "fake": "amman-hospital-login",
        "spoof": "AmmanHospital-Care",
        "topic": "بوابة المرضى",
        "nonmatch": "Amman hospitality businesses joined a tourism workshop.",
        "expect_domain": True,
    },
    {
        "id": "al_al_bayt_university",
        "label": "Al al-Bayt University",
        "domain": "aabu.edu.jo",
        "fake": "aabu-student",
        "spoof": "AABU-Portal",
        "topic": "قبول جامعي",
        "nonmatch": "The phrase aalbaytlegacy appears in a book catalogue, not a university notice.",
        "expect_domain": True,
    },
    {
        "id": "tafila_technical_university",
        "label": "Tafila Technical University",
        "domain": "ttu.edu.jo",
        "fake": "ttu-registration",
        "spoof": "TTU-Register",
        "topic": "تسجيل مواد",
        "nonmatch": "A rattus species note in a biology article should not match TTU.",
        "expect_domain": True,
    },
    {
        "id": "al_hussein_bin_talal_university",
        "label": "Al-Hussein Bin Talal University",
        "domain": "ahu.edu.jo",
        "fake": "ahu-admission",
        "spoof": "AHU-Admissions",
        "topic": "نتيجة قبول",
        "nonmatch": "The word yahoo appears in a casual technology article.",
        "expect_domain": True,
    },
    {
        "id": "al_hussein_technical_university",
        "label": "Al Hussein Technical University",
        "domain": "htu.edu.jo",
        "fake": "htu-exam",
        "spoof": "HTU-Exam",
        "topic": "بوابة امتحانات",
        "nonmatch": "The token shtutdown is unrelated to HTU and should not match.",
        "expect_domain": True,
    },
    {
        "id": "amman_arab_university",
        "label": "Amman Arab University",
        "domain": "aau.edu.jo",
        "fake": "aau-tuition",
        "spoof": "AAU-Pay",
        "topic": "رسوم جامعية",
        "nonmatch": "An aaudio file update should not be treated as a university claim.",
        "expect_domain": True,
    },
    {
        "id": "zarqa_university",
        "label": "Zarqa University",
        "domain": "zu.edu.jo",
        "fake": "zu-student",
        "spoof": "ZU-Portal",
        "topic": "بوابة طالب",
        "nonmatch": "The word azure appears in a design note and should not match ZU.",
        "expect_domain": True,
    },
    {
        "id": "middle_east_university_jo",
        "label": "Middle East University",
        "domain": "meu.edu.jo",
        "fake": "meu-login",
        "spoof": "MEU-Student",
        "topic": "خدمات الطالب",
        "nonmatch": "A museum guide about the Middle East does not claim a university.",
        "expect_domain": True,
    },
    {
        "id": "al_ahliyya_amman_university",
        "label": "Al-Ahliyya Amman University",
        "domain": "ammanu.edu.jo",
        "fake": "ammanu-fees",
        "spoof": "AAU-Amman-Fees",
        "topic": "دفع رسوم",
        "nonmatch": "An ammanual draft about campus design should not match AmmanU.",
        "expect_domain": True,
    },
    {
        "id": "jerash_university",
        "label": "Jerash University",
        "domain": "jpu.edu.jo",
        "fake": "jpu-exam",
        "spoof": "JPU-Exam",
        "topic": "نتيجة امتحان",
        "nonmatch": "The word jpegupdate appears in a file note and should not match JPU.",
        "expect_domain": True,
    },
    {
        "id": "isra_university_jo",
        "label": "Isra University",
        "domain": "iu.edu.jo",
        "fake": "iu-admission",
        "spoof": "IsraU-Portal",
        "topic": "طلب قبول",
        "nonmatch": "An insurance update mentions no university or student portal.",
        "expect_domain": True,
    },
    {
        "id": "ministry_of_transport_jo",
        "label": "Ministry of Transport Jordan",
        "domain": "mot.gov.jo",
        "fake": "mot-service",
        "spoof": "MOT-Service",
        "topic": "خدمة نقل",
        "nonmatch": "A motorbike safety article should not match any transport ministry entity.",
        "expect_domain": True,
    },
    {
        "id": "ministry_of_tourism_antiquities_jo",
        "label": "Ministry of Tourism and Antiquities Jordan",
        "domain": "mota.gov.jo",
        "fake": "mota-fee",
        "spoof": "MOTA-Service",
        "topic": "تصريح سياحي",
        "nonmatch": "A motivational training message should not match any tourism ministry entity.",
        "expect_domain": True,
    },
    {
        "id": "department_of_lands_survey_jo",
        "label": "Department of Lands and Survey",
        "domain": "dls.gov.jo",
        "fake": "dls-document",
        "spoof": "DLS-Docs",
        "topic": "وثيقة أرض",
        "nonmatch": "A landslide report is not an official property department message.",
        "expect_domain": True,
    },
    {
        "id": "smsa_express_jordan",
        "label": "SMSA Express",
        "domain": "smsaexpress.com",
        "fake": "smsa-delivery",
        "spoof": "SMSA-Delivery",
        "topic": "شحنة معلقة",
        "nonmatch": "An smsanalysis note should not match any courier company.",
        "expect_domain": True,
    },
]


def _append_phase_7_5_entity_cases() -> None:
    next_id = max(case.case_id for case in CASES) + 1
    for spec in _PHASE_7_5_ENTITY_CASE_SPECS:
        eid = spec["id"]
        label = spec["label"]
        domain = spec["domain"]
        fake = spec["fake"]
        domain_kwargs = (
            {"expected_domain": eid, "required_evidence_any": {"entity_official_domain_alignment"}}
            if spec.get("expect_domain", True)
            else {}
        )
        CASES.extend(
            [
                EntityCase(
                    next_id,
                    "phase_7_5_official_alignment",
                    "safe",
                    f"{label}: إشعار رسمي حول {spec['topic']} بدون طلب بيانات https://{domain}",
                    max_verdict="warn",
                    expected_claimed=eid,
                    **domain_kwargs,
                ),
                EntityCase(
                    next_id + 1,
                    "phase_7_5_mismatch_impersonation",
                    "suspicious",
                    f"{label}: يجب تحديث بيانات الحساب فوراً عبر الرابط https://{fake}.test",
                    min_verdict="caution",
                    expected_claimed=eid,
                ),
                EntityCase(
                    next_id + 2,
                    "phase_7_5_forbidden_request",
                    "dangerous",
                    f"{label} يطلب كلمة المرور ورمز التحقق لتأكيد {spec['topic']}",
                    min_verdict="warn",
                    expected_claimed=eid,
                    required_evidence_any={f"entity_policy_forbidden_{eid}", "danger_password_request"},
                ),
                EntityCase(
                    next_id + 3,
                    "phase_7_5_safe_awareness",
                    "safe",
                    f"{label}: لا تشارك كلمة المرور أو رمز التحقق أو CVV عبر الرسائل أو روابط غير رسمية",
                    max_verdict="warn",
                    expected_claimed=eid,
                    forbidden_evidence={f"entity_policy_forbidden_{eid}", "danger_password_request"},
                ),
                EntityCase(
                    next_id + 4,
                    "phase_7_5_alias_non_overmatch",
                    "safe",
                    spec["nonmatch"],
                    max_verdict="caution",
                    forbidden_claimed={eid},
                    forbidden_evidence={f"entity_policy_forbidden_{eid}"},
                ),
                EntityCase(
                    next_id + 5,
                    "phase_7_5_sender_spoofing",
                    "suspicious",
                    f"{label}: {spec['topic']} يحتاج مراجعة بيانات من https://{fake}-support.test",
                    sender_name=spec["spoof"],
                    min_verdict="caution",
                    expected_claimed=eid,
                    forbidden_sender={eid},
                    max_sender_trust="unknown",
                ),
            ]
        )
        next_id += 6


_append_phase_7_5_entity_cases()



_PHASE_7_6_ENTITY_CASE_SPECS = [
    {
        "id": "ebay",
        "label": "eBay",
        "domain": "ebay.com",
        "fake": "ebay-refund",
        "spoof": "eBay-Verify",
        "topic": "refund request",
        "request": "password",
        "nonmatch": "A marketplace-neutral game note mentions prebattle strategy only.",
        "expect_domain": True,
    },
    {
        "id": "etsy",
        "label": "Etsy",
        "domain": "etsy.com",
        "fake": "etsy-payment",
        "spoof": "Etsy-Support",
        "topic": "shop confirmation",
        "request": "password",
        "nonmatch": "A design note discusses handmade style without naming any marketplace.",
        "expect_domain": True,
    },
    {
        "id": "discover_network",
        "label": "Discover Network",
        "domain": "discoverglobalnetwork.com",
        "fake": "discover-card-verify",
        "spoof": "Discover-Card",
        "topic": "card verification",
        "request": "card",
        "nonmatch": "Students study graph theory in class without naming any card network.",
        "expect_domain": True,
    },
    {
        "id": "apple_pay",
        "label": "Apple Pay",
        "domain": "apple.com",
        "fake": "apple-pay-wallet",
        "spoof": "ApplePay-Wallet",
        "topic": "digital wallet",
        "request": "wallet",
        "nonmatch": "A recipe discusses fruit pie and household budgeting with no wallet service.",
        "expect_domain": False,
    },
    {
        "id": "google_wallet",
        "label": "Google Wallet",
        "domain": "wallet.google",
        "fake": "google-wallet-reactivate",
        "spoof": "GWallet-Verify",
        "topic": "wallet reactivation",
        "request": "wallet",
        "nonmatch": "A leather accessory review mentions no digital wallet account.",
        "expect_domain": True,
    },
    {
        "id": "bolt_ride_hailing",
        "label": "Bolt",
        "domain": "bolt.eu",
        "fake": "bolt-ride-account",
        "spoof": "Bolt-Verify",
        "topic": "ride account",
        "request": "password",
        "nonmatch": "A weather article describes lightning over the city with no ride service.",
        "expect_domain": True,
    },
    {
        "id": "damamax_jordan",
        "label": "DamaMax",
        "domain": "damamax.jo",
        "fake": "damamax-fiber",
        "spoof": "DamaMax-Fiber",
        "topic": "fiber subscription",
        "request": "password",
        "nonmatch": "A lab report discusses maximum throughput with no internet provider.",
        "expect_domain": True,
    },
    {
        "id": "vtel_jordan",
        "label": "VTEL Jordan",
        "domain": "vtel.jo",
        "fake": "vtel-account",
        "spoof": "VTEL-Support",
        "topic": "internet account",
        "request": "password",
        "nonmatch": "A debug trace contains the token avtellog only.",
        "expect_domain": True,
    },
    {
        "id": "snapchat",
        "label": "Snapchat",
        "domain": "snapchat.com",
        "fake": "snapchat-recovery",
        "spoof": "Snapchat-Code",
        "topic": "account recovery",
        "request": "otp",
        "nonmatch": "????? ????? ?? ????? ????? ????? ??? ?? ???? ????????.",
        "expect_domain": True,
    },
    {
        "id": "linkedin",
        "label": "LinkedIn",
        "domain": "linkedin.com",
        "fake": "linkedin-premium-verify",
        "spoof": "LinkedIn-Jobs",
        "topic": "professional account",
        "request": "password",
        "nonmatch": "A programming lesson discusses linked lists only.",
        "expect_domain": True,
    },
    {
        "id": "youtube",
        "label": "YouTube",
        "domain": "youtube.com",
        "fake": "youtube-studio-appeal",
        "spoof": "YouTube-Studio",
        "topic": "creator channel",
        "request": "recovery",
        "nonmatch": "A hardware note describes a U shaped bracket only.",
        "expect_domain": True,
    },
    {
        "id": "prime_video",
        "label": "Prime Video",
        "domain": "primevideo.com",
        "fake": "prime-video-renewal",
        "spoof": "PrimeVideo-Billing",
        "topic": "subscription renewal",
        "request": "card",
        "nonmatch": "A math lesson discusses prime numbers and classroom recordings only.",
        "expect_domain": True,
    },
    {
        "id": "apple_tv_plus",
        "label": "Apple TV+",
        "domain": "tv.apple.com",
        "fake": "apple-tv-renewal",
        "spoof": "AppleTV-Plus",
        "topic": "streaming subscription",
        "request": "card",
        "nonmatch": "A television repair note mentions a colored screen only.",
        "expect_domain": True,
    },
    {
        "id": "starzplay",
        "label": "STARZPLAY",
        "domain": "starzplay.com",
        "fake": "starzplay-billing",
        "spoof": "STARZPLAY-Pay",
        "topic": "subscription billing",
        "request": "card",
        "nonmatch": "A sample code variable describes a media player only.",
        "expect_domain": True,
    },
    {
        "id": "nepco_jo",
        "label": "NEPCO",
        "domain": "nepco.com.jo",
        "fake": "nepco-bill",
        "spoof": "NEPCO-Bill",
        "topic": "electricity notice",
        "request": "card",
        "nonmatch": "A lab file contains the token pinepcoanalysis only.",
        "expect_domain": True,
    },
    {
        "id": "samra_electric_power_company",
        "label": "Samra Electric Power Company",
        "domain": "sepco.com.jo",
        "fake": "sepco-supplier",
        "spoof": "SEPCO-Pay",
        "topic": "electricity service",
        "request": "card",
        "nonmatch": "A programming note contains the token parsepcode only.",
        "expect_domain": True,
    },
    {
        "id": "aes_jordan",
        "label": "AES Jordan",
        "domain": "aesjordan.com.jo",
        "fake": "aes-jordan-invoice",
        "spoof": "AESJordan-Service",
        "topic": "service invoice",
        "request": "card",
        "nonmatch": "A design workshop discusses aesthetics only.",
        "expect_domain": True,
    },
]


def _phase_7_6_forbidden_text(label: str, topic: str, request: str) -> tuple[str, set[str]]:
    if request == "card":
        return (
            f"{label} asks you to enter card number and CVV to confirm {topic}",
            {"danger_card_request"},
        )
    if request == "otp":
        return (
            f"{label} asks you to send the OTP code to confirm {topic}",
            {"danger_otp_request"},
        )
    if request == "recovery":
        return (
            f"{label} asks you to send the recovery code and OTP code to confirm {topic}",
            {"danger_otp_request", "credential_request"},
        )
    if request == "wallet":
        return (
            f"{label} asks for your password and OTP code to reactivate {topic}",
            {"danger_password_request", "danger_otp_request"},
        )
    return (
        f"{label} asks for your password and OTP code to confirm {topic}",
        {"danger_password_request", "danger_otp_request"},
    )


def _append_phase_7_6_entity_cases() -> None:
    next_id = max(case.case_id for case in CASES) + 1
    for spec in _PHASE_7_6_ENTITY_CASE_SPECS:
        eid = spec["id"]
        label = spec["label"]
        domain = spec["domain"]
        fake = spec["fake"]
        forbidden_text, trigger_evidence = _phase_7_6_forbidden_text(label, spec["topic"], spec["request"])
        official_kwargs = {}
        if spec.get("expect_domain", True):
            official_kwargs["expected_domain"] = eid
        CASES.extend(
            [
                EntityCase(
                    next_id,
                    "phase_7_6_official_alignment",
                    "safe",
                    f"{label}: official service notice about {spec['topic']} with no data request https://{domain}",
                    max_verdict="warn",
                    expected_claimed=(eid if spec.get("expect_domain", True) else None),
                    **official_kwargs,
                ),
                EntityCase(
                    next_id + 1,
                    "phase_7_6_mismatch_impersonation",
                    "suspicious",
                    f"{label}: account update required now at https://{fake}.test",
                    min_verdict="caution",
                    expected_claimed=eid,
                    required_evidence_any={"url_brand_impersonation", "url_brand_phishing_combo", "url_claimed_brand_domain_mismatch", "url_brand_suspicious_tld"},
                ),
                EntityCase(
                    next_id + 2,
                    "phase_7_6_forbidden_request",
                    "dangerous",
                    forbidden_text,
                    min_verdict="warn",
                    expected_claimed=eid,
                    required_evidence_any={f"entity_policy_forbidden_{eid}", *trigger_evidence},
                ),
                EntityCase(
                    next_id + 3,
                    "phase_7_6_safe_awareness",
                    "safe",
                    f"{label}: does not ask for your password, OTP, CVV, or card details through messages; do not share them",
                    max_verdict="warn",
                    expected_claimed=eid,
                    forbidden_evidence={f"entity_policy_forbidden_{eid}", "danger_password_request", "danger_otp_request", "danger_card_request"},
                ),
                EntityCase(
                    next_id + 4,
                    "phase_7_6_alias_non_overmatch",
                    "safe",
                    spec["nonmatch"],
                    max_verdict="caution",
                    forbidden_claimed={eid},
                    forbidden_evidence={f"entity_policy_forbidden_{eid}"},
                ),
                EntityCase(
                    next_id + 5,
                    "phase_7_6_sender_spoofing",
                    "suspicious",
                    f"{label}: {spec['topic']} requires account review at https://{fake}-support.test",
                    sender_name=spec["spoof"],
                    min_verdict="caution",
                    expected_claimed=eid,
                    forbidden_sender={eid},
                    max_sender_trust="unknown",
                ),
            ]
        )
        next_id += 6


_append_phase_7_6_entity_cases()


def _rank(verdict: str) -> int:
    return _VERDICT_RANK.get(verdict, 99)


def _risk_class(verdict: str) -> str:
    if verdict == "block":
        return "dangerous"
    if verdict in {"warn", "caution"}:
        return "suspicious"
    return "safe"


def _entity_id(entity: dict[str, Any] | None) -> str:
    return (entity or {}).get("entity_id") or "-"


def _top_evidence_ids(result: Any) -> list[str]:
    ranked = sorted(
        result.evidence,
        key=lambda ev: (ev.score_delta, ev.severity == "critical"),
        reverse=True,
    )
    return [ev.id for ev in ranked[:6]]


def _policy_trace_summary(result: Any) -> str:
    trace = list(getattr(result, "policy_trace", []) or [])
    if not trace:
        return "-"
    important = [
        item
        for item in trace
        if "block" in item.lower()
        or "cap" in item.lower()
        or "allow" in item.lower()
        or "warn" in item.lower()
    ]
    return " | ".join((important or trace)[:3])


def _load_registry() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _collect_values(entities: list[dict[str, Any]], field: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for entity in entities:
        for value in entity.get(field, []) or []:
            rows.append((entity["id"], entity.get("entity_type", ""), str(value)))
    return rows


def _duplicates_by_norm(rows: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for entity_id, _entity_type, value in rows:
        key = _norm(value)
        if key:
            grouped[key].append((entity_id, value))
    out = []
    for key, values in grouped.items():
        entity_ids = sorted({entity_id for entity_id, _value in values})
        if len(entity_ids) > 1:
            out.append({"key": key, "entities": entity_ids, "values": values})
    return sorted(out, key=lambda item: (len(item["entities"]), item["key"]), reverse=True)


def _substring_aliases(rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    normalized = [(entity_id, value, _norm(value)) for entity_id, _typ, value in rows]
    out: list[tuple[str, str, str, str]] = []
    for entity_a, value_a, key_a in normalized:
        if len(key_a) < 3:
            continue
        for entity_b, value_b, key_b in normalized:
            if entity_a == entity_b and value_a == value_b:
                continue
            if len(key_b) <= len(key_a):
                continue
            if key_a in key_b:
                out.append((entity_a, value_a, entity_b, value_b))
                break
    return out


def _normalization_collisions(rows: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for entity_id, _typ, value in rows:
        key = _norm(value)
        if key:
            grouped[key].append((entity_id, value))
    collisions = []
    for key, values in grouped.items():
        raw_values = {value for _entity_id, value in values}
        entity_ids = {entity_id for entity_id, _value in values}
        if len(raw_values) > 1:
            collisions.append({
                "key": key,
                "entities": sorted(entity_ids),
                "values": sorted(raw_values),
            })
    return sorted(collisions, key=lambda item: (len(item["values"]), item["key"]), reverse=True)


def _domain_audit(entities: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _collect_values(entities, "official_domains")
    by_norm: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for entity_id, _typ, domain in rows:
        by_norm[_strip_domain(domain)].append((entity_id, domain))

    duplicate_domains = [
        {"domain": domain, "entities": sorted({eid for eid, _raw in values}), "values": values}
        for domain, values in by_norm.items()
        if domain and len({eid for eid, _raw in values}) > 1
    ]
    domains = [domain for _eid, _typ, domain in rows]
    stripped_domains = [_strip_domain(domain) for domain in domains]
    suspiciously_broad = [
        domain for domain in stripped_domains
        if domain.count(".") == 0 or domain in {"com", "jo", "gov.jo", "org", "net"}
    ]
    www_pairs = [
        domain for domain in stripped_domains
        if f"www.{domain}" in {d.lower() for d in domains}
    ]
    return {
        "duplicate_domains": sorted(duplicate_domains, key=lambda item: item["domain"]),
        "missing_domains": [e["id"] for e in entities if not e.get("official_domains")],
        "suspiciously_broad": sorted(set(suspiciously_broad)),
        "with_protocol": [d for d in domains if "://" in d],
        "with_path": [d for d in domains if "/" in d.strip().replace("://", "")],
        "with_uppercase": [d for d in domains if d != d.lower()],
        "www_duplicates": sorted(set(www_pairs)),
        "subdomain_risks": sorted(
            {
                domain
                for domain in stripped_domains
                if domain.count(".") >= 2 and not domain.endswith(".gov.jo")
            }
        ),
    }


def _runtime_usage_gaps(allowed_types: set[str]) -> list[str]:
    py_files = list((BACKEND_DIR / "app").rglob("*.py"))
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in py_files
        if path.name != "entity_registry.py"
    )
    gaps = []
    if "allowed_message_types" not in runtime_text:
        gaps.append("allowed_message_types_not_used_by_runtime_logic")
    for allowed in sorted(allowed_types):
        if allowed and allowed not in runtime_text:
            gaps.append(f"allowed_message_type_unused:{allowed}")
    return gaps


def _registry_brand_gap(entities: list[dict[str, Any]]) -> dict[str, Any]:
    known = set(_KNOWN_BRANDS)
    known_domains = {
        _strip_domain(domain)
        for domains in _KNOWN_BRANDS.values()
        for domain in domains
    }
    bridge_count = registry_brand_candidates_count()
    missing_by_domain = []
    for entity in entities:
        domains = {_strip_domain(domain) for domain in entity.get("official_domains", [])}
        if domains and not domains.intersection(known_domains):
            missing_by_domain.append(entity["id"])
    return {
        "known_brand_count": len(known),
        "registry_url_brand_bridge": "implemented" if bridge_count else "not_implemented",
        "registry_entities_available_to_url_brand_detection": bridge_count,
        "registry_brand_candidates_count": bridge_count,
        "registry_entities_not_covered_by_known_brand_domains": sorted(missing_by_domain),
    }


def registry_quality_audit() -> dict[str, Any]:
    raw = _load_registry()
    registry = get_registry()
    entities = raw.get("entities", [])
    alias_rows = _collect_values(entities, "aliases")
    sender_rows = _collect_values(entities, "official_sender_names")
    forbidden_rows = _collect_values(entities, "forbidden_requests")
    allowed_rows = _collect_values(entities, "allowed_message_types")
    domain = _domain_audit(entities)

    alias_values = [value for _eid, _typ, value in alias_rows]
    sender_values = [value for _eid, _typ, value in sender_rows]
    forbidden_values = {value for _eid, _typ, value in forbidden_rows}
    allowed_values = {value for _eid, _typ, value in allowed_rows}

    by_entity_type = Counter(e.get("entity_type", "unknown") for e in entities)
    by_country = Counter(e.get("country", "unknown") for e in entities)
    aliases_shorter_than_3 = [
        (eid, value) for eid, _typ, value in alias_rows if len(_norm(value)) < 3
    ]
    arabic_aliases_shorter_than_3 = [
        (eid, value)
        for eid, _typ, value in alias_rows
        if 0 < len(_AR_LETTERS_RE.findall(value)) < 3
    ]
    common_alias_risks = [
        (eid, value)
        for eid, _typ, value in alias_rows
        if _norm(value) in {_norm(v) for v in _COMMON_ALIAS_RISK}
    ]
    sender_short = [
        (eid, value) for eid, _typ, value in sender_rows if len(_norm(value)) < 3
    ]
    sender_overmatch = [
        (eid, value)
        for eid, _typ, value in sender_rows
        if _norm(value) in _GENERIC_SENDER_WORDS or len(_norm(value)) == 3
    ]

    entity_types_empty_forbidden = sorted({
        e.get("entity_type", "unknown")
        for e in entities
        if not e.get("forbidden_requests")
    })
    entity_types_empty_allowed = sorted({
        e.get("entity_type", "unknown")
        for e in entities
        if not e.get("allowed_message_types")
    })
    undercovered_entity_types = sorted([
        typ for typ, count in by_entity_type.items()
        if count < 3
    ])

    unmapped_forbidden = sorted(value for value in forbidden_values if value not in _FORBIDDEN_TO_FLAG)
    runtime_gaps = _runtime_usage_gaps(allowed_values)

    return {
        "dataset_version": raw.get("dataset_version", "unknown"),
        "entity_count": len(entities),
        "count_by_country": dict(sorted(by_country.items())),
        "count_by_entity_type": dict(sorted(by_entity_type.items())),
        "alias_count": len(alias_rows),
        "official_domain_count": sum(len(e.get("official_domains", [])) for e in entities),
        "official_sender_count": len(sender_rows),
        "forbidden_request_count": len(forbidden_rows),
        "allowed_message_type_count": len(allowed_rows),
        "aliases_shorter_than_3": aliases_shorter_than_3,
        "arabic_aliases_shorter_than_3": arabic_aliases_shorter_than_3,
        "common_alias_risks": common_alias_risks,
        "duplicate_aliases": _duplicates_by_norm(alias_rows),
        "alias_substrings": _substring_aliases(alias_rows),
        "alias_normalization_collisions": _normalization_collisions(alias_rows),
        "domain": domain,
        "duplicate_domain_policy": (
            "implemented"
            if hasattr(registry, "find_entities_by_domain")
            else "not_implemented"
        ),
        "duplicate_senders": _duplicates_by_norm(sender_rows),
        "sender_shorter_than_3": sender_short,
        "sender_overmatch_risks": sender_overmatch,
        "sender_normalization_collisions": _normalization_collisions(sender_rows),
        "sender_generic_words": [
            (eid, value)
            for eid, _typ, value in sender_rows
            if _norm(value) in _GENERIC_SENDER_WORDS
        ],
        "forbidden_values": sorted(forbidden_values),
        "unmapped_forbidden_requests": unmapped_forbidden,
        "entity_types_empty_forbidden": entity_types_empty_forbidden,
        "allowed_message_types": sorted(allowed_values),
        "entity_types_empty_allowed": entity_types_empty_allowed,
        "runtime_gaps": runtime_gaps,
        "undercovered_entity_types": undercovered_entity_types,
        "registry_brand_gap": _registry_brand_gap(entities),
    }


def _trust_rank(trust: str) -> int:
    return {"unknown": 0, "known": 1, "trusted": 2, "suspicious": -1}.get(trust, 0)


def _run_case(case: EntityCase) -> tuple[dict[str, Any], list[str]]:
    result = _SVC.analyze_full(
        text=case.text,
        sender=case.sender,
        sender_name=case.sender_name,
        extra_urls=case.extra_urls,
    )
    entity_intel = result.entity_intelligence or {}
    evidence_ids = {ev.id for ev in result.evidence}
    trace = set(result.policy_trace or [])
    claimed = _entity_id(entity_intel.get("claimed_entity"))
    sender_entity = _entity_id(entity_intel.get("sender_entity"))
    domain_entity = _entity_id(entity_intel.get("domain_entity"))
    url_entity = domain_entity
    top_ids = _top_evidence_ids(result)

    row = {
        "case_id": case.case_id,
        "family": case.family,
        "expected": case.expected,
        "score": result.risk_score,
        "class": _risk_class(result.verdict),
        "verdict": result.verdict,
        "claimed_entity": claimed,
        "sender_entity": sender_entity,
        "url_entity": url_entity,
        "top_evidence_ids": top_ids,
        "policy_trace_summary": _policy_trace_summary(result),
        "intent": result.message_intent,
        "category": result.message_category,
        "sender_trust": result.sender_assessment.trust_level,
    }

    issues: list[str] = []
    if case.min_verdict and _rank(result.verdict) < _rank(case.min_verdict):
        issues.append(f"VERDICT_BELOW_MIN({result.verdict}<{case.min_verdict})")
    if case.max_verdict and _rank(result.verdict) > _rank(case.max_verdict):
        issues.append(f"VERDICT_ABOVE_MAX({result.verdict}>{case.max_verdict})")
    if case.expected_claimed and claimed != case.expected_claimed:
        issues.append(f"CLAIMED_ENTITY({claimed}!={case.expected_claimed})")
    if case.expected_sender and sender_entity != case.expected_sender:
        issues.append(f"SENDER_ENTITY({sender_entity}!={case.expected_sender})")
    if case.expected_domain and domain_entity != case.expected_domain:
        issues.append(f"URL_ENTITY({domain_entity}!={case.expected_domain})")
    if claimed in case.forbidden_claimed:
        issues.append(f"FORBIDDEN_CLAIMED_ENTITY({claimed})")
    if sender_entity in case.forbidden_sender:
        issues.append(f"FORBIDDEN_SENDER_ENTITY({sender_entity})")
    if domain_entity in case.forbidden_domain:
        issues.append(f"FORBIDDEN_URL_ENTITY({domain_entity})")
    if case.required_evidence_any and not (case.required_evidence_any & evidence_ids):
        issues.append(f"MISSING_ANY_EVIDENCE({sorted(case.required_evidence_any)})")
    forbidden_evidence = case.forbidden_evidence & evidence_ids
    if forbidden_evidence:
        issues.append(f"FORBIDDEN_EVIDENCE({sorted(forbidden_evidence)})")
    if case.required_policy_trace_any and not (case.required_policy_trace_any & trace):
        issues.append(f"MISSING_POLICY_TRACE({sorted(case.required_policy_trace_any)})")
    if case.max_sender_trust and _trust_rank(result.sender_assessment.trust_level) > _trust_rank(case.max_sender_trust):
        issues.append(f"SENDER_TRUST_TOO_HIGH({result.sender_assessment.trust_level}>{case.max_sender_trust})")

    return row, issues


def _run_regression_script(script_name: str) -> str:
    script_path = BACKEND_DIR / "scripts" / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return "PASS" if result.returncode == 0 else "FAIL"


def _print_audit(audit: dict[str, Any]) -> None:
    print("Registry quality audit:")
    print(f"  dataset_version={audit['dataset_version']}")
    print(f"  total_entities={audit['entity_count']}")
    print("  count_by_country=" + ", ".join(f"{k}:{v}" for k, v in audit["count_by_country"].items()))
    print("  count_by_entity_type=" + ", ".join(f"{k}:{v}" for k, v in audit["count_by_entity_type"].items()))
    print(f"  total_aliases={audit['alias_count']}")
    print(f"  total_official_domains={audit['official_domain_count']}")
    print(f"  total_official_sender_names={audit['official_sender_count']}")
    print(f"  total_forbidden_requests={audit['forbidden_request_count']}")
    print(f"  total_allowed_message_types={audit['allowed_message_type_count']}")
    print("Alias quality:")
    print(f"  aliases_shorter_than_3={len(audit['aliases_shorter_than_3'])}")
    print(f"  arabic_aliases_shorter_than_3={len(audit['arabic_aliases_shorter_than_3'])}")
    print(f"  common_alias_risks={len(audit['common_alias_risks'])}")
    print(f"  duplicate_alias_count={len(audit['duplicate_aliases'])}")
    print(f"  alias_substring_risks={len(audit['alias_substrings'])}")
    print(f"  alias_normalization_collisions={len(audit['alias_normalization_collisions'])}")
    print("Domain quality:")
    print(f"  duplicate_domain_count={len(audit['domain']['duplicate_domains'])}")
    print(f"  duplicate_domain_policy={audit['duplicate_domain_policy']}")
    print("  duplicate_domain_groups=" + (
        "; ".join(
            f"{item['domain']}=>{','.join(item['entities'])}"
            for item in audit["domain"]["duplicate_domains"]
        )
        or "none"
    ))
    print(f"  missing_domains={len(audit['domain']['missing_domains'])}")
    print(f"  suspiciously_broad_domains={len(audit['domain']['suspiciously_broad'])}")
    print(f"  domains_with_protocol={len(audit['domain']['with_protocol'])}")
    print(f"  domains_with_path={len(audit['domain']['with_path'])}")
    print(f"  domains_with_uppercase={len(audit['domain']['with_uppercase'])}")
    print(f"  www_duplicate_risks={len(audit['domain']['www_duplicates'])}")
    print(f"  subdomain_handling_risks={len(audit['domain']['subdomain_risks'])}")
    print("Sender quality:")
    print(f"  duplicate_sender_count={len(audit['duplicate_senders'])}")
    print(f"  sender_names_shorter_than_3={len(audit['sender_shorter_than_3'])}")
    print(f"  sender_overmatch_risks={len(audit['sender_overmatch_risks'])}")
    print(f"  sender_normalization_collisions={len(audit['sender_normalization_collisions'])}")
    print(f"  sender_generic_words={len(audit['sender_generic_words'])}")
    print("Forbidden request quality:")
    print("  values=" + ", ".join(audit["forbidden_values"]))
    print("  unmapped_forbidden_requests=" + (", ".join(audit["unmapped_forbidden_requests"]) or "none"))
    print("  entity_types_empty_forbidden=" + (", ".join(audit["entity_types_empty_forbidden"]) or "none"))
    print("Allowed message type quality:")
    print("  values=" + ", ".join(audit["allowed_message_types"]))
    print("  entity_types_empty_allowed=" + (", ".join(audit["entity_types_empty_allowed"]) or "none"))
    print("  allowed_message_types_runtime_gaps=" + str(len(audit["runtime_gaps"])))
    print("Registry vs URL brand gap:")
    print(f"  known_brand_count={audit['registry_brand_gap']['known_brand_count']}")
    print(f"  registry_url_brand_bridge={audit['registry_brand_gap']['registry_url_brand_bridge']}")
    print(
        "  registry_entities_available_to_url_brand_detection="
        f"{audit['registry_brand_gap']['registry_entities_available_to_url_brand_detection']}"
    )
    print(f"  registry_brand_candidates_count={audit['registry_brand_gap']['registry_brand_candidates_count']}")
    print(
        "  registry_entities_not_covered_by_known_brand_domains="
        f"{len(audit['registry_brand_gap']['registry_entities_not_covered_by_known_brand_domains'])}"
    )
    print("Top 10 alias risks:")
    alias_risks = audit["common_alias_risks"][:10]
    for entity_id, value in alias_risks:
        print(f"  {entity_id}: {value}")
    if not alias_risks:
        print("  none")
    print("Top 10 sender/domain risks:")
    sender_domain_risks: list[str] = []
    sender_domain_risks.extend(f"duplicate_domain:{item['domain']}->{','.join(item['entities'])}" for item in audit["domain"]["duplicate_domains"][:10])
    sender_domain_risks.extend(f"sender_overmatch:{eid}:{value}" for eid, value in audit["sender_overmatch_risks"][:10])
    for item in sender_domain_risks[:10]:
        print(f"  {item}")
    if not sender_domain_risks:
        print("  none")


def main() -> int:
    audit = registry_quality_audit()
    _print_audit(audit)

    hdr = (
        f"{'ID':>3} {'FAMILY':24} {'EXPECTED':10} {'SCORE':>5} {'CLASS':10} "
        f"{'CLAIMED':28} {'SENDER':24} {'URL_ENTITY':24} {'TOP_EVIDENCE':46} "
        f"{'TRACE':30} {'R':4}"
    )
    print("=" * len(hdr))
    print("APG Entity Intelligence v2 Evaluation")
    print(f"Cases: {len(CASES)}")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    passed = failed = 0
    family_counts: dict[str, list[int]] = {}
    failed_rows: list[tuple[int, list[str]]] = []

    for case in CASES:
        row, issues = _run_case(case)
        result = "PASS" if not issues else "FAIL"
        family_counts.setdefault(case.family, [0, 0])
        family_counts[case.family][0] += 1
        if not issues:
            family_counts[case.family][1] += 1
            passed += 1
        else:
            failed += 1
            failed_rows.append((case.case_id, issues))
        top = ",".join(row["top_evidence_ids"])[:46]
        trace = row["policy_trace_summary"][:30]
        print(
            f"{row['case_id']:>3} {row['family'][:24]:24} {row['expected'][:10]:10} "
            f"{row['score']:>5} {row['class'][:10]:10} {row['claimed_entity'][:28]:28} "
            f"{row['sender_entity'][:24]:24} {row['url_entity'][:24]:24} "
            f"{top:46} {trace:30} {result:4}"
        )
        if issues:
            for issue in issues:
                print(f"   - {issue}")

    print("-" * len(hdr))
    print(f"PASS: {passed}  FAIL: {failed}  TOTAL: {len(CASES)}")
    print("Family summary:")
    for family in sorted(family_counts):
        total, ok = family_counts[family]
        print(f"  {family}: {ok}/{total} pass")

    regression_status = {
        "behavioral_v2": _run_regression_script("evaluate_behavioral_v2.py"),
        "promo_false_positive": _run_regression_script("evaluate_behavioral_false_positives.py"),
        "dynamic_sandbox": _run_regression_script("evaluate_dynamic_url_sandbox.py"),
    }

    blocking_registry_gaps = {
        "unmapped_forbidden_requests": audit["unmapped_forbidden_requests"],
    }
    alias_total, alias_ok = family_counts.get("alias_substring", [0, 0])
    spoof_total, spoof_ok = family_counts.get("sender_spoofing", [0, 0])
    sender_precision_total, sender_precision_ok = family_counts.get("sender_precision", [0, 0])
    forbidden_total, forbidden_ok = family_counts.get("forbidden_request", [0, 0])
    awareness_total, awareness_ok = family_counts.get("safe_awareness", [0, 0])
    duplicate_total, duplicate_ok = family_counts.get("duplicate_domain_policy", [0, 0])
    url_bridge_total, url_bridge_ok = family_counts.get("registry_url_brand_bridge", [0, 0])
    required_family_gates = {
        "alias_substring_regression": (alias_ok, alias_total),
        "sender_spoofing": (spoof_ok, spoof_total),
        "sender_precision": (sender_precision_ok, sender_precision_total),
        "forbidden_request_cases": (forbidden_ok, forbidden_total),
        "safe_awareness_cases": (awareness_ok, awareness_total),
        "duplicate_domain_cases": (duplicate_ok, duplicate_total),
        "registry_url_brand_bridge_cases": (url_bridge_ok, url_bridge_total),
    }
    required_families_pass = all(total > 0 and ok == total for ok, total in required_family_gates.values())
    remaining_gaps = [
        "allowed_message_types_runtime_use_deferred",
        "undercovered_entity_types:" + (",".join(audit["undercovered_entity_types"]) or "none"),
        "medium_lower_priority_registry_expansion",
        "optional_legacy_known_brands_generation_from_registry",
    ]
    phase_complete = (
        failed == 0
        and not blocking_registry_gaps["unmapped_forbidden_requests"]
        and required_families_pass
        and audit["duplicate_domain_policy"] == "implemented"
        and audit["registry_brand_gap"]["registry_url_brand_bridge"] == "implemented"
        and all(status == "PASS" for status in regression_status.values())
    )

    print("Quality gate:")
    print(f"  PHASE_5_STATUS: {'COMPLETE' if phase_complete else 'NOT_COMPLETE'}")
    print(f"  PHASE_5_1_STATUS: {'COMPLETE' if phase_complete else 'NOT_COMPLETE'}")
    print(f"  entity_cases_total={len(CASES)}")
    print(f"  entity_cases_passed={passed}")
    print(f"  entity_cases_failed={failed}")
    print(f"  alias_substring_regression={alias_ok}/{alias_total}")
    print(f"  sender_spoofing={spoof_ok}/{spoof_total}")
    print(f"  sender_precision={sender_precision_ok}/{sender_precision_total}")
    print(f"  forbidden_request_cases={forbidden_ok}/{forbidden_total}")
    print(f"  safe_awareness_cases={awareness_ok}/{awareness_total}")
    print(f"  registry_entities_count={audit['entity_count']}")
    print(f"  alias_count={audit['alias_count']}")
    print(f"  official_domain_count={audit['official_domain_count']}")
    print(f"  official_sender_count={audit['official_sender_count']}")
    print(f"  forbidden_request_count={audit['forbidden_request_count']}")
    print(f"  allowed_message_type_count={audit['allowed_message_type_count']}")
    print(f"  duplicate_alias_count={len(audit['duplicate_aliases'])}")
    print(f"  duplicate_domain_count={len(audit['domain']['duplicate_domains'])}")
    print(f"  duplicate_domain_policy={audit['duplicate_domain_policy']}")
    print("  duplicate_domain_groups:")
    for item in audit["domain"]["duplicate_domains"]:
        print(f"    {item['domain']}: {', '.join(item['entities'])}")
    print(f"  duplicate_domain_conflict_cases_passed={duplicate_ok}/{duplicate_total}")
    print(f"  registry_url_brand_bridge={audit['registry_brand_gap']['registry_url_brand_bridge']}")
    print(
        "  registry_entities_available_to_url_brand_detection="
        f"{audit['registry_brand_gap']['registry_entities_available_to_url_brand_detection']}"
    )
    print(f"  legacy_known_brands_count={audit['registry_brand_gap']['known_brand_count']}")
    print(f"  registry_brand_candidates_count={audit['registry_brand_gap']['registry_brand_candidates_count']}")
    print(
        "  registry_not_covered_by_known_brands_count="
        f"{len(audit['registry_brand_gap']['registry_entities_not_covered_by_known_brand_domains'])}"
    )
    print(f"  registry_url_brand_bridge_cases={url_bridge_ok}/{url_bridge_total}")
    print(f"  url_brand_consistency_cases_passed={url_bridge_ok}/{url_bridge_total}")
    print(f"  short_alias_risk_count={len(audit['aliases_shorter_than_3']) + len(audit['arabic_aliases_shorter_than_3']) + len(audit['common_alias_risks'])}")
    print("  unmapped_forbidden_requests=" + (", ".join(audit["unmapped_forbidden_requests"]) or "none"))
    print("  undercovered_entity_types=" + (", ".join(audit["undercovered_entity_types"]) or "none"))
    print("  runtime_gaps:")
    for gap in audit["runtime_gaps"][:12]:
        print(f"    {gap}")
    if len(audit["runtime_gaps"]) > 12:
        print(f"    ... {len(audit['runtime_gaps']) - 12} more")
    print(f"  behavioral_v2_regression={regression_status['behavioral_v2']}")
    print(f"  promo_false_positive_regression={regression_status['promo_false_positive']}")
    print(f"  dynamic_sandbox_regression={regression_status['dynamic_sandbox']}")
    print("  regression_status:")
    for name, status in regression_status.items():
        print(f"    {name}: {status}")
    print("  remaining_gaps:")
    for gap in remaining_gaps:
        print(f"    {gap}")
    if failed_rows:
        print("Failed entity cases:")
        for case_id, issues in failed_rows[:20]:
            print(f"  {case_id}: {'; '.join(issues)}")
    return 0 if phase_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
