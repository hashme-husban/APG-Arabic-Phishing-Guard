from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class TextFusionEngine:
    """Fuse semantic + lexical risk into a final text decision."""

    DEFAULTS = {
        "semantic_weight": 0.58,
        "lexical_weight": 0.42,
        "safe_max": 0.35,
        "phishing_min": 0.72,
        "strong_safe": 0.20,
        "strong_phishing": 0.85,
        "disagreement_gap": 0.30,
        "suspicious_center_margin": 0.18,
        "min_tokens_for_full_confidence": 4,
    }

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config = dict(self.DEFAULTS)
        if config_path:
            path = Path(config_path)
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.config.update(loaded)
                except Exception:
                    pass

        total_weight = float(self.config["semantic_weight"]) + float(self.config["lexical_weight"])
        if total_weight <= 0:
            self.config["semantic_weight"] = 0.5
            self.config["lexical_weight"] = 0.5
        else:
            self.config["semantic_weight"] /= total_weight
            self.config["lexical_weight"] /= total_weight

    def _safe_score(self, value: Any, default: float = 0.5) -> float:
        try:
            value = float(value)
        except Exception:
            return default
        return max(0.0, min(1.0, value))

    def _token_count(self, text: str) -> int:
        text = (text or "").strip()
        if not text:
            return 0
        return len([tok for tok in text.split() if tok.strip()])

    def label_from_score(self, score: float) -> str:
        safe_max = float(self.config["safe_max"])
        phishing_min = float(self.config["phishing_min"])
        if score >= phishing_min:
            return "phishing"
        if score <= safe_max:
            return "safe"
        return "suspicious"

    def _component_reason(self, name: str, score: float) -> str:
        if score >= 0.85:
            return f"{name} sees very strong phishing evidence in the text."
        if score >= 0.72:
            return f"{name} sees clear phishing-leaning patterns."
        if score <= 0.20:
            return f"{name} sees strong legitimate patterns."
        if score <= 0.35:
            return f"{name} leans toward legitimate language."
        return f"{name} is not fully certain from the text alone."

    def _label_from_scores(self, semantic_score: float, lexical_score: float, fused_score: float) -> str:
        strong_safe = float(self.config["strong_safe"])
        strong_phishing = float(self.config["strong_phishing"])
        safe_max = float(self.config["safe_max"])
        phishing_min = float(self.config["phishing_min"])
        disagreement_gap = float(self.config["disagreement_gap"])
        disagreement = abs(semantic_score - lexical_score)

        both_strong_safe = semantic_score <= strong_safe and lexical_score <= strong_safe
        both_strong_phishing = semantic_score >= strong_phishing and lexical_score >= strong_phishing
        opposite_extremes = (
            (semantic_score <= safe_max and lexical_score >= phishing_min)
            or (lexical_score <= safe_max and semantic_score >= phishing_min)
        )

        if both_strong_safe:
            return "safe"
        if both_strong_phishing:
            return "phishing"
        if opposite_extremes or disagreement >= disagreement_gap:
            return "suspicious"
        return self.label_from_score(fused_score)

    def _compute_confidence(
        self,
        label: str,
        fused_score: float,
        semantic_score: float,
        lexical_score: float,
        token_count: int,
    ) -> float:
        safe_max = float(self.config["safe_max"])
        phishing_min = float(self.config["phishing_min"])
        center_margin = float(self.config["suspicious_center_margin"])
        min_tokens = int(self.config["min_tokens_for_full_confidence"])

        disagreement = abs(semantic_score - lexical_score)
        agreement = 1.0 - disagreement

        if label == "phishing":
            margin = max(0.0, fused_score - phishing_min) / max(1e-6, (1.0 - phishing_min))
            confidence = 0.55 + (agreement * 0.25) + (margin * 0.20)
        elif label == "safe":
            margin = max(0.0, safe_max - fused_score) / max(1e-6, safe_max)
            confidence = 0.55 + (agreement * 0.25) + (margin * 0.20)
        else:
            center_distance = abs(fused_score - 0.5)
            center_bonus = max(0.0, center_margin - center_distance) / max(1e-6, center_margin)
            confidence = 0.48 + (min(0.20, disagreement * 0.45)) + (center_bonus * 0.15)

        if token_count < min_tokens:
            confidence -= 0.08
        return max(0.0, min(0.99, confidence))

    def evaluate(
        self,
        semantic_result: Dict[str, Any],
        lexical_result: Dict[str, Any],
        normalized_text: str = "",
        raw_text: str = "",
    ) -> Dict[str, Any]:
        semantic_score = self._safe_score(semantic_result.get("risk_score"))
        lexical_score = self._safe_score(lexical_result.get("risk_score"))
        semantic_weight = float(self.config["semantic_weight"])
        lexical_weight = float(self.config["lexical_weight"])

        base_score = (semantic_weight * semantic_score) + (lexical_weight * lexical_score)
        disagreement = abs(semantic_score - lexical_score)
        agreement = 1.0 - disagreement

        adjusted_score = base_score
        if disagreement >= float(self.config["disagreement_gap"]):
            adjusted_score = (0.70 * base_score) + (0.30 * 0.50)

        token_count = self._token_count(normalized_text or raw_text)
        if token_count < int(self.config["min_tokens_for_full_confidence"]):
            adjusted_score = (0.90 * adjusted_score) + (0.10 * 0.50)

        label = self._label_from_scores(semantic_score, lexical_score, adjusted_score)
        confidence = self._compute_confidence(
            label=label,
            fused_score=adjusted_score,
            semantic_score=semantic_score,
            lexical_score=lexical_score,
            token_count=token_count,
        )

        reasons: List[str] = [
            self._component_reason("Semantic model", semantic_score),
            self._component_reason("Lexical model", lexical_score),
        ]
        if disagreement >= float(self.config["disagreement_gap"]):
            reasons.append("Semantic and lexical layers disagree noticeably, so the text is treated cautiously.")
        elif agreement >= 0.75:
            reasons.append("Semantic and lexical layers strongly agree on the text signal.")

        if label == "phishing":
            reasons.append("The fused text risk is high enough to classify the message as phishing.")
        elif label == "safe":
            reasons.append("The fused text risk is low enough to classify the message as safe.")
        else:
            reasons.append("The fused text signal falls in an ambiguous zone, so the message is marked suspicious.")

        if token_count < int(self.config["min_tokens_for_full_confidence"]):
            reasons.append("The message is short, so text-only certainty is limited.")

        return {
            "text_score": round(adjusted_score, 6),
            "text_label": label,
            "confidence": round(confidence, 6),
            "agreement_score": round(agreement, 6),
            "disagreement_score": round(disagreement, 6),
            "text_reasons": reasons[:6],
        }
