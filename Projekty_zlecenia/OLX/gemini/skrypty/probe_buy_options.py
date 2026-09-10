"""Probe prawdziwej sciezki zakupu OLX: /buy-options/{offer_id}."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE / "profiles" / "olx_profile"
DANE_DIR = BASE / "gemini" / "dane"
DANE_DIR.mkdir(parents=True, exist_ok=True)

OFFER_ID = sys.argv[1] if len(sys.argv) > 1 else "1018987579"
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
        if any(k in u for k in ["delivery", "buy", "rock", "order", "pricing", "checkout", "api", "graphql"]):
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

    print(f"[*] Otwieram docelowy URL: {TARGET_URL}")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(6000)

    cur_url = page.url
    print(f"[*] URL koncowy: {cur_url}")

    shot_path = DANE_DIR / f"buy_options_{OFFER_ID}.png"
    page.screenshot(path=str(shot_path), full_page=True)
    print(f"[+] Zapisano zrzut: {shot_path}")

    # Wyciagnij elementy formularza i przyciski
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
    print(f"[+] Wykryto {len(filtered)} elementow interaktywnych w DOM:")
    for el in filtered[:30]:
        print(f"    - <{el['tag']}> testId='{el['testId']}' text='{el['text']}' href='{el['href']}'")

    (DANE_DIR / f"buy_options_{OFFER_ID}_dom.json").write_text(
        json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (DANE_DIR / f"buy_options_{OFFER_ID}_traffic.json").write_text(
        json.dumps(captured, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    ctx.close()

print("[*] Z zakonczono sukcesem.")
