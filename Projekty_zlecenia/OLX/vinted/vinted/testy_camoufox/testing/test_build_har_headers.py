# coding: utf-8
"""Test: POST checkout/build z pelnymi headerami z HAR (UA Opera GX, incognia token,
sec-ch-ua, referer strony itemu) na transakcji 21872241924."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# Token Incognia z HAR (z checkout/build)
INCOGNIA = ("eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkExMjhDQkMtSFMyNTYifQ"
            ".oiK8KBQ2KtW_dPBysaPHF5aKgMZFXL-52K6CZMMRsVrnuAxq7agrwy-ds7U2X7f0XFKrgr6xQOcIVwDnjnPD22-xIok-JHPhcOpTb0BsF")

s = cr.Session()
cookies = json.loads((BASE / "cookies_profil.json").read_text(encoding="utf-8"))
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
    "referer": "https://www.vinted.pl/items/9807925466-genesis-krypton-700",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 OPR/134.0.0.0"),
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Opera GX";v="134"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON, "x-incognia-request-token": INCOGNIA}

for label, impersonate in [("chrome136", BrowserType.chrome136), ("chrome131", BrowserType.chrome131)]:
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": 21872241924, "type": "transaction"}]},
               headers=H, impersonate=impersonate, timeout=30, allow_redirects=False)
    print(f"[{label}] build: {r.status_code}")
    print(f"  headers final URL: {r.url}")
    body = r.text[:800]
    print(f"  body: {body}\n")
    # sprawdz czy DataDome
    if "captcha-delivery.com" in r.url or "geo.captcha" in r.url:
        print("  => REDIRECT DataDome!")

# wariant: chrome136 impersonate z incognia z payment z HAR
print("\n--- Payment token test ---")
r2 = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
            json={"purchase_items": [{"id": 21872241924, "type": "transaction"}]},
            headers={"x-csrf-token": CSRF, "x-anon-id": ANON},
            impersonate=BrowserType.chrome136, timeout=30, allow_redirects=False)
print(f"bez incognia: {r2.status_code} {r2.url[:80]}")
