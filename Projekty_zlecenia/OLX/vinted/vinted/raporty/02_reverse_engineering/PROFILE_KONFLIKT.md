# Konflikt profili przeglądarki — rozstrzygnięcie

Data: 2026-09-01
Status: **ROZSTRZYGNIĘTE — STARE PROFILE USUNIĘTE**

---

## 1. PROBLEM

W projekcie istnieją **3 lokalizacje profili Camoufox** i **2 różne nazwy**, co wprowadzało zamęt i powodowało fałszywe wyniki testów (403 na build).

### Lokalizacje fizyczne (PRZED usunięciem):
| Lokalizacja | Opis | Status |
|---|---|---|
| `testy_camoufox/implementation/browser-profiles/profil_firefox/` | profil testowy (FF152) | ❌ USUNIĘTY (zablokowany, 403) |
| `testy_camoufox/implementation/browser-profiles/profil_firefox_135/` | profil produkcyjny (FF135) | ✅ **ZACHOWANY (kanoniczny)** |
| `testy_camoufox/tools/profil_firefox/` | **PUSTY** — artefakt, błędna ścieżka | ❌ USUNIĘTY (1 cookie) |

### Konflikt nazewniczy:
- `profil_firefox` — używany w większości skryptów testowych w `testy_camoufox/` (H1, H2, benchmark, capture)
- `profil_firefox_135` — używany w **działającym bocie** (`bot/scripts/test_build_bez_tokena.py`, `bot/src/vintedbot/`) i daje build=200

---

## 2. DOWODY

### Build=200 działa TYLKO na `profil_firefox_135`:
```
test_build_bez_tokena.py (profil_firefox_135):
  zakup 1: status_build=200, pickup=200, payment=400 (114 - brak karty)
  zakup 2 (skip-build): total 1031ms
```

### Build=403 na `profil_firefox` (nie odblokowany sliderem):
```
_checkout_h1_test.py / _checkout_h2_test.py (profil_firefox):
  build=403 (captcha DataDome) — nawet z tokenem Incognia i prefetch strony
```

### Cookies (oba profile w `browser-profiles/` mają ważne cookies):
```
== profil_firefox ==      access_token_web: 868B, datadome: 128B, refresh: 869B
== profil_firefox_135 ==  access_token_web: 868B, datadome: 128B, refresh: 869B
== tools/profil_firefox ==  BRAK WSZYSTKIEGO (pusty)
```

---

## 3. PRZYCZYNA RÓŻNICY

Nie sam profil decyduje o 200 vs 403, ale **czy profil przeszedł captcha slider DataDome**:
- `profil_firefox_135` — odblokowany sliderem (solver `slider_solver.py`), cookie DataDome "czyste"
- `profil_firefox` — NIE odblokowany, cookie DataDome oznacza urządzenie jako wymagające captcha

Po odblokowaniu DataDome "uczy się" urządzenia i następne build przechodzą nawet w czystym curl_cffi (bez przeglądarki, bez tokenu Incognia).

---

## 4. ROZSTRZYGNIĘCIE — SOURCE OF TRUTH

### ✅ Kanoniczny profil: `profil_firefox_135`

**Ścieżka kanoniczna (jedyna poprawna):**
```
vinted/testy_camoufox/implementation/browser-profiles/profil_firefox_135
```

### Uzasadnienie:
1. To jedyny profil, na którym **build=200** (potwierdzone 2026-09-01).
2. Jest używany przez produkcyjny kod bota (`bot/`).
3. Jest odblokowany sliderem — cookies DataDome czyste.

### ❌ Profile usunięte (2026-09-01):
- `profil_firefox` (browser-profiles) — zablokowany sliderem, dawał mylące 403 → **USUNIĘTY**
- `tools/profil_firefox` — pusty artefakt (1 cookie) → **USUNIĘTY**

### Po usunięciu: jedyny profil w projekcie to `profil_firefox_135`.

---

## 5. NAKAZ DLA AGENTÓW

1. **JEDYNY profil w projekcie:** `profil_firefox_135` w `implementation/browser-profiles/`. Stare `profil_firefox` są usunięte.
2. **NIGDY** nie twórz nowego profilu o nazwie `profil_firefox` — używaj wyłącznie `profil_firefox_135`.
3. Jeśli nowy profil — najpierw odblokuj sliderem (`slider_solver.rozwiaz_slider`), inaczej build=403.
4. Jeśli build=403 mimo `profil_firefox_135` — profil stracił odblokowanie (cookie wygasło), uruchom solver ponownie.

---

## 6. POPRAWIONE SKRYPTY (wskaż kanoniczny profil)

Skrypty poprawione na `profil_firefox_135` (2026-09-01):
- `_checkout_h1_test.py`, `_checkout_h2_test.py`, `_card_registrations_probe.py`, `_probe_catalog.py`, `playwright_speed_trials.py`
- `_checkout_403_diag.py`, `_checkout_probe.py`, `_checkout_diag.py`, `_login_probe.py`, `_camoufox_checkout_probe.py`
- `_capture_incognia_token.py`, `_capture_incognia_plaintext.py`, `checkout_hybrid.py`, `manual_slider_unlock.py`, `playwright_warm_path.py`, `cleanse.py`, `refresh_cookies_headless.py`, `verify_cookies_headless.py`, `render_bramka.py`, `_smoke_firefox.py`, `_check_login.py`
- `capture/capture_incognia.py`, `capture/capture_purchases_sequence.py`, `capture/capture_all_trace.py`
- `bot/bench_checkout.py`, `bot/bench_stabilnosc.py`, `bot/spike_faza3*.py`, `bot/diag_*.py`
- `implementation/hybrid/*.py`, `implementation/playwright/test_reset_playwright.py`, `implementation/curl-cffi/*.py`
- `_merge_datadome.py`, `_inspect_cookies.py`, `_diag_cat.py`, `_check_cookie_expiry.py`, `_check_cookies_profiles.py`, `check_profiles.py`, `_read_dd152.py`

Skrypty `testing/spikes/*` i `testing/probes/*` wskazują na usunięte ścieżki — to martwy kod (nieużywany).

---

## 7. AKTUALIZACJA captured_requests.json

Nie zmienia captured_requests (tam są tylko endpointy). Ta decyzja dotyczy konfiguracji profili.
