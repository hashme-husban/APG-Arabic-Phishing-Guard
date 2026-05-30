from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from .ai_adapter import AIAdapter
from .entities import EntityExtractor
from .explanations import reasons_for, recommendation_for
from .normalizer import ArabicNormalizer, dedupe
from .resolver import RiskResolver
from .rule_engine import RuleEngine
from .schemas import HybridResult
from .url_reputation import URLReputationService

logger = logging.getLogger("apg.analyzer")

APG_ANALYZER_VERSION = "APG-Hybrid-Analyzer v5.0 URL-Reputation + Intent Fusion"
CRITICAL_RULES_ENABLED = True


class HybridAnalyzerV5:
    def __init__(self) -> None:
        self.normalizer = ArabicNormalizer()
        self.entities = EntityExtractor()
        self.url_reputation = URLReputationService()
        self.rules = RuleEngine()
        self.ai = AIAdapter()
        self.resolver = RiskResolver()

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
        raw_text = text or ""
        normalized = self.normalizer.normalize(raw_text)
        entities, entity_signals = self.entities.extract(
            raw_text,
            normalized,
            source=source,
            sender=sender,
            sender_name=sender_name,
            package_name=package_name,
            source_app=source_app,
            extra_urls=extra_urls,
            is_known_contact=is_known_contact,
            sender_trust=sender_trust,
        )
        url_result = self.url_reputation.check_urls(entities.urls, mock_verdicts=mock_url_reputation)
        rules = self.rules.evaluate(normalized, entities, entity_signals, url_result)
        models = self.ai.score(normalized or raw_text)
        risk_score, classification = self.resolver.resolve(rules, models, entities, url_result)
        reasons = reasons_for(classification, rules)
        reasons = dedupe(reasons + self._model_reasons(models, rules))[:8]

        debug = {
            "semantic_score": round(models.semantic_score, 6) if self.ai.semantic.loaded else None,
            "lexical_score": round(models.lexical_score, 6) if self.ai.lexical.loaded else None,
            "rule_score": rules.max_weight(),
            "url_score": url_result.max_score,
            "sender_score": max((s.weight for s in rules.signals if "sender" in s.name), default=0),
            "critical_floor": 85 if rules.definite_danger else 0,
            "model_loaded": {"semantic": self.ai.semantic.loaded, "lexical": self.ai.lexical.loaded},
            "semantic_details": models.semantic_details,
            "lexical_details": models.lexical_details,
            "analyzer_version": APG_ANALYZER_VERSION,
            "normalized_text": normalized,
            "domains": entities.domains,
            "phone_numbers_detected": len(entities.phones),
            "entities": sorted(entities.entities),
            "intents": sorted(rules.intents.intents),
            "safe_context": rules.intents.safe_context,
            "is_known_contact": entities.is_known_contact,
            "sender_trust": entities.sender_trust,
            "url_reputation": {
                "enabled": url_result.enabled,
                "verdict": url_result.verdict,
                "findings": [
                    {
                        "domain": f.domain,
                        "verdict": f.verdict,
                        "score": f.score,
                        "providers": [p.__dict__ for p in f.provider_verdicts],
                        "local_signals": [s.to_dict() for s in f.local_signals],
                    }
                    for f in url_result.findings
                ],
            },
        }
        return HybridResult(
            risk_score=int(max(0, min(100, risk_score))),
            classification=classification,
            masked_text="",
            detected_url=entities.urls[0] if entities.urls else None,
            reasons=reasons,
            matched_signals=[signal.to_dict() for signal in rules.signals[:24]],
            recommendation=recommendation_for(classification),
            debug=debug,
        )

    def status(self) -> dict[str, Any]:
        return {
            "analyzer_version": APG_ANALYZER_VERSION,
            "semantic_model_path": str(self.ai.semantic.path),
            "semantic_model_loaded": self.ai.semantic.loaded,
            "semantic_model_error": self.ai.semantic.error,
            "lexical_model_path": str(self.ai.lexical.bundle_path),
            "lexical_model_loaded": self.ai.lexical.loaded,
            "lexical_model_error": self.ai.lexical.error,
            "critical_rules_enabled": CRITICAL_RULES_ENABLED,
            **self.url_reputation.status(),
        }

    def check_url(self, url: str, mock_url_reputation: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.url_reputation.check_urls([url], mock_verdicts=mock_url_reputation)
        finding = result.findings[0] if result.findings else None
        return {
            "analyzer_version": APG_ANALYZER_VERSION,
            "url_reputation_enabled": result.enabled,
            "cache_status": result.cache_status,
            "verdict": result.verdict,
            "finding": None if finding is None else {
                "url": finding.url,
                "normalized_url": finding.normalized_url,
                "domain": finding.domain,
                "final_url": finding.final_url,
                "verdict": finding.verdict,
                "score": finding.score,
                "local_signals": [s.to_dict() for s in finding.local_signals],
                "provider_verdicts": [p.__dict__ for p in finding.provider_verdicts],
            },
        }

    def _model_reasons(self, models, rules) -> list[str]:
        if rules.intents.safe_context or rules.definite_danger:
            return []
        reasons: list[str] = []
        if self.ai.semantic.loaded and models.semantic_scaled >= 70:
            reasons.append("نموذج الذكاء الاصطناعي رأى مؤشرات إضافية، واستخدم فقط لدعم الحالات غير الواضحة.")
        if self.ai.lexical.loaded and models.lexical_scaled >= 70:
            reasons.append("النموذج اللغوي رأى نمطا يحتاج حذرا، واستخدم فقط لدعم الحالات غير الواضحة.")
        return reasons


@lru_cache(maxsize=1)
def get_analyzer_service() -> HybridAnalyzerV5:
    analyzer = HybridAnalyzerV5()
    status = analyzer.status()
    logger.info("APG_ANALYZER_VERSION %s", APG_ANALYZER_VERSION)
    logger.info("APG_SEMANTIC_MODEL_PATH %s", status["semantic_model_path"])
    logger.info("APG_SEMANTIC_MODEL_LOADED %s", str(status["semantic_model_loaded"]).lower())
    logger.info("APG_LEXICAL_MODEL_PATH %s", status["lexical_model_path"])
    logger.info("APG_LEXICAL_MODEL_LOADED %s", str(status["lexical_model_loaded"]).lower())
    logger.info("APG_URL_REPUTATION_ENABLED %s", str(status["url_reputation_enabled"]).lower())
    logger.info("APG_ANALYZER_READY")
    return analyzer
