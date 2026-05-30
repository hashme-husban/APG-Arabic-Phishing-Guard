from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qsl


class URLFeatureExtractor:
    SUSPICIOUS_TLDS_DEFAULT = {
        "xyz", "top", "cfd", "click", "site", "online", "monster", "rest",
        "quest", "cam", "work", "support", "live", "gq", "tk", "ml",
    }
    SHORTENER_DOMAINS_DEFAULT = {
        "bit.ly", "tinyurl.com", "goo.gl", "t.co", "rb.gy", "cutt.ly", "ow.ly", "rebrand.ly",
    }
    SUSPICIOUS_KEYWORDS_DEFAULT = {
        "login", "signin", "verify", "verification", "secure", "account", "update", "confirm",
        "wallet", "billing", "payment", "otp", "bank", "unlock", "suspend", "review", "recover",
    }
    ACTION_KEYWORDS_DEFAULT = {
        "login", "signin", "verify", "update", "confirm", "review", "reset", "activate", "unlock",
        "continue", "secure", "submit", "validate",
    }
    DECEPTIVE_HOST_TOKENS_DEFAULT = {
        "secure", "login", "verify", "update", "confirm", "account", "bank", "wallet", "support",
        "service", "signin", "auth", "payment", "billing", "portal", "validation",
    }
    REDIRECT_PARAMETER_NAMES_DEFAULT = {
        "next", "url", "target", "dest", "destination", "continue", "redirect", "redir", "return", "return_to",
    }
    SENSITIVE_SECTORS_DEFAULT = {"bank", "payment", "wallet", "government", "telecom", "education"}
    SECTOR_DOMAIN_TOKENS_DEFAULT = {
        "bank": ["bank", "pay", "wallet", "card"],
        "payment": ["pay", "wallet", "card", "billing"],
        "government": ["gov", "tax", "citizen", "service"],
        "education": ["edu", "university", "portal", "student"],
        "telecom": ["sim", "telecom", "carrier", "network"],
    }
    DOWNLOAD_EXTENSIONS = {"apk", "exe", "msi", "zip", "rar", "jar", "scr", "js", "vbs", "docm", "xlsm"}

    def __init__(self, config_path: str = "configs/url_layer_config.json", brand_hints_path: str = "configs/url_brand_hints.json") -> None:
        self.config = self._load_json(config_path)
        self.brand_hints = self._load_json(brand_hints_path)
        self.shortener_domains = set(self.config.get("shortener_domains", [])) or set(self.SHORTENER_DOMAINS_DEFAULT)
        self.suspicious_keywords = set(self.config.get("suspicious_keywords", [])) or set(self.SUSPICIOUS_KEYWORDS_DEFAULT)
        self.action_keywords = set(self.config.get("action_keywords", [])) or set(self.ACTION_KEYWORDS_DEFAULT)
        self.deceptive_host_tokens = set(self.config.get("deceptive_host_tokens", [])) or set(self.DECEPTIVE_HOST_TOKENS_DEFAULT)
        self.redirect_parameter_names = set(self.config.get("redirect_parameter_names", [])) or set(self.REDIRECT_PARAMETER_NAMES_DEFAULT)
        self.sensitive_sectors = set(self.config.get("sensitive_sectors", [])) or set(self.SENSITIVE_SECTORS_DEFAULT)
        self.sector_domain_tokens = self.config.get("sector_domain_tokens", {}) or dict(self.SECTOR_DOMAIN_TOKENS_DEFAULT)
        self.suspicious_tlds = set(self.config.get("suspicious_tlds", [])) or set(self.SUSPICIOUS_TLDS_DEFAULT)

    def _load_json(self, path_str: str) -> Dict[str, Any]:
        path = Path(path_str)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _count_digits(self, value: str) -> int:
        return len(re.findall(r"\d", value or ""))

    def _digit_ratio(self, value: str) -> float:
        value = value or ""
        return 0.0 if not value else self._count_digits(value) / max(1, len(value))

    def _path_depth(self, path: str) -> int:
        path = (path or "").strip("/")
        return 0 if not path else len([p for p in path.split("/") if p])

    def _count_subdomains(self, subdomain: str) -> int:
        return 0 if not subdomain else len([p for p in subdomain.split(".") if p])

    def _tokenize(self, value: str) -> List[str]:
        value = (value or "").lower()
        return [tok for tok in re.split(r"[^a-z0-9\u0600-\u06FF]+", value) if tok]

    def _match_tokens(self, tokens: List[str], vocab: set) -> List[str]:
        return sorted({tok for tok in tokens if tok in vocab})

    def _has_redirect_param(self, query_pairs: List[tuple]) -> bool:
        return any(key.lower() in self.redirect_parameter_names for key, _ in query_pairs)

    def _download_extension(self, path: str) -> str:
        last = (path or "").split("/")[-1].lower()
        if "." not in last:
            return ""
        ext = last.rsplit(".", 1)[-1]
        return ext if ext in self.DOWNLOAD_EXTENSIONS else ""

    def _nested_url_count(self, query_pairs: List[tuple]) -> int:
        count = 0
        for _, value in query_pairs:
            if re.search(r"(?:https?://|www\.)", value, re.IGNORECASE):
                count += 1
        return count

    def _brand_features(self, registrable_domain: str, claimed_entity: Dict[str, Any] | None) -> Dict[str, Any]:
        if not claimed_entity or not claimed_entity.get("entity_id"):
            return {
                "brand_signal_available": False,
                "brand_match": False,
                "brand_mismatch": False,
                "official_domain_match": False,
                "matched_expected_tokens": [],
            }
        entity_map = self.brand_hints.get("entities", {}) if isinstance(self.brand_hints, dict) else {}
        entity_hint = entity_map.get(claimed_entity.get("entity_id"), {}) if isinstance(entity_map, dict) else {}
        official_domains = {str(x).lower() for x in entity_hint.get("official_domains", [])}
        expected_tokens = [str(t).lower() for t in entity_hint.get("expected_tokens", [])]
        if not official_domains and not expected_tokens:
            return {
                "brand_signal_available": False,
                "brand_match": False,
                "brand_mismatch": False,
                "official_domain_match": False,
                "matched_expected_tokens": [],
            }
        domain_lower = (registrable_domain or "").lower()
        official_domain_match = domain_lower in official_domains
        matched_expected_tokens = [token for token in expected_tokens if token in domain_lower]
        brand_match = official_domain_match or bool(matched_expected_tokens)
        return {
            "brand_signal_available": True,
            "brand_match": brand_match,
            "brand_mismatch": not brand_match,
            "official_domain_match": official_domain_match,
            "matched_expected_tokens": matched_expected_tokens,
        }

    def _claimed_sector_features(self, registrable_domain: str, claimed_entity: Dict[str, Any] | None) -> Dict[str, Any]:
        if not claimed_entity:
            return {
                "claimed_sector": "",
                "claimed_sector_sensitive": 0,
                "domain_contains_claimed_sector_token": 0,
                "matched_claimed_sector_tokens": [],
            }
        sector = str(claimed_entity.get("sector", "")).strip().lower()
        sector_tokens = self.sector_domain_tokens.get(sector, []) if isinstance(self.sector_domain_tokens, dict) else []
        matched_sector_tokens = [tok for tok in sector_tokens if tok.lower() in (registrable_domain or "").lower()]
        return {
            "claimed_sector": sector,
            "claimed_sector_sensitive": int(sector in self.sensitive_sectors),
            "domain_contains_claimed_sector_token": int(bool(matched_sector_tokens)),
            "matched_claimed_sector_tokens": matched_sector_tokens,
        }

    def extract(self, canonical_info: Dict[str, Any], claimed_entity: Dict[str, Any] | None = None) -> Dict[str, Any]:
        canonical_url = canonical_info.get("canonical_url", "")
        host_ascii = canonical_info.get("host_ascii", "")
        registrable_domain = canonical_info.get("registrable_domain", "")
        subdomain = canonical_info.get("subdomain", "")
        path = canonical_info.get("path", "")
        query = canonical_info.get("query", "")
        query_pairs = parse_qsl(query, keep_blank_values=True)
        host_tokens = self._tokenize(host_ascii)
        path_tokens = self._tokenize(path)
        query_tokens = self._tokenize(query)
        all_tokens = host_tokens + path_tokens + query_tokens
        matched_suspicious_keywords = self._match_tokens(all_tokens, self.suspicious_keywords)
        matched_action_keywords = self._match_tokens(host_tokens + path_tokens + query_tokens, self.action_keywords)
        matched_deceptive_host_tokens = self._match_tokens(host_tokens, self.deceptive_host_tokens)
        download_extension = self._download_extension(path)
        nested_url_count = self._nested_url_count(query_pairs)
        encoded_char_count = canonical_url.count("%")
        tld = str(canonical_info.get("tld", "")).lower()

        features = {
            "url_length": len(canonical_url),
            "hostname_length": len(host_ascii),
            "path_length": len(path),
            "query_length": len(query),
            "num_dots": host_ascii.count("."),
            "num_subdomains": self._count_subdomains(subdomain),
            "num_hyphens": canonical_url.count("-"),
            "num_digits": self._count_digits(canonical_url),
            "digit_ratio": round(self._digit_ratio(canonical_url), 6),
            "path_depth": self._path_depth(path),
            "num_query_params": len(query_pairs),
            "has_ip": int(bool(canonical_info.get("has_ip"))),
            "ip_is_private": int(bool(canonical_info.get("ip_is_private"))),
            "ip_is_loopback": int(bool(canonical_info.get("ip_is_loopback"))),
            "ip_is_reserved": int(bool(canonical_info.get("ip_is_reserved"))),
            "ip_is_link_local": int(bool(canonical_info.get("ip_is_link_local"))),
            "has_punycode": int(bool(canonical_info.get("has_punycode"))),
            "had_unicode_host": int(bool(canonical_info.get("had_unicode_host"))),
            "host_mixed_script": int(bool(canonical_info.get("host_mixed_script"))),
            "has_at_symbol": int(bool(canonical_info.get("has_at_symbol"))),
            "has_credentials": int(bool(canonical_info.get("has_credentials"))),
            "has_unusual_port": int(bool(canonical_info.get("has_unusual_port"))),
            "was_obfuscated": int(bool(canonical_info.get("was_obfuscated"))),
            "fragment_present": int(bool(canonical_info.get("fragment_present"))),
            "insecure_http": int(not bool(canonical_info.get("is_https"))),
            "is_shortener": int(registrable_domain.lower() in self.shortener_domains),
            "suspicious_keyword_count": len(matched_suspicious_keywords),
            "action_keyword_count": len(matched_action_keywords),
            "host_deceptive_token_count": len(matched_deceptive_host_tokens),
            "has_redirect_param": int(self._has_redirect_param(query_pairs)),
            "has_https_token_misuse": int(("https" in host_ascii.lower() or "https" in path.lower()) and canonical_info.get("scheme") != "https"),
            "long_query": int(len(query) > 80),
            "excessive_length": int(len(canonical_url) > 80),
            "too_many_subdomains": int(self._count_subdomains(subdomain) >= 3),
            "suspicious_tld": int(tld in self.suspicious_tlds),
            "download_like_path": int(bool(download_extension)),
            "nested_url_count": nested_url_count,
            "encoded_char_count": encoded_char_count,
            "heavy_encoding": int(encoded_char_count >= 6),
            "matched_suspicious_keywords": matched_suspicious_keywords,
            "matched_action_keywords": matched_action_keywords,
            "matched_deceptive_host_tokens": matched_deceptive_host_tokens,
            "download_extension": download_extension,
            "tld": tld,
            "host_tokens": host_tokens,
            "path_tokens": path_tokens,
        }
        features.update(self._brand_features(registrable_domain, claimed_entity))
        features.update(self._claimed_sector_features(registrable_domain, claimed_entity))
        return features
