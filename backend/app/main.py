from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import admin, auth, analysis
from app.services.hybrid_analyzer import get_analyzer_status, get_hybrid_analyzer
from app.services.seed import seed_data

settings = get_settings()
logging.basicConfig(
    level=logging.INFO if settings.is_production else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("apg")

app = FastAPI(
    title="APG Admin Console API",
    version=settings.app_version,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length", "X-APG-Export"],
)


@app.middleware("http")
async def production_middleware(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("unhandled_error path=%s", request.url.path)
        if settings.is_production:
            return JSONResponse(status_code=500, content={"success": False, "data": None, "message": "Internal server error", "error": "INTERNAL_SERVER_ERROR"})
        raise exc
    elapsed = int((time.perf_counter() - started) * 1000)
    response.headers["X-Process-Time-ms"] = str(elapsed)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if settings.is_production:
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
    logger.info("%s %s status=%s elapsed_ms=%s", request.method, request.url.path, response.status_code, elapsed)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"success": False, "data": None, "message": "Validation error", "error": "VALIDATION_ERROR", "details": exc.errors()})


app.include_router(auth.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    get_hybrid_analyzer()
    init_db()
    db = SessionLocal()
    try:
        if not settings.is_production or settings.enable_dev_seed_on_startup:
            seed_data(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    started = time.perf_counter()
    db_status = "connected"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    latency = int((time.perf_counter() - started) * 1000)
    analyzer_status = get_analyzer_status()
    return {
        "success": True,
        "data": {
            "backend_status": "ok",
            "database_status": db_status,
            "current_time": datetime.now(timezone.utc).isoformat(),
            "version": settings.app_version,
            "environment": settings.app_env,
            "latency_ms": latency,
            "analyzer_version": analyzer_status["analyzer_version"],
            "semantic_model_loaded": analyzer_status["semantic_model_loaded"],
            "lexical_model_loaded": analyzer_status["lexical_model_loaded"],
            "critical_rules_enabled": analyzer_status["critical_rules_enabled"],
        },
        "message": "APG backend health check",
        "error": None,
    }
