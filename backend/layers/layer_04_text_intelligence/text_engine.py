from __future__ import annotations

from typing import Any, Dict, Optional

from layers.common import TextSignalAnalyzer
from .fusion import TextFusionEngine


class TextIntelligenceEngine:
    """Layer 04 wrapper with graceful model fallback and deterministic heuristics."""

    def __init__(
        self,
        semantic_adapter: Any = None,
        lexical_adapter: Any = None,
        fusion_engine: Optional[TextFusionEngine] = None,
        heuristic_analyzer: Optional[TextSignalAnalyzer] = None,
    ) -> None:
        self.semantic_adapter = semantic_adapter
        self.lexical_adapter = lexical_adapter
        self.fusion_engine = fusion_engine or TextFusionEngine()
        self.heuristic_analyzer = heuristic_analyzer or TextSignalAnalyzer()

    def _neutral_model_result(self, model_type: str) -> Dict[str, Any]:
        return {
            "model_type": model_type,
            "model_version": f"{model_type}_unavailable",
            "risk_score": 0.5,
            "component_label": "suspicious",
            "confidence": 0.0,
            "available": False,
        }

    def _evaluate_adapter(self, adapter: Any, text: str, model_type: str) -> Dict[str, Any]:
        if adapter is None or not hasattr(adapter, "evaluate"):
            return self._neutral_model_result(model_type)
        try:
            return adapter.evaluate(text)
        except Exception as exc:
            result = self._neutral_model_result(model_type)
            result["init_error"] = str(exc)
            return result

    def _blend_with_heuristics(
        self,
        fused_score: float,
        heuristic_score: float,
        semantic_result: Dict[str, Any],
        lexical_result: Dict[str, Any],
    ) -> float:
        semantic_available = bool(semantic_result.get("available", True))
        lexical_available = bool(lexical_result.get("available", True))
        available_count = int(semantic_available) + int(lexical_available)

        if available_count == 0:
            return heuristic_score

        disagreement = abs(float(semantic_result.get("risk_score", 0.5)) - float(lexical_result.get("risk_score", 0.5)))
        blended = fused_score

        if heuristic_score >= 0.82 and fused_score < 0.72:
            blended = max(blended, (0.74 * fused_score) + (0.26 * heuristic_score))
        elif heuristic_score <= 0.24 and fused_score <= 0.40:
            blended = min(blended, (0.80 * fused_score) + (0.20 * heuristic_score))

        if disagreement >= 0.35:
            blended = (0.82 * blended) + (0.18 * heuristic_score)

        return max(0.0, min(1.0, blended))

    def evaluate(
        self,
        raw_text: str,
        normalized_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        text_for_models = (normalized_text or raw_text or "").strip()

        if not text_for_models:
            return {
                "semantic_score": 0.5,
                "lexical_score": 0.5,
                "heuristic_score": 0.5,
                "text_score": 0.5,
                "text_label": "suspicious",
                "text_reasons": ["No usable text was available for Layer 04."],
                "text_confidence": 0.0,
                "semantic_details": {},
                "lexical_details": {},
                "heuristic_details": {},
                "fusion_details": {},
            }

        heuristic_result = self.heuristic_analyzer.analyze(
            raw_text=raw_text,
            normalized_text=text_for_models,
            channel=str((context.get("input") or {}).get("channel", "")),
            claimed_entity=(context.get("extracted") or {}).get("claimed_entity"),
        )

        semantic_result = self._evaluate_adapter(self.semantic_adapter, text_for_models, "semantic")
        lexical_result = self._evaluate_adapter(self.lexical_adapter, text_for_models, "lexical")

        semantic_available = bool(semantic_result.get("available", True))
        lexical_available = bool(lexical_result.get("available", True))

        if semantic_available or lexical_available:
            fusion_result = self.fusion_engine.evaluate(
                semantic_result=semantic_result,
                lexical_result=lexical_result,
                normalized_text=text_for_models,
                raw_text=raw_text,
            )
            blended_score = self._blend_with_heuristics(
                fused_score=float(fusion_result.get("text_score", 0.5)),
                heuristic_score=float(heuristic_result.get("risk_score", 0.5)),
                semantic_result=semantic_result,
                lexical_result=lexical_result,
            )
            text_label = self.fusion_engine.label_from_score(blended_score)
            text_confidence = max(
                float(fusion_result.get("confidence", 0.0) or 0.0),
                float(heuristic_result.get("confidence", 0.0) or 0.0) * 0.85,
            )
            reasons = list(fusion_result.get("text_reasons", []))
            for reason in heuristic_result.get("reasons", []):
                if reason not in reasons:
                    reasons.append(reason)
        else:
            blended_score = float(heuristic_result.get("risk_score", 0.5))
            text_label = str(heuristic_result.get("component_label", "suspicious"))
            text_confidence = float(heuristic_result.get("confidence", 0.0) or 0.0)
            reasons = list(heuristic_result.get("reasons", []))
            fusion_result = {
                "text_score": blended_score,
                "text_label": text_label,
                "confidence": text_confidence,
                "agreement_score": None,
                "disagreement_score": None,
                "text_reasons": reasons,
                "mode": "heuristic_only",
            }

        if semantic_result.get("init_error"):
            reasons.append("Semantic model fallback was used.")
        if lexical_result.get("init_error"):
            reasons.append("Lexical model fallback was used.")

        return {
            "semantic_score": semantic_result.get("risk_score"),
            "lexical_score": lexical_result.get("risk_score"),
            "heuristic_score": heuristic_result.get("risk_score"),
            "text_score": round(float(blended_score), 6),
            "text_label": text_label,
            "text_reasons": reasons[:8],
            "text_confidence": round(float(text_confidence), 6),
            "semantic_details": semantic_result,
            "lexical_details": lexical_result,
            "heuristic_details": heuristic_result,
            "fusion_details": fusion_result,
        }
