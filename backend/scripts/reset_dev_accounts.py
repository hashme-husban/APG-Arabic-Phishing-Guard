"""Repair APG development accounts without deleting dashboard data.

Run from backend folder:
    python scripts/reset_dev_accounts.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402
from app.services.security import hash_password, verify_password  # noqa: E402

ACCOUNTS = [
    ("APG Admin", "admin@apg-secure.com", "admin123", "admin"),
    ("APG Admin", "admin@apg.local", "admin123", "admin"),
    ("APG User", "user@apg-secure.com", "user123", "user"),
    ("APG User", "user@apg.local", "user123", "user"),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for name, email, password, role in ACCOUNTS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(name=name, email=email, password_hash=hash_password(password), role=role, is_active=True)
                db.add(user)
                db.flush()
                status = "created"
            else:
                user.name = name
                user.role = role
                user.is_active = True
                user.password_hash = hash_password(password)
                db.flush()
                status = "updated"
            ok = verify_password(password, user.password_hash)
            print(f"[OK] {status}: {email} / {password} / role={role} / verify={ok}")
        db.commit()
        print("\nDevelopment credentials are ready:")
        print("  admin@apg-secure.com / admin123")
        print("  admin@apg.local       / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
