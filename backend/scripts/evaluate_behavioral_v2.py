"""
APG Phase 4.2 - Behavioral Intelligence v2 Evaluation
=====================================================

Regression checks for structured Arabic phishing behavior families and safe
lookalikes. Uses synthetic text and fake .test domains only.

Usage:
  cd backend
  python scripts/evaluate_behavioral_v2.py

Exit codes:
  0  all cases PASS
  1  one or more cases FAIL
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
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

from app.services.risk_engine.service import RiskEngineV1Service  # noqa: E402


_SVC = RiskEngineV1Service()

_VERDICT_RANK = {
    "allow": 0,
    "caution": 1,
    "warn": 2,
    "block": 3,
}

_PHRASE_FILE = BACKEND_DIR / "app" / "data" / "ar_behavioral_phrases.json"
_V2_FAMILY_KEYS = (
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
_KNOWN_SHORT_TOKENS = {"OTP", "CVV", "CVC", "PIN", "KYC", "CliQ"}
_ARABIC_LETTERS_RE = re.compile(r"[\u0621-\u064A]")


@dataclass(frozen=True)
class EvalCase:
    case_id: int
    family: str
    expected: str
    text: str
    dialect: str = "msa"
    sector: str = "mixed"
    min_verdict: str | None = None
    max_verdict: str | None = None
    required_evidence_any: set[str] = field(default_factory=set)
    forbidden_evidence: set[str] = field(default_factory=set)


CASES: list[EvalCase] = [
    EvalCase(1, "account_takeover", "dangerous", "حسابك موقوف يرجى تحديث بيانات الحساب https://account-review.test", min_verdict="block", required_evidence_any={"behavioral_account_takeover_url", "behavioral_account_takeover_v2"}),
    EvalCase(2, "account_takeover", "suspicious_or_dangerous", "نشاط غير معتاد على حسابك تحقق من حسابك https://secure-account.test", min_verdict="warn"),
    EvalCase(3, "account_takeover", "dangerous", "سيتم إيقاف حسابك قم بتسجيل الدخول https://account-stop.test", min_verdict="block", required_evidence_any={"behavioral_account_takeover_url", "behavioral_account_takeover_v2"}),
    EvalCase(4, "otp_theft", "suspicious_or_dangerous", "أرسل رمز التحقق لتأكيد العملية الآن", min_verdict="caution"),
    EvalCase(5, "otp_theft", "suspicious_or_dangerous", "كود واتساب مطلوب انقل رمز الواتساب الآن", min_verdict="caution"),
    EvalCase(6, "otp_theft", "dangerous", "أدخل كود التحقق لتأكيد العملية https://otp-check.test", min_verdict="block"),
    EvalCase(7, "password_theft", "dangerous", "أدخل كلمة المرور لتأكيد الحساب", min_verdict="block", required_evidence_any={"danger_password_request"}),
    EvalCase(8, "password_theft", "dangerous", "بيانات الدخول مطلوبة سجل دخولك https://login-check.test", min_verdict="block"),
    EvalCase(9, "password_theft", "suspicious_or_dangerous", "اسم المستخدم وكلمة المرور مطلوبان الآن", min_verdict="warn"),
    EvalCase(10, "card_payment", "dangerous", "أدخل بيانات البطاقة لدفع رسوم التوصيل https://delivery-pay.test", min_verdict="block", required_evidence_any={"danger_card_request", "behavioral_payment_phishing"}),
    EvalCase(11, "card_payment", "dangerous", "رقم البطاقة مطلوب وسدد الرسوم https://card-pay.test", min_verdict="block"),
    EvalCase(12, "card_payment", "dangerous", "أدخل CVV لتأكيد الدفع https://billing-check.test", min_verdict="block"),
    EvalCase(13, "wallet_freeze", "dangerous", "تم تجميد محفظتك أعد تفعيل المحفظة https://wallet-restore.test", min_verdict="block", required_evidence_any={"behavioral_wallet_freeze_reactivation"}),
    EvalCase(14, "wallet_freeze", "dangerous", "رصيد المحفظة معلق تحديث بيانات المحفظة https://wallet-update.test", min_verdict="block", required_evidence_any={"behavioral_wallet_freeze_reactivation"}),
    EvalCase(15, "wallet_freeze", "dangerous", "حوالتك معلقة استلام حوالة يتطلب تأكيد https://transfer-verify.test", min_verdict="block", required_evidence_any={"behavioral_wallet_freeze_reactivation"}),
    EvalCase(16, "delivery_customs", "suspicious_or_dangerous", "شحنتك معلقة ادفع رسوم التوصيل https://delivery-fee.test", min_verdict="warn", required_evidence_any={"behavioral_delivery_customs_fee", "behavioral_payment_phishing"}),
    EvalCase(17, "delivery_customs", "suspicious_or_dangerous", "رسوم جمركية على الشحنة دفع فرق التوصيل https://customs-pay.test", min_verdict="caution"),
    EvalCase(18, "delivery_customs", "suspicious_or_dangerous", "سيتم إرجاع الطرد تحديث عنوان التسليم https://parcel-update.test", min_verdict="caution"),
    EvalCase(19, "fake_government", "suspicious_or_dangerous", "مخالفة مستحقة رسوم حكومية ادفع المبلغ المستحق https://gov-fees.test", min_verdict="caution", required_evidence_any={"behavioral_fake_government_payment", "behavioral_payment_phishing"}),
    EvalCase(20, "fake_government", "suspicious_or_dangerous", "طلبك الحكومي معلق استكمال طلب الدعم https://gov-support.test", min_verdict="caution"),
    EvalCase(21, "fake_government", "suspicious_or_dangerous", "ضريبة مستحقة تصديق الطلب https://tax-verify.test", min_verdict="caution"),
    EvalCase(22, "bank_kyc", "dangerous", "تحديث KYC مطلوب حسابك البنكي بحاجة لتحديث https://bank-kyc.test", min_verdict="block", required_evidence_any={"behavioral_bank_kyc_update", "behavioral_account_takeover_url"}),
    EvalCase(23, "bank_kyc", "dangerous", "اعرف عميلك مراجعة بيانات العميل https://customer-review.test", min_verdict="block", required_evidence_any={"behavioral_bank_kyc_update"}),
    EvalCase(24, "bank_kyc", "dangerous", "تأكيد الهوية البنكية سجل دخولك https://bank-login.test", min_verdict="block"),
    EvalCase(25, "whatsapp_social", "suspicious_or_dangerous", "كود واتساب أرسل رمز الواتساب الآن", min_verdict="caution"),
    EvalCase(26, "whatsapp_social", "dangerous", "حسابك الإعلاني تم تقييده تحقق من صفحة الأعمال https://meta-review.test", min_verdict="block", required_evidence_any={"behavioral_whatsapp_social_takeover"}),
    EvalCase(27, "whatsapp_social", "dangerous", "Instagram verification سجل دخولك لتأكيد الحساب https://insta-verify.test", min_verdict="block", required_evidence_any={"behavioral_whatsapp_social_takeover"}),
    EvalCase(28, "prize_reward", "suspicious_or_dangerous", "ربحت جائزة لتأكيد الجائزة أدخل بياناتك https://prize-claim.test", min_verdict="caution", required_evidence_any={"behavioral_prize_reward_phishing"}),
    EvalCase(29, "prize_reward", "suspicious_or_dangerous", "رسوم استلام الجائزة ادفع من الرابط https://reward-fee.test", min_verdict="warn", required_evidence_any={"behavioral_prize_reward_phishing", "behavioral_payment_phishing"}),
    EvalCase(30, "prize_reward", "suspicious_or_dangerous", "جائزة نقدية تأكيد هوية الفائز https://winner-confirm.test", min_verdict="caution"),
    EvalCase(31, "safe_promo", "not_dangerous", "عرض خصم على الباقات بدون طلب بيانات https://promo-offer.test", max_verdict="warn", forbidden_evidence={"suspicious_financial_link", "behavioral_prize_reward_phishing"}),
    EvalCase(32, "safe_promo", "not_dangerous", "كود خصم جديد لفترة محدودة شاهد التفاصيل https://coupon-info.test", max_verdict="warn", forbidden_evidence={"suspicious_financial_link"}),
    EvalCase(33, "safe_promo", "not_dangerous", "تخفيضات نهاية الأسبوع على المنتجات", max_verdict="caution"),
    EvalCase(34, "safe_promo", "not_dangerous", "وفر أكثر مع عروضنا الجديدة", max_verdict="caution"),
    EvalCase(35, "safe_promo", "not_dangerous", "sale discount promo coupon for subscribers https://promo-details.test", max_verdict="warn"),
    EvalCase(36, "safe_promo", "not_dangerous", "عرض محدود لعملائنا بدون تسجيل دخول وبدون طلب كلمة مرور", max_verdict="warn", forbidden_evidence={"danger_password_request"}),
    EvalCase(37, "safe_promo", "not_dangerous", "خصومات وتنزيلات على المنتجات اليوم فقط", max_verdict="caution"),
    EvalCase(38, "safe_promo", "not_dangerous", "شاهد تفاصيل العرض الجديد من المتجر https://store-promo.test", max_verdict="warn"),
    EvalCase(39, "safe_receipt", "not_dangerous", "تم استلام مبلغ في حسابك ولا يلزم أي إجراء", max_verdict="caution"),
    EvalCase(40, "safe_receipt", "not_dangerous", "تم دفع الفاتورة بنجاح رقم العملية 12345", max_verdict="caution"),
    EvalCase(41, "safe_receipt", "not_dangerous", "تم تسديد الفاتورة بنجاح شكرا لاستخدامك الخدمة", max_verdict="caution"),
    EvalCase(42, "safe_receipt", "not_dangerous", "وصل الدفع متاح داخل التطبيق الرسمي", max_verdict="caution"),
    EvalCase(43, "safe_receipt", "not_dangerous", "تمت عملية الدفع بنجاح ولا حاجة للرد", max_verdict="caution"),
    EvalCase(44, "safe_receipt", "not_dangerous", "تم استلام حوالتك بنجاح في المحفظة", max_verdict="caution"),
    EvalCase(45, "safe_receipt", "not_dangerous", "تم تحديث عنوانك بنجاح", max_verdict="caution"),
    EvalCase(46, "safe_receipt", "not_dangerous", "تذكير بموعد تسليم شحنتك بدون رسوم", max_verdict="caution"),
    EvalCase(47, "safe_awareness", "not_dangerous", "لا تشارك رمز التحقق مع أي شخص", max_verdict="caution", forbidden_evidence={"danger_otp_request"}),
    EvalCase(48, "safe_awareness", "not_dangerous", "البنك لا يطلب كلمة المرور عبر الرسائل", max_verdict="caution", forbidden_evidence={"danger_password_request"}),
    EvalCase(49, "safe_awareness", "not_dangerous", "احذر من روابط تحديث الحساب ولا تدخل بياناتك", max_verdict="caution"),
    EvalCase(50, "safe_awareness", "not_dangerous", "نصيحة أمنية: لا تدخل بيانات البطاقة في روابط مجهولة", max_verdict="caution", forbidden_evidence={"danger_card_request"}),
    EvalCase(51, "safe_awareness", "not_dangerous", "رسالة توعوية: لا ترد على من يطلب كود واتساب", max_verdict="caution", forbidden_evidence={"danger_otp_request"}),
    EvalCase(52, "safe_awareness", "not_dangerous", "احم حسابك ولا تشارك رمز الدخول", max_verdict="caution"),
    EvalCase(53, "safe_awareness", "not_dangerous", "تنبيه أمني: استخدم التطبيق الرسمي لتحديث بياناتك", max_verdict="caution"),
    EvalCase(54, "safe_awareness", "not_dangerous", "لا تضغط على روابط مجهولة تطلب دفع رسوم", max_verdict="caution"),
    EvalCase(55, "otp_delivery", "not_dangerous", "رمز التحقق الخاص بك هو 123456 ولا تشاركه", max_verdict="caution"),
    EvalCase(56, "otp_delivery", "not_dangerous", "كود الدخول 445566 لا تشاركه مع أي شخص", max_verdict="caution"),
    EvalCase(57, "otp_delivery", "not_dangerous", "رمز OTP لتسجيل الدخول هو 987654", max_verdict="caution"),
    EvalCase(58, "otp_delivery", "not_dangerous", "رمز واتساب الخاص بك هو 112233 لا ترسله لأحد", max_verdict="caution"),
    EvalCase(59, "otp_delivery", "not_dangerous", "استخدم الرمز 778899 داخل التطبيق فقط", max_verdict="caution"),
    EvalCase(60, "otp_delivery", "not_dangerous", "رمز التحقق لإتمام العملية هو 246810 ولا يطلبه الموظفون", max_verdict="caution"),
    EvalCase(61, "account_takeover", "suspicious_or_dangerous", "حسابك رح يتوقف لازم تحدث معلوماتك https://jo-account.test", dialect="jordanian", sector="bank", min_verdict="caution", required_evidence_any={"behavioral_account_takeover_v2"}),
    EvalCase(62, "account_takeover", "suspicious_or_dangerous", "صار دخول غريب على حسابك لازم تأكد حسابك https://account-confirm.test", dialect="jordanian", sector="telecom", min_verdict="caution"),
    EvalCase(63, "account_takeover", "suspicious_or_dangerous", "حسابك هيتقفل أعد تسجيل الدخول https://eg-account.test", dialect="egyptian", sector="bank", min_verdict="caution"),
    EvalCase(64, "otp_theft", "suspicious_or_dangerous", "ابعت رمز التحقق لتأكيد العملية الآن", dialect="jordanian", sector="bank", min_verdict="caution"),
    EvalCase(65, "otp_theft", "suspicious_or_dangerous", "ابعث الكود حتى نثبت حسابك", dialect="gulf", sector="telecom", min_verdict="caution"),
    EvalCase(66, "otp_theft", "suspicious_or_dangerous", "حط رمز التأكيد في الصفحة https://otp-secure.test", dialect="mixed", sector="bank", min_verdict="caution"),
    EvalCase(67, "password_theft", "dangerous", "ادخل باسوردك لتأكيد الحساب", dialect="jordanian", sector="bank", min_verdict="block"),
    EvalCase(68, "password_theft", "suspicious_or_dangerous", "فوت على حسابك من الرابط https://login-jo.test", dialect="jordanian", sector="telecom", min_verdict="caution"),
    EvalCase(69, "password_theft", "dangerous", "اكتب كلمة السر لتحديث الطلب", dialect="egyptian", sector="government", min_verdict="block"),
    EvalCase(70, "card_payment", "dangerous", "ادخل رقم البطاقة لدفع فرق الشحن https://card-delivery.test", dialect="msa", sector="delivery", min_verdict="block"),
    EvalCase(71, "card_payment", "dangerous", "ادخل CVC وسدد المبلغ https://card-cvc.test", dialect="mixed", sector="bank", min_verdict="block"),
    EvalCase(72, "card_payment", "suspicious_or_dangerous", "عليك مبلغ مستحق ادفع 1.5 دينار https://fee-pay.test", dialect="jordanian", sector="delivery", min_verdict="caution"),
    EvalCase(73, "wallet_freeze", "dangerous", "محفظتك على زين كاش موقوفة تفعيل زين كاش https://zaincash-restore.test", dialect="jordanian", sector="wallet", min_verdict="block", required_evidence_any={"behavioral_wallet_freeze_reactivation"}),
    EvalCase(74, "wallet_freeze", "dangerous", "حوالة كليك معلقة تأكيد كليك https://cliq-confirm.test", dialect="jordanian", sector="wallet", min_verdict="block"),
    EvalCase(75, "wallet_freeze", "suspicious_or_dangerous", "اورنج موني بحاجة تحديث من الرابط https://orange-money-update.test", dialect="jordanian", sector="wallet", min_verdict="caution"),
    EvalCase(76, "delivery_customs", "suspicious_or_dangerous", "الطرد واقف عليها رسوم جمرك ادفع من الرابط https://parcel-fee.test", dialect="jordanian", sector="delivery", min_verdict="caution"),
    EvalCase(77, "delivery_customs", "suspicious_or_dangerous", "الشحنة معلقة بالجمارك دفع رسوم الجمارك https://customs-duty.test", dialect="msa", sector="delivery", min_verdict="caution"),
    EvalCase(78, "delivery_customs", "suspicious_or_dangerous", "عنوانك ناقص حدث عنوان التوصيل https://address-update.test", dialect="gulf", sector="delivery", min_verdict="caution"),
    EvalCase(79, "fake_government", "suspicious_or_dangerous", "طلب الدعم بحاجة تأكيد استكمال دعم حكومي https://gov-support-confirm.test", dialect="msa", sector="government", min_verdict="caution"),
    EvalCase(80, "fake_government", "suspicious_or_dangerous", "مخالفات مستحقة رسوم معاملة https://gov-fines.test", dialect="msa", sector="government", min_verdict="caution"),
    EvalCase(81, "fake_government", "suspicious_or_dangerous", "يرجى إكمال الطلب الحكومي تصديق المعاملة https://gov-transaction.test", dialect="gulf", sector="government", min_verdict="caution"),
    EvalCase(82, "bank_kyc", "dangerous", "KYC مطلوب تحديث ملف العميل https://bank-file.test", dialect="mixed", sector="bank", min_verdict="block", required_evidence_any={"behavioral_bank_kyc_update"}),
    EvalCase(83, "bank_kyc", "dangerous", "بيانات العميل ناقصة تحديث رقم الهاتف البنكي https://bank-phone.test", dialect="msa", sector="bank", min_verdict="block"),
    EvalCase(84, "bank_kyc", "dangerous", "حسابك البنكي تحت المراجعة تفعيل الخدمات المصرفية https://bank-services.test", dialect="msa", sector="bank", min_verdict="block"),
    EvalCase(85, "whatsapp_social", "suspicious_or_dangerous", "كود واتساب وصل بالغلط ابعتلي كود الواتساب", dialect="jordanian", sector="social", min_verdict="caution"),
    EvalCase(86, "whatsapp_social", "dangerous", "صفحة الفيسبوك معرضة للإغلاق تأكيد صفحة الأعمال https://facebook-page.test", dialect="egyptian", sector="social", min_verdict="block"),
    EvalCase(87, "whatsapp_social", "dangerous", "Meta Business verification تفعيل حساب الإعلانات https://meta-business.test", dialect="mixed", sector="social", min_verdict="block"),
    EvalCase(88, "prize_reward", "suspicious_or_dangerous", "مبروك فزت لتأكيد الفوز أدخل بياناتك https://winner-prize.test", dialect="egyptian", sector="prize", min_verdict="caution"),
    EvalCase(89, "prize_reward", "suspicious_or_dangerous", "جائزتك جاهزة ادفع رسوم رمزية https://gift-fee.test", dialect="gulf", sector="prize", min_verdict="caution"),
    EvalCase(90, "subscription_suspension", "suspicious_or_dangerous", "باقتك رح توقف تحديث الباقة https://bundle-update.test", dialect="jordanian", sector="subscription", min_verdict="caution", required_evidence_any={"behavioral_subscription_suspension"}),
    EvalCase(91, "safe_awareness", "not_dangerous", "تنبيه أمني: لا ترسل رمز التحقق لأي شخص", dialect="msa", sector="awareness", max_verdict="caution", forbidden_evidence={"danger_otp_request"}),
    EvalCase(92, "safe_awareness", "not_dangerous", "البنك لا يطلب كلمة السر عبر الرسائل", dialect="msa", sector="awareness", max_verdict="caution", forbidden_evidence={"danger_password_request"}),
    EvalCase(93, "safe_receipt", "not_dangerous", "تم دفع الفاتورة بنجاح", dialect="msa", sector="receipt", max_verdict="caution"),
    EvalCase(94, "safe_receipt", "not_dangerous", "تم استلام حوالة كليك", dialect="jordanian", sector="wallet", max_verdict="caution"),
    EvalCase(95, "safe_receipt", "not_dangerous", "تذكير: شحنتك قيد التوصيل", dialect="msa", sector="delivery", max_verdict="caution"),
    EvalCase(96, "safe_receipt", "not_dangerous", "تم تحديث عنوانك بنجاح", dialect="msa", sector="delivery", max_verdict="caution"),
    EvalCase(97, "safe_promo", "not_dangerous", "عرض خصم بدون تسجيل دخول أو بيانات", dialect="msa", sector="promo", max_verdict="caution", forbidden_evidence={"suspicious_financial_link"}),
    EvalCase(98, "safe_promo", "not_dangerous", "كود الخصم الخاص بك", dialect="msa", sector="promo", max_verdict="caution"),
    EvalCase(99, "otp_delivery", "not_dangerous", "رمز التحقق الخاص بك هو 123456 ولا تشاركه", dialect="msa", sector="awareness", max_verdict="caution"),
    EvalCase(100, "safe_awareness", "not_dangerous", "احذر من رسائل تطلب كود واتساب", dialect="msa", sector="awareness", max_verdict="caution", forbidden_evidence={"danger_otp_request"}),
    EvalCase(101, "safe_awareness", "not_dangerous", "نصيحة: لا تدخل بيانات البطاقة في روابط مجهولة", dialect="msa", sector="awareness", max_verdict="warn", forbidden_evidence={"danger_card_request"}),
    EvalCase(102, "safe_receipt", "not_dangerous", "تم تجديد اشتراكك بنجاح", dialect="msa", sector="subscription", max_verdict="caution"),
    EvalCase(103, "safe_receipt", "not_dangerous", "تم شحن الرصيد بنجاح", dialect="gulf", sector="telecom", max_verdict="caution"),
    EvalCase(104, "safe_receipt", "not_dangerous", "الفاتورة مدفوعة ولا يلزم أي إجراء", dialect="msa", sector="receipt", max_verdict="caution"),
    EvalCase(105, "safe_promo", "not_dangerous", "خصومات بدون طلب كلمة مرور", dialect="msa", sector="promo", max_verdict="caution", forbidden_evidence={"danger_password_request"}),
    EvalCase(106, "safe_promo", "not_dangerous", "تفاصيل العرض داخل التطبيق", dialect="msa", sector="promo", max_verdict="caution"),
    EvalCase(107, "safe_awareness", "not_dangerous", "لا ترسل لقطة شاشة للرمز", dialect="msa", sector="awareness", max_verdict="caution"),
    EvalCase(108, "safe_awareness", "not_dangerous", "لا تشارك كود واتساب", dialect="jordanian", sector="awareness", max_verdict="caution"),
    EvalCase(109, "safe_receipt", "not_dangerous", "شحنتك قيد التوصيل ولا يوجد رسوم", dialect="msa", sector="delivery", max_verdict="warn"),
    EvalCase(110, "safe_receipt", "not_dangerous", "تم تحديث العنوان بنجاح", dialect="msa", sector="delivery", max_verdict="caution"),
    EvalCase(111, "safe_promo", "not_dangerous", "عرض الباقات الجديد متاح الآن", dialect="jordanian", sector="promo", max_verdict="caution"),
    EvalCase(112, "safe_promo", "not_dangerous", "تخفيضات المتجر بدون طلب بيانات", dialect="egyptian", sector="promo", max_verdict="caution"),
    EvalCase(113, "otp_delivery", "not_dangerous", "كود واتساب الخاص بك هو 778899 لا تشاركه", dialect="msa", sector="social", max_verdict="caution"),
    EvalCase(114, "otp_delivery", "not_dangerous", "رمز الدخول للتطبيق 543210", dialect="gulf", sector="telecom", max_verdict="caution"),
    EvalCase(115, "safe_awareness", "not_dangerous", "احذر من روابط تحديث الحساب المزيفة", dialect="msa", sector="awareness", max_verdict="caution"),
    EvalCase(116, "safe_awareness", "not_dangerous", "لا تعطي موظف الدعم رمز الدخول", dialect="gulf", sector="awareness", max_verdict="caution"),
    EvalCase(117, "safe_receipt", "not_dangerous", "تم استلام الدفعة بنجاح", dialect="msa", sector="receipt", max_verdict="caution"),
    EvalCase(118, "safe_receipt", "not_dangerous", "تم تجديد الباقة بنجاح", dialect="jordanian", sector="subscription", max_verdict="caution"),
    EvalCase(119, "safe_promo", "not_dangerous", "كوبون خصم جديد بدون تسجيل دخول", dialect="mixed", sector="promo", max_verdict="caution"),
    EvalCase(120, "safe_awareness", "not_dangerous", "نصيحة أمنية: الشركات لا تطلب CVC أو CVV في الرسائل", dialect="mixed", sector="awareness", max_verdict="caution"),
    EvalCase(121, "whatsapp_social", "dangerous", "تم طلب كود واتساب لحسابك ارسل كود واتساب الآن", dialect="msa", sector="social", min_verdict="block", required_evidence_any={"behavioral_whatsapp_social_takeover"}),
    EvalCase(122, "whatsapp_social", "dangerous", "شخص يحاول تفعيل واتساب برقمك انقل رمز الواتساب", dialect="msa", sector="social", min_verdict="block", required_evidence_any={"behavioral_whatsapp_social_takeover"}),
    EvalCase(123, "whatsapp_social", "dangerous", "رمز واتساب لتأكيد النقل https://whatsapp-transfer.test", dialect="msa", sector="social", min_verdict="block", required_evidence_any={"behavioral_whatsapp_social_takeover"}),
    EvalCase(124, "whatsapp_social", "dangerous", "استعادة واتساب تتطلب الرمز اكتب رمز واتساب", dialect="msa", sector="social", min_verdict="block", required_evidence_any={"behavioral_whatsapp_social_takeover"}),
    EvalCase(125, "safe_promo", "not_dangerous", "عرض على الباقات بدون تسجيل", dialect="msa", sector="promo", max_verdict="caution"),
    EvalCase(126, "safe_promo", "not_dangerous", "كود خصم للاستخدام في التطبيق", dialect="msa", sector="promo", max_verdict="caution"),
    EvalCase(127, "safe_receipt", "not_dangerous", "تم إضافة الرصيد بنجاح", dialect="msa", sector="receipt", max_verdict="caution"),
    EvalCase(128, "safe_awareness", "not_dangerous", "لا تشارك كود واتساب مع أي شخص", dialect="msa", sector="awareness", max_verdict="caution", forbidden_evidence={"danger_otp_request"}),
]


def _rank(verdict: str) -> int:
    return _VERDICT_RANK.get(verdict, 99)


def _risk_class(verdict: str) -> str:
    if verdict == "block":
        return "dangerous"
    if verdict in {"warn", "caution"}:
        return "suspicious"
    return "safe"


def _top_evidence_ids(result: Any) -> list[str]:
    ranked = sorted(
        result.evidence,
        key=lambda ev: (ev.score_delta, ev.severity == "critical"),
        reverse=True,
    )
    return [ev.id for ev in ranked[:5]]


def _phrase_audit() -> dict[str, Any]:
    data = json.loads(_PHRASE_FILE.read_text(encoding="utf-8"))
    phrases: list[str] = []
    same_family_duplicates: dict[str, list[tuple[str, int]]] = {}
    phrase_families: dict[str, set[str]] = {}
    for key in _V2_FAMILY_KEYS:
        family_phrases = data.get(key, [])
        phrases.extend(family_phrases)
        family_counts = Counter(family_phrases)
        dupes = [(phrase, count) for phrase, count in family_counts.items() if count > 1]
        if dupes:
            same_family_duplicates[key] = dupes
        for phrase in family_phrases:
            phrase_families.setdefault(phrase, set()).add(key)

    counts = Counter(phrases)
    duplicates = [(phrase, count) for phrase, count in counts.most_common() if count > 1]
    cross_family_duplicates = [
        (phrase, sorted(families))
        for phrase, families in phrase_families.items()
        if len(families) > 1
    ]
    under_covered = [
        key for key in _V2_FAMILY_KEYS
        if len(data.get(key, [])) < 20
    ]
    short_phrases: list[tuple[str, str]] = []
    for key in _V2_FAMILY_KEYS:
        for phrase in data.get(key, []):
            if phrase in _KNOWN_SHORT_TOKENS:
                continue
            arabic_len = len(_ARABIC_LETTERS_RE.findall(phrase))
            if 0 < arabic_len < 3:
                short_phrases.append((key, phrase))

    return {
        "loaded_v2_phrase_count": len(phrases),
        "family_counts": {key: len(data.get(key, [])) for key in _V2_FAMILY_KEYS},
        "duplicates": duplicates,
        "same_family_duplicates": same_family_duplicates,
        "cross_family_duplicates": cross_family_duplicates,
        "under_covered": under_covered,
        "short_phrases": short_phrases,
    }


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


def _run(case: EvalCase) -> tuple[dict[str, Any], list[str]]:
    result = _SVC.analyze_full(text=case.text)
    evidence_ids = {ev.id for ev in result.evidence}
    top_ids = _top_evidence_ids(result)

    row = {
        "case_id": case.case_id,
        "family": case.family,
        "dialect": case.dialect,
        "sector": case.sector,
        "expected": case.expected,
        "score": result.risk_score,
        "class": _risk_class(result.verdict),
        "verdict": result.verdict,
        "intent": result.message_intent,
        "category": result.message_category,
        "top_evidence_ids": top_ids,
    }

    issues: list[str] = []
    if case.min_verdict and _rank(result.verdict) < _rank(case.min_verdict):
        issues.append(f"VERDICT_BELOW_MIN({result.verdict}<{case.min_verdict})")
    if case.max_verdict and _rank(result.verdict) > _rank(case.max_verdict):
        issues.append(f"VERDICT_ABOVE_MAX({result.verdict}>{case.max_verdict})")
    if case.required_evidence_any and not (case.required_evidence_any & evidence_ids):
        issues.append(f"MISSING_ANY_EVIDENCE({sorted(case.required_evidence_any)})")
    forbidden = case.forbidden_evidence & evidence_ids
    if forbidden:
        issues.append(f"FORBIDDEN_EVIDENCE({sorted(forbidden)})")

    return row, issues


def main() -> int:
    hdr = (
        f"{'ID':>3} {'FAMILY':18} {'DIALECT':10} {'SECTOR':12} {'EXPECTED':22} {'SCORE':>5} "
        f"{'CLASS':10} {'INTENT':20} {'CATEGORY':22} {'TOP_EVIDENCE':42} {'R':4}"
    )
    print("=" * len(hdr))
    print("APG Phase 4.3 - Behavioral Intelligence v2 Dialect & Sector Evaluation")
    print(f"Cases: {len(CASES)}")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    passed = failed = 0
    family_counts: dict[str, list[int]] = {}
    dialect_counts: dict[str, list[int]] = {}
    sector_counts: dict[str, list[int]] = {}
    improved_ids: list[int] = []
    protected_ids: list[int] = []

    for case in CASES:
        row, issues = _run(case)
        result = "PASS" if not issues else "FAIL"
        family_counts.setdefault(case.family, [0, 0])
        family_counts[case.family][0] += 1
        dialect_counts.setdefault(case.dialect, [0, 0])
        dialect_counts[case.dialect][0] += 1
        sector_counts.setdefault(case.sector, [0, 0])
        sector_counts[case.sector][0] += 1
        if not issues:
            family_counts[case.family][1] += 1
            dialect_counts[case.dialect][1] += 1
            sector_counts[case.sector][1] += 1
        top = ",".join(row["top_evidence_ids"])[:42]
        print(
            f"{row['case_id']:>3} {row['family'][:18]:18} {row['dialect'][:10]:10} "
            f"{row['sector'][:12]:12} {row['expected'][:22]:22} "
            f"{row['score']:>5} {row['class'][:10]:10} {row['intent'][:20]:20} "
            f"{row['category'][:22]:22} {top:42} {result:4}"
        )
        if issues:
            failed += 1
            for issue in issues:
                print(f"   - {issue}")
        else:
            passed += 1
            if case.expected != "not_dangerous" and row["class"] in {"suspicious", "dangerous"}:
                improved_ids.append(case.case_id)
            if case.expected == "not_dangerous" and row["class"] != "dangerous":
                protected_ids.append(case.case_id)

    print("-" * len(hdr))
    print(f"PASS: {passed}  FAIL: {failed}  TOTAL: {len(CASES)}")
    print("Family summary:")
    for family in sorted(family_counts):
        total, ok = family_counts[family]
        print(f"  {family}: {ok}/{total} pass")
    print("Dialect summary:")
    for dialect in sorted(dialect_counts):
        total, ok = dialect_counts[dialect]
        print(f"  {dialect}: {ok}/{total} pass")
    print("Sector summary:")
    for sector in sorted(sector_counts):
        total, ok = sector_counts[sector]
        print(f"  {sector}: {ok}/{total} pass")
    audit = _phrase_audit()
    print("Phrase audit:")
    print(f"  loaded_v2_phrase_count={audit['loaded_v2_phrase_count']}")
    undercovered = ", ".join(audit["under_covered"]) or "none"
    print("  families_under_20=" + undercovered)
    print("  duplicate_summary:")
    print(f"    same_family_duplicate_families={len(audit['same_family_duplicates'])}")
    print(f"    cross_family_duplicate_phrases={len(audit['cross_family_duplicates'])}")
    print("  top_duplicate_phrases:")
    for phrase, count in audit["duplicates"][:10]:
        print(f"    {count}x {phrase}")
    print("  short_phrase_warnings:")
    if audit["short_phrases"]:
        for key, phrase in audit["short_phrases"][:10]:
            print(f"    {key}: {phrase}")
    else:
        print("    none")
    print(f"Improved suspicious/dangerous detections: {improved_ids[:10]}")
    print(f"False-positive protections held: {protected_ids[:10]}")

    regression_status = {
        "behavioral_v2": "PASS" if failed == 0 else "FAIL",
        "promo_false_positive": _run_regression_script("evaluate_behavioral_false_positives.py"),
        "dynamic_sandbox": _run_regression_script("evaluate_dynamic_url_sandbox.py"),
    }
    phase_complete = (
        failed == 0
        and not audit["under_covered"]
        and not audit["same_family_duplicates"]
        and all(status == "PASS" for status in regression_status.values())
    )
    print("Quality gate:")
    print(f"  PHASE_4_STATUS: {'COMPLETE' if phase_complete else 'NOT_COMPLETE'}")
    print(f"  total_cases={len(CASES)}")
    print(f"  pass_count={passed}")
    print(f"  fail_count={failed}")
    print(f"  loaded_v2_phrase_count={audit['loaded_v2_phrase_count']}")
    print(f"  undercovered_families={undercovered}")
    print(
        "  duplicate_summary="
        f"same_family:{len(audit['same_family_duplicates'])},"
        f"cross_family:{len(audit['cross_family_duplicates'])}"
    )
    print("  dialect_coverage=" + ", ".join(
        f"{dialect}:{ok}/{total}" for dialect, (total, ok) in sorted(dialect_counts.items())
    ))
    print("  sector_coverage=" + ", ".join(
        f"{sector}:{ok}/{total}" for sector, (total, ok) in sorted(sector_counts.items())
    ))
    print("  regression_status:")
    for name, status in regression_status.items():
        print(f"    {name}: {status}")
    return 0 if phase_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
