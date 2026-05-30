"""
APG Risk Intelligence Engine v1 — Input Modality Detector

Classifies each analysis request into one of four input modalities so that
the engine does not penalise unavailable dimensions:

  text_only      — message text with no URL (run text scoring; skip VT)
  url_only       — bare URL with no surrounding message text
  text_with_url  — both text and URL present (default; all layers active)
  empty          — no usable input
"""
from __future__ import annotations

import re

InputModality = str  # "text_only" | "url_only" | "text_with_url" | "empty"


def detect_modality(raw_text: str, extracted_urls: list[str]) -> InputModality:
    """
    Classify the analysis input into one of four modalities.

    Algorithm:
      1. Empty string → "empty"
      2. No URLs extracted → "text_only"
      3. Strip every URL from the raw text; if word characters remain → "text_with_url"
      4. Otherwise (the whole input was URL(s)) → "url_only"
    """
    text = (raw_text or "").strip()
    if not text:
        return "empty"
    if not extracted_urls:
        return "text_only"

    remaining = text
    for url in extracted_urls:
        remaining = remaining.replace(url, "")

    if re.search(r"\w", remaining):
        return "text_with_url"
    return "url_only"
