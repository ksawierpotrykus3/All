"""Probe 6: czy strony itemów renderują się z przyciskiem "Kup teraz" (vs redirect na profil)."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
ITEMS = [9859425123, 9859424771, 9859422415, 9859423787, 9859423234,
         9859359951, 9851834183, 9859426224, 9859420333, 9859425359]


def main() -> int:
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG

    wyniki = []
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        for it in ITEMS:
            r = {"item": it}
            try:
                page.goto(f"https://www.vinted.pl/items/{it}",
                          wait_until="domcontentloaded", timeout=45000)
                time.sleep(6)  # daj czas na ewentualny interstitial + render
                r["tytul"] = page.title()
                r["url"] = page.url
                for sel in ["[data-testid='item-buy-button']",
                            "button:has-text('Kup teraz')"]:
                    try:
                        r[sel] = page.locator(sel).count()
                    except Exception as e:
                        r[sel] = f"ERR {e}"
                r["profil_redirect"] = "member profile" in page.title()
            except Exception as e:
                r["error"] = str(e)
            wyniki.append(r)
            buy = r.get("[data-testid='item-buy-button']")
            print(f"[p6] {it}: tytul={str(r.get('tytul','?'))[:40]!r} "
                  f"buy={buy} redirect={r.get('profil_redirect')}", flush=True)

    (ROOT / "output" / "probe6_items.json").write_text(
        json.dumps(wyniki, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
