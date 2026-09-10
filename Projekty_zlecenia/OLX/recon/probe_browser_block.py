# coding: utf-8
"""
Probe: dlaczego strona kategorii OLX nie laduje ofert w headless Chromium?

Przechwytuje:
  - statusy odpowiedzi (response) na XHR/fetch
  - bledy konsoli
  - tresc HTML (czy sa tam jakies dane ofert, np. __NEXT_DATA__)

Uruchamienie: python probe_browser_block.py
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://www.olx.pl/elektronika/telefony/q-iphone/"
LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL",
        )
        page = ctx.new_page()

        console_msgs = []
        responses = []

        page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text[:200]}"))
        page.on("response", lambda r: responses.append((r.status, r.url[:200])))

        print(f"Goto {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        # zbadaj HTML
        html = page.content()
        print(f"HTML length: {len(html)}")
        print(f"HTML zawiera 'offer': {'offer' in html.lower()}")
        print(f"HTML zawiera '__NEXT_DATA__': {'__NEXT_DATA__' in html}")
        print(f"HTML zawiera '403': {'403' in html}")
        print(f"HTML zawiera 'CloudFront': {'cloudfront' in html.lower()}")

        # pierwsze 500 znakow body
        body_text = page.locator("body").inner_text()
        print(f"\nBody text (300): {body_text[:300]!r}")

        # zapisz html do pliku
        (LOG_DIR / "browser_page.html").write_text(html, encoding="utf-8")

        print(f"\n=== Odpowiedzi (status, url) ===")
        for status, url in responses:
            if "/api/" in url or status >= 400:
                print(f"  {status} {url}")

        print(f"\n=== Console (bledy) ===")
        for m in console_msgs[:30]:
            print(f"  {m}")

        browser.close()


if __name__ == "__main__":
    run()