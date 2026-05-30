from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class DecisionFusionEngine:
    """Layer 06 — Decision Fusion.

    Produces a stable final verdict while preserving backward compatibility with
    older config keys such as `legit_max` / `strong_legit`.
    """

    DEFAULT_CONFIG = {
        "base_weights": {
            "sender": 0.15,
            "policy": 0.15,
            "text": 0.40,
            "url": 0.30,
        },
        "safe_max": 0.32,
        "phishing_min": 0.72,
        "strong_phishing": 0.85,
        "strong_safe": 0.15,
        "high_risk_cutoff": 0.65,
        "low_risk_cutoff": 0.35,
        "huge_disagreement": 0.55,
        "adjustments": {
            "text_url_strong_boost": 0.08,
            "text_url_moderate_boost": 0.05,
            "text_policy_boost": 0.05,
            "sender_policy_text_boost": 0.04,
            "policy_sender_risk_boost": 0.05,
            "trusted_sender_discount": 0.04,
            "all_clear_discount": 0.06,
            "disagreement_pull_to_center": 0.25,
        },
        "confidence": {
            "noise_threshold": 70,
            "typo_threshold": 60,
            "noise_penalty": 0.04,
            "typo_penalty": 0.03,
        },
    }

    def __init__(self, config_path: str = "configs/fusion_layer_config.json") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def evaluate(
        self,
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        normalization_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}

        components = self._build_components(
            sender_result=sender_result,
            policy_result=policy_result,
            text_result=text_result,
            url_result=url_result,
        )

        normalized_weights = self._normalized_weights(components)
        base_score, contributions = self._weighted_score(components, normalized_weights)

        active_scores = [c["score"] for c in components.values() if c["available"] and c["score"] is not None]
        disagreement = self._compute_disagreement(active_scores)
        agreement = 1.0 - disagreement

        adjusted_score = self._apply_adjustments(
            base_score=base_score,
            components=components,
            disagreement=disagreement,
        )

        final_label = self._label_from_state(
            score=adjusted_score,
            components=components,
            disagreement=disagreement,
        )

        confidence = self._compute_confidence(
            final_label=final_label,
            adjusted_score=adjusted_score,
            components=components,
            agreement=agreement,
            disagreement=disagreement,
            normalization_result=normalization_result,
        )

        final_reasons = self._build_reasons(
            final_label=final_label,
            adjusted_score=adjusted_score,
            components=components,
            disagreement=disagreement,
            normalization_result=normalization_result,
        )

        recommendation = self._build_recommendation(final_label)

        dominant_layers = [
            {
                "layer": name,
                "score": round(float(info["score"]), 6),
                "weight": round(float(normalized_weights.get(name, 0.0)), 6),
                "contribution": round(float(contributions.get(name, 0.0)), 6),
            }
            for name, info in components.items()
            if info["available"] and info["score"] is not None
        ]
        dominant_layers.sort(key=lambda x: x["contribution"], reverse=True)

        return {
            "final_score": int(round(adjusted_score * 100)),
            "final_label": final_label,
            "confidence": round(confidence, 6),
            "final_reasons": final_reasons[:8],
            "recommendation": recommendation,
            "fusion_details": {
                "normalized_weights": {k: round(float(v), 6) for k, v in normalized_weights.items()},
                "component_contributions": {k: round(float(v), 6) for k, v in contributions.items()},
                "base_score": round(base_score, 6),
                "adjusted_score": round(adjusted_score, 6),
                "agreement_score": round(agreement, 6),
                "disagreement_score": round(disagreement, 6),
                "dominant_layers": dominant_layers[:4],
            },
        }

    def _build_components(
        self,
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        sender_status = sender_result.get("sender_status")
        policy_status = policy_result.get("policy_status")
        text_label = self._canonical_label(text_result.get("text_label"))
        url_label = self._canonical_label(url_result.get("url_label"))

        sender_score = self._safe_score(sender_result.get("sender_score"))
        policy_score = self._safe_score(policy_result.get("policy_score"))
        text_score = self._safe_score(text_result.get("text_score"))
        url_score = self._safe_score(url_result.get("url_score"))

        return {
            "sender": {
                "score": sender_score,
                "status": sender_status,
                "available": sender_score is not None and sender_status not in {"not_evaluated", "error", None},
            },
            "policy": {
                "score": policy_score,
                "status": policy_status,
                "available": policy_score is not None and policy_status not in {"not_evaluated", "error", None},
            },
            "text": {
                "score": text_score,
                "status": text_label,
                "available": text_score is not None and text_label not in {"not_evaluated", "error", None},
            },
            "url": {
                "score": url_score,
                "status": url_label,
                "available": url_score is not None and url_label not in {"not_evaluated", "error", "absent", None},
            },
        }

    def _normalized_weights(self, components: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        base_weights = self.config.get("base_weights", {})
        active = {name: float(base_weights.get(name, 0.0)) for name, info in components.items() if info["available"]}
        total = sum(active.values())
        if total <= 0:
            return {name: 0.0 for name in components.keys()}
        return {name: active.get(name, 0.0) / total for name in components.keys()}

    def _weighted_score(
        self,
        components: Dict[str, Dict[str, Any]],
        normalized_weights: Dict[str, float],
    ) -> tuple[float, Dict[str, float]]:
        score = 0.0
        contributions: Dict[str, float] = {}
        for name, info in components.items():
            weight = float(normalized_weights.get(name, 0.0))
            contribution = weight * float(info["score"]) if info["available"] and info["score"] is not None else 0.0
            contributions[name] = contribution
            score += contribution
        return max(0.0, min(1.0, score)), contributions

    def _apply_adjustments(
        self,
        base_score: float,
        components: Dict[str, Dict[str, Any]],
        disagreement: float,
    ) -> float:
        score = float(base_score)
        adj = self.config.get("adjustments", {})

        text_score = self._component_score(components, "text")
        url_score = self._component_score(components, "url")
        policy_score = self._component_score(components, "policy")
        sender_score = self._component_score(components, "sender")
        sender_status = components["sender"]["status"]
        policy_status = components["policy"]["status"]

        strong_phishing = float(self.config.get("strong_phishing", 0.85))
        high_risk_cutoff = float(self.config.get("high_risk_cutoff", 0.65))
        low_risk_cutoff = float(self.config.get("low_risk_cutoff", 0.35))
        huge_disagreement = float(self.config.get("huge_disagreement", 0.55))

        if text_score is not None and url_score is not None:
            if text_score >= strong_phishing and url_score >= strong_phishing:
                score += float(adj.get("text_url_strong_boost", 0.08))
            elif text_score >= high_risk_cutoff and url_score >= high_risk_cutoff:
                score += float(adj.get("text_url_moderate_boost", 0.05))

        if text_score is not None and policy_score is not None:
            if text_score >= strong_phishing and policy_score >= high_risk_cutoff:
                score += float(adj.get("text_policy_boost", 0.05))

        if policy_score is not None and sender_score is not None:
            if policy_score >= float(self.config.get("phishing_min", 0.72)) and sender_score >= high_risk_cutoff:
                score += float(adj.get("policy_sender_risk_boost", 0.05))

        if text_score is not None and sender_score is not None and policy_status == "conflicting":
            if text_score >= high_risk_cutoff and sender_score >= high_risk_cutoff:
                score += float(adj.get("sender_policy_text_boost", 0.04))

        if sender_status == "trusted":
            if ((text_score is None or text_score < high_risk_cutoff)
                    and (url_score is None or url_score < high_risk_cutoff)
                    and (policy_score is None or policy_score < high_risk_cutoff)):
                score -= float(adj.get("trusted_sender_discount", 0.04))

        if sender_status == "trusted" and policy_status == "compliant":
            if ((text_score is not None and text_score <= low_risk_cutoff)
                    and (url_score is None or url_score <= low_risk_cutoff)):
                score -= float(adj.get("all_clear_discount", 0.06))

        if disagreement >= huge_disagreement and not self._has_risk_consensus(components):
            pull = float(adj.get("disagreement_pull_to_center", 0.25))
            score = ((1.0 - pull) * score) + (pull * 0.50)

        return max(0.0, min(1.0, score))

    def _has_risk_consensus(self, components: Dict[str, Dict[str, Any]]) -> bool:
        strong_phishing = float(self.config.get("strong_phishing", 0.85))
        phishing_min = float(self.config.get("phishing_min", 0.72))
        text_score = self._component_score(components, "text")
        url_score = self._component_score(components, "url")
        policy_score = self._component_score(components, "policy")
        if text_score is not None and url_score is not None and text_score >= strong_phishing and url_score >= strong_phishing:
            return True
        if text_score is not None and policy_score is not None and text_score >= strong_phishing and policy_score >= phishing_min:
            return True
        return False

    def _label_from_state(self, score: float, components: Dict[str, Dict[str, Any]], disagreement: float) -> str:
        safe_max = float(self.config.get("safe_max", self.config.get("legit_max", 0.32)))
        phishing_min = float(self.config.get("phishing_min", 0.72))
        strong_phishing = float(self.config.get("strong_phishing", 0.85))
        strong_safe = float(self.config.get("strong_safe", self.config.get("strong_legit", 0.15)))
        huge_disagreement = float(self.config.get("huge_disagreement", 0.55))

        text_score = self._component_score(components, "text")
        url_score = self._component_score(components, "url")
        policy_score = self._component_score(components, "policy")
        sender_score = self._component_score(components, "sender")

        if text_score is not None and url_score is not None and text_score >= strong_phishing and url_score >= strong_phishing:
            return "phishing"
        if text_score is not None and policy_score is not None and text_score >= strong_phishing and policy_score >= phishing_min:
            return "phishing"
        if disagreement >= huge_disagreement and not self._has_risk_consensus(components):
            return "suspicious"
        if score >= phishing_min:
            return "phishing"

        high_risk = [s for s in [text_score, url_score, policy_score, sender_score] if s is not None and s >= float(self.config.get("high_risk_cutoff", 0.65))]
        if score <= safe_max and not high_risk:
            return "safe"

        low_risk = [s for s in [text_score, url_score, policy_score, sender_score] if s is not None and s <= strong_safe]
        if len(low_risk) >= 2 and score <= 0.40:
            return "safe"

        return "suspicious"

    def _compute_confidence(
        self,
        final_label: str,
        adjusted_score: float,
        components: Dict[str, Dict[str, Any]],
        agreement: float,
        disagreement: float,
        normalization_result: Dict[str, Any],
    ) -> float:
        evidence_count = sum(1 for comp in components.values() if comp["available"])
        support_ratio = self._support_ratio(final_label, components)
        safe_max = float(self.config.get("safe_max", self.config.get("legit_max", 0.32)))
        phishing_min = float(self.config.get("phishing_min", 0.72))

        if final_label == "phishing":
            margin = max(0.0, adjusted_score - phishing_min)
            margin_norm = margin / max(1e-6, (1.0 - phishing_min))
            confidence = 0.52 + (0.18 * agreement) + (0.18 * margin_norm) + (0.12 * support_ratio)
        elif final_label == "safe":
            margin = max(0.0, safe_max - adjusted_score)
            margin_norm = margin / max(1e-6, safe_max)
            confidence = 0.52 + (0.18 * agreement) + (0.18 * margin_norm) + (0.12 * support_ratio)
        else:
            center_bonus = 1.0 - min(1.0, abs(adjusted_score - 0.5) / 0.5)
            confidence = 0.46 + (0.18 * disagreement) + (0.14 * center_bonus) + (0.08 * min(1.0, evidence_count / 4.0))

        meta = self.config.get("confidence", {})
        noise_penalty = float(meta.get("noise_penalty", 0.04))
        typo_penalty = float(meta.get("typo_penalty", 0.03))
        if self._normalized_meta_score(normalization_result.get("noise_score")) >= float(meta.get("noise_threshold", 70)):
            confidence -= noise_penalty
        if self._normalized_meta_score(normalization_result.get("typo_score")) >= float(meta.get("typo_threshold", 60)):
            confidence -= typo_penalty

        return max(0.0, min(0.99, confidence))

    def _support_ratio(self, final_label: str, components: Dict[str, Dict[str, Any]]) -> float:
        scores = [comp["score"] for comp in components.values() if comp["available"] and comp["score"] is not None]
        if not scores:
            return 0.0
        if final_label == "phishing":
            supporting = [s for s in scores if s >= float(self.config.get("high_risk_cutoff", 0.65))]
        elif final_label == "safe":
            supporting = [s for s in scores if s <= float(self.config.get("low_risk_cutoff", 0.35))]
        else:
            supporting = [s for s in scores if 0.35 < s < 0.72]
        return max(0.0, min(1.0, len(supporting) / len(scores)))

    def _build_reasons(
        self,
        final_label: str,
        adjusted_score: float,
        components: Dict[str, Dict[str, Any]],
        disagreement: float,
        normalization_result: Dict[str, Any],
    ) -> List[str]:
        reasons: List[str] = []
        text_score = self._component_score(components, "text")
        url_score = self._component_score(components, "url")
        policy_score = self._component_score(components, "policy")
        sender_status = components["sender"]["status"]
        policy_status = components["policy"]["status"]
        url_status = components["url"]["status"]

        if text_score is not None and text_score >= 0.72:
            reasons.append("Text analysis strongly indicates phishing-like content.")
        elif text_score is not None and text_score <= 0.32:
            reasons.append("Text analysis leans toward safe content.")

        if url_score is not None and url_score >= 0.72:
            reasons.append("URL analysis indicates a high-risk or phishing-like link.")
        elif url_status == "absent":
            reasons.append("No URL was available, so the final decision relies on the other layers.")

        if policy_score is not None and policy_status == "conflicting":
            reasons.append("The requested behavior conflicts with the expected policy of the claimed entity.")
        elif policy_score is not None and policy_status == "compliant":
            reasons.append("The message behavior is broadly consistent with the claimed policy profile.")

        if sender_status == "trusted":
            reasons.append("Sender verification provides trusted evidence.")
        elif sender_status == "spoof_suspected":
            reasons.append("Sender identity appears inconsistent with the claimed entity.")
        elif sender_status == "unknown":
            reasons.append("Sender verification provides no trust evidence.")

        if text_score is not None and url_score is not None and text_score >= 0.85 and url_score >= 0.85:
            reasons.append("Text and URL layers strongly agree on a phishing verdict.")

        if disagreement >= float(self.config.get("huge_disagreement", 0.55)) and final_label == "suspicious":
            reasons.append("The layers disagree noticeably, so the final decision stays cautious.")

        meta = self.config.get("confidence", {})
        if self._normalized_meta_score(normalization_result.get("noise_score")) >= float(meta.get("noise_threshold", 70)):
            reasons.append("The message is unusually noisy, so certainty is slightly reduced.")
        if self._normalized_meta_score(normalization_result.get("typo_score")) >= float(meta.get("typo_threshold", 60)):
            reasons.append("Heavy typo/obfuscation patterns slightly reduce certainty.")

        if final_label == "phishing":
            reasons.append("The combined risk across the active layers is high enough for a phishing decision.")
        elif final_label == "safe":
            reasons.append("The combined evidence is low-risk enough for a safe decision.")
        else:
            reasons.append("The overall evidence stays in an ambiguous zone, so the message is marked suspicious.")

        return self._dedupe(reasons)

    def _build_recommendation(self, final_label: str) -> str:
        if final_label == "phishing":
            return "Do not click the link, do not reply with OTPs or credentials, and verify the request through the official website or app."
        if final_label == "suspicious":
            return "Do not take action yet. Verify the message through an official channel before opening links or sharing any sensitive data."
        return "No strong phishing evidence was found. For sensitive actions, it is still safer to use the official website or app directly."

    def _load_config(self) -> Dict[str, Any]:
        config = json.loads(json.dumps(self.DEFAULT_CONFIG))
        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    for key, value in loaded.items():
                        if key in {"base_weights", "adjustments", "confidence"} and isinstance(value, dict):
                            config[key].update(value)
                        else:
                            config[key] = value
            except Exception:
                pass
        if "safe_max" not in config and "legit_max" in config:
            config["safe_max"] = config["legit_max"]
        if "strong_safe" not in config and "strong_legit" in config:
            config["strong_safe"] = config["strong_legit"]
        return config

    def _safe_score(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            value = float(value)
        except Exception:
            return None
        return max(0.0, min(1.0, value))

    def _normalized_meta_score(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            score = float(value)
        except Exception:
            return 0.0
        if score <= 1.0:
            return max(0.0, score) * 100.0
        return max(0.0, min(100.0, score))

    def _component_score(self, components: Dict[str, Dict[str, Any]], name: str) -> Optional[float]:
        component = components.get(name, {})
        return component.get("score") if component.get("available") else None

    def _compute_disagreement(self, scores: List[float]) -> float:
        if len(scores) <= 1:
            return 0.0
        return max(0.0, min(1.0, max(scores) - min(scores)))

    def _canonical_label(self, value: Any) -> Any:
        label = str(value or "").strip().lower()
        if label in {"legit", "benign", "ham"}:
            return "safe"
        return label or value

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result
