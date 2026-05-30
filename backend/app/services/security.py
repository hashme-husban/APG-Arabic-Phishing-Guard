from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from jose import jwt
from passlib.context import CryptContext
from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_ALGORITHM = "HS256"

def _settings():
    return get_settings()

def token_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=_settings().jwt_expire_minutes)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_verification_code(email: str, code: str) -> str:
    message = f"{email.strip().lower()}:{code.strip()}".encode("utf-8")
    secret = _settings().jwt_secret.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_verification_code(email: str, code: str, code_hash: str | None) -> bool:
    if not code_hash:
        return False
    expected = hash_verification_code(email, code)
    return hmac.compare_digest(expected, code_hash)


def create_access_token(user_id: int, role: str) -> str:
    expire = token_expires_at()
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, _settings().jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _settings().jwt_secret, algorithms=[JWT_ALGORITHM])
