"""Test wyboru Paczkomatu przez data-testid='map-list-item' i weryfikacja blokady 15 min."""
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
print("=== DOKLADNY TEST WYBORU PACZKOMATU I BLOKADY OFERTY ===")
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

    # 1. Krok buy-options -> Dalej
    print("[1/5] Otwieram buy-options...")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(2500)
    page.locator("[data-testid='buy-option-with-delivery']").first.click()
    page.wait_for_timeout(500)
    page.locator("[data-testid='buy-options-continue']").first.click()
    page.wait_for_timeout(4500)
    print(f"[*] URL checkoutu: {page.url}")

    # 2. Wypelnij dane odbiorcy
    print("[2/5] Wypelniam dane odbiorcy...")
    for field, val in [
        ("personalDetails.firstName", "Ksaw"),
        ("personalDetails.lastName", "Ksaw"),
        ("personalDetails.email", "ksawierpotrykus3@gmail.com"),
        ("personalDetails.phoneNumber", "515151600"),
    ]:
        try:
            inp = page.locator(f"[data-testid='{field}']").first
            inp.wait_for(state="visible", timeout=5000)
            inp.fill(val)
            print(f"    - {field} = {val}")
        except Exception as e:
            print(f"    ! {field}: {e}")

    # 3. Wybierz Paczkomat przez potwierdzony selektor map-list-item
    print("[3/5] Otwieram modal wyboru Paczkomatu...")
    page.locator("[data-testid='select-locker']").first.click()
    page.wait_for_timeout(3000)

    print("[*] Wybieram punkt: data-testid='map-list-item'...")
    point_btn = page.locator("[data-testid='map-list-item']").first
    point_btn.wait_for(state="visible", timeout=8000)
    point_text = point_btn.inner_text().replace("\n", " ")
    print(f"    - Klikam punkt: {point_text[:50]}")
    point_btn.click()
    page.wait_for_timeout(3000)

    # Sprawdz czy pojawil sie przycisk potwierdzenia punktu (np. "Wybierz ten punkt")
    confirm_btn = page.locator("button:has-text('Wybierz ten punkt'), button:has-text('Zatwierdź'), [data-testid='confirm-point'], [data-testid='select-point-button']").first
    if confirm_btn.count() > 0:
        print("[*] Klikam potwierdzenie punktu...")
        confirm_btn.click()
        page.wait_for_timeout(2000)

    page.screenshot(path=str(DANE_DIR / "checkout_step3_paczkomat_selected.png"), full_page=True)
    print(f"[+] Zapisano zrzut: {DANE_DIR / 'checkout_step3_paczkomat_selected.png'}")

    # 4. Sprawdz przycisk Dalej na dole strony
    print("[4/5] Sprawdzam przycisk Dalej na formularzu...")
    dalej_btn = page.locator("[data-testid='button-action'], button:has-text('Dalej')").last
    print(f"    - Przycisk Dalej disabled: {dalej_btn.is_disabled()}")
    
    # Klikamy Dalej
    print("[*] Klikam Dalej...")
    dalej_btn.click()
    page.wait_for_timeout(6000)
    
    print(f"[*] URL po kliknieciu Dalej: {page.url}")
    page.screenshot(path=str(DANE_DIR / "checkout_step4_final.png"), full_page=True)
    print(f"[+] Zapisano zrzut po Dalej: {DANE_DIR / 'checkout_step4_final.png'}")

    ctx.close()

# 5. Sprawdz publiczne API oferty
print("[5/5] Weryfikacja stanu oferty w publicznym API OLX...")
r = creq.get(f"https://www.olx.pl/api/v1/offers/{AD_ID}/", impersonate="chrome124", timeout=10)
d = r.json().get("data", {})
rock = d.get("delivery", {}).get("rock", {})
status = d.get("status")

print(f"\n==================================================")
print(f"STAN PUBLICZNY OFERTY {AD_ID}:")
print(f"  Status: {status}")
print(f"  delivery.rock: {rock}")
print(f"==================================================")

proof = {
    "timestamp": time.time(),
    "ad_id": AD_ID,
    "offer_status": status,
    "delivery_rock": rock,
    "traffic": captured,
}
(DANE_DIR / "paczkomat_and_lock_proof.json").write_text(
    json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f"[+] Zapisano dowod do gemini/dane/paczkomat_and_lock_proof.json")
