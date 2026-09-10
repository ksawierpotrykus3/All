"""Krok 2 zakupu OLX: Wybierz opcje z dostawa i przejdz Dalej."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE / "profiles" / "olx_profile"
DANE_DIR = BASE / "gemini" / "dane"
DANE_DIR.mkdir(parents=True, exist_ok=True)

OFFER_ID = "1018987579"
TARGET_URL = f"https://www.olx.pl/buy-options/{OFFER_ID}"

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
        if any(k in u for k in ["delivery", "buy", "rock", "order", "pricing", "checkout", "api", "graphql", "payment"]):
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

    print(f"[*] Otwieram {TARGET_URL}...")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)

    # Kliknij "Kup z Pakietem Ochronnym"
    print("[*] Wybieram: buy-option-with-delivery...")
    opt = page.locator("[data-testid='buy-option-with-delivery']").first
    opt.click()
    page.wait_for_timeout(1000)

    # Kliknij "Dalej"
    print("[*] Klikam: Dalej (buy-options-continue)...")
    btn = page.locator("[data-testid='buy-options-continue']").first
    btn.click()
    page.wait_for_timeout(6000)

    cur_url = page.url
    print(f"[*] URL po kliknieciu Dalej: {cur_url}")

    shot_path = DANE_DIR / "checkout_step2.png"
    page.screenshot(path=str(shot_path), full_page=True)
    print(f"[+] Zapisano zrzut: {shot_path}")

    # Wyciagnij elementy DOM
    elements = page.eval_on_selector_all(
        "button, a, input, [data-testid]",
        """els => els.map(e => ({
            tag: e.tagName,
            text: (e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 100),
            testId: e.getAttribute('data-testid'),
            href: e.getAttribute('href'),
            name: e.getAttribute('name'),
            type: e.getAttribute('type'),
            value: e.value || null
        }))"""
    )
    filtered = [e for e in elements if e["text"] or e["testId"] or e["name"]]
    print(f"[+] Wykryto {len(filtered)} elementow w DOM po kroku 2.")

    (DANE_DIR / "checkout_step2_dom.json").write_text(
        json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (DANE_DIR / "checkout_step2_traffic.json").write_text(
        json.dumps(captured, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    ctx.close()

print("[*] Zakonczono pomyslnie.")
