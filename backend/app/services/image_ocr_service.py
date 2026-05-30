from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urlunparse

# PIL — required for image loading; also used by Tesseract preprocessing
try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# Tesseract — fallback OCR engine
try:
    import pytesseract
    _TESSERACT_AVAILABLE = _PIL_AVAILABLE
except ImportError:
    _TESSERACT_AVAILABLE = False

_SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_PILLOW_FORMAT_MAP = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
_MAX_SIDE_PX = 2400
_MIN_SIDE_PX = 600  # upscale if smaller than this


@dataclass
class OcrResult:
    success: bool
    extracted_text: str
    normalized_text: str
    extracted_urls: list[str] = field(default_factory=list)
    confidence: Optional[float] = None
    engine: str = "tesseract"
    language: str = "ara+eng"
    error: Optional[str] = None


# ── public helpers ────────────────────────────────────────────────────────────

def is_tesseract_available() -> bool:
    if not _TESSERACT_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def get_tesseract_version() -> str:
    try:
        v = pytesseract.get_tesseract_version()
        return str(v)
    except Exception:
        return "unavailable"


def is_paddle_microservice_available(service_url: str, timeout: int = 5) -> bool:
    """Probe the OCR microservice /health endpoint. Returns False on any failure."""
    if not service_url:
        return False
    try:
        import httpx
        parsed = urlparse(service_url)
        health_url = urlunparse((parsed.scheme, parsed.netloc, "/health", "", "", ""))
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(health_url)
        return resp.status_code == 200
    except Exception:
        return False


def _detect_content_type_from_bytes(image_bytes: bytes) -> Optional[str]:
    """Probe actual image format using Pillow. Returns content-type string or None."""
    if not _PIL_AVAILABLE:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return _PILLOW_FORMAT_MAP.get((img.format or "").upper())
    except Exception:
        return None


# ── main entry point ──────────────────────────────────────────────────────────

def extract_text_from_image_bytes(
    image_bytes: bytes,
    content_type: str,
    languages: str = "ara+eng",
    max_mb: int = 5,
    engine: str = "auto",
    paddle_service_url: str = "",
    paddle_timeout: int = 20,
) -> OcrResult:
    ct = (content_type or "").lower().split(";")[0].strip()

    # For generic octet-stream, probe actual format with Pillow before deciding
    if ct == "application/octet-stream":
        detected = _detect_content_type_from_bytes(image_bytes)
        if detected:
            ct = detected
        else:
            return OcrResult(
                success=False,
                extracted_text="",
                normalized_text="",
                language=languages,
                error="Unsupported image format: could not identify image type from bytes",
            )

    if ct not in _SUPPORTED_CONTENT_TYPES:
        return OcrResult(
            success=False,
            extracted_text="",
            normalized_text="",
            language=languages,
            error=f"Unsupported image type: {ct}",
        )

    if len(image_bytes) > max_mb * 1024 * 1024:
        return OcrResult(
            success=False,
            extracted_text="",
            normalized_text="",
            language=languages,
            error=f"Image too large (max {max_mb}MB)",
        )

    engine_name = (engine or "auto").lower().strip()

    # explicit tesseract
    if engine_name == "tesseract":
        if not _TESSERACT_AVAILABLE:
            return OcrResult(
                success=False,
                extracted_text="",
                normalized_text="",
                language=languages,
                error="OCR engine not available on this server",
            )
        return _run_tesseract_ocr(image_bytes, languages)

    # explicit paddle / paddle_microservice — require microservice URL
    if engine_name in ("paddle", "paddle_microservice"):
        if not paddle_service_url:
            return OcrResult(
                success=False,
                extracted_text="",
                normalized_text="",
                language=languages,
                error="PaddleOCR microservice not configured (set OCR_PADDLE_SERVICE_URL)",
            )
        return _call_paddle_microservice(image_bytes, ct, paddle_service_url, paddle_timeout, languages)

    # auto: try microservice if URL configured, fall back to Tesseract on failure
    if engine_name == "auto":
        if paddle_service_url:
            result = _call_paddle_microservice(image_bytes, ct, paddle_service_url, paddle_timeout, languages)
            if result.success:
                return result
            # microservice failed — fall through to Tesseract
        if _TESSERACT_AVAILABLE:
            return _run_tesseract_ocr(image_bytes, languages)
        return OcrResult(
            success=False,
            extracted_text="",
            normalized_text="",
            language=languages,
            error="No OCR engine available on this server",
        )

    # unknown engine value — treat as auto
    if _TESSERACT_AVAILABLE:
        return _run_tesseract_ocr(image_bytes, languages)
    return OcrResult(
        success=False,
        extracted_text="",
        normalized_text="",
        language=languages,
        error="No OCR engine available on this server",
    )


# ── PaddleOCR microservice call ───────────────────────────────────────────────

def _call_paddle_microservice(
    image_bytes: bytes,
    content_type: str,
    service_url: str,
    timeout: int,
    languages: str,
) -> OcrResult:
    try:
        import httpx
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                service_url,
                files={"file": ("image", image_bytes, content_type)},
            )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                raw = data.get("text", "")
                normalized = _clean(raw)
                urls = extract_urls(normalized)
                return OcrResult(
                    success=True,
                    extracted_text=raw.strip(),
                    normalized_text=normalized,
                    extracted_urls=urls,
                    engine="paddle",
                    language=languages,
                )
            return OcrResult(
                success=False,
                extracted_text="",
                normalized_text="",
                engine="paddle",
                language=languages,
                error=data.get("error") or "OCR microservice returned failure",
            )
        return OcrResult(
            success=False,
            extracted_text="",
            normalized_text="",
            engine="paddle",
            language=languages,
            error=f"OCR microservice returned HTTP {response.status_code}",
        )
    except Exception as exc:
        return OcrResult(
            success=False,
            extracted_text="",
            normalized_text="",
            engine="paddle",
            language=languages,
            error=str(exc),
        )


# ── Tesseract runner ──────────────────────────────────────────────────────────

def _run_tesseract_ocr(image_bytes: bytes, languages: str) -> OcrResult:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = _preprocess(img)
        # PSM 6: uniform text block — best for phishing screenshots with 1–2 paragraphs
        raw_text = pytesseract.image_to_string(img, lang=languages, config="--psm 6")
        normalized = _clean(raw_text)
        urls = extract_urls(normalized)
        return OcrResult(
            success=True,
            extracted_text=raw_text.strip(),
            normalized_text=normalized,
            extracted_urls=urls,
            engine="tesseract",
            language=languages,
        )
    except Exception as exc:
        return OcrResult(
            success=False,
            extracted_text="",
            normalized_text="",
            engine="tesseract",
            language=languages,
            error=str(exc),
        )


def _parse_paddle_result(result) -> str:
    """Extract text from PaddleOCR output, preserving top-to-bottom line order.
    Kept as utility for unit tests; production calls go through the microservice."""
    if not result:
        return ""
    page = result[0] if len(result) > 0 else None
    if not page:
        return ""

    def _bbox_center_y(item):
        try:
            bbox = item[0]
            return (bbox[0][1] + bbox[2][1]) / 2
        except Exception:
            return 0

    try:
        sorted_lines = sorted(page, key=_bbox_center_y)
    except Exception:
        sorted_lines = page

    texts = []
    for line in sorted_lines:
        try:
            text = line[1][0]
            if text and text.strip():
                texts.append(text.strip())
        except (IndexError, TypeError):
            continue
    return "\n".join(texts)


# ── Tesseract preprocessing ───────────────────────────────────────────────────

def _preprocess(img: "Image.Image") -> "Image.Image":
    # 1. EXIF auto-rotation
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # 2. Normalise mode
    if img.mode == "RGBA":
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # 3. Downscale very large images
    w, h = img.size
    if max(w, h) > _MAX_SIDE_PX:
        factor = _MAX_SIDE_PX / max(w, h)
        img = img.resize((int(w * factor), int(h * factor)), Image.LANCZOS)

    # 4. Upscale small images (Tesseract accuracy degrades below 300 DPI equivalent)
    w, h = img.size
    if min(w, h) < _MIN_SIDE_PX:
        scale = min(3.0, _MIN_SIDE_PX / min(w, h))
        new_w = min(int(w * scale), _MAX_SIDE_PX)
        new_h = min(int(h * scale), _MAX_SIDE_PX)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # 5. Greyscale
    img = img.convert("L")

    # 6. Contrast enhancement
    img = ImageEnhance.Contrast(img).enhance(1.4)

    # 7. Light sharpening
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=110, threshold=3))

    return img


# ── text cleaning ─────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    text = repair_ocr_urls(text)
    text = _remove_garbage_lines(text)
    return text.strip()


def _remove_garbage_lines(text: str) -> str:
    """
    Conservatively drop lines that are pure OCR noise.
    A line is kept if it has: Arabic text, a URL, or Latin words >= 3 chars.
    Single characters, stray punctuation, isolated vertical bars, etc. are dropped.
    Arabic text is NEVER removed.
    """
    result = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        if re.search(r"[؀-ۿ]", stripped):
            result.append(line)
            continue
        if re.search(r"(?:https?://|www\.)\S", stripped, re.IGNORECASE):
            result.append(line)
            continue
        if re.search(r"[A-Za-z]{3,}", stripped):
            result.append(line)
            continue
        if re.search(r"\d{3,}", stripped):
            result.append(line)
            continue
    return "\n".join(result)


# ── URL helpers ───────────────────────────────────────────────────────────────

def repair_ocr_urls(text: str) -> str:
    text = re.sub(
        r"\b(https?)\s*:\s*/\s*/\s*",
        lambda m: m.group(1).lower() + "://",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bwww\s*\.\s*", "www.", text, flags=re.IGNORECASE)
    text = re.sub(r"([A-Za-z0-9-])\s+\.\s+([A-Za-z0-9])", r"\1.\2", text)
    text = re.sub(r"\s*([/?=&])\s*", r"\1", text)
    return text


def extract_urls(text: str) -> list[str]:
    pattern = re.compile(
        r"((?:https?://|www\.)[^\s<>\"،؛؟]+"
        r"|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s<>\"،؛؟]*)?)",
        re.IGNORECASE,
    )
    results: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        url = _clean_url(match.group(0))
        if url and "." in url and url not in seen:
            results.append(url)
            seen.add(url)
    return results


def _clean_url(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[)\].,،؛؟!]+$", "", value)
    value = re.sub(r"^[(\[]+", "", value)
    return value
