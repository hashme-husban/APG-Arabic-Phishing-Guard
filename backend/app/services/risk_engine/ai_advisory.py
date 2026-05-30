"""
APG Risk Intelligence Engine v1 — AI Advisory

Wraps the v5 AIAdapter (AraBERT semantic model + lexical model) and converts
its scores into a structured AIAssessment used by the policy engine.

Critical design constraints:
  - AI is ADVISORY only; it cannot override a definite block.
  - AI cannot turn a clear awareness / OTP-delivery / bank-transaction message
    into a dangerous result.
  - If both models are missing/unavailable, the engine still works via rules.
  - Confidence of AI-driven verdicts is lower than rule-driven ones.
"""
from __future__ import annotations

from app.services.analyzer.ai_adapter import AIAdapter as _AIAdapter
from .schemas import AIAssessment, Evidence


def _advisory_verdict(max_scaled: int) -> str:
    if max_scaled <= 0:
        return "unavailable"
    if max_scaled >= 75:
        return "high"
    if max_scaled >= 55:
        return "medium"
    return "low"


class AIAdvisoryAnalyzer:
    def __init__(self) -> None:
        self._inner = _AIAdapter()

    def assess(self, normalized_text: str) -> AIAssessment:
        models = self._inner.score(normalized_text or "")

        semantic_loaded = self._inner.semantic.loaded
        lexical_loaded = self._inner.lexical.loaded

        sem_scaled = int(round(models.semantic_score * 100)) if semantic_loaded else 0
        lex_scaled = int(round(models.lexical_score * 100)) if lexical_loaded else 0
        max_scaled = max(sem_scaled, lex_scaled)

        advisory = _advisory_verdict(max_scaled)

        evidence: list[Evidence] = []

        if semantic_loaded and sem_scaled >= 65:
            evidence.append(Evidence(
                id="ai_semantic_high",
                category="ai",
                severity="medium" if sem_scaled < 80 else "high",
                score_delta=min(sem_scaled, 55),
                confidence=round(models.semantic_score, 4),
                matched_text="",
                explanation_ar=(
                    "نموذج الذكاء الاصطناعي (AraBERT) رأى مؤشرات إضافية. "
                    "هذا الحكم استشاري فقط ويُستخدم لدعم الحالات غير الواضحة."
                ),
                explanation_en="AraBERT semantic model detected elevated risk — advisory only.",
            ))

        if lexical_loaded and lex_scaled >= 65:
            evidence.append(Evidence(
                id="ai_lexical_high",
                category="ai",
                severity="medium" if lex_scaled < 80 else "high",
                score_delta=min(lex_scaled, 55),
                confidence=round(models.lexical_score, 4),
                matched_text="",
                explanation_ar=(
                    "النموذج المعجمي رأى نمطاً يستوجب الحذر. "
                    "هذا الحكم استشاري فقط ويُستخدم لدعم الحالات غير الواضحة."
                ),
                explanation_en="Lexical model flagged suspicious pattern — advisory only.",
            ))

        return AIAssessment(
            semantic_score=models.semantic_score,
            lexical_score=models.lexical_score,
            semantic_loaded=semantic_loaded,
            lexical_loaded=lexical_loaded,
            advisory_verdict=advisory,
            evidence=evidence,
        )

    @property
    def semantic_model_status(self) -> dict:
        return {
            "loaded": self._inner.semantic.loaded,
            "path": str(self._inner.semantic.path),
            "error": self._inner.semantic.error,
        }

    @property
    def lexical_model_status(self) -> dict:
        return {
            "loaded": self._inner.lexical.loaded,
            "path": str(self._inner.lexical.bundle_path),
            "error": self._inner.lexical.error,
        }
