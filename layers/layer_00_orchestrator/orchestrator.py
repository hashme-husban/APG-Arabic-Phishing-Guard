from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SUPPORTED_CHANNELS = {"sms", "email", "messaging", "unknown"}
CHANNEL_ALIASES = {
    "sms": "sms",
    "text": "sms",
    "mms": "sms",
    "email": "email",
    "mail": "email",
    "gmail": "email",
    "whatsapp": "messaging",
    "telegram": "messaging",
    "messenger": "messaging",
    "instagram": "messaging",
    "notification": "messaging",
    "notifications": "messaging",
    "messaging": "messaging",
}

URL_REGEX = re.compile(r"(?:(?:https?://|www\.)[^\s<>'\"\]\)]+)", re.IGNORECASE)
OBFUSCATED_URL_REGEX = re.compile(
    r"(?:hxxps?://[^\s<>'\"]+|(?:[a-zA-Z0-9-]+\s*\[\.\]\s*)+[a-zA-Z]{2,})",
    re.IGNORECASE,
)
BARE_DOMAIN_REGEX = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|co|xyz|top|site|online|click|live|store|app|dev|info|biz|me|pro|cc|link|shop|bank|sa|jo|eg|uk|de|fr|ru|cn|tr|ae|qa|kw|bh|om|edu|gov)\b(?:/[^\s<>'\"]*)?",
    re.IGNORECASE,
)


@dataclass
class APGInput:
    sender: str = ""
    raw_text: str = ""
    urls: List[str] = field(default_factory=list)
    channel: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    aliases_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class Orchestrator:
    """Layer 00 - Orchestrator / Manager."""

    def __init__(
        self,
        entity_aliases_path: str = "configs/entity_aliases.json",
        sender_verifier: Any = None,
        policy_engine: Any = None,
        normalizer: Any = None,
        text_engine: Any = None,
        url_engine: Any = None,
        fusion_engine: Any = None,
        output_formatter: Any = None,
    ) -> None:
        self.entity_aliases_path = Path(entity_aliases_path)
        self.entity_catalog = self._load_entity_catalog(self.entity_aliases_path)
        self.sender_verifier = sender_verifier
        self.policy_engine = policy_engine
        self.normalizer = normalizer
        self.text_engine = text_engine
        self.url_engine = url_engine
        self.fusion_engine = fusion_engine
        self.output_formatter = output_formatter

    def prepare_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        apg_input = self._build_input(payload)
        extracted_urls = self.extract_urls(apg_input.raw_text)
        merged_urls = self._dedupe_preserve_order((apg_input.urls or []) + extracted_urls)
        url_candidates = self.extract_obfuscated_url_candidates(apg_input.raw_text)
        sender_type = self.detect_sender_type(apg_input.sender)
        claimed_entity = self.infer_claimed_entity(raw_text=apg_input.raw_text, sender=apg_input.sender)

        route_plan = self.build_route_plan(
            sender=apg_input.sender,
            raw_text=apg_input.raw_text,
            urls=merged_urls,
            url_candidates=url_candidates,
            claimed_entity=claimed_entity,
        )

        context = {
            "request_id": self._make_request_id(),
            "received_at": self._now_iso(),
            "input": {
                "sender": apg_input.sender,
                "raw_text": apg_input.raw_text,
                "urls": merged_urls,
                "channel": apg_input.channel,
                "metadata": apg_input.metadata,
                "aliases_used": apg_input.aliases_used,
                "warnings": apg_input.warnings,
            },
            "extracted": {
                "sender_type": sender_type,
                "urls": merged_urls,
                "url_candidates": url_candidates,
                "claimed_entity": claimed_entity,
            },
            "routing": route_plan,
            "layer_results": {},
            "final": None,
            "output": None,
        }
        return context

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        context = self.prepare_context(payload)
        sender_result = self._run_sender_verification(context)
        policy_result = self._run_entity_policy(context, sender_result)
        normalization_result = self._run_normalization(context)
        text_result = self._run_text_intelligence(context, normalization_result)
        url_result = self._run_url_intelligence(context, normalization_result)
        fusion_result = self._run_decision_fusion(
            context=context,
            sender_result=sender_result,
            policy_result=policy_result,
            normalization_result=normalization_result,
            text_result=text_result,
            url_result=url_result,
        )
        explanation_result = self._run_explanation(
            context=context,
            sender_result=sender_result,
            policy_result=policy_result,
            normalization_result=normalization_result,
            text_result=text_result,
            url_result=url_result,
            fusion_result=fusion_result,
        )

        context["layer_results"] = {
            "layer_01_sender_verification": sender_result,
            "layer_02_entity_policy": policy_result,
            "layer_03_normalization": normalization_result,
            "layer_04_text_intelligence": text_result,
            "layer_05_url_intelligence": url_result,
            "layer_06_decision_fusion": fusion_result,
            "layer_07_explanation": explanation_result,
        }
        context["final"] = explanation_result.get("public_result", fusion_result)
        context["output"] = explanation_result
        return context

    def _build_input(self, payload: Dict[str, Any]) -> APGInput:
        payload = payload if isinstance(payload, dict) else {}
        aliases_used: List[str] = []
        warnings: List[str] = []

        sender = self._first_non_empty(payload, ["sender", "from", "sender_name", "display_sender"])
        raw_text = self._first_non_empty(payload, ["raw_text", "message", "text", "body", "content"])
        if sender and "sender" not in payload:
            aliases_used.append("sender_alias")
        if raw_text and "raw_text" not in payload:
            aliases_used.append("raw_text_alias")

        urls_value = payload.get("urls")
        if urls_value is None:
            single_url = self._first_non_empty(payload, ["url", "link", "href"])
            urls_value = [single_url] if single_url else []
            if single_url:
                aliases_used.append("url_alias")

        if not isinstance(urls_value, list):
            urls_value = [urls_value] if urls_value else []

        clean_urls = []
        for item in urls_value:
            value = self._safe_str(item)
            if value:
                clean_urls.append(value)

        metadata = payload.get("metadata", {}) or {}
        if not isinstance(metadata, dict):
            warnings.append("metadata_was_not_a_dict")
            metadata = {}

        channel = self._canonical_channel(payload.get("channel", payload.get("source", "unknown")))

        return APGInput(
            sender=sender,
            raw_text=raw_text,
            urls=self._dedupe_preserve_order(clean_urls),
            channel=channel,
            metadata=metadata,
            aliases_used=aliases_used,
            warnings=warnings,
        )

    def extract_urls(self, text: str) -> List[str]:
        if not text:
            return []
        matches = URL_REGEX.findall(text)
        bare_domains = [m for m in BARE_DOMAIN_REGEX.findall(text) if not m.lower().startswith(("http://", "https://", "www."))]
        cleaned = [self._clean_url_token(m) for m in matches]
        cleaned.extend([self._clean_url_token("http://" + m) for m in bare_domains])
        return self._dedupe_preserve_order([u for u in cleaned if u])

    def extract_obfuscated_url_candidates(self, text: str) -> List[str]:
        if not text:
            return []
        matches = OBFUSCATED_URL_REGEX.findall(text)
        cleaned = [self._normalize_spaces(m) for m in matches]
        exact_urls = set(self.extract_urls(text))
        return self._dedupe_preserve_order([m for m in cleaned if m and m not in exact_urls])

    def detect_sender_type(self, sender: str) -> str:
        sender = sender.strip()
        if not sender:
            return "unknown"
        if re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", sender):
            return "email"
        digits = re.sub(r"\D", "", sender)
        if re.fullmatch(r"\d{3,6}", digits):
            return "short_code"
        if re.fullmatch(r"\d{6,15}", digits):
            return "phone"
        if re.fullmatch(r"(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}", sender.lower()):
            return "domain"
        return "display_name"

    def infer_claimed_entity(self, raw_text: str, sender: str) -> Optional[Dict[str, Any]]:
        if not self.entity_catalog:
            return None

        haystack = self._normalize_for_lookup(f"{sender} {raw_text}")
        best_match: Optional[Dict[str, Any]] = None
        best_alias_length = 0

        for entity in self.entity_catalog:
            aliases = entity.get("aliases", [])
            for alias in aliases:
                alias_norm = self._normalize_for_lookup(alias)
                if not alias_norm:
                    continue
                if alias_norm in haystack:
                    alias_length = len(alias_norm)
                    if alias_length > best_alias_length:
                        best_alias_length = alias_length
                        best_match = {
                            "entity_id": entity.get("entity_id"),
                            "display_name": entity.get("display_name"),
                            "sector": entity.get("sector"),
                            "matched_alias": alias,
                            "confidence": round(min(0.99, 0.55 + alias_length / 100), 2),
                        }
        return best_match

    def build_route_plan(
        self,
        sender: str,
        raw_text: str,
        urls: List[str],
        url_candidates: List[str],
        claimed_entity: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "run_layer_01_sender_verification": bool(sender),
            "run_layer_02_entity_policy": bool(claimed_entity or raw_text),
            "run_layer_03_normalization": bool(raw_text),
            "run_layer_04_text_intelligence": bool(raw_text),
            "run_layer_05_url_intelligence": bool(urls or url_candidates),
            "run_layer_06_decision_fusion": True,
            "notes": {
                "has_sender": bool(sender),
                "has_text": bool(raw_text),
                "has_urls": bool(urls),
                "has_obfuscated_url_candidates": bool(url_candidates),
                "has_claimed_entity": bool(claimed_entity),
            },
        }

    def _run_sender_verification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        sender = context["input"]["sender"]
        claimed_entity = context["extracted"]["claimed_entity"]
        if self.sender_verifier and hasattr(self.sender_verifier, "evaluate"):
            try:
                return self.sender_verifier.evaluate(sender=sender, claimed_entity=claimed_entity, context=context)
            except Exception as exc:
                logger.exception("Layer 01 failed: %s", exc)
                return self._default_sender_result(error=str(exc))
        return self._default_sender_result()

    def _run_entity_policy(self, context: Dict[str, Any], sender_result: Dict[str, Any]) -> Dict[str, Any]:
        raw_text = context["input"]["raw_text"]
        claimed_entity = context["extracted"]["claimed_entity"]
        if self.policy_engine and hasattr(self.policy_engine, "evaluate"):
            try:
                return self.policy_engine.evaluate(
                    raw_text=raw_text,
                    claimed_entity=claimed_entity,
                    sender_result=sender_result,
                    context=context,
                )
            except Exception as exc:
                logger.exception("Layer 02 failed: %s", exc)
                return self._default_policy_result(error=str(exc))
        return self._default_policy_result()

    def _run_normalization(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raw_text = context["input"]["raw_text"]
        urls = context["input"]["urls"]
        if self.normalizer and hasattr(self.normalizer, "process"):
            try:
                return self.normalizer.process(raw_text=raw_text, urls=urls, context=context)
            except Exception as exc:
                logger.exception("Layer 03 failed: %s", exc)
                return self._default_normalization_result(raw_text=raw_text, error=str(exc))
        return self._default_normalization_result(raw_text=raw_text)

    def _run_text_intelligence(self, context: Dict[str, Any], normalization_result: Dict[str, Any]) -> Dict[str, Any]:
        raw_text = context["input"]["raw_text"]
        normalized_text = normalization_result.get("normalized_text", raw_text)
        if self.text_engine and hasattr(self.text_engine, "evaluate"):
            try:
                return self.text_engine.evaluate(raw_text=raw_text, normalized_text=normalized_text, context=context)
            except Exception as exc:
                logger.exception("Layer 04 failed: %s", exc)
                return self._default_text_result(error=str(exc))
        return self._default_text_result()

    def _run_url_intelligence(self, context: Dict[str, Any], normalization_result: Dict[str, Any]) -> Dict[str, Any]:
        urls = context["input"]["urls"]
        url_candidates = context["extracted"]["url_candidates"]
        claimed_entity = context["extracted"]["claimed_entity"]
        recovered_urls = normalization_result.get("recovered_urls", [])
        merged_urls = self._dedupe_preserve_order(urls + recovered_urls)
        if self.url_engine and hasattr(self.url_engine, "evaluate"):
            try:
                return self.url_engine.evaluate(urls=merged_urls, url_candidates=url_candidates, claimed_entity=claimed_entity, context=context)
            except Exception as exc:
                logger.exception("Layer 05 failed: %s", exc)
                return self._default_url_result(error=str(exc), urls=merged_urls)
        return self._default_url_result(urls=merged_urls)

    def _run_decision_fusion(
        self,
        context: Dict[str, Any],
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        normalization_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.fusion_engine and hasattr(self.fusion_engine, "evaluate"):
            try:
                return self.fusion_engine.evaluate(
                    sender_result=sender_result,
                    policy_result=policy_result,
                    normalization_result=normalization_result,
                    text_result=text_result,
                    url_result=url_result,
                    context=context,
                )
            except Exception as exc:
                logger.exception("Layer 06 failed: %s", exc)
                return self._default_fusion_result(error=str(exc))
        return self._default_fusion_result()

    def _run_explanation(
        self,
        context: Dict[str, Any],
        sender_result: Dict[str, Any],
        policy_result: Dict[str, Any],
        normalization_result: Dict[str, Any],
        text_result: Dict[str, Any],
        url_result: Dict[str, Any],
        fusion_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.output_formatter and hasattr(self.output_formatter, "evaluate"):
            try:
                return self.output_formatter.evaluate(
                    final_result=fusion_result,
                    sender_result=sender_result,
                    policy_result=policy_result,
                    normalization_result=normalization_result,
                    text_result=text_result,
                    url_result=url_result,
                    context=context,
                )
            except Exception as exc:
                logger.exception("Layer 07 failed: %s", exc)
                return self._default_output_result(fusion_result=fusion_result, error=str(exc))
        return self._default_output_result(fusion_result=fusion_result)

    def _default_sender_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "sender_status": "not_evaluated" if not error else "error",
            "sender_score": None,
            "matched_entity": None,
            "sender_reasons": ["Layer 01 is not connected yet."] if not error else [error],
        }

    def _default_policy_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "policy_status": "not_evaluated" if not error else "error",
            "policy_score": None,
            "policy_flags": [],
            "policy_reasons": ["Layer 02 is not connected yet."] if not error else [error],
        }

    def _default_normalization_result(self, raw_text: str, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "normalized_text": raw_text,
            "noise_score": None,
            "typo_score": None,
            "repair_actions": [],
            "recovered_urls": [],
            "normalization_reasons": ["Layer 03 is not connected yet."] if not error else [error],
        }

    def _default_text_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "semantic_score": None,
            "lexical_score": None,
            "heuristic_score": 0.5,
            "text_score": None,
            "text_label": "not_evaluated" if not error else "error",
            "text_reasons": ["Layer 04 is not connected yet."] if not error else [error],
        }

    def _default_url_result(self, error: Optional[str] = None, urls: Optional[List[str]] = None) -> Dict[str, Any]:
        urls = urls or []
        return {
            "url_score": None,
            "url_label": "absent" if not urls else ("not_evaluated" if not error else "error"),
            "url_flags": [],
            "url_reasons": ["No URL found in request."] if not urls else (["Layer 05 is not connected yet."] if not error else [error]),
            "analyzed_urls": urls,
        }

    def _default_fusion_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "final_score": None,
            "final_label": "pending" if not error else "error",
            "confidence": 0.0,
            "final_reasons": ["Layer 06 is not connected yet."] if not error else [error],
            "recommendation": "Pipeline is not fully connected yet.",
        }

    def _default_output_result(self, fusion_result: Dict[str, Any], error: Optional[str] = None) -> Dict[str, Any]:
        if error:
            return {
                "public_result": {
                    "final_label": "error",
                    "final_score": None,
                    "confidence": 0.0,
                    "headline": "Output formatting failed",
                    "summary": error,
                    "reasons": [error],
                    "recommendation": "Check Layer 07 configuration.",
                    "action_items": [],
                    "risk_badges": [],
                    "layer_breakdown": {},
                },
                "mobile_result": {
                    "label": "error",
                    "score": None,
                    "confidence": 0.0,
                    "headline": "Output formatting failed",
                    "short_summary": error,
                    "top_reasons": [error],
                    "action_items": [],
                    "badges": [],
                },
                "debug_result": {"error": error},
            }
        return {"public_result": fusion_result, "mobile_result": fusion_result, "debug_result": {"note": "Layer 07 is not connected yet."}}

    def _load_entity_catalog(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            logger.warning("Entity alias config not found: %s", path)
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            entities = data.get("entities", [])
            return entities if isinstance(entities, list) else []
        except Exception as exc:
            logger.exception("Failed to load entity alias config: %s", exc)
            return []

    def _make_request_id(self) -> str:
        return uuid.uuid4().hex

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _first_non_empty(self, payload: Dict[str, Any], keys: List[str]) -> str:
        for key in keys:
            value = self._safe_str(payload.get(key))
            if value:
                return value
        return ""

    def _canonical_channel(self, value: Any) -> str:
        value = self._safe_str(value).lower()
        if value in SUPPORTED_CHANNELS:
            return value
        return CHANNEL_ALIASES.get(value, "unknown")

    def _clean_url_token(self, url: str) -> str:
        url = self._normalize_spaces(url)
        url = url.rstrip(".,;!?)]]}")
        return url

    def _normalize_spaces(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _dedupe_preserve_order(self, items: List[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _normalize_for_lookup(self, text: str) -> str:
        text = self._safe_str(text).lower()
        replacements = {
            "أ": "ا",
            "إ": "ا",
            "آ": "ا",
            "ى": "ي",
            "ؤ": "و",
            "ئ": "ي",
            "ة": "ه",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = re.sub(r"[^\w\s@.+-]", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()
        return text
