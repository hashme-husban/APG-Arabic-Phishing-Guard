"""
APG Risk Intelligence Engine v1 — Service Orchestrator

This is the main entry point for the new risk engine.  It wires all
sub-components together and exposes the same public interface as the v5
HybridAnalyzerV5 so that hybrid_analyzer.py can swap between engines.

Public interface (mirrors HybridAnalyzerV5):
  analyze(text, ...) -> HybridResult          (backward compatible)
  analyze_full(text, ...) -> RiskResult        (new rich result)
  status() -> dict
  check_url(url, ...) -> dict

All existing callers that receive a HybridResult will continue to work.
The new /api/admin/analyzer/explain endpoint calls analyze_full() directly.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.services.analyzer.schemas import HybridResult

from .action_detector import ActionDetectorAdapter
from .ai_advisory import AIAdvisoryAnalyzer
from .compatibility import to_hybrid_result
from .entity_extractor import ClaimedEntityExtractor, EntityExtractorAdapter
from .behavioral_detector import detect_behavioral_phishing
from .entity_policy import evaluate_entity_policy
from .evidence_builder import build_all_evidence
from .explanation_builder import build_primary_reason
from .intent_detector import detect_message_intent
from .message_classifier import classify_message
from .modality import detect_modality
from .normalizer import Normalizer
from .dynamic_url_analysis import (
    DynamicURLAnalysisResult,
    analyze_url_dynamically,
    dynamic_result_to_evidence,
)
from .policy_engine import PolicyEngine
from .schemas import RiskResult
from .sender_intelligence import SenderIntelligenceAnalyzer
from .url_intelligence import URLIntelligenceAnalyzer, _is_trusted_domain as _check_trusted_domain
from .url_providers import get_provider_status

# Feature flag — always False unless DYNAMIC_URL_ANALYSIS_ENABLED=true in env.
# Evaluated once at import time; changing the env var requires a process restart.
# Phase 2B shadow mode: flag must be explicitly set; zero behaviour change by default.
_DYNAMIC_URL_ANALYSIS_ENABLED: bool = False
_DYNAMIC_URL_TIMEOUT: int = 10          # safe defaults always set before try block
_DYNAMIC_URL_OBSERVATION_MS: int = 1500
_DYNAMIC_URL_TIME_SIMULATION_ENABLED: bool = False
_DYNAMIC_URL_SIMULATED_MINUTES: int = 0
# Phase 3: conservative sandbox scoring — disabled by default, independent of sandbox flag.
_DYNAMIC_URL_SCORE_ENABLED: bool = False
try:
    import os as _os
    _DYNAMIC_URL_ANALYSIS_ENABLED = (
        _os.getenv("DYNAMIC_URL_ANALYSIS_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    _raw_timeout = int(_os.getenv("DYNAMIC_URL_ANALYSIS_TIMEOUT_SECONDS", "10"))
    _DYNAMIC_URL_TIMEOUT = max(1, min(_raw_timeout, 20))   # clamped 1-20 s
    _raw_obs = int(_os.getenv("DYNAMIC_URL_ANALYSIS_OBSERVATION_MS", "1500"))
    _DYNAMIC_URL_OBSERVATION_MS = max(0, min(_raw_obs, 5000))  # clamped 0-5000 ms
    _DYNAMIC_URL_TIME_SIMULATION_ENABLED = (
        _os.getenv("DYNAMIC_URL_ANALYSIS_TIME_SIMULATION_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    _raw_simmin = int(_os.getenv("DYNAMIC_URL_ANALYSIS_SIMULATED_MINUTES", "0"))
    _DYNAMIC_URL_SIMULATED_MINUTES = max(0, min(_raw_simmin, 60))  # clamped 0-60
    _DYNAMIC_URL_SCORE_ENABLED = (
        _os.getenv("DYNAMIC_URL_ANALYSIS_SCORE_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
except Exception:
    pass  # keep safe defaults set above

logger = logging.getLogger("apg.risk_engine_v1")

APG_RISK_ENGINE_VERSION = "APG-Risk-Intelligence-Engine v1"

# ─── Phase 3: conservative sandbox scoring gate ───────────────────────────────

# Safe message intents where sandbox evidence is suppressed unless there is a
# very strong sensitive-field signal combined with a hard mismatch indicator.
_SCORING_SAFE_INTENTS: frozenset[str] = frozenset({
    "security_advice", "otp_code", "advertisement",
    "transactional", "service_notice", "promotional",
})

# Message categories that indicate account/credential risk context.
_ACCOUNT_RISK_CATEGORIES: frozenset[str] = frozenset({
    "credential_request", "account_notice", "phishing", "brand_impersonation",
})


def _should_score_dynamic_url_evidence(
    dynamic_result: Any,
    url_intel: Any,
    entities: Any,
    intents: Any,
    message_category: str,
    message_intent: str,
    dyn_evidence: list,
) -> tuple[bool, str]:
    """
    Conservative gate: returns (allowed, reason).

    Sandbox evidence is scored only when strong risk combinations are present.
    This function NEVER modifies any argument.
    """
    # ── Preconditions ─────────────────────────────────────────────────────────
    if dynamic_result is None:
        return False, "no_dynamic_result"
    if getattr(dynamic_result, "status", "failed") != "completed":
        return False, "sandbox_not_completed"
    if getattr(dynamic_result, "error", None) is not None:
        return False, "sandbox_error"
    if not dyn_evidence:
        return False, "no_evidence"

    # ── Compute domain change ─────────────────────────────────────────────────
    from urllib.parse import urlparse as _up
    def _r2(h: str) -> str:
        parts = [p for p in h.strip(".").split(".") if p]
        return ".".join(parts[-2:]) if len(parts) >= 2 else h

    _orig = ((_up(dynamic_result.url).hostname or "").lower()) if dynamic_result.url else ""
    _final_url = getattr(dynamic_result, "final_url", None)
    _final = ((_up(_final_url).hostname or "").lower()) if _final_url else ""
    final_domain_changed = bool(
        _final and _orig and _r2(_orig) != _r2(_final) and _r2(_orig)
    )

    # ── Signal shortcuts ──────────────────────────────────────────────────────
    brand_imp       = bool(getattr(url_intel, "brand_impersonation", False))
    url_suspicious  = getattr(url_intel, "verdict", "unknown") in ("suspicious", "malicious")
    has_pass        = bool(getattr(dynamic_result, "has_password_field", False))
    has_otp         = bool(getattr(dynamic_result, "has_otp_field", False))
    has_login       = bool(getattr(dynamic_result, "has_login_form", False))
    delayed_redir   = bool(getattr(dynamic_result, "delayed_url_change", False))
    sensitive_delay = bool(getattr(dynamic_result, "delayed_sensitive_field_appeared", False))
    susp_reqs       = int(getattr(dynamic_result, "suspicious_requests", 0))

    strong_mismatch = final_domain_changed or brand_imp or url_suspicious

    # Account / credential risk context
    has_account_ctx = bool(
        getattr(entities, "has_bank_or_account", False)
        or getattr(intents, "credential_request", False)
        or getattr(intents, "otp_request", False)
        or getattr(intents, "password_request", False)
        or getattr(intents, "card_data_request", False)
        or message_category in _ACCOUNT_RISK_CATEGORIES
    )

    # ── Safe context guard ────────────────────────────────────────────────────
    # For benign intents allow scoring only when a sensitive field co-occurs
    # with a hard mismatch (domain change, brand impersonation, bad reputation).
    if message_intent in _SCORING_SAFE_INTENTS:
        if (has_pass or has_otp) and strong_mismatch:
            return True, "safe_context_sensitive_field_strong_mismatch"
        return False, "safe_context_insufficient_signal"

    # ── Combination 1: password field ─────────────────────────────────────────
    if has_pass:
        if brand_imp or url_suspicious or final_domain_changed or susp_reqs >= 2 or has_account_ctx:
            return True, "password_field_with_risk_signal"

    # ── Combination 2: OTP field ──────────────────────────────────────────────
    if has_otp:
        if (
            getattr(intents, "otp_request", False)
            or has_account_ctx
            or brand_imp
            or final_domain_changed
        ):
            return True, "otp_field_with_risk_signal"

    # ── Combination 4: delayed behaviour + hard mismatch ──────────────────────
    if (delayed_redir or sensitive_delay) and strong_mismatch:
        return True, "delayed_behavior_with_mismatch"

    # ── Combination 5: domain changed + login form + context ──────────────────
    if final_domain_changed and has_login and (brand_imp or has_account_ctx):
        return True, "domain_changed_login_with_context"

    return False, "insufficient_risk_signals"


class RiskEngineV1Service:
    """
    APG Risk Intelligence Engine v1.

    Orchestrates: normalise → extract entities → detect actions → URL
    intelligence → sender assessment → message classification → evidence
    building → AI advisory → policy decision → explanation → compatibility.

    The existing AraBERT and lexical models are used as ADVISORY signals via
    AIAdvisoryAnalyzer.  They cannot override definite block rules.
    """

    def __init__(self) -> None:
        self._normalizer = Normalizer()
        self._entities = EntityExtractorAdapter()
        self._claimed = ClaimedEntityExtractor()
        self._actions = ActionDetectorAdapter()
        self._url = URLIntelligenceAnalyzer()
        self._sender = SenderIntelligenceAnalyzer()
        self._ai = AIAdvisoryAnalyzer()
        self._policy = PolicyEngine()

    # ─── Main analysis ────────────────────────────────────────────────────────

    def analyze_full(
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
    ) -> RiskResult:
        """Full analysis returning the rich internal RiskResult."""
        raw_text = (text or "").strip()
        normalized = self._normalizer.normalize(raw_text)

        # ── 1. Extract entities ───────────────────────────────────────────
        entities, _raw_signals = self._entities.extract(
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

        # ── 1b. Claimed entity intelligence (debug layer, no score impact) ──
        entity_intelligence = self._claimed.extract(
            text=raw_text,
            sender_name=sender_name or sender,
            extra_urls=extra_urls,
        )

        # ── 2. Detect actions + safe context ──────────────────────────────
        intents = self._actions.detect(normalized, entities)

        # ── 3. URL intelligence ───────────────────────────────────────────
        url_intel = self._url.analyze(
            raw_text,
            normalized,
            extra_urls=extra_urls,
            mock_verdicts=mock_url_reputation,
        )

        # ── 3b. Dynamic URL analysis ──────────────────────────────────────
        # Runs only when DYNAMIC_URL_ANALYSIS_ENABLED=true.
        # Flag is False by default — zero behaviour change unless explicitly enabled.
        # Evidence conversion happens later (step 6a) once message_intent is known.
        _dynamic_result: DynamicURLAnalysisResult | None = None
        if _DYNAMIC_URL_ANALYSIS_ENABLED and url_intel.primary_url:
            try:
                _dynamic_result = analyze_url_dynamically(
                    url_intel.primary_url,
                    enabled=_DYNAMIC_URL_ANALYSIS_ENABLED,
                    timeout_seconds=_DYNAMIC_URL_TIMEOUT,
                    observation_ms=_DYNAMIC_URL_OBSERVATION_MS,
                    time_simulation_enabled=_DYNAMIC_URL_TIME_SIMULATION_ENABLED,
                    simulated_minutes=_DYNAMIC_URL_SIMULATED_MINUTES,
                )
            except Exception as _dyn_exc:
                logger.warning("analyze_url_dynamically raised unexpectedly: %s", _dyn_exc)
                _dynamic_result = DynamicURLAnalysisResult(
                    url=url_intel.primary_url,
                    status="failed",
                    error=f"unexpected:{type(_dyn_exc).__name__}",
                )
        elif _DYNAMIC_URL_ANALYSIS_ENABLED and not url_intel.primary_url:
            # Feature is on but no URL was found in the message — emit a stable
            # skipped marker so debug.dynamic_url_analysis reflects the real state.
            _dynamic_result = DynamicURLAnalysisResult(url="", status="skipped", error="no_url")

        # ── 3c. Modality ──────────────────────────────────────────────────
        modality = detect_modality(raw_text, url_intel.extracted_urls)

        # ── 4. Sender assessment ──────────────────────────────────────────
        sender_assessment = self._sender.assess(entities, intents, modality=modality)

        # ── 5. Message classification ─────────────────────────────────────
        message_category = classify_message(entities, intents, url_intel)

        # ── 5b. Message intent (consumer-friendly label) ──────────────────
        message_intent, intent_confidence = detect_message_intent(
            entities, intents, url_intel, message_category, normalized,
        )

        # ── 6. Build evidence ─────────────────────────────────────────────
        ai_assessment = self._ai.assess(normalized or raw_text)
        evidence = build_all_evidence(
            entities, intents, url_intel, sender_assessment, ai_assessment,
            modality=modality,
        )

        # ── 6a. Dynamic URL shadow mode (Phase 2: visibility only) ──────────
        # Sandbox evidence is computed here for debug preview.
        # Phase 3 scoring (step 6a-score) may then selectively add items to
        # the main evidence list when DYNAMIC_URL_ANALYSIS_SCORE_ENABLED=true.
        _dyn_evidence: list = []
        if _dynamic_result is not None:
            from urllib.parse import urlparse as _urlparse
            _primary_host = (
                (_urlparse(url_intel.primary_url).hostname or "").lower()
                if url_intel.primary_url
                else ""
            )
            try:
                _dyn_evidence = dynamic_result_to_evidence(
                    _dynamic_result,
                    url_verdict=url_intel.verdict,
                    message_intent=message_intent,
                    is_trusted_domain=_check_trusted_domain(_primary_host),
                    has_brand_impersonation=url_intel.brand_impersonation,
                )
            except Exception as _dyn_ev_exc:
                logger.warning("dynamic_result_to_evidence failed: %s", _dyn_ev_exc)
                _dyn_evidence = []
            # Shadow mode: serialise for debug preview.
            _dynamic_result.evidence_preview = [e.to_dict() for e in _dyn_evidence]

        # ── 6a-score. Dynamic URL conservative scoring (Phase 3) ───────────────
        # Activated ONLY when DYNAMIC_URL_ANALYSIS_SCORE_ENABLED=true.
        # risk_score and classification are unaffected when the flag is false.
        if _dynamic_result is not None and _DYNAMIC_URL_SCORE_ENABLED:
            _gate_ok, _gate_reason = _should_score_dynamic_url_evidence(
                _dynamic_result, url_intel, entities, intents,
                message_category, message_intent, _dyn_evidence,
            )
            _dynamic_result.scoring_gate = {"allowed": _gate_ok, "reason": _gate_reason}

            if _gate_ok and _dyn_evidence:
                # Select up to 3 items; total sandbox delta capped at 45.
                # Each item is already capped at _MAX_SINGLE_DELTA=28 by
                # dynamic_result_to_evidence() so no per-item cap needed here.
                _selected: list = []
                _total_delta = 0
                for _ev in sorted(_dyn_evidence, key=lambda e: e.score_delta, reverse=True):
                    if len(_selected) >= 3:
                        break
                    if _total_delta + _ev.score_delta > 45:
                        continue
                    _selected.append(_ev)
                    _total_delta += _ev.score_delta
                if _selected:
                    evidence.extend(_selected)
                    _dynamic_result.scored_evidence_summary = {
                        "count": len(_selected),
                        "total_delta": _total_delta,
                        "ids": [e.id for e in _selected],
                    }
                    _dynamic_result.score_impact_override = "conservative_scoring_enabled"
                    logger.info(
                        "apg.dynamic_url: scored %d items, total_delta=%d, gate=%s",
                        len(_selected), _total_delta, _gate_reason,
                    )
                else:
                    _dynamic_result.scored_evidence_summary = {"count": 0, "total_delta": 0, "ids": []}
                    _dynamic_result.score_impact_override = "scoring_enabled_no_evidence"
            else:
                _dynamic_result.scored_evidence_summary = {"count": 0, "total_delta": 0, "ids": []}
                _dynamic_result.score_impact_override = (
                    "scoring_enabled_no_evidence" if not _dyn_evidence
                    else "scoring_blocked_by_gate"
                )

        # ── 6b. Entity policy evaluation ──────────────────────────────────
        # Runs AFTER evidence is built so it can append without re-calling
        # build_all_evidence.  Violations are stored on entity_intelligence
        # for debug output; evidence items are appended to the shared list
        # so the policy engine sees them during Phase 1 / score computation.
        entity_ev, entity_violations = evaluate_entity_policy(
            entity_intelligence,
            intents,
            url_intel,
            message_intent=message_intent,
            normalized_text=normalized,
        )
        if entity_ev:
            evidence.extend(entity_ev)
        entity_intelligence["entity_policy_violations"] = entity_violations

        # ── 6c. Behavioral phishing detection ─────────────────────────────
        behavioral = detect_behavioral_phishing(
            raw_text,
            has_url=url_intel.has_link_surface,
            dangerous_text_request=intents.dangerous_text_request,
            has_credential_request=(
                intents.credential_request
                or intents.password_request
                or intents.otp_request
                or intents.card_data_request
            ),
            has_known_entity=bool(
                entity_intelligence.get("claimed_entity")
                or entity_intelligence.get("alias_entity")
                or url_intel.brand_impersonation
            ),
            has_payment_context=(
                entities.has_bank_or_account
                or intents.has("payment_request")
                or intents.has("ambiguous_financial_notice")
            ),
            safe_context=bool(intents.safe_context or intents.awareness),
        )
        if behavioral["evidence"]:
            evidence.extend(behavioral["evidence"])

        # ── 7. Policy decision ────────────────────────────────────────────
        decision = self._policy.decide(
            entities, intents, url_intel, sender_assessment,
            message_category, evidence, ai_assessment,
            message_intent=message_intent,
        )

        # ── 8. Explanation ────────────────────────────────────────────────
        primary_reason = build_primary_reason(decision, evidence, message_category)

        # ── 9. Risk level ─────────────────────────────────────────────────
        risk_level = PolicyEngine._score_to_risk_level(decision.risk_score)

        # ── 10. Collect privacy notes ─────────────────────────────────────
        privacy_notes: list[str] = []
        privacy_notes.extend(url_intel.privacy_notes)
        if is_known_contact is None:
            privacy_notes.append(
                "لم تُرسل بيانات جهات الاتصال. التحقق من المرسل استند إلى متغير is_known_contact فقط."
            )

        # ── 11. Build detected_actions list (for audit) ───────────────────
        detected_actions: list[str] = []
        if intents.otp_request:
            detected_actions.append("otp_request")
        if intents.password_request:
            detected_actions.append("password_request")
        if intents.card_data_request:
            detected_actions.append("card_data_request")
        if intents.credential_request:
            detected_actions.append("credential_request")
        if intents.threat_urgency:
            detected_actions.append("threat_urgency")
        if intents.awareness:
            detected_actions.append("awareness")
        detected_actions.extend(sorted(intents.intents - {
            "otp_request", "password_request", "card_data_request",
            "credential_request", "threat_urgency", "awareness",
        }))

        return RiskResult(
            verdict=decision.verdict,
            risk_level=risk_level,
            risk_score=decision.risk_score,
            confidence=decision.confidence,
            message_category=message_category,
            attack_type=decision.attack_type,
            user_action=decision.user_action,
            primary_reason_ar=primary_reason,
            primary_reason_en=None,
            evidence=evidence,
            url_intelligence=url_intel,
            sender_assessment=sender_assessment,
            ai_assessment=ai_assessment,
            policy_trace=decision.policy_trace,
            privacy_notes=privacy_notes,
            normalized_text=normalized,
            original_text=raw_text,
            extracted_entities=entities.entities,
            detected_actions=detected_actions,
            analyzer_version=APG_RISK_ENGINE_VERSION,
            applied_cap=decision.applied_cap,
            modality=modality,
            message_intent=message_intent,
            intent_confidence=intent_confidence,
            entity_intelligence=entity_intelligence,
            behavioral_analysis={
                k: v for k, v in behavioral.items() if k != "evidence"
            },
            # Shadow mode (Phase 2B): dynamic result stored for admin explain only.
            # Never affects HybridResult / public API.
            dynamic_url_analysis_result=_dynamic_result,
            score_breakdown=decision.score_breakdown,
        )

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
        """
        Backward-compatible wrapper — returns HybridResult for existing callers.
        """
        risk = self.analyze_full(
            text,
            source=source,
            sender=sender,
            package_name=package_name,
            extra_urls=extra_urls,
            is_known_contact=is_known_contact,
            sender_trust=sender_trust,
            sender_name=sender_name,
            source_app=source_app,
            mock_url_reputation=mock_url_reputation,
        )
        return to_hybrid_result(risk)

    # ─── Status ───────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        url_svc = self._url._service
        ai = self._ai
        return {
            "analyzer_version": APG_RISK_ENGINE_VERSION,
            "semantic_model_path": str(ai.semantic_model_status["path"]),
            "semantic_model_loaded": ai.semantic_model_status["loaded"],
            "semantic_model_error": ai.semantic_model_status["error"],
            "lexical_model_path": str(ai.lexical_model_status["path"]),
            "lexical_model_loaded": ai.lexical_model_status["loaded"],
            "lexical_model_error": ai.lexical_model_status["error"],
            "critical_rules_enabled": True,
            "url_reputation_enabled": url_svc.enabled,
            "providers_configured": get_provider_status(),
            "cache_status": url_svc.cache_status(),
            "cache_items": len(url_svc._cache),
            "cache_ttl_hours": round(url_svc.cache_ttl / 3600, 2),
            "engine": "risk_engine_v1",
            "dynamic_url_analysis_enabled": _DYNAMIC_URL_ANALYSIS_ENABLED,
            "dynamic_url_analysis_status": (
                "active" if _DYNAMIC_URL_ANALYSIS_ENABLED else "disabled"
            ),
            "dynamic_url_timeout_seconds": _DYNAMIC_URL_TIMEOUT,
            "dynamic_url_observation_ms": _DYNAMIC_URL_OBSERVATION_MS,
            "dynamic_url_time_simulation_enabled": _DYNAMIC_URL_TIME_SIMULATION_ENABLED,
            "dynamic_url_simulated_minutes": _DYNAMIC_URL_SIMULATED_MINUTES,
            "dynamic_url_score_enabled": _DYNAMIC_URL_SCORE_ENABLED,
        }

    # ─── URL check passthrough ────────────────────────────────────────────────

    def check_url(
        self,
        url: str,
        mock_url_reputation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url_svc = self._url._service
        result = url_svc.check_urls([url], mock_verdicts=mock_url_reputation)
        finding = result.findings[0] if result.findings else None
        return {
            "analyzer_version": APG_RISK_ENGINE_VERSION,
            "url_reputation_enabled": result.enabled,
            "cache_status": result.cache_status,
            "verdict": result.verdict,
            "finding": (
                None
                if finding is None
                else {
                    "url": finding.url,
                    "normalized_url": finding.normalized_url,
                    "domain": finding.domain,
                    "final_url": finding.final_url,
                    "verdict": finding.verdict,
                    "score": finding.score,
                    "local_signals": [s.to_dict() for s in finding.local_signals],
                    "provider_verdicts": [p.__dict__ for p in finding.provider_verdicts],
                }
            ),
        }


@lru_cache(maxsize=1)
def get_risk_engine_service() -> RiskEngineV1Service:
    """Cached singleton — loaded once on first call."""
    svc = RiskEngineV1Service()
    st = svc.status()
    logger.info("APG_RISK_ENGINE_VERSION %s", APG_RISK_ENGINE_VERSION)
    logger.info(
        "APG_SEMANTIC_MODEL_LOADED %s", str(st["semantic_model_loaded"]).lower()
    )
    logger.info(
        "APG_LEXICAL_MODEL_LOADED %s", str(st["lexical_model_loaded"]).lower()
    )
    logger.info(
        "APG_URL_REPUTATION_ENABLED %s", str(st["url_reputation_enabled"]).lower()
    )
    logger.info("APG_RISK_ENGINE_READY")
    return svc
