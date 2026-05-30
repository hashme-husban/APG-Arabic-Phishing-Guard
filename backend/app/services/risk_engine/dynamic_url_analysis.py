"""
APG Risk Intelligence Engine v1 — Dynamic URL Analysis

Provides a sandboxed dynamic URL analysis layer backed by Playwright.

Phase 2A: stub only (status="disabled" / "not_implemented").
Phase 2B: real Playwright sandbox in shadow mode — scoring unchanged.
Phase 2C: conservative evidence integration — suspicious_context only, max +28 pts.
Phase 2D: delayed observation window, time simulation prep, runtime signal detection.

Phase 2D additions:
  - Delayed observation: DynamicURLAnalysisResult carries before/after diffs.
  - New runtime signals: delayed_redirect, sensitive_form_appeared, title_changed,
    multi_stage_navigation — all mapped to conservative suspicious_context evidence.
  - Optional time simulation: Date.now() override (disabled by default).
  - External host list exposed for admin debugging (capped at 20 hosts).

All evidence remains category="suspicious_context". No dangerous_intent.
Max score_delta per Evidence item: _MAX_SINGLE_DELTA = 28.
DYNAMIC_URL_ANALYSIS_ENABLED remains false by default.

Playwright is optional.  If not installed the sandbox returns
status="failed" with error="playwright_not_installed" and the
backend starts and runs normally.

See docs/PHASE2_DYNAMIC_URL_ANALYSIS_PLAN.md for full architecture,
security requirements, and evidence mapping tables.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from .schemas import Evidence

logger = logging.getLogger("apg.dynamic_url_analysis")

# ─── Status literals ──────────────────────────────────────────────────────────

DynamicAnalysisStatus = Literal[
    "disabled",          # feature flag is off (Phase 2A default)
    "not_implemented",   # flag is on but sandbox not available
    "skipped",           # URL passed validation but sandbox deemed unnecessary
    "completed",         # sandbox ran and returned results
    "failed",            # sandbox ran but encountered an error
]


# ─── Signal dataclass ─────────────────────────────────────────────────────────

@dataclass
class DynamicURLSignal:
    """
    A single signal produced by the dynamic sandbox.

    In Phase 2B these are generated but not converted to Evidence (shadow mode).
    Phase 2C will wire them into the scoring pipeline.

    Fields:
      id            — stable identifier (e.g. "dyn_login_form_detected")
      severity      — info / low / medium / high / critical
      score_delta   — advisory contribution (positive = raises risk)
      explanation_ar — Arabic user-facing text
      explanation_en — English text (optional)
      extra         — provider-specific metadata
    """
    id: str
    severity: str
    score_delta: int
    explanation_ar: str
    explanation_en: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class DynamicURLAnalysisResult:
    """
    Structured result from a dynamic URL sandbox run.

    All fields default to safe/empty values.  A disabled or failed result
    never injects unexpected data into the engine.
    """
    url: str = ""
    status: DynamicAnalysisStatus = "disabled"
    final_url: str | None = None
    redirect_chain: list[str] = field(default_factory=list)
    page_title: str | None = None
    has_login_form: bool = False
    has_password_field: bool = False
    has_otp_field: bool = False
    form_count: int = 0
    external_requests: int = 0
    suspicious_requests: int = 0
    external_host_list: list[str] = field(default_factory=list)
    # Phase 2D delayed observation fields
    delayed_url_change: bool = False
    delayed_title_change: bool = False
    delayed_form_change: bool = False
    delayed_sensitive_field_appeared: bool = False
    # Phase 2D time simulation fields
    time_simulation_enabled: bool = False
    simulated_minutes: int = 0
    time_simulation_error: str | None = None
    signals: list[DynamicURLSignal] = field(default_factory=list)
    screenshot_path: str | None = None
    error: str | None = None
    elapsed_ms: float = 0.0
    # Shadow-mode evidence preview (Phase 2): serialised Evidence dicts computed
    # by dynamic_result_to_evidence() but NOT added to the scoring pipeline.
    evidence_preview: list[dict[str, Any]] = field(default_factory=list)
    # Phase 3 scoring metadata — set by service.py when score flag is active.
    # None when flag is off; populated with gate decision when flag is on.
    scoring_gate: dict[str, Any] | None = None
    scored_evidence_summary: dict[str, Any] | None = None
    score_impact_override: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "final_url": self.final_url,
            "redirect_chain": self.redirect_chain,
            "page_title": self.page_title,
            "has_login_form": self.has_login_form,
            "has_password_field": self.has_password_field,
            "has_otp_field": self.has_otp_field,
            "form_count": self.form_count,
            "external_requests": self.external_requests,
            "suspicious_requests": self.suspicious_requests,
            "external_host_list": self.external_host_list,
            # Phase 2D
            "delayed_url_change": self.delayed_url_change,
            "delayed_title_change": self.delayed_title_change,
            "delayed_form_change": self.delayed_form_change,
            "delayed_sensitive_field_appeared": self.delayed_sensitive_field_appeared,
            "time_simulation_enabled": self.time_simulation_enabled,
            "simulated_minutes": self.simulated_minutes,
            "time_simulation_error": self.time_simulation_error,
            "signals": [
                {
                    "id": s.id,
                    "severity": s.severity,
                    "score_delta": s.score_delta,
                    "explanation_ar": s.explanation_ar,
                    "explanation_en": s.explanation_en,
                }
                for s in self.signals
            ],
            "screenshot_path": self.screenshot_path,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "evidence_preview": self.evidence_preview,
            "scoring_gate": self.scoring_gate,
            "scored_evidence_summary": self.scored_evidence_summary,
            "score_impact_override": self.score_impact_override,
        }


# ─── Main entry point ─────────────────────────────────────────────────────────

def analyze_url_dynamically(
    url: str,
    *,
    enabled: bool = False,
    timeout_seconds: int = 10,
    observation_ms: int = 1500,
    time_simulation_enabled: bool = False,
    simulated_minutes: int = 0,
) -> DynamicURLAnalysisResult:
    """
    Run a dynamic analysis of *url* using the Playwright sandbox.

    enabled=False → returns immediately with status="disabled" (no network).
    enabled=True  → runs run_sandbox() with all Phase 2D observation params.

    Synchronous — safe to call from sync FastAPI route handlers (thread pool).
    Must NOT be called from an async context when enabled=True because
    playwright.sync_api creates its own event loop internally.

    See docs/PHASE2_DYNAMIC_URL_ANALYSIS_PLAN.md for full security guarantees.
    """
    t0 = time.monotonic()

    if not enabled:
        return DynamicURLAnalysisResult(
            url=url,
            status="disabled",
            elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    # Lazy import to avoid crashing backend when Playwright is absent
    try:
        from app.services.url_sandbox.playwright_sandbox import run_sandbox
    except Exception as import_exc:
        logger.warning("url_sandbox import failed: %s", import_exc)
        return DynamicURLAnalysisResult(
            url=url,
            status="failed",
            error=f"import_error:{type(import_exc).__name__}",
            elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    raw = run_sandbox(
        url,
        timeout_seconds=timeout_seconds,
        observation_ms=observation_ms,
        time_simulation_enabled=time_simulation_enabled,
        simulated_minutes=simulated_minutes,
    )

    result = DynamicURLAnalysisResult(
        url=raw.get("url", url),
        status=raw.get("status", "failed"),
        final_url=raw.get("final_url"),
        redirect_chain=raw.get("redirect_chain") or [],
        page_title=raw.get("page_title"),
        has_login_form=bool(raw.get("has_login_form")),
        has_password_field=bool(raw.get("has_password_field")),
        has_otp_field=bool(raw.get("has_otp_field")),
        form_count=int(raw.get("form_count") or 0),
        external_requests=int(raw.get("external_requests") or 0),
        suspicious_requests=int(raw.get("suspicious_requests") or 0),
        external_host_list=list(raw.get("external_host_list") or []),
        # Phase 2D delayed observation
        delayed_url_change=bool(raw.get("delayed_url_change")),
        delayed_title_change=bool(raw.get("delayed_title_change")),
        delayed_form_change=bool(raw.get("delayed_form_change")),
        delayed_sensitive_field_appeared=bool(raw.get("delayed_sensitive_field_appeared")),
        # Phase 2D time simulation
        time_simulation_enabled=bool(raw.get("time_simulation_enabled")),
        simulated_minutes=int(raw.get("simulated_minutes") or 0),
        time_simulation_error=raw.get("time_simulation_error"),
        screenshot_path=None,  # no screenshots
        error=raw.get("error"),
        elapsed_ms=float(raw.get("elapsed_ms") or 0.0),
    )

    if result.status == "completed":
        result.signals = _generate_signals(result)

    return result


# ─── Signal generation (advisory — for admin debug output) ───────────────────

def _generate_signals(result: "DynamicURLAnalysisResult") -> list[DynamicURLSignal]:
    """
    Produce advisory DynamicURLSignal items from sandbox observations.

    These signals appear in the admin explain endpoint debug output.
    The score_deltas here are advisory (uncalibrated); actual scoring uses the
    conservative Evidence items produced by dynamic_result_to_evidence().
    """
    signals: list[DynamicURLSignal] = []

    if result.has_password_field:
        signals.append(DynamicURLSignal(
            id="dyn_password_field_detected",
            severity="high",
            score_delta=55,
            explanation_ar="الصفحة تحتوي على حقل كلمة مرور — مؤشر قوي على صفحة تصيّد محتملة.",
            explanation_en="Page contains a password input field.",
        ))

    if result.has_login_form and not result.has_password_field:
        signals.append(DynamicURLSignal(
            id="dyn_login_form_detected",
            severity="medium",
            score_delta=45,
            explanation_ar="الصفحة تحتوي على نموذج تسجيل دخول.",
            explanation_en="Page contains a login/authentication form.",
        ))

    if result.has_otp_field:
        signals.append(DynamicURLSignal(
            id="dyn_otp_field_detected",
            severity="medium",
            score_delta=50,
            explanation_ar="الصفحة تحتوي على حقل رمز تحقق (OTP/PIN).",
            explanation_en="Page contains an OTP or verification code field.",
        ))

    chain_len = len(result.redirect_chain)
    if chain_len >= 3:
        signals.append(DynamicURLSignal(
            id="dyn_redirect_chain_long",
            severity="low",
            score_delta=30,
            explanation_ar=f"الرابط يمر عبر {chain_len} تحويلات — سلوك غير معتاد.",
            explanation_en=f"URL passed through {chain_len} intermediate redirects.",
        ))

    if result.final_url:
        from urllib.parse import urlparse
        orig_domain = _reg_domain((urlparse(result.url).hostname or "").lower())
        final_domain = _reg_domain((urlparse(result.final_url).hostname or "").lower())
        if orig_domain and final_domain and orig_domain != final_domain:
            signals.append(DynamicURLSignal(
                id="dyn_redirect_to_different_domain",
                severity="medium",
                score_delta=40,
                explanation_ar="الرابط يعيد التوجيه إلى نطاق مختلف عن النطاق الأصلي.",
                explanation_en="URL redirects to a different registered domain.",
            ))

    if result.suspicious_requests >= 3:
        signals.append(DynamicURLSignal(
            id="dyn_suspicious_external_requests",
            severity="low",
            score_delta=35,
            explanation_ar=f"الصفحة تُحمّل سكريبتات أو طلبات بيانات من {result.suspicious_requests} جهات خارجية.",
            explanation_en=f"Page makes active requests (scripts/XHR/fetch) to {result.suspicious_requests} external domains.",
        ))

    # ── Phase 2D advisory signals ──────────────────────────────────────────────

    if result.delayed_url_change:
        signals.append(DynamicURLSignal(
            id="dyn_delayed_redirect_detected",
            severity="medium",
            score_delta=16,
            explanation_ar="الرابط غيّر وجهته بعد تحميل الصفحة — تحويل مؤجل عبر JavaScript أو Meta-Refresh.",
            explanation_en="URL destination changed after page load — JS or meta-refresh delayed redirect.",
        ))

    if result.delayed_sensitive_field_appeared:
        signals.append(DynamicURLSignal(
            id="dyn_sensitive_form_appeared_after_delay",
            severity="medium",
            score_delta=18,
            explanation_ar="حقل كلمة مرور أو رمز تحقق ظهر في الصفحة بعد تحميلها — سلوك مشبوه.",
            explanation_en="Password or OTP field appeared after initial page load — delayed form injection.",
        ))

    if result.delayed_title_change:
        signals.append(DynamicURLSignal(
            id="dyn_title_changed_after_load",
            severity="low",
            score_delta=6,
            explanation_ar="عنوان الصفحة تغيّر بعد التحميل الأولي.",
            explanation_en="Page title changed after initial load.",
        ))

    # Multi-stage navigation: long chain OR JS-driven redirect after load
    if len(result.redirect_chain) >= 3 or result.delayed_url_change:
        signals.append(DynamicURLSignal(
            id="dyn_multi_stage_navigation",
            severity="medium",
            score_delta=14,
            explanation_ar="الصفحة تستخدم تنقلاً متعدد المراحل — تسلسل تحويلات غير عادي.",
            explanation_en="Page uses multi-stage navigation — unusually long redirect or delayed URL change sequence.",
        ))

    return signals


def _reg_domain(hostname: str) -> str:
    """Return last-two-label registered domain."""
    parts = [p for p in hostname.strip(".").split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname


# ─── Evidence conversion (Phase 2C — conservative scoring) ───────────────────

# Intents that indicate a safe/expected context; dynamic evidence is suppressed
# for these unless alarming signals (domain change, OTP, suspicious requests,
# brand impersonation) are present.
_SAFE_INTENTS: frozenset[str] = frozenset({
    "security_advice",
    "otp_code",
    "advertisement",
    "service_notice",
    "transactional",
})

# Phase 2C max score_delta cap — no single evidence item may exceed this.
_MAX_SINGLE_DELTA: int = 28


def dynamic_result_to_evidence(
    result: DynamicURLAnalysisResult,
    *,
    url_verdict: str = "unknown",
    message_intent: str = "unknown",
    is_trusted_domain: bool = False,
    has_brand_impersonation: bool = False,
) -> list[Evidence]:
    """
    Convert a DynamicURLAnalysisResult into Evidence items for the risk engine.

    Phase 2C conservative mapping:

      Evidence.id                       | severity | score_delta | condition
      ----------------------------------|----------|-------------|-------------------------------
      dyn_redirect_chain_observed       | low      | +10         | redirect_chain length >= 2
      dyn_final_domain_changed          | medium   | +14         | final host != original host
      dyn_login_form_detected           | low      | +8          | has_login_form (suppressed for trusted/clean)
      dyn_password_field_detected       | medium   | +10         | has_password_field (suppressed for trusted/clean)
      dyn_otp_field_detected            | medium   | +16         | has_otp_field
      dyn_suspicious_external_requests  | medium   | +12         | suspicious_requests > 0
      dyn_multi_signal_phishing_surface | high     | +25         | 3 signal groups co-present

    Guardrails (suppress or reduce evidence):
      1. Trusted domain: login/password evidence suppressed (or capped at +5).
      2. Clean URL verdict: login/password/form/redirect evidence skipped unless
         alarming signals (domain change, OTP, suspicious requests) present.
      3. Safe intent: all evidence skipped unless alarming signals present.
      4. Failure never penalises: non-completed status → always [].

    No evidence item is category="dangerous_intent" in Phase 2C.
    No single score_delta exceeds _MAX_SINGLE_DELTA (28).

    Args:
        result:                 Dynamic sandbox result.
        url_verdict:            URLIntelligence.verdict ("clean"/"suspicious"/…)
        message_intent:         Detected intent label from intent_detector.
        is_trusted_domain:      True if the primary URL domain is on the trusted list.
        has_brand_impersonation: True if url_intel flagged brand impersonation.
    """
    if result.status != "completed":
        return []

    from urllib.parse import urlparse

    orig_host = (urlparse(result.url).hostname or "").lower()
    final_host = (
        (urlparse(result.final_url).hostname or "").lower()
        if result.final_url
        else orig_host
    )
    final_domain_changed = bool(
        result.final_url
        and _reg_domain(orig_host) != _reg_domain(final_host)
        and _reg_domain(orig_host)  # ignore if original has no registered domain
    )

    # "Alarming" signals that override safe-context and clean-verdict guards.
    alarming = (
        final_domain_changed
        or result.has_otp_field
        or result.suspicious_requests > 0
        or has_brand_impersonation
    )

    # Guard 3 — safe intent: skip all evidence unless alarming signals present.
    if message_intent in _SAFE_INTENTS and not alarming:
        return []

    # Guard 2 — clean verdict: skip most evidence unless alarming signals present.
    clean_suppressed = url_verdict == "clean" and not alarming

    # Shared extra dict attached to every evidence item for admin visibility.
    extra_base: dict = {
        "dynamic_analysis": True,
        "final_url": result.final_url,
        "page_title": result.page_title,
        "redirect_count": len(result.redirect_chain),
        "form_count": result.form_count,
        "suspicious_request_count": result.suspicious_requests,
    }

    evidence: list[Evidence] = []

    # Track which signal groups fired (for multi-signal compound below).
    has_redirect_signal = False
    has_domain_change_signal = False
    has_credential_signal = False   # login form / password / OTP
    has_suspicious_req_signal = False

    # ── 1. Redirect chain ──────────────────────────────────────────────────────
    if len(result.redirect_chain) >= 2 and not clean_suppressed:
        has_redirect_signal = True
        evidence.append(Evidence(
            id="dyn_redirect_chain_observed",
            category="suspicious_context",
            severity="low",
            score_delta=10,
            confidence=0.70,
            matched_text=result.url,
            explanation_ar=(
                f"الرابط يمر عبر {len(result.redirect_chain)} تحويلات متتالية — سلوك غير معتاد."
            ),
            explanation_en=(
                f"URL passed through {len(result.redirect_chain)} intermediate redirects."
            ),
            extra=extra_base,
        ))

    # ── 2. Final domain changed ────────────────────────────────────────────────
    if final_domain_changed:
        has_domain_change_signal = True
        evidence.append(Evidence(
            id="dyn_final_domain_changed",
            category="suspicious_context",
            severity="medium",
            score_delta=14,
            confidence=0.80,
            matched_text=result.final_url or result.url,
            explanation_ar="الرابط يعيد التوجيه إلى نطاق مختلف عن النطاق الأصلي.",
            explanation_en=(
                f"URL redirects from {_reg_domain(orig_host)} to a different registered domain."
            ),
            extra=extra_base,
        ))

    # ── 3. Login form (suppressed for trusted domains and clean verdict) ───────
    if result.has_login_form and not clean_suppressed:
        has_credential_signal = True
        # Guard 1 — trusted domain: cap score_delta at 5 instead of suppressing
        # outright (a trusted site with a login form is normal, but may still be
        # relevant when combined with other signals).
        delta = 5 if is_trusted_domain else 8
        if not (message_intent in _SAFE_INTENTS and not alarming):
            evidence.append(Evidence(
                id="dyn_login_form_detected",
                category="suspicious_context",
                severity="low",
                score_delta=delta,
                confidence=0.60,
                matched_text=result.url,
                explanation_ar="الصفحة تحتوي على نموذج تسجيل دخول.",
                explanation_en="Page contains a login/authentication form.",
                extra=extra_base,
            ))

    # ── 4. Password field (suppressed for trusted + clean; capped for trusted) ─
    if result.has_password_field and not clean_suppressed:
        has_credential_signal = True
        # Guard 1 — trusted domain: suppressed entirely (login pages are expected).
        if not is_trusted_domain:
            if not (message_intent in _SAFE_INTENTS and not alarming):
                evidence.append(Evidence(
                    id="dyn_password_field_detected",
                    category="suspicious_context",
                    severity="medium",
                    score_delta=10,
                    confidence=0.65,
                    matched_text=result.url,
                    explanation_ar="الصفحة تحتوي على حقل إدخال كلمة مرور.",
                    explanation_en="Page contains a password input field.",
                    extra=extra_base,
                ))
        else:
            # Trusted domain with a password field: still mark credential signal
            # for multi-signal tracking but add no evidence item.
            pass

    # ── 5. OTP field (not suppressed by trusted domain — OTP phishing is common) ─
    if result.has_otp_field:
        has_credential_signal = True
        evidence.append(Evidence(
            id="dyn_otp_field_detected",
            category="suspicious_context",
            severity="medium",
            score_delta=16,
            confidence=0.75,
            matched_text=result.url,
            explanation_ar="الصفحة تحتوي على حقل رمز تحقق (OTP/PIN).",
            explanation_en="Page contains an OTP or verification code field.",
            extra=extra_base,
        ))

    # ── 6. Suspicious external requests ───────────────────────────────────────
    if result.suspicious_requests > 0 and not clean_suppressed:
        has_suspicious_req_signal = True
        evidence.append(Evidence(
            id="dyn_suspicious_external_requests",
            category="suspicious_context",
            severity="medium",
            score_delta=12,
            confidence=0.65,
            matched_text=result.url,
            explanation_ar=(
                f"الصفحة تُحمّل موارد نشطة من {result.suspicious_requests} مصدر خارجي."
            ),
            explanation_en=(
                f"Page makes active script/XHR/fetch requests to {result.suspicious_requests} external host(s)."
            ),
            extra=extra_base,
        ))

    # ── 7. Multi-signal compound (all three groups co-present) ────────────────
    # Condition: (redirect OR domain-change) AND (login/password/OTP) AND suspicious-requests
    if (
        (has_redirect_signal or has_domain_change_signal)
        and has_credential_signal
        and has_suspicious_req_signal
    ):
        evidence.append(Evidence(
            id="dyn_multi_signal_phishing_surface",
            category="suspicious_context",
            severity="high",
            score_delta=25,
            confidence=0.82,
            matched_text=result.final_url or result.url,
            explanation_ar=(
                "الصفحة تجمع عدة مؤشرات مشبوهة: تحويلات متعددة، نموذج بيانات حساسة، "
                "وطلبات خارجية — نمط شائع في صفحات التصيّد."
            ),
            explanation_en=(
                "Page exhibits multiple phishing surface signals: redirects, "
                "credential form, and suspicious external requests."
            ),
            extra=extra_base,
        ))

    # ── Phase 2D runtime signals ───────────────────────────────────────────────

    # 8. Delayed URL change (JS/meta-refresh redirect after domcontentloaded)
    # Trusted domain guard: delayed redirects on trusted domains are common (SSO,
    # analytics). Only generate evidence if domain ALSO changed, or if not trusted.
    if result.delayed_url_change and not clean_suppressed:
        _trusted_delayed = is_trusted_domain and not final_domain_changed
        if not _trusted_delayed and not (message_intent in _SAFE_INTENTS and not alarming):
            evidence.append(Evidence(
                id="dyn_delayed_redirect_detected",
                category="suspicious_context",
                severity="medium",
                score_delta=16,
                confidence=0.70,
                matched_text=result.url,
                explanation_ar=(
                    "الرابط غيّر وجهته بعد تحميل الصفحة — "
                    "تحويل مؤجل عبر JavaScript أو Meta-Refresh."
                ),
                explanation_en="URL destination changed after page load — JS or meta-refresh delayed redirect.",
                extra=extra_base,
            ))

    # 9. Sensitive form appeared after delay (dynamic form injection)
    # NOT suppressed by trusted domain — dynamic credential-form injection is alarming
    # even on seemingly legitimate domains.
    if result.delayed_sensitive_field_appeared:
        if not (message_intent in _SAFE_INTENTS and not alarming):
            evidence.append(Evidence(
                id="dyn_sensitive_form_appeared_after_delay",
                category="suspicious_context",
                severity="medium",
                score_delta=18,
                confidence=0.78,
                matched_text=result.url,
                explanation_ar=(
                    "حقل كلمة مرور أو رمز تحقق ظهر في الصفحة بعد تحميلها — "
                    "حقن نموذج مؤجل."
                ),
                explanation_en="Password or OTP field appeared after initial page load — delayed form injection.",
                extra=extra_base,
            ))

    # 10. Title changed after load (weak signal — suppressed aggressively)
    # Only generated when: not trusted, not clean, not safe intent, and alarming context.
    if result.delayed_title_change and alarming and not clean_suppressed and not is_trusted_domain:
        if not (message_intent in _SAFE_INTENTS and not alarming):
            evidence.append(Evidence(
                id="dyn_title_changed_after_load",
                category="suspicious_context",
                severity="low",
                score_delta=6,
                confidence=0.55,
                matched_text=result.url,
                explanation_ar="عنوان الصفحة تغيّر بعد التحميل الأولي.",
                explanation_en="Page title changed after initial page load.",
                extra=extra_base,
            ))

    # 11. Multi-stage navigation
    # Triggered by redirect_chain >= 3 OR delayed URL change.
    # Suppressed for trusted + clean unless alarming.
    _has_multi_stage = len(result.redirect_chain) >= 3 or result.delayed_url_change
    if _has_multi_stage and not clean_suppressed:
        _trusted_multi = is_trusted_domain and not alarming
        if not _trusted_multi and not (message_intent in _SAFE_INTENTS and not alarming):
            evidence.append(Evidence(
                id="dyn_multi_stage_navigation",
                category="suspicious_context",
                severity="medium",
                score_delta=14,
                confidence=0.65,
                matched_text=result.url,
                explanation_ar=(
                    "الصفحة تستخدم تنقلاً متعدد المراحل — "
                    "تسلسل تحويلات أو تغييرات URL غير عادي."
                ),
                explanation_en="Page uses multi-stage navigation — unusually long redirect or delayed URL change sequence.",
                extra=extra_base,
            ))

    return evidence
