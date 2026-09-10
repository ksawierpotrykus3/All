"""Probe 3: decydujący test — cookies po rozwiązaniu interstitialu vs katalog API.

Flow: goto -> czekaj na REALNĄ stronę (do 40s) -> eksport cookies -> catalog przez curl_cffi.
Jeśli 200 -> fix: _swieze_cookies musi czekać na realną stronę zamiast 2.5s.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
MARKERY = ("Przedmioty", "Sprzedaj", "Kobiety", "Wyszukaj")


def main() -> int:
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG
    from vintedbot.config import wczytaj_cookies, tls_kwargs, IMPERSONATE
    import curl_cffi.requests as creq

    wynik = {}
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        t0 = time.monotonic()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        # Czekaj aż pojawi się REALNY content (interstitial DataDome się rozwiąże).
        realna_strona = False
        for _ in range(8):  # 8 x 5s = 40s max
            time.sleep(5)
            if page.locator("body").count():
                try:
                    txt = page.locator("body").inner_text(timeout=2000)
                except Exception:
                    txt = ""
                if any(m in txt for m in MARKERY):
                    realna_strona = True
                    break
        wynik["realna_strona"] = realna_strona
        wynik["czekanie_s"] = round(time.monotonic() - t0, 1)
        raw = ctx.cookies()
        cookies = {c.get("name", ""): c.get("value", "") for c in raw if c.get("name")}
        dd = {k: v for k, v in cookies.items() if "datadome" in k.lower()}
        wynik["dd_len"] = {k: len(v) for k, v in dd.items()}

        # Katalog przez curl_cffi z tymi cookies.
        s = creq.Session(impersonate=IMPERSONATE)
        s.cookies.update(cookies)
        s.headers.update({"Accept-Language": "pl-PL,pl;q=0.9"})
        for i in range(3):
            t1 = time.perf_counter()
            r = s.get(
                "https://www.vinted.pl/api/v2/catalog/items",
                params={"catalog_ids[]": "1206", "currency": "PLN",
                        "order": "newest_first", "per_page": 5},
                **tls_kwargs(), timeout=15,
            )
            ms = (time.perf_counter() - t1) * 1000
            wynik[f"katalog_{i+1}"] = {"http": r.status_code, "ms": round(ms, 1),
                                       "kb": len(r.content) // 1024}
            print(f"[p3] katalog #{i+1}: HTTP {r.status_code} {ms:.0f} ms "
                  f"{len(r.content)//1024} KB", flush=True)
            time.sleep(1.3)
        s.close()

    (ROOT / "output" / "probe_datadome3.json").write_text(
        json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[p3] wynik: {json.dumps(wynik, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
