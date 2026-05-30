from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class OutputFormatter:
    """Layer 07 — Explanation / Output.

    Builds three stable views:
    1) public_result  -> main API response for web/mobile clients
    2) mobile_result  -> short compact response for lightweight UI use
    3) debug_result   -> richer engineering view
    """

    DEFAULT_CONFIG = {
        "api_version": "apg_v1",
        "model_version": "apg_backend_v2",
        "public_reason_limit": 5,
        "mobile_reason_limit": 3,
        "debug_reason_limit": 8,
        "headlines": {
            "phishing": "High phishing risk detected",
            "suspicious": "Suspicious message detected",
            "safe": "No strong phishing evidence detected",
        },
        "summaries": {
            "phishing": "The message shows strong phishing indicators across multiple layers.",
            "suspicious": "The message is not clearly safe and should be verified before any action.",
            "safe": "No strong phishing indicators were found, but sensitive actions should still use official channels.",
        },
        "recommendations": {
            "phishing": "Do not interact with this message. Use the official app or website manually and report or block the sender.",
            "suspicious": "Pause before acting. Verify the request through an official channel before opening links or sharing information.",
            "safe": "No immediate threat is visible. Continue using normal caution and rely on official channels for sensitive actions.",
        },
        "actions": {
            "phishing": [
                "Do not click the link",
                "Do not reply with OTPs or credentials",
                "Verify through the official website or app",
            ],
            "suspicious": [
                "Do not take action yet",
                "Verify through an official channel",
                "Avoid opening links until verified",
            ],
            "safe": [
                "Use the official website or app for sensitive actions",
                "Stay cautious with future messages",
            ],
        },
    }

    def __init__(self, config_path: str = "configs/output_layer_config.json") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def evaluate(
        self,
        final_result: Dict[str, Any],
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        normalization_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}

        request_id = context.get("request_id")
        input_block = context.get("input", {}) or {}
        extracted_block = context.get("extracted", {}) or {}

        final_label = self._canonical_label(final_result.get("final_label", "suspicious"))
        final_score = int(final_result.get("final_score", 50))
        confidence = self._safe_float(final_result.get("confidence", 0.5), 0.5)

        headline = self.config["headlines"].get(final_label, "Message analysis completed")
        summary = self.config["summaries"].get(final_label, "Message analysis completed.")
        action_items = self._actions_for(final_label)
        recommendation = (
            final_result.get("recommendation")
            or self.config.get("recommendations", {}).get(final_label)
            or (action_items[0] if action_items else "Review the message carefully before taking action.")
        )

        reasons = self._select_reasons(
            final_reasons=final_result.get("final_reasons", []),
            sender_result=sender_result,
            policy_result=policy_result,
            text_result=text_result,
            url_result=url_result,
        )

        layer_breakdown = self._build_layer_breakdown(
            sender_result=sender_result,
            policy_result=policy_result,
            text_result=text_result,
            url_result=url_result,
        )

        risk_badges = self._build_risk_badges(
            sender_result=sender_result,
            policy_result=policy_result,
            text_result=text_result,
            url_result=url_result,
        )

        api_response = {
            "request_id": request_id,
            "api_version": self.config.get("api_version", "apg_v1"),
            "model_version": self.config.get("model_version", "apg_backend_v2"),
            "channel": input_block.get("channel"),
            "claimed_entity": (extracted_block.get("claimed_entity") or {}).get("display_name"),
            "final_label": final_label,
            "final_score": final_score,
            "confidence": round(confidence, 6),
            "headline": headline,
            "summary": summary,
            "reasons": reasons[: int(self.config.get("public_reason_limit", 5))],
            "recommendation": recommendation,
            "action_items": action_items,
            "risk_badges": risk_badges,
            "layer_breakdown": layer_breakdown,
            "analysis_mode": self._infer_analysis_mode(text_result, url_result),
            "input_warnings": input_block.get("warnings", []),
        }

        mobile_result = {
            "label": final_label,
            "final_label": final_label,
            "score": final_score,
            "final_score": final_score,
            "confidence": round(confidence, 6),
            "headline": headline,
            "short_summary": summary,
            "summary": summary,
            "top_reasons": reasons[: int(self.config.get("mobile_reason_limit", 3))],
            "action_items": action_items,
            "badges": risk_badges,
        }

        debug_result = {
            "request_id": request_id,
            "received_at": context.get("received_at"),
            "final_label": final_label,
            "final_score": final_score,
            "confidence": round(confidence, 6),
            "selected_reasons": reasons[: int(self.config.get("debug_reason_limit", 8))],
            "layer_breakdown": layer_breakdown,
            "risk_badges": risk_badges,
            "normalization_snapshot": {
                "noise_score": normalization_result.get("noise_score"),
                "typo_score": normalization_result.get("typo_score"),
                "repair_actions": normalization_result.get("repair_actions", []),
                "recovered_urls": normalization_result.get("recovered_urls", []),
            },
            "input_snapshot": {
                "sender": input_block.get("sender"),
                "raw_text": input_block.get("raw_text"),
                "urls": input_block.get("urls", []),
                "channel": input_block.get("channel"),
                "aliases_used": input_block.get("aliases_used", []),
                "warnings": input_block.get("warnings", []),
            },
            "text_details": text_result.get("fusion_details", text_result),
            "url_details": {
                "url_analysis_mode": url_result.get("url_analysis_mode"),
                "dominant_url": url_result.get("dominant_url"),
                "url_flags": url_result.get("url_flags", []),
                "url_details": url_result.get("url_details", []),
            },
            "fusion_details": final_result.get("fusion_details", {}),
        }

        return {
            "public_result": api_response,
            "mobile_result": mobile_result,
            "debug_result": debug_result,
        }

    def _select_reasons(
        self,
        final_reasons: List[str],
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
    ) -> List[str]:
        reasons: List[str] = []

        for reason in final_reasons or []:
            reason = self._safe_str(reason)
            if reason:
                reasons.append(reason)

        if len(reasons) < 3:
            sender_reasons = sender_result.get("sender_reasons", [])
            policy_reasons = policy_result.get("policy_reasons", [])
            text_reasons = text_result.get("text_reasons", [])
            url_reasons = url_result.get("url_reasons", [])

            for source_list in [text_reasons, url_reasons, policy_reasons, sender_reasons]:
                for item in source_list:
                    item = self._safe_str(item)
                    if item and item not in reasons:
                        reasons.append(item)
                    if len(reasons) >= int(self.config.get("debug_reason_limit", 8)):
                        break
                if len(reasons) >= int(self.config.get("debug_reason_limit", 8)):
                    break

        return self._dedupe(reasons)

    def _build_layer_breakdown(
        self,
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "sender": {
                "status": sender_result.get("sender_status"),
                "score": self._to_percent(sender_result.get("sender_score")),
            },
            "policy": {
                "status": policy_result.get("policy_status"),
                "score": self._to_percent(policy_result.get("policy_score")),
            },
            "text": {
                "status": self._canonical_label(text_result.get("text_label")),
                "score": self._to_percent(text_result.get("text_score")),
            },
            "url": {
                "status": self._canonical_label(url_result.get("url_label")),
                "score": self._to_percent(url_result.get("url_score")),
            },
        }

    def _build_risk_badges(
        self,
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        badges = [
            {
                "layer": "sender",
                "status": sender_result.get("sender_status"),
                "score": self._to_percent(sender_result.get("sender_score")),
            },
            {
                "layer": "policy",
                "status": policy_result.get("policy_status"),
                "score": self._to_percent(policy_result.get("policy_score")),
            },
            {
                "layer": "text",
                "status": self._canonical_label(text_result.get("text_label")),
                "score": self._to_percent(text_result.get("text_score")),
            },
            {
                "layer": "url",
                "status": self._canonical_label(url_result.get("url_label")),
                "score": self._to_percent(url_result.get("url_score")),
            },
        ]
        return [badge for badge in badges if badge["status"] is not None]

    def _actions_for(self, final_label: str) -> List[str]:
        return list(self.config.get("actions", {}).get(final_label, []))

    def _to_percent(self, score: Any) -> Optional[int]:
        value = self._safe_float(score, None)
        if value is None:
            return None
        return int(round(max(0.0, min(1.0, value)) * 100))

    def _safe_float(self, value: Any, default: Optional[float]) -> Optional[float]:
        if value is None:
            return default
        try:
            return float(value)
        except Exception:
            return default

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _canonical_label(self, value: Any) -> str:
        label = self._safe_str(value).lower() or "suspicious"
        if label in {"legit", "benign", "ham"}:
            return "safe"
        return label

    def _infer_analysis_mode(self, text_result: Dict[str, Any], url_result: Dict[str, Any]) -> str:
        text_mode = ((text_result.get("fusion_details") or {}).get("mode") or "text_default")
        url_mode = url_result.get("url_analysis_mode") or "url_default"
        return f"{text_mode}+{url_mode}"

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _load_config(self) -> Dict[str, Any]:
        config = json.loads(json.dumps(self.DEFAULT_CONFIG))

        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    for key, value in loaded.items():
                        if key in {"headlines", "summaries", "recommendations", "actions"} and isinstance(value, dict):
                            config[key].update(value)
                        else:
                            config[key] = value
            except Exception:
                pass

        # Backward compatibility with older configs using "legit"
        if "legit" in config.get("headlines", {}) and "safe" not in config["headlines"]:
            config["headlines"]["safe"] = config["headlines"]["legit"]
        if "legit" in config.get("summaries", {}) and "safe" not in config["summaries"]:
            config["summaries"]["safe"] = config["summaries"]["legit"]
        if "legit" in config.get("recommendations", {}) and "safe" not in config["recommendations"]:
            config["recommendations"]["safe"] = config["recommendations"]["legit"]
        if "legit" in config.get("actions", {}) and "safe" not in config["actions"]:
            config["actions"]["safe"] = config["actions"]["legit"]

        return config
