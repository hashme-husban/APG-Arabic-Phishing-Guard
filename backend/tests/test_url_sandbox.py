"""
APG URL Sandbox — Unit Tests

Tests URL validation helpers and the dynamic analysis entry point.
All tests run without Playwright installed (validation errors happen before
any browser is launched).

Run:
    cd backend
    python -m pytest tests/test_url_sandbox.py -v
    # or without pytest:
    python -m unittest tests.test_url_sandbox -v
"""
from __future__ import annotations

import sys
import os
import unittest

# Allow running from the backend/ directory directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Validator tests ──────────────────────────────────────────────────────────

class TestValidateUrlScheme(unittest.TestCase):

    def _validate(self, url: str) -> None:
        from app.services.url_sandbox.url_validator import validate_url_scheme
        validate_url_scheme(url)

    def _expect_blocked(self, url: str, expected_fragment: str = "") -> None:
        from app.services.url_sandbox.url_validator import (
            validate_url_scheme,
            URLValidationError,
        )
        with self.assertRaises(URLValidationError) as ctx:
            validate_url_scheme(url)
        if expected_fragment:
            self.assertIn(expected_fragment, ctx.exception.reason)

    def test_http_allowed(self):
        self._validate("http://example.com/path")

    def test_https_allowed(self):
        self._validate("https://example.com/path?q=1")

    def test_empty_url_blocked(self):
        self._expect_blocked("", "empty")

    def test_file_scheme_blocked(self):
        self._expect_blocked("file:///etc/passwd", "file")

    def test_ftp_scheme_blocked(self):
        self._expect_blocked("ftp://example.com/file", "ftp")

    def test_data_scheme_blocked(self):
        self._expect_blocked("data:text/html,<h1>x</h1>", "data")

    def test_javascript_scheme_blocked(self):
        self._expect_blocked("javascript:alert(1)", "javascript")

    def test_chrome_scheme_blocked(self):
        self._expect_blocked("chrome://settings", "chrome")

    def test_about_scheme_blocked(self):
        self._expect_blocked("about:blank", "about")

    def test_blob_scheme_blocked(self):
        self._expect_blocked("blob:https://example.com/uuid", "blob")

    def test_no_scheme_blocked(self):
        self._expect_blocked("example.com/path")


class TestIsIpBlocked(unittest.TestCase):

    def _blocked(self, ip: str) -> bool:
        from app.services.url_sandbox.url_validator import _is_ip_blocked
        return _is_ip_blocked(ip)

    def test_loopback_127_blocked(self):
        self.assertTrue(self._blocked("127.0.0.1"))

    def test_loopback_127_x_blocked(self):
        self.assertTrue(self._blocked("127.0.0.2"))

    def test_private_10_blocked(self):
        self.assertTrue(self._blocked("10.0.0.1"))
        self.assertTrue(self._blocked("10.255.255.255"))

    def test_private_172_blocked(self):
        self.assertTrue(self._blocked("172.16.0.1"))
        self.assertTrue(self._blocked("172.31.255.255"))

    def test_private_192_168_blocked(self):
        self.assertTrue(self._blocked("192.168.0.1"))
        self.assertTrue(self._blocked("192.168.1.100"))

    def test_metadata_169_254_blocked(self):
        self.assertTrue(self._blocked("169.254.169.254"))  # AWS/GCP/Azure metadata
        self.assertTrue(self._blocked("169.254.0.1"))

    def test_ipv6_loopback_blocked(self):
        self.assertTrue(self._blocked("::1"))

    def test_ipv6_link_local_blocked(self):
        self.assertTrue(self._blocked("fe80::1"))

    def test_public_ip_allowed(self):
        self.assertFalse(self._blocked("8.8.8.8"))
        self.assertFalse(self._blocked("1.1.1.1"))

    def test_documentation_range_blocked(self):
        # 203.0.113.0/24 is RFC 5737 documentation range — blocked per policy
        self.assertTrue(self._blocked("203.0.113.1"))

    def test_unparseable_ip_blocked(self):
        # Fail closed on unparseable strings
        self.assertTrue(self._blocked("not-an-ip"))
        self.assertTrue(self._blocked(""))


class TestResolveAndValidateHost(unittest.TestCase):

    def _validate(self, host: str) -> None:
        from app.services.url_sandbox.url_validator import resolve_and_validate_host
        resolve_and_validate_host(host)

    def _expect_blocked(self, host: str, expected_fragment: str = "") -> None:
        from app.services.url_sandbox.url_validator import (
            resolve_and_validate_host,
            URLValidationError,
        )
        with self.assertRaises(URLValidationError) as ctx:
            resolve_and_validate_host(host)
        if expected_fragment:
            self.assertIn(expected_fragment, ctx.exception.reason)

    def test_localhost_blocked(self):
        self._expect_blocked("localhost", "localhost")

    def test_localhost_subdomain_blocked(self):
        self._expect_blocked("app.localhost", "localhost")

    def test_bare_127_blocked(self):
        self._expect_blocked("127.0.0.1", "blocked_ip")

    def test_bare_private_10_blocked(self):
        self._expect_blocked("10.0.0.1", "blocked_ip")

    def test_bare_192_168_blocked(self):
        self._expect_blocked("192.168.1.1", "blocked_ip")

    def test_bare_metadata_ip_blocked(self):
        self._expect_blocked("169.254.169.254", "blocked_ip")

    def test_empty_hostname_blocked(self):
        self._expect_blocked("", "empty")

    def test_domain_name_proceeds_to_dns(self):
        # Phase 2E regression: domain names must NOT be blocked as "blocked_ip".
        # _is_ip_blocked() fails closed for non-IP strings, but resolve_and_validate_host
        # must first verify the hostname is an IP before calling _is_ip_blocked.
        # This test checks that a legitimate FQDN reaches DNS (may raise dns_failed
        # if there is no network, but must NOT raise "blocked_ip").
        from app.services.url_sandbox.url_validator import (
            resolve_and_validate_host,
            URLValidationError,
        )
        try:
            resolve_and_validate_host("example.com")
            # Passed — network is available and example.com resolved to a public IP
        except URLValidationError as exc:
            self.assertNotIn(
                "blocked_ip",
                exc.reason,
                f"Domain name incorrectly treated as blocked IP: {exc.reason}",
            )
            # dns_failed, redirect_to_blocked, etc. are acceptable in offline environments


class TestValidateUrlSafe(unittest.TestCase):

    def _expect_blocked(self, url: str, fragment: str = "") -> None:
        from app.services.url_sandbox.url_validator import (
            validate_url_safe,
            URLValidationError,
        )
        with self.assertRaises(URLValidationError) as ctx:
            validate_url_safe(url)
        if fragment:
            self.assertIn(fragment, ctx.exception.reason)

    def test_file_url_blocked(self):
        self._expect_blocked("file:///etc/passwd", "file")

    def test_ftp_url_blocked(self):
        self._expect_blocked("ftp://192.168.1.1/file", "ftp")

    def test_http_localhost_blocked(self):
        self._expect_blocked("http://localhost/admin", "localhost")

    def test_http_127_blocked(self):
        self._expect_blocked("http://127.0.0.1/", "blocked_ip")

    def test_http_10_blocked(self):
        self._expect_blocked("http://10.0.0.1/internal", "blocked_ip")

    def test_http_192_168_blocked(self):
        self._expect_blocked("http://192.168.0.1/", "blocked_ip")

    def test_metadata_endpoint_blocked(self):
        self._expect_blocked("http://169.254.169.254/latest/meta-data/", "blocked_ip")


# ─── analyze_url_dynamically entry point tests ────────────────────────────────

class TestAnalyzeUrlDynamically(unittest.TestCase):

    def test_disabled_returns_disabled_status(self):
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically("https://example.com", enabled=False)
        self.assertEqual(result.status, "disabled")
        self.assertIsNone(result.error)
        self.assertEqual(result.redirect_chain, [])
        self.assertEqual(result.signals, [])

    def test_disabled_never_contacts_network(self):
        # Even a completely invalid URL returns disabled when flag is off
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically("file:///etc/passwd", enabled=False)
        self.assertEqual(result.status, "disabled")

    def test_enabled_file_scheme_rejected_before_browser(self):
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically("file:///etc/passwd", enabled=True)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)
        self.assertIn("file", result.error)

    def test_enabled_localhost_rejected_before_browser(self):
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically("http://localhost/", enabled=True)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)
        self.assertIn("localhost", result.error)

    def test_enabled_127_rejected_before_browser(self):
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically("http://127.0.0.1/", enabled=True)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)

    def test_enabled_192_168_rejected_before_browser(self):
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically("http://192.168.1.1/", enabled=True)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)

    def test_enabled_metadata_ip_rejected_before_browser(self):
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically("http://169.254.169.254/", enabled=True)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)

    def test_enabled_missing_playwright_graceful(self):
        """Backend must not crash when Playwright is not installed."""
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        # We can't mock the import easily without pytest, but we can verify that
        # a public URL with enabled=True does NOT raise any exception.
        # The result will be either:
        #   - failed (playwright_not_installed) if Playwright is absent
        #   - completed / failed (network) if Playwright is present
        #   - failed (dns_failed / blocked_ip) if the DNS resolves to private IP
        try:
            result = analyze_url_dynamically("https://example.com", enabled=True)
            # Must never raise — status can be anything valid
            self.assertIn(result.status, {"completed", "failed", "disabled", "not_implemented", "skipped"})
        except Exception as exc:
            self.fail(f"analyze_url_dynamically raised unexpectedly: {exc}")

    def test_result_to_dict_always_safe(self):
        """to_dict() must work on all status values."""
        from app.services.risk_engine.dynamic_url_analysis import (
            analyze_url_dynamically,
            DynamicURLAnalysisResult,
        )
        result = analyze_url_dynamically("https://example.com", enabled=False)
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("status", d)
        self.assertIn("url", d)
        self.assertIn("elapsed_ms", d)

    def test_phase2d_params_ignored_when_disabled(self):
        """Phase 2D params must be accepted but ignored when enabled=False."""
        from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
        result = analyze_url_dynamically(
            "https://example.com",
            enabled=False,
            observation_ms=3000,
            time_simulation_enabled=True,
            simulated_minutes=30,
        )
        self.assertEqual(result.status, "disabled")
        self.assertFalse(result.time_simulation_enabled)

    def test_phase2d_result_dict_includes_new_fields(self):
        """to_dict() must include all Phase 2D fields."""
        from app.services.risk_engine.dynamic_url_analysis import DynamicURLAnalysisResult
        result = DynamicURLAnalysisResult(
            url="https://example.com",
            status="completed",
            delayed_url_change=True,
            delayed_title_change=False,
            delayed_form_change=True,
            delayed_sensitive_field_appeared=False,
            time_simulation_enabled=False,
            simulated_minutes=0,
        )
        d = result.to_dict()
        for key in (
            "delayed_url_change", "delayed_title_change", "delayed_form_change",
            "delayed_sensitive_field_appeared", "time_simulation_enabled",
            "simulated_minutes", "time_simulation_error", "external_host_list",
        ):
            self.assertIn(key, d, f"to_dict() missing key {key!r}")


# ─── dynamic_result_to_evidence tests ────────────────────────────────────────

class TestDynamicResultToEvidence(unittest.TestCase):

    def test_non_completed_always_returns_empty(self):
        """Phase 2C: non-completed statuses must always return [] (no data)."""
        from app.services.risk_engine.dynamic_url_analysis import (
            DynamicURLAnalysisResult,
            dynamic_result_to_evidence,
        )
        for status in ("disabled", "not_implemented", "skipped", "failed"):
            result = DynamicURLAnalysisResult(
                url="https://example.com",
                status=status,
                has_password_field=True,
                has_login_form=True,
            )
            ev = dynamic_result_to_evidence(result)
            self.assertEqual(
                ev,
                [],
                f"expected [] for status={status!r} but got {ev}",
            )

    def test_completed_with_no_signals_returns_empty(self):
        """Completed result with no detectable signals must return []."""
        from app.services.risk_engine.dynamic_url_analysis import (
            DynamicURLAnalysisResult,
            dynamic_result_to_evidence,
        )
        result = DynamicURLAnalysisResult(
            url="https://example.com",
            status="completed",
        )
        ev = dynamic_result_to_evidence(result)
        self.assertEqual(ev, [])

    def test_completed_with_signals_returns_evidence(self):
        """Phase 2C: completed result with alarming signals produces Evidence items."""
        from app.services.risk_engine.dynamic_url_analysis import (
            DynamicURLAnalysisResult,
            dynamic_result_to_evidence,
        )
        result = DynamicURLAnalysisResult(
            url="https://phish.example.com/",
            final_url="https://different.net/login",
            status="completed",
            has_password_field=True,
            suspicious_requests=2,
        )
        ev = dynamic_result_to_evidence(result)
        self.assertGreater(len(ev), 0, "expected evidence for alarming completed result")


if __name__ == "__main__":
    unittest.main(verbosity=2)
