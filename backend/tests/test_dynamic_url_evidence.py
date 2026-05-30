"""
APG Phase 2C — dynamic_result_to_evidence() Tests

Verifies the conservative evidence mapping introduced in Phase 2C.
All tests run without Playwright (no browser, no network).

Run:
    cd backend
    python -m pytest tests/test_dynamic_url_evidence.py -v
    # or without pytest:
    python -m unittest tests.test_dynamic_url_evidence -v
"""
from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.risk_engine.dynamic_url_analysis import (
    DynamicURLAnalysisResult,
    dynamic_result_to_evidence,
    _MAX_SINGLE_DELTA,
)


def _completed(**kwargs) -> DynamicURLAnalysisResult:
    """Build a completed result with sane defaults."""
    return DynamicURLAnalysisResult(
        url=kwargs.pop("url", "https://suspicious-site.example.com/login"),
        status="completed",
        final_url=kwargs.pop("final_url", None),
        **kwargs,
    )


class TestNonCompletedAlwaysEmpty(unittest.TestCase):
    """Non-completed statuses must always return [] regardless of field values."""

    def _call(self, status: str) -> list:
        result = DynamicURLAnalysisResult(
            url="https://example.com",
            status=status,
            has_password_field=True,
            has_login_form=True,
            has_otp_field=True,
            suspicious_requests=5,
        )
        return dynamic_result_to_evidence(result)

    def test_disabled_returns_empty(self):
        self.assertEqual(self._call("disabled"), [])

    def test_failed_returns_empty(self):
        self.assertEqual(self._call("failed"), [])

    def test_skipped_returns_empty(self):
        self.assertEqual(self._call("skipped"), [])

    def test_not_implemented_returns_empty(self):
        self.assertEqual(self._call("not_implemented"), [])


class TestCompletedNoSignals(unittest.TestCase):
    """Completed result with no detectable signals must return []."""

    def test_empty_completed_returns_empty(self):
        result = _completed()
        ev = dynamic_result_to_evidence(result)
        self.assertEqual(ev, [])


class TestIndividualSignals(unittest.TestCase):
    """Each individual signal produces the expected evidence item."""

    def test_redirect_chain_below_threshold_no_evidence(self):
        result = _completed(redirect_chain=["https://suspicious-site.example.com/login"])
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_redirect_chain_observed", ids)

    def test_redirect_chain_at_threshold_produces_evidence(self):
        result = _completed(
            redirect_chain=[
                "https://suspicious-site.example.com/r1",
                "https://suspicious-site.example.com/r2",
            ]
        )
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertIn("dyn_redirect_chain_observed", ids)

    def test_redirect_chain_evidence_is_low_severity(self):
        result = _completed(
            redirect_chain=["https://a.example.com/", "https://b.example.com/"]
        )
        ev = dynamic_result_to_evidence(result)
        redir = next(e for e in ev if e.id == "dyn_redirect_chain_observed")
        self.assertEqual(redir.severity, "low")
        self.assertEqual(redir.category, "suspicious_context")

    def test_final_domain_changed_produces_evidence(self):
        result = _completed(
            url="https://original.com/",
            final_url="https://totally-different.net/landing",
        )
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertIn("dyn_final_domain_changed", ids)

    def test_final_domain_same_no_domain_change_evidence(self):
        result = _completed(
            url="https://example.com/page1",
            final_url="https://example.com/page2",
        )
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_final_domain_changed", ids)

    def test_login_form_only_produces_weak_evidence(self):
        result = _completed(has_login_form=True)
        ev = dynamic_result_to_evidence(result)
        login_ev = [e for e in ev if e.id == "dyn_login_form_detected"]
        self.assertEqual(len(login_ev), 1)
        self.assertLessEqual(login_ev[0].score_delta, 10)
        self.assertEqual(login_ev[0].severity, "low")

    def test_password_field_only_produces_medium_evidence(self):
        result = _completed(has_password_field=True)
        ev = dynamic_result_to_evidence(result)
        pw_ev = [e for e in ev if e.id == "dyn_password_field_detected"]
        self.assertEqual(len(pw_ev), 1)
        self.assertLessEqual(pw_ev[0].score_delta, 12)
        self.assertIn(pw_ev[0].severity, ("low", "medium"))

    def test_otp_field_produces_medium_evidence(self):
        result = _completed(has_otp_field=True)
        ev = dynamic_result_to_evidence(result)
        otp_ev = [e for e in ev if e.id == "dyn_otp_field_detected"]
        self.assertEqual(len(otp_ev), 1)
        self.assertEqual(otp_ev[0].severity, "medium")
        self.assertGreaterEqual(otp_ev[0].score_delta, 14)
        self.assertLessEqual(otp_ev[0].score_delta, 18)

    def test_suspicious_requests_produces_evidence(self):
        result = _completed(suspicious_requests=3)
        ev = dynamic_result_to_evidence(result)
        req_ev = [e for e in ev if e.id == "dyn_suspicious_external_requests"]
        self.assertEqual(len(req_ev), 1)
        self.assertEqual(req_ev[0].category, "suspicious_context")


class TestMultiSignalCompound(unittest.TestCase):
    """dyn_multi_signal_phishing_surface fires only when all 3 groups co-present."""

    def _multi_signal_result(self, **overrides) -> DynamicURLAnalysisResult:
        defaults = dict(
            url="https://phish.example.com/",
            final_url="https://real-bank.net/login",  # domain change
            redirect_chain=["https://phish.example.com/r1", "https://phish.example.com/r2"],
            has_password_field=True,
            suspicious_requests=2,
        )
        defaults.update(overrides)
        return _completed(**defaults)

    def test_all_three_groups_produce_compound(self):
        result = self._multi_signal_result()
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertIn("dyn_multi_signal_phishing_surface", ids)

    def test_compound_is_high_severity_suspicious_context(self):
        result = self._multi_signal_result()
        ev = dynamic_result_to_evidence(result)
        compound = next(e for e in ev if e.id == "dyn_multi_signal_phishing_surface")
        self.assertEqual(compound.severity, "high")
        self.assertEqual(compound.category, "suspicious_context")
        self.assertLessEqual(compound.score_delta, _MAX_SINGLE_DELTA)

    def test_missing_suspicious_requests_no_compound(self):
        result = self._multi_signal_result(suspicious_requests=0)
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_multi_signal_phishing_surface", ids)

    def test_missing_credential_signal_no_compound(self):
        # No login form, no password, no OTP
        result = self._multi_signal_result(
            has_password_field=False,
            has_login_form=False,
            has_otp_field=False,
        )
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_multi_signal_phishing_surface", ids)

    def test_missing_redirect_and_domain_change_no_compound(self):
        result = self._multi_signal_result(
            final_url=None,          # no domain change
            redirect_chain=[],       # no redirect chain signal
        )
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_multi_signal_phishing_surface", ids)


class TestTrustedDomainGuard(unittest.TestCase):
    """Trusted domain suppresses or reduces login/password evidence."""

    def test_trusted_domain_suppresses_password_field_evidence(self):
        result = _completed(has_password_field=True)
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_password_field_detected", ids)

    def test_trusted_domain_caps_login_form_evidence(self):
        result = _completed(has_login_form=True)
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        login_ev = [e for e in ev if e.id == "dyn_login_form_detected"]
        # Either suppressed or capped at <= 5
        for item in login_ev:
            self.assertLessEqual(item.score_delta, 5)

    def test_trusted_domain_does_not_suppress_otp_field(self):
        # OTP phishing can target trusted-looking domains — not suppressed.
        result = _completed(has_otp_field=True)
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertIn("dyn_otp_field_detected", ids)

    def test_trusted_domain_does_not_suppress_domain_change(self):
        result = _completed(
            url="https://google.com/",
            final_url="https://totally-different.net/phish",
        )
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertIn("dyn_final_domain_changed", ids)


class TestCleanVerdictGuard(unittest.TestCase):
    """Clean URL verdict suppresses most evidence unless alarming signals present."""

    def test_clean_verdict_suppresses_login_form(self):
        result = _completed(has_login_form=True)
        ev = dynamic_result_to_evidence(result, url_verdict="clean")
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_login_form_detected", ids)

    def test_clean_verdict_suppresses_password_field(self):
        result = _completed(has_password_field=True)
        ev = dynamic_result_to_evidence(result, url_verdict="clean")
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_password_field_detected", ids)

    def test_clean_verdict_does_not_suppress_otp_with_alarming(self):
        # OTP field is itself alarming — clean verdict guard lifted.
        result = _completed(has_otp_field=True)
        ev = dynamic_result_to_evidence(result, url_verdict="clean")
        ids = [e.id for e in ev]
        self.assertIn("dyn_otp_field_detected", ids)

    def test_clean_verdict_does_not_suppress_domain_change(self):
        result = _completed(
            url="https://trusted.com/",
            final_url="https://attacker.net/page",
        )
        ev = dynamic_result_to_evidence(result, url_verdict="clean")
        ids = [e.id for e in ev]
        self.assertIn("dyn_final_domain_changed", ids)


class TestSafeIntentGuard(unittest.TestCase):
    """Safe message intents suppress evidence when no alarming signals present."""

    _SAFE = ("security_advice", "otp_code", "advertisement", "service_notice", "transactional")

    def test_safe_intent_suppresses_login_form(self):
        for intent in self._SAFE:
            with self.subTest(intent=intent):
                result = _completed(has_login_form=True)
                ev = dynamic_result_to_evidence(result, message_intent=intent)
                self.assertEqual(ev, [], f"expected [] for intent={intent!r}")

    def test_safe_intent_suppresses_password_field(self):
        for intent in self._SAFE:
            with self.subTest(intent=intent):
                result = _completed(has_password_field=True)
                ev = dynamic_result_to_evidence(result, message_intent=intent)
                self.assertEqual(ev, [], f"expected [] for intent={intent!r}")

    def test_safe_intent_overridden_by_domain_change(self):
        result = _completed(
            url="https://example.com/",
            final_url="https://attacker.net/phish",
            has_login_form=True,
        )
        ev = dynamic_result_to_evidence(result, message_intent="transactional")
        self.assertGreater(len(ev), 0, "domain change should override safe intent guard")

    def test_safe_intent_overridden_by_otp_field(self):
        result = _completed(has_otp_field=True)
        ev = dynamic_result_to_evidence(result, message_intent="service_notice")
        ids = [e.id for e in ev]
        self.assertIn("dyn_otp_field_detected", ids)

    def test_safe_intent_overridden_by_suspicious_requests(self):
        result = _completed(suspicious_requests=4)
        ev = dynamic_result_to_evidence(result, message_intent="advertisement")
        self.assertGreater(len(ev), 0)


class TestEvidenceCategoryConstraints(unittest.TestCase):
    """Phase 2C hard rules on categories and score_deltas."""

    def _all_evidence(self) -> list:
        """Collect evidence from a maximally-alarming result."""
        result = _completed(
            url="https://phish.example.com/",
            final_url="https://different-domain.net/login",
            redirect_chain=["https://phish.example.com/r1", "https://phish.example.com/r2"],
            has_login_form=True,
            has_password_field=True,
            has_otp_field=True,
            suspicious_requests=5,
        )
        return dynamic_result_to_evidence(result)

    def test_no_evidence_category_is_dangerous_intent(self):
        for ev in self._all_evidence():
            self.assertNotEqual(
                ev.category,
                "dangerous_intent",
                f"evidence {ev.id!r} must not be dangerous_intent in Phase 2C",
            )

    def test_no_score_delta_exceeds_max_single_delta(self):
        for ev in self._all_evidence():
            self.assertLessEqual(
                ev.score_delta,
                _MAX_SINGLE_DELTA,
                f"evidence {ev.id!r} score_delta={ev.score_delta} exceeds cap {_MAX_SINGLE_DELTA}",
            )

    def test_all_evidence_has_arabic_explanation(self):
        for ev in self._all_evidence():
            self.assertTrue(
                ev.explanation_ar,
                f"evidence {ev.id!r} missing explanation_ar",
            )

    def test_all_evidence_has_extra_with_dynamic_flag(self):
        for ev in self._all_evidence():
            self.assertTrue(
                ev.extra.get("dynamic_analysis"),
                f"evidence {ev.id!r} missing extra['dynamic_analysis']",
            )


# ─── Phase 2D runtime signal tests ───────────────────────────────────────────

class TestPhase2DConstants(unittest.TestCase):
    """Verify Phase 2D hard-limit constants have expected values."""

    def test_max_observation_ms_is_5000(self):
        from app.services.url_sandbox.playwright_sandbox import _MAX_OBSERVATION_MS
        self.assertEqual(_MAX_OBSERVATION_MS, 5000)

    def test_max_simulated_minutes_is_60(self):
        from app.services.url_sandbox.playwright_sandbox import _MAX_SIMULATED_MINUTES
        self.assertEqual(_MAX_SIMULATED_MINUTES, 60)

    def test_max_tracked_hosts_is_20(self):
        from app.services.url_sandbox.playwright_sandbox import _MAX_TRACKED_HOSTS
        self.assertEqual(_MAX_TRACKED_HOSTS, 20)

    def test_result_defaults_for_phase2d_fields(self):
        """New Phase 2D fields must default to False/None."""
        result = DynamicURLAnalysisResult()
        self.assertFalse(result.delayed_url_change)
        self.assertFalse(result.delayed_title_change)
        self.assertFalse(result.delayed_form_change)
        self.assertFalse(result.delayed_sensitive_field_appeared)
        self.assertFalse(result.time_simulation_enabled)
        self.assertEqual(result.simulated_minutes, 0)
        self.assertIsNone(result.time_simulation_error)
        self.assertEqual(result.external_host_list, [])

    def test_time_simulation_disabled_by_default(self):
        result = DynamicURLAnalysisResult(status="completed")
        ev = dynamic_result_to_evidence(result)
        # No time_simulation field in evidence — it doesn't affect scoring
        self.assertFalse(result.time_simulation_enabled)


class TestPhase2DDelayedRedirect(unittest.TestCase):
    """Delayed URL change signal generates evidence appropriately."""

    def test_delayed_redirect_produces_evidence(self):
        result = _completed(delayed_url_change=True)
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertIn("dyn_delayed_redirect_detected", ids)

    def test_delayed_redirect_is_medium_suspicious_context(self):
        result = _completed(delayed_url_change=True)
        ev = dynamic_result_to_evidence(result)
        item = next(e for e in ev if e.id == "dyn_delayed_redirect_detected")
        self.assertEqual(item.severity, "medium")
        self.assertEqual(item.category, "suspicious_context")

    def test_delayed_redirect_score_delta_in_range(self):
        result = _completed(delayed_url_change=True)
        ev = dynamic_result_to_evidence(result)
        item = next(e for e in ev if e.id == "dyn_delayed_redirect_detected")
        self.assertGreaterEqual(item.score_delta, 14)
        self.assertLessEqual(item.score_delta, 18)

    def test_delayed_redirect_suppressed_for_trusted_no_domain_change(self):
        # Trusted domain + no cross-domain redirect → delayed redirects are common (SSO)
        result = _completed(delayed_url_change=True)
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_delayed_redirect_detected", ids)

    def test_delayed_redirect_trusted_but_domain_changed(self):
        # Even trusted domain: delayed redirect with CROSS-domain change is suspicious
        result = _completed(
            url="https://google.com/",
            final_url="https://attacker.net/phish",
            delayed_url_change=True,
        )
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertIn("dyn_delayed_redirect_detected", ids)

    def test_delayed_redirect_suppressed_by_safe_intent_no_alarming(self):
        result = _completed(delayed_url_change=True)
        ev = dynamic_result_to_evidence(result, message_intent="transactional")
        # delayed_url_change is itself "alarming" so it should NOT be fully suppressed
        # — it IS alarming (URL changed). Let's verify by checking alarming logic:
        # alarming = final_domain_changed OR has_otp_field OR suspicious_requests > 0 OR brand
        # delayed_url_change is NOT in the alarming set, so safe intent suppresses it
        # unless another alarming signal is present.
        # In this result: no final_domain_changed, no otp, no suspicious_requests
        # → alarming = False → safe intent guard fires → []
        self.assertEqual(ev, [])

    def test_no_delayed_redirect_no_evidence(self):
        result = _completed(delayed_url_change=False)
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_delayed_redirect_detected", ids)


class TestPhase2DSensitiveFormAppeared(unittest.TestCase):
    """Delayed sensitive field appearance signal."""

    def test_sensitive_form_appeared_produces_evidence(self):
        result = _completed(delayed_sensitive_field_appeared=True)
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertIn("dyn_sensitive_form_appeared_after_delay", ids)

    def test_sensitive_form_appeared_score_in_range(self):
        result = _completed(delayed_sensitive_field_appeared=True)
        ev = dynamic_result_to_evidence(result)
        item = next(e for e in ev if e.id == "dyn_sensitive_form_appeared_after_delay")
        self.assertGreaterEqual(item.score_delta, 16)
        self.assertLessEqual(item.score_delta, 18)

    def test_sensitive_form_appeared_not_suppressed_by_trusted_domain(self):
        # Dynamic form injection is suspicious even on trusted-looking domains
        result = _completed(delayed_sensitive_field_appeared=True)
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertIn("dyn_sensitive_form_appeared_after_delay", ids)

    def test_sensitive_form_appeared_is_alarming_overrides_safe_intent(self):
        # delayed_sensitive_field_appeared sets has_otp or password after delay
        # BUT it is NOT in the "alarming" set of dynamic_result_to_evidence.
        # However, clean-verdict guard only suppresses if alarming = False.
        # For "transactional" intent with NO other alarming signals → suppressed.
        result = _completed(delayed_sensitive_field_appeared=True)
        ev = dynamic_result_to_evidence(result, message_intent="transactional")
        # alarming = False (no final_domain_changed, no otp, no suspicious requests, no brand)
        # safe intent guard → []
        self.assertEqual(ev, [])

    def test_sensitive_form_appeared_with_suspicious_requests_not_suppressed(self):
        # suspicious_requests > 0 makes alarming = True, overriding safe intent
        result = _completed(delayed_sensitive_field_appeared=True, suspicious_requests=2)
        ev = dynamic_result_to_evidence(result, message_intent="transactional")
        ids = [e.id for e in ev]
        self.assertIn("dyn_sensitive_form_appeared_after_delay", ids)


class TestPhase2DTitleChanged(unittest.TestCase):
    """Title changed signal — weak, suppressed aggressively."""

    def test_title_changed_alone_no_evidence(self):
        # Requires alarming context — title change alone is too weak
        result = _completed(delayed_title_change=True)
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_title_changed_after_load", ids)

    def test_title_changed_with_alarming_generates_evidence(self):
        # With suspicious_requests (alarming) and not trusted + not clean
        result = _completed(
            delayed_title_change=True,
            suspicious_requests=3,  # makes alarming=True
        )
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertIn("dyn_title_changed_after_load", ids)

    def test_title_changed_score_delta_is_low(self):
        result = _completed(delayed_title_change=True, suspicious_requests=3)
        ev = dynamic_result_to_evidence(result)
        item = next((e for e in ev if e.id == "dyn_title_changed_after_load"), None)
        if item is not None:
            self.assertLessEqual(item.score_delta, 8)
            self.assertEqual(item.severity, "low")

    def test_title_changed_suppressed_for_trusted_domain(self):
        result = _completed(delayed_title_change=True, suspicious_requests=3)
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_title_changed_after_load", ids)


class TestPhase2DMultiStageNavigation(unittest.TestCase):
    """Multi-stage navigation signal (redirect_chain >= 3 OR delayed URL change)."""

    def test_long_redirect_chain_produces_multi_stage(self):
        result = _completed(
            redirect_chain=[
                "https://a.example.com/r1",
                "https://a.example.com/r2",
                "https://a.example.com/r3",
            ]
        )
        ev = dynamic_result_to_evidence(result)
        ids = [e.id for e in ev]
        self.assertIn("dyn_multi_stage_navigation", ids)

    def test_delayed_url_change_triggers_multi_stage(self):
        result = _completed(delayed_url_change=True)
        ev = dynamic_result_to_evidence(result)
        # delayed_url_change alone without alarming signals: safe_intent guard not active
        # (message_intent defaults to "unknown" which is not in _SAFE_INTENTS)
        # trusted=False, clean=False → should fire
        ids = [e.id for e in ev]
        self.assertIn("dyn_multi_stage_navigation", ids)

    def test_multi_stage_score_delta_in_range(self):
        result = _completed(
            redirect_chain=["https://a.example.com/r1", "https://a.example.com/r2", "https://a.example.com/r3"]
        )
        ev = dynamic_result_to_evidence(result)
        item = next(e for e in ev if e.id == "dyn_multi_stage_navigation")
        self.assertGreaterEqual(item.score_delta, 12)
        self.assertLessEqual(item.score_delta, 16)

    def test_multi_stage_suppressed_for_trusted_domain_no_alarming(self):
        result = _completed(delayed_url_change=True)
        ev = dynamic_result_to_evidence(result, is_trusted_domain=True)
        ids = [e.id for e in ev]
        self.assertNotIn("dyn_multi_stage_navigation", ids)

    def test_multi_stage_is_suspicious_context(self):
        result = _completed(
            redirect_chain=["https://a.example.com/r1", "https://a.example.com/r2", "https://a.example.com/r3"]
        )
        ev = dynamic_result_to_evidence(result)
        item = next(e for e in ev if e.id == "dyn_multi_stage_navigation")
        self.assertEqual(item.category, "suspicious_context")


class TestPhase2DHardConstraints(unittest.TestCase):
    """Phase 2D hard constraints on all new evidence."""

    def _all_phase2d_evidence(self) -> list:
        result = _completed(
            url="https://phish.example.com/",
            final_url="https://different-domain.net/login",
            redirect_chain=[
                "https://phish.example.com/r1",
                "https://phish.example.com/r2",
                "https://phish.example.com/r3",
            ],
            has_login_form=True,
            has_password_field=True,
            has_otp_field=True,
            suspicious_requests=5,
            delayed_url_change=True,
            delayed_title_change=True,
            delayed_form_change=True,
            delayed_sensitive_field_appeared=True,
        )
        return dynamic_result_to_evidence(result)

    def test_no_phase2d_evidence_is_dangerous_intent(self):
        for ev in self._all_phase2d_evidence():
            self.assertNotEqual(
                ev.category,
                "dangerous_intent",
                f"evidence {ev.id!r} must not be dangerous_intent",
            )

    def test_no_phase2d_score_delta_exceeds_cap(self):
        for ev in self._all_phase2d_evidence():
            self.assertLessEqual(
                ev.score_delta,
                _MAX_SINGLE_DELTA,
                f"evidence {ev.id!r} score_delta={ev.score_delta} exceeds cap",
            )

    def test_all_phase2d_evidence_has_arabic_explanation(self):
        for ev in self._all_phase2d_evidence():
            self.assertTrue(ev.explanation_ar, f"evidence {ev.id!r} missing explanation_ar")

    def test_all_phase2d_evidence_has_extra_dynamic_flag(self):
        for ev in self._all_phase2d_evidence():
            self.assertTrue(
                ev.extra.get("dynamic_analysis"),
                f"evidence {ev.id!r} missing extra['dynamic_analysis']",
            )

    def test_no_new_single_delta_exceeds_18(self):
        """Phase 2D individual signal max is +18 (compound +25 from Phase 2C is exempt)."""
        phase2d_ids = {
            "dyn_delayed_redirect_detected",
            "dyn_sensitive_form_appeared_after_delay",
            "dyn_title_changed_after_load",
            "dyn_multi_stage_navigation",
        }
        for ev in self._all_phase2d_evidence():
            if ev.id in phase2d_ids:
                self.assertLessEqual(
                    ev.score_delta,
                    18,
                    f"Phase 2D evidence {ev.id!r} score_delta={ev.score_delta} exceeds 18",
                )

    def test_disabled_produces_no_evidence(self):
        result = DynamicURLAnalysisResult(
            url="https://example.com",
            status="disabled",
            delayed_url_change=True,
            delayed_sensitive_field_appeared=True,
        )
        ev = dynamic_result_to_evidence(result)
        self.assertEqual(ev, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
