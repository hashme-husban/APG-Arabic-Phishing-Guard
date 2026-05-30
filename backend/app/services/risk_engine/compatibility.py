"""
APG Risk Intelligence Engine v1 — Backward Compatibility Layer

Maps the new RiskResult → HybridResult so that existing routers, Flutter
mobile clients, and the Web Admin console continue to work unchanged.

Mapping (from spec):
  allow  → safe
  caution → suspicious
  warn    → suspicious
  block   → dangerous

Public API fields preserved (from original hybrid_analyzer.py):
  - classification: safe | suspicious | dangerous
  - risk_score
  - reasons
  - matched_signals
  - recommendation
  - detected_url
  - masked_text          (still empty; masking is done by the router)
  - analyzer_version     (in debug dict)
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse as _urlparse

from app.services.analyzer.schemas import HybridResult
from app.services.entity_registry import get_registry
from .explanation_builder import build_recommendation
from .schemas import RiskResult


_SEVERITY_ORDER: tuple[str, ...] = ("info", "low", "medium", "high", "critical")

# Registered-domain extractor (2-label, no tldextract dependency)
def _reg2(hostname: str) -> str:
    parts = [p for p in hostname.strip(".").split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname


def _normalize_error_category(error: str | None) -> str | None:
    """Map a raw sandbox error string to a stable error category enum."""
    if not error:
        return None
    e = error.lower()
    if e.startswith("dns_failed") or "dns" in e:
        return "dns_failed"
    if "timeout" in e:
        return "timeout"
    if "playwright_not_installed" in e or "playwright_unavailable" in e or "import_error" in e:
        return "playwright_unavailable"
    if e == "no_url":
        return "unsupported_url"
    if "navigation" in e or "net::err" in e:
        return "navigation_failed"
    if "unsupported" in e:
        return "unsupported_url"
    return "unexpected_error"


def _build_evidence_preview_summary(evidence_preview: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact summary of shadow-mode evidence — count, max delta, max severity, IDs."""
    if not evidence_preview:
        return {"count": 0, "max_delta": 0, "max_severity": "none", "ids": []}
    max_delta = max((int(e.get("score_delta", 0)) for e in evidence_preview), default=0)
    max_sev_idx = max(
        (
            _SEVERITY_ORDER.index(e["severity"])
            for e in evidence_preview
            if e.get("severity") in _SEVERITY_ORDER
        ),
        default=0,
    )
    return {
        "count": len(evidence_preview),
        "max_delta": max_delta,
        "max_severity": _SEVERITY_ORDER[max_sev_idx],
        "ids": [e["id"] for e in evidence_preview if "id" in e],
    }


def _build_sandbox_summary(
    dynamic_result: Any,
    final_domain_changed: bool,
) -> dict[str, Any]:
    """
    High-level human-readable risk summary for the sandbox run.

    Included for both completed and non-completed (failed/skipped) results.
    """
    if dynamic_result is None or getattr(dynamic_result, "status", "failed") != "completed":
        return {
            "risk_indicators_count": 0,
            "has_redirects": False,
            "has_delayed_behavior": False,
            "has_login_surface": False,
            "has_sensitive_fields": False,
            "has_external_requests": False,
            "domain_changed": False,
            "summary_ar": "تعذر تحليل الرابط ديناميكيًا، وتم الاعتماد على التحليل الثابت.",
        }

    has_redirects = len(getattr(dynamic_result, "redirect_chain", [])) > 0
    has_delayed = bool(
        getattr(dynamic_result, "delayed_url_change", False)
        or getattr(dynamic_result, "delayed_title_change", False)
        or getattr(dynamic_result, "delayed_sensitive_field_appeared", False)
    )
    has_login = bool(getattr(dynamic_result, "has_login_form", False))
    has_sensitive = bool(
        getattr(dynamic_result, "has_password_field", False)
        or getattr(dynamic_result, "has_otp_field", False)
    )
    has_external = getattr(dynamic_result, "suspicious_requests", 0) > 0

    risk_indicators_count = sum([
        has_redirects, has_delayed, has_login, has_sensitive,
        has_external, final_domain_changed,
    ])

    if has_login or has_sensitive:
        summary_ar = "الصفحة تحتوي على نموذج دخول أو حقول حساسة."
    elif has_redirects or has_delayed:
        summary_ar = "الرابط يحتوي على تحويلات أو تغيّر بعد التحميل."
    elif risk_indicators_count >= 2:
        summary_ar = "تم رصد عدة مؤشرات ديناميكية تحتاج تحققًا إضافيًا."
    else:
        summary_ar = "لم تظهر مؤشرات ديناميكية واضحة داخل الصفحة."

    return {
        "risk_indicators_count": risk_indicators_count,
        "has_redirects": has_redirects,
        "has_delayed_behavior": has_delayed,
        "has_login_surface": has_login,
        "has_sensitive_fields": has_sensitive,
        "has_external_requests": has_external,
        "domain_changed": final_domain_changed,
        "summary_ar": summary_ar,
    }


def _build_dynamic_url_debug(dynamic_result: Any) -> dict[str, Any]:
    """
    Build a normalized debug object from a DynamicURLAnalysisResult.

    Always present in debug.dynamic_url_analysis so callers can detect
    whether the feature was enabled/executed without checking for None.

    Stable shapes:
      disabled  → {enabled:false, mode:"disabled", executed:false, score_impact:..., ready_for_scoring:false}
      no_url    → {enabled:true, mode:"shadow", executed:false, reason:"no_url", score_impact:..., ready_for_scoring:false}
      failed    → base + error_category + sandbox_summary + evidence_preview_summary + ready_for_scoring
      completed → full object
    """
    # ── Disabled (feature flag off) ───────────────────────────────────────────
    if dynamic_result is None or getattr(dynamic_result, "status", "disabled") == "disabled":
        return {
            "enabled": False,
            "mode": "disabled",
            "executed": False,
            "score_impact": "none_shadow_mode",
            "ready_for_scoring": False,
        }

    status = getattr(dynamic_result, "status", "failed")
    error = getattr(dynamic_result, "error", None) or None
    error_category = _normalize_error_category(error)
    evidence_preview: list[dict[str, Any]] = getattr(dynamic_result, "evidence_preview", [])

    # ── Enabled but no URL (skipped with reason=no_url) ──────────────────────
    if status == "skipped" and error == "no_url":
        return {
            "enabled": True,
            "mode": "shadow",
            "executed": False,
            "reason": "no_url",
            "score_impact": "none_shadow_mode",
            "ready_for_scoring": False,
        }

    executed = status in ("completed", "failed")

    # Use score_impact_override when Phase 3 scoring is active; fall back to shadow-mode label.
    _score_impact = getattr(dynamic_result, "score_impact_override", None) or "none_shadow_mode"
    _scoring_gate = getattr(dynamic_result, "scoring_gate", None)
    _scored_ev_summary = getattr(dynamic_result, "scored_evidence_summary", None)

    base: dict[str, Any] = {
        "enabled": True,
        "mode": "shadow",
        "executed": executed,
        "primary_url": getattr(dynamic_result, "url", None) or None,
        "score_impact": _score_impact,
        "error": error,
        "error_category": error_category,
        "scoring_gate": _scoring_gate,
        "scored_evidence_summary": _scored_ev_summary,
    }

    # ── Non-completed (failed / other) ────────────────────────────────────────
    if status != "completed":
        ep_summary = _build_evidence_preview_summary(evidence_preview)
        ready = executed and error is None and ep_summary["count"] > 0
        base.update({
            "sandbox_summary": _build_sandbox_summary(dynamic_result, False),
            "evidence_preview_summary": ep_summary,
            "evidence_preview": evidence_preview,
            "ready_for_scoring": ready,
        })
        return base

    # ── Completed ─────────────────────────────────────────────────────────────
    orig_host = (_urlparse(dynamic_result.url).hostname or "").lower() if dynamic_result.url else ""
    final_url = getattr(dynamic_result, "final_url", None)
    final_host = (_urlparse(final_url).hostname or "").lower() if final_url else ""

    final_domain_changed = bool(
        final_host
        and orig_host
        and _reg2(orig_host) != _reg2(final_host)
        and _reg2(orig_host)
    )

    ep_summary = _build_evidence_preview_summary(evidence_preview)
    ready = executed and error is None and ep_summary["count"] > 0

    base.update({
        "initial_domain": orig_host or None,
        "final_url": final_url,
        "final_domain": final_host or None,
        "final_domain_changed": final_domain_changed,
        "redirect_count": len(dynamic_result.redirect_chain),
        # redirect_chain is list[str] in current sandbox impl
        "redirect_chain": dynamic_result.redirect_chain[:10],
        "page_title": getattr(dynamic_result, "page_title", None),
        "forms_count": getattr(dynamic_result, "form_count", 0),
        "login_form_detected": bool(getattr(dynamic_result, "has_login_form", False)),
        "password_field_detected": bool(getattr(dynamic_result, "has_password_field", False)),
        "otp_field_detected": bool(getattr(dynamic_result, "has_otp_field", False)),
        "card_field_detected": False,   # not tracked in current sandbox impl
        "delayed_redirect_detected": bool(getattr(dynamic_result, "delayed_url_change", False)),
        "title_changed_after_load": bool(getattr(dynamic_result, "delayed_title_change", False)),
        "sensitive_form_appeared_after_delay": bool(
            getattr(dynamic_result, "delayed_sensitive_field_appeared", False)
        ),
        "external_hosts": list(getattr(dynamic_result, "external_host_list", []))[:20],
        "suspicious_external_requests_count": getattr(dynamic_result, "suspicious_requests", 0),
        "time_simulation_enabled": bool(getattr(dynamic_result, "time_simulation_enabled", False)),
        "simulated_minutes": getattr(dynamic_result, "simulated_minutes", 0),
        "elapsed_ms": round(getattr(dynamic_result, "elapsed_ms", 0.0), 2),
        # Shadow-mode evidence
        "evidence_preview": evidence_preview,
        "evidence_preview_summary": ep_summary,
        "sandbox_summary": _build_sandbox_summary(dynamic_result, final_domain_changed),
        "ready_for_scoring": ready,
    })
    return base

VERDICT_TO_CLASSIFICATION: dict[str, str] = {
    "allow": "safe",
    "caution": "suspicious",
    "warn": "suspicious",
    "block": "dangerous",
}


def _entity_ref(entity: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a stable public entity reference from registry match data."""
    if not entity or not entity.get("entity_id"):
        return None
    entity_id = entity.get("entity_id")
    full = get_registry().get_entity(entity_id) or {}
    return {
        "id": entity_id,
        "name": entity.get("entity_name") or full.get("name") or "",
        "arabic_name": full.get("primary_arabic_name") or "",
        "type": entity.get("entity_type") or full.get("entity_type") or "",
    }


def _build_entity_summary(
    entity_intelligence: dict[str, Any] | None,
    url_rep: Any,
    evidence: list[Any],
) -> dict[str, Any] | None:
    """
    Project existing entity intelligence into a stable UI contract.

    This is presentation-only: it does not recompute detection, score evidence,
    or alter policy decisions.
    """
    if not entity_intelligence:
        return None

    claimed = entity_intelligence.get("claimed_entity")
    sender = entity_intelligence.get("sender_entity")
    domain = entity_intelligence.get("domain_entity")
    domain_candidates = entity_intelligence.get("domain_entities") or []
    domain_candidate_ids = set(entity_intelligence.get("domain_entity_ids") or [])
    violations = entity_intelligence.get("entity_policy_violations") or []
    primary_domain = url_rep.primary_domain if url_rep else None

    claimed_id = claimed.get("entity_id") if claimed else None
    official_domain_match = bool(
        claimed_id
        and primary_domain
        and (
            claimed_id in domain_candidate_ids
            or (domain and claimed_id == domain.get("entity_id"))
        )
    )

    evidence_ids = {getattr(ev, "id", "") for ev in evidence}
    brand_mismatch = bool(
        evidence_ids
        & {
            "url_brand_impersonation",
            "url_brand_phishing_combo",
            "url_claimed_brand_domain_mismatch",
        }
    )
    entity_conflict = bool(entity_intelligence.get("entity_conflict", False))
    mismatch = bool(entity_conflict or brand_mismatch)

    mismatch_type = None
    if entity_conflict:
        mismatch_type = "entity_sender_domain_conflict"
    elif brand_mismatch:
        mismatch_type = "claimed_entity_domain_mismatch"

    claimed_ref = _entity_ref(claimed)
    sender_ref = _entity_ref(sender)
    domain_ref = _entity_ref(domain)
    candidate_refs = [
        ref
        for ref in (_entity_ref(candidate) for candidate in domain_candidates)
        if ref is not None
    ]

    has_useful_data = any(
        [
            claimed_ref,
            sender_ref,
            domain_ref,
            candidate_refs,
            mismatch,
            violations,
        ]
    )
    if not has_useful_data:
        return None

    if not claimed_ref:
        display_message = "لم يتم التعرف على جهة محددة في الرسالة."
    elif official_domain_match:
        display_message = "الرابط يتطابق مع نطاق رسمي للجهة المذكورة."
    elif mismatch:
        display_message = "الجهة المذكورة لا تبدو متطابقة مع نطاق الرابط."
    elif primary_domain:
        display_message = "تم التعرف على الجهة، لكن حالة النطاق الرسمي تحتاج تحققًا إضافيًا."
    else:
        display_message = "تم التعرف على الجهة المذكورة دون رابط قابل للتحقق."

    return {
        "claimed": claimed_ref,
        "sender": sender_ref,
        "domain": domain_ref,
        "domain_candidates": candidate_refs,
        "official_domain_match": official_domain_match,
        "mismatch": mismatch,
        "mismatch_type": mismatch_type,
        "link_domain": primary_domain,
        "policy_violations": violations,
        "display_message_ar": display_message,
    }


def to_hybrid_result(risk: RiskResult) -> HybridResult:
    """Convert a RiskResult to a backward-compatible HybridResult."""
    classification = VERDICT_TO_CLASSIFICATION.get(risk.verdict, "suspicious")

    # Build reasons list — most critical evidence explanations first
    reasons: list[str] = []
    if risk.primary_reason_ar:
        reasons.append(risk.primary_reason_ar)
    if classification != "safe":
        for ev in risk.evidence:
            if ev.category in ("dangerous_intent", "suspicious_context") and ev.explanation_ar:
                if ev.explanation_ar not in reasons:
                    reasons.append(ev.explanation_ar)
    for ev in risk.evidence:
        if ev.category == "safe_context" and ev.explanation_ar and classification == "safe":
            if ev.explanation_ar not in reasons:
                reasons.append(ev.explanation_ar)
    reasons = reasons[:8]

    # Build matched_signals list (mirrors old format)
    matched_signals: list[dict[str, Any]] = []
    for ev in risk.evidence[:24]:
        weight = abs(ev.score_delta)
        signal: dict[str, Any] = {
            "name": ev.id,
            "type": ev.category,
            "weight": weight,
            "explanation_ar": ev.explanation_ar,
            "evidence": ev.matched_text,
            "category": ev.category,
            "impact": (
                "high" if weight >= 80
                else "medium" if weight >= 40
                else "low"
            ),
        }
        # Merge provider-specific extra fields (e.g. VirusTotal stats).
        # ev.extra["type"] intentionally overrides the generic category string
        # for provider signals so API consumers can distinguish them.
        if ev.extra:
            signal.update(ev.extra)
        matched_signals.append(signal)

    detected_url = risk.url_intelligence.primary_url if risk.url_intelligence else None
    entity_summary = _build_entity_summary(
        risk.entity_intelligence,
        risk.url_intelligence,
        risk.evidence,
    )

    # Build debug dict — enriched with new fields, but always includes the
    # old fields that v5 callers expect.
    url_rep = risk.url_intelligence
    debug: dict[str, Any] = {
        "analyzer_version": risk.analyzer_version,
        # New fields
        "verdict": risk.verdict,
        "risk_level": risk.risk_level,
        "confidence": round(risk.confidence, 4),
        "message_category": risk.message_category,
        "attack_type": risk.attack_type,
        "user_action": risk.user_action,
        "modality": risk.modality,
        "message_intent": risk.message_intent,
        "intent_confidence": round(risk.intent_confidence, 4),
        "policy_trace": risk.policy_trace,
        "privacy_notes": risk.privacy_notes,
        # Old v5-compatible fields
        "semantic_score": (
            round(risk.ai_assessment.semantic_score, 6)
            if risk.ai_assessment.semantic_loaded else None
        ),
        "lexical_score": (
            round(risk.ai_assessment.lexical_score, 6)
            if risk.ai_assessment.lexical_loaded else None
        ),
        "rule_score": max(
            (abs(e.score_delta) for e in risk.evidence if e.category == "dangerous_intent"),
            default=0,
        ),
        "url_score": url_rep.max_local_score if url_rep else 0,
        "sender_score": max(
            (abs(e.score_delta) for e in risk.sender_assessment.evidence if e.score_delta > 0),
            default=0,
        ),
        "critical_floor": risk.risk_score if risk.verdict == "block" else 0,
        "model_loaded": {
            "semantic": risk.ai_assessment.semantic_loaded,
            "lexical": risk.ai_assessment.lexical_loaded,
        },
        "normalized_text": risk.normalized_text,
        "entities": sorted(risk.extracted_entities),
        "detected_actions": risk.detected_actions,
        "intents": risk.detected_actions,
        "safe_context": (
            "educational_awareness"
            if any(
                e.id.startswith("safe_awareness")
                for e in risk.evidence
                if e.category == "safe_context"
            ) else None
        ),
        "is_known_contact": risk.sender_assessment.is_known_contact,
        "sender_trust": risk.sender_assessment.trust_level,
        "url_reputation": {
            "enabled": True,
            "verdict": url_rep.verdict if url_rep else "unknown",
            "findings": [
                {
                    "url": u,
                    "domain": url_rep.primary_domain,
                    "verdict": url_rep.verdict,
                    "score": url_rep.max_local_score,
                    "local_signals": [e.to_dict() for e in url_rep.local_evidence],
                    "providers": url_rep.provider_verdicts,
                }
                for u in (url_rep.extracted_urls[:3] if url_rep else [])
            ],
        },
        # Applied cap info
        "applied_cap": risk.applied_cap,
        # Entity intelligence (debug — no score impact)
        "claimed_entity": (
            risk.entity_intelligence.get("claimed_entity")
            if risk.entity_intelligence else None
        ),
        "sender_entity": (
            risk.entity_intelligence.get("sender_entity")
            if risk.entity_intelligence else None
        ),
        "domain_entity": (
            risk.entity_intelligence.get("domain_entity")
            if risk.entity_intelligence else None
        ),
        "entity_conflict": (
            risk.entity_intelligence.get("entity_conflict", False)
            if risk.entity_intelligence else False
        ),
        "entity_policy_violations": (
            risk.entity_intelligence.get("entity_policy_violations", [])
            if risk.entity_intelligence else []
        ),
        "entity_summary": entity_summary,
        "behavioral_analysis": risk.behavioral_analysis,
        # Score breakdown — structured audit trail of how the final score was reached
        "score_breakdown": (
            risk.score_breakdown.to_dict() if risk.score_breakdown is not None else None
        ),
        # Dynamic URL sandbox — shadow mode (Phase 2): metadata only, no score impact
        "dynamic_url_analysis": _build_dynamic_url_debug(risk.dynamic_url_analysis_result),
        # Source domains list
        "domains": [url_rep.primary_domain] if url_rep and url_rep.primary_domain else [],
        "phone_numbers_detected": 0,
        "semantic_details": risk.ai_assessment.to_dict().get("evidence", []),
        "lexical_details": {},
    }

    return HybridResult(
        risk_score=risk.risk_score,
        classification=classification,
        masked_text="",
        detected_url=detected_url,
        reasons=reasons,
        matched_signals=matched_signals,
        recommendation=build_recommendation(risk.verdict),
        debug=debug,
        confidence=risk.confidence,
        verdict=risk.verdict,
        message_category=risk.message_category,
    )


def to_backward_compatible_response(risk: RiskResult) -> dict[str, Any]:
    """
    Build the dict returned by POST /analyze.

    Always includes the old fields; new fields are added alongside so
    that new clients can parse them without breaking old ones.
    """
    hybrid = to_hybrid_result(risk)
    return {
        # Old (always present)
        "classification": hybrid.classification,
        "risk_score": hybrid.risk_score,
        "reasons": hybrid.reasons,
        "matched_signals": hybrid.matched_signals,
        "recommendation": hybrid.recommendation,
        "detected_url": hybrid.detected_url,
        "masked_text": hybrid.masked_text,
        "analyzer_version": risk.analyzer_version,
        # New (opt-in for clients that want richer data)
        "verdict": risk.verdict,
        "risk_level": risk.risk_level,
        "confidence": round(risk.confidence, 4),
        "message_category": risk.message_category,
        "attack_type": risk.attack_type,
        "user_action": risk.user_action,
        "message_intent": risk.message_intent,
        "intent_confidence": round(risk.intent_confidence, 4),
        "entity_summary": hybrid.debug.get("entity_summary"),
    }
