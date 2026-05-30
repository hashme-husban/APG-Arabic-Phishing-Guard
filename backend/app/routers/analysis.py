from __future__ import annotations

import time
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.config import get_settings
from app.dependencies import get_current_user, get_db
from app.models import AnalysisResult, Device, Report, User
from app.services.hybrid_analyzer import get_hybrid_analyzer
from app.services.intelligence_memory import record_analysis_indicators
from app.services.masking import mask_sensitive
from app.services.rate_limit import check_rate_limit, client_key

router = APIRouter(tags=["analysis"])


def _optional_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "known", "trusted", "contact"}:
        return True
    if text in {"false", "0", "no", "unknown", "stranger"}:
        return False
    return None


@router.post("/analyze")
@router.post("/analysis/analyze")
def analyze(payload: dict, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate_limit(client_key(request, "analyze"), limit=60, window_seconds=60)
    started = time.perf_counter()
    text = str(payload.get("input_text") or payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="input_text is required")
    if len(text) > 4000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="input_text is too long")
    source = str(payload.get("source") or "manual").lower()
    allowed_sources = {"manual", "sms", "email", "whatsapp", "notification", "link", "unknown"}
    if source not in allowed_sources:
        source = "unknown"
    device_label = str(payload.get("device_id") or payload.get("device_label") or "web-admin-test")[:80]
    device = db.query(Device).filter(Device.user_id == user.id, Device.device_label == device_label).first()
    if not device:
        device = Device(user_id=user.id, device_label=device_label, platform=str(payload.get("platform") or "android")[:50], app_version=str(payload.get("app_version") or "1.0.0")[:50])
        db.add(device)
        db.flush()
    sender_name = str(payload.get("sender_name") or payload.get("title") or "")[:120]
    sender = str(payload.get("sender") or sender_name or "")[:120]
    source_app = str(payload.get("source_app") or "")[:160]
    package_name = str(payload.get("packageName") or payload.get("package_name") or source_app or "")[:160]
    extra_urls = payload.get("urls") if isinstance(payload.get("urls"), list) else []
    is_known_contact = _optional_bool(payload.get("is_known_contact", payload.get("known_contact")))
    sender_trust = str(payload.get("sender_trust") or ("known" if is_known_contact is True else "unknown" if is_known_contact is False else "unknown"))[:40]
    analysis = get_hybrid_analyzer().analyze(
        text,
        source=source,
        sender=sender,
        package_name=package_name,
        extra_urls=extra_urls,
        is_known_contact=is_known_contact,
        sender_trust=sender_trust,
        sender_name=sender_name,
        source_app=source_app,
    )
    masked_text = mask_sensitive(text)
    result = AnalysisResult(
        user_id=user.id,
        device_id=device.id,
        source=source,
        input_text=text,
        masked_text=masked_text,
        detected_url=analysis.detected_url,
        risk_score=analysis.risk_score,
        classification=analysis.classification,
        reasons=analysis.reasons,
        matched_signals=analysis.matched_signals,
        recommendation=analysis.recommendation,
        needs_review=analysis.classification in {"dangerous", "suspicious"},
        review_status="pending" if analysis.classification in {"dangerous", "suspicious"} else "none",
        model_version=analysis.debug.get("analyzer_version", "APG-Hybrid-Analyzer"),
        response_time_ms=int((time.perf_counter() - started) * 1000),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    record_analysis_indicators(
        db,
        {
            "analysis_result": result,
            "debug": analysis.debug,
            "sender": sender,
            "extra_urls": extra_urls,
        },
        source=f"{source}_analysis",
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
    response = {
        "id": result.id,
        "risk_score": result.risk_score,
        "classification": result.classification,
        "masked_text": result.masked_text,
        "detected_url": result.detected_url,
        "reasons": result.reasons,
        "matched_signals": result.matched_signals,
        "recommendation": result.recommendation,
        "created_at": result.created_at,
        # New fields from Risk Engine v1 (null when using v5 fallback)
        "verdict": analysis.debug.get("verdict"),
        "risk_level": analysis.debug.get("risk_level"),
        "confidence": analysis.debug.get("confidence"),
        "message_category": analysis.debug.get("message_category"),
        "attack_type": analysis.debug.get("attack_type"),
        "user_action": analysis.debug.get("user_action"),
        "message_intent": analysis.debug.get("message_intent"),
        "intent_confidence": analysis.debug.get("intent_confidence"),
        # Entity intelligence — always present, null/false/[] when unavailable
        "claimed_entity": analysis.debug.get("claimed_entity"),
        "sender_entity": analysis.debug.get("sender_entity"),
        "domain_entity": analysis.debug.get("domain_entity"),
        "entity_conflict": analysis.debug.get("entity_conflict", False),
        "entity_policy_violations": analysis.debug.get("entity_policy_violations", []),
        "entity_summary": analysis.debug.get("entity_summary"),
        "behavioral_analysis": analysis.debug.get("behavioral_analysis"),
    }
    if not get_settings().is_production:
        response.update({
            "semantic_score": analysis.debug.get("semantic_score"),
            "lexical_score": analysis.debug.get("lexical_score"),
            "rule_score": analysis.debug.get("rule_score"),
            "url_score": analysis.debug.get("url_score"),
            "critical_floor": analysis.debug.get("critical_floor"),
            "model_loaded": analysis.debug.get("model_loaded"),
            "analyzer_version": analysis.debug.get("analyzer_version"),
            "policy_trace": analysis.debug.get("policy_trace"),
            "privacy_notes": analysis.debug.get("privacy_notes"),
        })
    return response


@router.get("/analysis/history")
def history(classification: str | None = None, source: str | None = None, search: str | None = None, page: int = 1, limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(AnalysisResult).filter(AnalysisResult.user_id == user.id)
    if classification and classification != "all":
        q = q.filter(AnalysisResult.classification == classification)
    if source and source != "all":
        q = q.filter(AnalysisResult.source == source)
    if search:
        q = q.filter(or_(AnalysisResult.masked_text.ilike(f"%{search}%"), AnalysisResult.source.ilike(f"%{search}%")))
    total = q.count()
    items = q.order_by(AnalysisResult.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [{"id": x.id, "risk_score": x.risk_score, "classification": x.classification, "masked_text": x.masked_text, "source": x.source, "created_at": x.created_at, "detected_url": x.detected_url} for x in items], "total": total, "page": page, "limit": limit}


@router.get("/analysis/{analysis_id}")
def detail(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(AnalysisResult, analysis_id)
    if not item or (item.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="analysis not found")
    return {"id": item.id, "risk_score": item.risk_score, "classification": item.classification, "masked_text": item.masked_text, "detected_url": item.detected_url, "reasons": item.reasons, "matched_signals": item.matched_signals, "recommendation": item.recommendation, "source": item.source, "created_at": item.created_at}


@router.post("/analysis/ocr-image")
async def ocr_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    check_rate_limit(client_key(request, "ocr"), limit=20, window_seconds=60)
    settings = get_settings()
    if not settings.ocr_enabled:
        raise HTTPException(status_code=503, detail="OCR service is not enabled on this server")

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}
    if content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="Unsupported image type. Use JPEG, PNG or WebP.")

    max_bytes = settings.ocr_max_image_mb * 1024 * 1024
    image_bytes = await file.read()
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Maximum allowed size is {settings.ocr_max_image_mb}MB.",
        )

    from app.services.image_ocr_service import extract_text_from_image_bytes
    result = extract_text_from_image_bytes(
        image_bytes,
        content_type=content_type,
        languages=settings.ocr_languages,
        max_mb=settings.ocr_max_image_mb,
        engine=settings.ocr_engine,
        paddle_service_url=settings.ocr_paddle_service_url,
        paddle_timeout=settings.ocr_paddle_timeout_seconds,
    )

    if not result.success:
        return {
            "success": False,
            "data": None,
            "message": "OCR extraction did not return text",
            "error": "OCR_FAILED",
        }

    return {
        "success": True,
        "data": {
            "extracted_text": result.extracted_text,
            "normalized_text": result.normalized_text,
            "extracted_urls": result.extracted_urls,
            "engine": result.engine,
            "language": result.language,
        },
        "message": "Text extracted successfully",
        "error": None,
    }


@router.post("/reports")
def create_report(payload: dict, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate_limit(client_key(request, "reports"), limit=30, window_seconds=60)
    analysis_id = payload.get("analysis_id")
    report_type = str(payload.get("report_type") or "inaccurate_result")
    note = str(payload.get("message") or payload.get("note") or "")[:2000]
    if analysis_id:
        analysis = db.get(AnalysisResult, int(analysis_id))
        if not analysis or (analysis.user_id != user.id and user.role != "admin"):
            raise HTTPException(status_code=404, detail="analysis not found")
    item = Report(analysis_id=analysis_id, user_id=user.id, report_type=report_type, message=note, status="new")
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "status": item.status}
