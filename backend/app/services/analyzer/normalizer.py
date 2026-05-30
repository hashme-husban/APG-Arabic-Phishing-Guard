from __future__ import annotations

import re
import unicodedata

DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
TATWEEL_RE = re.compile(r"\u0640+")
REPEATED_AR_LETTER_RE = re.compile(r"([\u0621-\u064A])\1{2,}")


class ArabicNormalizer:
    def normalize(self, text: str) -> str:
        value = unicodedata.normalize("NFKC", text or "")
        value = DIACRITICS_RE.sub("", value)
        value = TATWEEL_RE.sub("", value)
        value = value.translate(
            str.maketrans(
                {
                    "أ": "ا",
                    "إ": "ا",
                    "آ": "ا",
                    "ٱ": "ا",
                    "ى": "ي",
                    "ؤ": "و",
                    "ئ": "ي",
                    "ة": "ه",
                    "گ": "ك",
                }
            )
        )
        value = re.sub(r"[\u200f\u200e]", " ", value)
        value = REPEATED_AR_LETTER_RE.sub(r"\1\1", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip().lower()


_NORMALIZER = ArabicNormalizer()


def normalize_arabic(text: str) -> str:
    return _NORMALIZER.normalize(text)


def n_terms(terms: list[str]) -> list[str]:
    return [_NORMALIZER.normalize(term) for term in terms]


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term and term in text for term in terms)


def first_match(text: str, terms: list[str]) -> str:
    return next((term for term in terms if term and term in text), "")


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = (item or "").strip()
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def dedupe_signals(signals):
    seen: set[tuple[str, str]] = set()
    output = []
    for signal in signals:
        key = (signal.name, signal.evidence)
        if key not in seen:
            seen.add(key)
            output.append(signal)
    return output
