"""Probe 7: samo-odblokowanie przez produkcyjny harvest na DOBRYM itemie.

9859424771 ma buy=1 (probe6). Harvest klika "Kup teraz" -> build -> ewentualny slider.
Po harvest: test katalogu przez curl_cffi (oczekiwane 200 z mocnym cookie)."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
ITEM_ID = 9859424771


def main() -> int:
    from vintedbot.incognia_harvest import przechwyc_token_incognia
    from vintedbot.config import tls_kwargs, IMPERSONATE
    import curl_cffi.requests as creq

    wynik = {"item_id": ITEM_ID}
    t0 = time.monotonic()
    h = przechwyc_token_incognia(ITEM_ID, PROFIL, timeout_s=60)
    wynik["czas_s"] = round(time.monotonic() - t0, 1)
    wynik["harvest"] = {k: (h[k] if not isinstance(h[k], dict) else "dict")
                        for k in ("token", "status_build", "segmenty",
                                  "slider_proba", "slider_solved") if k in h}
    wynik["cookies_n"] = len(h.get("cookies", {}))
    print(f"[p7] harvest: {json.dumps(wynik['harvest'], ensure_ascii=False)} "
          f"czas={wynik['czas_s']}s cookies={wynik['cookies_n']}", flush=True)

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
            print(f"[p7] katalog #{i+1}: HTTP {r.status_code} {ms:.0f} ms "
                  f"{len(r.content)//1024} KB", flush=True)
            time.sleep(1.3)
        s.close()

    (ROOT / "output" / "probe_datadome7.json").write_text(
        json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[p7] wynik: {json.dumps(wynik, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
