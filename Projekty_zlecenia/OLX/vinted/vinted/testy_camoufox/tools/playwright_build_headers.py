# coding: utf-8
"""Playwright headless: przechwyc DOKLADNIE request checkout/build (wszystkie headery),
sprawdz czy incognia token jest wysylany. Dodatkowo wymus domyslny UA Opery GX z HAR."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
COOKIES_FILE = BASE / "cookies_profil.json"
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"

cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))

captured = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 OPR/134.0.0.0"),
        extra_http_headers={
            "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Opera GX";v="134"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
        viewport={"width": 1920, "height": 1080},
    )
    ctx.add_cookies(cookies)
    page = ctx.new_page()

    def on_request(req):
        if "checkout/build" in req.url or "checkout/payment" in req.url:
            captured.append({
                "method": req.method,
                "url": req.url,
                "headers": dict(req.headers),
                "post_data": req.post_data,
            })
            print(f"[REQ] {req.method} {req.url}")
            print(f"  incognia: {'x-incognia-request-token' in req.headers}")
            print(f"  referer: {req.headers.get('referer')}")
            print(f"  UA: {req.headers.get('user-agent')[:60]}")
            print(f"  BODY: {(req.post_data or '')[:300]}")

    def on_response(res):
        if "checkout/build" in res.url or "checkout/payment" in res.url:
            body = ""
            try:
                body = res.text()[:600]
            except Exception:
                pass
            print(f"[RESP] {res.status} {res.url}")
            print(f"  body: {body}\n")

    page.on("request", on_request)
    page.on("response", on_response)

    page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    logged = page.evaluate('document.body.innerHTML.includes("Moje konto")')
    ua = page.evaluate("navigator.userAgent")
    wd = page.evaluate("navigator.webdriver")
    print("Zalogowany: " + str(logged))
    print("UA page: " + ua[:60])
    print("webdriver: " + str(wd))

    btn = page.query_selector('button[data-testid="item-buy-button"]')
    if btn:
        page.click('button[data-testid="item-buy-button"]')
        print("Kliknieto 'Kup teraz'")
        page.wait_for_timeout(10000)
    else:
        print("Przycisk NIE istnieje")

    browser.close()

(BASE / "playwright_build_headers_out.json").write_text(
    json.dumps(captured, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nZapisano {len(captured)} zdarzen")
