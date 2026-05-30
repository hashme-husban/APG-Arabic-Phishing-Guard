from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class URLFusionEngine:
    DEFAULTS = {
        "safe_max": 0.30,
        "phishing_min": 0.72,
        "rules_weight": 0.65,
        "model_weight": 0.35,
        "disagreement_gap": 0.35,
        "external_hit_floor": 0.92,
    }

    def __init__(self, config_path: str = "configs/url_layer_config.json") -> None:
        self.config = dict(self.DEFAULTS)

        path = Path(config_path)
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.config.update(loaded)
            except Exception:
                pass

        total = float(self.config["rules_weight"]) + float(self.config["model_weight"])
        if total <= 0:
            self.config["rules_weight"] = 0.5
            self.config["model_weight"] = 0.5
        else:
            self.config["rules_weight"] /= total
            self.config["model_weight"] /= total

    def label_from_score(self, score: float) -> str:
        safe_max = float(self.config["safe_max"])
        phishing_min = float(self.config["phishing_min"])

        if score >= phishing_min:
            return "phishing"
        if score <= safe_max:
            return "safe"
        return "suspicious"

    def _local_fusion(
        self,
        rules_result: Dict[str, Any],
        model_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rules_score = float(rules_result.get("rules_score", 0.5))

        if not model_result:
            confidence = max(0.40, min(0.95, 0.55 + abs(rules_score - 0.5)))
            return {
                "score": round(rules_score, 6),
                "label": self.label_from_score(rules_score),
                "confidence": round(confidence, 6),
                "mode": "rules_only",
                "agreement_score": None,
                "disagreement_score": None,
            }

        model_score = float(model_result.get("model_score", 0.5))
        rules_weight = float(self.config["rules_weight"])
        model_weight = float(self.config["model_weight"])

        base_score = (rules_weight * rules_score) + (model_weight * model_score)
        disagreement = abs(rules_score - model_score)

        if disagreement >= float(self.config["disagreement_gap"]):
            base_score = (0.75 * base_score) + (0.25 * 0.50)

        agreement = 1.0 - disagreement
        confidence = 0.55 + (0.25 * agreement) + (0.20 * abs(base_score - 0.5))
        confidence = max(0.0, min(0.99, confidence))

        return {
            "score": round(base_score, 6),
            "label": self.label_from_score(base_score),
            "confidence": round(confidence, 6),
            "mode": "hybrid_local",
            "agreement_score": round(agreement, 6),
            "disagreement_score": round(disagreement, 6),
        }

    def evaluate(
        self,
        rules_result: Dict[str, Any],
        model_result: Optional[Dict[str, Any]] = None,
        external_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        local = self._local_fusion(rules_result=rules_result, model_result=model_result)
        final_score = float(local["score"])
        final_mode = local["mode"]
        confidence = float(local["confidence"])

        if external_result and external_result.get("available"):
            label = str(external_result.get("label", "unknown")).strip().lower()
            hit = bool(external_result.get("hit", False))
            ext_score = float(external_result.get("score", 0.0) or 0.0)
            hit_floor = float(external_result.get("external_hit_floor", self.config.get("external_hit_floor", 0.92)))

            if hit and label in {"phishing", "malicious", "social_engineering"}:
                final_score = max(final_score, hit_floor, ext_score)
                final_mode = "hybrid_with_external_hit"
                confidence = max(confidence, 0.92)

            elif label == "safe" and final_score < 0.55:
                final_score = max(0.0, final_score * 0.90)
                final_mode = "hybrid_with_external_safe"
                confidence = max(confidence, 0.72)

        return {
            "fused_score": round(final_score, 6),
            "fused_label": self.label_from_score(final_score),
            "fusion_confidence": round(min(0.99, confidence), 6),
            "fusion_mode": final_mode,
            "agreement_score": local.get("agreement_score"),
            "disagreement_score": local.get("disagreement_score"),
        }
