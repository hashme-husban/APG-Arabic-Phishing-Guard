"""
APG Risk Intelligence Engine v1 — URL Providers

Documents and re-exports the provider abstraction from the v5 URL reputation
service.  The actual provider implementations live in:

    app.services.analyzer.url_reputation.URLReputationService

This module exists as a named entry point so that adding or overriding a
provider in future is a single-file change, and so that tests can import
the provider status helper without importing the full service.
"""
from __future__ import annotations

import os


def get_provider_status() -> dict[str, dict[str, bool | str]]:
    """
    Returns the configuration status of each external URL reputation provider.

    A provider is "configured" when its API key environment variable is set.
    Missing key → provider is skipped (not an error).
    """
    return {
        "google_safe_browsing": {
            "configured": bool(os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")),
            "env_key": "GOOGLE_SAFE_BROWSING_API_KEY",
        },
        "virustotal": {
            "configured": bool(os.getenv("VIRUSTOTAL_API_KEY")),
            "env_key": "VIRUSTOTAL_API_KEY",
        },
        "urlscan": {
            "configured": bool(os.getenv("URLSCAN_API_KEY")),
            "env_key": "URLSCAN_API_KEY",
        },
        "phishtank": {
            "configured": bool(os.getenv("PHISHTANK_API_KEY")),
            "env_key": "PHISHTANK_API_KEY",
        },
    }


def url_reputation_enabled() -> bool:
    return os.getenv("URL_REPUTATION_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }
