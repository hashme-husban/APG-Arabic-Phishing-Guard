from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_settings

DATABASE_URL = get_settings().database_url
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def _ensure_sqlite_columns() -> None:
    """Tiny development migration helper for existing SQLite databases.

    The project intentionally avoids Alembic for the lightweight local build, but
    we still need old developer DB files to survive new columns added during
    production polish.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "admin_actions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("admin_actions")}
    with engine.begin() as conn:
        if "old_value" not in columns:
            conn.execute(text("ALTER TABLE admin_actions ADD COLUMN old_value TEXT"))
        if "new_value" not in columns:
            conn.execute(text("ALTER TABLE admin_actions ADD COLUMN new_value TEXT"))

        # Production-readiness lightweight migrations for existing SQLite DBs.
        tables = inspector.get_table_names()
        if "admin_actions" in tables:
            action_columns = {col["name"] for col in inspector.get_columns("admin_actions")}
            if "metadata_json" not in action_columns:
                conn.execute(text("ALTER TABLE admin_actions ADD COLUMN metadata_json JSON"))
        if "analysis_results" in tables:
            analysis_columns = {col["name"] for col in inspector.get_columns("analysis_results")}
            if "matched_signals" not in analysis_columns:
                conn.execute(text("ALTER TABLE analysis_results ADD COLUMN matched_signals JSON"))
        if "reports" in tables:
            report_columns = {col["name"] for col in inspector.get_columns("reports")}
            if "reviewed_by" not in report_columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN reviewed_by INTEGER"))
            if "reviewed_at" not in report_columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN reviewed_at DATETIME"))


def init_db() -> None:
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
