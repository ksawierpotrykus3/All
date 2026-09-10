
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
import stripe
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session
from stripe import SignatureVerificationError

from .auth import create_access_token, decode_access_token, hash_password, verify_password
from .config import settings
from .database import Base, engine, get_db
from .license_signing import sign_payload
from .models import License, StripeCustomer, User
from .utils import _coerce_utc
from .schemas import (
    AdminCreateLicenseRequest,
    AdminResetHwidRequest,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    LicenseCreateResponse,
    LicenseInfo,
    LicenseValidateRequest,
    LicenseValidateResponse,
    TokenResponse,
    UserInfo,
    UserLogin,
    UserRegister,
)
from .security import validate_startup_security

# _RATE_MAX/_RATE_WINDOW: limit license validation to guard against brute-force
# key guessing and backend overload from many concurrent clients.
_RATE_MAX = 5
_RATE_WINDOW = 60.0
# _AUTH_RATE_MAX/_AUTH_RATE_WINDOW: limit login/register to slow password
# guessing and registration spam.
_AUTH_RATE_MAX = 10
_AUTH_RATE_WINDOW = 300

redis_client: aioredis.Redis | None = None

logger = logging.getLogger(__name__)


def _license_response(
    license_key: str,
    hwid: str | None,
    valid: bool,
    expires_at: datetime | None,
    message: str,
) -> LicenseValidateResponse:
    payload = {
        "license_key": license_key,
        "hwid": hwid,
        "valid": valid,
        "message": message,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    signature = None
    if settings.license_private_key_pem:
        signature = sign_payload(payload, settings.license_private_key_pem)
    elif not settings.allow_unsigned_license_response:
        raise HTTPException(status_code=503, detail="License signing key not configured")
    return LicenseValidateResponse(signature=signature, signed_payload=payload)


async def _check_event_idempotent(event_id: str) -> bool:
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis required for idempotency; refusing webhook")
    key = f"webhook:idempotency:{event_id}"
    try:
        result = await redis_client.set(key, "1", nx=True, ex=86400)
    except (RedisConnectionError, OSError):
        raise HTTPException(status_code=503, detail="Redis unavailable; refusing webhook") from None
    return result is True


def _guard_rate_limiter() -> None:
    if settings.rate_limit_fail_closed:
        raise HTTPException(status_code=503, detail="Rate limit service unavailable")


async def _check_rate_limit(license_key: str) -> bool:
    if redis_client is None:
        _guard_rate_limiter()
        return True
    key = f"rate:license:{license_key}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, int(_RATE_WINDOW))
        return count <= _RATE_MAX
    except (RedisConnectionError, OSError):
        logger.warning("Redis unavailable; rate limit skip for %s", license_key)
        _guard_rate_limiter()
        return True


async def _check_auth_rate_limit(email: str) -> bool:
    if redis_client is None:
        _guard_rate_limiter()
        return True
    key = f"rate:auth:{email}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, _AUTH_RATE_WINDOW)
        return count <= _AUTH_RATE_MAX
    except (RedisConnectionError, OSError):
        logger.warning("Redis unavailable; auth rate limit skip for %s", email)
        _guard_rate_limiter()
        return True


stripe.api_key = settings.stripe_secret_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    validate_startup_security()
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield
    if redis_client is not None:
        await redis_client.close()


app = FastAPI(title="Last Z Bot - License Backend", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.removeprefix("Bearer ")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user


@app.post("/auth/register", response_model=TokenResponse)
async def register(data: UserRegister, db: Session = Depends(get_db)):
    if not await _check_auth_rate_limit(data.email):
        raise HTTPException(status_code=429, detail="Too many requests")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already taken")

    try:
        password_hash = hash_password(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Password too long (max 72 bytes)") from exc

    user = User(email=data.email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)

    license_key = f"LZ-{uuid.uuid4().hex[:12].upper()}"
    lic = License(user_id=user.id, key=license_key, is_active=False)
    db.add(lic)
    db.commit()

    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/checkout/session", response_model=CheckoutSessionResponse)
def create_checkout_session(
    data: CheckoutSessionRequest,
    user: User = Depends(_get_current_user),
):
    allowed_domains = {
        d.strip().lower()
        for d in settings.checkout_allowed_domains.split(",")
        if d.strip()
    }
    for url in (data.success_url, data.cancel_url):
        host = url.host.lower() if url.host else ""
        if host not in allowed_domains:
            raise HTTPException(status_code=400, detail="Invalid checkout URL domain")
    if not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Stripe price ID is not configured")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            customer_email=user.email,
            success_url=str(data.success_url),
            cancel_url=str(data.cancel_url),
            client_reference_id=user.id,
            metadata={"user_id": user.id},
        )
    except stripe.StripeError as exc:
        logger.exception("Failed to create Stripe checkout session")
        raise HTTPException(status_code=502, detail="Failed to create Stripe checkout session") from exc
    return CheckoutSessionResponse(checkout_url=session.url)


@app.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin, db: Session = Depends(get_db)):
    if not await _check_auth_rate_limit(data.email):
        raise HTTPException(status_code=429, detail="Too many requests")
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        password_ok = verify_password(data.password, user.password_hash)
    except ValueError:
        password_ok = False
    if not password_ok:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive account")
    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/license/validate", response_model=LicenseValidateResponse)
async def validate_license(data: LicenseValidateRequest, db: Session = Depends(get_db)):
    if not await _check_rate_limit(data.license_key):
        raise HTTPException(status_code=429, detail="Too many requests")
    lic = db.query(License).filter(License.key == data.license_key).first()
    if not lic:
        return _license_response(data.license_key, data.hwid, False, None, "Invalid license key")
    if not lic.is_active:
        return _license_response(data.license_key, data.hwid, False, None, "Inactive license")
    now = datetime.now(UTC)
    expires_at = _coerce_utc(lic.expires_at)
    in_grace = False
    if expires_at and expires_at < now:
        grace = timedelta(hours=settings.license_grace_period_hours)
        if now > expires_at + grace:
            return _license_response(data.license_key, data.hwid, False, expires_at, "License expired")
        in_grace = True
    if data.hwid:
        if lic.hwid is None:
            lic.hwid = data.hwid
        elif lic.hwid != data.hwid:
            return _license_response(
                data.license_key, data.hwid, False, None, "License assigned to another computer"
            )
    lic.last_validated_at = datetime.now(UTC)
    db.commit()
    if in_grace:
        return _license_response(data.license_key, data.hwid, True, expires_at, "License in grace period")
    return _license_response(data.license_key, data.hwid, True, expires_at, "OK")


@app.get("/user/me", response_model=UserInfo)
def get_me(user: User = Depends(_get_current_user)):
    return user


@app.get("/user/licenses", response_model=list[LicenseInfo])
def get_my_licenses(user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    return db.query(License).filter(License.user_id == user.id).all()


@app.post("/admin/licenses", status_code=201, response_model=LicenseCreateResponse)
def create_license(
    data: AdminCreateLicenseRequest,
    user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    target = db.query(User).filter(User.email == data.user_email).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    license_key = f"LZ-{uuid.uuid4().hex[:12].upper()}"
    lic = License(
        user_id=target.id,
        key=license_key,
        is_active=True,
        expires_at=datetime.now(UTC) + timedelta(days=data.expires_in_days),
    )
    db.add(lic)
    db.commit()
    return {"license_key": license_key, "user_email": data.user_email}


@app.post("/admin/licenses/reset-hwid")
def reset_license_hwid(
    data: AdminResetHwidRequest,
    user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    lic = db.query(License).filter(License.key == data.license_key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    lic.hwid = None
    db.commit()
    return {"status": "ok", "message": "HWID reset"}


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid payload") from err
    except SignatureVerificationError as err:
        raise HTTPException(status_code=400, detail="Invalid signature") from err

    event_type = event["type"]
    data = event["data"]["object"]

    if not await _check_event_idempotent(event["id"]):
        return JSONResponse({"status": "ignored", "reason": "duplicate_event"})

    if event_type == "checkout.session.completed":
        user_id = data.get("client_reference_id")
        stripe_customer_id = data.get("customer")
        if user_id and stripe_customer_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                existing = (
                    db.query(StripeCustomer).filter(StripeCustomer.user_id == user.id).first()
                )
                if existing:
                    existing.stripe_customer_id = stripe_customer_id
                    existing.subscription_status = "active"
                else:
                    db.add(
                        StripeCustomer(
                            user_id=user.id,
                            stripe_customer_id=stripe_customer_id,
                            subscription_status="active",
                        )
                    )
                for lic in user.licenses:
                    lic.is_active = True
                    if not lic.expires_at:
                        lic.expires_at = datetime.now(UTC) + timedelta(days=30)
                db.commit()

    elif event_type == "invoice.payment_failed":
        stripe_customer_id = data.get("customer")
        if stripe_customer_id:
            sc = (
                db.query(StripeCustomer)
                .filter(StripeCustomer.stripe_customer_id == stripe_customer_id)
                .first()
            )
            if sc:
                sc.subscription_status = "past_due"
                user = db.query(User).filter(User.id == sc.user_id).first()
                if user:
                    for lic in user.licenses:
                        lic.is_active = False
                db.commit()

    elif event_type in ("invoice.paid", "invoice.payment_succeeded"):
        stripe_customer_id = data.get("customer")
        if stripe_customer_id:
            sc = (
                db.query(StripeCustomer)
                .filter(StripeCustomer.stripe_customer_id == stripe_customer_id)
                .first()
            )
            if sc:
                sc.subscription_status = "active"
                user = db.query(User).filter(User.id == sc.user_id).first()
                if user:
                    # Prefer the invoice period end so renewals extend the exact
                    # billing period instead of a fixed +30 days.
                    period_end = data.get("period_end")
                    new_expiry = (
                        datetime.fromtimestamp(period_end, tz=UTC)
                        if period_end
                        else datetime.now(UTC) + timedelta(days=30)
                    )
                    for lic in user.licenses:
                        lic.is_active = True
                        lic.expires_at = new_expiry
                db.commit()

    elif event_type == "customer.subscription.updated":
        stripe_customer_id = data.get("customer")
        status = data.get("status")
        if stripe_customer_id and status:
            sc = (
                db.query(StripeCustomer)
                .filter(StripeCustomer.stripe_customer_id == stripe_customer_id)
                .first()
            )
            if sc:
                sc.subscription_status = status
                if status in ("canceled", "past_due", "unpaid", "incomplete_expired"):
                    user = db.query(User).filter(User.id == sc.user_id).first()
                    if user:
                        for lic in user.licenses:
                            lic.is_active = False
                db.commit()

    elif event_type == "customer.subscription.deleted":
        stripe_customer_id = data.get("customer")
        if stripe_customer_id:
            sc = (
                db.query(StripeCustomer)
                .filter(StripeCustomer.stripe_customer_id == stripe_customer_id)
                .first()
            )
            if sc:
                sc.subscription_status = "inactive"
                user = db.query(User).filter(User.id == sc.user_id).first()
                if user:
                    for lic in user.licenses:
                        lic.is_active = False
                db.commit()

    return JSONResponse({"status": "ok"})
