# coding: utf-8
"""
Przechwyc requesty API wysylane przez frontend OLX na stronach kategorii.

Cel: dowiedziec sie, jak PRZEGLADARKA pobiera oferty (jakie endpointy, parametry,
kategorie), zebysmy uzywali tego samego zrodla danych co front - a nie zgadywali.

Uruchamienie: python probe_browser.py
Zapisuje: logs/browser_requests.jsonl (wszystkie requesty do /api/)
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
OUT = LOG_DIR / "browser_requests.jsonl"

URLS = [
    "https://www.olx.pl/elektronika/telefony/q-iphone/",
    "https://www.olx.pl/elektronika/komputery/laptopy/q-macbook/",
    "https://www.olx.pl/motoryzacja/samochody/q-bmw/",
]


def run():
    api_requests = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL",
        )
        page = ctx.new_page()

        def on_request(req):
            if "/api/" in req.url:
                api_requests.append({
                    "url": req.url,
                    "method": req.method,
                    "resource_type": req.resource_type,
                })

        page.on("request", on_request)

        for url in URLS:
            print(f"\n=== {url} ===")
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(5000)
                # przewin w dol, zeby front doladowal kolejne oferty
                for _ in range(5):
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(1500)
                print(f"  title: {page.title()!r}")
                print(f"  widoczne linki ogloszen: {page.locator('a[href*=\"olx.pl/d/oferta\"]').count()}")
            except Exception as e:  # noqa: BLE001
                print(f"  BLAD: {e}")

        browser.close()

    # zapisz unikalne requesty
    seen = set()
    unique = []
    for r in api_requests:
        key = r["url"].split("?")[0] + "|" + r["method"]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    with open(OUT, "w", encoding="utf-8") as f:
        for r in api_requests:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n=== PODSUMOWANIE: {len(api_requests)} requestow API, {len(unique)} unikalnych endpointow ===")
    for r in unique:
        print(f"  {r['method']:6} {r['resource_type']:8} {r['url']}")


if __name__ == "__main__":
    run()