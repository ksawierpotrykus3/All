"""
checkout_flow.py — pełna sekwencja checkout przez curl_cffi.

Sekwencja (na bazie bench_curl_gateway.py + Faza J + Faza K):
1. GET /catalog/items — znajduje dostępny item
2. POST /conversations {"initiator": "buy"} — tworzy transakcję, zwraca txn_id
3. POST /checkout/build — buduje checkout, zwraca checkout_id + checksum
4. PUT /checkout/{id} — komponenty (payment_method, shipping)
5. POST /checkout/{id}/payment — płatność z checksum + fingerprint + token

Wszystko przez curl_cffi, bez Camoufox (poza początkowym harvestem cookies/fingerprintu).
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from curl_cffi import requests as cr

from payment_sender import load_fingerprint

BASE_DIR = Path(__file__).resolve().parent
COOKIES_PATH = BASE_DIR / "cookies_profil.json"

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

IMPERSONATE = "firefox133"


def _load_cookies() -> list:
    """Wczytuje cookies z cookies_profil.json."""
    return json.loads(COOKIES_PATH.read_text(encoding="utf-8"))


def _create_session() -> cr.Session:
    """Tworzy sesję curl_cffi z cookies i domyślnymi nagłówkami."""
    s = cr.Session()
    access_token = None
    for c in _load_cookies():
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
            if c["name"] == "access_token_web":
                access_token = c["value"]
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "priority": "u=3",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    })
    if access_token:
        s.headers["authorization"] = f"Bearer {access_token}"
    return s


def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Bazowe nagłówki z CSRF i anon_id."""
    h = {"x-csrf-token": CSRF, "x-anon-id": ANON}
    if extra:
        h.update(extra)
    return h


def _find_checksum(obj: Any) -> List[str]:
    """Rekurencyjnie szuka klucza 'checksum' w odpowiedzi."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(_find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(_find_checksum(v))
    return hits


def step1_find_item(session: cr.Session) -> Dict[str, Any]:
    """
    Krok 1: GET /catalog/items — znajduje dostępny item (nie sprzedany, widoczny).
    """
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           "?price_to=100&order=newest_first&page=1&per_page=40&currency=PLN")
    r = session.get(url, headers=_headers(), impersonate=IMPERSONATE, timeout=30)
    item = None
    for it in r.json().get("items", []):
        if it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        item = it
        break
    if item is None:
        return {"status": r.status_code, "error": "brak dostępnego itemu"}
    return {
        "status": r.status_code,
        "item_id": item["id"],
        "seller_id": item["user"]["id"],
        "title": item.get("title", "")[:60],
        "price": item.get("price", {}),
    }


def step2_create_transaction(
    session: cr.Session,
    item_id: int,
    seller_id: int,
) -> Dict[str, Any]:
    """
    Krok 2: POST /conversations {"initiator": "buy"} — tworzy transakcję, zwraca txn_id.
    """
    url = "https://www.vinted.pl/api/v2/conversations"
    body = {"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id}
    r = session.post(
        url, json=body, headers=_headers(),
        impersonate=IMPERSONATE, timeout=30, allow_redirects=False,
    )
    data = r.json()
    conv = data.get("conversation", {})
    txn = conv.get("transaction") or {}
    return {
        "status": r.status_code,
        "conversation_id": conv.get("id"),
        "transaction_id": txn.get("id"),
        "raw": data,
    }


def step3_build(
    session: cr.Session,
    transaction_id: int,
    item_id: int,
    token: str,
) -> Dict[str, Any]:
    """
    Krok 3: POST /checkout/build — buduje checkout, zwraca checkout_id + checksum.
    """
    url = "https://www.vinted.pl/api/v2/purchases/checkout/build"
    body = {"purchase_items": [{"id": transaction_id, "type": "transaction"}]}
    r = session.post(
        url, json=body,
        headers=_headers({
            "referer": f"https://www.vinted.pl/items/{item_id}",
            "x-incognia-request-token": token,
        }),
        impersonate=IMPERSONATE, timeout=30, allow_redirects=False,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text[:500]}
    checkout = data.get("checkout", {}) if isinstance(data, dict) else {}
    checksums = _find_checksum(data)
    return {
        "status": r.status_code,
        "checkout_id": checkout.get("id"),
        "checksum": checksums[0] if checksums else None,
        "components": list(checkout.get("components", {}).keys()) if isinstance(checkout, dict) else [],
        "raw": data,
    }


def step4_put_components(
    session: cr.Session,
    checkout_id: str,
    build_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Krok 4: PUT /checkout/{checkout_id} — komponenty (payment_method, shipping, pickup_details).
    """
    url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"

    # Wyciągnij dane wysyłki z build (do pickup points)
    components = build_data.get("checkout", {}).get("components", {})
    shipping_address = components.get("shipping_address", {})
    so_id = shipping_address.get("shipping_order_id")
    addr = shipping_address.get("address", {})
    coords = addr.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")

    # 4a: PUT payment_method (puste shipping)
    body1 = {"components": {
        "additional_service": {},
        "payment_method": {"card_id": None, "pay_in_method_id": "12"},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": {},
    }}
    r = session.put(
        url, json=body1,
        headers=_headers({"referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"}),
        impersonate=IMPERSONATE, timeout=30, allow_redirects=False,
    )
    try:
        data1 = r.json()
        checksums1 = _find_checksum(data1)
    except Exception:
        data1 = {"raw_text": r.text[:300]}
        checksums1 = []

    # 4b: Pobierz pickup points (jeśli shipping_order_id istnieje)
    details = {}
    if so_id and lat and lon:
        pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
                   f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
        r_pts = session.get(pts_url, headers=_headers(), impersonate=IMPERSONATE, timeout=30)
        try:
            pp = r_pts.json()
            spoints = (pp or {}).get("shipping_points") or []
            sug = (pp or {}).get("suggested_shipping_point_code")
            point = None
            for cand in spoints:
                sp = cand.get("point", {})
                if sug and sp.get("code") == sug:
                    point = sp
                    break
            if point is None and spoints:
                point = spoints[0].get("point", {})
            if point:
                if point.get("code"):
                    details["point_code"] = point["code"]
                if point.get("uuid"):
                    details["point_uuid"] = point["uuid"]
                if point.get("rate_uuid"):
                    details["rate_uuid"] = point["rate_uuid"]
        except Exception:
            pass

    # 4c: PUT pickup_details (jeśli znaleziono punkt)
    checksums2 = []
    if details:
        body2 = {"components": {
            "additional_service": {},
            "payment_method": {},
            "shipping_address": {},
            "shipping_pickup_options": {},
            "shipping_pickup_details": details,
        }}
        r2 = session.put(
            url, json=body2,
            headers=_headers({"referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"}),
            impersonate=IMPERSONATE, timeout=30, allow_redirects=False,
        )
        try:
            data2 = r2.json()
            checksums2 = _find_checksum(data2)
        except Exception:
            pass

    # Zwróć najświeższy checksum (z pickup_details lub payment_method)
    final_checksum = (checksums2 or checksums1)
    return {
        "status": r.status_code,
        "checksum": final_checksum[0] if final_checksum else None,
        "pickup_details": details,
        "raw": data1,
    }


def step5_payment(
    session: cr.Session,
    checkout_id: str,
    checksum: str,
    token: str,
) -> Dict[str, Any]:
    """
    Krok 5: POST /checkout/{checkout_id}/payment — płatność z checksum + fingerprint + token.
    """
    fingerprint = load_fingerprint()
    url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
    body = {
        "checksum": checksum,
        "payment_options": {
            "browser_info": {
                "language": "pl",
                "color_depth": 24,
                "java_enabled": False,
                "screen_height": fingerprint["screen_height"],
                "screen_width": fingerprint["screen_width"],
                "timezone_offset": -120,
            }
        },
    }
    r = session.post(
        url, json=body,
        headers=_headers({
            "referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}",
            "x-incognia-request-token": token,
        }),
        impersonate=IMPERSONATE, timeout=30, allow_redirects=False,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text[:500]}
    payment = data.get("payment", {}) if isinstance(data, dict) else {}
    action = data.get("action", {}) if isinstance(data, dict) else {}
    nav = (action.get("parameters") or {})
    return {
        "status": r.status_code,
        "payment_status": payment.get("status"),
        "redirect_url": nav.get("url", ""),
        "success": r.status_code == 200 and payment.get("status") == "pending" and bool(nav.get("url")),
        "raw": data,
    }


def run_checkout_flow(token: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Uruchamia pełną sekwencję checkout przez curl_cffi: catalog → conversations → build → PUT → payment.
    Build jest flaky (DataDome) — retry z exponential backoff.
    """
    results = {}
    session = _create_session()

    # Krok 1: Znajdź item
    print("[1] GET /catalog/items — szukanie dostępnego itemu...")
    r1 = step1_find_item(session)
    results["step1_item"] = r1
    if "error" in r1:
        print(f"    ❌ {r1['error']}")
        return results
    item_id, seller_id = r1["item_id"], r1["seller_id"]
    print(f"    ✅ item {item_id} seller={seller_id} '{r1['title'][:40]}' ({r1['price']})")

    # Krok 2: Utwórz transakcję
    print("[2] POST /conversations — tworzenie transakcji...")
    r2 = step2_create_transaction(session, item_id, seller_id)
    results["step2_conversations"] = {"status": r2["status"], "transaction_id": r2["transaction_id"]}
    print(f"    Status: {r2['status']}, transaction_id: {r2['transaction_id']}")
    if r2["status"] != 200 or not r2["transaction_id"]:
        return results

    # Krok 3: Build z retry (flaky DataDome)
    r3 = None
    for attempt in range(max_retries):
        print(f"[3] POST /checkout/build (próba {attempt + 1}/{max_retries})...")
        time.sleep(1 + attempt)  # exponential backoff
        r3 = step3_build(session, r2["transaction_id"], item_id, token)
        results["step3_build"] = {"status": r3["status"], "checkout_id": r3["checkout_id"],
                                  "checksum": bool(r3["checksum"]), "attempt": attempt + 1}
        print(f"    Status: {r3['status']}, checkout_id: {r3['checkout_id']}, checksum: {bool(r3['checksum'])}")
        if r3["status"] == 200 and r3["checkout_id"]:
            break
    if not r3 or r3["status"] != 200 or not r3["checkout_id"]:
        results["step3_build"]["raw"] = r3["raw"] if r3 else None
        return results

    # Krok 4: PUT components (payment_method + pickup_details)
    print("[4] PUT /checkout/{id} — komponenty (payment_method + pickup_details)...")
    r4 = step4_put_components(session, r3["checkout_id"], r3["raw"])
    results["step4_put"] = {"status": r4["status"], "checksum": bool(r4["checksum"]),
                            "pickup_details": r4["pickup_details"]}
    print(f"    Status: {r4['status']}, checksum: {bool(r4['checksum'])}, pickup: {bool(r4['pickup_details'])}")

    # Użyj checksum z PUT (świeższy) lub z build
    final_checksum = r4["checksum"] or r3["checksum"]

    # Krok 5: Payment
    print("[5] POST /checkout/payment...")
    r5 = step5_payment(session, r3["checkout_id"], final_checksum, token)
    results["step5_payment"] = {
        "status": r5["status"],
        "payment_status": r5["payment_status"],
        "success": r5["success"],
        "redirect_url": r5["redirect_url"][:100],
    }
    print(f"    Status: {r5['status']}, payment_status: {r5['payment_status']}, success: {r5['success']}")
    if r5["redirect_url"]:
        print(f"    Redirect: {r5['redirect_url'][:80]}...")

    return results
