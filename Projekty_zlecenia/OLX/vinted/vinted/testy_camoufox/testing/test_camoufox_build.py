# coding: utf-8
"""Test: Camoufox (swiezy profil, fingerprint preset) + cookies_profil.json -> klik 'Kup teraz'
-> czy checkout/build wyszedl i jaki status. Loguje incognia token."""
import json
from pathlib import Path

from camoufox import Camoufox

BASE = Path(__file__).resolve().parent
COOKIES_FILE = BASE / "cookies_profil.json"
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"

cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
results = {"requests": [], "responses": []}


def main():
    with Camoufox(headless=True, os="windows", fingerprint_preset=True,
                  humanize=True) as ctx:
        page = ctx.new_page()

        def on_request(req):
            if "checkout/build" in req.url or "checkout/payment" in req.url:
                hdrs = req.headers
                entry = {
                    "method": req.method, "url": req.url,
                    "has_incognia": "x-incognia-request-token" in hdrs,
                    "ua": hdrs.get("user-agent", "")[:80],
                    "referer": hdrs.get("referer", ""),
                    "body": (req.post_data or "")[:200],
                }
                results["requests"].append(entry)
                print(f"[REQ] {req.method} {req.url}")
                print(f"  incognia={entry['has_incognia']} ua={entry['ua']}")
                print(f"  referer={entry['referer']}")
                print(f"  body={entry['body']}")

        def on_response(res):
            if "checkout/build" in res.url or "checkout/payment" in res.url:
                body = ""
                try:
                    body = res.text()[:400]
                except Exception:
                    pass
                results["responses"].append({"status": res.status, "url": res.url, "body": body})
                print(f"[RESP] {res.status} {res.url}")
                print(f"  body={body}")

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        # cookies do domeny
        page.context.add_cookies(cookies)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        logged = page.evaluate('document.body.innerHTML.includes("Moje konto")')
        print("Zalogowany: " + str(logged))

        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        btn = page.query_selector('button[data-testid="item-buy-button"]')
        if btn:
            print("Przycisk 'Kup teraz' istnieje")
            page.click('button[data-testid="item-buy-button"]')
            print("Kliknieto")
            page.wait_for_timeout(10000)
        else:
            print("Przycisk NIE istnieje")

    (BASE / "camoufox_build_out.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Zapisano camoufox_build_out.json")


if __name__ == "__main__":
    main()
