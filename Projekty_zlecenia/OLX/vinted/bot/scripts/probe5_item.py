"""Probe 5: dlaczego harvest nie kliknął "Kup teraz"?
Otwiera stronę itemu (headless), czeka na realny content, sprawdza selektery przycisku."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
ITEM_ID = 9859425123  # ten sam co w harvest (probe 4)
DEBUG = ROOT / "output" / "probe5"


def main() -> int:
    DEBUG.mkdir(exist_ok=True)
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG

    wynik = {"item_id": ITEM_ID}
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto(f"https://www.vinted.pl/items/{ITEM_ID}",
                  wait_until="domcontentloaded", timeout=60000)
        # Czekaj na realny content (do 40s).
        for i in range(8):
            time.sleep(5)
            try:
                txt = page.locator("body").inner_text(timeout=2000)
            except Exception:
                txt = ""
            wynik[f"proba_{i+1}"] = {"t": i + 1, "dlugosc": len(txt),
                                     "frag": txt[:80].replace("\n", " ")}
            if "Kup teraz" in txt or "Sprzedano" in txt or len(txt) > 500:
                break
        page.screenshot(path=str(DEBUG / "item.png"), full_page=False)
        wynik["tytul"] = page.title()
        # Selektory przycisku zakupu.
        for sel in ["[data-testid='item-buy-button']", "[data-testid='item-buy-button-secondary']",
                    "button:has-text('Kup teraz')"]:
            try:
                n = page.locator(sel).count()
                wynik[f"sel:{sel}"] = n
            except Exception as e:
                wynik[f"sel:{sel}"] = f"ERR {e}"
        # Czy jest status sprzedany / niedostępny?
        txt_full = ""
        try:
            txt_full = page.locator("body").inner_text(timeout=5000)
        except Exception:
            pass
        wynik["sprzedano"] = "Sprzedano" in txt_full
        wynik["niedostepne"] = ("niedostępne" in txt_full or "unavailable" in txt_full.lower())
        wynik["body_koniec"] = txt_full[-200:].replace("\n", " ")

    (ROOT / "output" / "probe5_item.json").write_text(
        json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
