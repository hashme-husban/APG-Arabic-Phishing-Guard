"""
APG Dynamic URL Sandbox -- Local Validation Script

Runs without Playwright. All blocked-URL cases exercise the pre-flight validators
only -- no browser is launched.

Usage:
    cd backend
    python scripts/validate_dynamic_url_sandbox.py          # static checks only
    python scripts/validate_dynamic_url_sandbox.py --live   # + Playwright live run on example.com

Exit codes:
    0  all checks passed
    1  one or more checks failed
"""
from __future__ import annotations

import sys
import os
import argparse
import time

# Allow running from backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_failures: list[str] = []
_passes:   list[str] = []
_skips:    list[str] = []


def _check(label: str, result: bool, note: str = "") -> None:
    tag = PASS if result else FAIL
    suffix = f"  ({note})" if note else ""
    line = f"  [{tag}] {label}{suffix}"
    print(line)
    if result:
        _passes.append(label)
    else:
        _failures.append(label)


def _skip(label: str, note: str = "") -> None:
    suffix = f"  ({note})" if note else ""
    print(f"  [{SKIP}] {label}{suffix}")
    _skips.append(label)


# ---- 1. Disabled mode returns status=disabled --------------------------------

def check_disabled_mode() -> None:
    print("\n[1] Disabled mode")
    from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically

    result = analyze_url_dynamically("https://example.com", enabled=False)
    _check("disabled status returned",         result.status == "disabled")
    _check("error is None",                    result.error is None)
    _check("redirect_chain is empty",          result.redirect_chain == [])
    _check("signals is empty",                 result.signals == [])
    _check("time_simulation_enabled is False", not result.time_simulation_enabled)
    _check("delayed_url_change is False",      not result.delayed_url_change)
    _check("external_host_list is empty",      result.external_host_list == [])

    # Even a malicious URL is silent when disabled
    evil_result = analyze_url_dynamically("file:///etc/passwd", enabled=False)
    _check("file:// silent when disabled",     evil_result.status == "disabled")


# ---- 2. Scheme blocking (pre-flight, no browser) ----------------------------

def check_scheme_blocking() -> None:
    print("\n[2] Scheme blocking (pre-flight, no browser)")
    from app.services.url_sandbox.url_validator import validate_url_safe, URLValidationError

    blocked = [
        ("file:///etc/passwd",          "file"),
        ("javascript:alert(1)",         "javascript"),
        ("data:text/html,<h1>x</h1>",  "data"),
        ("ftp://example.com/file",      "ftp"),
        ("blob:https://example.com/x",  "blob"),
        ("about:blank",                 "about"),
        ("chrome://settings",           "chrome"),
    ]
    for url, expected_fragment in blocked:
        try:
            validate_url_safe(url)
            _check(f"{url[:40]} blocked", False, "no exception raised")
        except URLValidationError as exc:
            ok = expected_fragment in exc.reason
            _check(f"{url[:40]} blocked", ok, exc.reason if not ok else "")
        except Exception as exc:
            _check(f"{url[:40]} blocked", False, f"unexpected: {exc}")


# ---- 3. Private IP / localhost blocking (pre-flight, no browser) ------------

def check_private_ip_blocking() -> None:
    print("\n[3] Private IP / localhost blocking (pre-flight, no browser)")
    from app.services.url_sandbox.url_validator import validate_url_safe, URLValidationError

    blocked = [
        ("http://localhost/admin",            "localhost"),
        ("http://127.0.0.1/",                 "blocked_ip"),
        ("http://192.168.1.1/",               "blocked_ip"),
        ("http://10.0.0.1/internal",          "blocked_ip"),
        ("http://169.254.169.254/meta-data/", "blocked_ip"),
    ]
    for url, expected_fragment in blocked:
        try:
            validate_url_safe(url)
            _check(f"{url[:50]} blocked", False, "no exception raised")
        except URLValidationError as exc:
            ok = expected_fragment in exc.reason
            _check(f"{url[:50]} blocked", ok, exc.reason if not ok else "")
        except Exception as exc:
            _check(f"{url[:50]} blocked", False, f"unexpected: {exc}")


# ---- 4. Domain names not wrongly blocked as blocked_ip ----------------------

def check_domain_not_blocked_as_ip() -> None:
    """
    Phase 2E regression check:
    _is_ip_blocked() fails closed for non-IP strings (returns True), but
    resolve_and_validate_host() must first verify the hostname is a valid IP
    before calling _is_ip_blocked(). If it doesn't, every FQDN is wrongly
    blocked with 'blocked_ip'. This check verifies the fix is in place.

    DNS resolution is network-dependent; the check accepts dns_failed (offline)
    but rejects blocked_ip for a domain name.
    """
    print("\n[4] Domain name not wrongly blocked as blocked_ip (Phase 2E regression)")
    from app.services.url_sandbox.url_validator import (
        resolve_and_validate_host,
        URLValidationError,
    )

    test_host = "example.com"
    try:
        resolve_and_validate_host(test_host)
        _check(f"{test_host} passes pre-flight (network available)", True)
    except URLValidationError as exc:
        if "blocked_ip" in exc.reason:
            _check(
                f"{test_host} not wrongly blocked as blocked_ip",
                False,
                f"bug still present: {exc.reason}",
            )
        else:
            # dns_failed, etc. -- acceptable in offline environments
            _skip(
                f"{test_host} pre-flight (network unavailable)",
                f"reason={exc.reason} -- offline environment, DNS check skipped",
            )
    except Exception as exc:
        _check(f"{test_host} pre-flight did not crash", False,
               f"unexpected: {type(exc).__name__}: {exc}")


# ---- 5. analyze_url_dynamically -- blocked URLs -> status=failed (no crash) --

def check_analyze_blocked_urls() -> None:
    print("\n[5] analyze_url_dynamically -- blocked URLs -> status=failed (no crash)")
    from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically

    cases = [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,<h1>x</h1>",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/",
    ]
    for url in cases:
        try:
            result = analyze_url_dynamically(url, enabled=True)
            _check(f"{url[:45]} -> failed",
                   result.status == "failed",
                   f"got status={result.status}")
            _check(f"{url[:45]} -> error set",
                   result.error is not None,
                   "error field is None")
        except Exception as exc:
            _check(f"{url[:45]} -> no crash", False,
                   f"raised: {type(exc).__name__}: {exc}")


# ---- 6. Evidence mapping remains conservative --------------------------------

def check_evidence_conservative() -> None:
    print("\n[6] Evidence mapping -- conservative guardrails")
    from app.services.risk_engine.dynamic_url_analysis import (
        DynamicURLAnalysisResult,
        dynamic_result_to_evidence,
        _MAX_SINGLE_DELTA,
    )

    # Non-completed result always returns []
    for status in ("disabled", "failed", "skipped", "not_implemented"):
        result = DynamicURLAnalysisResult(
            url="https://example.com",
            status=status,
            has_password_field=True,
            has_login_form=True,
        )
        ev = dynamic_result_to_evidence(result)
        _check(f"status={status} -> evidence=[]", ev == [], f"got {len(ev)} items")

    # No dangerous_intent category
    alarming_result = DynamicURLAnalysisResult(
        url="https://phish.example.com/",
        final_url="https://different-evil.net/login",
        status="completed",
        has_password_field=True,
        has_otp_field=True,
        suspicious_requests=3,
        redirect_chain=["https://phish.example.com/", "https://redir.net/x"],
    )
    evidence = dynamic_result_to_evidence(alarming_result)
    categories = {e.category for e in evidence}
    _check("no dangerous_intent category",
           "dangerous_intent" not in categories,
           f"found: {categories}")

    # No delta exceeds _MAX_SINGLE_DELTA
    bad_deltas = [e for e in evidence if e.score_delta > _MAX_SINGLE_DELTA]
    _check(f"no delta > {_MAX_SINGLE_DELTA}",
           not bad_deltas,
           f"offenders: {[e.id for e in bad_deltas]}")

    # All evidence has Arabic explanation
    missing_ar = [e for e in evidence if not e.explanation_ar]
    _check("all evidence has Arabic explanation",
           not missing_ar,
           f"missing: {[e.id for e in missing_ar]}")

    # Disabled produces no evidence
    disabled_result = DynamicURLAnalysisResult(
        url="https://example.com",
        status="disabled",
    )
    ev_disabled = dynamic_result_to_evidence(disabled_result)
    _check("disabled -> no evidence", ev_disabled == [])

    # Phase 2D: no individual Phase 2D signal exceeds +18
    phase2d_ids = {
        "dyn_delayed_redirect_detected",
        "dyn_sensitive_form_appeared_after_delay",
        "dyn_title_changed_after_load",
        "dyn_multi_stage_navigation",
    }
    phase2d_evidence = [e for e in evidence if e.id in phase2d_ids]
    bad_phase2d = [e for e in phase2d_evidence if e.score_delta > 18]
    _check("no Phase 2D delta > 18",
           not bad_phase2d,
           f"offenders: {[e.id for e in bad_phase2d]}")


# ---- 7. to_dict() completeness -----------------------------------------------

def check_to_dict_completeness() -> None:
    print("\n[7] to_dict() completeness -- all Phase 2D fields present")
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
    required_keys = [
        "url", "status", "final_url", "redirect_chain", "page_title",
        "has_login_form", "has_password_field", "has_otp_field", "form_count",
        "external_requests", "suspicious_requests", "external_host_list",
        "delayed_url_change", "delayed_title_change", "delayed_form_change",
        "delayed_sensitive_field_appeared", "time_simulation_enabled",
        "simulated_minutes", "time_simulation_error",
        "signals", "screenshot_path", "error", "elapsed_ms",
    ]
    for key in required_keys:
        _check(f"to_dict has '{key}'", key in d)


# ---- 8. Regression -- enabled flag defaults to False -------------------------

def check_enabled_default() -> None:
    print("\n[8] Regression -- DYNAMIC_URL_ANALYSIS_ENABLED defaults to False")
    from app.services.risk_engine import service as svc

    flag_value = getattr(svc, "_DYNAMIC_URL_ANALYSIS_ENABLED", None)
    if os.getenv("DYNAMIC_URL_ANALYSIS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        _skip("_DYNAMIC_URL_ANALYSIS_ENABLED default",
              "env var is set in this environment -- not a default-off check")
    else:
        _check("_DYNAMIC_URL_ANALYSIS_ENABLED is False", flag_value is False,
               f"got: {flag_value!r}")


# ---- 9. Optional --live mode -------------------------------------------------

def check_live(url: str = "https://example.com") -> None:
    print(f"\n[9] Live Playwright run -- {url}")
    print("    (requires: pip install playwright && python -m playwright install chromium)")
    from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically

    t0 = time.monotonic()
    try:
        result = analyze_url_dynamically(url, enabled=True, timeout_seconds=15, observation_ms=2000)
        elapsed = (time.monotonic() - t0) * 1000

        print(f"    status        : {result.status}")
        print(f"    final_url     : {result.final_url or '(same as input)'}")
        print(f"    page_title    : {result.page_title!r}")
        print(f"    elapsed_ms    : {result.elapsed_ms:.0f} ms (wall: {elapsed:.0f} ms)")
        print(f"    error         : {result.error}")
        print(f"    redirect_chain: {result.redirect_chain}")
        print(f"    external_hosts: {result.external_host_list}")
        print(f"    delayed_url_change         : {result.delayed_url_change}")
        print(f"    delayed_title_change       : {result.delayed_title_change}")
        print(f"    delayed_form_change        : {result.delayed_form_change}")
        print(f"    delayed_sensitive_appeared : {result.delayed_sensitive_field_appeared}")
        print(f"    time_simulation_enabled    : {result.time_simulation_enabled}")
        if result.signals:
            print(f"    signals ({len(result.signals)}):")
            for s in result.signals:
                print(f"      - {s.id}  severity={s.severity}  delta=+{s.score_delta}")
        if result.status == "failed" and result.error == "playwright_not_installed":
            print("    NOTE: Playwright not installed.")
            print("          Run: pip install playwright && python -m playwright install chromium")

        _check("live run did not raise", True)
        _check("live status is valid",
               result.status in {"completed", "failed", "disabled", "skipped"},
               result.status)

    except Exception as exc:
        _check("live run did not raise", False, f"{type(exc).__name__}: {exc}")


# ---- Main --------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="APG Dynamic URL Sandbox Validation")
    parser.add_argument("--live", action="store_true",
                        help="Run a live Playwright test on https://example.com")
    args = parser.parse_args()

    print("=" * 60)
    print("APG Dynamic URL Sandbox -- Local Validation")
    print("=" * 60)

    check_disabled_mode()
    check_scheme_blocking()
    check_private_ip_blocking()
    check_domain_not_blocked_as_ip()
    check_analyze_blocked_urls()
    check_evidence_conservative()
    check_to_dict_completeness()
    check_enabled_default()

    if args.live:
        check_live("https://example.com")

    print("\n" + "=" * 60)
    total  = len(_passes) + len(_failures) + len(_skips)
    print(f"Results: {len(_passes)}/{total} passed, {len(_failures)} failed, {len(_skips)} skipped")

    if _failures:
        print("\nFailed checks:")
        for f in _failures:
            print(f"  - {f}")
        print("=" * 60)
        return 1

    print("All checks passed.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
