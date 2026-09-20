# 03 — Plan odzyskania ofert z Useme (nie ma ich w magazynie)

**Cel:** ustalić, które zlecenia istnieją na Useme, a brak ich w `magazyn/`. Jednorazowy eksperyment Playwright, **bez zmiany kodu produkcyjnego**; nowy skrypt w `trae/`.

**Dlaczego pierwszy:** brak lokalnej historii „moje oferty z Useme" — nie da się zweryfikować fałszywego WYSLANO bez scrapu panelu.

## 1. Trzy źródła prawdy na Useme
| Źródło | URL (do potwierdzenia) | Co daje |
|---|---|---|
| Panel złożonych ofert | `/pl/dashboard/` lub `/pl/my-offers/` | realnie wysłane oferty |
| Listy kategorii | `/pl/jobs/category/programowanie-i-it,35/?page=N`, `...,serwisy-internetowe,34` | wszystkie zlecenia |
| Panel zleceń | `/pl/my-jobs/` | statusy |

## 2. Bezpieczeństwo
1. Tylko odczyt — żadnego „Wyślij".
2. `HEADLESS=False`.
3. Te same cookies (`tech/cookies.json`), reuse `browser_driver` (stealth).
4. Nie modyfikuj `magazyn/`, `marker.json`, `data/pipelines/`. Wyniki → `trae/odzyskane/`.
5. Sprawdź `check_logged_in` przed scrapem; brak sesji → STOP.

## 3. Kroki
1. Spis lokalny (baseline): 36 ID + statusy.
2. Scrap panelu ofert → `U_offers`. Test A1: `U_offers \ L_WYSLANO`.
3. Scrap list kategorii → `U_jobs`. Odzyskane: `U_jobs \ L`.
4. Cross-check: A. Brakujące w magazynie · B. Fałszywie wysłane · C. Wysłane bez dowodu (11) · D. Utknięte (12).
5. Raport `trae/odzyskane/raport_odzyskania.{json,md}`.

## 4. Szkielet (PROPOZYCJA — nie uruchamiany)
```python
# trae/recover_offers.py  (DO ZATWIERDZENIA)
import json, glob, pathlib
from browser_driver import BrowserDriver
from storage import MAGAZYN_DIR

OUT = pathlib.Path("trae/odzyskane"); OUT.mkdir(parents=True, exist_ok=True)

def local_ids():
    ids = {}
    for p in glob.glob(str(MAGAZYN_DIR / "*" / "*.json")):
        d = json.loads(pathlib.Path(p).read_text("utf-8"))
        ids[d["id"]] = d.get("status")
    return ids

def main():
    L = local_ids()
    drv = BrowserDriver(); drv.start()
    if not drv.check_logged_in():
        print("BRAK SESJI — STOP"); return
    # TODO: wykryć selektory panelu i kategorii empirycznie
    # 1) panel ofert -> U_offers  2) listy kategorii -> U_jobs
    # 3) różnice + raport
    ...
```

## 5. Oczekiwane wnioski
| Scenariusz | Wniosek |
|---|---|
| U_offers ≈ 22 | formularz działa, problem w wolumenie |
| U_offers << 22 | fałszywy WYSLANO |
| U_jobs >> 36 | bot gubi oferty na wejściu |
| 144256 w U_jobs | cichy stop potwierdzony |

## 6. Kolejność (po zatwierdzeniu)
1. Potwierdzić URL-e panelu ręcznie.
2. Dopiąć selektory.
3. Uruchomić HEADLESS=False, tylko odczyt.
4. Raport → zawęzić hipotezy do realnej przyczyny.

> Nie wykonujemy automatycznie — wymaga zgody (żywa sesja, realne konto).