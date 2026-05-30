from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok - {message}")


def main() -> int:
    os.environ.setdefault("DYNAMIC_URL_ANALYSIS_ENABLED", "false")

    from app.config import get_settings
    from app.routers.admin import _playwright_available
    from app.services.risk_engine.dynamic_url_analysis import analyze_url_dynamically
    from app.services.url_sandbox.playwright_sandbox import run_sandbox

    settings = get_settings()
    _check(settings.dynamic_url_analysis_enabled is False, "dynamic URL analysis default remains disabled")
    _check(settings.dynamic_url_analysis_timeout_seconds >= 1, "timeout config is readable")
    _check(settings.dynamic_url_analysis_observation_ms >= 0, "observation config is readable")
    _check(settings.dynamic_url_analysis_time_simulation_enabled is False, "time simulation default remains disabled")
    _check(settings.dynamic_url_analysis_simulated_minutes == 0, "simulated minutes default is zero")

    disabled = analyze_url_dynamically("https://example.com", enabled=False)
    _check(disabled.status == "disabled", "disabled analysis returns without browser/network")

    blocked = run_sandbox("http://127.0.0.1/admin", timeout_seconds=1)
    _check(blocked["status"] == "failed", "blocked local URL fails closed")
    _check(blocked["error"] is not None, "blocked local URL returns safe error")

    available = _playwright_available()
    print(f"info - playwright_chromium_available={available}")
    print("dynamic URL sandbox validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
