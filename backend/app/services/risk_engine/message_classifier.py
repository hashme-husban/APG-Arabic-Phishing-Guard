"""
APG Risk Intelligence Engine v1 — Message Classifier

Classifies a message into one of the canonical MessageCategory values based
on the combined output of entity extraction, action detection, and URL
intelligence.

Rules are evaluated top-down; the first matching rule wins.
"""
from __future__ import annotations

from app.services.analyzer.schemas import EntityResult, IntentResult
from .schemas import MessageCategory, URLIntelligence


def classify_message(
    entities: EntityResult,
    intents: IntentResult,
    url_intel: URLIntelligence,
) -> MessageCategory:
    """
    Derive the canonical message category.

    Priority order (high → low risk):
      phishing > brand_impersonation > credential_request >
      government_notice > subscription_notice > service_notification >
      link_action > account_notice > app_verification >
      otp_delivery > awareness > survey > promotional >
      bank_transaction > transactional > casual > unknown
    """

    # ── Definite phishing ──────────────────────────────────────────────────
    if url_intel.verdict == "malicious":
        return "phishing"

    if intents.credential_request and url_intel.has_link_surface:
        return "phishing"

    # ── Brand impersonation ────────────────────────────────────────────────
    if url_intel.brand_impersonation:
        return "brand_impersonation"

    # ── Credential request (without URL = pure social engineering) ─────────
    # Awareness warnings may mention OTPs/passwords as examples. If they do
    # not include a delivered one-time code or link, keep them in awareness.
    if (
        intents.awareness
        and not intents.has("otp_code_delivery")
        and not url_intel.has_link_surface
    ):
        return "awareness"

    if intents.dangerous_text_request:
        return "credential_request"

    # ── Government notice — intercept before link_action ──────────────────
    # Government messages with URLs (e.g. Ministry of Justice receipt) must
    # not be misclassified as link_action.
    # Guard: OTP code delivery takes priority (e.g. Hajj permit OTP).
    if intents.has("government_notice_context") and not intents.has("otp_code_delivery"):
        return "government_notice"

    # ── Subscription notice — intercept before link_action ────────────────
    if intents.has("subscription_notice_context"):
        return "subscription_notice"

    # ── Service notification — intercept before link_action ───────────────
    if intents.has("service_notification_context"):
        return "service_notification"

    # ── Promotional notice — intercept before link_action ─────────────────
    # Promo messages may carry URLs (e.g. event registration links).
    if intents.has("promotional_context"):
        return "promotional"

    # ── Link action — URL present with account/update intent ──────────────
    if url_intel.has_link_surface and (
        intents.has("account_update") or intents.url_account_action
    ):
        return "link_action"

    # ── Account notice — vague account warning without dangerous request ───
    if (
        intents.has("account_update") or intents.has("ambiguous_financial_notice")
    ) and not intents.dangerous_text_request:
        return "account_notice"

    # ── App verification (WhatsApp, Telegram, etc.) ────────────────────────
    if (
        "whatsapp" in entities.entities
        and intents.has("informational_notification")
        and not intents.dangerous_text_request
        and not url_intel.has_url
    ):
        return "app_verification"

    if intents.has("informational_notification") and (
        "whatsapp" in entities.entities or intents.has("otp_delivery")
    ) and not intents.dangerous_text_request and not url_intel.has_url:
        return "app_verification"

    # ── OTP delivery (code given WITH or WITHOUT do-not-share) ────────────
    if intents.has("otp_delivery") and not intents.dangerous_text_request:
        return "otp_delivery"

    # ── Security awareness message ─────────────────────────────────────────
    if intents.awareness and not intents.dangerous_text_request:
        return "awareness"

    # ── Survey / customer feedback ─────────────────────────────────────────
    if intents.has("survey_context"):
        return "survey"

    # ── Bank/financial transaction notification (backward-compatible) ────────
    if intents.has("bank_transaction") and not intents.dangerous_text_request:
        return "transactional"

    # ── Casual conversation ────────────────────────────────────────────────
    if (
        intents.has("casual")
        and not entities.has_sensitive_entity
        and not entities.has_bank_or_account
        and not url_intel.has_link_surface
    ):
        return "casual"

    return "unknown"
