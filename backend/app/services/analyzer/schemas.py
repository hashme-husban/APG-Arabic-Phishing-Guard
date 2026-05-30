from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Classification = str


@dataclass(frozen=True)
class Signal:
    name: str
    type: str
    weight: int
    explanation_ar: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "weight": self.weight,
            "explanation_ar": self.explanation_ar,
            "evidence": self.evidence,
            "category": self.type,
            "impact": "high" if self.weight >= 80 else "medium" if self.weight >= 40 else "low",
        }


@dataclass
class EntityResult:
    entities: set[str] = field(default_factory=set)
    urls: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    link_reference: bool = False
    source: str = "manual"
    sender: str = ""
    sender_name: str = ""
    source_app: str = ""
    package_name: str = ""
    is_known_contact: bool | None = None
    sender_trust: str = "unknown"

    @property
    def has_url(self) -> bool:
        return bool(self.urls)

    @property
    def has_link_surface(self) -> bool:
        return self.has_url or self.link_reference

    @property
    def has_sensitive_entity(self) -> bool:
        return bool(self.entities & {"otp", "password", "pin", "card", "cvv", "iban"})

    @property
    def has_bank_or_account(self) -> bool:
        return bool(self.entities & {"bank", "account", "card", "money_transaction", "iban"})


@dataclass
class IntentResult:
    intents: set[str] = field(default_factory=set)
    dangerous_text_request: bool = False
    credential_request: bool = False
    card_data_request: bool = False
    otp_request: bool = False
    password_request: bool = False
    url_account_action: bool = False
    threat_urgency: bool = False
    awareness: bool = False
    safe_context: str | None = None
    evidence: dict[str, str] = field(default_factory=dict)

    def has(self, name: str) -> bool:
        return name in self.intents


@dataclass
class ModelScores:
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    semantic_scaled: int = 0
    lexical_scaled: int = 0
    semantic_details: dict[str, Any] = field(default_factory=dict)
    lexical_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderVerdict:
    provider: str
    status: str
    verdict: str = "unknown"
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class URLFinding:
    url: str
    normalized_url: str
    domain: str
    final_url: str | None = None
    local_signals: list[Signal] = field(default_factory=list)
    provider_verdicts: list[ProviderVerdict] = field(default_factory=list)
    verdict: str = "unknown"
    score: int = 0


@dataclass
class URLReputationResult:
    findings: list[URLFinding] = field(default_factory=list)
    enabled: bool = True
    cache_status: str = "empty"

    @property
    def verdict(self) -> str:
        order = {"malicious": 3, "suspicious": 2, "clean": 1, "unknown": 0}
        return max((f.verdict for f in self.findings), key=lambda v: order.get(v, 0), default="unknown")

    @property
    def max_score(self) -> int:
        return max((f.score for f in self.findings), default=0)

    @property
    def signals(self) -> list[Signal]:
        output: list[Signal] = []
        for finding in self.findings:
            output.extend(finding.local_signals)
            if finding.verdict == "malicious":
                output.append(Signal("malicious_url_reputation", "danger", 98, "سمعة الرابط تشير إلى تصيّد أو برمجيات خبيثة.", finding.domain))
            elif finding.verdict == "suspicious":
                output.append(Signal("suspicious_url_reputation", "suspicious", 68, "سمعة الرابط أو خصائصه تحتاج حذرا إضافيا.", finding.domain))
            elif finding.verdict == "clean":
                output.append(Signal("clean_url_reputation", "context", -4, "لم ترصد مزودات السمعة مؤشرا خبيثا معروفا للرابط، وهذا لا يثبت الأمان بشكل كامل.", finding.domain))
        return output


@dataclass
class RuleResult:
    intents: IntentResult
    signals: list[Signal] = field(default_factory=list)

    @property
    def definite_danger(self) -> bool:
        return any(s.type == "danger" and s.weight >= 85 for s in self.signals)

    def has_signal(self, *names: str) -> bool:
        wanted = set(names)
        return any(s.name in wanted for s in self.signals)

    def max_weight(self, signal_type: str | None = None) -> int:
        return max((s.weight for s in self.signals if signal_type is None or s.type == signal_type), default=0)


@dataclass
class HybridResult:
    risk_score: int
    classification: Classification
    masked_text: str
    detected_url: str | None
    reasons: list[str]
    matched_signals: list[dict[str, Any]]
    recommendation: str
    debug: dict[str, Any]
    confidence: float = 0.0
    verdict: str = ""
    message_category: str = ""
