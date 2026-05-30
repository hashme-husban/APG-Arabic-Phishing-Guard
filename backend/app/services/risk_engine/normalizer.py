"""
APG Risk Intelligence Engine v1 — Normalizer

Thin adapter over the existing ArabicNormalizer from the v5 analyzer.
Returns both the normalized form and preserves the original for display.
"""
from __future__ import annotations

from app.services.analyzer.normalizer import ArabicNormalizer as _ArabicNormalizer


class Normalizer:
    def __init__(self) -> None:
        self._inner = _ArabicNormalizer()

    def normalize(self, text: str) -> str:
        """Return normalized Arabic/mixed text (lower-cased, diacritics removed, alef variants unified)."""
        return self._inner.normalize(text or "")


# Module-level singleton
_NORMALIZER = Normalizer()


def normalize(text: str) -> str:
    return _NORMALIZER.normalize(text)
