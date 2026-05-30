"""
APG Dynamic URL Sandbox — Regression & Evaluation Pack (Phase 3.3)
==================================================================
Compares risk engine output across three operating modes using mocked
sandbox results and synthetic test messages. No outbound network calls.

Modes
-----
  0  disabled : DYNAMIC_URL_ANALYSIS_ENABLED=false
  1  shadow   : DYNAMIC_URL_ANALYSIS_ENABLED=true, SCORE_ENABLED=false
  2  scoring  : DYNAMIC_URL_ANALYSIS_ENABLED=true, SCORE_ENABLED=true

Pass criteria (checked automatically)
--------------------------------------
  P1  shadow_score  == disabled_score      (shadow never changes score)
  P2  shadow_class  == disabled_class      (shadow never changes class)
  P3  gate_blocked  → scoring_score == disabled_score
  P4  SAFE category → scoring_class != "dangerous"
  P5  scoring_score  <= 100               (score cannot exceed ceiling)
  P6  disabled/shadow score_impact == "none_shadow_mode"
  P7  case-specific gate expectation, when declared
  P8  expected no-delta cases remain unchanged
  P9  expected visible-delta cases increase in scoring mode
  P10 scoring mode never lowers the disabled-mode score

Usage
-----
  cd backend
  python scripts/evaluate_dynamic_url_sandbox.py
  python scripts/evaluate_dynamic_url_sandbox.py --failures-only
  python scripts/evaluate_dynamic_url_sandbox.py --verbose
  python scripts/evaluate_dynamic_url_sandbox.py --json reports/sandbox_eval.json

Exit codes
----------
  0  all cases PASS
  1  one or more cases FAIL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── UTF-8 output (Arabic text on Windows) ────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ── Engine imports ────────────────────────────────────────────────────────────
import app.services.risk_engine.service as _svc_mod  # noqa: E402
from app.services.risk_engine.dynamic_url_analysis import DynamicURLAnalysisResult
from app.services.risk_engine.service import RiskEngineV1Service
from app.services.risk_engine.compatibility import _build_dynamic_url_debug

# Singleton service — created once for the whole evaluation run.
_SVC = RiskEngineV1Service()

_VERDICT_TO_CLASS = {
    "allow": "safe",
    "caution": "suspicious",
    "warn": "suspicious",
    "block": "dangerous",
}
_CLASS_ABBR = {"safe": "S", "suspicious": "W", "dangerous": "D"}


# ── Sandbox result factories ──────────────────────────────────────────────────
# Each factory takes the URL string extracted by the engine and returns a
# DynamicURLAnalysisResult that simulates a particular sandbox observation.
# "evil-redirect.test" is used as the redirect target for domain-change cases.

def _sb_clean(url: str) -> DynamicURLAnalysisResult:
    """No suspicious indicators — completed cleanly."""
    return DynamicURLAnalysisResult(url=url, status="completed")


def _sb_login_only(url: str) -> DynamicURLAnalysisResult:
    """Login form present, no other signals."""
    return DynamicURLAnalysisResult(
        url=url, status="completed", has_login_form=True, form_count=1,
    )


def _sb_password_domain_change(url: str) -> DynamicURLAnalysisResult:
    """Password field AND domain changed after redirect."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_password_field=True, has_login_form=True, form_count=1,
        final_url="http://evil-redirect.test/harvester",
        redirect_chain=[url, "http://evil-redirect.test/harvester"],
    )


def _sb_otp_field(url: str) -> DynamicURLAnalysisResult:
    """OTP/PIN field detected on page."""
    return DynamicURLAnalysisResult(
        url=url, status="completed", has_otp_field=True, form_count=1,
    )


def _sb_otp_domain_change(url: str) -> DynamicURLAnalysisResult:
    """OTP field AND domain changed after redirect."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_otp_field=True, form_count=1,
        final_url="http://evil-redirect.test/otp",
        redirect_chain=[url, "http://evil-redirect.test/otp"],
    )


def _sb_delayed_domain_change(url: str) -> DynamicURLAnalysisResult:
    """JS/meta-refresh delayed redirect to a different domain."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        delayed_url_change=True,
        final_url="http://evil-redirect.test/harvester",
        redirect_chain=[url, "http://evil-redirect.test/harvester"],
    )


def _sb_password_suspicious_reqs(url: str) -> DynamicURLAnalysisResult:
    """Password field + 3 suspicious external script requests."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_password_field=True, has_login_form=True, form_count=1,
        suspicious_requests=3,
        external_host_list=["tracker1.test", "tracker2.test", "tracker3.test"],
    )


def _sb_login_suspicious_reqs(url: str) -> DynamicURLAnalysisResult:
    """Login form + suspicious external requests, no password field."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_login_form=True, form_count=2,
        suspicious_requests=3,
        external_host_list=["track.test", "analytics-inj.test", "beacon.test"],
    )


def _sb_otp_login_field(url: str) -> DynamicURLAnalysisResult:
    """OTP/PIN field detected inside a login form."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_otp_field=True, has_login_form=True, form_count=1,
    )


def _sb_delayed_login_domain_change(url: str) -> DynamicURLAnalysisResult:
    """Delayed redirect to a different domain from a page with a login form."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_login_form=True, form_count=1,
        delayed_url_change=True,
        final_url="http://evil-redirect.test/harvester",
        redirect_chain=[url, "http://evil-redirect.test/harvester"],
    )


def _sb_password_domain_change_external(url: str) -> DynamicURLAnalysisResult:
    """Password + domain change + external requests for visible borderline delta."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_password_field=True, has_login_form=True, form_count=1,
        suspicious_requests=3,
        external_host_list=["asset-one.test", "asset-two.test", "asset-three.test"],
        final_url="http://evil-redirect.test/harvester",
        redirect_chain=[url, "http://evil-redirect.test/harvester"],
    )


def _sb_otp_domain_change_external(url: str) -> DynamicURLAnalysisResult:
    """OTP + domain change + external requests for visible borderline delta."""
    return DynamicURLAnalysisResult(
        url=url, status="completed",
        has_otp_field=True, has_login_form=True, form_count=1,
        suspicious_requests=3,
        external_host_list=["asset-one.test", "asset-two.test", "asset-three.test"],
        final_url="http://evil-redirect.test/otp",
        redirect_chain=[url, "http://evil-redirect.test/otp"],
    )


# ── Test case definition ──────────────────────────────────────────────────────

@dataclass
class EvalCase:
    id: int
    category: str           # SAFE | SUSPICIOUS | DANGEROUS
    label: str
    text: str
    mock_url: dict | None   # {domain: verdict} for URL reputation override
    # callable(url) -> DynamicURLAnalysisResult, or None (no URL in message)
    sandbox: Any
    # Pass rules to enforce for this case
    enforce_safe_not_dangerous: bool = True     # P4: SAFE cases only
    enforce_gate_blocked_no_delta: bool = True  # P3: always
    phase: str = "BASELINE"
    expected_gate_allowed: bool | None = None
    expect_no_delta: bool = False
    expect_positive_delta: bool = False
    note: str = ""


# ── Synthetic test cases ──────────────────────────────────────────────────────
# All domains use reserved TLDs (.test / .invalid) — no real URLs.

CASES: list[EvalCase] = [

    # ── SAFE: must NOT become dangerous due to sandbox alone ──────────────────

    EvalCase(
        id=1, category="SAFE", label="safe_advertisement",
        text="احصل على خصم 30% على جميع المنتجات! زر موقعنا https://safe-shop.test/deals",
        mock_url={"safe-shop.test": "clean"},
        sandbox=_sb_clean,
    ),
    EvalCase(
        id=2, category="SAFE", label="security_awareness",
        text=(
            "تنبيه أمني: لا تشارك رمز التحقق مع أحد. "
            "البنك لن يطلب كلمة المرور أبداً. "
            "للمزيد: https://secure-tips.test/info"
        ),
        mock_url={"secure-tips.test": "clean"},
        sandbox=_sb_clean,
    ),
    EvalCase(
        id=3, category="SAFE", label="otp_delivery_no_url",
        text="رمز التحقق الخاص بك هو 847291. صالح لمدة 5 دقائق. لا تشاركه.",
        mock_url=None,
        sandbox=None,   # no URL in message — sandbox not invoked
    ),
    EvalCase(
        id=4, category="SAFE", label="casual_link",
        text="أهلاً! إليك الملف الذي طلبته https://files-share.test/doc123",
        mock_url={"files-share.test": "clean"},
        sandbox=_sb_clean,
    ),
    EvalCase(
        id=5, category="SAFE", label="official_service_notice",
        text=(
            "تم تجديد اشتراكك في خدمة الإنترنت بنجاح. "
            "المبلغ: 45 دينار. https://telecom-official.test/receipt"
        ),
        mock_url={"telecom-official.test": "clean"},
        sandbox=_sb_clean,
    ),
    EvalCase(
        id=6, category="SAFE", label="newsletter_promo",
        text="عرض حصري لعملائنا المميزين! خصم 50% على طلبك التالي. https://promo-shop.test/offer",
        mock_url={"promo-shop.test": "clean"},
        sandbox=_sb_clean,
    ),
    EvalCase(
        id=7, category="SAFE", label="plain_login_no_context",
        text="يرجى تسجيل الدخول إلى حسابك https://account-portal.test/signin",
        mock_url={"account-portal.test": "clean"},
        # Login form, clean URL → evidence suppressed by clean_suppressed guard.
        # Gate should block due to no_evidence.
        sandbox=_sb_login_only,
    ),
    EvalCase(
        id=8, category="SAFE", label="contact_harmless_link",
        text="مرحباً! إليك صور الحفل: https://photo-album.test/gallery",
        mock_url={"photo-album.test": "clean"},
        sandbox=_sb_clean,
    ),

    # ── SUSPICIOUS: caution or warn expected; safe-to-dangerous rule relaxed ──

    EvalCase(
        id=9, category="SUSPICIOUS", label="login_url_only",
        text="https://update-portal.test/login?session=abc123",
        mock_url=None,
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=10, category="SUSPICIOUS", label="short_url_unknown",
        text="تحقق من هذا الرابط: https://go.quicklink.test/xyz",
        mock_url=None,
        sandbox=_sb_clean,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=11, category="SUSPICIOUS", label="unknown_domain_login_page",
        text="قم بتسجيل الدخول لتحديث بياناتك https://not-your-bank.test/login",
        mock_url=None,
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=12, category="SUSPICIOUS", label="financial_update_suspicious_url",
        text="حسابك يحتاج تحديثاً عاجلاً. انقر هنا: https://update-bank.test/verify",
        mock_url={"update-bank.test": "suspicious"},
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=13, category="SUSPICIOUS", label="delivery_fee_url",
        text="تم إيقاف شحنتك. لاستلامها يرجى دفع 1.5 دينار: https://delivery-fee.test/pay",
        mock_url=None,
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=14, category="SUSPICIOUS", label="telecom_suspension_url",
        text="سيتم إيقاف خدماتك خلال 24 ساعة. قم بالتحديث: https://telecom-verify.test/update",
        mock_url=None,
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=15, category="SUSPICIOUS", label="government_fee_url",
        text="مخالفة مرورية بانتظارك. ادفع 35 دينار عبر: https://gov-fines.test/traffic",
        mock_url=None,
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),

    # ── DANGEROUS: high risk; score may increase when gate allows ─────────────

    EvalCase(
        id=16, category="DANGEROUS", label="password_request_url",
        text="شارك كلمة المرور لتأكيد هويتك عبر: https://verify-now.test/confirm",
        mock_url={"verify-now.test": "suspicious"},
        sandbox=_sb_password_domain_change,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=17, category="DANGEROUS", label="otp_request_url",
        text="أرسل رمز التحقق الذي وصلك لإلغاء تجميد حسابك: https://unfreeze-acct.test/otp",
        mock_url={"unfreeze-acct.test": "suspicious"},
        sandbox=_sb_otp_domain_change,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=18, category="DANGEROUS", label="card_cvv_request_url",
        text="أدخل بيانات بطاقتك الائتمانية لتجديد الاشتراك: https://renew-billing.test/card",
        mock_url={"renew-billing.test": "suspicious"},
        sandbox=_sb_login_suspicious_reqs,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=19, category="DANGEROUS", label="bank_account_suspension",
        text="تم تجميد حسابك البنكي. قم بإلغاء التجميد فوراً: https://bank-restore.test/unfreeze",
        mock_url={"bank-restore.test": "suspicious"},
        sandbox=_sb_password_suspicious_reqs,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=20, category="DANGEROUS", label="brand_impersonation_malicious_url",
        text="بنك الأردن: تم رصد نشاط مشبوه على حسابك. تحقق فوراً: https://jordan-bank-verify.test/secure",
        mock_url={"jordan-bank-verify.test": "malicious"},
        sandbox=_sb_password_domain_change,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=21, category="DANGEROUS", label="domain_changed_password_field",
        # Neutral text — relies on sandbox to push score; gate allows via
        # password_field + url_suspicious (suspicious URL verdict).
        text="تحقق من حسابك الآن: https://account-check.test/verify",
        mock_url={"account-check.test": "suspicious"},
        sandbox=_sb_password_domain_change,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=22, category="DANGEROUS", label="otp_field_with_otp_context",
        text="أدخل رمز التحقق لتفعيل حسابك: https://activate-account.test/verify",
        mock_url={"activate-account.test": "suspicious"},
        sandbox=_sb_otp_field,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=23, category="DANGEROUS", label="delayed_redirect_bank_update",
        text="حدّث بياناتك البنكية الآن: https://bank-data-update.test/info",
        mock_url={"bank-data-update.test": "suspicious"},
        sandbox=_sb_delayed_domain_change,
        enforce_safe_not_dangerous=False,
    ),
    EvalCase(
        id=24, category="DANGEROUS", label="suspicious_reqs_bank_login",
        # Adds bank/account context to help gate trigger on login+suspicious reqs
        text="قم بتحديث بيانات حسابك البنكي: https://ctrl-panel.test/admin",
        mock_url={"ctrl-panel.test": "suspicious"},
        sandbox=_sb_password_suspicious_reqs,
        enforce_safe_not_dangerous=False,
    ),

    # ── Regression: Phase 3.2 false-positive fix ──────────────────────────
    # R1: Genuine discount promo — word "المميزين" contains "زين" as substring.
    #     Word-boundary fix must prevent brand-impersonation false positive.
    EvalCase(
        id=25, category="SAFE", label="promo_discount_zain_substring",
        text=(
            "عزيزي العميل المميز، احصل على خصم 40% على جميع المنتجات "
            "لعملائنا المميزين. https://discount-offers.test/sale"
        ),
        mock_url={"discount-offers.test": "clean"},
        sandbox=_sb_clean,
    ),
    # R2: Fake prize phishing with credential update link — must remain dangerous/suspicious.
    EvalCase(
        id=26, category="SUSPICIOUS", label="fake_prize_credential_link",
        text=(
            "تهانينا! لقد ربحت جائزة خاصة. "
            "سجّل دخولك وحدّث بياناتك للمطالبة بها: "
            "https://prize-claim.test/login"
        ),
        mock_url=None,
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),
    # R3: Promo referencing Zain brand on a non-official domain with login path
    #     — real impersonation, brand name appears as a standalone word.
    EvalCase(
        id=27, category="DANGEROUS", label="zain_impersonation_promo_login",
        text=(
            "رسالة من زين: تم تقييد حسابك، سجّل دخولك لإعادة التفعيل: "
            "https://zain-account-portal.test/login"
        ),
        mock_url={"zain-account-portal.test": "suspicious"},
        sandbox=_sb_login_only,
        enforce_safe_not_dangerous=False,
    ),

    # ── Borderline: Phase 3.3 dynamic sandbox benefit probes ───────────────
    # These cases exercise safe/caution/warn static outcomes where possible.
    # If static analysis already reaches dangerous, the row documents that the
    # sandbox delta is not visible without changing production scoring logic.
    EvalCase(
        id=28, category="SUSPICIOUS", label="borderline_weak_password_domain",
        text="يرجى المتابعة من هنا https://account-review.test/start",
        mock_url=None,
        sandbox=_sb_password_domain_change,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        note="Required #1: weak text + password field + final domain changed.",
    ),
    EvalCase(
        id=29, category="SUSPICIOUS", label="borderline_zain_url_password",
        text="https://zain-login-review.test",
        mock_url={"zain-login-review.test": "clean"},
        sandbox=_sb_password_domain_change,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        note=(
            "Required #2: exact URL-only Zain impersonation case; static URL "
            "logic already treats this surface as dangerous."
        ),
    ),
    EvalCase(
        id=30, category="SUSPICIOUS", label="borderline_account_otp_field",
        text="راجع حالة الحساب من الرابط https://verify-account.test",
        mock_url={"verify-account.test": "clean"},
        sandbox=_sb_otp_login_field,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        note="Required #3: weak account wording + OTP field + login form.",
    ),
    EvalCase(
        id=31, category="SUSPICIOUS", label="borderline_delivery_delayed",
        text="راجع حالة الشحنة من هنا https://delivery-track.test",
        mock_url={"delivery-track.test": "clean"},
        sandbox=_sb_delayed_login_domain_change,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        note="Required #4: delivery wording + delayed redirect + domain change.",
    ),
    EvalCase(
        id=32, category="SUSPICIOUS", label="borderline_gov_password_domain",
        text="يرجى استكمال الطلب https://gov-service-review.test",
        mock_url={"gov-service-review.test": "clean"},
        sandbox=_sb_password_domain_change_external,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        expect_positive_delta=True,
        note=(
            "Required #5: weak government/service wording + password field + "
            "domain change; external requests make the visible score benefit observable."
        ),
    ),
    EvalCase(
        id=33, category="SAFE", label="borderline_plain_login_no_context",
        text="تفضل الرابط https://normal-login.test",
        mock_url={"normal-login.test": "clean"},
        sandbox=_sb_login_only,
        phase="BORDERLINE",
        expected_gate_allowed=False,
        expect_no_delta=True,
        note="Required #6: plain login page with no surrounding risk context.",
    ),
    EvalCase(
        id=34, category="SAFE", label="borderline_safe_promo_login",
        text="عرض خاص لعملائنا، شاهد التفاصيل https://promo-example.test",
        mock_url={"promo-example.test": "clean"},
        sandbox=_sb_login_only,
        phase="BORDERLINE",
        expected_gate_allowed=False,
        expect_no_delta=True,
        note="Required #7: safe promo + login page.",
    ),
    EvalCase(
        id=35, category="SAFE", label="borderline_awareness_no_sensitive",
        text="تنبيه: لا تشارك رمز التحقق مع أي شخص https://awareness-example.test",
        mock_url={"awareness-example.test": "clean"},
        sandbox=_sb_login_only,
        phase="BORDERLINE",
        expected_gate_allowed=False,
        expect_no_delta=True,
        note="Required #8: security advice + login form, no sensitive field.",
    ),
    EvalCase(
        id=36, category="SUSPICIOUS", label="borderline_otp_domain_changed",
        text="أكمل التحقق الآن https://verify-secure.test",
        mock_url={"verify-secure.test": "clean"},
        sandbox=_sb_otp_domain_change_external,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        note=(
            "Required #9: weak OTP theft wording + OTP field + domain change; "
            "current static URL cap can hide final-score movement."
        ),
    ),
    EvalCase(
        id=37, category="SUSPICIOUS", label="borderline_external_login_only",
        text="راجع الطلب https://review-request.test",
        mock_url=None,
        sandbox=_sb_login_suspicious_reqs,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=False,
        expect_no_delta=True,
        note="Required #10: external requests + login form only.",
    ),
    EvalCase(
        id=38, category="SUSPICIOUS", label="borderline_low_static_password_delta",
        text="تابع هنا https://neutral-page.test/a",
        mock_url=None,
        sandbox=_sb_password_domain_change_external,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        expect_positive_delta=True,
        note="Added Phase 3.3 control: low-static password/domain case with visible delta.",
    ),
    EvalCase(
        id=39, category="SUSPICIOUS", label="borderline_low_static_otp_delta",
        text="تابع هنا https://plain-flow.test/a",
        mock_url=None,
        sandbox=_sb_otp_domain_change_external,
        enforce_safe_not_dangerous=False,
        phase="BORDERLINE",
        expected_gate_allowed=True,
        expect_positive_delta=True,
        note="Added Phase 3.3 control: low-static OTP/domain case with visible delta.",
    ),
]


# ── Flag patching helpers ─────────────────────────────────────────────────────

def _set_flags(enabled: bool, score_enabled: bool) -> None:
    """Monkeypatch module-level flag constants in the live service module."""
    _svc_mod._DYNAMIC_URL_ANALYSIS_ENABLED = enabled
    _svc_mod._DYNAMIC_URL_SCORE_ENABLED = score_enabled


def _reset_flags() -> None:
    _set_flags(False, False)


# ── Single-case runner ────────────────────────────────────────────────────────

def _run(case: EvalCase, enabled: bool, score_enabled: bool) -> dict[str, Any]:
    """
    Run one test case with the given flag settings.

    When enabled=True and sandbox is provided, analyze_url_dynamically is
    monkeypatched to return the case's fake sandbox result without any
    outbound network call.
    """
    _set_flags(enabled, score_enabled)

    original_fn = _svc_mod.analyze_url_dynamically
    if enabled and case.sandbox is not None:
        # The lambda receives the URL extracted by url_intelligence so that
        # the sandbox result's .url field matches the engine's primary_url.
        _svc_mod.analyze_url_dynamically = lambda url, **kw: case.sandbox(url)

    try:
        result = _SVC.analyze_full(
            text=case.text,
            mock_url_reputation=case.mock_url,
        )
    finally:
        _svc_mod.analyze_url_dynamically = original_fn

    classification = _VERDICT_TO_CLASS.get(result.verdict, "suspicious")
    dyn = result.dynamic_url_analysis_result
    debug = _build_dynamic_url_debug(dyn)
    gate = (dyn.scoring_gate or {}) if dyn else {}
    scored = (dyn.scored_evidence_summary or {}) if dyn else {}

    return {
        "risk_score": result.risk_score,
        "classification": classification,
        "verdict": result.verdict,
        "score_impact": debug.get("score_impact", "n/a"),
        "gate_allowed": gate.get("allowed", False),
        "gate_reason": gate.get("reason", "n/a"),
        "scored_count": scored.get("count", 0),
        "scored_delta": scored.get("total_delta", 0),
        "scored_ids": scored.get("ids", []),
    }


# ── Pass / fail checker ───────────────────────────────────────────────────────

def _check_pass(
    case: EvalCase,
    r0: dict,   # disabled
    r1: dict,   # shadow
    r2: dict,   # scoring
) -> list[str]:
    """Return list of failure reasons. Empty list = PASS."""
    issues: list[str] = []

    # P1 / P2 — shadow must be identical to disabled
    if r0["risk_score"] != r1["risk_score"]:
        issues.append(
            f"P1_SHADOW_SCORE_CHANGED {r0['risk_score']}->{r1['risk_score']}"
        )
    if r0["classification"] != r1["classification"]:
        issues.append(
            f"P2_SHADOW_CLASS_CHANGED {r0['classification']}->{r1['classification']}"
        )

    # P3 — gate blocked must not change score
    if case.enforce_gate_blocked_no_delta and not r2["gate_allowed"]:
        if r0["risk_score"] != r2["risk_score"]:
            issues.append(
                f"P3_GATE_BLOCKED_BUT_SCORE_CHANGED {r0['risk_score']}->{r2['risk_score']}"
            )

    # P4 — sandbox scoring must not escalate a SAFE-labeled case to dangerous.
    # Check only when static analysis (mode 0) is NOT already dangerous —
    # if the engine already classifies it as dangerous without sandbox, that
    # is a separate concern from sandbox scoring.
    if (
        case.enforce_safe_not_dangerous
        and r0["classification"] != "dangerous"   # wasn't dangerous before sandbox
        and r2["classification"] == "dangerous"   # became dangerous in scoring mode
    ):
        issues.append("P4_SANDBOX_ESCALATED_SAFE_TO_DANGEROUS")

    # P5 — score ceiling
    for mode, r in (("DIS", r0), ("SHA", r1), ("SCO", r2)):
        if r["risk_score"] > 100:
            issues.append(f"P5_SCORE_EXCEEDED_100_{mode}({r['risk_score']})")

    # P6 — score_impact in disabled/shadow must be none_shadow_mode
    if r0["score_impact"] not in ("none_shadow_mode", "n/a"):
        issues.append(f"P6_WRONG_IMPACT_DISABLED({r0['score_impact']})")
    if r1["score_impact"] not in ("none_shadow_mode", "n/a"):
        issues.append(f"P6_WRONG_IMPACT_SHADOW({r1['score_impact']})")

    delta = r2["risk_score"] - r0["risk_score"]

    # Phase 3.3 case-specific expectations. These stay test-only and describe
    # the current conservative gate contract without changing production logic.
    if case.expected_gate_allowed is not None:
        if r2["gate_allowed"] != case.expected_gate_allowed:
            issues.append(
                "P7_GATE_EXPECTATION_MISMATCH "
                f"expected={case.expected_gate_allowed} actual={r2['gate_allowed']}"
            )

    if case.expect_no_delta and delta != 0:
        issues.append(f"P8_EXPECTED_NO_DELTA_BUT_CHANGED {delta:+d}")

    if case.expect_positive_delta and delta <= 0:
        issues.append(f"P9_EXPECTED_POSITIVE_DELTA_BUT_GOT {delta:+d}")

    if delta < 0:
        issues.append(f"P10_SCORING_DECREASED_SCORE {delta:+d}")

    return issues


# ── Table formatting ──────────────────────────────────────────────────────────

_HDR = (
    f"{'ID':>3} {'CAT':10} {'LABEL':32} "
    f"{'DIS':>8} {'SHA':>8} {'SCO':>8} "
    f"{'ΔSCO':>5} {'GATE':5} {'REASON':38} {'IMPACT':30} {'R':4}"
)
_SEP = "-" * len(_HDR)


def _score_str(r: dict) -> str:
    return f"{r['risk_score']:3d}/{_CLASS_ABBR.get(r['classification'], '?')}"


def _print_row(
    case: EvalCase,
    r0: dict, r1: dict, r2: dict,
    issues: list[str],
    failures_only: bool,
) -> None:
    if failures_only and not issues:
        return
    delta = r2["risk_score"] - r0["risk_score"]
    gate_ch = "Y" if r2["gate_allowed"] else "N"
    result = "PASS" if not issues else "FAIL"
    print(
        f"{case.id:>3} {case.category:10} {case.label:32} "
        f"{_score_str(r0):>8} {_score_str(r1):>8} {_score_str(r2):>8} "
        f"{delta:>+5} {gate_ch:5} {r2['gate_reason'][:38]:38} "
        f"{r2['score_impact']:30} {result:4}"
    )
    if issues:
        for iss in issues:
            print(f"    >> {iss}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="APG Dynamic URL Sandbox — Phase 3.1 Regression & Evaluation"
    )
    parser.add_argument(
        "--failures-only", action="store_true",
        help="Print only failing cases in the table",
    )
    parser.add_argument(
        "--json", metavar="PATH",
        help="Write full results to a JSON file",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show scored evidence IDs for scoring-mode rows",
    )
    args = parser.parse_args()

    print("=" * len(_HDR))
    print("APG Dynamic URL Sandbox — Phase 3.3 Regression & Evaluation Pack")
    print(f"Cases: {len(CASES)}  |  Sandbox: mocked (no network)")
    print("=" * len(_HDR))
    print()
    print(_HDR)
    print(_SEP)

    all_rows: list[dict] = []
    passed = failed = 0

    for case in CASES:
        r0 = _run(case, enabled=False, score_enabled=False)   # disabled
        r1 = _run(case, enabled=True,  score_enabled=False)   # shadow
        r2 = _run(case, enabled=True,  score_enabled=True)    # scoring

        issues = _check_pass(case, r0, r1, r2)
        _print_row(case, r0, r1, r2, issues, args.failures_only)

        if args.verbose and r2["scored_count"] > 0:
            print(f"    scored_ids: {r2['scored_ids']}  total_delta=+{r2['scored_delta']}")
        # Advisory: SAFE case the engine already considers dangerous (no sandbox involvement)
        if case.enforce_safe_not_dangerous and r0["classification"] == "dangerous":
            print(f"    NOTE: static analysis already dangerous (score={r0['risk_score']}); sandbox had no effect")

        row = {
            "id": case.id,
            "category": case.category,
            "label": case.label,
            "phase": case.phase,
            "note": case.note,
            "disabled": r0,
            "shadow": r1,
            "scoring": r2,
            "delta": r2["risk_score"] - r0["risk_score"],
            "issues": issues,
            "result": "PASS" if not issues else "FAIL",
        }
        all_rows.append(row)
        if issues:
            failed += 1
        else:
            passed += 1

    print(_SEP)
    print()

    # ── Category summary ──────────────────────────────────────────────────────
    for cat in ("SAFE", "SUSPICIOUS", "DANGEROUS"):
        rows_cat = [r for r in all_rows if r["category"] == cat]
        cat_pass = sum(1 for r in rows_cat if not r["issues"])
        gate_allowed = sum(1 for r in rows_cat if r["scoring"]["gate_allowed"])
        avg_delta = (
            sum(r["delta"] for r in rows_cat) / len(rows_cat) if rows_cat else 0
        )
        print(
            f"  {cat:10}  {len(rows_cat):2} cases  "
            f"{cat_pass:2}/{len(rows_cat)} pass  "
            f"gate_allowed={gate_allowed}  avg_delta={avg_delta:+.1f}"
        )
    print()

    # ── Phase 3.3 borderline summary ────────────────────────────────────────
    borderline_rows = [r for r in all_rows if r["phase"] == "BORDERLINE"]
    visible_delta_rows = [r for r in all_rows if r["delta"] > 0]
    blocked_ok_rows = [
        r for r in borderline_rows
        if not r["scoring"]["gate_allowed"] and r["delta"] == 0 and not r["issues"]
    ]
    borderline_failures = [r for r in borderline_rows if r["issues"]]
    print(
        "PHASE 3.3: "
        f"borderline_added={len(borderline_rows)}  "
        f"visible_delta={len(visible_delta_rows)}  "
        f"gate_blocked_correctly={len(blocked_ok_rows)}  "
        f"borderline_failures={len(borderline_failures)}"
    )
    if visible_delta_rows:
        visible_ids = ", ".join(
            f"{r['id']}:{r['label']}({r['delta']:+d})"
            for r in visible_delta_rows
        )
        print(f"  Visible sandbox deltas: {visible_ids}")
    if blocked_ok_rows:
        blocked_ids = ", ".join(f"{r['id']}:{r['label']}" for r in blocked_ok_rows)
        print(f"  Gate blocked as expected: {blocked_ids}")
    print()

    # ── Overall summary ───────────────────────────────────────────────────────
    print(f"TOTAL: {passed}/{len(CASES)} passed, {failed} failed")

    if failed:
        print("\nFailed cases:")
        for row in all_rows:
            if row["issues"]:
                print(f"  Case {row['id']:2} ({row['label']}): {', '.join(row['issues'])}")

    # ── JSON export ───────────────────────────────────────────────────────────
    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(all_rows, fh, ensure_ascii=False, indent=2)
        print(f"\nJSON results written to {out_path}")

    # Reset flags so this module's side effects are contained
    _reset_flags()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
