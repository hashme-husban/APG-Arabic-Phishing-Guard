from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from layers.common import TextSignalAnalyzer, normalize_loose_text


class EntityPolicyEngine:
    """Layer 02 — Entity Policy with rules + heuristic fallback."""

    DEFAULT_CONFIG = {
        "unknown_policy_score": 0.5,
        "compliant_max": 0.32,
        "conflicting_min": 0.70,
        "trusted_sender_discount": 0.06,
        "spoof_sender_boost": 0.08,
    }

    URL_HINT_REGEX = re.compile(r"(?:https?://|www\.|hxxp://|hxxps://|\[\.\]|الرابط|link|url)", re.IGNORECASE)

    def __init__(self, rules_path: str = "configs/entity_policy_rules.json", config_path: str = "configs/entity_policy_config.json") -> None:
        self.rules_path = Path(rules_path)
        self.config_path = Path(config_path)
        self.rules = self._load_rules()
        self.config = self._load_config()
        self.term_sets = self.rules.get("term_sets", {})
        self.global_rules = self.rules.get("global_rules", [])
        self.sector_rules = self.rules.get("sectors", {})
        self.sector_hints = self.rules.get("sector_hints", {})
        self.signal_analyzer = TextSignalAnalyzer()

    def evaluate(
        self,
        raw_text: str,
        claimed_entity: Optional[Dict[str, Any]] = None,
        sender_result: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw_text = self._safe_str(raw_text)
        claimed_entity = claimed_entity or {}
        sender_result = sender_result or {}

        if not raw_text:
            unknown_score = self._cfg("unknown_policy_score", 0.5)
            return {
                "policy_status": "unknown",
                "policy_score": round(float(unknown_score), 6),
                "policy_flags": [],
                "policy_reasons": ["No text was available for policy evaluation."],
                "policy_details": {"sector_used": None, "detected_categories": [], "baseline_score": unknown_score},
            }

        normalized_text = normalize_loose_text(raw_text)
        detected_categories = self._detect_categories(normalized_text, raw_text)
        heuristic = self.signal_analyzer.analyze(
            raw_text=raw_text,
            normalized_text=normalized_text,
            channel=str(((context or {}).get("input") or {}).get("channel", "")),
            claimed_entity=claimed_entity,
        )

        sector_used = claimed_entity.get("sector") or self._infer_sector_from_text(normalized_text)
        entity_name = claimed_entity.get("display_name") or claimed_entity.get("entity_id")

        rules_score = None
        flags: List[str] = []
        reasons: List[str] = []
        baseline_score = float(self._cfg("unknown_policy_score", 0.5))

        if sector_used and sector_used in self.sector_rules:
            sector_profile = self.sector_rules.get(sector_used, {})
            baseline_score = float(sector_profile.get("baseline_score", 0.35))
            score = baseline_score

            for rule in self.global_rules:
                if self._rule_matches(rule, detected_categories):
                    score = max(score, float(rule.get("risk", score)))
                    if rule.get("flag"):
                        flags.append(rule["flag"])
                    if rule.get("reason"):
                        reasons.append(rule["reason"])

            for rule in sector_profile.get("allowed_rules", []):
                if self._rule_matches(rule, detected_categories):
                    score = max(0.0, score + float(rule.get("adjustment", 0.0)))
                    if rule.get("reason"):
                        reasons.append(rule["reason"])

            for rule in sector_profile.get("risky_rules", []):
                if self._rule_matches(rule, detected_categories):
                    score = max(score, float(rule.get("risk", score)))
                    if rule.get("flag"):
                        flags.append(rule["flag"])
                    if rule.get("reason"):
                        reasons.append(rule["reason"])

            rules_score = max(0.0, min(1.0, score))

        heuristic_score, heuristic_flags, heuristic_reasons = self._heuristic_policy_score(
            categories=detected_categories,
            heuristic_result=heuristic,
            claimed_entity=claimed_entity,
        )
        flags.extend(heuristic_flags)
        reasons.extend(heuristic_reasons)

        if rules_score is None:
            score = heuristic_score
            baseline_score = float(self._cfg("unknown_policy_score", 0.5))
        else:
            if heuristic_score >= 0.75 and rules_score < 0.65:
                score = (0.78 * rules_score) + (0.22 * heuristic_score)
            else:
                score = max(rules_score, (0.88 * rules_score) + (0.12 * heuristic_score))

        sender_status = sender_result.get("sender_status")
        if sender_status == "trusted":
            score = max(0.0, score - float(self._cfg("trusted_sender_discount", 0.06)))
            reasons.append("Trusted sender evidence slightly reduces policy risk.")
        elif sender_status == "spoof_suspected":
            score = min(1.0, score + float(self._cfg("spoof_sender_boost", 0.08)))
            reasons.append("Sender spoof suspicion increases policy risk.")

        if entity_name:
            reasons.insert(0, f"Policy evaluation was performed against the claimed sector/entity profile: {entity_name}.")

        score = max(0.0, min(1.0, score))
        policy_status = self._status_from_score(score)
        return {
            "policy_status": policy_status,
            "policy_score": round(score, 6),
            "policy_flags": self._dedupe(flags),
            "policy_reasons": self._dedupe(reasons)[:10],
            "policy_details": {
                "sector_used": sector_used,
                "detected_categories": sorted(detected_categories),
                "baseline_score": round(baseline_score, 6),
                "rules_score": None if rules_score is None else round(rules_score, 6),
                "heuristic_score": round(heuristic_score, 6),
                "claimed_entity_id": claimed_entity.get("entity_id"),
                "sender_status": sender_status,
            },
        }

    def _rule_matches(self, rule: Dict[str, Any], detected_categories: Set[str]) -> bool:
        required_all = set(rule.get("all", []))
        required_any = set(rule.get("any", []))
        if required_all and not required_all.issubset(detected_categories):
            return False
        if required_any and not (required_any & detected_categories):
            return False
        return bool(required_all or required_any)

    def _detect_categories(self, normalized_text: str, raw_text: str) -> Set[str]:
        detected = set(self.signal_analyzer.detect_categories(raw_text, normalized_text))
        for category, terms in self.term_sets.items():
            for term in terms:
                term_norm = self._normalize_text(term)
                if term_norm and term_norm in normalized_text:
                    detected.add(category)
                    break
        if self.URL_HINT_REGEX.search(raw_text):
            detected.add("link_words")
        return detected

    def _heuristic_policy_score(
        self,
        categories: Set[str],
        heuristic_result: Dict[str, Any],
        claimed_entity: Dict[str, Any],
    ) -> tuple[float, List[str], List[str]]:
        score = 0.28
        flags: List[str] = []
        reasons: List[str] = []

        if "safe_context" in categories and not ({"credential_request", "otp_request", "threat", "urgency"} & categories):
            score -= 0.12
            reasons.append("The message resembles a routine reminder or benign informational update.")
            flags.append("ROUTINE_CONTEXT")

        if "credential_request" in categories:
            score += 0.22
            reasons.append("Policy risk increases because the message asks for credentials or account secrets.")
            flags.append("CREDENTIAL_REQUEST")
        if "otp_request" in categories:
            score += 0.24
            reasons.append("Policy risk increases because the message asks for an OTP or verification code.")
            flags.append("OTP_REQUEST")
        if "payment_request" in categories:
            score += 0.10
            reasons.append("The message requests money-related action, which deserves caution.")
            flags.append("PAYMENT_REQUEST")
        if "action_link" in categories:
            score += 0.10
            reasons.append("The message pushes the user toward a link or immediate action.")
            flags.append("ACTION_LINK")
        if "urgency" in categories:
            score += 0.06
            reasons.append("Urgency language is present.")
            flags.append("URGENCY")
        if "threat" in categories:
            score += 0.08
            reasons.append("Threat or suspension language is present.")
            flags.append("THREAT")
        if "prize_or_refund" in categories:
            score += 0.08
            reasons.append("Prize/refund language is often abused in social engineering.")
            flags.append("PRIZE_OR_REFUND")
        if "attachment_or_app" in categories:
            score += 0.08
            reasons.append("The message references an attachment, document, or app install flow.")
            flags.append("ATTACHMENT_OR_APP")

        if {"otp_request", "action_link"}.issubset(categories):
            score += 0.12
            reasons.append("OTP instructions combined with a link are strongly inconsistent with normal policy.")
            flags.append("OTP_LINK_POLICY_CONFLICT")
        if {"credential_request", "action_link"}.issubset(categories):
            score += 0.12
            reasons.append("Credential collection combined with a link is highly policy-conflicting.")
            flags.append("CREDENTIAL_LINK_POLICY_CONFLICT")
        if {"urgency", "threat", "action_link"}.issubset(categories):
            score += 0.10
            reasons.append("Threat, urgency, and link pressure appear together.")
            flags.append("THREAT_URGENCY_ACTION")

        sector = str(claimed_entity.get("sector", "")).strip().lower()
        if sector in {"bank", "payment", "wallet", "government"} and ({"otp_request", "credential_request", "action_link", "payment_request"} & categories):
            score += 0.08
            reasons.append(f"The claimed sector ({sector}) is sensitive, so this request is more policy-conflicting.")
            flags.append("SENSITIVE_SECTOR_POLICY")

        model_score = float(heuristic_result.get("risk_score", 0.5) or 0.5)
        if model_score >= 0.72:
            score = max(score, (0.76 * score) + (0.24 * model_score))
        elif model_score <= 0.32 and score < 0.45:
            score = min(score, (0.85 * score) + (0.15 * model_score))

        return max(0.0, min(1.0, score)), flags, reasons

    def _infer_sector_from_text(self, normalized_text: str) -> Optional[str]:
        for sector, hints in self.sector_hints.items():
            for hint in hints:
                if self._normalize_text(hint) in normalized_text:
                    return sector
        if re.search(r"\b(bank|wallet|payment|بطاقه|بطاقة|بنك|محفظه|محفظة|دفع|سداد)\b", normalized_text, re.IGNORECASE):
            return "bank"
        if re.search(r"\b(government|ministry|وزاره|وزارة|حكومه|حكومة)\b", normalized_text, re.IGNORECASE):
            return "government"
        if re.search(r"\b(university|college|جامعه|جامعة|بوابة الجامعة)\b", normalized_text, re.IGNORECASE):
            return "education"
        return None

    def _status_from_score(self, score: float) -> str:
        compliant_max = float(self._cfg("compliant_max", 0.32))
        conflicting_min = float(self._cfg("conflicting_min", 0.70))
        if score >= conflicting_min:
            return "conflicting"
        if score <= compliant_max:
            return "compliant"
        return "unknown"

    def _load_rules(self) -> Dict[str, Any]:
        if not self.rules_path.exists():
            return {}
        try:
            with self.rules_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_config(self) -> Dict[str, Any]:
        config = dict(self.DEFAULT_CONFIG)
        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    config.update(data)
            except Exception:
                pass
        return config

    def _cfg(self, key: str, default: Any) -> Any:
        return self.config.get(key, default)

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_text(self, text: str) -> str:
        return normalize_loose_text(text)

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result
