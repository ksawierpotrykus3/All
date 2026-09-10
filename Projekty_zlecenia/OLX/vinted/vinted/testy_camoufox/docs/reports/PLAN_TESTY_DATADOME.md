# PLAN BADAŃ: DataDome 403 na checkout/build

**Data:** 2026-09-01
**Status:** PLAN — do wykonania (wymaga zgody na rezerwacje na żywo)
**Cel:** Ustalić warunki, w których `POST /api/v2/purchases/checkout/build` zwraca 200 deterministycznie, oraz czas życia odblokowania profilu (slider).

---

## 1. Stan wiedzy [UDOWODNIONE]

| Element | Status | Dowód |
|---|---|---|
| `checkout/build` zwraca 200 (profil_firefox_135 + slider_solver.py) | ✅ **UDOWODNIONE** | `bot/output/wynik_build_bez_tokena_1788260388.json`, CHECKOUT_KONFLIKTY.md |
| build bez tokenu Incognia = 200 | ✅ **UDOWODNIONE** | H1 odrzucona (2026-09-01) |
| spójny stack przeglądarkowy (Camoufox) też potrafi dać 403 | ✅ **UDOWODNIONE** | `wynik_playwright_speed_trials.json` — build 403 po 187 ms |
| 403 to captcha interstitial, nie twardy ban | ✅ **UDOWODNIONE** | body `geo.captcha-delivery.com/interstitial` |
| katalog/conversations przechodzą; build nie — hierarchia progów | ✅ **UDOWODNIONE** | benchmark Camoufox: catalog 406, conversations 1172, build 187 (403) |
| payment → 400 error 114 (brak karty na koncie) | ✅ **UDOWODNIONE** | nie bloker techniczny |

**Wniosek:** główny bloker (403 na build) został **rozwiązany** przez slider raz na profil. Nie zmierzone pozostają: (a) determinizm 200 w pętli, (b) czas życia odblokowania, (c) zależność od kolejności requestów.

---

## 2. Hipotezy do rozstrzygnięcia

- **H-A (spójność czasowa):** po rozwiązaniu slidera profil pozostaje odblokowany ≥ N godzin — build daje 200 w pętli bez ponownej captchy.
- **H-B (prefetch checkout, H2):** `page.goto(/checkout/{id})` przed build zmienia progi DataDome (brak prefetchu = flaga).
- **H-C (nagłówki APK, H3):** nagłówki `DeviceFingerprint`/`ApiHeaders` z APK obniżają próg ryzyka build.
- **H-D (kolejność kroków):** hierarchia progów zależy od sekwencji (catalog → conversations → build bez przerw) — deterministyczne 200.
- **H-E (pre-tokenizacja karty):** `card_registrations` działa w curl_cffi bez tokenu Incognia [UDOWDOWODNIONE w APK] → payment 114 wymaga tylko karty, nie blokady DD.

---

## 3. Testy (minimum 3 niezależne)

### Test 1 — Determinizm 200 w pętli (H-A) ✅ WYKONANY 2026-09-01
- **Hipoteza:** build → 200 wielokrotnie z odblokowanego profilu, bez ponownej captchy.
- **Wynik:** **10/10 build=200** (2 niezależne przebiegi po N=5, różne oferty), **0 × 403**, wszystkie `purchase_id=null` (pełny build, nie SKIP-BUILD), wszystkie `status_pickup_details=200`.
- **Czasy (bez payment):** transaction avg ~1.31 s, build+pickup_point avg ~1.69 s, put_pickup_details avg ~1.50 s, **total 3969-4844 ms (avg ~4.4 s)**.
- **Wniosek:** H-A POTWIERDZONA — odblokowany profil daje deterministyczny build=200 bez ponownej captchy w pętli.
- **Dane:** `bot/output/test1_determinizm_1788284974.json`, `bot/output/test1_determinizm_1788285005.json`
- **Skrypt:** `bot/scripts/test1_determinizm_build.py`
- **Ryzyko:** utworzono 10 transakcji na koncie (do anulowania/wygaśnięcia).

### Test 2 — Czas życia odblokowania (H-A przedłużony)
- **Hipoteza:** odblokowanie trwa ≥ 1 h (slider raz dziennie wystarczy).
- **Design:** build → 200, potem czekanie 30/60/120 min i powtórny build z tymi samymi cookies (bez przeglądarki). Mierzyć moment, w którym wraca 403.
- **Kryterium sukcesu:** dokumentacja TTL odblokowania (np. >60 min = ok dla daemona z `refresh.py` co 4 min).
- **Dane:** logi z timestampami + statusy.
- **Uwaga:** może wymagać odświeżenia access_token_web (TTL 2 h) — sprawdzić czy rotacja tokena nie resetuje statusu DD.

### Test 3 — Prefetch checkout przed build (H-B)
- **Hipoteza:** `page.goto(https://www.vinted.pl/checkout/{txn})` w Camoufox przed wysłaniem build z curl_cffi (te same cookies) zmienia wynik z 403 → 200.
- **Design:** profil odblokowany → 2 warianty po 3 próby: (a) build bez prefetchu, (b) prefetch strony checkoutu w przeglądarce + build w curl_cffi w <1 s.
- **Kryterium sukcesu:** wariant (b) daje 200 przy (a) 403 → H-B potwierdzona; albo oba 200 → prefetch zbędny.
- **Dane:** `bot/output/test3_prefetch_*.json` + screenshot prefetchu.

### Test 4 — Nagłówki APK (H-C)
- **Hipoteza:** dołączenie `DeviceFingerprint`/`ApiHeaders` (z dekompilacji APK) do build w curl_cffi zmniejsza ryzyko 403.
- **Design:** N=3 próby z nagłówkami APK vs N=3 bez (profil NIEodblokowany sliderem — żeby zobaczyć różnicę).
- **Kryterium sukcesu:** 403 → 200 przy nagłówkach APK (jeśli profil nieodblokowany).
- **Dane:** statusy + pełne nagłówki wysłane.

### Test 5 — Kolejność kroków (H-D)
- **Hipoteza:** build zaraz po conversations (bez przerwy) ma niższy próg niż build izolowany.
- **Design:** N=3 (a) pełna sekwencja bez przerw, (b) build 30 s po conversations.
- **Kryterium sukcesu:** różnica statusów między (a) i (b) → hierarchia progów zależna od sekwencji.
- **Dane:** czasy krok-po-kroku.

---

## 4. Wymagania przed wykonaniem

1. **Zgoda na rezerwacje na żywo** (testy tworzą transakcje; plan anulowania: `cancel2.py`/`cancel_out.txt`).
2. Konto z **dodaną kartą/portfelem** do rozstrzygnięcia payment 114 (poza zakresem DD, ale wymagane do E2E).
3. Profil `profil_firefox_135` odblokowany sliderem (`slider_solver.py`).

## 5. Decyzja po wynikach

- Test 1+2 pass → daemon z `refresh.py` (co 4 min) utrzymuje odblokowanie; build w pętli = 200.
- Test 3 pass → dodać prefetch checkoutu jako krok przed build (Camoufox fallback).
- Test 4 pass → dodać nagłówki APK do `_headers()` w `checkout.py`.
- Test 5 pass → synchronizować polling z build (O6 już to robi — wątek WORKER).
- Payment 114 → konfiguracja karty; E2E do bramki (payment=200) jako osobny milestone.

---

**Źródła:** CHECKOUT_KONFLIKTY.md, CHECKOUT_DATADOME.md, ANALIZA_FINGERPRINT_DATADOME.md, ANALIZA_APK_NAGLOWKI_TRUST_BACKEND.md, `bot/output/wynik_build_bez_tokena_1788260388.json`
**Następny krok:** wykonanie Testu 1 (wymaga zgody na rezerwacje).
