from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from layers.common import normalize_arabic_digits


class Normalizer:
    """Layer 03 - Normalization / Repair with stronger text cleanup and URL recovery."""

    DIRECT_URL_REGEX = re.compile(r"(?:(?:https?://|www\.)[^\s<>'\"\]\)]+)", re.IGNORECASE)
    BARE_DOMAIN_REGEX = re.compile(
        r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|co|xyz|top|site|online|click|live|store|app|dev|info|biz|me|pro|cc|link|shop|bank|sa|jo|eg|uk|de|fr|ru|cn|tr|ae|qa|kw|bh|om|edu|gov)\b(?:/[^\s<>'\"]*)?",
        re.IGNORECASE,
    )
    OBFUSCATED_HTTP_REGEX = re.compile(r"(hxxps?://[^\s<>'\"]+)", re.IGNORECASE)
    OBFUSCATED_DOT_DOMAIN_REGEX = re.compile(r"\b((?:www\.)?[A-Za-z0-9-]+(?:\s*\[\.\]\s*[A-Za-z0-9-]+)+(?:/[^\s<>'\"]*)?)", re.IGNORECASE)
    PHONE_REGEX = re.compile(r"(?:(?:\+|00)?\d[\d\-\s]{7,}\d)")
    EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    AMOUNT_REGEX = re.compile(r"(?:(?:\d+(?:[.,]\d+)?)\s*(?:د\.?ا|دينار|ريال|usd|sar|jod|\$|€|£))", re.IGNORECASE)
    EMOJI_REGEX = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002700-\U000027BF"
        "\U00002600-\U000026FF"
        "]+",
        flags=re.UNICODE,
    )

    ZERO_WIDTH_REGEX = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069]")
    ARABIC_DIACRITICS_REGEX = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]")
    TATWEEL_REGEX = re.compile(r"\u0640+")
    MULTISPACE_REGEX = re.compile(r"\s+")
    MULTI_PUNCT_REGEX = re.compile(r"([!?.,،؛:])\1{2,}")
    ELONGATION_REGEX = re.compile(r"([A-Za-z\u0621-\u064A])\1{2,}")
    MIXED_SCRIPT_WORD_REGEX = re.compile(r"\b(?=\w*[A-Za-z])(?=\w*[\u0600-\u06FF])\w+\b", re.UNICODE)

    OTP_CONTEXT_DIGITS_REGEX = re.compile(r"((?:otp|pin|code|verification|كود|رمز|الرمز|تحقق|التحقق)[^\n]{0,12}?)(\d{4,8})", re.IGNORECASE)
    DIGITS_ONLY_OTP_LINE_REGEX = re.compile(r"\b\d{4,8}\b")

    def process(self, raw_text: str, urls: List[str] | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        raw_text = (raw_text or "").strip()
        urls = urls or []

        repair_actions: List[str] = []
        reasons: List[str] = []
        working_text = raw_text

        if not working_text:
            return {
                "normalized_text": "",
                "noise_score": 0,
                "typo_score": 0,
                "repair_actions": [],
                "recovered_urls": [],
                "normalization_reasons": ["No text was provided."],
            }

        before_cleanup = working_text
        working_text = normalize_arabic_digits(working_text)
        working_text = self.ZERO_WIDTH_REGEX.sub(" ", working_text)
        if working_text != before_cleanup:
            repair_actions.append("INVISIBLE_CHARS_REMOVED")
            reasons.append("Removed invisible control characters and normalized Arabic digits.")

        direct_urls = self._dedupe(urls + self.extract_direct_urls(working_text))
        bare_domains = self.extract_bare_domains(working_text)
        direct_urls = self._dedupe(direct_urls + [u for u in bare_domains if u not in direct_urls])
        obfuscated_tokens, recovered_urls = self.extract_obfuscated_urls(working_text)

        emoji_count = self.count_emojis(working_text)
        if emoji_count > 0:
            working_text = self.remove_emojis(working_text)
            repair_actions.append("EMOJI_REMOVED")
            reasons.append(f"Removed {emoji_count} emoji character(s).")

        if direct_urls:
            working_text = self.mask_direct_urls(working_text, direct_urls)
            repair_actions.append("URL_MASKED")
            reasons.append(f"Masked {len(direct_urls)} direct or bare URL(s).")

        if obfuscated_tokens:
            working_text = self.mask_obfuscated_url_tokens(working_text, obfuscated_tokens)
            repair_actions.append("OBFUSCATED_URL_MASKED")
            reasons.append(f"Recovered {len(recovered_urls)} obfuscated URL candidate(s).")

        before_norm = working_text
        working_text = self.normalize_arabic(working_text)
        if working_text != before_norm:
            repair_actions.append("ARABIC_NORMALIZED")
            reasons.append("Applied Arabic normalization.")

        before_reduce = working_text
        working_text = self.reduce_repetition_noise(working_text)
        if working_text != before_reduce:
            repair_actions.append("REPETITION_REDUCED")
            reasons.append("Reduced excessive character or punctuation repetition.")

        working_text, otp_hits = self.mask_otp(working_text)
        if otp_hits > 0:
            repair_actions.append("OTP_MASKED")
            reasons.append(f"Masked {otp_hits} OTP-like token(s).")

        working_text, phone_hits = self.mask_phone_numbers(working_text)
        if phone_hits > 0:
            repair_actions.append("PHONE_MASKED")
            reasons.append(f"Masked {phone_hits} phone-like number(s).")

        working_text, email_hits = self.mask_emails(working_text)
        if email_hits > 0:
            repair_actions.append("EMAIL_MASKED")
            reasons.append(f"Masked {email_hits} email address(es).")

        working_text, amount_hits = self.mask_amounts(working_text)
        if amount_hits > 0:
            repair_actions.append("AMOUNT_MASKED")
            reasons.append(f"Masked {amount_hits} amount token(s).")

        working_text = self.clean_spacing(working_text)
        noise_score = self.estimate_noise_score(raw_text=raw_text, emoji_count=emoji_count, obfuscated_url_count=len(recovered_urls))
        typo_score = self.estimate_typo_score(raw_text)

        return {
            "normalized_text": working_text,
            "noise_score": noise_score,
            "typo_score": typo_score,
            "repair_actions": self._dedupe(repair_actions),
            "recovered_urls": self._dedupe(recovered_urls + direct_urls),
            "normalization_reasons": reasons if reasons else ["No major normalization action was needed."],
        }

    def extract_direct_urls(self, text: str) -> List[str]:
        if not text:
            return []
        return self._dedupe([self._clean_url(m) for m in self.DIRECT_URL_REGEX.findall(text)])

    def extract_bare_domains(self, text: str) -> List[str]:
        if not text:
            return []
        matches = []
        for token in self.BARE_DOMAIN_REGEX.findall(text):
            token = self._clean_url(token)
            if token and not token.lower().startswith(("http://", "https://", "www.")):
                matches.append("http://" + token)
        return self._dedupe(matches)

    def extract_obfuscated_urls(self, text: str) -> Tuple[List[str], List[str]]:
        if not text:
            return [], []
        found_tokens: List[str] = []
        recovered_urls: List[str] = []
        remaining_text = text

        for match in self.OBFUSCATED_HTTP_REGEX.finditer(text):
            token = match.group(1).strip().rstrip(".,;!?)")
            repaired = token.replace("hxxps://", "https://").replace("hxxp://", "http://")
            repaired = re.sub(r"\s*\[\.\]\s*", ".", repaired)
            repaired = re.sub(r"\s+", "", repaired).rstrip(".,;!?)")
            found_tokens.append(token)
            recovered_urls.append(repaired)
            remaining_text = remaining_text.replace(token, " ")

        for match in self.OBFUSCATED_DOT_DOMAIN_REGEX.finditer(remaining_text):
            token = match.group(1).strip().rstrip(".,;!?)")
            repaired = re.sub(r"\s*\[\.\]\s*", ".", token)
            repaired = re.sub(r"\s+", "", repaired)
            if not repaired.lower().startswith(("http://", "https://")):
                repaired = "http://" + repaired
            repaired = repaired.rstrip(".,;!?)")
            found_tokens.append(token)
            recovered_urls.append(repaired)

        return self._dedupe(found_tokens), self._dedupe(recovered_urls)

    def mask_direct_urls(self, text: str, urls: List[str]) -> str:
        result = text
        for url in sorted(urls, key=len, reverse=True):
            variants = {url, url.replace("http://", ""), url.replace("https://", "")}
            for variant in sorted(variants, key=len, reverse=True):
                if variant:
                    result = result.replace(variant, " <URL> ")
        return result

    def mask_obfuscated_url_tokens(self, text: str, tokens: List[str]) -> str:
        result = text
        for token in sorted(tokens, key=len, reverse=True):
            if token:
                result = result.replace(token, " <URL> ")
        return result

    def normalize_arabic(self, text: str) -> str:
        if not text:
            return ""
        text = self.ARABIC_DIACRITICS_REGEX.sub("", text)
        text = self.TATWEEL_REGEX.sub("", text)
        replacements = {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"}
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        return text

    def reduce_repetition_noise(self, text: str) -> str:
        text = self.MULTI_PUNCT_REGEX.sub(r"\1\1", text)
        text = self.ELONGATION_REGEX.sub(r"\1\1", text)
        return text

    def remove_emojis(self, text: str) -> str:
        return self.EMOJI_REGEX.sub(" ", text)

    def count_emojis(self, text: str) -> int:
        matches = self.EMOJI_REGEX.findall(text)
        return sum(len(m) for m in matches)

    def mask_otp(self, text: str) -> Tuple[str, int]:
        hits = 0

        def replace_contextual(match: re.Match) -> str:
            nonlocal hits
            hits += 1
            return f"{match.group(1)}<OTP>"

        text = self.OTP_CONTEXT_DIGITS_REGEX.sub(replace_contextual, text)
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if self.DIGITS_ONLY_OTP_LINE_REGEX.fullmatch(stripped):
                lines.append("<OTP>")
                hits += 1
            else:
                lines.append(line)
        return "\n".join(lines), hits

    def mask_phone_numbers(self, text: str) -> Tuple[str, int]:
        hits = 0

        def repl(match: re.Match) -> str:
            nonlocal hits
            candidate = match.group(0)
            digits = re.sub(r"\D", "", candidate)
            if len(digits) >= 9:
                hits += 1
                return "<PHONE>"
            return candidate

        return self.PHONE_REGEX.sub(repl, text), hits

    def mask_emails(self, text: str) -> Tuple[str, int]:
        hits = 0

        def repl(_: re.Match) -> str:
            nonlocal hits
            hits += 1
            return "<EMAIL>"

        return self.EMAIL_REGEX.sub(repl, text), hits

    def mask_amounts(self, text: str) -> Tuple[str, int]:
        hits = 0

        def repl(_: re.Match) -> str:
            nonlocal hits
            hits += 1
            return "<AMOUNT>"

        return self.AMOUNT_REGEX.sub(repl, text), hits

    def estimate_noise_score(self, raw_text: str, emoji_count: int = 0, obfuscated_url_count: int = 0) -> int:
        if not raw_text:
            return 0
        total_len = max(len(raw_text), 1)
        punct_count = len(re.findall(r"[!?,.;:،؛]", raw_text))
        symbol_count = len(re.findall(r"[^\w\s\u0600-\u06FF]", raw_text, flags=re.UNICODE))
        repeated_punct = len(re.findall(r"([!?.,،؛:])\1{2,}", raw_text))
        repeated_chars = len(re.findall(r"([A-Za-z\u0621-\u064A])\1{2,}", raw_text))
        mixed_script_words = len(self.MIXED_SCRIPT_WORD_REGEX.findall(raw_text))
        whitespace_irregular = len(re.findall(r"\s{2,}", raw_text))
        score = 0.0
        score += min(20, (symbol_count / total_len) * 100 * 0.8)
        score += min(12, (punct_count / total_len) * 100 * 0.7)
        score += min(14, repeated_punct * 4)
        score += min(14, repeated_chars * 3)
        score += min(12, emoji_count * 2)
        score += min(14, mixed_script_words * 4)
        score += min(8, whitespace_irregular * 2)
        score += min(12, obfuscated_url_count * 6)
        return int(round(min(100, score)))

    def estimate_typo_score(self, raw_text: str) -> int:
        if not raw_text:
            return 0
        elongated_words = len(re.findall(r"\b\w*([A-Za-z\u0621-\u064A])\1{2,}\w*\b", raw_text))
        mixed_script_words = len(self.MIXED_SCRIPT_WORD_REGEX.findall(raw_text))
        digit_inside_arabic_words = len(re.findall(r"\b[\u0621-\u064A]+\d+[\u0621-\u064A]*\b|\b[\u0621-\u064A]*\d+[\u0621-\u064A]+\b", raw_text))
        odd_separators = len(re.findall(r"[|_/\\~]{2,}", raw_text))
        bracket_dot_obfuscation = len(re.findall(r"\[\.\]", raw_text))
        score = 0.0
        score += min(24, elongated_words * 5)
        score += min(24, mixed_script_words * 6)
        score += min(18, digit_inside_arabic_words * 6)
        score += min(14, odd_separators * 4)
        score += min(20, bracket_dot_obfuscation * 7)
        return int(round(min(100, score)))

    def clean_spacing(self, text: str) -> str:
        for token in ["<URL>", "<OTP>", "<PHONE>", "<AMOUNT>", "<EMAIL>"]:
            text = re.sub(rf"\s*{re.escape(token)}\s*", f" {token} ", text)
        return self.MULTISPACE_REGEX.sub(" ", text).strip()

    def _clean_url(self, url: str) -> str:
        url = re.sub(r"\s+", "", url).strip()
        return url.rstrip(".,;!?)")

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result
