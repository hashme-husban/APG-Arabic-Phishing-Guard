import re

EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
PHONE_RE = re.compile(r"\b(\d{3})(\d{4,})(\d{3})\b")
OTP_RE = re.compile(r"(?i)\b(otp|رمز\s*التحقق|verification\s*code)[:\s-]*\d{4,8}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
PASSWORD_RE = re.compile(r"(?i)(password|كلمة\s*المرور)[:\s-]+\S+")
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def mask_sensitive(text: str) -> str:
    if not text:
        return ""
    value = EMAIL_RE.sub(lambda m: f"{m.group(1)}***{m.group(3)}", text)
    value = PHONE_RE.sub(lambda m: f"{m.group(1)}****{m.group(3)}", value)
    value = OTP_RE.sub(lambda m: f"{m.group(1)} ******", value)
    value = CARD_RE.sub("**** **** **** ****", value)
    value = PASSWORD_RE.sub(lambda m: f"{m.group(1)} ******", value)
    return value


def detect_url(text: str) -> str | None:
    match = URL_RE.search(text or "")
    return match.group(0) if match else None
