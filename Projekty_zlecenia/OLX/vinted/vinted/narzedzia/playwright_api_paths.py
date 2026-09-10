# coding: utf-8
"""Przechwyc WSZYSTKIE requesty do /api/ (bez filtra 'catalog') na stronie kategorii.
Zapisuje pelne URL do pliku, zeby zobaczyc jaka jest prawdziwa nazwa parametru."""
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

api_requests = []

def on_request(req):
    u = req.url
    if "/api/" in u:
        api_requests.append(u)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="pl-PL",
        viewport={"width": 1366, "height": 900},
    )
    ctx.add_cookies(load_cookies())
    page = ctx.new_page()
    page.on("request", on_request)

    # otworz strone konkretnej kategorii (women = 1904)
    url = "https://www.vinted.pl/catalog?catalog%5B%5D=1904&page=1"
    print("OTWIERAM:", url)
    page.goto(url, timeout=90000, wait_until="networkidle")
    time.sleep(8)

    print("TITLE:", page.title())

    browser.close()

# wypisz tylko unikalne api, skracajac do sensownej dlugosci
print("\n=== REQUESTY DO /api/ ===")
seen = set()
for u in api_requests:
    # normalizuj: zostaw tylko sciezke i query bez tokenow
    if "?" in u:
        base, q = u.split("?", 1)
        # usun dlugie wartosci (tokeny)
        seen.add(base)
    else:
        seen.add(u)

for s in sorted(seen):
    print(s)

with open("captured_api_paths.json", "w") as f:
    json.dump({"paths": sorted(seen), "raw_count": len(api_requests)}, f, indent=2)
print("\nUnikalnych sciezek:", len(seen), "| surowych requestow:", len(api_requests))