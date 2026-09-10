"""Zarządzanie kartami płatniczymi na koncie Vinted (Adyen CSE).

Umożliwia:
- Programistyczną rejestrację/tokenizację nowej karty (POST -> szyfrowanie JWE -> PUT).
- Pobranie listy zapisanych kart.
- Usunięcie karty.
"""
from typing import Any
from curl_cffi import requests as creq

from .adyen_cse import zaszyfruj_pola_karty
from .json_utils import json_loads
from .config import CARD_REGISTRATIONS_URL, CARDS_URL, IMPERSONATE, tls_kwargs
from .models import KonfiguracjaKonta


def _headers(konto: KonfiguracjaKonta) -> dict[str, str]:
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": konto.csrf,
        "x-anon-id": konto.anon_id,
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    at = konto.cookies.get("access_token_web")
    if at:
        h["Authorization"] = f"Bearer {at}"
    return h


_ACCESS_KEY_CACHE: dict[str, str] = {}


def pobierz_lub_pobierz_access_key(konto: KonfiguracjaKonta, session: creq.Session | None = None) -> str:
    """Pobiera lub zwraca zcache'owany publiczny access_key Adyen z endpointu card_registrations."""
    klucz = konto.anon_id
    if klucz in _ACCESS_KEY_CACHE:
        return _ACCESS_KEY_CACHE[klucz]
    
    req_headers = _headers(konto)
    if session is not None:
        r = session.post(CARD_REGISTRATIONS_URL, json={"card_registration": None}, headers=req_headers, timeout=15, **tls_kwargs())
    else:
        r = creq.post(CARD_REGISTRATIONS_URL, json={"card_registration": None}, headers=req_headers, cookies=konto.cookies, impersonate=konto.impersonate, timeout=15, **tls_kwargs())
    r.raise_for_status()
    init_data = json_loads(r.content) if hasattr(r, 'content') and r.content else r.json()
    reg_obj = init_data.get("card_registration") or init_data
    access_key = reg_obj.get("access_key")
    if access_key:
        _ACCESS_KEY_CACHE[klucz] = access_key
        return access_key
    raise RuntimeError(f"Brak access_key w odpowiedzi card_registrations: {init_data}")


def przygotuj_zaszyfrowana_karte(karta: dict[str, str], access_key: str) -> dict[str, str]:
    """Pre-komputacja: szyfruje 4 pola karty Adyen CSE z góry (0 ms narzutu w trakcie zakupu)."""
    return zaszyfruj_pola_karty(
        karta=karta,
        access_key=access_key,
    )


def zarejestruj_karte(
    karta: dict[str, str],
    konto: KonfiguracjaKonta,
    session: creq.Session | None = None,
    single_use: bool = False,
    return_url: str = "scheme://card_add_result",
) -> dict[str, Any]:
    """Rejestruje nową kartę na koncie kupującego przez Adyen CSE.

    karta: słownik z kluczami: 'number', 'expiryMonth', 'expiryYear', 'cvc'.
    Zwraca słownik odpowiedzi serwera po rejestracji karty.
    """
    req_headers = _headers(konto)
    
    # Krok 1: Utworzenie sesji rejestracji i pobranie access_key Adyen
    if session is not None:
        r_init = session.post(
            CARD_REGISTRATIONS_URL,
            json={"card_registration": None},
            headers=req_headers,
            timeout=15,
            **tls_kwargs(),
        )
    else:
        r_init = creq.post(
            CARD_REGISTRATIONS_URL,
            json={"card_registration": None},
            headers=req_headers,
            cookies=konto.cookies,
            impersonate=konto.impersonate,
            timeout=15,
            **tls_kwargs(),
        )
    r_init.raise_for_status()
    init_data = json_loads(r_init.content) if hasattr(r_init, 'content') and r_init.content else r_init.json()
    
    reg_obj = init_data.get("card_registration") or init_data
    reg_id = reg_obj.get("id") or reg_obj.get("card_registration_id")
    access_key = reg_obj.get("access_key")
    
    if not reg_id or not access_key:
        raise RuntimeError(f"Brak reg_id lub access_key w odpowiedzi POST card_registrations: {init_data}")
    
    # Krok 2: Lokalne szyfrowanie danych karty algorytmem JWE
    encrypted = zaszyfruj_pola_karty(karta, access_key)
    
    # Krok 3: Wysłanie zaszyfrowanych pól
    update_payload = {
        "card_registration": {
            "return_url": return_url,
            "single_use": single_use,
            "encrypted_card_details": {
                "number": encrypted.get("encryptedCardNumber", ""),
                "expiration_month": encrypted.get("encryptedExpiryMonth", ""),
                "expiration_year": encrypted.get("encryptedExpiryYear", ""),
                "security_code": encrypted.get("encryptedSecurityCode", ""),
            },
            "secure_3ds_details": {
                "platform": "android",
                "browser_info": {
                    "language": "pl",
                    "color_depth": 24,
                    "java_enabled": False,
                    "screen_height": 1080,
                    "screen_width": 1920,
                    "timezone_offset": -120,
                },
            },
        },
        "tracking_context": None,
    }
    
    put_url = f"{CARD_REGISTRATIONS_URL}/{reg_id}"
    if session is not None:
        r_put = session.put(
            put_url,
            json=update_payload,
            headers=req_headers,
            timeout=15,
            **tls_kwargs(),
        )
    else:
        r_put = creq.put(
            put_url,
            json=update_payload,
            headers=req_headers,
            cookies=konto.cookies,
            impersonate=konto.impersonate,
            timeout=15,
            **tls_kwargs(),
        )
    r_put.raise_for_status()
    return json_loads(r_put.content) if hasattr(r_put, 'content') and r_put.content else r_put.json()


def pobierz_zapisane_karty(
    konto: KonfiguracjaKonta,
    session: creq.Session | None = None,
) -> list[dict[str, Any]]:
    """Zwraca listę zarejestrowanych kart na koncie."""
    req_headers = _headers(konto)
    if session is not None:
        r = session.get(CARDS_URL, headers=req_headers, timeout=15, **tls_kwargs())
    else:
        r = creq.get(CARDS_URL, headers=req_headers, cookies=konto.cookies,
                     impersonate=konto.impersonate, timeout=15, **tls_kwargs())
    r.raise_for_status()
    data = json_loads(r.content) if hasattr(r, 'content') and r.content else r.json()
    if isinstance(data, dict):
        return data.get("cards") or []
    elif isinstance(data, list):
        return data
    return []


def usun_karte(
    card_id: int | str,
    konto: KonfiguracjaKonta,
    session: creq.Session | None = None,
) -> bool:
    """Usuwa wskazaną kartę z konta."""
    req_headers = _headers(konto)
    del_url = f"{CARDS_URL}/{card_id}"
    if session is not None:
        r = session.delete(del_url, headers=req_headers, timeout=15, **tls_kwargs())
    else:
        r = creq.delete(del_url, headers=req_headers, cookies=konto.cookies,
                        impersonate=konto.impersonate, timeout=15, **tls_kwargs())
    return r.status_code in (200, 204)
