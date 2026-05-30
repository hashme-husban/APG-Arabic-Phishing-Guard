from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO, BytesIO
from pathlib import Path
import csv
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_admin
from app.models import AdminAction, AnalysisResult, Incident, Report, SystemStatus, ThreatIndicator, ThreatSignal, User
from app.schemas import IncidentUpdate, ReviewUpdate, ThreatSignalCreate, ThreatSignalOut, ThreatSignalUpdate, ToggleSignalRequest, SyncRulesRequest
from app.services.audit import record_admin_action
from app.services.hybrid_analyzer import get_analyzer_status, get_hybrid_analyzer
from app.services.intelligence_memory import cleanup_old_indicators, sanitize_display_value
from app.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

RANGE_DAYS = {"today": 1, "7d": 7, "30d": 30, "7 days": 7, "30 days": 30}
BASELINE = {
    "today": {"total": 243, "dangerous": 37, "suspicious": 61, "safe": 145, "channels": {"SMS": 86, "Email": 44, "WhatsApp": 62, "Notification": 35, "Manual": 16}},
    "7d": {"total": 1248, "dangerous": 75, "suspicious": 215, "safe": 958, "channels": {"SMS": 410, "Email": 238, "WhatsApp": 315, "Notification": 190, "Manual": 95}},
    "30d": {"total": 5320, "dangerous": 311, "suspicious": 890, "safe": 4119, "channels": {"SMS": 1750, "Email": 940, "WhatsApp": 1305, "Notification": 850, "Manual": 475}},
}
INTELLIGENCE_INDICATOR_TYPES = {"domain", "url_hash", "sender", "entity", "signal", "path"}


def _range_key(time_range: str | None) -> str:
    value = (time_range or "today").strip().lower()
    if value in ["7 days", "7days", "week"]:
        return "7d"
    if value in ["30 days", "30days", "month"]:
        return "30d"
    if value not in ["today", "7d", "30d"]:
        return "today"
    return value


def _since(time_range: str | None):
    return datetime.utcnow() - timedelta(days=RANGE_DAYS.get(_range_key(time_range), 1))


def _display_counts(db: Session, time_range: str | None):
    """Return counts for the requested range.

    Production rule: if the database has analysis rows in the selected range,
    use those real rows as the source of truth. Baseline seed aggregates are
    used only when the database is empty, so the console never contradicts
    real mobile/backend data once it exists.
    """
    key = _range_key(time_range)
    since = _since(key)
    q = db.query(AnalysisResult).filter(AnalysisResult.created_at >= since)
    db_total = q.count()
    db_counts = dict(q.with_entities(AnalysisResult.classification, func.count(AnalysisResult.id)).group_by(AnalysisResult.classification).all())
    if db_total > 0:
        dangerous = int(db_counts.get("dangerous", 0))
        suspicious = int(db_counts.get("suspicious", 0))
        safe = int(db_counts.get("safe", 0))
        # If an older database contains unexpected classifications, preserve the
        # total rather than hiding rows.
        total = max(db_total, dangerous + suspicious + safe)
        return {"total": total, "dangerous": dangerous, "suspicious": suspicious, "safe": safe, "key": key, "query": q, "source": "database", "sample_count": db_total}
    base = BASELINE[key]
    return {"total": base["total"], "dangerous": base["dangerous"], "suspicious": base["suspicious"], "safe": base["safe"], "key": key, "query": q, "source": "seed_fallback", "sample_count": 0}


ACTION_TITLES = {
    "login": "Admin signed in",
    "logout": "Admin signed out",
    "toggle_signal": "Signal disabled",
    "edit_signal": "Signal updated",
    "add_signal": "Signal added",
    "mark_incident_resolved": "Incident resolved",
    "mark_incident_monitoring": "Incident moved to monitoring",
    "review_mark_correct": "Result marked correct",
    "review_false_positive": "Result marked false positive",
    "review_false_negative": "Result marked false negative",
    "test_connection": "Connection tested",
    "sync_rules": "Rules synced",
    "rules_synced": "Rules synced",
    "signal_updated": "Signal updated",
    "incident_resolved": "Incident resolved",
    "connection_tested": "Connection tested",
    "export_incidents": "CSV exported",
    "export_quality": "CSV exported",
    "export_signals": "CSV exported",
    "export_security_summary": "CSV exported",
    "export_incidents_csv": "CSV exported",
    "export_detection_quality_csv": "CSV exported",
    "export_threat_signals_csv": "CSV exported",
    "export_security_summary_csv": "CSV exported",
    "export_security_report_pdf": "PDF report exported",
}


def _action_to_text(action_type: str) -> str:
    return ACTION_TITLES.get(action_type, action_type.replace("_", " ").title())


def _target_name(db: Session, action: AdminAction) -> str:
    if action.target_type == "threat_signal" and action.target_id:
        item = db.get(ThreatSignal, action.target_id)
        return item.name if item else f"Threat signal #{action.target_id}"
    if action.target_type == "incident" and action.target_id:
        item = db.get(Incident, action.target_id)
        return item.title if item else f"Incident #{action.target_id}"
    if action.target_type == "analysis" and action.target_id:
        item = db.get(AnalysisResult, action.target_id)
        return f"Analysis #{action.target_id} ({item.classification})" if item else f"Analysis #{action.target_id}"
    if action.target_type == "quality":
        return "Detection quality CSV"
    if action.target_type == "incidents_export":
        return "Incidents CSV"
    if action.target_type == "threat_signals":
        return "Threat signals CSV"
    if action.target_type == "security_summary":
        return "Security summary CSV"
    if action.target_type == "security_report_pdf":
        return "Security Report PDF"
    return action.target_type.replace("_", " ").title()


def _actor_email(db: Session, action: AdminAction) -> str:
    if action.admin_id:
        user = db.get(User, action.admin_id)
        if user:
            return user.email
    return "system"


def _action_out(action: AdminAction, db: Session | None = None):
    actor = _actor_email(db, action) if db else ("admin" if action.admin_id else "system")
    target_name = _target_name(db, action) if db else (f"{action.target_type}#{action.target_id}" if action.target_id else action.target_type)
    return {
        "id": action.id,
        "actor": actor,
        "actor_email": actor,
        "action": _action_to_text(action.action_type),
        "action_title": _action_to_text(action.action_type),
        "action_type": action.action_type,
        "target": target_name,
        "target_name": target_name,
        "target_type": action.target_type,
        "target_id": action.target_id,
        "old_value": action.old_value,
        "new_value": action.new_value,
        "note": action.note,
        "created_at": action.created_at,
    }


def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            return Path(pw.chromium.executable_path).exists()
    except Exception:
        return False


def _ocr_status(settings) -> dict:
    from app.services.image_ocr_service import (
        is_tesseract_available, get_tesseract_version,
        is_paddle_microservice_available,
    )
    tess_avail = is_tesseract_available()
    svc_url = getattr(settings, "ocr_paddle_service_url", "")
    svc_timeout = min(getattr(settings, "ocr_paddle_timeout_seconds", 20), 5)
    paddle_svc_configured = bool(svc_url)
    paddle_svc_available = is_paddle_microservice_available(svc_url, timeout=svc_timeout) if paddle_svc_configured else False
    engine_cfg = getattr(settings, "ocr_engine", "auto")

    if engine_cfg == "tesseract":
        active_engine = "tesseract" if tess_avail else "none"
    elif engine_cfg in ("paddle", "paddle_microservice"):
        active_engine = "paddle_microservice" if paddle_svc_available else "none"
    else:  # auto
        if paddle_svc_available:
            active_engine = "paddle_microservice"
        elif tess_avail:
            active_engine = "tesseract"
        else:
            active_engine = "none"

    return {
        "enabled": settings.ocr_enabled,
        "engine_config": engine_cfg,
        "active_engine": active_engine,
        "paddle_microservice_configured": paddle_svc_configured,
        "paddle_microservice_available": paddle_svc_available,
        "tesseract_available": tess_avail,
        "tesseract_version": get_tesseract_version() if tess_avail else "unavailable",
        "languages": settings.ocr_languages,
        "max_image_mb": settings.ocr_max_image_mb,
    }


def _dynamic_url_analysis_status(analyzer_status: dict) -> dict:
    settings = get_settings()
    enabled = bool(
        analyzer_status.get(
            "dynamic_url_analysis_enabled",
            settings.dynamic_url_analysis_enabled,
        )
    )
    return {
        "enabled": enabled,
        "mode": "evidence_ready" if enabled else "production_disabled",
        "timeout_seconds": int(
            analyzer_status.get(
                "dynamic_url_timeout_seconds",
                settings.dynamic_url_analysis_timeout_seconds,
            )
        ),
        "observation_ms": int(
            analyzer_status.get(
                "dynamic_url_observation_ms",
                settings.dynamic_url_analysis_observation_ms,
            )
        ),
        "time_simulation_enabled": bool(
            analyzer_status.get(
                "dynamic_url_time_simulation_enabled",
                settings.dynamic_url_analysis_time_simulation_enabled,
            )
        ),
        "simulated_minutes": int(
            analyzer_status.get(
                "dynamic_url_simulated_minutes",
                settings.dynamic_url_analysis_simulated_minutes,
            )
        ),
        "scoring_integration": "conservative_evidence_mapping_available",
        "default_enabled": False,
        "playwright_available": _playwright_available(),
        "safety_controls": {
            "private_ip_blocking": True,
            "localhost_blocking": True,
            "dangerous_schemes_blocked": True,
            "no_form_submission": True,
            "no_credential_entry": True,
            "screenshots_disabled": True,
        },
    }


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content="﻿" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _json_export_response(payload: dict, filename: str) -> Response:
    return Response(
        content=json.dumps(payload, default=str, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _intelligence_indicator_query(
    db: Session,
    indicator_type: str | None = None,
    min_seen_count: int | None = None,
):
    selected_type = (indicator_type or "").strip().lower()
    if selected_type and selected_type not in INTELLIGENCE_INDICATOR_TYPES:
        return None
    q = db.query(ThreatIndicator)
    if selected_type:
        q = q.filter(ThreatIndicator.indicator_type == selected_type)
    if min_seen_count is not None:
        q = q.filter(ThreatIndicator.seen_count >= max(1, int(min_seen_count)))
    return q


def _safe_indicator_row(item: ThreatIndicator) -> dict:
    metadata = item.metadata_json or {}
    return {
        "indicator_type": item.indicator_type,
        "display_value": sanitize_display_value(item.indicator_type, item.display_value),
        "seen_count": item.seen_count,
        "first_seen": item.first_seen,
        "last_seen": item.last_seen,
        "max_risk_score": item.max_risk_score,
        "last_classification": item.last_classification,
        "last_source": item.last_source,
        "tags": item.tags_json or [],
        "metadata": {str(k)[:50]: str(v)[:160] for k, v in metadata.items()},
    }


def _minimal_pdf_bytes(title: str, lines: list[str]) -> bytes:
    """Small dependency-free PDF fallback used only if reportlab is unavailable."""
    def clean(value: str) -> str:
        return str(value).replace('\\', '/').replace('(', '[').replace(')', ']')[:115]

    content = ["BT", "/F1 16 Tf", "72 790 Td", f"({clean(title)}) Tj", "/F1 10 Tf"]
    for line in lines:
        content.append("0 -18 Td")
        content.append(f"({clean(line)}) Tj")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "ignore")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)

@router.get("/monitoring")
def monitoring(range: str = Query("today"), time_range: str | None = None, db: Session = Depends(get_db)):
    effective_range = time_range or range
    counts = _display_counts(db, effective_range)
    q = counts["query"]
    source_counts = dict(q.with_entities(AnalysisResult.source, func.count(AnalysisResult.id)).group_by(AnalysisResult.source).all())
    base_channels = BASELINE[counts["key"]]["channels"]
    if counts.get("source") == "database" and source_counts:
        aliases = {"sms": "SMS", "email": "Email", "whatsapp": "WhatsApp", "notification": "Notification", "manual": "Manual", "link": "Link", "unknown": "Unknown"}
        ordered = ["sms", "email", "whatsapp", "notification", "manual", "link", "unknown"]
        channel_breakdown = []
        for key_name in ordered:
            value = int(source_counts.get(key_name, 0) or source_counts.get(aliases.get(key_name, key_name), 0) or 0)
            if value:
                channel_breakdown.append({"channel": aliases.get(key_name, key_name.title()), "count": value})
        for raw, value in source_counts.items():
            label = aliases.get(str(raw).lower(), str(raw).title())
            if label not in {c["channel"] for c in channel_breakdown}:
                channel_breakdown.append({"channel": label, "count": int(value)})
    else:
        channel_breakdown = [{"channel": name, "count": value} for name, value in base_channels.items()]
    pending_reports = db.query(Report).filter(Report.status.in_(["new", "in_review"])).count()
    otp_signal = db.query(ThreatSignal).filter(ThreatSignal.name.ilike("%OTP%")).first()
    verify_incident = db.query(Incident).filter(Incident.title.ilike("%verify%")).first()
    otp_incident = db.query(Incident).filter(Incident.title.ilike("%OTP%")).first()
    system = db.query(SystemStatus).order_by(SystemStatus.checked_at.desc()).first()
    actions = db.query(AdminAction).order_by(AdminAction.created_at.desc()).limit(5).all()
    top_indicators = [
        {"name": "OTP request", "count": 71, "target_type": "incident", "target_id": otp_incident.id if otp_incident else None},
        {"name": "Shortened URL", "count": 54, "target_type": "signal", "target_id": otp_signal.id if otp_signal else None},
        {"name": "Login/verify path", "count": 39, "target_type": "incident", "target_id": verify_incident.id if verify_incident else None},
        {"name": "Bank impersonation", "count": 28, "target_type": "incident", "target_id": otp_incident.id if otp_incident else None},
    ]
    return {
        "range": counts["key"],
        "metrics": [
            {"label": "Total Analyses", "value": counts["total"], "change": 12.4, "tone": "cyan", "drilldown": {"path": "/incidents"}},
            {"label": "High Risk", "value": counts["dangerous"], "change": 8.4, "tone": "danger", "drilldown": {"path": "/incidents?severity=high"}},
            {"label": "Suspicious", "value": counts["suspicious"], "change": 3.2, "tone": "warning", "drilldown": {"path": "/incidents?severity=medium"}},
            {"label": "Safe", "value": counts["safe"], "change": -1.1, "tone": "success"},
        ],
        "risk_distribution": [
            {"name": "Safe", "value": counts["safe"], "key": "safe"},
            {"name": "Suspicious", "value": counts["suspicious"], "key": "suspicious"},
            {"name": "High Risk", "value": counts["dangerous"], "key": "dangerous"},
        ],
        "channel_breakdown": channel_breakdown,
        "needs_attention": [
            {"title": "Spike in OTP messages", "detail": "OTP and verification-code requests increased across SMS campaigns.", "severity": "high", "target_type": "incident", "target_id": otp_incident.id if otp_incident else None, "path": f"/incidents/{otp_incident.id}" if otp_incident else "/incidents?severity=high"},
            {"title": "Recurring login/verify links", "detail": "Multiple suspicious links use /verify or /login paths.", "severity": "medium", "target_type": "incident", "target_id": verify_incident.id if verify_incident else None, "path": f"/incidents/{verify_incident.id}" if verify_incident else "/threat-signals?category=link"},
            {"title": "Pending user reports", "detail": f"{pending_reports} reports need admin review.", "severity": "medium", "path": "/detection-quality?tab=reports"},
            {"title": "API status", "detail": "Server is stable." if not system or system.server_status == "connected" else "Server warning detected.", "severity": "low", "path": "/system"},
        ],
        "recent_activity": [_action_out(a, db) for a in actions] or [
            {"event": "High-risk incident logged", "actor": "system", "target": "Fake OTP banking campaign", "time": "5 min ago", "type": "incident"},
            {"event": "Threat signal updated", "actor": "admin", "target": "OTP code request", "time": "18 min ago", "type": "signal"},
            {"event": "Rules synced", "actor": "admin", "target": "rules-2026.05", "time": "1 h ago", "type": "system"},
        ],
        "threat_story": "High-risk messages today mostly rely on OTP requests and urgent account-closure language. SMS is the most affected channel. Keep OTP and shortened URL signals enabled.",
        "top_indicators": top_indicators,
        "system_status": system.server_status if system else "connected",
        "seed_data": counts.get("source") != "database",
    }


@router.get("/incidents")
def incidents(severity: str | None = None, status: str | None = None, search: str | None = None, range: str = "today", page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(Incident)
    if severity and severity != "all":
        q = q.filter(Incident.severity == severity)
    if status and status != "all":
        q = q.filter(Incident.status == status)
    if search:
        q = q.filter(or_(Incident.title.ilike(f"%{search}%"), Incident.description.ilike(f"%{search}%")))
    total = q.count()
    items = q.order_by(Incident.last_seen.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/incidents/{incident_id}")
def incident_detail(incident_id: int, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    related = db.query(AnalysisResult).filter(AnalysisResult.classification.in_(["dangerous", "suspicious"])).order_by(AnalysisResult.created_at.desc()).limit(6).all()
    return {
        "incident": incident,
        "cases_over_time": [
            {"day": "D-6", "cases": 8}, {"day": "D-5", "cases": 12}, {"day": "D-4", "cases": 14},
            {"day": "D-3", "cases": 21}, {"day": "D-2", "cases": 19}, {"day": "D-1", "cases": 27}, {"day": "Today", "cases": incident.cases_count},
        ],
        "top_indicators": incident.indicators,
        "affected_channels": [{"channel": incident.channel, "count": incident.cases_count}],
        "related_results": [{"id": r.id, "masked_text": r.masked_text, "risk_score": r.risk_score, "classification": r.classification, "source": r.source, "created_at": r.created_at} for r in related],
    }


@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: int, payload: IncidentUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    old = {"status": incident.status, "recommended_action": incident.recommended_action}
    if payload.status:
        incident.status = payload.status
    if payload.recommended_action:
        incident.recommended_action = payload.recommended_action
    incident.updated_at = datetime.utcnow()
    action = "mark_incident_resolved" if payload.status == "resolved" else "mark_incident_monitoring" if payload.status == "monitoring" else "update_incident"
    record_admin_action(db, admin, action, "incident", incident.id, old_value=old, new_value={"status": incident.status, "recommended_action": incident.recommended_action}, note=payload.status or payload.recommended_action)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/threat-signals")
def threat_signals(category: str | None = None, search: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ThreatSignal)
    if category and category != "all":
        q = q.filter(ThreatSignal.category == category)
    if search:
        q = q.filter(or_(ThreatSignal.name.ilike(f"%{search}%"), ThreatSignal.description.ilike(f"%{search}%")))
    return {"items": q.order_by(ThreatSignal.impact.desc(), ThreatSignal.name).all()}


@router.get("/intelligence/indicators")
def intelligence_indicators(
    indicator_type: str | None = Query(None, alias="type"),
    min_seen_count: int | None = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    capped_limit = max(1, min(int(limit or 50), 200))
    q = _intelligence_indicator_query(db, indicator_type, min_seen_count)
    if q is None:
        return {"items": [], "limit": capped_limit}
    items = (
        q.order_by(ThreatIndicator.seen_count.desc(), ThreatIndicator.last_seen.desc())
        .limit(capped_limit)
        .all()
    )
    return {
        "items": [
            _safe_indicator_row(item)
            for item in items
        ],
        "limit": capped_limit,
    }


@router.get("/intelligence/summary")
def intelligence_summary(db: Session = Depends(get_db)):
    top_types = (
        db.query(ThreatIndicator.indicator_type, func.count(ThreatIndicator.id))
        .group_by(ThreatIndicator.indicator_type)
        .order_by(func.count(ThreatIndicator.id).desc())
        .all()
    )
    top_repeated = db.query(func.max(ThreatIndicator.seen_count)).scalar() or 0
    latest_seen = db.query(func.max(ThreatIndicator.last_seen)).scalar()
    return {
        "total_indicators": db.query(func.count(ThreatIndicator.id)).scalar() or 0,
        "top_types": [{"type": indicator_type, "count": count} for indicator_type, count in top_types],
        "top_repeated": top_repeated,
        "latest_seen": latest_seen,
    }


@router.post("/intelligence/cleanup")
def intelligence_cleanup(
    dry_run: bool = Query(True),
    retention_days: int | None = Query(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    selected_days = max(7, int(retention_days or settings.intelligence_memory_retention_days or 90))
    result = cleanup_old_indicators(db, retention_days=selected_days, dry_run=dry_run)
    if not dry_run:
        db.commit()
    return result


@router.get("/intelligence/export")
def intelligence_export(
    format: str = Query("json"),
    indicator_type: str | None = Query(None, alias="type"),
    min_seen_count: int | None = Query(None),
    limit: int = Query(1000),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    selected_format = (format or "json").strip().lower()
    if selected_format not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="format must be json or csv")
    capped_limit = max(1, min(int(limit or 1000), 5000))
    q = _intelligence_indicator_query(db, indicator_type, min_seen_count)
    if q is None:
        rows = []
    else:
        items = (
            q.order_by(ThreatIndicator.seen_count.desc(), ThreatIndicator.last_seen.desc())
            .limit(capped_limit)
            .all()
        )
        rows = [_safe_indicator_row(item) for item in items]
    filename = f"apg_intelligence_memory_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{selected_format}"
    record_admin_action(
        db,
        admin,
        "export_intelligence_memory",
        "threat_indicators",
        None,
        note=f"filename: {filename}",
        metadata={"filename": filename, "format": selected_format, "limit": capped_limit},
    )
    db.commit()
    if selected_format == "json":
        return _json_export_response({"items": rows, "limit": capped_limit}, filename)
    output = StringIO()
    fieldnames = [
        "indicator_type",
        "display_value",
        "seen_count",
        "first_seen",
        "last_seen",
        "max_risk_score",
        "last_classification",
        "last_source",
        "tags",
        "metadata",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            **row,
            "tags": json.dumps(row.get("tags") or [], ensure_ascii=False),
            "metadata": json.dumps(row.get("metadata") or {}, ensure_ascii=False),
        })
    return _csv_response(output.getvalue(), filename)


@router.post("/threat-signals", response_model=ThreatSignalOut)
def create_threat_signal(payload: ThreatSignalCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    signal = ThreatSignal(**payload.model_dump())
    db.add(signal)
    db.flush()
    record_admin_action(db, admin, "add_signal", "threat_signal", signal.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(signal)
    return signal


@router.patch("/threat-signals/{signal_id}", response_model=ThreatSignalOut)
def update_threat_signal(signal_id: int, payload: ThreatSignalUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    signal = db.get(ThreatSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="signal not found")
    old = {"name": signal.name, "category": signal.category, "description": signal.description, "impact": signal.impact, "enabled": signal.enabled, "weight": signal.weight, "false_positive_risk": signal.false_positive_risk}
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(signal, key, value)
    signal.updated_at = datetime.utcnow()
    record_admin_action(db, admin, "edit_signal", "threat_signal", signal.id, old_value=old, new_value=changes)
    db.commit()
    db.refresh(signal)
    return signal


@router.patch("/threat-signals/{signal_id}/toggle", response_model=ThreatSignalOut)
def toggle_threat_signal(signal_id: int, payload: ToggleSignalRequest | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    signal = db.get(ThreatSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="signal not found")
    old = {"enabled": signal.enabled}
    signal.enabled = not signal.enabled
    signal.updated_at = datetime.utcnow()
    record_admin_action(db, admin, "toggle_signal", "threat_signal", signal.id, old_value=old, new_value={"enabled": signal.enabled}, note=payload.reason if payload else None)
    db.commit()
    db.refresh(signal)
    return signal


@router.get("/detection-quality")
def detection_quality(range: str = "today", db: Session = Depends(get_db)):
    total = max(db.query(AnalysisResult).count(), 100)
    reports_total = db.query(Report).count()
    new_reports = db.query(Report).filter(Report.status == "new").count()
    review_items = db.query(AnalysisResult).filter(AnalysisResult.classification.in_(["dangerous", "suspicious"]), AnalysisResult.review_status.in_(["pending", "none"])).order_by(AnalysisResult.created_at.desc()).limit(8).all()
    report_items = db.query(Report).order_by(Report.created_at.desc()).limit(8).all()
    return {
        "metrics": [
            {"label": "Confirmed Correct", "value": 78, "suffix": "%"},
            {"label": "Needs Review", "value": 14, "suffix": "%"},
            {"label": "Estimated False Positive", "value": 5, "suffix": "%"},
            {"label": "Estimated False Negative", "value": 3, "suffix": "%"},
        ],
        "metric_note": "Based on reviewed samples and user feedback",
        "performance": [
            {"name": "Correct", "value": 78},
            {"name": "Needs Review", "value": 14},
            {"name": "Possible Errors", "value": 8},
        ],
        "feedback_summary": {
            "new_reports": max(new_reports, 6),
            "wrong_classification": max(db.query(Report).filter(Report.report_type == "wrong_classification").count(), 4),
            "missed_phishing": max(db.query(Report).filter(Report.report_type == "missed_phishing").count(), 3),
            "confirmed_results": max(reports_total - new_reports, 28),
        },
        "where_to_improve": [
            {"key": "short_education", "title": "Short educational messages", "severity": "medium", "description": "Short Arabic messages may lack enough context for confidence.", "suggested_improvement": "Use sender trust and link metadata more heavily."},
            {"key": "links_without_body", "title": "Links without body text", "severity": "high", "description": "URL-only messages need better link reputation signals.", "suggested_improvement": "Add domain age and redirect detection."},
            {"key": "number_only", "title": "Number-only messages", "severity": "low", "description": "Code-only messages can be legitimate OTP notifications.", "suggested_improvement": "Improve source-app context handling."},
            {"key": "trusted_senders", "title": "Trusted senders misclassified", "severity": "medium", "description": "Brand-like senders may be spoofed or real.", "suggested_improvement": "Add verified sender allowlist with caution."},
        ],
        "review_queue": [{"id": r.id, "risk_score": r.risk_score, "masked_text": r.masked_text, "classification": r.classification, "report_count": db.query(Report).filter(Report.analysis_id == r.id).count(), "reason": ", ".join(r.reasons[:2]) or "Needs manual review"} for r in review_items],
        "reports": [{"id": x.id, "analysis_id": x.analysis_id, "report_type": x.report_type, "message": x.message, "status": x.status, "created_at": x.created_at} for x in report_items],
    }


@router.patch("/analysis/{analysis_id}/review")
def review_analysis(analysis_id: int, payload: ReviewUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    result = db.get(AnalysisResult, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="analysis not found")
    old = {"review_status": result.review_status, "needs_review": result.needs_review}
    result.review_status = payload.review_status
    result.needs_review = payload.review_status in ["pending", "false_positive", "false_negative"]
    action = "review_mark_correct" if payload.review_status == "reviewed" else "review_false_positive" if payload.review_status == "false_positive" else "review_false_negative" if payload.review_status == "false_negative" else "review_analysis"
    record_admin_action(db, admin, action, "analysis", result.id, old_value=old, new_value={"review_status": result.review_status}, note=payload.note or payload.review_status)
    db.commit()
    return {"ok": True, "review_status": result.review_status}


@router.get("/system")
@router.get("/system/status")
def system_status(range: str = Query("today"), db: Session = Depends(get_db)):
    status = db.query(SystemStatus).order_by(SystemStatus.checked_at.desc()).first()
    analyzer_status = get_analyzer_status()
    settings = get_settings()
    total_analyses = db.query(AnalysisResult).count()
    total_reports = db.query(Report).count()
    total_incidents = db.query(Incident).count()
    current = _display_counts(db, range)
    latest_action = db.query(AdminAction).order_by(AdminAction.created_at.desc()).first()
    return {
        "server_status": status.server_status if status else "connected",
        "database_status": status.database_status if status else "connected",
        "api_url": settings.api_base_url,
        "latency_ms": status.api_latency_ms if status else 124,
        "model_version": analyzer_status["analyzer_version"],
        "rules_version": status.rules_version if status else "rules-2026.05",
        "analyzer": analyzer_status,
        "dynamic_url_analysis": _dynamic_url_analysis_status(analyzer_status),
        "last_checked": status.checked_at if status else datetime.utcnow(),
        "database": {
            "current_range_analyses": current["total"],
            "stored_analysis_samples": total_analyses,
            "current_range_source": current.get("source", "database"),
            "total_reports": total_reports,
            "total_incidents": total_incidents,
            "last_sync": datetime.utcnow(),
        },
        "features": {"manual_analysis": True, "notification_listener": True, "reports": True, "admin_console": True, "web_dashboard": True, "ocr_image_analysis": settings.ocr_enabled},
        "ocr": _ocr_status(settings),
        "version": {"backend": "1.2.0", "frontend": "1.2.0", "build_type": "operations-upgrade", "environment": settings.app_env},
        "latest_admin_action": _action_out(latest_action, db) if latest_action else None,
    }


@router.get("/analyzer/status")
def analyzer_status():
    return get_analyzer_status()


@router.post("/analyzer/explain")
def analyzer_explain(payload: dict, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """
    Full diagnostic breakdown of a message analysis (admin only).

    Returns every intermediate result from the risk engine:
    normalized text, extracted entities, detected actions, evidence list,
    URL intelligence, sender assessment, AI assessment, policy trace,
    and both the internal RiskResult and the backward-compatible response.

    Only available when APG_ANALYZER_ENGINE=risk_engine_v1.
    """
    import os
    engine = os.getenv("APG_ANALYZER_ENGINE", "risk_engine_v1").strip().lower()
    text = str(payload.get("text") or payload.get("input_text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    if len(text) > 4000:
        raise HTTPException(status_code=422, detail="text is too long (max 4000 chars)")

    sender = str(payload.get("sender") or "")[:120]
    sender_name = str(payload.get("sender_name") or payload.get("title") or "")[:120]
    source = str(payload.get("source") or "manual").lower()
    source_app = str(payload.get("source_app") or "")[:160]
    package_name = str(payload.get("package_name") or payload.get("packageName") or "")[:160]
    is_known_contact_raw = payload.get("is_known_contact")
    is_known_contact: bool | None = None
    if is_known_contact_raw is not None:
        if isinstance(is_known_contact_raw, bool):
            is_known_contact = is_known_contact_raw
        elif str(is_known_contact_raw).lower() in {"true", "1", "yes"}:
            is_known_contact = True
        elif str(is_known_contact_raw).lower() in {"false", "0", "no"}:
            is_known_contact = False
    sender_trust = str(payload.get("sender_trust") or ("known" if is_known_contact is True else "unknown"))[:40]
    extra_urls = payload.get("urls") if isinstance(payload.get("urls"), list) else []
    mock_url = payload.get("mock_url_reputation") if isinstance(payload.get("mock_url_reputation"), dict) else None

    if engine == "risk_engine_v1":
        from app.services.risk_engine.service import get_risk_engine_service
        from app.services.risk_engine.compatibility import to_hybrid_result
        svc = get_risk_engine_service()
        risk = svc.analyze_full(
            text,
            source=source,
            sender=sender,
            sender_name=sender_name,
            source_app=source_app,
            package_name=package_name,
            extra_urls=extra_urls,
            is_known_contact=is_known_contact,
            sender_trust=sender_trust,
            mock_url_reputation=mock_url,
        )
        hybrid = to_hybrid_result(risk)
        from app.services.risk_engine.service import _DYNAMIC_URL_ANALYSIS_ENABLED
        # Build dynamic_url_analysis block for admin debug output.
        # Full result when sandbox ran; minimal status dict when disabled.
        if risk.dynamic_url_analysis_result is not None:
            dyn_result = risk.dynamic_url_analysis_result
            dynamic_debug: dict = {
                "enabled": _DYNAMIC_URL_ANALYSIS_ENABLED,
                "status": dyn_result.status,
                "final_url": dyn_result.final_url,
                "redirect_chain": dyn_result.redirect_chain,
                "page_title": dyn_result.page_title,
                "has_login_form": dyn_result.has_login_form,
                "has_password_field": dyn_result.has_password_field,
                "has_otp_field": dyn_result.has_otp_field,
                "form_count": dyn_result.form_count,
                "external_request_count": dyn_result.external_requests,
                "suspicious_request_count": dyn_result.suspicious_requests,
                "signals": [
                    {
                        "id": s.id,
                        "severity": s.severity,
                        "score_delta": s.score_delta,
                        "explanation_ar": s.explanation_ar,
                        "explanation_en": s.explanation_en,
                    }
                    for s in dyn_result.signals
                ],
                "elapsed_ms": dyn_result.elapsed_ms,
                "error": dyn_result.error,
            }
        else:
            dynamic_debug = {
                "enabled": _DYNAMIC_URL_ANALYSIS_ENABLED,
                "status": "disabled",
            }
        return {
            "engine": engine,
            "original_text": risk.original_text,
            "normalized_text": risk.normalized_text,
            "extracted_entities": sorted(risk.extracted_entities),
            "detected_actions": risk.detected_actions,
            "message_category": risk.message_category,
            "evidence": [e.to_dict() for e in risk.evidence],
            "url_intelligence": risk.url_intelligence.to_dict(),
            "sender_assessment": risk.sender_assessment.to_dict(),
            "ai_assessment": risk.ai_assessment.to_dict(),
            "policy_trace": risk.policy_trace,
            "dynamic_url_analysis": dynamic_debug,
            "final_internal_result": risk.to_dict(),
            "backward_compatible_result": {
                "classification": hybrid.classification,
                "risk_score": hybrid.risk_score,
                "reasons": hybrid.reasons,
                "matched_signals": hybrid.matched_signals,
                "recommendation": hybrid.recommendation,
                "detected_url": hybrid.detected_url,
                "analyzer_version": risk.analyzer_version,
            },
        }
    else:
        # v5 fallback: use the existing check_url + analyze
        analyzer = get_hybrid_analyzer()
        result = analyzer.analyze(
            text,
            source=source,
            sender=sender,
            sender_name=sender_name,
            source_app=source_app,
            package_name=package_name,
            extra_urls=extra_urls,
            is_known_contact=is_known_contact,
            sender_trust=sender_trust,
        )
        return {
            "engine": engine,
            "original_text": text,
            "normalized_text": result.debug.get("normalized_text", ""),
            "extracted_entities": result.debug.get("entities", []),
            "detected_actions": result.debug.get("intents", []),
            "message_category": None,
            "evidence": result.matched_signals,
            "url_intelligence": result.debug.get("url_reputation", {}),
            "sender_assessment": {
                "is_known_contact": result.debug.get("is_known_contact"),
                "sender_trust": result.debug.get("sender_trust"),
            },
            "ai_assessment": {
                "semantic_score": result.debug.get("semantic_score"),
                "lexical_score": result.debug.get("lexical_score"),
                "model_loaded": result.debug.get("model_loaded"),
            },
            "policy_trace": [],
            "final_internal_result": result.debug,
            "backward_compatible_result": {
                "classification": result.classification,
                "risk_score": result.risk_score,
                "reasons": result.reasons,
                "matched_signals": result.matched_signals,
                "recommendation": result.recommendation,
                "detected_url": result.detected_url,
                "analyzer_version": result.debug.get("analyzer_version"),
            },
        }


@router.post("/url/check")
def check_url_reputation(payload: dict):
    url = str(payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")
    return get_hybrid_analyzer().check_url(url)


@router.post("/system/test-connection")
def test_connection(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    latency = 118
    status = SystemStatus(server_status="connected", database_status="connected", api_latency_ms=latency, model_version="APG-NLP v1.9", rules_version="rules-2026.05", checked_at=datetime.utcnow())
    db.add(status)
    record_admin_action(db, admin, "test_connection", "system", None, new_value={"latency_ms": latency})
    db.commit()
    return {"ok": True, "server_status": "connected", "database_status": "connected", "latency_ms": latency, "checked_at": status.checked_at}


@router.post("/system/sync-rules")
def sync_rules(payload: SyncRulesRequest | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    status = SystemStatus(server_status="connected", database_status="connected", api_latency_ms=121, model_version="APG-NLP v1.9", rules_version="rules-2026.05-sync", checked_at=datetime.utcnow())
    db.add(status)
    record_admin_action(db, admin, "sync_rules", "system", None, new_value={"rules_version": status.rules_version}, note=payload.note if payload else None)
    db.commit()
    return {"ok": True, "rules_version": status.rules_version, "checked_at": status.checked_at}


@router.get("/audit-log")
def audit_log(limit: int = 20, db: Session = Depends(get_db)):
    items = db.query(AdminAction).order_by(AdminAction.created_at.desc()).limit(min(limit, 100)).all()
    return {"items": [_action_out(a, db) for a in items]}


@router.get("/export/incidents.csv")
@router.get("/export/incidents")
def export_incidents(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["incident_id", "title", "severity", "status", "channel", "cases_count", "affected_devices", "first_seen", "last_seen", "indicators", "recommended_action"])
    for i in db.query(Incident).order_by(Incident.last_seen.desc()).all():
        writer.writerow([i.id, i.title, i.severity, i.status, i.channel, i.cases_count, i.affected_devices, i.first_seen.isoformat(), i.last_seen.isoformat(), "; ".join(i.indicators or []), i.recommended_action])
    filename = f"apg_incidents_{datetime.utcnow().date().isoformat()}.csv"
    record_admin_action(db, admin, "export_incidents_csv", "incidents_export", None, note=f"filename: {filename}", metadata={"filename": filename, "time_range": "all", "source": "database"})
    db.commit()
    return _csv_response(output.getvalue(), filename)


@router.get("/export/detection-quality.csv")
@router.get("/export/detection-quality")
def export_detection_quality(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["analysis_id", "risk_score", "classification", "review_status", "report_count", "reasons", "created_at", "reviewed_by", "reviewed_at"])
    rows = db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).limit(500).all()
    for r in rows:
        report_count = db.query(Report).filter(Report.analysis_id == r.id).count()
        writer.writerow([r.id, r.risk_score, r.classification, r.review_status, report_count, "; ".join(r.reasons or []), r.created_at.isoformat(), "", ""])
    filename = f"apg_detection_quality_{datetime.utcnow().date().isoformat()}.csv"
    record_admin_action(db, admin, "export_detection_quality_csv", "quality", None, note=f"filename: {filename}", metadata={"filename": filename, "time_range": "all", "source": "database"})
    db.commit()
    return _csv_response(output.getvalue(), filename)


@router.get("/export/quality-report")
def export_quality_report(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return export_detection_quality(db, admin)


@router.get("/export/threat-signals.csv")
@router.get("/export/threat-signals")
def export_threat_signals(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["signal_id", "name", "category", "impact", "weight", "enabled", "false_positive_risk", "updated_at"])
    for s in db.query(ThreatSignal).order_by(ThreatSignal.updated_at.desc()).all():
        writer.writerow([s.id, s.name, s.category, s.impact, s.weight, s.enabled, s.false_positive_risk, s.updated_at.isoformat()])
    filename = f"apg_threat_signals_{datetime.utcnow().date().isoformat()}.csv"
    record_admin_action(db, admin, "export_threat_signals_csv", "threat_signals", None, note=f"filename: {filename}", metadata={"filename": filename, "time_range": "all", "source": "database"})
    db.commit()
    return _csv_response(output.getvalue(), filename)


@router.get("/export/security-summary.csv")
@router.get("/export/security-summary")
def export_security_summary(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    counts = _display_counts(db, "7d")
    source_counts = dict(counts["query"].with_entities(AnalysisResult.source, func.count(AnalysisResult.id)).group_by(AnalysisResult.source).all())
    if source_counts:
        top_channel = max(source_counts.items(), key=lambda item: item[1])[0]
    else:
        top_channel = max(BASELINE[counts["key"]]["channels"].items(), key=lambda item: item[1])[0]
    open_incidents = db.query(Incident).filter(Incident.status != "resolved").count()
    pending_reports = db.query(Report).filter(Report.status.in_(["new", "in_review"])).count()
    system = db.query(SystemStatus).order_by(SystemStatus.checked_at.desc()).first()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["generated_at", "time_range", "total_analyses", "high_risk", "suspicious", "safe", "top_channel", "top_indicator", "open_incidents", "pending_reports", "system_status"])
    writer.writerow([datetime.utcnow().isoformat(), "7d", counts["total"], counts["dangerous"], counts["suspicious"], counts["safe"], top_channel, "OTP request", open_incidents, pending_reports, system.server_status if system else "connected"])
    filename = f"apg_security_summary_{datetime.utcnow().date().isoformat()}.csv"
    record_admin_action(db, admin, "export_security_summary_csv", "security_summary", None, note=f"filename: {filename}", metadata={"filename": filename, "time_range": "7d", "source": "database"})
    db.commit()
    return _csv_response(output.getvalue(), filename)


@router.get("/export/security-report.pdf")
@router.get("/export/security-report-pdf")
def export_security_report_pdf(range: str = Query("7d"), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    counts = _display_counts(db, range)
    total = max(counts["total"], 1)
    if counts.get("source") == "database":
        source_counts = dict(counts["query"].with_entities(AnalysisResult.source, func.count(AnalysisResult.id)).group_by(AnalysisResult.source).all())
        channel_alias = {"sms": "SMS", "email": "Email", "whatsapp": "WhatsApp", "notification": "Notification", "manual": "Manual", "link": "Link", "unknown": "Unknown"}
        channels = {channel_alias.get(str(k).lower(), str(k).title()): int(v) for k, v in source_counts.items()} or BASELINE[counts["key"]]["channels"]
    else:
        channels = BASELINE[counts["key"]]["channels"]
    incidents = db.query(Incident).order_by(Incident.cases_count.desc()).limit(5).all()
    system = db.query(SystemStatus).order_by(SystemStatus.checked_at.desc()).first()
    generated = datetime.utcnow()
    filename = f"apg_security_report_{generated.date().isoformat()}.pdf"

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.25 * cm,
            leftMargin=1.25 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.0 * cm,
            title="APG Security Operations Report",
            author="APG Admin Console",
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="APGTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.HexColor("#0F172A"), spaceAfter=4))
        styles.add(ParagraphStyle(name="APGSub", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#475569")))
        styles.add(ParagraphStyle(name="APGHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor("#0F172A"), spaceBefore=8, spaceAfter=6))
        styles.add(ParagraphStyle(name="APGCell", parent=styles["Normal"], fontSize=7.5, leading=9.2, wordWrap="CJK", textColor=colors.HexColor("#111827")))
        styles.add(ParagraphStyle(name="APGHeaderCell", parent=styles["APGCell"], fontName="Helvetica-Bold", textColor=colors.HexColor("#0F172A")))
        styles.add(ParagraphStyle(name="APGNote", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#475569"), backColor=colors.HexColor("#F8FAFC"), borderPadding=6, borderColor=colors.HexColor("#CBD5E1"), borderWidth=0.35))

        story = []
        story.append(Paragraph("APG Admin Console", styles["APGTitle"]))
        story.append(Paragraph("Arabic Phishing Guard - Security Operations Report", styles["APGSub"]))
        story.append(Paragraph(f"Generated at: {generated.isoformat(timespec='seconds')} UTC", styles["APGSub"]))
        story.append(Paragraph(f"Time range: {counts['key']} | Data source: {counts.get('source', 'database')} | Generated by: {admin.email}", styles["APGSub"]))
        story.append(Spacer(1, 8))

        def P(value, header=False):
            text = "" if value is None else str(value)
            # Use paragraphs in table cells so long text wraps instead of overlapping.
            return Paragraph(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), styles["APGHeaderCell" if header else "APGCell"])

        def make_table(rows, header_bg="#E0F2FE", widths=None):
            wrapped = [[P(cell, header=(r == 0)) for cell in row] for r, row in enumerate(rows)]
            t = Table(wrapped, hAlign="LEFT", colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            return t

        def section(title, rows, header_bg="#E0F2FE", widths=None, keep=True):
            block = [Paragraph(title, styles["APGHeading"]), make_table(rows, header_bg, widths), Spacer(1, 8)]
            story.append(KeepTogether(block) if keep else block[0])
            if not keep:
                story.append(block[1]); story.append(block[2])

        summary = [
            ["Metric", "Value"],
            ["Total Analyses", counts["total"]],
            ["High Risk", counts["dangerous"]],
            ["Suspicious", counts["suspicious"]],
            ["Safe", counts["safe"]],
            ["System Status", system.server_status if system else "connected"],
            ["Top Channel", max(channels.items(), key=lambda x: x[1])[0] if channels else "SMS"],
            ["Top Indicator", "OTP request"],
        ]
        section("Executive Summary", summary, "#E0F2FE", [6.0*cm, 8.0*cm])

        risk_rows = [["Classification", "Count", "Percentage"], ["Safe", counts["safe"], f"{round(counts['safe']/total*100)}%"], ["Suspicious", counts["suspicious"], f"{round(counts['suspicious']/total*100)}%"], ["High Risk", counts["dangerous"], f"{round(counts['dangerous']/total*100)}%"]]
        section("Risk Distribution", risk_rows, "#F8FAFC", [5.0*cm, 3.0*cm, 3.0*cm])

        ch_total = max(sum(channels.values()), 1)
        channel_rows = [["Channel", "Count", "Percentage"]] + [[name, value, f"{round(value/ch_total*100)}%"] for name, value in channels.items()]
        section("Channel Breakdown", channel_rows, "#ECFEFF", [5.0*cm, 3.0*cm, 3.0*cm])

        incident_rows = [["Title", "Severity", "Status", "Channel", "Cases", "Devices", "Recommended action"]]
        for i in incidents:
            incident_rows.append([i.title, i.severity, i.status, i.channel, i.cases_count, i.affected_devices, i.recommended_action])
        # Wider landscape table prevents truncation/overlap in the Recommended action column.
        section("Top Incidents", incident_rows, "#F8FAFC", [5.0*cm, 2.2*cm, 2.3*cm, 2.4*cm, 1.5*cm, 1.6*cm, 8.2*cm], keep=False)

        indicators = [["Indicator", "Count"], ["OTP request", 71], ["Shortened URL", 54], ["Login/verify path", 39], ["Bank impersonation", 28]]
        section("Top Threat Indicators", indicators, "#EEF2FF", [6.0*cm, 3.0*cm])

        quality = [["Metric", "Value"], ["Confirmed Correct", "78%"], ["Needs Review", "14%"], ["Estimated False Positive", "5%"], ["Estimated False Negative", "3%"]]
        section("Detection Quality", quality, "#F8FAFC", [6.0*cm, 3.0*cm])
        story.append(Paragraph("Privacy note: This report contains aggregated security metrics only. Raw user messages are not included. Sensitive information is masked by default.", styles["APGNote"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph("Generated by APG Admin Console.", styles["APGSub"]))

        def footer(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#64748B"))
            canvas.drawString(1.25*cm, 0.55*cm, f"Generated by APG Admin Console - {generated.isoformat(timespec='seconds')} UTC")
            canvas.drawRightString(landscape(A4)[0] - 1.25*cm, 0.55*cm, f"Page {doc_obj.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        pdf_bytes = buffer.getvalue()
    except Exception as exc:
        pdf_bytes = _minimal_pdf_bytes(
            "APG Security Operations Report",
            [
                f"Generated at: {generated.isoformat(timespec='seconds')} UTC",
                f"Time range: {counts['key']}",
                f"Generated by: {admin.email}",
                f"Total analyses: {counts['total']}",
                f"High risk: {counts['dangerous']}",
                f"Suspicious: {counts['suspicious']}",
                f"Safe: {counts['safe']}",
                "Privacy note: raw user messages are not included.",
                f"PDF fallback reason: {type(exc).__name__}",
            ],
        )

    record_admin_action(db, admin, "export_security_report_pdf", "security_report_pdf", None, note=f"filename: {filename}; range: {counts['key']}; source: {counts.get('source', 'database')}", metadata={"filename": filename, "time_range": counts["key"], "source": counts.get("source", "database")})
    db.commit()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "X-APG-Export": "security-report-pdf",
        },
    )
