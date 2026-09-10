# coding: utf-8
"""RETEST rezerwacji na koncie weraa13 przez Playwright (realna przegladarka).

Cel: sprawdzic, czy naturalna przegladarka (Chromium) z cookies Weroniki przejdzie
DataDome tam, gdzie curl_cffi dal 403.

BEZPIECZENSTWO:
- rezerwacja TYLKO na wlasny przedmiot Weroniki 9782578256 (potwierdzony przez SSR)
- brak platnosci (nie klikamy "Zaplac")
"""
import json
import time
from playwright.sync_api import sync_playwright

COOKIES_FILE = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\cookies_fresh.txt"
ITEM_ID = 9782578256
OUTPUT = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\wynik_playwright_rezerwacja.json"


def load_cookies_netscape(path):
    cookies = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, flag, path, secure, expires, name, value = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "expires": float(expires) if expires.isdigit() else -1,
                "httpOnly": False,
                "secure": secure == "TRUE",
                "sameSite": "Lax",
            })
    return cookies


def main():
    cookies = load_cookies_netscape(COOKIES_FILE)
    print(f"Zaladowano {len(cookies)} cookies")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="pl-PL",
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        results = {"steps": []}

        # KROK 1: naturalne wejscie na strone glowna (uzupelnienie fingerprint DataDome)
        print("KROK 1: otwieram strone glowna Vinted...")
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        results["steps"].append({"step": "home", "url": page.url, "title": page.title()})

        # KROK 2: wejscie na strone wlasnego przedmiotu
        item_url = f"https://www.vinted.pl/items/{ITEM_ID}"
        print("KROK 2: otwieram strone przedmiotu...")
        page.goto(item_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        results["steps"].append({"step": "item_page", "url": page.url})

        # KROK 3: przechwytujemy, co wysyla przegladarka przy checkout/build (bez klikania)
        # Najpierw sprawdzmy, czy jestesmy zalogowani jako weraa13
        print("KROK 3: sprawdzam tozsamosc przez API w kontekscie przegladarki...")
        resp = page.evaluate("""async () => {
            const r = await fetch('/api/v2/users/current', {headers: {'Accept': 'application/json'}});
            return {status: r.status, body: await r.text()};
        }""")
        results["steps"].append({"step": "identity_check", "data": resp})
        print("Identity:", resp.get("status"), (resp.get("body") or "")[:200])

        # KROK 4: proba rezerwacji checkout/build przez fetch w przegladarce
        print("KROK 4: proba rezerwacji checkout/build (BEZ platnosci)...")
        resp2 = page.evaluate("""async (itemId) => {
            const r = await fetch('/api/v2/purchases/checkout/build', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify({purchase_items: [{id: itemId, type: 'item'}]})
            });
            return {status: r.status, body: await r.text()};
        }""", ITEM_ID)
        results["steps"].append({"step": "checkout_build", "data": resp2})
        print("CHECKOUT BUILD STATUS:", resp2.get("status"))
        print("CHECKOUT BUILD BODY (first 600):", (resp2.get("body") or "")[:600])

        # zapisz wynik
        with open(OUTPUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Zapisano wynik do: {OUTPUT}")

        browser.close()


if __name__ == "__main__":
    main()