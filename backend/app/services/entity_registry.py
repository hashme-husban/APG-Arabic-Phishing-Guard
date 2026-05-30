"""
APG Entity Registry — in-memory singleton backed by jo_entities.json.

Loads the JSON dataset once at startup and builds three fast indexes:
  - alias_index:  normalized alias/name → entity
  - sender_index: normalized official sender name → entity
  - domain_index: normalized domain → entity

Arabic normalization rules applied to all keys:
  ة→ه, أإآ→ا, tatweel stripped, whitespace collapsed, lowercased.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("apg.entity_registry")

_DATA_FILE = Path(__file__).parent.parent / "data" / "entities" / "jo_entities.json"

# ─── Arabic normalization (inline — no external deps required) ────────────────

_DIACRITICS_RE = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL_RE = re.compile(r"ـ+")
_ALEF_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_BIDI_RE = re.compile(r"[‏‎]")


def _norm(text: str) -> str:
    """Normalize text for index keys and lookup comparisons."""
    v = (text or "").strip()
    if not v:
        return ""
    v = _DIACRITICS_RE.sub("", v)
    v = _TATWEEL_RE.sub("", v)
    v = v.translate(_ALEF_MAP)
    v = _BIDI_RE.sub(" ", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip().lower()


def _is_arabic_char(ch: str) -> bool:
    """Return True for Arabic-script letters used in APG message matching."""
    if not ch:
        return False
    code = ord(ch)
    return (
        0x0600 <= code <= 0x06FF
        or 0x0750 <= code <= 0x077F
        or 0x08A0 <= code <= 0x08FF
        or 0xFB50 <= code <= 0xFDFF
        or 0xFE70 <= code <= 0xFEFF
    )


def _is_latin_alnum(ch: str) -> bool:
    return bool(ch) and ch.isascii() and ch.isalnum()


def _is_token_char(ch: str) -> bool:
    return _is_arabic_char(ch) or _is_latin_alnum(ch) or ch == "_"


def _arabic_letter_count(text: str) -> int:
    return sum(1 for ch in text if _is_arabic_char(ch))


def _ascii_alnum_count(text: str) -> int:
    return sum(1 for ch in text if _is_latin_alnum(ch))


def _is_short_alias(alias: str) -> bool:
    arabic_len = _arabic_letter_count(alias)
    ascii_len = _ascii_alnum_count(alias)
    if arabic_len:
        return arabic_len <= 3
    if ascii_len:
        return ascii_len <= 4
    return len(alias) <= 4


_CONTEXT_REQUIRED_ALIASES: set[str] = {
    _norm("سند"),
    _norm("أية"),
    _norm("اية"),
}


def _has_boundary(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not _is_token_char(before) and not _is_token_char(after)


def _has_ambiguous_alias_context(text: str, alias: str, start: int, end: int) -> bool:
    """Allow common-word aliases only when the phrase reads like an entity claim."""
    if start == 0:
        return True
    window_start = max(0, start - 24)
    window_end = min(len(text), end + 24)
    window = text[window_start:window_end]
    contextual_patterns = (
        f"من {alias}",
        f"عن {alias}",
        f"تطبيق {alias}",
        f"شركه {alias}",
        f"شركة {alias}",
        f"خدمه {alias}",
        f"خدمة {alias}",
        f"استخدام {alias}",
        f"استخدم {alias}",
        f"{alias}:",
        f"{alias} pay",
        f"{alias} للدفع",
        f"{alias} الحكوم",
    )
    return any(pattern in window for pattern in contextual_patterns)


def _has_short_alias_context(text: str, alias: str, start: int, end: int) -> bool:
    """Require context for short standalone tokens like Zain, CAB, BOJ, or PSD."""
    if start == 0:
        return True
    window_start = max(0, start - 24)
    window_end = min(len(text), end + 24)
    window = text[window_start:window_end]
    contextual_patterns = (
        f"من {alias}",
        f"عن {alias}",
        f"رساله {alias}",
        f"رسالة {alias}",
        f"حساب {alias}",
        f"{alias} حساب",
        f"{alias} account",
        f"my {alias}",
        f"{alias} login",
        f"{alias} verification",
        f"{alias} verify",
        f"{alias} payment",
        f"{alias} official",
        f"{alias}:",
    )
    return any(pattern in window for pattern in contextual_patterns)


def _boundary_match(text: str, alias: str) -> bool:
    """Boundary-aware containment; never performs reverse substring matching."""
    if not text or not alias or len(alias) < 3:
        return False

    pos = text.find(alias)
    while pos != -1:
        end = pos + len(alias)
        if _has_boundary(text, pos, end):
            if _is_short_alias(alias) and not _has_short_alias_context(text, alias, pos, end):
                pos = text.find(alias, pos + 1)
                continue
            if alias not in _CONTEXT_REQUIRED_ALIASES:
                return True
            if _has_ambiguous_alias_context(text, alias, pos, end):
                return True
        pos = text.find(alias, pos + 1)
    return False


# ─── Null result helper ───────────────────────────────────────────────────────

def _no_match() -> dict[str, Any]:
    return {
        "matched": False,
        "entity_id": None,
        "entity_name": None,
        "entity_type": None,
        "confidence": 0.0,
        "match_source": None,
    }


# ─── Entity Registry ──────────────────────────────────────────────────────────

class EntityRegistry:
    """
    In-memory registry of known Jordan entities.

    Indexes are built at construction time from jo_entities.json.
    Use the module-level ``get_registry()`` to obtain the singleton.
    """

    def __init__(self, data_path: Path = _DATA_FILE) -> None:
        raw = json.loads(data_path.read_text(encoding="utf-8"))
        self._entities: list[dict[str, Any]] = raw.get("entities", [])
        self._dataset_version: str = raw.get("dataset_version", "unknown")

        # normalized_key → entity dict
        self._alias_index: dict[str, dict[str, Any]] = {}
        self._sender_index: dict[str, dict[str, Any]] = {}
        self._domain_index: dict[str, dict[str, Any]] = {}
        self._domain_multi_index: dict[str, list[dict[str, Any]]] = {}
        # entity_id → entity dict (for fast full-record lookups)
        self._id_index: dict[str, dict[str, Any]] = {}

        for entity in self._entities:
            # ID index (always unique)
            eid = entity.get("id", "")
            if eid:
                self._id_index[eid] = entity

            # Aliases (and primary name fields treated as implicit aliases)
            for alias in entity.get("aliases", []):
                self._index_alias(alias, entity)
            for field in ("name", "primary_arabic_name"):
                self._index_alias(entity.get(field, ""), entity)

            # Official sender names
            for sender in entity.get("official_sender_names", []):
                key = _norm(sender)
                if key and key not in self._sender_index:
                    self._sender_index[key] = entity

            # Official domains — stored as bare domain (no scheme/path)
            for domain in entity.get("official_domains", []):
                key = _strip_domain(domain)
                if key:
                    self._domain_multi_index.setdefault(key, []).append(entity)
                if key and key not in self._domain_index:
                    self._domain_index[key] = entity

        logger.info(
            "EntityRegistry ready — %d entities | aliases=%d senders=%d domains=%d (v=%s)",
            len(self._entities),
            len(self._alias_index),
            len(self._sender_index),
            len(self._domain_index),
            self._dataset_version,
        )

    # ── internal helpers ──────────────────────────────────────────────────────

    def _index_alias(self, value: str, entity: dict[str, Any]) -> None:
        key = _norm(value)
        if key and key not in self._alias_index:
            self._alias_index[key] = entity

    @staticmethod
    def _make(entity: dict[str, Any], confidence: float, source: str) -> dict[str, Any]:
        return {
            "matched": True,
            "entity_id": entity.get("id"),
            "entity_name": entity.get("name"),
            "entity_type": entity.get("entity_type"),
            "confidence": round(confidence, 4),
            "match_source": source,
        }

    # ── public lookup API ─────────────────────────────────────────────────────

    def find_entity_by_alias(self, text: str) -> dict[str, Any]:
        """
        Match *text* against all entity aliases.

        Returns confidence 1.0 for an exact match, 0.7 for a boundary-aware
        text match. Reverse substring matching is intentionally disallowed.
        """
        if not text:
            return _no_match()
        norm_text = _norm(text)
        if not norm_text:
            return _no_match()

        # Exact
        if norm_text in self._alias_index:
            return self._make(self._alias_index[norm_text], 1.0, "alias")

        # Boundary-aware contains (prefer longest alias key to minimise false positives)
        best_entity: dict[str, Any] | None = None
        best_len = 0
        for key, entity in self._alias_index.items():
            if _boundary_match(norm_text, key):
                if len(key) > best_len:
                    best_len = len(key)
                    best_entity = entity

        if best_entity is not None:
            return self._make(best_entity, 0.7, "alias")

        return _no_match()

    def find_entity_by_sender(self, sender: str) -> dict[str, Any]:
        """
        Match *sender* against official_sender_names.

        Returns 1.0 for exact normalized sender matches.

        Sender names are stricter than message text aliases: a spoof like
        "ZAIN-FAKE" or "ArabBankSecure" must not be treated as an official
        sender just because it contains a real sender token.
        """
        if not sender:
            return _no_match()
        norm_sender = _norm(sender)
        if not norm_sender:
            return _no_match()

        # Exact
        if norm_sender in self._sender_index:
            return self._make(self._sender_index[norm_sender], 1.0, "sender")

        return _no_match()

    def find_entity_by_domain(self, domain: str) -> dict[str, Any]:
        """
        Match *domain* against official_domains.

        Returns 1.0 for exact, 0.9 for subdomain suffix match.
        """
        if not domain:
            return _no_match()
        stripped = _strip_domain(domain)
        if not stripped:
            return _no_match()

        # Exact
        if stripped in self._domain_index:
            return self._make(self._domain_index[stripped], 1.0, "domain")

        # Subdomain suffix: e.g. "online.arabbank.jo" → "arabbank.jo"
        best_entity: dict[str, Any] | None = None
        best_len = 0
        for key, entity in self._domain_index.items():
            if stripped.endswith("." + key):
                if len(key) > best_len:
                    best_len = len(key)
                    best_entity = entity

        if best_entity is not None:
            return self._make(best_entity, 0.9, "domain")

        return _no_match()

    def find_entities_by_domain(self, domain: str) -> list[dict[str, Any]]:
        """
        Match *domain* against official_domains and return all candidates.

        Shared official domains are valid for related entities such as a parent
        organization and a wallet/service brand. The legacy single-result
        finder remains first-wins for compatibility; this method exposes the
        complete candidate set for conflict/alignment decisions.
        """
        if not domain:
            return []
        stripped = _strip_domain(domain)
        if not stripped:
            return []

        if stripped in self._domain_multi_index:
            return [
                self._make(entity, 1.0, "domain")
                for entity in self._domain_multi_index[stripped]
            ]

        best_key = ""
        for key in self._domain_multi_index:
            if stripped.endswith("." + key) and len(key) > len(best_key):
                best_key = key

        if best_key:
            return [
                self._make(entity, 0.9, "domain")
                for entity in self._domain_multi_index[best_key]
            ]

        return []

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Return the full entity record for *entity_id*, or None if not found."""
        return self._id_index.get(entity_id or "")

    # ── metadata ──────────────────────────────────────────────────────────────

    @property
    def dataset_version(self) -> str:
        return self._dataset_version

    @property
    def entity_count(self) -> int:
        return len(self._entities)


# ─── Domain normalization helper ──────────────────────────────────────────────

def _strip_domain(raw: str) -> str:
    """Extract bare domain from a raw string (strips scheme, www., port, path)."""
    d = (raw or "").strip().lower()
    # Strip scheme
    d = re.sub(r"^https?://", "", d)
    # Strip path and query
    d = d.split("/")[0].split("?")[0].split("#")[0]
    # Strip port
    d = re.sub(r":\d+$", "", d)
    # Strip www.
    d = re.sub(r"^www\.", "", d)
    return d.strip()


# ─── Singleton ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_registry() -> EntityRegistry:
    """Return the module-level singleton.  Loaded once on first call."""
    return EntityRegistry()
