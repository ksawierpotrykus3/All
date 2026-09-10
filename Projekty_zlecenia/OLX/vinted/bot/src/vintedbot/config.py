"""Stałe konfiguracyjne i ładowanie cookies (JSON lub Netscape)."""
import base64
import json
import threading
from pathlib import Path

IMPERSONATE = "firefox135"
PAY_IN_METHOD = "1"  # karta

# Fingerprint TLS Firefox 152 — zweryfikowany (100% JA3+JA4 match, wynik_curl_cffi_firefox152.json).
# DataDome odrzuca requesty bez tego (wbudowany firefox135/firefox147 nie matchuje Camoufox FF152).
FF152_JA3 = "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-34-18-51-43-13-45-28-27-65037,4588-29-23-24-25-256-257,0"
FF152_AKAMAI = "1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s"
FF152_EXTRA_FP = {
    "tls_delegated_credential": "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:ecdsa_secp521r1_sha512:ecdsa_sha1",
    "tls_record_size_limit": 16385,
    "tls_cert_compression": "zstd",
    "tls_signature_algorithms": [
        "ecdsa_secp256r1_sha256",
        "ecdsa_secp384r1_sha384",
        "ecdsa_secp521r1_sha512",
        "rsa_pss_rsae_sha256",
        "rsa_pss_rsae_sha384",
        "rsa_pss_rsae_sha512",
        "rsa_pkcs1_sha256",
        "rsa_pkcs1_sha384",
        "rsa_pkcs1_sha512",
        "ecdsa_sha1",
        "rsa_pkcs1_sha1",
    ],
}


def tls_kwargs() -> dict:
    """Parametry TLS do każdego requestu curl_cffi (Firefox 152)."""
    return {"ja3": FF152_JA3, "akamai": FF152_AKAMAI, "extra_fp": FF152_EXTRA_FP}

CSRF_DEFAULT = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON_DEFAULT = "98c6af5a-87da-45f2-9be5-24cf9345b003"

INQUIRIES_URL = "https://api.vinted.pl/messaging/main/inquiries"
# Przeglądarka używa /api/v2/conversations (nie /inquiries) do utworzenia transakcji przy Kup teraz.
# Dowod: bot/output/item_page_requests_1788178470.json
CONVERSATIONS_URL = "https://www.vinted.pl/api/v2/conversations"
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
CHECKOUT_URL = "https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
PAYMENT_URL = "https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
PAYMENT_CONTINUE_URL = "https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment/continue"
CHECK_AVAILABILITY_URL = "https://api.vinted.pl/checkout/purchases/check_availability"
CARD_REGISTRATIONS_URL = "https://api.vinted.pl/payments/public/api/card_registrations"
CARDS_URL = "https://api.vinted.pl/payments/public/api/cards"
PICKUP_URL = ("https://api.vinted.pl/shipping-estimation/external/shipping_orders/"
              "{shipping_order_id}/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
SDK_CONFIG_URL = "https://api.vinted.pl/j3r4zw/v1/config"

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
NODE_TOKEN_SCRIPT = SCRIPTS_DIR / "generate_incognia_token.js"

# Globalny lock per profil Camoufox. Firefox NIE pozwala otworzyć tego samego
# user_data_dir z dwóch procesów naraz — drugi start kończy się cichym
# exitCode=0 i `launch_persistent_context` rzuca wyjątek. Harvest, screenshot
# w tle i refresh muszą więc serializować dostęp do tego samego profilu.
_PROFILE_LOCKS: dict[str, threading.Lock] = {}
_PROFILE_LOCKS_GUARD = threading.Lock()


def profile_lock(profil: str | Path) -> threading.Lock:
    """Zwraca współdzielony Lock dla danego katalogu profilu (tworzy gdy brak)."""
    klucz = str(profil)
    with _PROFILE_LOCKS_GUARD:
        lk = _PROFILE_LOCKS.get(klucz)
        if lk is None:
            lk = threading.Lock()
            _PROFILE_LOCKS[klucz] = lk
        return lk


def wczytaj_cookies(path: str | Path) -> dict[str, str]:
    """Wczytuje cookies z pliku JSON (lista obiektów lub dict name->value) albo Netscape."""
    data = Path(path).read_text(encoding="utf-8").lstrip()
    if data.startswith("["):
        return {c["name"]: c["value"] for c in json.loads(data) if c.get("name")}
    if data.startswith("{"):
        # Format dict name->value (z vintedbot.refresh.pobierz_swieze_cookies).
        raw = json.loads(data)
        return {str(k): str(v) for k, v in raw.items() if v is not None}
    cookies: dict[str, str] = {}
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies


def csrf_z_cookies(cookies: dict[str, str]) -> str | None:
    """Wyciąga CSRF z payloadu JWT access_token_web (Vinted trzyma tam csrf)."""
    at = cookies.get("access_token_web", "")
    parts = at.split(".")
    if len(parts) < 2:
        return None
    try:
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
        return payload.get("csrf")
    except Exception:
        return None