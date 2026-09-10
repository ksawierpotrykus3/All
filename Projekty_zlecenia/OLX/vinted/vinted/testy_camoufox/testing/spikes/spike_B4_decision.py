# coding: utf-8
"""Spike B5: Weryfikacja HIPOTEZY że Incognia SDK ładuje się przy checkout flow.

Wcześniejsze odkrycie (B4): SDK Incognia NIE jest w żadnym pobranym skrypcie
strony przedmiotu, ale w HTML jest INCOGNIA_WEB_CLIENT_SIDE_KEY.

Hipoteza: SDK Incognia ładuje się dynamicznie dopiero przy przejściu do
checkout flow (initiated przez kliknięcie 'Kup').

Test:
  1) Otwórz stronę przedmiotu
  2) Sprawdź czy SDK Incognia się załadował po 10s -> BRAK
  3) Kliknij "Kup teraz" (trusted click)
  4) Monitoruj network 30s pod kątem requestów do incognia.com
  5) Sprawdź czy pojawia się window.Incognia

Wynik: jeśli SDK Incognia ładuje się dopiero przy checkout, to:
  -NIE MOŻNA użyć curl_cffi nawet z harvestowanymi cookies
  -NIE MA sensu budować lekkiego silnika JS (Incognia i tak musi załadować
   swój własny runtime, więc już jest silnikiem JS)
  -JEDYNA strategia = Camoufox z pełną aktywnością (co już mamy - 100% pass rate)

Dodatkowy test: czy SDK Incognia ma jakiś URL statyczny, z którego można go
załadować poza Vinted (np. unpkg.com/incognia-sdk).
"""
import json
import time
from pathlib import Path

from camoufox.sync_api import Camoufox

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
OUTPUT = Path(r"C:\Temp\wynik_spike_B5_incognia_load_on_action.json")
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    findings = {"phases": []}

    with Camoufox(headless=True, persistent_context=True,
                  user_data_dir=PROFIL, locale="pl-PL") as cf:
        page = cf.new_page() if hasattr(cf, "new_page") else cf.pages[0]

        incognia_requests = []
        all_urls_after_click = []

        def on_request(req):
            try:
                url = req.url
                if "incognia" in url.lower():
                    incognia_requests.append({
                        "url": url, "method": req.method,
                        "resource_type": req.resource_type,
                        "ts": time.time(),
                    })
                if req.resource_type == "script":
                    all_urls_after_click.append(url)
            except Exception:
                pass

        page.on("request", on_request)

        print(f"[B5] Otwieram {ITEM_URL}", flush=True)
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        phase1 = page.evaluate("""
() => ({
  has_Incognia: typeof window.Incognia,
  incog_keys: Object.getOwnPropertyNames(window).filter(k => /incog/i.test(k)),
  dd_loaded: typeof window.dd !== 'undefined',
  ddjskey: window.ddjskey,
})""")
        findings["phases"].append({"phase": "1_before_click", "state": phase1,
                                    "incognia_requests_so_far": len(incognia_requests)})
        print(f"[B5] Phase 1: {phase1}", flush=True)

        # Szukaj przycisku "Kup teraz" / "Buy now"
        buy_button = None
        for selector in [
            'button:has-text("Kup teraz")',
            'button:has-text("Kup")',
            '[data-testid="buy-now"]',
            'button:has-text("Buy")',
            'a:has-text("Kup")',
        ]:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=1000):
                    buy_button = el
                    print(f"[B5] Found buy button with selector: {selector}", flush=True)
                    break
            except Exception:
                continue

        if buy_button:
            print("[B5] Klikam 'Kup teraz' (trusted click)...", flush=True)
            try:
                buy_button.click(timeout=5000)
            except Exception as e:
                print(f"[B5] Click error: {e}", flush=True)
        else:
            print("[B5] Nie znaleziono przycisku 'Kup'", flush=True)
            # Spróbuj scroll + sprawdź wszystkie buttony
            all_buttons = page.evaluate("""
() => Array.from(document.querySelectorAll('button, a[role=button]'))
  .map(b => ({tag: b.tagName, text: b.textContent.trim().substring(0, 50),
               href: b.href, classes: b.className.substring(0, 100)}))
""")
            findings["all_buttons"] = all_buttons[:30]
            print(f"[B5] Buttons na stronie: {len(all_buttons)}", flush=True)

        # Czekaj 15s na reakcję
        time.sleep(15)

        phase2 = page.evaluate("""
() => ({
  has_Incognia: typeof window.Incognia,
  has_incogniaSdk: typeof window.IncogniaSDK,
  incog_keys: Object.getOwnPropertyNames(window).filter(k => /incog/i.test(k)),
  current_url: location.href,
  modal_count: document.querySelectorAll('[role=dialog], .modal, [class*=modal]').length,
  has_iframe_incognia: !!document.querySelector('iframe[src*="incognia"]'),
})""")
        findings["phases"].append({"phase": "2_after_click", "state": phase2,
                                    "incognia_requests_total": len(incognia_requests),
                                    "scripts_after_click": all_urls_after_click[-20:]})
        print(f"[B5] Phase 2: {phase2}", flush=True)
        print(f"[B5] Incognia requests total: {len(incognia_requests)}", flush=True)

        # Sprawdź też czy może Incognia potrzebuje scrollowania
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(5)
        phase3 = page.evaluate("""
() => ({
  has_Incognia: typeof window.Incognia,
  incog_keys: Object.getOwnPropertyNames(window).filter(k => /incog/i.test(k)),
})""")
        findings["phases"].append({"phase": "3_after_scroll", "state": phase3})
        print(f"[B5] Phase 3: {phase3}", flush=True)

        findings["incognia_requests"] = incognia_requests
        findings["incognia_requests_total"] = len(incognia_requests)

    OUTPUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[B5] Zapisano {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
