"""Probe 4: czy samo-odblokowanie przez PRZECHLAPCINCY/przechwyc_token_incognia
(produkcyjna ścieżka z checkout.py:514) nadal działa i daje cookie ważne dla API.

Flow:
  1) Przeszukaj stronę katalogu w Camoufox (interstitial się rozwiąże na stronie)
     -> zbierz item_id pierwszej oferty (bez API!).
  2) przechwyc_token_incognia(item_id, PROFIL) -> klik "Kup teraz" -> slider -> mocne cookies.
  3) Test: catalog API przez curl_cffi z mocnymi cookies (oczekiwane 200).
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"


def main() -> int:
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG
    from vintedbot.incognia_harvest import przechwyc_token_incognia
    from vintedbot.config import tls_kwargs, IMPERSONATE
    import curl_cffi.requests as creq

    wynik = {}

    # 1) Scrape item_id ze strony katalogu (bez API, strona przechodzi interstitial).
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/catalog?search_text=nike&order=newest_first",
                  wait_until="domcontentloaded", timeout=60000)
        for _ in range(12):  # do 60s na interstitial + render
            time.sleep(5)
            hrefs = page.eval_on_selector_all(
                "a[href*='/items/']", "els => els.map(e => e.href)")
            if hrefs:
                break
        ids = []
        for h in hrefs:
            m = re.search(r"/items/(\d+)", h)
            if m:
                ids.append(int(m.group(1)))
        wynik["item_ids_ze_strony"] = ids[:10]
        print(f"[p4] item_ids ze strony: {ids[:10]}", flush=True)

    if not ids:
        wynik["error"] = "brak item_id ze strony"
        (ROOT / "output" / "probe_datadome4.json").write_text(
            json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
        return 1

    # 2) Produkcyjne samo-odblokowanie: harvest + slider na pierwszym itemie.
    t0 = time.monotonic()
    h = przechwyc_token_incognia(ids[0], PROFIL, timeout_s=60)
    wynik["harvest"] = {k: (h[k] if not isinstance(h[k], dict) else "dict")
                        for k in ("token", "status_build", "segmenty", "slider_proba",
                                  "slider_solved") if k in h}
    wynik["harvest_czas_s"] = round(time.monotonic() - t0, 1)
    wynik["harvest_cookies_n"] = len(h.get("cookies", {}))
    print(f"[p4] harvest: {json.dumps(wynik['harvest'], ensure_ascii=False)} "
          f"cookies={wynik['harvest_cookies_n']}", flush=True)

    # 3) Katalog przez curl_cffi z cookies z harvestu.
    if h.get("cookies"):
        s = creq.Session(impersonate=IMPERSONATE)
        s.cookies.update(h["cookies"])
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
            print(f"[p4] katalog #{i+1}: HTTP {r.status_code} {ms:.0f} ms "
                  f"{len(r.content)//1024} KB", flush=True)
            time.sleep(1.3)
        s.close()

    (ROOT / "output" / "probe_datadome4.json").write_text(
        json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[p4] wynik: {json.dumps(wynik, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
