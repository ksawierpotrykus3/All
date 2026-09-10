# coding: utf-8
"""Test: czy rotacja anon_id wystarczy do zmiany tozsamosci dla DataDome?"""
import json
import uuid
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"

def test_with_anon_id(anon_id, label):
    """Test checkout/build z konkretnym anon_id."""
    s = cr.Session()
    cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
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
    H = {"x-csrf-token": CSRF, "x-anon-id": anon_id}

    # swiezy item
    r = s.get("https://www.vinted.pl/api/v2/catalog/items"
              "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
              headers=H, impersonate=BrowserType.chrome146, timeout=30)
    it = r.json().get("items", [])[0]
    item_id, seller_id = it["id"], it["user"]["id"]
    print(f"[{label}] item {item_id}")

    r = s.post("https://www.vinted.pl/api/v2/conversations",
               json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
               headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    txn = r.json()["conversation"]["transaction"]["id"]
    print(f"[{label}] conversations: {r.status_code} txn={txn}")

    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": txn, "type": "transaction"}]},
               headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    print(f"[{label}] build: {r.status_code}")
    return r.status_code

# Test 1: oryginalny anon_id
print("=== TEST 1: oryginalny anon_id ===")
orig = "98c6af5a-87da-45f2-9be5-24cf9345b003"
s1 = test_with_anon_id(orig, "orig")

# Test 2: nowy anon_id
print("\n=== TEST 2: nowy anon_id ===")
new = str(uuid.uuid4())
s2 = test_with_anon_id(new, "nowy")

# Test 3: jeszcze inny anon_id
print("\n=== TEST 3: kolejny nowy anon_id ===")
new2 = str(uuid.uuid4())
s3 = test_with_anon_id(new2, "nowy2")

print(f"\n=== WYNIKI ===")
print(f"orig: {s1}")
print(f"nowy: {s2}")
print(f"nowy2: {s3}")
print(f"\nWniosek: rotacja anon_id {'POMOGLA' if s2 == 200 or s3 == 200 else 'NIE POMOGLA'}")
