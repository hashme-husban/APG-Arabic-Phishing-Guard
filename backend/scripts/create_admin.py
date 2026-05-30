from __future__ import annotations
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import SessionLocal, init_db
from app.models import User
from app.services.security import hash_password

email = os.getenv("ADMIN_EMAIL") or (sys.argv[1] if len(sys.argv) > 1 else None)
password = os.getenv("ADMIN_PASSWORD") or (sys.argv[2] if len(sys.argv) > 2 else None)
if not email or not password:
    raise SystemExit("Usage: ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='strong-password' python scripts/create_admin.py")
init_db()
with SessionLocal() as db:
    user = db.query(User).filter(User.email == email.lower()).first()
    if user:
        user.password_hash = hash_password(password)
        user.role = "admin"
        user.is_active = True
        print(f"[OK] updated admin: {email}")
    else:
        db.add(User(name="APG Admin", email=email.lower(), password_hash=hash_password(password), role="admin", is_active=True))
        print(f"[OK] created admin: {email}")
    db.commit()
