"""
APG Risk Intelligence Engine v1 — Entity Extractor

Two classes live here:

EntityExtractorAdapter
    Wraps the v5 EntityExtractor (pattern-based signals, URL extraction).
    Used throughout the existing risk engine pipeline.

ClaimedEntityExtractor
    Uses the EntityRegistry (jo_entities.json) to identify *which* known
    organisation a message is claiming to represent.
    Priority: sender_name > URL domain > message text.
    Produces a structured intelligence dict consumed by the debug layer.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.analyzer.entities import EntityExtractor as _EntityExtractor
from app.services.analyzer.schemas import EntityResult
from app.services.entity_registry import _no_match, _strip_domain, get_registry


_PROMO_DISCOUNT_TERMS = (
    "خصم",
    "تخفيض",
    "تخفيضات",
    "عرض",
    "عروض",
    "كوبون",
    "كود خصم",
    "وفر",
    "وفر اكثر",
    "وفّر",
    "وفّر اكثر",
    "خصومات",
    "تنزيلات",
    "sale",
    "discount",
    "promo",
    "coupon",
)

_TRUE_FINANCIAL_RISK_TERMS = (
    "دفع",
    "ادفع",
    "سداد",
    "سدد",
    "رسوم",
    "مستحقات",
    "مبلغ مستحق",
    "فاتوره",
    "فاتورة",
    "غرامه",
    "غرامة",
    "ضريبه",
    "ضريبة",
    "جمرك",
    "جمارك",
    "تحويل",
    "حواله",
    "حوالة",
    "محفظه",
    "محفظة",
    "بطاقه",
    "بطاقة",
    "cvv",
    "cvc",
    "pin",
    "iban",
    "حساب بنكي",
    "حسابك البنكي",
    "البنك",
    "بنك",
    "رصيد",
    "شحن رصيد",
    "payment",
    "fee",
    "invoice",
    "wallet",
    "card",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term and term in text for term in terms)


def _is_promo_only_money_context(normalized: str, entities: set[str]) -> bool:
    """
    Return True when the legacy money_transaction hit came only from
    promotional discount language, not actual payment/account context.
    """
    if "money_transaction" not in entities:
        return False
    if entities & {"bank", "account", "card", "cvv", "iban"}:
        return False
    if not _contains_any(normalized, _PROMO_DISCOUNT_TERMS):
        return False
    return not _contains_any(normalized, _TRUE_FINANCIAL_RISK_TERMS)


class EntityExtractorAdapter:
    """
    Adapter around the v5 EntityExtractor.

    Returns the existing EntityResult (no new type introduced) because all
    downstream components already know how to read it, and we don't want to
    duplicate the proven detection logic.
    """

    def __init__(self) -> None:
        self._inner = _EntityExtractor()

    def extract(
        self,
        raw_text: str,
        normalized: str,
        *,
        source: str = "manual",
        sender: str = "",
        sender_name: str = "",
        package_name: str = "",
        source_app: str = "",
        extra_urls: list[str] | None = None,
        is_known_contact: bool | None = None,
        sender_trust: str = "unknown",
    ) -> tuple[EntityResult, list[Any]]:
        """
        Returns (EntityResult, raw_signals_from_v5).

        The raw_signals list is kept for building Evidence later; it holds
        app.services.analyzer.schemas.Signal objects from the v5 analyzer.
        """
        entities, signals = self._inner.extract(
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
        if _is_promo_only_money_context(normalized or "", entities.entities):
            entities.entities.discard("money_transaction")
            signals = [
                signal
                for signal in signals
                if getattr(signal, "name", "") != "entity_money_transaction"
            ]
        return entities, signals


# ─── URL domain extractor (lightweight — no network calls) ────────────────────

_URL_RE = re.compile(
    r"https?://([A-Za-z0-9\-._~:@!$&'()*+,;=]+?)(?:/|\?|#|$)",
    re.IGNORECASE,
)


def _extract_domains(text: str, extra_urls: list[str] | None = None) -> list[str]:
    """Pull bare domains from inline URLs and any pre-extracted URL list."""
    domains: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        d = _strip_domain(m.group(1))
        if d and d not in domains:
            domains.append(d)
    for url in (extra_urls or []):
        m = _URL_RE.match((url or "").strip())
        if m:
            d = _strip_domain(m.group(1))
            if d and d not in domains:
                domains.append(d)
    return domains


# ─── Claimed Entity Extractor ─────────────────────────────────────────────────

class ClaimedEntityExtractor:
    """
    Identifies the *claimed* organisational identity in a message using
    the EntityRegistry (jo_entities.json).

    Lookup priority (higher wins):
      1. sender_name  → find_entity_by_sender   (confidence ×1.0)
      2. URL domains  → find_entity_by_domain   (confidence ×0.9)
      3. message text → find_entity_by_alias    (confidence ×0.7)

    Conflict: sender and domain point to *different* known entities.
    """

    def __init__(self) -> None:
        self._registry = get_registry()

    def extract(
        self,
        text: str = "",
        sender_name: str = "",
        extra_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Return entity intelligence dict:

        {
          "claimed_entity":  {...} | None,   # best overall match
          "sender_entity":   {...} | None,
          "domain_entity":   {...} | None,
          "alias_entity":    {...} | None,
          "confidence":      float,
          "entity_conflict": bool,
        }
        """
        sender_result: dict[str, Any] = _no_match()
        domain_result: dict[str, Any] = _no_match()
        alias_result: dict[str, Any] = _no_match()
        domain_candidates: list[dict[str, Any]] = []

        # 1. Sender name (highest priority)
        if sender_name and sender_name.strip():
            sender_result = self._registry.find_entity_by_sender(sender_name.strip())

        # 2. URL domains extracted from text + extra_urls
        domains = _extract_domains(text, extra_urls)
        for domain in domains:
            candidates = self._registry.find_entities_by_domain(domain)
            for candidate in candidates:
                if not any(existing["entity_id"] == candidate["entity_id"] for existing in domain_candidates):
                    domain_candidates.append(candidate)
            r = candidates[0] if candidates else self._registry.find_entity_by_domain(domain)
            if r["matched"] and r["confidence"] > domain_result.get("confidence", 0.0):
                domain_result = r

        # 3. Message text alias scan (lowest priority)
        if text and text.strip():
            alias_result = self._registry.find_entity_by_alias(text.strip())

        domain_candidate_ids = {
            candidate["entity_id"]
            for candidate in domain_candidates
            if candidate.get("entity_id")
        }
        if sender_result["matched"] and sender_result["entity_id"] in domain_candidate_ids:
            domain_result = next(
                candidate
                for candidate in domain_candidates
                if candidate["entity_id"] == sender_result["entity_id"]
            )
        elif alias_result["matched"] and alias_result["entity_id"] in domain_candidate_ids:
            domain_result = next(
                candidate
                for candidate in domain_candidates
                if candidate["entity_id"] == alias_result["entity_id"]
            )

        # Best claimed entity by priority
        if sender_result["matched"]:
            claimed = sender_result
        elif domain_result["matched"]:
            claimed = domain_result
        elif alias_result["matched"]:
            claimed = alias_result
        else:
            claimed = _no_match()

        # Conflict type A: sender and URL domain point to different known entities
        domain_conflict = (
            sender_result["matched"]
            and domain_result["matched"]
            and sender_result["entity_id"] not in (domain_candidate_ids or {domain_result["entity_id"]})
        )
        # Conflict type B: sender and message text alias point to different entities
        alias_conflict = (
            sender_result["matched"]
            and alias_result["matched"]
            and sender_result["entity_id"] != alias_result["entity_id"]
        )
        entity_conflict = domain_conflict or alias_conflict

        return {
            "claimed_entity": claimed if claimed["matched"] else None,
            "sender_entity": sender_result if sender_result["matched"] else None,
            "domain_entity": domain_result if domain_result["matched"] else None,
            "domain_entities": domain_candidates,
            "domain_entity_ids": sorted(domain_candidate_ids),
            "alias_entity": alias_result if alias_result["matched"] else None,
            "confidence": round(claimed.get("confidence", 0.0), 4),
            "entity_conflict": entity_conflict,
            "domain_conflict": domain_conflict,
            "alias_conflict": alias_conflict,
        }
