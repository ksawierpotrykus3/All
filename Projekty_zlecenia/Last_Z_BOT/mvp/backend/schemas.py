
from datetime import UTC, datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from .utils import _coerce_utc

MAX_PASSWORD_LEN = 72


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LEN)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LEN)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LicenseValidateRequest(BaseModel):
    license_key: str = Field(max_length=64)
    hwid: str | None = Field(default=None, max_length=128)


class LicenseValidateResponse(BaseModel):
    # The license response is signed; `valid`/`expires_at`/`message` are only
    # available inside `signed_payload`, so the client cannot skip signature
    # verification and trust unsigned fields.
    signature: str | None = None
    signed_payload: dict | None = None


class UserInfo(BaseModel):
    id: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _created_utc(cls, v):
        return _coerce_utc(v)


class LicenseInfo(BaseModel):
    id: str
    key: str
    is_active: bool
    expires_at: datetime | None = None
    last_validated_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("expires_at", "last_validated_at", mode="before")
    @classmethod
    def _times_utc(cls, v):
        return _coerce_utc(v)


class LicenseCreateResponse(BaseModel):
    license_key: str
    user_email: str


class CheckoutSessionRequest(BaseModel):

    success_url: HttpUrl
    cancel_url: HttpUrl


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class AdminCreateLicenseRequest(BaseModel):

    user_email: EmailStr
    expires_in_days: int = Field(default=30, ge=1, le=3650)


class AdminResetHwidRequest(BaseModel):

    license_key: str
