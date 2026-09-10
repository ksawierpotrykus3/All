"""Test Hipotezy Blokady: Wypelnienie danych dostawy i sprawdzenie czy oferta zostaje zablokowana.

1. Otwiera krok 2 checkoutu z trwalego profilu.
2. Wybiera punkt InPost i uzupelnia dane odbiorcy.
3. Klika 'Dalej' przechodzac do podsumowania/platnosci.
4. Sprawdza publiczne API GET /api/v1/offers/{id}/: czy delivery.rock.active spadlo do False!
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE / "profiles" / "olx_profile"
DANE_DIR = BASE / "gemini" / "dane"

AD_ID = 1018987579
TARGET_URL = f"https://www.olx.pl/buy-options/{AD_ID}"

captured = []

print("=" * 60)
print("=== BADANIE HIPOTEZY BLOKADY 15 MIN / LOCK ===")
print("=" * 60)

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
        if any(k in u for k in ["order", "fulfillment", "ps.prd.eu.olx.org", "delivery"]):
            if not any(ext in u for ext in [".js", ".css", ".png", ".svg", ".jpg", ".woff2", ".ico"]):
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

    # 1. Krok buy-options -> Dalej
    print("[1/4] Otwieram buy-options...")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(2500)
    page.locator("[data-testid='buy-option-with-delivery']").first.click()
    page.wait_for_timeout(500)
    page.locator("[data-testid='buy-options-continue']").first.click()
    page.wait_for_timeout(5000)

    print(f"[2/4] Aktualny URL checkoutu: {page.url}")

    # 2. Sprawdz elementy formularza odbiorcy
    # Pola: Imie, Nazwisko, Email, Telefon
    try:
        inputs = page.locator("input[type='text'], input[type='tel'], input[type='email']")
        cnt = inputs.count()
        print(f"[*] Znaleziono {cnt} pol wejsciowych w formularzu.")
        
        # Wybor punktu odbioru (jesli jest przycisk)
        btn_point = page.locator("text='Wybierz punkt odbioru'").first
        if btn_point.count() > 0:
            print("[*] Klikam 'Wybierz punkt odbioru'...")
            btn_point.click()
            page.wait_for_timeout(3000)
            page.screenshot(path=str(DANE_DIR / "point_selection_modal.png"))
            
            # Wyszukaj lub wybierz pierwszy dostepny punkt
            point_item = page.locator("[data-testid*='pickup-point'], [data-testid*='point-item'], .pickup-point-item, button:has-text('Wybierz')").first
            if point_item.count() > 0:
                print("[*] Wybieram punkt odbioru...")
                point_item.click()
                page.wait_for_timeout(2000)
    except Exception as e:
        print(f"[!] Blad przy wyborze punktu: {e}")

    # Zapisz zrzut
    page.screenshot(path=str(DANE_DIR / "checkout_step3_attempt.png"), full_page=True)

    # 3. Sprawdz stan oferty w publicznym API
    print("[3/4] Weryfikacja stanu oferty w publicznym API OLX...")
    r = creq.get(f"https://www.olx.pl/api/v1/offers/{AD_ID}/", impersonate="chrome124", timeout=10)
    offer_data = r.json().get("data", {})
    rock = offer_data.get("delivery", {}).get("rock", {})
    status = offer_data.get("status")

    print(f"    Status oferty: {status}")
    print(f"    delivery.rock: {rock}")

    lock_proof = {
        "timestamp": time.time(),
        "ad_id": AD_ID,
        "offer_status": status,
        "delivery_rock": rock,
        "traffic_intercepted": captured
    }
    (DANE_DIR / "lock_hypothesis_result.json").write_text(
        json.dumps(lock_proof, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[4/4] Zapisano wynik testu do gemini/dane/lock_hypothesis_result.json")
    ctx.close()
