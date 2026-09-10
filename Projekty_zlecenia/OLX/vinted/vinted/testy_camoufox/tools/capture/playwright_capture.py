# coding: utf-8
"""Playwright: laduje cookies_profil.json, otwiera item, klika 'Kup teraz',
loguje WSZYSTKIE requesty checkout/purchases + kontekst. Porownanie z HAR."""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
COOKIES_FILE = BASE / "cookies_profil.json"
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"

if not COOKIES_FILE.exists():
    print("BRAK cookies_profil.json")
    sys.exit(1)

cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
print(f"Cookies: {len(cookies)} sztuk")
for c in cookies[:5]:
    print(f"  {c.get('name')} domain={c.get('domain')}")

from playwright.sync_api import sync_playwright

captured = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context()
    ctx.add_cookies(cookies)

    page = ctx.new_page()

    def on_request(req):
        u = req.url
        if any(k in u for k in ("checkout/build", "checkout/payment", "/conversations")):
            captured.append({
                "type": "request",
                "method": req.method,
                "url": u,
                "headers": req.headers,
                "post_data": req.post_data,
            })
            print(f"[REQ] {req.method} {u}")

    def on_response(res):
        u = res.url
        if any(k in u for k in ("checkout/build", "checkout/payment", "/conversations")):
            body = ""
            try:
                body = res.text()[:2000]
            except Exception:
                pass
            captured.append({"type": "response", "url": u, "status": res.status, "body": body})
            print(f"[RESP] {res.status} {u}")

    page.on("request", on_request)
    page.on("response", on_response)

    # test logowania
    page.goto("https://www.vinted.pl/catalog?search_text=test", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    logged = page.evaluate("document.body.innerHTML.includes('Wyloguj') || document.body.innerHTML.includes('Moje konto')")
    print(f"Zalogowany: {logged}")

    # strona itemu
    page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    buy_btn = page.query_selector('button[data-testid="item-buy-button"]')
    if buy_btn:
        print("Przycisk 'Kup teraz' istnieje")
        page.click('button[data-testid="item-buy-button"]')
        print("Kliknieto 'Kup teraz'")
        page.wait_for_timeout(10000)
    else:
        print("Przycisk 'Kup teraz' NIE istnieje")
        # co jest na stronie?
        html = page.content()[:3000]
        print(html[:2000])

    browser.close()

# zapisz
(BASE / "playwright_capture_out.json").write_text(
    json.dumps(captured, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nPrzechwycono {len(captured)} zdarzen. Zapisano do playwright_capture_out.json")
