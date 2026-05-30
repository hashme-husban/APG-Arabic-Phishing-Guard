"""
APG Hybrid Analyzer Facade

Routes analysis calls to either:
  - APG-Risk-Intelligence-Engine v1 (default, APG_ANALYZER_ENGINE=risk_engine_v1)
  - APG-Hybrid-Analyzer v5       (legacy fallback, APG_ANALYZER_ENGINE=v5)

Both engines expose the same interface:
  analyze(text, ...) -> HybridResult
  status() -> dict
  check_url(url, ...) -> dict

Callers (routers, admin console, tests) do not need to know which engine
is active — they call get_hybrid_analyzer() and use the result.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from app.services.analyzer.schemas import HybridResult


def _engine_name() -> str:
    return os.getenv("APG_ANALYZER_ENGINE", "risk_engine_v1").strip().lower()


def get_hybrid_analyzer():
    """
    Return the active analyzer service (cached singleton).

    Switching APG_ANALYZER_ENGINE at runtime requires process restart because
    both engines are cached with lru_cache.
    """
    name = _engine_name()
    if name == "v5":
        from app.services.analyzer.service import get_analyzer_service
        return get_analyzer_service()
    # Default: risk_engine_v1
    from app.services.risk_engine.service import get_risk_engine_service
    return get_risk_engine_service()


def get_analyzer_status() -> dict[str, Any]:
    return get_hybrid_analyzer().status()


# ─── Legacy class wrapper (kept for any code that instantiates HybridAnalyzer
#     directly rather than calling get_hybrid_analyzer()) ─────────────────────

class HybridAnalyzer:
    """Backward-compatible facade that delegates to the active engine."""

    def __init__(self) -> None:
        self._service = get_hybrid_analyzer()

    def analyze(
        self,
        text: str,
        source: str = "manual",
        sender: str = "",
        package_name: str = "",
        extra_urls: list[str] | None = None,
        is_known_contact: bool | None = None,
        sender_trust: str = "unknown",
        sender_name: str = "",
        source_app: str = "",
        mock_url_reputation: dict[str, Any] | None = None,
    ) -> HybridResult:
        return self._service.analyze(
            text,
            source=source,
            sender=sender,
            package_name=package_name,
            extra_urls=extra_urls,
            is_known_contact=is_known_contact,
            sender_trust=sender_trust,
            sender_name=sender_name,
            source_app=source_app,
            mock_url_reputation=mock_url_reputation,
        )

    def status(self) -> dict[str, Any]:
        return self._service.status()

    def check_url(
        self, url: str, mock_url_reputation: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._service.check_url(url, mock_url_reputation=mock_url_reputation)
