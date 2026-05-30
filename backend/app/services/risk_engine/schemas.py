"""
APG Risk Intelligence Engine v1 — Internal Data Model

All types used internally by the engine.  The compatibility module maps these
to the backward-compatible HybridResult before returning to callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# ─── Primitive type aliases ────────────────────────────────────────────────────

Verdict = Literal["allow", "caution", "warn", "block"]
RiskLevel = Literal["minimal", "low", "medium", "high", "critical"]
MessageCategory = Literal[
    "casual",
    "transactional",
    "bank_transaction",
    "payment_receipt",
    "promotional",
    "service_notification",
    "subscription_notice",
    "survey",
    "government_notice",
    "awareness",
    "otp_delivery",
    "app_verification",
    "account_notice",
    "credential_request",
    "link_action",
    "brand_impersonation",
    "phishing",
    "unknown",
]
AttackType = Literal[
    "none",
    "otp_theft",
    "password_theft",
    "card_theft",
    "bank_account_takeover",
    "malicious_url",
    "brand_impersonation",
    "social_engineering",
    "credential_harvesting",
    "unknown",
]
UserAction = Literal[
    "no_action_needed",
    "do_not_share_code",
    "do_not_click_link",
    "verify_from_official_app",
    "contact_bank_directly",
    "report_message",
]
EvidenceCategory = Literal[
    "safe_context",
    "suspicious_context",
    "dangerous_intent",
    "entity",
    "url",
    "sender",
    "ai",
    "privacy",
]
EvidenceSeverity = Literal["info", "low", "medium", "high", "critical"]


# ─── Evidence ────────────────────────────────────────────────────────────────

@dataclass
class Evidence:
    """
    Single piece of structured evidence produced by a detector.

    score_delta: positive = raises risk, negative = lowers risk.
    confidence:  0.0-1.0 — how certain this evidence item is.
    matched_text: excerpt that triggered this evidence (may be empty).
    extra: optional provider-specific fields merged into matched_signals
           output (e.g. VirusTotal stats).  Defaults to empty dict.
    """
    id: str
    category: EvidenceCategory
    severity: EvidenceSeverity
    score_delta: int
    confidence: float
    matched_text: str
    explanation_ar: str
    explanation_en: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "score_delta": self.score_delta,
            "confidence": round(self.confidence, 4),
            "matched_text": self.matched_text,
            "explanation_ar": self.explanation_ar,
            "explanation_en": self.explanation_en,
        }


# ─── URL Intelligence ────────────────────────────────────────────────────────

@dataclass
class URLIntelligence:
    extracted_urls: list[str] = field(default_factory=list)
    primary_url: str | None = None
    primary_domain: str | None = None
    has_url: bool = False
    has_link_reference: bool = False
    verdict: str = "unknown"        # clean | suspicious | malicious | unknown
    provider_verdicts: list[dict[str, Any]] = field(default_factory=list)
    local_evidence: list[Evidence] = field(default_factory=list)
    shortener_detected: bool = False
    ip_url_detected: bool = False
    punycode_detected: bool = False
    suspicious_tld: bool = False
    brand_impersonation: bool = False
    privacy_notes: list[str] = field(default_factory=list)

    @property
    def has_link_surface(self) -> bool:
        return self.has_url or self.has_link_reference

    @property
    def max_local_score(self) -> int:
        return max(
            (e.score_delta for e in self.local_evidence if e.score_delta > 0),
            default=0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "extracted_urls": self.extracted_urls,
            "primary_url": self.primary_url,
            "primary_domain": self.primary_domain,
            "has_url": self.has_url,
            "has_link_reference": self.has_link_reference,
            "verdict": self.verdict,
            "provider_verdicts": self.provider_verdicts,
            "local_evidence": [e.to_dict() for e in self.local_evidence],
            "shortener_detected": self.shortener_detected,
            "ip_url_detected": self.ip_url_detected,
            "punycode_detected": self.punycode_detected,
            "suspicious_tld": self.suspicious_tld,
            "brand_impersonation": self.brand_impersonation,
            "privacy_notes": self.privacy_notes,
        }


# ─── Sender Assessment ───────────────────────────────────────────────────────

@dataclass
class SenderAssessment:
    sender: str = ""
    sender_name: str = ""
    source: str = "manual"
    source_app: str = ""
    package_name: str = ""
    is_known_contact: bool | None = None
    trust_level: str = "unknown"    # trusted | known | unknown | suspicious
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "sender_name": self.sender_name,
            "source": self.source,
            "source_app": self.source_app,
            "package_name": self.package_name,
            "is_known_contact": self.is_known_contact,
            "trust_level": self.trust_level,
            "evidence": [e.to_dict() for e in self.evidence],
        }


# ─── AI Assessment ───────────────────────────────────────────────────────────

@dataclass
class AIAssessment:
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    semantic_loaded: bool = False
    lexical_loaded: bool = False
    advisory_verdict: str = "unavailable"   # high | medium | low | unavailable
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def max_scaled(self) -> int:
        return max(
            int(round(self.semantic_score * 100)) if self.semantic_loaded else 0,
            int(round(self.lexical_score * 100)) if self.lexical_loaded else 0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_score": round(self.semantic_score, 6) if self.semantic_loaded else None,
            "lexical_score": round(self.lexical_score, 6) if self.lexical_loaded else None,
            "semantic_loaded": self.semantic_loaded,
            "lexical_loaded": self.lexical_loaded,
            "advisory_verdict": self.advisory_verdict,
            "evidence": [e.to_dict() for e in self.evidence],
        }


# ─── Score Breakdown ─────────────────────────────────────────────────────────

@dataclass
class ScoreSignal:
    id: str
    name_ar: str
    layer: str
    severity: str
    delta: int
    confidence: float
    explanation_ar: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name_ar": self.name_ar,
            "layer": self.layer,
            "severity": self.severity,
            "delta": self.delta,
            "confidence": round(self.confidence, 4),
            "explanation_ar": self.explanation_ar,
        }


@dataclass
class ScoreFloorOrCap:
    id: str
    from_score: int
    to_score: int
    reason_ar: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_score": self.from_score,
            "to_score": self.to_score,
            "reason_ar": self.reason_ar,
        }


@dataclass
class ScoreAdjustment:
    id: str
    delta: int
    reason_ar: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "delta": self.delta,
            "reason_ar": self.reason_ar,
        }


@dataclass
class ScoreBreakdown:
    base_score: int
    positive_signals: list[ScoreSignal]
    negative_signals: list[ScoreSignal]
    floors_applied: list[ScoreFloorOrCap]
    caps_applied: list[ScoreFloorOrCap]
    adjustments: list[ScoreAdjustment]
    raw_score_before_caps: int
    final_score: int
    verdict: str
    decision_summary_ar: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_score": self.base_score,
            "positive_signals": [s.to_dict() for s in self.positive_signals],
            "negative_signals": [s.to_dict() for s in self.negative_signals],
            "floors_applied": [f.to_dict() for f in self.floors_applied],
            "caps_applied": [c.to_dict() for c in self.caps_applied],
            "adjustments": [a.to_dict() for a in self.adjustments],
            "raw_score_before_caps": self.raw_score_before_caps,
            "final_score": self.final_score,
            "verdict": self.verdict,
            "decision_summary_ar": self.decision_summary_ar,
        }


# ─── Policy Decision (internal) ──────────────────────────────────────────────

@dataclass
class PolicyDecision:
    verdict: Verdict
    risk_score: int
    attack_type: AttackType
    user_action: UserAction
    confidence: float
    applied_cap: int | None
    policy_trace: list[str] = field(default_factory=list)
    block_rule_triggered: str | None = None
    cap_reason_ar: str | None = None  # Arabic reason when an intent-based cap was applied
    score_breakdown: "ScoreBreakdown | None" = None


# ─── Final Risk Result ────────────────────────────────────────────────────────

@dataclass
class RiskResult:
    # Core verdict
    verdict: Verdict
    risk_level: RiskLevel
    risk_score: int
    confidence: float

    # Message analysis
    message_category: MessageCategory
    attack_type: AttackType
    user_action: UserAction

    # Explanations
    primary_reason_ar: str
    primary_reason_en: str | None

    # Evidence
    evidence: list[Evidence]

    # Sub-analyses
    url_intelligence: URLIntelligence
    sender_assessment: SenderAssessment
    ai_assessment: AIAssessment

    # Audit
    policy_trace: list[str]
    privacy_notes: list[str]

    # Raw data
    normalized_text: str
    original_text: str
    extracted_entities: set[str]
    detected_actions: list[str]
    analyzer_version: str
    applied_cap: int | None = None
    modality: str = "text_with_url"  # text_only | url_only | text_with_url | empty
    message_intent: str = "unknown"
    intent_confidence: float = 0.0
    entity_intelligence: dict[str, Any] | None = None  # populated by ClaimedEntityExtractor
    behavioral_analysis: dict[str, Any] | None = None  # populated by BehavioralDetector
    # Type: DynamicURLAnalysisResult | None — Any avoids circular import with dynamic_url_analysis.py
    # Shadow mode (Phase 2B): populated when DYNAMIC_URL_ANALYSIS_ENABLED=true.
    # Never affects public HybridResult; only surfaced in admin explain endpoint.
    dynamic_url_analysis_result: Any = None
    score_breakdown: "ScoreBreakdown | None" = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "confidence": round(self.confidence, 4),
            "message_category": self.message_category,
            "attack_type": self.attack_type,
            "user_action": self.user_action,
            "primary_reason_ar": self.primary_reason_ar,
            "primary_reason_en": self.primary_reason_en,
            "evidence": [e.to_dict() for e in self.evidence],
            "url_intelligence": self.url_intelligence.to_dict(),
            "sender_assessment": self.sender_assessment.to_dict(),
            "ai_assessment": self.ai_assessment.to_dict(),
            "policy_trace": self.policy_trace,
            "privacy_notes": self.privacy_notes,
            "normalized_text": self.normalized_text,
            "original_text": self.original_text,
            "extracted_entities": sorted(self.extracted_entities),
            "detected_actions": self.detected_actions,
            "analyzer_version": self.analyzer_version,
            "applied_cap": self.applied_cap,
            "modality": self.modality,
            "message_intent": self.message_intent,
            "intent_confidence": round(self.intent_confidence, 4),
            "entity_intelligence": self.entity_intelligence,
            "behavioral_analysis": self.behavioral_analysis,
            "dynamic_url_analysis": (
                self.dynamic_url_analysis_result.to_dict()
                if self.dynamic_url_analysis_result is not None
                else None
            ),
            "score_breakdown": (
                self.score_breakdown.to_dict()
                if self.score_breakdown is not None
                else None
            ),
        }
