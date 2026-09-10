"""Test blokady 15 min — wersja z wyborem Paczkomatu (pierwszy z listy).

BEZPIECZEŃSTWO: nie wysyła płatności; zatrzymuje się na podsumowaniu.
Wybiera pierwszy dostępny punkt odbioru, wypełnia dane, klika Dalej,
potem weryfikuje delivery.rock.active w publicznym API.
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


def get_rock() -> dict:
    try:
        r = creq.get(OFFER_API, impersonate="chrome124", timeout=15)
        d = (r.json() or {}).get("data", {})
        return {"status": r.status_code, "offer_status": d.get("status"), "rock": d.get("delivery", {}).get("rock", {})}
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 64)
    print("=== TEST BLOKADY 15 MIN (z wyborem Paczkomatu) ===")
    print("=" * 64)

    before = get_rock()
    print(f"\n[PRZED] {json.dumps(before, ensure_ascii=False)}")
    captured = []

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
                entry = {"method": req.method, "url": u, "status": resp.status, "post_data": req.post_data}
                try:
                    entry["json"] = resp.json()
                except Exception:
                    pass
                captured.append(entry)
                print(f"[{req.method}] {resp.status} {u}")

        page.on("response", on_resp)

        # 1. przejście do checkoutu
        print("\n[1/5] /buy-options -> checkout")
        page.goto(f"https://www.olx.pl/buy-options/{AD_ID}", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)
        page.locator("[data-testid='buy-option-with-delivery']").first.click(timeout=10000)
        page.wait_for_timeout(600)
        page.locator("[data-testid='buy-options-continue']").first.click(timeout=10000)
        page.wait_for_timeout(5000)
        print(f"URL: {page.url}")

        # 2. dane odbiorcy
        print("\n[2/5] wypełniam dane odbiorcy")
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
                print(f"  + {sel} = {RECIPIENT[key]}")
            except Exception as e:
                print(f"  ! {sel}: {e}")

        # 3. wybór Paczkomatu
        print("\n[3/5] wybór punktu odbioru (pierwszy z listy)")
        try:
            sel_btn = page.locator("[data-testid='select-locker']").first
            sel_btn.wait_for(state="visible", timeout=10000)
            sel_btn.click(timeout=10000)
            page.wait_for_timeout(3000)
            page.screenshot(path=str(DANE_DIR / "lock_paczkomat_modal.png"), full_page=True)

            # próbujemy różne selektory punktu
            point = None
            for s in (
                "[data-testid*='pickup-point']",
                "[data-testid*='point-item']",
                "[data-testid*='locker']",
                "button:has-text('Wybierz')",
                "li:has-text('Paczkomat')",
            ):
                cand = page.locator(s).first
                if cand.count() > 0:
                    point = cand
                    print(f"  znaleziono punkt przez: {s}")
                    break

            if point:
                point.click(timeout=10000)
                page.wait_for_timeout(2500)
                print("  wybrano punkt")
            else:
                print("  ! nie znaleziono selektora punktu — zrzut zapisany")
                page.screenshot(path=str(DANE_DIR / "lock_paczkomat_no_point.png"), full_page=True)
        except Exception as e:
            print(f"  ! błąd wyboru punktu: {e}")

        # 4. Dalej
        print("\n[4/5] klikam Dalej")
        try:
            btn = page.locator("[data-testid='button-action']").first
            btn.wait_for(state="visible", timeout=10000)
            btn.click(timeout=10000)
            page.wait_for_timeout(6000)
        except Exception as e:
            print(f"  ! błąd Dalej: {e}")

        print(f"URL po Dalej: {page.url}")
        page.screenshot(path=str(DANE_DIR / "lock_step4_after_paczkomat.png"), full_page=True)
        ctx.close()

    # 5. weryfikacja
    print("\n[5/5] weryfikacja delivery.rock PO")
    time.sleep(2)
    after = get_rock()
    print(f"[PO] {json.dumps(after, ensure_ascii=False)}")

    result = {
        "timestamp": time.time(),
        "ad_id": AD_ID,
        "recipient": RECIPIENT,
        "before": before,
        "after": after,
        "changed": before.get("rock", {}).get("active") != after.get("rock", {}).get("active"),
        "traffic": captured,
    }
    out = DANE_DIR / "lock_hypothesis_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] zapisano {out}")

    b = before.get("rock", {}).get("active")
    a = after.get("rock", {}).get("active")
    if b is True and a is False:
        print("\n[WYNIK] BLOKADA POTWIERDZONA (True -> False)")
    elif b == a:
        print("\n[WYNIK] BRAK ZMIANY — blokada nie nastąpiła na tym kroku")
    else:
        print("\n[WYNIK] niejednoznaczne")


if __name__ == "__main__":
    main()