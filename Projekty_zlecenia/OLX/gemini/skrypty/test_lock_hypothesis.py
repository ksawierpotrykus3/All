"""Test hipotezy blokady 15 min: czy przejście do podsumowania płatności blokuje ofertę.

BEZPIECZEŃSTWO:
  - Wypełnia dane odbiorcy i przechodzi do podsumowania/platnosci,
  - NIE wysyla platnosci (nie klika finalnego zatwierdzenia BLIK/PayU),
  - Mozliwe, ze oferta zostanie zablokowana dla innych na ~15 min (zaakceptowane).

Weryfikuje publiczne API:
  GET https://www.olx.pl/api/v1/offers/{ad_id}/  ->  delivery.rock.active
  przed i po przejsciu flowu, zapisujac dowod do gemini/dane/lock_hypothesis_result.json.
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE / "profiles" / "olx_profile"
DANE_DIR = BASE / "gemini" / "dane"
DANE_DIR.mkdir(parents=True, exist_ok=True)

AD_ID = 1018987579
OFFER_API = f"https://www.olx.pl/api/v1/offers/{AD_ID}/"

RECIPIENT = {
    "firstName": "Ksaw",
    "lastName": "Ksaw",
    "email": "ksawierpotrykus3@gmail.com",
    "phoneNumber": "515151600",
}


def get_rock_active() -> dict:
    """Zwroc status oferty i delivery.rock z publicznego API."""
    try:
        r = creq.get(OFFER_API, impersonate="chrome124", timeout=15)
        data = (r.json() or {}).get("data", {})
        return {
            "http_status": r.status_code,
            "offer_status": data.get("status"),
            "rock": data.get("delivery", {}).get("rock", {}),
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 64)
    print("=== TEST HIPOTEZY BLOKADY 15 MIN (bez platnosci) ===")
    print("=" * 64)

    # Stan przed
    before = get_rock_active()
    print(f"\n[PRZED] delivery.rock: {json.dumps(before, ensure_ascii=False)}")

    captured = []
    before_rock = before.get("rock", {})

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            locale="pl-PL",
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_resp(resp):
            req = resp.request
            u = req.url
            if "ps.prd.eu.olx.org" in u and not any(ext in u for ext in (".js", ".css", ".png", ".svg", ".jpg", ".woff2", ".ico")):
                entry = {
                    "method": req.method,
                    "url": u,
                    "status": resp.status,
                    "post_data": req.post_data,
                }
                try:
                    entry["json"] = resp.json()
                except Exception:
                    pass
                captured.append(entry)
                print(f"[{req.method}] {resp.status} {u}")

        page.on("response", on_resp)

        # 1. buy-options -> wybierz dostawę -> dalej
        print("\n[1/4] Otwieram /buy-options/ i przechodzę do checkoutu...")
        page.goto(f"https://www.olx.pl/buy-options/{AD_ID}", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)

        try:
            page.locator("[data-testid='buy-option-with-delivery']").first.click(timeout=10000)
            page.wait_for_timeout(600)
            page.locator("[data-testid='buy-options-continue']").first.click(timeout=10000)
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"[!] Blad przy przejściu do checkoutu: {e}")
            page.screenshot(path=str(DANE_DIR / "lock_step1_error.png"), full_page=True)

        print(f"[2/4] URL checkoutu: {page.url}")

        # 2. Wypełnij dane odbiorcy
        print("[*] Wypełniam dane odbiorcy...")
        for key, sel in (
            ("firstName", "personalDetails.firstName"),
            ("lastName", "personalDetails.lastName"),
            ("email", "personalDetails.email"),
            ("phoneNumber", "personalDetails.phoneNumber"),
        ):
            try:
                loc = page.locator(f"[data-testid='{sel}']").first
                loc.wait_for(state="visible", timeout=10000)
                loc.fill(RECIPIENT[key])
                print(f"    + {sel} = {RECIPIENT[key]}")
            except Exception as e:
                print(f"    ! blad {sel}: {e}")

        page.screenshot(path=str(DANE_DIR / "lock_step2_filled.png"), full_page=True)

        # 3. Kliknij Dalej (data-testid=button-action) -> podsumowanie/platnosc
        print("[3/4] Klikam Dalej (do podsumowania/platnosci)...")
        try:
            btn = page.locator("[data-testid='button-action']").first
            btn.wait_for(state="visible", timeout=10000)
            btn.click(timeout=10000)
            page.wait_for_timeout(6000)
        except Exception as e:
            print(f"[!] Blad przy kliknięciu Dalej: {e}")

        print(f"[*] URL po Dalej: {page.url}")
        page.screenshot(path=str(DANE_DIR / "lock_step3_summary.png"), full_page=True)
        ctx.close()

    # 4. Stan po
    print("\n[4/4] Sprawdzam delivery.rock PO przejściu flowu...")
    time.sleep(2)
    after = get_rock_active()
    print(f"[PO] delivery.rock: {json.dumps(after, ensure_ascii=False)}")

    result = {
        "timestamp": time.time(),
        "ad_id": AD_ID,
        "offer_api": OFFER_API,
        "recipient_used": RECIPIENT,
        "before": before,
        "after": after,
        "rock_active_changed": before_rock.get("active") != after.get("rock", {}).get("active"),
        "traffic": captured,
    }
    out = DANE_DIR / "lock_hypothesis_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Zapisano wynik do {out}")

    if before_rock.get("active") is True and after.get("rock", {}).get("active") is False:
        print("\n[WYNIK] BLOKADA POTWIERDZONA: delivery.rock.active spadł True -> False.")
    elif before_rock.get("active") == after.get("rock", {}).get("active"):
        print("\n[WYNIK] BRAK ZMIANY delivery.rock.active — blokada NIE nastąpiła na tym kroku.")
    else:
        print("\n[WYNIK] Zmiana niejednoznaczna — sprawdź plik.")


if __name__ == "__main__":
    main()