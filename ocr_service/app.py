from __future__ import annotations

import io
import logging
import re
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps

logger = logging.getLogger("apg_ocr")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="APG OCR Microservice", docs_url=None, redoc_url=None)

_SUPPORTED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}
_PILLOW_FORMAT_MAP = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
_MAX_SIDE_PX = 2400
_MAX_MB = 8

_paddle_instance = None


def _get_paddle():
    global _paddle_instance
    if _paddle_instance is None:
        from paddleocr import PaddleOCR
        logger.info("Initialising PaddleOCR Arabic model…")
        _paddle_instance = PaddleOCR(lang="ar", use_angle_cls=False, show_log=False)
        logger.info("PaddleOCR ready")
    return _paddle_instance


def _detect_format(image_bytes: bytes) -> Optional[str]:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return _PILLOW_FORMAT_MAP.get((img.format or "").upper())
    except Exception:
        return None


def _parse_result(result) -> tuple[str, list[str]]:
    """Extract text lines from PaddleOCR output, sorted top-to-bottom by bbox y-coordinate."""
    if not result:
        return "", []
    page = result[0] if result else None
    if not page:
        return "", []

    def _center_y(item):
        try:
            bbox = item[0]
            return (bbox[0][1] + bbox[2][1]) / 2
        except Exception:
            return 0

    try:
        sorted_lines = sorted(page, key=_center_y)
    except Exception:
        sorted_lines = page

    lines_text: list[str] = []
    for line in sorted_lines:
        try:
            text = line[1][0]
            if text and text.strip():
                lines_text.append(text.strip())
        except (IndexError, TypeError):
            continue

    return "\n".join(lines_text), lines_text


@app.get("/health")
def health():
    return {"status": "ok", "service": "apg-ocr-microservice"}


@app.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in _SUPPORTED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {content_type}")

    image_bytes = await file.read()

    if len(image_bytes) > _MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image too large (max {_MAX_MB}MB)")

    if content_type == "application/octet-stream":
        detected = _detect_format(image_bytes)
        if not detected:
            return JSONResponse(content={
                "success": False,
                "engine": "paddleocr",
                "text": "",
                "lines": [],
                "error": "Cannot identify image format from bytes",
            })
        content_type = detected

    try:
        img = Image.open(io.BytesIO(image_bytes))
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > _MAX_SIDE_PX:
            factor = _MAX_SIDE_PX / max(w, h)
            img = img.resize((int(w * factor), int(h * factor)), Image.LANCZOS)
        img_array = np.array(img)
        ocr = _get_paddle()
        result = ocr.ocr(img_array, cls=False)
        text, lines = _parse_result(result)
        return {
            "success": True,
            "engine": "paddleocr",
            "text": text,
            "lines": lines,
            "error": None,
        }
    except Exception as exc:
        logger.error("PaddleOCR failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "engine": "paddleocr",
                "text": "",
                "lines": [],
                "error": str(exc),
            },
        )
