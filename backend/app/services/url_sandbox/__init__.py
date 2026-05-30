"""
APG URL Sandbox package.

Provides safe, isolated URL analysis using Playwright (optional dependency).
Import `run_sandbox` to execute a dynamic analysis.
Import `validate_url_safe` for URL scheme + DNS validation without running a browser.
"""
from .url_validator import (
    URLValidationError,
    validate_url_scheme,
    resolve_and_validate_host,
    validate_url_safe,
    _BLOCKED_NETWORKS,
    _is_ip_blocked,
)
from .playwright_sandbox import run_sandbox

__all__ = [
    "URLValidationError",
    "validate_url_scheme",
    "resolve_and_validate_host",
    "validate_url_safe",
    "_BLOCKED_NETWORKS",
    "_is_ip_blocked",
    "run_sandbox",
]
