from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class URLRulesEngine:
    DEFAULT_CONFIG = {"safe_max": 0.30, "phishing_min": 0.72, "weights": {}}

    def __init__(self, config_path: str = "configs/url_layer_config.json") -> None:
        self.config = dict(self.DEFAULT_CONFIG)
        path = Path(config_path)
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.config.update(loaded)
            except Exception:
                pass
        self.weights = self.config.get("weights", {})

    def _w(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.weights.get(key, default))
        except Exception:
            return default

    def _label_from_score(self, score: float) -> str:
        safe_max = float(self.config.get("safe_max", 0.30))
        phishing_min = float(self.config.get("phishing_min", 0.72))
        if score >= phishing_min:
            return "phishing"
        if score <= safe_max:
            return "safe"
        return "suspicious"

    def evaluate(
        self,
        canonical_info: Dict[str, Any],
        features: Dict[str, Any],
        claimed_entity: Dict[str, Any] | None = None,
        url_count: int = 1,
    ) -> Dict[str, Any]:
        score = 0.0
        flags: List[str] = []
        reasons: List[str] = []

        def add(flag: str, weight: float, reason: str) -> None:
            nonlocal score
            if flag not in flags:
                flags.append(flag)
                score += weight
                reasons.append(reason)

        if features.get("was_obfuscated"):
            add("OBFUSCATED_INPUT", self._w("OBFUSCATED_INPUT", 0.22), "The URL appears to have been intentionally obfuscated before analysis.")
        if features.get("insecure_http"):
            add("INSECURE_HTTP", self._w("INSECURE_HTTP", 0.08), "The URL uses HTTP instead of HTTPS.")
        if features.get("has_credentials") or features.get("has_at_symbol"):
            add("CREDENTIALS_OR_AT_SYMBOL", self._w("CREDENTIALS_OR_AT_SYMBOL", 0.16), "The URL contains credentials or '@', which can hide the real destination.")
        if features.get("has_ip"):
            add("IP_LITERAL", self._w("IP_LITERAL", 0.22), "The URL uses an IP address instead of a normal domain name.")
        if features.get("ip_is_private") or features.get("ip_is_loopback") or features.get("ip_is_reserved") or features.get("ip_is_link_local"):
            add("PRIVATE_OR_INTERNAL_IP", self._w("PRIVATE_OR_INTERNAL_IP", 0.26), "The URL points to a private, loopback, reserved, or link-local IP address.")
        if features.get("has_punycode") or features.get("had_unicode_host"):
            add("PUNYCODE_OR_IDN", self._w("PUNYCODE_OR_IDN", 0.18), "The hostname uses internationalized or punycode-style encoding.")
        if features.get("host_mixed_script"):
            add("MIXED_SCRIPT_HOST", self._w("MIXED_SCRIPT_HOST", 0.12), "The hostname mixes scripts, which is risky for phishing lookalikes.")
        if features.get("too_many_subdomains"):
            add("TOO_MANY_SUBDOMAINS", self._w("TOO_MANY_SUBDOMAINS", 0.12), "The URL has many subdomains, which can be used to mimic trusted brands.")
        if features.get("excessive_length"):
            add("EXCESSIVE_LENGTH", self._w("EXCESSIVE_LENGTH", 0.10), "The URL is unusually long.")
        if int(features.get("suspicious_keyword_count", 0)) > 0:
            matched = ", ".join(features.get("matched_suspicious_keywords", [])[:4])
            add("SUSPICIOUS_KEYWORDS", self._w("SUSPICIOUS_KEYWORDS", 0.10), f"The URL contains phishing-related keywords ({matched})." if matched else "The URL contains phishing-related keywords.")
        if int(features.get("action_keyword_count", 0)) > 0:
            matched = ", ".join(features.get("matched_action_keywords", [])[:4])
            add("ACTION_LINK", self._w("ACTION_LINK", 0.10), f"The path/query suggests an action flow such as login, verify, or update ({matched})." if matched else "The path/query suggests an action flow such as login, verify, or update.")
        if int(features.get("host_deceptive_token_count", 0)) > 0:
            matched = ", ".join(features.get("matched_deceptive_host_tokens", [])[:4])
            add("HOST_DECEPTIVE_TOKEN", self._w("HOST_DECEPTIVE_TOKEN", 0.18), f"The hostname contains deceptive or phishing-style terms ({matched})." if matched else "The hostname contains deceptive or phishing-style terms.")
        if features.get("has_redirect_param"):
            add("REDIRECT_PARAM", self._w("REDIRECT_PARAM", 0.18), "The URL contains redirect-style parameters that may hide the final destination.")
        if features.get("nested_url_count", 0) > 0:
            add("NESTED_URL", self._w("NESTED_URL", 0.16), "The query contains another embedded URL, which is often used in redirect chains.")
        if features.get("is_shortener"):
            add("URL_SHORTENER", self._w("URL_SHORTENER", 0.14), "The URL uses a shortening service that hides the final destination.")
        if features.get("brand_signal_available") and features.get("brand_mismatch"):
            entity_name = (claimed_entity or {}).get("display_name", "the claimed entity")
            add("BRAND_MISMATCH", self._w("BRAND_MISMATCH", 0.25), f"The domain does not match the expected brand hints for {entity_name}.")
        if features.get("has_unusual_port"):
            add("UNUSUAL_PORT", self._w("UNUSUAL_PORT", 0.10), "The URL uses a non-standard port.")
        if features.get("has_https_token_misuse"):
            add("HTTPS_TOKEN_MISUSE", self._w("HTTPS_TOKEN_MISUSE", 0.10), "The string 'https' appears inside the hostname/path in a misleading way.")
        if features.get("long_query"):
            add("LONG_QUERY", self._w("LONG_QUERY", 0.08), "The URL has a long query string.")
        if features.get("suspicious_tld"):
            add("SUSPICIOUS_TLD", self._w("SUSPICIOUS_TLD", 0.12), f"The URL uses a higher-risk top-level domain ({features.get('tld')}).")
        if features.get("download_like_path"):
            add("DOWNLOADABLE_FILE", self._w("DOWNLOADABLE_FILE", 0.18), f"The path points to a downloadable or executable-style file ({features.get('download_extension')}).")
        if features.get("heavy_encoding"):
            add("HEAVY_ENCODING", self._w("HEAVY_ENCODING", 0.10), "The URL uses heavy percent-encoding, which can hide suspicious content.")

        if features.get("was_obfuscated") and int(features.get("action_keyword_count", 0)) > 0:
            add("OBFUSCATED_ACTION_LINK", self._w("OBFUSCATED_ACTION_LINK", 0.14), "The link is both obfuscated and action-oriented, which is a strong phishing pattern.")
        if features.get("claimed_sector_sensitive") and int(features.get("action_keyword_count", 0)) > 0:
            sector = features.get("claimed_sector", "sensitive sector")
            add("SENSITIVE_ENTITY_ACTION_LINK", self._w("SENSITIVE_ENTITY_ACTION_LINK", 0.12), f"The claimed entity is in a sensitive sector ({sector}) and the link requests user action.")
        if features.get("claimed_sector_sensitive") and features.get("insecure_http"):
            sector = features.get("claimed_sector", "sensitive sector")
            add("SENSITIVE_ENTITY_INSECURE_HTTP", self._w("SENSITIVE_ENTITY_INSECURE_HTTP", 0.10), f"The claimed entity is in a sensitive sector ({sector}) but the URL is not HTTPS.")
        if features.get("domain_contains_claimed_sector_token") and int(features.get("host_deceptive_token_count", 0)) > 0:
            matched_tokens = ", ".join(features.get("matched_claimed_sector_tokens", [])[:4])
            add("DECEPTIVE_SECTOR_DOMAIN", self._w("DECEPTIVE_SECTOR_DOMAIN", 0.12), f"The domain looks sector-themed ({matched_tokens}) while also using deceptive host terms." if matched_tokens else "The domain looks sector-themed while also using deceptive host terms.")
        if url_count > 1:
            add("MULTIPLE_URLS", self._w("MULTIPLE_URLS", 0.04), "The message contains multiple URLs.")

        score = min(1.0, max(0.0, score))
        return {
            "rules_score": round(score, 6),
            "rules_label": self._label_from_score(score),
            "rules_flags": flags,
            "rules_reasons": reasons[:12],
        }
