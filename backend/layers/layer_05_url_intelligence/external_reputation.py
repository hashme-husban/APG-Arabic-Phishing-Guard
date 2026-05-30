from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class ExternalReputationAdapter:
    """
    Generic optional webhook adapter.

    Expected webhook response JSON:
    {
      "provider": "custom_reputation",
      "label": "phishing|safe|suspicious|unknown",
      "score": 0.0,
      "hit": false,
      "reason": "..."
    }
    """

    def __init__(self, config_path: str = "configs/url_layer_config.json") -> None:
        self.config = self._load_json(config_path)
        self.enabled = bool(self.config.get("enable_external_reputation", False))
        self.provider = str(self.config.get("external_provider", "webhook")).strip().lower()
        self.timeout_seconds = int(self.config.get("external_timeout_seconds", 5))
        self.min_trigger_score = float(self.config.get("external_min_trigger_score", 0.55))
        self.force_on_flags = set(self.config.get("external_force_on_flags", []))
        self.webhook_url = (
            os.getenv("APG_URL_REPUTATION_WEBHOOK")
            or self.config.get("external_webhook_url", "")
        )
        self.external_hit_floor = float(self.config.get("external_hit_floor", 0.92))

    def _load_json(self, path_str: str) -> Dict[str, Any]:
        path = Path(path_str)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def should_lookup(self, local_score: float, flags: List[str]) -> bool:
        if not self.enabled:
            return False
        if local_score >= self.min_trigger_score:
            return True
        return any(flag in self.force_on_flags for flag in flags)

    def evaluate(
        self,
        canonical_url: str,
        local_score: float,
        flags: List[str],
    ) -> Optional[Dict[str, Any]]:
        if not self.should_lookup(local_score, flags):
            return None

        if self.provider != "webhook" or not self.webhook_url:
            return {
                "lookup_attempted": False,
                "provider": self.provider or "unknown",
                "available": False,
                "reason": "External reputation is enabled but no supported provider configuration was found."
            }

        payload = {
            "url": canonical_url,
            "local_score": local_score,
            "flags": flags,
        }

        request = Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            return {
                "lookup_attempted": True,
                "provider": "webhook",
                "available": False,
                "error": str(exc),
            }

        if not isinstance(data, dict):
            return {
                "lookup_attempted": True,
                "provider": "webhook",
                "available": False,
                "error": "Webhook returned a non-dict response.",
            }

        label = str(data.get("label", "unknown")).strip().lower()
        score = float(data.get("score", 0.0) or 0.0)
        hit = bool(data.get("hit", False))
        reason = str(data.get("reason", "")).strip()

        return {
            "lookup_attempted": True,
            "provider": data.get("provider", "webhook"),
            "available": True,
            "label": label,
            "score": max(0.0, min(1.0, score)),
            "hit": hit,
            "reason": reason,
            "external_hit_floor": self.external_hit_floor,
        }
