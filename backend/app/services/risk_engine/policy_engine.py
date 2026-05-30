"""
APG Risk Intelligence Engine v1 — Policy Engine

The policy engine is the single authority that translates all evidence into a
final PolicyDecision.  It follows explicit, auditable precedence rules:

  Phase 1 — Definite BLOCK (any rule match → immediate block, no score debate)
  Phase 2 — Safe caps (applied only when no block rule fired)
  Phase 3 — Evidence-based score computation
  Phase 4 — Adjustments (sender, URL, AI advisory)
  Phase 5 — Final verdict, attack-type, user-action, confidence

Key invariants:
  - AI advisory CANNOT override a definite block.
  - AI advisory CANNOT turn awareness / OTP-delivery / bank-transaction safe.
  - Known contact NEVER neutralises OTP / password / card requests.
  - Safe caps are only applied when no dangerous request is present.
  - Score is clamped to [0, 100] before producing a verdict.
"""
from __future__ import annotations

from typing import Any

from app.services.analyzer.schemas import EntityResult, IntentResult
from .schemas import (
    AIAssessment,
    AttackType,
    Evidence,
    PolicyDecision,
    ScoreAdjustment,
    ScoreBreakdown,
    ScoreFloorOrCap,
    ScoreSignal,
    SenderAssessment,
    URLIntelligence,
    UserAction,
    Verdict,
)
from .url_intelligence import _is_trusted_domain

# ─── Thresholds ────────────────────────────────────────────────────────────────
# These are the hard-coded defaults.  The YAML config at
# config/thresholds.yaml documents the same values for ops teams.
_BLOCK_MIN = 76
_WARN_MIN = 55
_CAUTION_MIN = 31

_SAFE_CAPS: dict[str, int] = {
    "awareness": 20,
    "otp_delivery": 25,
    "transactional": 25,
    "app_verification": 15,
}
_CASUAL_KNOWN_CONTACT_CAP = 10

# Official safe-context caps — applied even when a URL is present,
# because legitimate service/promotional messages routinely contain links.
# These caps are NEVER applied when dangerous_text_request is set.
# Caps are below caution_min (31) so the verdict resolves to "allow" / safe.
_OFFICIAL_SAFE_CAPS: dict[str, int] = {
    "transactional": 25,          # Bank transaction / payment receipt (with URL)
    "payment_receipt": 25,
    "government_notice": 28,      # Official government announcements
    "otp_delivery": 25,           # Also covers URL-bearing OTP delivery (WhatsApp)
    "service_notification": 30,   # Telecom/service status with trusted URL
    "subscription_notice": 30,    # Bundle welcome / renewal / expiry
    "survey": 30,                 # Customer satisfaction (official or third-party form)
    "promotional": 30,            # Telecom / retail / event offers
}

_AI_MIN_THRESHOLD = 65
_AI_MAX_NO_CONTEXT = 55
_AI_MAX_WITH_SUSPICIOUS = 68

# Intent-aware safe caps — keyed by message_intent (not message_category).
# These act as a fallback/extension to the category-based caps above and are
# the primary mechanism for keeping benign-intent messages in the safe/low range.
#
# Applied only when:
#   1. No dangerous_text_request (guarded in _get_safe_cap before this point).
#   2. URL is not deceptive / malicious (checked by _get_intent_cap).
#   3. For non-advice intents: no urgency+financial context (also in _get_intent_cap).
#
# Entries: (cap_score, arabic_reason)
_INTENT_SAFE_CAPS: dict[str, tuple[int, str]] = {
    # Warnings / educational: cap well below caution threshold (31)
    "security_advice": (
        22,
        "الرسالة توعوية وتحذر من مشاركة البيانات ولا تطلبها.",
    ),
    "otp_code": (
        22,
        "الرسالة تحتوي رمز تحقق مشروعاً ولا تطلب إرسال الرمز أو مشاركته.",
    ),
    # Promotional / marketing: top of safe range
    "advertisement": (
        30,
        "الرسالة تبدو إعلاناً أو عرضاً ترويجياً ولا تطلب بيانات حساسة.",
    ),
    # Informational / service messages: comfortably in safe range
    "service_notice": (
        28,
        "تم تقليل درجة الخطورة لأن الرسالة لا تطلب بيانات حساسة ولا يحتوي الرابط على مؤشرات خطيرة واضحة.",
    ),
    "payment_notice": (
        28,
        "تم تقليل درجة الخطورة لأن الرسالة لا تطلب بيانات حساسة ولا يحتوي الرابط على مؤشرات خطيرة واضحة.",
    ),
    "transactional": (
        25,
        "تم تقليل درجة الخطورة لأن الرسالة لا تطلب بيانات حساسة ولا يحتوي الرابط على مؤشرات خطيرة واضحة.",
    ),
    "survey_feedback": (
        28,
        "تم تقليل درجة الخطورة لأن الرسالة لا تطلب بيانات حساسة ولا يحتوي الرابط على مؤشرات خطيرة واضحة.",
    ),
}

_KNOWN_CONTACT_ADJ = -8
_UNKNOWN_FINANCIAL_ADJ = 6
_CLEAN_URL_ADJ = -5

# Arabic labels for definite-block rules: (name_ar, explanation_ar)
_BLOCK_RULE_LABELS: dict[str, tuple[str, str]] = {
    "malicious_url": (
        "رابط مصنف كخبيث",
        "صنّف مزود سمعة الروابط هذا الرابط كخبيث مما يؤكد محاولة احتيال.",
    ),
    "credential_link": (
        "طلب بيانات دخول مع رابط",
        "الرسالة تطلب بيانات دخول وتحتوي على رابط، وهو نمط تصيد احتيالي مباشر.",
    ),
    "otp_request_context": (
        "طلب رمز تحقق ضمن سياق تصيد",
        "الرسالة تطلب رمز OTP ضمن سياق مشبوه يشير إلى تصيد احتيالي.",
    ),
    "password_request": (
        "طلب كلمة مرور",
        "الرسالة تطلب كلمة المرور مباشرةً، وهو سلوك غير مشروع دائماً.",
    ),
    "card_data_request": (
        "طلب بيانات بطاقة بنكية",
        "الرسالة تطلب بيانات البطاقة البنكية أو رمز CVV مما يدل على احتيال مالي.",
    ),
    "url_urgency_account": (
        "تحديث حساب مالي مع استعجال",
        "رابط مشبوه مقترن بإلحاح وسياق مالي مما يشير إلى الاستيلاء على الحساب.",
    ),
    "impersonation_phishing_link": (
        "انتحال جهة مع رابط تصيد",
        "الرسالة تنتحل هوية جهة موثوقة وتحتوي على رابط تصيد احتيالي.",
    ),
    "financial_pressure_link": (
        "ضغط مالي مع رابط خارجي",
        "رابط خارجي مقترن بضغط مالي وحسابي مما يشير إلى محاولة اختراق.",
    ),
}


class PolicyEngine:
    """
    Stateless policy engine — all state comes from the parameters passed in.
    """

    def decide(
        self,
        entities: EntityResult,
        intents: IntentResult,
        url_intel: URLIntelligence,
        sender: SenderAssessment,
        message_category: str,
        evidence: list[Evidence],
        ai: AIAssessment,
        message_intent: str = "unknown",
    ) -> PolicyDecision:
        trace: list[str] = []

        # ─── Phase 1: Definite BLOCK ───────────────────────────────────────
        block = self._check_block(entities, intents, url_intel, evidence, trace)
        if block:
            return block

        # ─── Phase 2: Safe cap ────────────────────────────────────────────
        cap, cap_reason_ar = self._get_safe_cap(
            message_category, url_intel, intents, sender, entities, message_intent
        )
        if cap is not None:
            trace.append(
                f"CAP: category={message_category} intent={message_intent} "
                f"-> max_score={cap}"
            )

        # ─── Phase 3: Compute evidence-based score ────────────────────────
        base_score, _bd_raw = self._compute_score(
            evidence, ai, entities, intents, url_intel, sender, trace
        )

        # ─── Apply cap ────────────────────────────────────────────────────
        # Suppress safe caps when behavioral phishing fusion rules fired —
        # Rule A/C produce dangerous_intent+critical evidence that already
        # bypasses the 70-score cap; the promotional/service caps must also
        # yield to confirmed phishing patterns.
        _behavioral_phishing_ids = {
            "behavioral_account_takeover_url",
            "behavioral_payment_phishing",
        }
        if cap is not None and any(
            e.id in _behavioral_phishing_ids for e in evidence
        ):
            cap = None
            trace.append("CAP lifted: behavioral phishing evidence present")
        _bd_outer_caps: list[dict[str, Any]] = []
        if cap is not None:
            score = min(base_score, cap)
            if score != base_score:
                _bd_outer_caps.append({
                    "id": "safe_cap",
                    "from_score": base_score,
                    "to_score": score,
                    "reason_ar": cap_reason_ar or "تم تطبيق سقف أمان بناءً على تصنيف الرسالة أو نيّتها.",
                })
                trace.append(
                    f"CAP applied: base={base_score} capped to {score}"
                )
        else:
            score = base_score

        score = max(0, min(100, score))

        # ─── Phase 5: Derive verdict, attack-type, user-action ────────────
        verdict = self._score_to_verdict(score)
        attack_type = self._infer_attack_type(entities, intents, url_intel, verdict)
        user_action = self._infer_user_action(
            verdict, message_category, entities, intents, url_intel
        )
        confidence = self._compute_confidence(verdict, evidence, ai, score, cap)
        trace.append(
            f"FINAL: score={score} verdict={verdict} attack={attack_type} "
            f"action={user_action} confidence={round(confidence, 3)}"
        )

        score_breakdown = self._build_score_breakdown(
            evidence=evidence,
            bd_raw=_bd_raw,
            outer_caps=_bd_outer_caps,
            final_score=score,
            verdict=verdict,
        )

        return PolicyDecision(
            verdict=verdict,
            risk_score=score,
            attack_type=attack_type,
            user_action=user_action,
            confidence=confidence,
            applied_cap=cap,
            cap_reason_ar=cap_reason_ar,
            policy_trace=trace,
            score_breakdown=score_breakdown,
        )

    # ─── Block phase ──────────────────────────────────────────────────────────

    def _check_block(
        self,
        entities: EntityResult,
        intents: IntentResult,
        url_intel: URLIntelligence,
        evidence: list[Evidence],
        trace: list[str],
    ) -> PolicyDecision | None:

        # Rule 1: Malicious URL provider verdict
        if url_intel.verdict == "malicious":
            trace.append("BLOCK: malicious_url provider verdict")
            return self._make_block(
                score=98, attack_type="malicious_url",
                user_action="do_not_click_link", confidence=0.98,
                rule="malicious_url", trace=trace, evidence=evidence,
            )

        # Rule 2: Credential request + link surface (highest score of the two)
        if intents.credential_request and url_intel.has_link_surface:
            trace.append("BLOCK: credential_request + has_link_surface")
            return self._make_block(
                score=max(95, url_intel.max_local_score),
                attack_type="credential_harvesting",
                user_action="do_not_click_link", confidence=0.95,
                rule="credential_link", trace=trace, evidence=evidence,
            )

        # Awareness messages (educational) are exempt from credential block rules
        # unless they also contain an actual link surface (which would be anomalous)
        _awareness_only = intents.awareness and not url_intel.has_link_surface

        # Rule 3: OTP / code request with phishing context. OTP alone is
        # advisory/needs-verification; it becomes dangerous only when paired
        # with a phishing URL, credential/payment collection, impersonation, or
        # explicit urgency/threat pressure.
        if (
            intents.otp_request
            and not intents.safe_context
            and not _awareness_only
            and PolicyEngine._otp_has_phishing_context(
                intents, entities, url_intel, evidence
            )
        ):
            trace.append("BLOCK: otp_request + phishing_context")
            return self._make_block(
                score=88, attack_type="otp_theft",
                user_action="do_not_share_code", confidence=0.93,
                rule="otp_request_context", trace=trace, evidence=evidence,
            )

        # Rule 4: Password / PIN request
        if intents.password_request and not intents.safe_context and not _awareness_only:
            trace.append("BLOCK: password_request")
            return self._make_block(
                score=92, attack_type="password_theft",
                user_action="verify_from_official_app", confidence=0.95,
                rule="password_request", trace=trace, evidence=evidence,
            )

        # Rule 5: Card / CVV request
        if intents.card_data_request and not intents.safe_context and not _awareness_only:
            trace.append("BLOCK: card_data_request")
            return self._make_block(
                score=96, attack_type="card_theft",
                user_action="contact_bank_directly", confidence=0.97,
                rule="card_data_request", trace=trace, evidence=evidence,
            )

        # Rule 6: URL + account-update + urgency AND financial entity
        # Both conditions required to avoid false blocks on benign account updates
        if (
            url_intel.has_link_surface
            and intents.has("account_update")
            and intents.threat_urgency
            and entities.has_bank_or_account
        ):
            score = 95 if url_intel.verdict == "suspicious" else 90
            trace.append(
                "BLOCK: url + account_update + urgency + financial"
            )
            return self._make_block(
                score=score, attack_type="bank_account_takeover",
                user_action="do_not_click_link", confidence=0.91,
                rule="url_urgency_account", trace=trace, evidence=evidence,
            )

        # Rule 7: Known/claimed entity mismatch + phishing link surface.
        # Generalized brand impersonation: when entity intelligence or URL
        # intelligence says the identity is inconsistent, and the message also
        # asks the user to login/update/verify/pay through a link, treat it as
        # dangerous instead of leaving it in the suspicious band.
        if (
            url_intel.has_link_surface
            and not intents.safe_context
            and PolicyEngine._has_impersonation_evidence(evidence, url_intel)
            and (
                intents.has("account_update")
                or intents.has("account_login")
                or intents.credential_request
                or intents.password_request
                or intents.card_data_request
                or intents.otp_request
                or entities.has_bank_or_account
            )
        ):
            trace.append("BLOCK: impersonation + phishing_link_context")
            return self._make_block(
                score=90,
                attack_type="brand_impersonation",
                user_action="do_not_click_link",
                confidence=0.91,
                rule="impersonation_phishing_link",
                trace=trace, evidence=evidence,
            )

        # Rule 8: External/suspicious link + payment/banking/account pressure.
        if (
            url_intel.has_link_surface
            and not intents.safe_context
            and (entities.has_bank_or_account or intents.has("ambiguous_financial_notice"))
            and (
                intents.threat_urgency
                or intents.has("account_update")
                or intents.has("account_login")
                or intents.has("payment_request")
            )
            and url_intel.verdict in {"unknown", "suspicious"}
        ):
            trace.append("BLOCK: financial_account_pressure + external_link")
            return self._make_block(
                score=86,
                attack_type="bank_account_takeover",
                user_action="do_not_click_link",
                confidence=0.89,
                rule="financial_pressure_link",
                trace=trace, evidence=evidence,
            )

        return None

    @staticmethod
    def _has_impersonation_evidence(
        evidence: list[Evidence],
        url_intel: URLIntelligence,
    ) -> bool:
        if url_intel.brand_impersonation:
            return True
        ids = {e.id for e in evidence}
        return any(
            marker in ids
            for marker in {
                "entity_conflict_sender_domain",
                "entity_conflict_sender_text",
                "url_misleading_brand_in_url",
                "url_brand_impersonation",
                "url_brand_phishing_combo",
                "url_brand_suspicious_tld",
                "url_brand_shortener",
                "url_claimed_brand_domain_mismatch",
                "sender_brand_impersonation",
                "sender_spoofed",
            }
        )

    @staticmethod
    def _otp_has_phishing_context(
        intents: IntentResult,
        entities: EntityResult,
        url_intel: URLIntelligence,
        evidence: list[Evidence],
    ) -> bool:
        if url_intel.verdict in {"malicious", "suspicious"}:
            return True
        if (
            url_intel.has_link_surface
            and (
                url_intel.brand_impersonation
                or url_intel.suspicious_tld
                or url_intel.punycode_detected
                or url_intel.ip_url_detected
            )
        ):
            return True
        if (
            intents.credential_request
            or intents.password_request
            or intents.card_data_request
            or intents.has("payment_request")
            or entities.has_bank_or_account
        ):
            return True
        evidence_ids = {e.id for e in evidence}
        if PolicyEngine._has_impersonation_evidence(evidence, url_intel):
            return True
        return bool(evidence_ids & {
            "behavioral_psychological_fear_threat",
            "behavioral_psychological_pressure_combo",
            "suspicious_threat_login",
            "suspicious_url_urgency_account",
        })

    @staticmethod
    def _build_block_score_breakdown(
        rule: str,
        score: int,
        confidence: float,
        evidence: list[Evidence] | None,
    ) -> ScoreBreakdown:
        name_ar, explanation_ar = _BLOCK_RULE_LABELS.get(
            rule,
            (rule, "قاعدة حاسمة في محرك السياسة أدت إلى الحجب الفوري."),
        )
        rule_signal = ScoreSignal(
            id=rule,
            name_ar=name_ar,
            layer="policy_engine",
            severity="critical",
            delta=score,
            confidence=confidence,
            explanation_ar=explanation_ar,
        )
        positive_signals: list[ScoreSignal] = [rule_signal]
        if evidence:
            supporting = sorted(
                (
                    e for e in evidence
                    if e.category == "dangerous_intent" and e.score_delta > 0
                ),
                key=lambda e: e.score_delta,
                reverse=True,
            )[:2]
            for ev in supporting:
                positive_signals.append(ScoreSignal(
                    id=ev.id,
                    name_ar=ev.id,
                    layer=PolicyEngine._evidence_layer(ev),
                    severity=ev.severity,
                    delta=ev.score_delta,
                    confidence=ev.confidence,
                    explanation_ar=ev.explanation_ar,
                ))
        return ScoreBreakdown(
            base_score=0,
            positive_signals=positive_signals,
            negative_signals=[],
            floors_applied=[],
            caps_applied=[],
            adjustments=[],
            raw_score_before_caps=score,
            final_score=score,
            verdict="block",
            decision_summary_ar="تم تصنيف الرسالة كخطيرة بسبب قاعدة حاسمة في محرك السياسة.",
        )

    @staticmethod
    def _make_block(
        score: int,
        attack_type: AttackType,
        user_action: UserAction,
        confidence: float,
        rule: str,
        trace: list[str],
        evidence: list[Evidence] | None = None,
    ) -> PolicyDecision:
        final_score = max(0, min(100, score))
        score_breakdown = PolicyEngine._build_block_score_breakdown(
            rule=rule,
            score=final_score,
            confidence=confidence,
            evidence=evidence,
        )
        trace.append("BREAKDOWN: block score breakdown generated")
        return PolicyDecision(
            verdict="block",
            risk_score=final_score,
            attack_type=attack_type,
            user_action=user_action,
            confidence=confidence,
            applied_cap=None,
            policy_trace=list(trace),
            block_rule_triggered=rule,
            score_breakdown=score_breakdown,
        )

    # ─── Safe cap phase ───────────────────────────────────────────────────────

    @staticmethod
    def _get_intent_cap(
        message_intent: str,
        url_intel: URLIntelligence,
        intents: IntentResult,
        entities: "EntityResult | None",
    ) -> tuple[int | None, str | None]:
        """
        Return (cap_score, arabic_reason) for intent-aware caps, or (None, None).

        Guards:
          - URL must not be deceptive or malicious/suspicious.
          - For non-advice intents: urgency combined with financial/account context
            prevents capping (the existing urgency floor in _compute_score is more
            appropriate for those messages).
          - Pure advice intents (security_advice, otp_code) are exempt from the
            urgency guard since urgency in a warning is normal and safe.
        """
        entry = _INTENT_SAFE_CAPS.get(message_intent)
        if entry is None:
            return None, None

        cap_score, reason_ar = entry

        # URL deception / threat guard
        if (
            url_intel.verdict in ("malicious", "suspicious")
            or url_intel.brand_impersonation
            or url_intel.punycode_detected
            or url_intel.ip_url_detected
            or url_intel.suspicious_tld
        ):
            return None, None

        # Urgency + financial context guard — skip for pure advisory intents
        if message_intent not in ("security_advice", "otp_code"):
            _ctx_urgency = (
                intents.threat_urgency
                and entities is not None
                and (
                    entities.has_bank_or_account
                    or intents.has("account_update")
                    or intents.has("ambiguous_financial_notice")
                )
            )
            if _ctx_urgency:
                return None, None

        return cap_score, reason_ar

    @staticmethod
    def _get_safe_cap(
        category: str,
        url_intel: URLIntelligence,
        intents: IntentResult,
        sender: SenderAssessment,
        entities: "EntityResult | None" = None,
        message_intent: str = "unknown",
    ) -> tuple[int | None, str | None]:
        """Return (cap_score, arabic_reason) or (None, None)."""

        if category == "app_verification" and not url_intel.has_url:
            return _SAFE_CAPS.get("app_verification", 15), None

        # Never cap if any dangerous request was detected — must be checked before
        # awareness so a phishing message that opens with a guardrail phrase ("لا
        # تشارك...") but then actually requests credentials is not capped to safe.
        # With sentence-boundary-aware negation in intents.py, genuine educational
        # messages that only quote credential terms will not set dangerous_text_request.
        if intents.dangerous_text_request:
            return None, None

        # Awareness cap: educational messages that warn about sharing credentials.
        # Only reached when dangerous_text_request is False, so the message is not
        # making an actual credential request.
        if intents.awareness and not url_intel.has_url:
            return _SAFE_CAPS.get("awareness", 20), None

        # ── VT-confirmed-clean URL advisory cap ────────────────────────────
        # When a URL reputation provider (VirusTotal) actively confirms the URL
        # is clean AND the message contains no credential/OTP/card request,
        # no urgency, no brand impersonation, and no sensitive entities (OTP,
        # password, PIN, card, CVV, IBAN), weak local heuristics such as
        # HTTP-vs-HTTPS or payment/login words in the URL path must not push
        # the score into the suspicious range.  They remain as advisory signals
        # in matched_signals but do not determine the final verdict.
        #
        # Invariants preserved:
        #   - Malicious VT verdict → Block Rule 1 fires in Phase 1 (before here).
        #   - OTP/password/card requests → dangerous_text_request=True, excluded.
        #   - Urgency + financial context → Block Rule 6 fires in Phase 1.
        #   - Brand impersonation → excluded.
        #   - VT disabled / skipped / errored → url_intel.verdict != "clean", excluded.
        _no_sensitive = entities is None or not entities.has_sensitive_entity
        if (
            url_intel.has_url
            and url_intel.verdict == "clean"
            and _no_sensitive
            and not intents.threat_urgency
            and not url_intel.brand_impersonation
        ):
            return 25, None  # advisory-only: lands in "allow" / safe

        # ── Intent-aware caps ──────────────────────────────────────────────
        # Applied BEFORE category caps so that message_intent (a richer signal
        # than message_category) takes precedence.  Covers cases where the
        # upstream category classifier returned "unknown" / "link_action" but
        # the intent detector correctly identified the message purpose.
        intent_cap, intent_reason = PolicyEngine._get_intent_cap(
            message_intent, url_intel, intents, entities
        )
        if intent_cap is not None:
            return intent_cap, intent_reason

        # ── Official safe-context caps (apply even with URL) ───────────────
        # These cover legitimate service/promotional/government messages that
        # routinely contain links.  Block rules (Phase 1) are evaluated before
        # this phase, so credential/OTP/card-theft messages are already handled.
        # Additionally we require no otp_request / password_request / card_data_request
        # as a belt-and-suspenders guard.
        if (
            not intents.otp_request
            and not intents.password_request
            and not intents.card_data_request
            and not url_intel.brand_impersonation
            and url_intel.verdict != "malicious"
        ):
            official_cap = _OFFICIAL_SAFE_CAPS.get(category)
            if official_cap is not None:
                return official_cap, None

        # ── Original caps (no-URL only) ────────────────────────────────────
        cap = _SAFE_CAPS.get(category)
        if cap is not None and not url_intel.has_url and not intents.has("ambiguous_financial_notice"):
            return cap, None

        if (
            category == "casual"
            and (
                sender.is_known_contact is True
                or sender.trust_level in {"known", "trusted"}
            )
        ):
            return _CASUAL_KNOWN_CONTACT_CAP, None

        return None, None

    # ─── Score computation ────────────────────────────────────────────────────

    @staticmethod
    def _evidence_layer(ev: Evidence) -> str:
        if ev.category == "safe_context":
            return "safe_context"
        eid = ev.id
        if eid.startswith(("url_", "dyn_")):
            return "url_intelligence"
        if eid.startswith("behavioral_"):
            return "behavioral"
        if eid.startswith("entity_"):
            return "entity_intelligence"
        if eid.startswith("sender_"):
            return "sender_intelligence"
        if eid.startswith(("ai_", "semantic_", "lexical_")):
            return "ai_advisory"
        if eid.startswith(("intent_", "credential_", "otp_", "password_", "card_")):
            return "action_intent"
        if eid.startswith("safe_"):
            return "safe_context"
        return "risk_engine"

    @staticmethod
    def _compute_score(
        evidence: list[Evidence],
        ai: AIAssessment,
        entities: EntityResult,
        intents: IntentResult,
        url_intel: URLIntelligence,
        sender: SenderAssessment,
        trace: list[str],
    ) -> tuple[int, dict[str, Any]]:
        # Breakdown tracking (additive only — no logic changes below)
        _bd_floors: list[dict[str, Any]] = []
        _bd_adjustments: list[dict[str, Any]] = []
        _bd_inner_caps: list[dict[str, Any]] = []

        # Aggregate suspicious / dangerous evidence deltas (positive only)
        suspicious_max = max(
            (
                e.score_delta
                for e in evidence
                if e.category in ("suspicious_context", "dangerous_intent")
                and e.score_delta > 0
            ),
            default=0,
        )

        # Base score
        score = max(10 if not evidence else 18, suspicious_max)
        _bd_base_score = score  # capture after init

        # Unknown URL + financial/account context floor
        if (
            url_intel.verdict == "unknown"
            and url_intel.has_link_surface
            and (intents.has("account_update") or entities.has_bank_or_account)
        ):
            if score < 55:
                _prev = score
                score = 55
                _bd_floors.append({
                    "id": "unknown_url_account_context",
                    "from_score": _prev,
                    "to_score": 55,
                    "reason_ar": "رابط غير معروف مع سياق مالي أو حسابي رفع الحد الأدنى إلى 55.",
                })
                trace.append("SCORE: unknown_url_account_context -> floor 55")

        if suspicious_max >= 55:
            _prev = score
            score = max(score, 55)
            if score != _prev:
                _bd_floors.append({
                    "id": "suspicious_max_floor_55",
                    "from_score": _prev,
                    "to_score": score,
                    "reason_ar": "أعلى مؤشر خطورة بلغ 55 أو أكثر، رُفع الحد الأدنى إلى 55.",
                })

        # Urgency/threat without credential request → suspicious floor
        # Only applies when combined with financial/account context or when urgency
        # explicitly targets account suspension (not generic marketing "الآن"/"now").
        _urgency_with_context = (
            intents.threat_urgency
            and not intents.dangerous_text_request
            and not intents.safe_context
            and (
                entities.has_bank_or_account
                or intents.has("account_update")
                or intents.has("account_login")
                or intents.has("ambiguous_financial_notice")
            )
        )
        if _urgency_with_context:
            urgency_floor = 45 if url_intel.has_link_surface else 35
            if score < urgency_floor:
                _prev = score
                score = urgency_floor
                _bd_floors.append({
                    "id": "urgency_financial_context",
                    "from_score": _prev,
                    "to_score": urgency_floor,
                    "reason_ar": f"وجود ضغط وإلحاح مع سياق مالي رفع الحد الأدنى إلى {urgency_floor}.",
                })
                trace.append(f"SCORE: urgency_no_credential -> floor {urgency_floor}")

        # AI advisory (only for ambiguous messages)
        ai_contribution = PolicyEngine._ai_contribution(ai, suspicious_max, intents)
        if ai_contribution > score:
            _prev = score
            score = ai_contribution
            _bd_adjustments.append({
                "id": "ai_advisory",
                "delta": ai_contribution - _prev,
                "reason_ar": "تقييم نموذج الذكاء الاصطناعي رفع الدرجة.",
            })
            trace.append(f"SCORE: ai_advisory -> {ai_contribution}")

        # ── Sender adjustments ────────────────────────────────────────────
        is_known = (
            sender.is_known_contact is True
            or sender.trust_level in {"known", "trusted"}
        )
        if is_known and not entities.has_sensitive_entity and suspicious_max < 55:
            score += _KNOWN_CONTACT_ADJ
            _bd_adjustments.append({
                "id": "known_contact",
                "delta": _KNOWN_CONTACT_ADJ,
                "reason_ar": "المرسل معروف أو موثوق، خُفِّضت الدرجة.",
            })
            trace.append(f"SCORE: known_contact -> {_KNOWN_CONTACT_ADJ}")

        # Unknown sender + financial context
        has_unknown_financial = any(
            e.id == "unknown_sender_financial_context" for e in sender.evidence
        )
        if has_unknown_financial:
            score += _UNKNOWN_FINANCIAL_ADJ
            _bd_adjustments.append({
                "id": "unknown_sender_financial",
                "delta": _UNKNOWN_FINANCIAL_ADJ,
                "reason_ar": "مرسل غير معروف مع سياق مالي، رُفِعت الدرجة.",
            })
            trace.append(f"SCORE: unknown_sender_financial -> +{_UNKNOWN_FINANCIAL_ADJ}")

        # Clean URL slight reduction
        if url_intel.verdict == "clean":
            score += _CLEAN_URL_ADJ
            _bd_adjustments.append({
                "id": "clean_url",
                "delta": _CLEAN_URL_ADJ,
                "reason_ar": "الرابط مصنّف نظيف، خُفِّضت الدرجة.",
            })
            trace.append(f"SCORE: clean_url -> {_CLEAN_URL_ADJ}")

        # Capture raw score after floors+adjustments, before any caps
        _raw_before_caps = int(round(max(0, min(100, score))))

        # Cap at 70 if no definite danger (no block rules fired here so we
        # rely on evidence category)
        has_definite_danger = any(
            e.category == "dangerous_intent" and e.severity == "critical"
            for e in evidence
        )
        if not has_definite_danger and suspicious_max > 0:
            _prev = score
            score = min(score, 70)
            if score != _prev:
                _bd_inner_caps.append({
                    "id": "no_critical_evidence_cap_70",
                    "from_score": int(round(max(0, min(100, _prev)))),
                    "to_score": 70,
                    "reason_ar": "لا توجد مؤشرات خطيرة قاطعة، سقف الدرجة 70.",
                })

        # Final calibration caps: weak/advisory signals can explain caution, but
        # should not stack into a dangerous classification without a strong
        # phishing combination.
        positive_evidence = [
            e for e in evidence
            if e.category in ("suspicious_context", "dangerous_intent")
            and e.score_delta > 0
        ]
        strong_evidence = [
            e for e in positive_evidence
            if PolicyEngine._is_strong_evidence(e)
        ]
        otp_only = (
            intents.otp_request
            and not strong_evidence
            and not PolicyEngine._otp_has_phishing_context(
                intents, entities, url_intel, evidence
            )
        )
        if otp_only and score > 45:
            _prev = score
            score = 45
            _bd_inner_caps.append({
                "id": "otp_without_phishing_context_cap_45",
                "from_score": int(round(max(0, min(100, _prev)))),
                "to_score": 45,
                "reason_ar": "طلب رمز OTP فقط بدون سياق تصيّد، سقف الدرجة 45.",
            })
            trace.append("CAP applied: otp_without_phishing_context -> max_score=45")
        elif positive_evidence and not strong_evidence and score > 54:
            _prev = score
            score = 54
            _bd_inner_caps.append({
                "id": "weak_advisory_stack_cap_54",
                "from_score": int(round(max(0, min(100, _prev)))),
                "to_score": 54,
                "reason_ar": "إشارات تحذيرية ضعيفة فقط بدون تأكيد قوي، سقف الدرجة 54.",
            })
            trace.append("CAP applied: weak_advisory_stack -> max_score=54")

        pressure_or_reward_only = (
            positive_evidence
            and all(
                e.id.startswith("behavioral_psychological_")
                or e.id in {"suspicious_urgency_link", "suspicious_urgent_account"}
                for e in positive_evidence
            )
            and not any(e.id == "behavioral_psychological_pressure_combo" for e in positive_evidence)
        )
        if pressure_or_reward_only and score > 48:
            _prev = score
            score = 48
            _bd_inner_caps.append({
                "id": "pressure_reward_only_cap_48",
                "from_score": int(round(max(0, min(100, _prev)))),
                "to_score": 48,
                "reason_ar": "ضغط نفسي فقط بدون تأكيد قوي، سقف الدرجة 48.",
            })
            trace.append("CAP applied: pressure_reward_only -> max_score=48")

        trusted_official_url = (
            url_intel.primary_domain
            and _is_trusted_domain(url_intel.primary_domain)
            and url_intel.verdict not in {"malicious", "suspicious"}
            and not url_intel.brand_impersonation
            and not url_intel.punycode_detected
            and not url_intel.ip_url_detected
        )
        official_has_dangerous_collection = (
            intents.credential_request
            or intents.password_request
            or intents.card_data_request
        )
        if (
            trusted_official_url
            and not official_has_dangerous_collection
            and not has_definite_danger
            and score > 30
        ):
            _prev = score
            score = 30
            _bd_inner_caps.append({
                "id": "trusted_official_domain_cap_30",
                "from_score": int(round(max(0, min(100, _prev)))),
                "to_score": 30,
                "reason_ar": "رابط من نطاق رسمي موثوق مع إشارات ضعيفة، سقف الدرجة 30.",
            })
            trace.append("CAP applied: trusted_official_domain_weak_signals -> max_score=30")

        _bd_raw: dict[str, Any] = {
            "base_score": _bd_base_score,
            "floors": _bd_floors,
            "adjustments": _bd_adjustments,
            "inner_caps": _bd_inner_caps,
            "raw_before_caps": _raw_before_caps,
        }

        return int(round(max(0, min(100, score)))), _bd_raw

    @staticmethod
    def _build_score_breakdown(
        evidence: list[Evidence],
        bd_raw: dict[str, Any],
        outer_caps: list[dict[str, Any]],
        final_score: int,
        verdict: str,
    ) -> ScoreBreakdown:
        positive_signals: list[ScoreSignal] = []
        negative_signals: list[ScoreSignal] = []
        for ev in evidence:
            sig = ScoreSignal(
                id=ev.id,
                name_ar=ev.id,
                layer=PolicyEngine._evidence_layer(ev),
                severity=ev.severity,
                delta=ev.score_delta,
                confidence=ev.confidence,
                explanation_ar=ev.explanation_ar,
            )
            if ev.score_delta > 0:
                positive_signals.append(sig)
            elif ev.score_delta < 0:
                negative_signals.append(sig)

        floors = [
            ScoreFloorOrCap(
                id=f["id"],
                from_score=f["from_score"],
                to_score=f["to_score"],
                reason_ar=f["reason_ar"],
            )
            for f in bd_raw["floors"]
        ]
        all_caps = [
            ScoreFloorOrCap(
                id=c["id"],
                from_score=c["from_score"],
                to_score=c["to_score"],
                reason_ar=c["reason_ar"],
            )
            for c in bd_raw["inner_caps"] + outer_caps
        ]
        adjustments = [
            ScoreAdjustment(
                id=a["id"],
                delta=a["delta"],
                reason_ar=a["reason_ar"],
            )
            for a in bd_raw["adjustments"]
        ]

        if verdict == "block":
            summary = "تم رفع الخطورة لأن الرسالة تحتوي على مؤشرات قوية مثل طلب بيانات حساسة أو رابط غير موثوق."
        elif verdict in ("warn", "caution"):
            summary = "الرسالة تحتوي على عدة مؤشرات تحتاج تحققًا قبل التفاعل معها."
        else:
            summary = "لم تظهر مؤشرات خطورة كافية، وتم تخفيض النتيجة بسبب سياق آمن أو موثوق."

        return ScoreBreakdown(
            base_score=bd_raw["base_score"],
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            floors_applied=floors,
            caps_applied=all_caps,
            adjustments=adjustments,
            raw_score_before_caps=bd_raw["raw_before_caps"],
            final_score=final_score,
            verdict=verdict,
            decision_summary_ar=summary,
        )

    @staticmethod
    def _is_strong_evidence(evidence: Evidence) -> bool:
        if evidence.category == "dangerous_intent" and evidence.severity == "critical":
            return True
        return evidence.id in {
            "url_brand_phishing_combo",
            "url_claimed_brand_domain_mismatch",
            "behavioral_account_takeover_url",
            "behavioral_payment_phishing",
            "behavioral_psychological_pressure_combo",
            "suspicious_credential_link",
            "suspicious_threat_login",
            "entity_conflict_sender_domain",
            "entity_conflict_sender_text",
        }

    @staticmethod
    def _ai_contribution(
        ai: AIAssessment, suspicious_max: int, intents: IntentResult
    ) -> int:
        """
        Compute the AI advisory contribution to the score.
        Returns 0 if:
          - max AI score < threshold
          - safe_context is set
          - definite danger is already present (rules handle it)
        """
        if intents.safe_context or intents.dangerous_text_request:
            return 0
        ai_score = ai.max_scaled
        if ai_score < _AI_MIN_THRESHOLD:
            return 0
        if suspicious_max >= 40:
            return min(ai_score, _AI_MAX_WITH_SUSPICIOUS)
        return min(ai_score, _AI_MAX_NO_CONTEXT)

    # ─── Verdict / label helpers ──────────────────────────────────────────────

    @staticmethod
    def _score_to_verdict(score: int) -> Verdict:
        if score >= _BLOCK_MIN:
            return "block"
        if score >= _WARN_MIN:
            return "warn"
        if score >= _CAUTION_MIN:
            return "caution"
        return "allow"

    @staticmethod
    def _score_to_risk_level(score: int) -> str:
        if score >= 85:
            return "critical"
        if score >= 65:
            return "high"
        if score >= 40:
            return "medium"
        if score >= 20:
            return "low"
        return "minimal"

    @staticmethod
    def _infer_attack_type(
        entities: EntityResult,
        intents: IntentResult,
        url_intel: URLIntelligence,
        verdict: Verdict,
    ) -> AttackType:
        if verdict not in ("block", "warn"):
            return "none"
        if url_intel.verdict == "malicious":
            return "malicious_url"
        if intents.credential_request and url_intel.has_link_surface:
            return "credential_harvesting"
        if intents.otp_request:
            return "otp_theft"
        if intents.password_request:
            return "password_theft"
        if intents.card_data_request:
            return "card_theft"
        if url_intel.has_link_surface and entities.has_bank_or_account:
            return "bank_account_takeover"
        if intents.credential_request:
            return "social_engineering"
        if url_intel.brand_impersonation:
            return "brand_impersonation"
        return "unknown"

    @staticmethod
    def _infer_user_action(
        verdict: Verdict,
        category: str,
        entities: EntityResult,
        intents: IntentResult,
        url_intel: URLIntelligence,
    ) -> UserAction:
        if verdict == "allow":
            return "no_action_needed"
        if url_intel.verdict == "malicious":
            return "report_message"
        if intents.otp_request or intents.password_request:
            return "do_not_share_code"
        if intents.card_data_request:
            return "contact_bank_directly"
        if url_intel.has_link_surface:
            return "do_not_click_link"
        if entities.has_bank_or_account:
            return "contact_bank_directly"
        return "verify_from_official_app"

    @staticmethod
    def _compute_confidence(
        verdict: Verdict,
        evidence: list[Evidence],
        ai: AIAssessment,
        score: int,
        cap: int | None,
    ) -> float:
        if verdict == "block":
            critical = [
                e for e in evidence
                if e.severity == "critical" and e.category == "dangerous_intent"
            ]
            return min(0.99, 0.90 + len(critical) * 0.03)

        if verdict == "allow":
            safe_ev = [e for e in evidence if e.category == "safe_context"]
            if cap is not None and score <= cap and safe_ev:
                return min(0.99, 0.88 + len(safe_ev) * 0.04)
            return 0.82 if score < 15 else 0.78

        # warn / caution
        ai_only = ai.max_scaled >= 65 and not any(
            e.category == "dangerous_intent" for e in evidence
        )
        if ai_only:
            return 0.62
        susp = [e for e in evidence if e.category == "suspicious_context"]
        return min(0.87, 0.60 + len(susp) * 0.08)
