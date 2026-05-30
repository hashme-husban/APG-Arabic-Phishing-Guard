"""
APG URL Sandbox — Playwright-based dynamic URL analysis.

Runs a headless Chromium browser in an isolated context to observe URL behaviour.

Security guarantees:
  - URL scheme and DNS pre-validation run BEFORE the browser starts.
  - Fresh, stateless browser context per URL (no shared cookies/cache/storage).
  - Downloads are disabled at the context level.
  - File/data/blob URL navigation is aborted at the routing level.
  - Final URL is re-validated after navigation (redirect-based SSRF protection).
  - External request hostnames are collected (capped at _MAX_TRACKED_HOSTS); request
    bodies, headers, and cookies are NOT stored.
  - Page evaluation is observation-only — no form interaction, no clicking,
    no credential entry.
  - All errors are caught; this function never raises.

Phase 2D additions:
  - Delayed observation: initial state captured after domcontentloaded, final state
    after a configurable observation window; diffs computed for URL/title/form changes.
  - Optional safe time simulation: injects a Date.now() override before navigation so
    time-gated JS logic can be observed. Disabled by default. Only Date.now() is
    overridden to avoid breaking page execution.
  - External host tracking capped at _MAX_TRACKED_HOSTS (20) to bound memory use.

Playwright is an OPTIONAL dependency.  If not installed, run_sandbox() returns
status="failed" with error="playwright_not_installed".

Installation (sandbox environment only — NOT the main API container):
    pip install playwright==<pinned_version>
    python -m playwright install chromium

See docs/PHASE2_DYNAMIC_URL_ANALYSIS_PLAN.md for full architecture and security
requirements.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from .url_validator import (
    URLValidationError,
    _registered_domain,
    resolve_and_validate_host,
    validate_url_safe,
)

logger = logging.getLogger("apg.url_sandbox")

# ─── Hard limits ──────────────────────────────────────────────────────────────

# Never exceed this even if env config is higher
_MAX_TIMEOUT_SECONDS: int = 20

# Max observation window — environment can configure lower, never higher
_MAX_OBSERVATION_MS: int = 5000

# Max simulated time offset — protects against runaway page spin-loops
_MAX_SIMULATED_MINUTES: int = 60

# Max external hostnames tracked per request — bounds memory usage
_MAX_TRACKED_HOSTS: int = 20

# ─── Resource classification ──────────────────────────────────────────────────

# Resource types that indicate active data exfiltration / script injection risk
_ACTIVE_RESOURCE_TYPES = frozenset({"script", "fetch", "xhr", "websocket"})

# Schemes that must be blocked at routing level (belt + suspenders after
# the pre-flight validate_url_scheme check which covers the initial URL)
_BLOCKED_SCHEME_PATTERNS = ("file://", "ftp://", "data:", "blob:", "javascript:")

# ─── Reusable JS for form/field inspection (observation only) ─────────────────

_FORM_INSPECT_JS: str = """() => {
    try {
        const inputs = Array.from(document.querySelectorAll('input'));
        const hasPassword = inputs.some(i => (i.type || '').toLowerCase() === 'password');
        const loginAttrTerms = ['username','email','login','user','account','phone','mobile','tel'];
        const hasLoginInput = inputs.some(i => {
            const attrs = [i.name, i.id, i.placeholder, i.autocomplete].join(' ').toLowerCase();
            return loginAttrTerms.some(t => attrs.includes(t));
        });
        const otpTerms = ['otp','code','verification','verify',
                          'رمز','تحقق','pin','passcode'];
        const hasOtpInput = inputs.some(i => {
            const attrs = [i.name, i.id, i.placeholder].join(' ').toLowerCase();
            const ml = parseInt(i.maxlength || '99');
            const isShortNumeric = ml <= 8 && ['number','tel','text'].includes(i.type || 'text');
            return otpTerms.some(t => attrs.includes(t)) || isShortNumeric;
        });
        const forms = document.querySelectorAll('form');
        const hasLoginForm = hasLoginInput || (forms.length > 0 && hasPassword);
        return {
            has_password: hasPassword,
            has_login_form: hasLoginForm,
            has_otp: hasOtpInput,
            form_count: forms.length,
        };
    } catch(e) {
        return {has_password: false, has_login_form: false, has_otp: false, form_count: 0};
    }
}"""

_FORM_INSPECT_DEFAULTS: dict = {
    "has_password": False,
    "has_login_form": False,
    "has_otp": False,
    "form_count": 0,
}


def _build_time_sim_script(offset_ms: int) -> str:
    """
    Build a safe JavaScript init script that advances Date.now() by offset_ms.

    Only Date.now() is overridden — new Date() still returns system time.
    Full Date constructor override is deferred to Phase 2E due to compatibility risk.
    The entire override is wrapped in try/catch so any failure is silent.
    """
    return (
        "(function() {"
        "  try {"
        f"    var _off = {offset_ms};"
        "    var _orig = Date.now;"
        "    Date.now = function() { return _orig() + _off; };"
        "  } catch(e) { /* ignore — page continues normally */ }"
        "})();"
    )


def run_sandbox(
    url: str,
    timeout_seconds: int = 10,
    observation_ms: int = 1500,
    time_simulation_enabled: bool = False,
    simulated_minutes: int = 0,
) -> dict:
    """
    Run a sandboxed Playwright analysis of *url*.

    Returns a dict whose keys match DynamicURLAnalysisResult fields.
    Never raises — all errors are caught and returned as status="failed".

    Args:
        url:                    URL to analyse. Must pass pre-flight validation.
        timeout_seconds:        Max total wall time (clamped to 1–20 s).
        observation_ms:         Post-load delay window (clamped to 0–5000 ms).
                                Initial state is captured before this window;
                                final state is captured after. Diffs detect
                                JS-driven delayed navigation and form changes.
        time_simulation_enabled: If True, injects a Date.now() override.
                                 Disabled by default — enables only when
                                 DYNAMIC_URL_ANALYSIS_TIME_SIMULATION_ENABLED=true.
        simulated_minutes:      Minutes to advance Date.now() (clamped to 0–60).
    """
    t0 = time.monotonic()

    # Clamp configurable limits — never exceed hard ceilings
    timeout_sec = max(1, min(int(timeout_seconds), _MAX_TIMEOUT_SECONDS))
    timeout_ms = timeout_sec * 1000
    obs_ms = max(0, min(int(observation_ms), _MAX_OBSERVATION_MS))
    sim_min = max(0, min(int(simulated_minutes), _MAX_SIMULATED_MINUTES))

    result: dict = {
        "url": url,
        "status": "failed",
        "final_url": None,
        "redirect_chain": [],
        "page_title": None,
        "has_login_form": False,
        "has_password_field": False,
        "has_otp_field": False,
        "form_count": 0,
        "external_requests": 0,
        "suspicious_requests": 0,
        "external_host_list": [],
        # Phase 2D delayed observation fields
        "delayed_url_change": False,
        "delayed_title_change": False,
        "delayed_form_change": False,
        "delayed_sensitive_field_appeared": False,
        # Phase 2D time simulation fields
        "time_simulation_enabled": time_simulation_enabled and sim_min > 0,
        "simulated_minutes": sim_min,
        "time_simulation_error": None,
        "signals": [],
        "screenshot_path": None,
        "error": None,
        "elapsed_ms": 0.0,
    }

    # ── Step 1: pre-flight URL validation (no browser needed) ─────────────────
    try:
        validate_url_safe(url)
    except URLValidationError as exc:
        result["error"] = exc.reason
        result["elapsed_ms"] = (time.monotonic() - t0) * 1000
        logger.info("url_sandbox pre-flight rejected %s: %s", _safe_log_host(url), exc.reason)
        return result

    # ── Step 2: optional Playwright import ────────────────────────────────────
    try:
        from playwright.sync_api import (  # type: ignore[import]
            sync_playwright,
            TimeoutError as PlaywrightTimeoutError,
        )
    except ImportError:
        result["error"] = "playwright_not_installed"
        result["elapsed_ms"] = (time.monotonic() - t0) * 1000
        logger.warning(
            "url_sandbox: Playwright not installed. "
            "Run: pip install playwright && python -m playwright install chromium"
        )
        return result

    # ── Step 3: sandbox execution ─────────────────────────────────────────────
    original_host = (urlparse(url).hostname or "").lower().strip(".")
    original_domain = _registered_domain(original_host)

    # Tracking state (mutated by request handler)
    external_hosts: set[str] = set()
    suspicious_host_count: int = 0

    def _on_request(request: object) -> None:
        nonlocal suspicious_host_count
        try:
            req_url = getattr(request, "url", "") or ""
            if not req_url:
                return
            lower_req = req_url.lower()
            for blocked in _BLOCKED_SCHEME_PATTERNS:
                if lower_req.startswith(blocked):
                    return
            req_host = (urlparse(req_url).hostname or "").lower().strip(".")
            if not req_host:
                return
            req_domain = _registered_domain(req_host)
            if req_domain == original_domain:
                return
            # Cap tracked hostnames to bound memory
            if len(external_hosts) < _MAX_TRACKED_HOSTS:
                external_hosts.add(req_host)
            rtype = getattr(request, "resource_type", "") or ""
            if rtype in _ACTIVE_RESOURCE_TYPES:
                suspicious_host_count += 1
        except Exception:
            pass

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-sync",
                    "--disable-translate",
                    "--mute-audio",
                    "--no-first-run",
                    "--safebrowsing-disable-auto-update",
                    "--disable-client-side-phishing-detection",
                    "--disable-hang-monitor",
                    "--disable-popup-blocking",
                    "--disable-prompt-on-repost",
                ],
            )
            context = browser.new_context(
                accept_downloads=False,
                ignore_https_errors=False,
                java_script_enabled=True,
                bypass_csp=False,
            )

            # ── Time simulation init script (Phase 2D, optional) ──────────────
            # Must be added to context BEFORE new_page() and page.goto() so it
            # runs on every navigation in this context. Only Date.now() is
            # overridden; setTimeout and setInterval are untouched.
            if time_simulation_enabled and sim_min > 0:
                offset_ms = sim_min * 60 * 1000
                try:
                    context.add_init_script(_build_time_sim_script(offset_ms))
                    logger.debug(
                        "url_sandbox time_simulation injected offset=%d ms for host=%s",
                        offset_ms,
                        _safe_log_host(url),
                    )
                except Exception as sim_exc:
                    result["time_simulation_error"] = (
                        f"init_script_error:{type(sim_exc).__name__}"
                    )
                    logger.warning(
                        "url_sandbox time_simulation init_script failed for host=%s: %s",
                        _safe_log_host(url),
                        type(sim_exc).__name__,
                    )
                    # Continue without time simulation — page still loads normally

            page = context.new_page()
            page.on("request", _on_request)

            def _route_handler(route: object) -> None:
                req = getattr(route, "request", None)
                req_url = getattr(req, "url", "") or ""
                lower_req = req_url.lower()
                should_block = any(lower_req.startswith(s) for s in _BLOCKED_SCHEME_PATTERNS)
                if should_block:
                    try:
                        route.abort("aborted")  # type: ignore[attr-defined]
                    except Exception:
                        pass
                else:
                    try:
                        route.continue_()  # type: ignore[attr-defined]
                    except Exception:
                        pass

            page.route("**/*", _route_handler)

            # ── Navigate ──────────────────────────────────────────────────────
            response = None
            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                result["error"] = "timeout"
                result["elapsed_ms"] = (time.monotonic() - t0) * 1000
                _safe_close(context, browser)
                return result
            except Exception as nav_exc:
                result["error"] = f"navigation_error:{type(nav_exc).__name__}"
                result["elapsed_ms"] = (time.monotonic() - t0) * 1000
                _safe_close(context, browser)
                return result

            # ── Capture INITIAL state (before observation window) ─────────────
            initial_url = page.url or url
            initial_title: str | None = None
            initial_form_data: dict = dict(_FORM_INSPECT_DEFAULTS)
            try:
                initial_title = page.title() or None
            except Exception:
                pass
            try:
                initial_form_data = page.evaluate(_FORM_INSPECT_JS)
            except Exception:
                pass

            # ── Observation window (Phase 2D configurable delay) ───────────────
            # Remaining budget after goto — never spin past timeout ceiling.
            elapsed_so_far_ms = (time.monotonic() - t0) * 1000
            remaining_ms = max(0, timeout_ms - int(elapsed_so_far_ms) - 200)  # 200 ms buffer
            actual_obs_ms = min(obs_ms, remaining_ms)
            if actual_obs_ms > 0:
                try:
                    page.wait_for_timeout(actual_obs_ms)
                except Exception:
                    pass

            # ── Capture FINAL state (after observation window) ─────────────────
            final_url_raw = page.url or initial_url

            # Compute delayed URL change BEFORE SSRF re-validation
            delayed_url_change = (final_url_raw != initial_url)

            final_title: str | None = None
            try:
                final_title = page.title() or None
            except Exception:
                pass
            final_form_data: dict = dict(_FORM_INSPECT_DEFAULTS)
            try:
                final_form_data = page.evaluate(_FORM_INSPECT_JS)
            except Exception:
                pass

            # Delayed diffs
            delayed_title_change = bool(
                initial_title and final_title and initial_title != final_title
            )
            delayed_form_change = (
                int(final_form_data.get("form_count", 0))
                != int(initial_form_data.get("form_count", 0))
            )
            delayed_sensitive_field_appeared = bool(
                (final_form_data.get("has_password") and not initial_form_data.get("has_password"))
                or (final_form_data.get("has_otp") and not initial_form_data.get("has_otp"))
            )

            # ── Re-validate final URL (redirect-based SSRF protection) ───────
            final_host = (urlparse(final_url_raw).hostname or "").lower().strip(".")
            try:
                resolve_and_validate_host(final_host)
            except URLValidationError as redir_exc:
                result["error"] = f"redirect_to_blocked:{redir_exc.reason}"
                result["elapsed_ms"] = (time.monotonic() - t0) * 1000
                logger.warning(
                    "url_sandbox redirect blocked for %s → %s: %s",
                    _safe_log_host(url),
                    _safe_log_host(final_url_raw),
                    redir_exc.reason,
                )
                _safe_close(context, browser)
                return result

            # ── Build redirect chain ──────────────────────────────────────────
            redirect_chain: list[str] = []
            if response is not None:
                try:
                    req = response.request
                    seen_in_chain: set[str] = {url, final_url_raw}
                    r = getattr(req, "redirected_from", None)
                    chain_entries: list[str] = []
                    while r is not None:
                        chain_entries.insert(0, r.url)
                        r = getattr(r, "redirected_from", None)
                    for entry in chain_entries:
                        if entry not in seen_in_chain:
                            seen_in_chain.add(entry)
                            redirect_chain.append(entry)
                except Exception:
                    pass

            _safe_close(context, browser)

            # ── Assemble result ───────────────────────────────────────────────
            result.update({
                "status": "completed",
                "final_url": final_url_raw if final_url_raw != url else None,
                "redirect_chain": redirect_chain,
                "page_title": final_title,
                "has_login_form": bool(final_form_data.get("has_login_form")),
                "has_password_field": bool(final_form_data.get("has_password")),
                "has_otp_field": bool(final_form_data.get("has_otp")),
                "form_count": int(final_form_data.get("form_count", 0)),
                "external_requests": len(external_hosts),
                "suspicious_requests": suspicious_host_count,
                "external_host_list": sorted(external_hosts),
                # Phase 2D delayed observation
                "delayed_url_change": delayed_url_change,
                "delayed_title_change": delayed_title_change,
                "delayed_form_change": delayed_form_change,
                "delayed_sensitive_field_appeared": delayed_sensitive_field_appeared,
                "error": None,
            })

            logger.info(
                "url_sandbox completed host=%s final_host=%s redirects=%d "
                "external_hosts=%d suspicious=%d login_form=%s pw_field=%s "
                "delayed_url_change=%s delayed_sensitive=%s elapsed_ms=%.0f",
                _safe_log_host(url),
                _safe_log_host(final_url_raw),
                len(redirect_chain),
                len(external_hosts),
                suspicious_host_count,
                result["has_login_form"],
                result["has_password_field"],
                delayed_url_change,
                delayed_sensitive_field_appeared,
                (time.monotonic() - t0) * 1000,
            )

    except Exception as exc:
        result["error"] = f"sandbox_error:{type(exc).__name__}"
        logger.warning(
            "url_sandbox unexpected error for host=%s: %s",
            _safe_log_host(url),
            type(exc).__name__,
        )

    result["elapsed_ms"] = round((time.monotonic() - t0) * 1000, 2)
    return result


# ─── Utilities ────────────────────────────────────────────────────────────────

def _safe_log_host(url: str) -> str:
    """Return only the hostname of a URL for safe log output."""
    try:
        return urlparse(url).hostname or "[unknown]"
    except Exception:
        return "[unknown]"


def _safe_close(*objects: object) -> None:
    """Close Playwright context/browser objects, silently ignoring errors."""
    for obj in objects:
        try:
            obj.close()  # type: ignore[attr-defined]
        except Exception:
            pass
