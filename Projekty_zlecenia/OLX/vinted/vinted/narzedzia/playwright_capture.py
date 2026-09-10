# coding: utf-8
"""Playwright: przechwyc WSZYSTKIE requesty (nie tylko katalog). Ground truth."""
import json, time
from playwright.sync_api import sync_playwright

COOKIES_FILE = r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\cookies.txt"

def load_cookies():
    cookies = []
    with open(COOKIES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies.append({
                    "name": parts[5],
                    "value": parts[6],
                    "domain": parts[0],
                    "path": parts[2],
                })
    return cookies

captured = []

def on_request(req):
    u = req.url
    if "vinted" in u and ("/api/" in u or "catalog" in u):
        captured.append({"method": req.method, "url": u})

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="pl-PL",
        viewport={"width": 1366, "height": 900},
    )
    ctx.add_cookies(load_cookies())
    page = ctx.new_page()

    # podlacz listener PRZED goto
    page.on("request", on_request)

    print("OTWIERAM katalog (dluzszy wait)...")
    page.goto("https://www.vinted.pl/catalog", timeout=90000, wait_until="networkidle")
    time.sleep(8)

    # zrzut tytulu strony i czy jest captcha
    print("TITLE:", page.title())
    body = page.content()
    print("BODY len:", len(body))
    print("DataDome/captcha w body:", any(x in body for x in ["datadome", "captcha", "challenge"]))

    # proba klikniecia kategorii - szukaj linku breadcrumb
    try:
        links = page.eval_on_selector_all("a[href*='/catalog/']", "els => els.map(e => e.href)")
        print("Znalezione linki kategorii:", len(links))
        for l in links[:5]:
            print("  ", l)
        if links:
            page.click(f"a[href*='/catalog/'] >> nth=0", timeout=10000)
            print("Kliknieto.")
            time.sleep(6)
    except Exception as e:
        print("Klikniecie nieudane:", repr(e))

    browser.close()

print("\n=== WSZYSTKIE PRZECHWYCONE (vinted + api/catalog) ===")
seen = set()
for c in captured:
    u = c["url"]
    # skroc do query
    if "?" in u:
        u = u.split("?", 1)[1]
    seen.add((c["method"], u))
for m, s in sorted(seen):
    print(f"[{m}] {s}")

with open("captured_requests.json", "w") as f:
    json.dump({"requests": [{"method": m, "query": s} for m, s in sorted(seen)]}, f, indent=2, ensure_ascii=False)
print("\nLiczba unikalnych:", len(seen))