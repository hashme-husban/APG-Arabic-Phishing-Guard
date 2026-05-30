from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlsplit, urlunsplit


class URLCanonicalizer:
    COMMON_TWO_LEVEL_SUFFIXES = {
        "co.uk", "org.uk", "gov.uk", "ac.uk",
        "com.au", "net.au", "org.au",
        "com.sa", "net.sa", "org.sa",
        "com.jo", "net.jo", "org.jo",
        "com.eg", "net.eg", "org.eg",
        "com.tr", "com.br", "co.in", "co.id",
    }

    def _iterative_unquote(self, value: str, rounds: int = 2) -> str:
        current = value
        for _ in range(rounds):
            decoded = unquote(current)
            if decoded == current:
                break
            current = decoded
        return current

    def repair_obfuscation(self, raw_url: str) -> str:
        value = (raw_url or "").strip()
        value = value.replace("hxxps://", "https://").replace("hxxp://", "http://")
        value = re.sub(r"\s*\[\.\]\s*", ".", value)
        value = re.sub(r"\(\s*dot\s*\)", ".", value, flags=re.IGNORECASE)
        value = value.replace("[: ]//", "://").replace("[: ]", ":")
        value = value.replace("[:]", ":").replace("(.)", ".")
        value = self._iterative_unquote(value, rounds=2)
        value = re.sub(r"\s+", "", value)
        return value.strip(" \t\r\n<>'\"")

    def ensure_scheme(self, url: str) -> str:
        if not url:
            return ""
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", url):
            return url
        return "http://" + url

    def _ip_obj(self, host: str):
        if not host:
            return None
        try:
            return ipaddress.ip_address(host)
        except Exception:
            return None

    def _is_ip(self, host: str) -> bool:
        return self._ip_obj(host) is not None

    def _ip_risk_flags(self, host: str) -> Dict[str, bool]:
        ip_obj = self._ip_obj(host)
        if ip_obj is None:
            return {
                "has_ip": False,
                "ip_is_private": False,
                "ip_is_loopback": False,
                "ip_is_reserved": False,
                "ip_is_link_local": False,
            }
        return {
            "has_ip": True,
            "ip_is_private": bool(ip_obj.is_private),
            "ip_is_loopback": bool(ip_obj.is_loopback),
            "ip_is_reserved": bool(ip_obj.is_reserved),
            "ip_is_link_local": bool(ip_obj.is_link_local),
        }

    def _has_mixed_script(self, host_raw: str) -> bool:
        if not host_raw:
            return False
        has_latin = bool(re.search(r"[A-Za-z]", host_raw))
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", host_raw))
        return has_latin and has_arabic

    def _extract_domain_parts(self, host_ascii: str) -> Dict[str, str]:
        if not host_ascii or self._is_ip(host_ascii):
            return {"registrable_domain": host_ascii, "subdomain": "", "tld": ""}
        labels = host_ascii.split(".")
        if len(labels) <= 2:
            return {"registrable_domain": host_ascii, "subdomain": "", "tld": labels[-1] if labels else ""}
        last_two = ".".join(labels[-2:])
        last_three = ".".join(labels[-3:]) if len(labels) >= 3 else ""
        if last_two in self.COMMON_TWO_LEVEL_SUFFIXES and len(labels) >= 3:
            registrable = last_three
            subdomain = ".".join(labels[:-3])
            tld = last_two.split(".")[-1]
        else:
            registrable = last_two
            subdomain = ".".join(labels[:-2])
            tld = labels[-1]
        return {"registrable_domain": registrable, "subdomain": subdomain, "tld": tld}

    def canonicalize(
        self,
        raw_url: str,
        source_was_obfuscated: bool = False,
        original_source: Optional[str] = None,
        source_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        original_url = (raw_url or "").strip()
        repaired_url = self.repair_obfuscation(original_url)
        with_scheme = self.ensure_scheme(repaired_url)
        parsed = urlsplit(with_scheme)
        scheme = (parsed.scheme or "http").lower()
        host_raw = (parsed.hostname or "").strip(".").lower()

        try:
            host_ascii = host_raw.encode("idna").decode("ascii")
        except Exception:
            host_ascii = host_raw

        had_unicode_host = host_raw != host_ascii
        has_punycode = "xn--" in host_ascii
        try:
            port = parsed.port
        except Exception:
            port = None

        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        query = parsed.query or ""
        fragment_present = bool(parsed.fragment)
        has_credentials = bool(parsed.username or parsed.password)
        netloc = host_ascii
        if has_credentials and parsed.username:
            netloc = f"{parsed.username}@{netloc}"
        if port is not None:
            netloc = f"{netloc}:{port}"
        canonical_url = urlunsplit((scheme, netloc, path, query, ""))
        domain_parts = self._extract_domain_parts(host_ascii)
        original_source = original_source or original_url
        was_obfuscated = source_was_obfuscated or any(token in original_source.lower() for token in ["hxxp", "[.]", "(dot)", "[:]"])
        ip_flags = self._ip_risk_flags(host_ascii)

        return {
            "original_url": original_url,
            "original_source": original_source,
            "repaired_url": repaired_url,
            "canonical_url": canonical_url,
            "scheme": scheme,
            "is_https": scheme == "https",
            "host_raw": host_raw,
            "host_ascii": host_ascii,
            "registrable_domain": domain_parts["registrable_domain"],
            "subdomain": domain_parts["subdomain"],
            "tld": domain_parts["tld"],
            "port": port,
            "path": path,
            "query": query,
            "fragment_present": fragment_present,
            "has_punycode": has_punycode,
            "had_unicode_host": had_unicode_host,
            "host_mixed_script": self._has_mixed_script(host_raw),
            "has_at_symbol": "@" in repaired_url,
            "has_credentials": has_credentials,
            "has_unusual_port": port not in (None, 80, 443),
            "was_obfuscated": was_obfuscated,
            "source_tags": source_tags or [],
            **ip_flags,
        }
