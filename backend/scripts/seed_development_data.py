from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import SessionLocal, init_db
from app.services.seed import seed_data

init_db()
with SessionLocal() as db:
    seed_data(db)
print("[OK] development seed data loaded")
