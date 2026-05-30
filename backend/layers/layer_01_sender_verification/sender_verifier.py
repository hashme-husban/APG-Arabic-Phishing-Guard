from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional


class SenderVerifier:
    """Layer 01 — Sender Verification with stronger impersonation checks."""

    DEFAULT_CONFIG = {
        "free_email_domains": [],
        "sensitive_sectors": ["bank", "government", "wallet", "payment"],
        "risky_sender_tokens": ["verify", "secure", "update", "alert", "support", "help", "login", "otp"],
        "risk_scores": {
            "trusted_exact": 0.03,
            "trusted_domain": 0.08,
            "trusted_phone": 0.08,
            "trusted_shortcode": 0.10,
            "unknown": 0.45,
            "unknown_sensitive": 0.60,
            "display_alias_only": 0.78,
            "free_email_sensitive_claim": 0.85,
            "hard_claim_conflict": 0.92,
            "soft_claim_conflict": 0.88,
            "lookalike_domain": 0.84,
            "brand_impersonation": 0.81,
            "risky_display_sender": 0.68,
        },
    }

    EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})$")
    DOMAIN_REGEX = re.compile(r"^(?:www\.)?([A-Za-z0-9.-]+\.[A-Za-z]{2,})$")
    SHORTCODE_REGEX = re.compile(r"^\d{3,6}$")
    PHONE_REGEX = re.compile(r"^\+?\d{6,15}$")

    def __init__(self, registry_path: str = "configs/sender_registry.json", config_path: str = "configs/sender_layer_config.json") -> None:
        self.registry_path = Path(registry_path)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.entities = self._load_registry()
        self.free_email_domains = {str(x).lower() for x in self.config.get("free_email_domains", [])}
        self.sensitive_sectors = {str(x).lower() for x in self.config.get("sensitive_sectors", [])}
        self.risky_sender_tokens = {str(x).lower() for x in self.config.get("risky_sender_tokens", [])}
        self.risk_scores = self.config.get("risk_scores", {})

    def evaluate(
        self,
        sender: str,
        claimed_entity: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sender = self._safe_str(sender)
        claimed_entity = claimed_entity or {}
        claimed_entity_id = claimed_entity.get("entity_id")
        claimed_entity_name = claimed_entity.get("display_name")
        claimed_sector = str(claimed_entity.get("sector", "")).strip().lower()

        if not sender:
            return {
                "sender_status": "unknown",
                "sender_score": self._risk("unknown", 0.45),
                "matched_entity": None,
                "sender_reasons": ["No sender value was provided."],
                "sender_flags": [],
                "sender_details": {
                    "sender_type": "unknown",
                    "normalized_sender": "",
                    "match_mode": None,
                },
            }

        sender_info = self._parse_sender(sender)
        hard_matches = self._find_hard_matches(sender_info)
        soft_matches = self._find_soft_alias_matches(sender_info)
        lookalike_match = self._find_lookalike_domain(sender_info, claimed_entity)
        impersonation_hint = self._detect_claim_brand_impersonation(sender_info, claimed_entity)

        best_hard = hard_matches[0] if hard_matches else None
        best_soft = soft_matches[0] if soft_matches else None

        reasons: List[str] = []
        flags: List[str] = []
        sender_status = "unknown"
        sender_score = self._risk("unknown", 0.45)
        matched_entity = None
        match_mode = None

        if best_hard:
            matched_entity = self._entity_summary(best_hard["entity"])
            match_mode = best_hard["match_mode"]
            reasons.append(best_hard["reason"])
            if claimed_entity_id and best_hard["entity"].get("entity_id") != claimed_entity_id:
                sender_status = "spoof_suspected"
                sender_score = self._risk("hard_claim_conflict", 0.92)
                reasons.append(
                    f"Sender matches official records for {best_hard['entity']['display_name']}, but the message claims {claimed_entity_name or claimed_entity_id}."
                )
                flags.append("CLAIM_CONFLICT")
            else:
                sender_status = "trusted"
                if best_hard["match_mode"] == "official_email_exact":
                    sender_score = self._risk("trusted_exact", 0.03)
                elif best_hard["match_mode"] == "official_domain_exact":
                    sender_score = self._risk("trusted_domain", 0.08)
                elif best_hard["match_mode"] == "official_phone_exact":
                    sender_score = self._risk("trusted_phone", 0.08)
                elif best_hard["match_mode"] == "official_shortcode_exact":
                    sender_score = self._risk("trusted_shortcode", 0.10)
                else:
                    sender_score = self._risk("trusted_domain", 0.08)
                reasons.append("Sender identity matches a trusted local registry entry.")
                flags.append("TRUSTED_MATCH")

        elif lookalike_match:
            sender_status = "spoof_suspected"
            sender_score = self._risk("lookalike_domain", 0.84)
            reasons.append(lookalike_match["reason"])
            flags.extend(["LOOKALIKE_DOMAIN", "BRAND_IMPERSONATION"])
            matched_entity = self._entity_summary(lookalike_match["entity"])
            match_mode = "lookalike_domain"

        elif impersonation_hint:
            sender_status = "spoof_suspected"
            sender_score = self._risk("brand_impersonation", 0.81)
            reasons.extend(impersonation_hint["reasons"])
            flags.extend(impersonation_hint["flags"])
            match_mode = "claim_brand_impersonation"

        elif best_soft:
            matched_entity = self._entity_summary(best_soft["entity"])
            match_mode = best_soft["match_mode"]
            reasons.append(best_soft["reason"])
            if claimed_entity_id and best_soft["entity"].get("entity_id") != claimed_entity_id:
                sender_status = "spoof_suspected"
                sender_score = self._risk("soft_claim_conflict", 0.88)
                reasons.append(
                    f"Sender naming resembles {best_soft['entity']['display_name']}, but the message claims {claimed_entity_name or claimed_entity_id}."
                )
                flags.append("CLAIM_CONFLICT")
            else:
                sender_status = "spoof_suspected"
                sender_score = self._risk("display_alias_only", 0.78)
                reasons.append("Sender resembles a known entity by name, but no official sender proof was found.")
                flags.append("DISPLAY_ALIAS_ONLY")

        else:
            sender_status = "unknown"
            sender_score = self._risk("unknown", 0.45)
            if sender_info["sender_type"] == "email":
                email_domain = sender_info.get("email_domain", "")
                if email_domain in self.free_email_domains and claimed_sector in self.sensitive_sectors:
                    sender_status = "spoof_suspected"
                    sender_score = self._risk("free_email_sensitive_claim", 0.85)
                    reasons.append(
                        f"Sender uses a free email domain ({email_domain}) while claiming a sensitive sector ({claimed_sector})."
                    )
                    flags.append("FREE_EMAIL_SENSITIVE_CLAIM")
                else:
                    reasons.append("Email sender is not present in the trusted local registry.")
            elif sender_info["sender_type"] in {"phone", "short_code"}:
                if claimed_sector in self.sensitive_sectors:
                    sender_score = self._risk("unknown_sensitive", 0.60)
                    reasons.append(
                        f"Numeric sender is unknown and the claimed entity belongs to a sensitive sector ({claimed_sector})."
                    )
                    flags.append("UNKNOWN_SENSITIVE_SENDER")
                else:
                    reasons.append("Numeric sender is not present in the trusted local registry.")
            elif sender_info["sender_type"] == "domain":
                reasons.append("Sender domain is not present in the trusted local registry.")
            else:
                reasons.append("Sender display name does not match any trusted local registry record.")

        if sender_info["sender_type"] == "display_name" and self._has_risky_sender_tokens(sender_info["normalized_sender"]):
            sender_score = max(sender_score, self._risk("risky_display_sender", 0.68))
            sender_status = "spoof_suspected" if sender_status == "unknown" else sender_status
            flags.append("RISKY_DISPLAY_TOKENS")
            reasons.append("The sender name uses security-style or verification-style wording that is common in phishing messages.")

        return {
            "sender_status": sender_status,
            "sender_score": round(float(sender_score), 6),
            "matched_entity": matched_entity,
            "sender_reasons": self._dedupe(reasons)[:8],
            "sender_flags": self._dedupe(flags),
            "sender_details": {
                "sender_type": sender_info["sender_type"],
                "normalized_sender": sender_info["normalized_sender"],
                "email_domain": sender_info.get("email_domain"),
                "is_free_email_domain": sender_info.get("email_domain") in self.free_email_domains,
                "claimed_entity_id": claimed_entity_id,
                "claimed_sector": claimed_sector,
                "match_mode": match_mode,
            },
        }

    def _find_hard_matches(self, sender_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        matches = []
        for entity in self.entities:
            display_name = entity.get("display_name", entity.get("entity_id"))
            official_emails = {self._safe_str(x).lower() for x in entity.get("official_emails", [])}
            official_domains = {self._normalize_domain(x) for x in entity.get("official_domains", []) if x}
            official_phones = {self._normalize_phone(x) for x in entity.get("official_phones", []) if x}
            official_shortcodes = {self._safe_str(x) for x in entity.get("official_short_codes", []) if x}

            if sender_info["sender_type"] == "email":
                if sender_info["normalized_sender"] in official_emails:
                    matches.append({
                        "entity": entity,
                        "confidence": 1.0,
                        "match_mode": "official_email_exact",
                        "reason": f"Sender exactly matches an official email for {display_name}.",
                    })
                email_domain = sender_info.get("email_domain")
                if email_domain:
                    for domain in official_domains:
                        if email_domain == domain or email_domain.endswith("." + domain):
                            matches.append({
                                "entity": entity,
                                "confidence": 0.92,
                                "match_mode": "official_domain_exact",
                                "reason": f"Sender email domain matches an official domain for {display_name}.",
                            })
                            break

            if sender_info["sender_type"] == "domain":
                sender_domain = sender_info.get("domain_value", "")
                for domain in official_domains:
                    if sender_domain == domain or sender_domain.endswith("." + domain):
                        matches.append({
                            "entity": entity,
                            "confidence": 0.90,
                            "match_mode": "official_domain_exact",
                            "reason": f"Sender domain matches an official domain for {display_name}.",
                        })
                        break

            if sender_info["sender_type"] == "phone" and sender_info["digits"] in official_phones:
                matches.append({
                    "entity": entity,
                    "confidence": 0.95,
                    "match_mode": "official_phone_exact",
                    "reason": f"Sender phone number matches an official phone for {display_name}.",
                })

            if sender_info["sender_type"] == "short_code" and sender_info["normalized_sender"] in official_shortcodes:
                matches.append({
                    "entity": entity,
                    "confidence": 0.94,
                    "match_mode": "official_shortcode_exact",
                    "reason": f"Sender short code matches an official short code for {display_name}.",
                })

        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches

    def _find_soft_alias_matches(self, sender_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        matches = []
        if sender_info["sender_type"] not in {"display_name", "domain", "email"}:
            return matches

        haystack = self._normalize_text(sender_info["normalized_sender"])
        email_domain = self._normalize_text(sender_info.get("email_domain", ""))
        for entity in self.entities:
            display_name = entity.get("display_name", entity.get("entity_id"))
            aliases = entity.get("display_aliases", [])
            for alias in aliases:
                alias_norm = self._normalize_text(alias)
                if alias_norm and (alias_norm in haystack or (email_domain and alias_norm in email_domain)):
                    matches.append({
                        "entity": entity,
                        "confidence": min(0.80, 0.55 + (len(alias_norm) / 100.0)),
                        "match_mode": "display_alias_only",
                        "reason": f"Sender naming resembles known alias '{alias}' for {display_name}.",
                    })
                    break
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches

    def _find_lookalike_domain(self, sender_info: Dict[str, Any], claimed_entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        domain = sender_info.get("email_domain") or sender_info.get("domain_value")
        if not domain:
            return None

        candidates = []
        if claimed_entity.get("entity_id"):
            for entity in self.entities:
                if entity.get("entity_id") == claimed_entity.get("entity_id"):
                    candidates.append(entity)
                    break
        if not candidates:
            candidates = self.entities

        for entity in candidates:
            official_domains = {self._normalize_domain(x) for x in entity.get("official_domains", []) if x}
            for official in official_domains:
                similarity = SequenceMatcher(None, domain, official).ratio()
                if official != domain and similarity >= 0.84:
                    return {
                        "entity": entity,
                        "reason": f"Sender domain '{domain}' closely resembles official domain '{official}', which is a common spoofing pattern.",
                    }
        return None

    def _detect_claim_brand_impersonation(self, sender_info: Dict[str, Any], claimed_entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not claimed_entity:
            return None
        aliases = [claimed_entity.get("display_name", ""), claimed_entity.get("matched_alias", "")]
        alias_tokens = [self._normalize_text(a) for a in aliases if a]
        alias_tokens = [a for a in alias_tokens if len(a) >= 3]
        if not alias_tokens:
            return None

        haystacks = [
            self._normalize_text(sender_info.get("normalized_sender", "")),
            self._normalize_text(sender_info.get("email_domain", "")),
            self._normalize_text(sender_info.get("domain_value", "")),
        ]
        joined = " ".join([h for h in haystacks if h])
        if not joined:
            return None

        matched_alias = next((token for token in alias_tokens if token in joined), None)
        if not matched_alias:
            return None

        reasons = ["Sender references the claimed brand or entity name, but no official sender proof was found."]
        flags = ["CLAIM_BRAND_IN_SENDER"]
        if self._has_risky_sender_tokens(joined):
            reasons.append("The sender also uses verification or security wording around the claimed brand.")
            flags.append("RISKY_BRAND_TOKENS")
        return {"reasons": reasons, "flags": flags}

    def _parse_sender(self, sender: str) -> Dict[str, Any]:
        sender = self._safe_str(sender)
        normalized_sender = sender.lower()
        email_match = self.EMAIL_REGEX.fullmatch(sender)
        if email_match:
            email_domain = self._normalize_domain(email_match.group(1))
            return {
                "sender_type": "email",
                "raw_sender": sender,
                "normalized_sender": normalized_sender,
                "email_domain": email_domain,
                "digits": None,
                "domain_value": None,
            }

        digits = self._normalize_phone(sender)
        if self.SHORTCODE_REGEX.fullmatch(digits):
            return {
                "sender_type": "short_code",
                "raw_sender": sender,
                "normalized_sender": digits,
                "email_domain": None,
                "digits": digits,
                "domain_value": None,
            }
        if self.PHONE_REGEX.fullmatch(digits):
            return {
                "sender_type": "phone",
                "raw_sender": sender,
                "normalized_sender": digits,
                "email_domain": None,
                "digits": digits,
                "domain_value": None,
            }

        domain_match = self.DOMAIN_REGEX.fullmatch(sender.lower())
        if domain_match:
            domain_value = self._normalize_domain(domain_match.group(1))
            return {
                "sender_type": "domain",
                "raw_sender": sender,
                "normalized_sender": normalized_sender,
                "email_domain": None,
                "digits": None,
                "domain_value": domain_value,
            }

        return {
            "sender_type": "display_name",
            "raw_sender": sender,
            "normalized_sender": normalized_sender,
            "email_domain": None,
            "digits": digits if digits else None,
            "domain_value": None,
        }

    def _load_config(self) -> Dict[str, Any]:
        config = json.loads(json.dumps(self.DEFAULT_CONFIG))
        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    for k, v in loaded.items():
                        if k == "risk_scores" and isinstance(v, dict):
                            config["risk_scores"].update(v)
                        else:
                            config[k] = v
            except Exception:
                pass
        return config

    def _load_registry(self) -> List[Dict[str, Any]]:
        if not self.registry_path.exists():
            return []
        try:
            with self.registry_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            entities = data.get("entities", [])
            return entities if isinstance(entities, list) else []
        except Exception:
            return []

    def _risk(self, key: str, default: float) -> float:
        try:
            return float(self.risk_scores.get(key, default))
        except Exception:
            return default

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_phone(self, value: str) -> str:
        return re.sub(r"\D", "", self._safe_str(value))

    def _normalize_domain(self, value: str) -> str:
        value = self._safe_str(value).lower()
        value = re.sub(r"^https?://", "", value)
        value = re.sub(r"^www\.", "", value)
        return value.strip("/")

    def _normalize_text(self, text: str) -> str:
        text = self._safe_str(text).lower()
        replacements = {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"}
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = re.sub(r"[^\w\s@.+-]", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _has_risky_sender_tokens(self, text: str) -> bool:
        haystack = self._normalize_text(text)
        return any(token in haystack for token in self.risky_sender_tokens)

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _entity_summary(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entity_id": entity.get("entity_id"),
            "display_name": entity.get("display_name"),
            "sector": entity.get("sector"),
        }
