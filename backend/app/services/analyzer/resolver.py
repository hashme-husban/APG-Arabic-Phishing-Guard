from __future__ import annotations

from .schemas import EntityResult, ModelScores, RuleResult, URLReputationResult


class RiskResolver:
    def resolve(self, rules: RuleResult, models: ModelScores, entities: EntityResult, url_result: URLReputationResult) -> tuple[int, str]:
        intents = rules.intents
        danger_weight = rules.max_weight("danger")
        suspicious_weight = rules.max_weight("suspicious")
        clean_url_adjustment = -5 if url_result.verdict == "clean" else 0

        if url_result.verdict == "malicious":
            return 98, "dangerous"
        if intents.credential_request and entities.has_link_surface:
            return max(92, danger_weight), "dangerous"
        if intents.card_data_request or intents.password_request:
            return max(92, danger_weight), "dangerous"
        if intents.otp_request:
            return max(88, danger_weight), "dangerous"
        if entities.has_link_surface and intents.has("account_update") and intents.threat_urgency:
            return max(95 if url_result.verdict == "suspicious" else 90, danger_weight), "dangerous"
        if rules.has_signal("threat_url_account"):
            return max(90, danger_weight), "dangerous"
        if rules.has_signal("url_account_update"):
            return max(86, danger_weight), "dangerous"
        if rules.has_signal("threat_login_account"):
            return max(78, danger_weight), "dangerous"

        cap = self._safe_cap(rules, entities)
        if cap is not None:
            model_weight = 0
        else:
            model_weight = self._model_weight(models, rules)

        score = max(10 if not rules.signals else 18, suspicious_weight, model_weight)
        if url_result.verdict == "unknown" and entities.has_link_surface and (intents.has("account_update") or entities.has_bank_or_account):
            score = max(score, 55)
        if suspicious_weight >= 55:
            score = max(score, 55)
        if rules.has_signal("unknown_sender_financial_context"):
            score += 6
        if rules.has_signal("known_contact_sender") and not entities.has_sensitive_entity and suspicious_weight < 55:
            score -= 8
        score += clean_url_adjustment

        if cap is not None:
            score = min(score, cap)
        elif suspicious_weight:
            score = min(score, 70)

        score = max(0, min(100, int(round(score))))
        if score >= 76:
            return score, "dangerous"
        if score >= 31:
            return score, "suspicious"
        return score, "safe"

    @staticmethod
    def _model_weight(models: ModelScores, rules: RuleResult) -> int:
        model_score = max(models.semantic_scaled, models.lexical_scaled)
        if model_score < 65 or rules.intents.safe_context or rules.definite_danger:
            return 0
        if rules.max_weight("suspicious") >= 40:
            return min(model_score, 68)
        return min(model_score, 55)

    @staticmethod
    def _safe_cap(rules: RuleResult, entities: EntityResult) -> int | None:
        intents = rules.intents
        if rules.definite_danger:
            return None
        if rules.has_signal("security_awareness_message") and not entities.has_link_surface:
            return 20
        if rules.has_signal("otp_informational_do_not_share") and not entities.has_link_surface:
            return 25
        if rules.has_signal("benign_bank_transaction") and not entities.has_link_surface:
            return 25
        if rules.has_signal("whatsapp_verification_status") and not entities.has_link_surface:
            return 15
        if intents.has("casual") and (entities.is_known_contact is True or entities.sender_trust in {"known", "trusted_contact"}):
            return 10
        return None
