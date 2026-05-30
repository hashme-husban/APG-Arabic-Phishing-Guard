from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = (value or "").strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Invalid email or username")
        return value


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    full_name: str | None = None


class VerificationRequiredResponse(BaseModel):
    ok: bool = True
    verification_required: bool = True
    message: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class ResendVerificationRequest(BaseModel):
    email: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    token: str
    user: UserOut
    role: str | None = None
    expires_at: str | None = None


class IncidentOut(BaseModel):
    id: int
    title: str
    severity: str
    status: str
    channel: str
    cases_count: int
    affected_devices: int
    indicators: list[str]
    description: str
    recommended_action: str
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True


class IncidentUpdate(BaseModel):
    status: str | None = None
    recommended_action: str | None = None


class ThreatSignalOut(BaseModel):
    id: int
    name: str
    category: str
    description: str
    impact: str
    enabled: bool
    weight: int
    false_positive_risk: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThreatSignalCreate(BaseModel):
    name: str = Field(min_length=2)
    category: str
    description: str
    impact: str
    enabled: bool = True
    weight: int = Field(ge=0, le=100)
    false_positive_risk: str = "medium"


class ThreatSignalUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    impact: str | None = None
    enabled: bool | None = None
    weight: int | None = Field(default=None, ge=0, le=100)
    false_positive_risk: str | None = None


class ReviewUpdate(BaseModel):
    review_status: str
    note: str | None = None


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: int

class ToggleSignalRequest(BaseModel):
    reason: str | None = None


class SyncRulesRequest(BaseModel):
    note: str | None = None
