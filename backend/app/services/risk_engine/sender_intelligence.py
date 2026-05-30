"""
APG Risk Intelligence Engine v1 — Sender Intelligence

Wraps the v5 SenderTrustAnalyzer and converts its Signal output into the
risk engine's structured Evidence and SenderAssessment types.

Design rules (from the spec):
  - Known contact lowers risk ONLY for casual/non-sensitive messages.
  - Known contact NEVER neutralizes OTP / password / card / CVV / PIN requests.
  - Bank-like sender name is weak evidence only (spoofing exists).
  - Unknown sender slightly raises score for vague financial/account notices.
"""
from __future__ import annotations

from app.services.analyzer.schemas import EntityResult, IntentResult
from app.services.analyzer.sender_trust import SenderTrustAnalyzer as _SenderTrustAnalyzer
from .schemas import Evidence, SenderAssessment


def _signal_to_evidence(signal) -> Evidence:
    """Convert a v5 sender Signal to a risk-engine Evidence item."""
    if signal.type == "suspicious":
        category = "suspicious_context"
        severity = "medium" if signal.weight >= 30 else "low"
    elif signal.type == "danger":
        category = "dangerous_intent"
        severity = "high"
    else:
        category = "sender"
        severity = "info"

    return Evidence(
        id=signal.name,
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        score_delta=signal.weight,
        confidence=0.75,
        matched_text=signal.evidence or "",
        explanation_ar=signal.explanation_ar,
    )


def _derive_trust_level(entities: EntityResult) -> str:
    trust = (entities.sender_trust or "unknown").strip().lower()
    if entities.is_known_contact is True or trust in {"known", "trusted_contact", "trusted", "contact"}:
        return "known"
    if entities.is_known_contact is False or trust in {"unknown", "stranger", "unknown_contact"}:
        return "unknown"
    return trust


class SenderIntelligenceAnalyzer:
    def __init__(self) -> None:
        self._inner = _SenderTrustAnalyzer()

    def assess(
        self,
        entities: EntityResult,
        intents: IntentResult,
        modality: str = "text_with_url",
    ) -> SenderAssessment:
        """Produce a SenderAssessment from entity/intent context."""
        trust_level = _derive_trust_level(entities)

        # For url_only with no explicit sender: skip all sender penalty signals.
        # The absence of a sender is expected (user pasted a bare URL), not evidence
        # of suspicious behaviour.
        if modality == "url_only" and not entities.sender:
            return SenderAssessment(
                sender="",
                sender_name="",
                source=entities.source or "manual",
                source_app=entities.source_app or "",
                package_name=entities.package_name or "",
                is_known_contact=entities.is_known_contact,
                trust_level=trust_level,
                evidence=[],
            )

        signals = self._inner.evaluate(entities, intents)
        evidence = [_signal_to_evidence(s) for s in signals]

        return SenderAssessment(
            sender=entities.sender or "",
            sender_name=entities.sender_name or "",
            source=entities.source or "manual",
            source_app=entities.source_app or "",
            package_name=entities.package_name or "",
            is_known_contact=entities.is_known_contact,
            trust_level=trust_level,
            evidence=evidence,
        )
