import logging

from .config import settings

logger = logging.getLogger(__name__)

MIN_JWT_SECRET_LEN = 32
_INSECURE_SECRETS = {"dev-secret-change-me", "your-secret-key-here", "changeme"}

# Stripe placeholders copied from deploy/.env.example unchanged must not pass
# silently: warn loudly so a misconfigured checkout/webhook is noticed.
_STRIPE_PLACEHOLDER_MARKERS = ("sk_live_...", "whsec_...", "price_...")


def validate_startup_security() -> None:
    secret = settings.jwt_secret
    if len(secret) < MIN_JWT_SECRET_LEN or secret in _INSECURE_SECRETS:
        raise RuntimeError(
            f"JWT_SECRET does not meet the security requirements "
            f"(min {MIN_JWT_SECRET_LEN} characters, non-default). Set it in .env."
        )

    for name, value in (
        ("STRIPE_SECRET_KEY", settings.stripe_secret_key),
        ("STRIPE_WEBHOOK_SECRET", settings.stripe_webhook_secret),
        ("STRIPE_PRICE_ID", settings.stripe_price_id),
    ):
        if value in _STRIPE_PLACEHOLDER_MARKERS or value == "":
            logger.warning(
                "%s is empty or a placeholder (%r). Checkout/webhooks will not "
                "work until it is set to a real value in .env.",
                name,
                value,
            )
