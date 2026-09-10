# coding: utf-8
"""Pelny flow rezerwacji na SWIEZYM itemie z katalogu przez curl_cffi:
catalog -> conversations -> build -> PUT payment_method -> GET pickup points
-> PUT pickup_details -> POST payment -> status.

Skoro status 200 (pending) NIE blokuje itemu publicznie (20.8.8),
test potwierdza ze sciezka do platnosci dziala end-to-end.
Pomija sprzedawcow juz uzytych w testach. BEZ cleanup (200 = transaction_in_progress).
"""
import json
import time
from pathlib import Path
from datetime import datetime
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# sprzedawcy juz "zuzyci" przez nasze testy rezerwacji
USED_SELLERS = {161574001, 3180795364, 3180346878}
MAX_ATTEMPTS = 3

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:  # noqa: BLE001
        pass
s.headers.update({
    "accept": "application/json,text/plain,*/*,image/webp",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "content-type": "application/json",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
    "referer": "https://www.vinted.pl/",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}


def find_checksum(obj):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(find_checksum(v))
    return hits


def get_txn_status(txn_id):
    r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
              impersonate=BrowserType.chrome146, timeout=30)
    t = r.json().get("transaction", {})
    return t.get("status"), t


def fetch_candidates():
    """Swieze, tanie itemy z katalogu (nowy-first)."""
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")
    r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
    items = r.json().get("items", [])
    cands = []
    for it in items:
        u = it.get("user", {})
        if it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        if u.get("id") in USED_SELLERS:
            continue
        cands.append(it)
    return cands


def full_flow(item):
    item_id = item["id"]
    seller_id = item["user"]["id"]
    res = {"item": {"id": item_id, "seller": seller_id,
                    "title": item.get("title", "")[:60],
                    "price": item.get("price", {})}}

    # 1) conversations
    r = s.post("https://www.vinted.pl/api/v2/conversations",
               json={"initiator": "buy", "item_id": str(item_id),
                     "opposite_user_id": seller_id},
               headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    j = r.json()
    conv = j.get("conversation", {})
    txn = conv.get("transaction", {})
    txn_id = txn.get("id")
    status = txn.get("status")
    res["conversations"] = {"http": r.status_code, "conv_id": conv.get("id"),
                            "txn_id": txn_id, "txn_status": status}
    if not txn_id or status != 1:
        res["skip"] = f"nie nowa transakcja (status={status}, http={r.status_code})"
        return res
    time.sleep(0.3)

    # 2) build
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
               headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    build = r.json()
    checkout_id = build.get("checkout", {}).get("id")
    ch = find_checksum(build)
    comps = build.get("checkout", {}).get("components", {})
    pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
    rate_uuid = pd_inner.get("selected_rate_uuid")
    so_id = comps.get("shipping_address", {}).get("shipping_order_id")
    address = comps.get("shipping_address", {}).get("address", {})
    coords = address.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    res["build"] = {"http": r.status_code, "checkout_id": checkout_id,
                    "rate_uuid": rate_uuid, "shipping_order_id": so_id}
    if not checkout_id:
        res["skip"] = f"brak checkout_id (http={r.status_code})"
        return res
    time.sleep(0.3)

    # 3) PUT payment_method 12
    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    r = s.put(put_url, json={"components": {
        "additional_service": {},
        "payment_method": {"card_id": None, "pay_in_method_id": "12"},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": {},
    }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    try:
        ch2 = find_checksum(r.json())
    except Exception:  # noqa: BLE001
        ch2 = []
    res["put_payment_method"] = {"http": r.status_code, "checksum_count": len(ch2)}
    if r.status_code != 200:
        res["skip"] = f"PUT payment_method nie 200 ({r.status_code})"
        return res
    time.sleep(0.3)

    # 4) GET nearby pickup points
    point = None
    if so_id:
        pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
                   f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
        r = s.get(pts_url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
        pp = r.json()
        spoints = (pp or {}).get("shipping_points") or []
        sug = (pp or {}).get("suggested_shipping_point_code")
        for cand in spoints:
            sp_inner = cand.get("point", {})
            if sug and sp_inner.get("code") == sug:
                point = sp_inner
                break
        if point is None:
            for cand in spoints:
                sp_inner = cand.get("point", {})
                if rate_uuid and sp_inner.get("rate_uuid") == rate_uuid:
                    point = sp_inner
                    break
        if point is None and spoints:
            point = spoints[0].get("point", {})
        res["pickup_points"] = {"http": r.status_code, "n": len(spoints), "sug": sug,
                                "chosen": point and {"code": point.get("code"),
                                                     "uuid": point.get("uuid")}}
        if not point:
            res["skip"] = "brak punktu pickup"
            return res
        time.sleep(0.3)

    # 5) PUT pickup_details
    details = {}
    if rate_uuid:
        details["rate_uuid"] = rate_uuid
    if point:
        if point.get("code"):
            details["point_code"] = point["code"]
        if point.get("uuid"):
            details["point_uuid"] = point["uuid"]
        if point.get("rate_uuid"):
            details["rate_uuid"] = point["rate_uuid"]
    r = s.put(put_url, json={"components": {
        "additional_service": {},
        "payment_method": {},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": details,
    }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    try:
        ch3 = find_checksum(r.json())
    except Exception:  # noqa: BLE001
        ch3 = []
    res["put_pickup_details"] = {"http": r.status_code, "details": details}
    if r.status_code != 200:
        res["skip"] = f"PUT pickup_details nie 200 ({r.status_code})"
        return res
    time.sleep(0.5)

    # 6) payment
    checksum = (ch3 or ch2 or ch)[0] if (ch3 or ch2 or ch) else ""
    pay_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
    pay_body = {
        "checksum": checksum,
        "payment_options": {
            "browser_info": {
                "language": "pl", "color_depth": 24, "java_enabled": False,
                "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
            }
        },
    }
    r = s.post(pay_url, json=pay_body, headers=H, impersonate=BrowserType.chrome146,
               timeout=30, allow_redirects=False)
    try:
        pj = r.json()
    except Exception:  # noqa: BLE001
        pj = {}
    pay_status = (pj.get("payment") or {}).get("status")
    nav = (pj.get("action") or {}).get("parameters") or {}
    res["payment"] = {"http": r.status_code, "payment_status": pay_status,
                      "redirect": str(nav.get("url", ""))[:120]}
    time.sleep(2)

    # 7) status transakcji
    st, t = get_txn_status(txn_id)
    res["after_payment"] = {"txn_status": st,
                            "is_reserved": t.get("is_reserved"),
                            "purchase_id": t.get("purchase_id"),
                            "status_title": t.get("status_title"),
                            "status_updated_at": t.get("status_updated_at")}
    return res


def main():
    cands = fetch_candidates()
    print(f"[KATALOG] {len(cands)} kandydatow (swieze, tanie, pominiety zuzyci sprzedawcy)")
    results = {"ts": datetime.now().isoformat(timespec="seconds"),
               "attempts": []}
    for attempt, item in enumerate(cands[:MAX_ATTEMPTS], 1):
        print(f"\n=== PROBA {attempt}/{MAX_ATTEMPTS}: item {item['id']} "
              f"seller={item['user']['id']} '{item.get('title', '')[:40]}' "
              f"cena={item.get('price', {})} ===")
        res = full_flow(item)
        results["attempts"].append(res)
        if res.get("skip"):
            print(f"  -> SKIP: {res['skip']}")
            continue
        if res.get("payment", {}).get("payment_status") == "pending":
            print("  -> PAYMENT PENDING — pelna sciezka dziala!")
            break
        # dalej testuj nastepny (nie jest to czysty pending)
        print(f"  -> payment status: {res.get('payment', {}).get('payment_status')}")
    Path(BASE_DIR / "wynik_rez_fresh_full.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nZapisano: wynik_rez_fresh_full.json")


if __name__ == "__main__":
    main()
