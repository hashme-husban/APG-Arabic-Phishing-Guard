from datetime import datetime, timedelta
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.dependencies import get_current_user, get_db
from app.models import EmailVerification, User
from app.services.audit import record_admin_action
from app.services.email_service import EmailService
from app.services.rate_limit import check_rate_limit, client_key
from app.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ResendVerificationRequest,
    UserOut,
    VerificationRequiredResponse,
    VerifyEmailRequest,
)
from app.services.security import (
    create_access_token,
    hash_password,
    hash_verification_code,
    token_expires_at,
    verify_verification_code,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
VERIFICATION_CODE_MINUTES = 10
MAX_VERIFICATION_ATTEMPTS = 5


def _is_valid_email(value: str) -> bool:
    value = value.strip()
    if not value or "@" not in value or value.startswith("@") or value.endswith("@"):
        return False
    local, domain = value.rsplit("@", 1)
    return bool(local.strip() and "." in domain and not domain.startswith(".") and not domain.endswith("."))


def _new_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _set_verification_code(verification: EmailVerification, code: str, email: str) -> None:
    verification.email = email
    verification.code_hash = hash_verification_code(email, code)
    verification.expires_at = datetime.utcnow() + timedelta(minutes=VERIFICATION_CODE_MINUTES)
    verification.attempts = 0
    verification.last_sent_at = datetime.utcnow()


def _pending_verification(db: Session, user_id: int) -> EmailVerification | None:
    return (
        db.query(EmailVerification)
        .filter(
            EmailVerification.user_id == user_id,
            EmailVerification.verified_at.is_(None),
        )
        .first()
    )


@router.post("/register", response_model=VerificationRequiredResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(client_key(request, "register"), limit=5, window_seconds=60)
    email = (payload.email or "").strip().lower()
    password = payload.password or ""
    display_name = (payload.name or payload.full_name or "").strip()

    if not _is_valid_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Weak password")
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        name=display_name or email.split("@", 1)[0],
        email=email,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    code = _new_verification_code()
    verification = EmailVerification(user_id=user.id, email=email, resend_count=0)
    _set_verification_code(verification, code, email)
    db.add(verification)
    db.commit()
    EmailService().send_verification_code(email, code)
    return {"ok": True, "verification_required": True, "message": "Email verification required"}


@router.post("/verify-email", response_model=LoginResponse)
def verify_email(payload: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(client_key(request, "verify-email"), limit=10, window_seconds=60)
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not _is_valid_email(email) or len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    user = db.query(User).filter(User.email == email).first()
    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.email == email,
            EmailVerification.verified_at.is_(None),
        )
        .first()
    )
    if not user or not verification:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
    if verification.expires_at is None or verification.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")
    if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts")

    verification.attempts += 1
    if not verify_verification_code(email, code, verification.code_hash):
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    verification.verified_at = datetime.utcnow()
    verification.code_hash = None
    verification.expires_at = None
    verification.attempts = 0
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.role)
    return {"token": token, "user": user, "role": user.role, "expires_at": token_expires_at().isoformat()}


@router.post("/resend-verification")
def resend_verification(payload: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(client_key(request, "resend-verification"), limit=5, window_seconds=60)
    email = (payload.email or "").strip().lower()
    generic = {"ok": True, "message": "If verification is required, a new code will be sent."}
    if not _is_valid_email(email):
        return generic

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return generic
    verification = _pending_verification(db, user.id)
    if not verification:
        return generic
    if verification.last_sent_at and verification.last_sent_at > datetime.utcnow() - timedelta(seconds=60):
        return generic

    code = _new_verification_code()
    _set_verification_code(verification, code, email)
    verification.resend_count += 1
    db.commit()
    EmailService().send_verification_code(email, code)
    return generic


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(client_key(request, "login"), limit=10, window_seconds=60)
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.role != "admin" and _pending_verification(db, user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email verification required")
    user.last_login_at = datetime.utcnow()
    record_admin_action(db, user, "login", "auth", user.id, note="web_admin_login")
    db.commit()
    token = create_access_token(user.id, user.role)
    return {"token": token, "user": user, "role": user.role, "expires_at": token_expires_at().isoformat()}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    record_admin_action(db, current_user, "logout", "auth", current_user.id, note="web_admin_logout")
    db.commit()
    # TODO: Add a token/session version column or denylist to revoke issued JWTs
    # immediately. Until then, clients clear the token locally and the JWT
    # remains cryptographically valid only until its normal expiry.
    return {"ok": True, "message": "Logged out locally. Token expires at its normal expiry time."}
