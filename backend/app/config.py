from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("apg.config")

def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

def _clean_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def _clean_smtp_password(value: str) -> str:
    return value.strip().replace(" ", "")

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_debug: bool = _bool("APP_DEBUG", True)
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    jwt_secret: str = os.getenv("JWT_SECRET", os.getenv("APP_SECRET", "change-me-in-production"))
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./apg_admin.db")
    cors_allowed_origins: str = os.getenv("CORS_ALLOWED_ORIGINS", os.getenv("CORS_ORIGINS", "http://localhost:5173"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000/api")
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@apg-secure.com")
    admin_password: str | None = os.getenv("ADMIN_PASSWORD")
    enable_demo_data: bool = _bool("ENABLE_DEMO_DATA", False)
    enable_dev_seed_on_startup: bool = _bool("ENABLE_DEV_SEED_ON_STARTUP", True)
    export_dir: str = os.getenv("EXPORT_DIR", "./exports")
    pdf_export_dir: str = os.getenv("PDF_EXPORT_DIR", "./exports/pdf")
    model_version: str = os.getenv("MODEL_VERSION", "APG-NLP v1.9")
    rules_version: str = os.getenv("RULES_VERSION", "rules-2026.05")
    email_provider: str = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    smtp_host: str = _clean_env("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = _clean_env("SMTP_USERNAME")
    smtp_password: str = _clean_smtp_password(os.getenv("SMTP_PASSWORD", ""))
    smtp_use_tls: bool = _bool("SMTP_USE_TLS", True)
    email_from: str = _clean_env("EMAIL_FROM")
    # Risk Engine v1 settings
    apg_analyzer_engine: str = os.getenv("APG_ANALYZER_ENGINE", "risk_engine_v1")
    url_reputation_enabled: bool = _bool("URL_REPUTATION_ENABLED", True)
    url_reputation_timeout_seconds: int = int(os.getenv("URL_REPUTATION_TIMEOUT_SECONDS", "3"))
    url_reputation_cache_ttl_hours: int = int(os.getenv("URL_REPUTATION_CACHE_TTL_HOURS", "12"))
    # Dynamic URL analysis (Phase 2A: disabled stub; Phase 2B+: sandbox)
    dynamic_url_analysis_enabled: bool = _bool("DYNAMIC_URL_ANALYSIS_ENABLED", False)
    dynamic_url_analysis_timeout_seconds: int = int(os.getenv("DYNAMIC_URL_ANALYSIS_TIMEOUT_SECONDS", "10"))
    dynamic_url_analysis_observation_ms: int = int(os.getenv("DYNAMIC_URL_ANALYSIS_OBSERVATION_MS", "1500"))
    dynamic_url_analysis_time_simulation_enabled: bool = _bool("DYNAMIC_URL_ANALYSIS_TIME_SIMULATION_ENABLED", False)
    dynamic_url_analysis_simulated_minutes: int = int(os.getenv("DYNAMIC_URL_ANALYSIS_SIMULATED_MINUTES", "0"))
    # Phase 3: conservative sandbox scoring — disabled by default
    dynamic_url_analysis_score_enabled: bool = _bool("DYNAMIC_URL_ANALYSIS_SCORE_ENABLED", False)
    intelligence_memory_retention_days: int = int(os.getenv("INTELLIGENCE_MEMORY_RETENTION_DAYS", "90"))
    intelligence_memory_cleanup_enabled: bool = _bool("INTELLIGENCE_MEMORY_CLEANUP_ENABLED", False)
    # OCR — backend Arabic image text extraction
    ocr_enabled: bool = _bool("OCR_ENABLED", True)
    ocr_engine: str = os.getenv("OCR_ENGINE", "auto")   # auto | paddle | paddle_microservice | tesseract
    ocr_max_image_mb: int = int(os.getenv("OCR_MAX_IMAGE_MB", "5"))
    ocr_languages: str = os.getenv("OCR_LANGUAGES", "ara+eng")
    # PaddleOCR microservice — internal Docker URL; empty = microservice disabled
    ocr_paddle_service_url: str = os.getenv("OCR_PADDLE_SERVICE_URL", "")
    ocr_paddle_timeout_seconds: int = int(os.getenv("OCR_PADDLE_TIMEOUT_SECONDS", "20"))

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_allowed_origins.split(',') if x.strip()]

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    logger.warning(
        "EMAIL_CONFIG EMAIL_PROVIDER=%s SMTP_HOST=%s SMTP_PORT=%s SMTP_USERNAME_present=%s SMTP_PASSWORD_present=%s EMAIL_FROM_present=%s",
        settings.email_provider,
        settings.smtp_host,
        settings.smtp_port,
        bool(settings.smtp_username),
        bool(settings.smtp_password),
        bool(settings.email_from),
    )
    return settings
