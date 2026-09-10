# Lekki Silnik Incognia (harvest + parametryzacja) — Plan Implementacji

> **Dla wykonawcy agentowego:** WYMAGANY SUB-SKILL: superpowers:executing-plans (inline) lub subagent-driven-development. Kroki używają checkbox (`- [ ]`).

**Cel:** Zbudować lekki silnik JS, który wysyła dokładnie to, co przeglądarka (Incognia snapshot + JWE token), z pełną kontrolą nad wartościami, bez klikania w selektory.

**Architektura:** curl_cffi robi sekwencję transportową (config → connectioncheck → cchd_config → consume → build). Node.js WebCrypto robi kryptografię (HKDF→AES-GCM + JWE RSA-OAEP). Sygnały snapshot są harvestowane raz z Camoufox FF152 i zahardkodowane; randomizacja tylko tam, gdzie serwer akceptuje zmienne (timing, trigger, seed). Wątek walidacji serwerowej: [HIPOTEZA] — rozstrzygnie Faza 0.

**Tech Stack:** Python + curl_cffi (transport, TLS FF152), Node.js WebCrypto (kryptografia), Camoufox (tylko harvest, raz).

---

## Sekwencja transportowa (do odtworzenia)

```
GET  https://api.vinted.pl/j3r4zw/v1/config            → sdkInstanceId, apiBaseUrl
POST https://conn-check.icg-in.com/connectioncheck     → klucz publiczny RSA (do JWE)
GET  https://metrics.vinted.lt/web/cchd_config          → JWE (NIE klucz)
GET  https://metrics.vinted.lt/web/pvt_cchd_config      → JWE
POST https://api.vinted.pl/j3r4zw/v1/consume (type=pls) → snapshot sygnałów AES-GCM
POST https://www.vinted.pl/api/v2/purchases/checkout/build
     headers: x-incognia-request-token (JWE RSA-OAEP 5 segmentów)
```

## Już gotowe w repo (NIE duplikować)

- `vinted/testy_camoufox/core/crypto/incognia_krypto_reference.js` — HKDF→AES-GCM (działa).
- `vinted/testy_camoufox/core/crypto/demo_node_crypto.js` — JWE RSA-OAEP + A128CBC-HS256 (działa).
- `vinted/testy_camoufox/core/crypto/incognia_transport_reference.js` — Dispatcher/encodeModel (`v/type/siid/ts/t/s`).
- `vinted/testy_camoufox/core/crypto/incognia_sdk_reference.js` — lifecycle SDK.
- `bot/src/vintedbot/config.py` — `tls_kwargs()` (FF152 JA3/Akamai/extra_fp).

---

## Faza 0: Rozstrzygnięcie [HIPOTEZA] walidacji serwerowej (WYMÓG AGENTS.md)

**Cel fazy:** potwierdzić/obalić, czy serwer akceptuje zreplayowany/zrandomizowany token. Bez tego Faza 4 to zgadywanie.

### Task 0.1: Harvest prawdziwego tokena JWE z sesji Camoufox

**Pliki:**
- Create: `vinted/testy_camoufox/tools/capture/harvest_incognia_token.py`

- [ ] **Krok 1: Napisz harvester (Camoufox, bez klikania w selektory)**

```python
"""Harvester x-incognia-request-token z realnej sesji Camoufox (bez builda)."""
import json, time
from pathlib import Path
from camoufox import Camoufox

PROFIL = Path("vinted/testy_camoufox/implementation/browser-profiles/profil_firefox_135").resolve()
OUT = Path("vinted/testy_camoufox/docs/logs/harvest_incognia_token.json")
captured = {}

def on_request(req):
    h = req.headers
    if "x-incognia-request-token" in h:
        captured["token"] = h["x-incognia-request-token"]
        captured["url"] = req.url
        captured["headers"] = dict(h)

def main():
    with Camoufox(persistent_context=True, headless=True, user_data_dir=str(PROFIL),
                  os="windows", fingerprint_preset=True, humanize=True) as ctx:
        page = ctx.new_page()
        page.on("request", on_request)
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(12)  # czas na initSdk + snapshot
        # Wymus dowolny fetch, ktory SDK podpina tokenem (read-only, nie build)
        page.evaluate("() => fetch('/api/v2/users/current', {headers:{'Accept':'application/json'}})")
        time.sleep(4)
    OUT.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
    print("token segmenty:", len(captured.get("token", "").split(".")))

if __name__ == "__main__":
    main()
```

- [ ] **Krok 2: Uruchom i zweryfikuj format tokenu**

Run: `python vinted/testy_camoufox/tools/capture/harvest_incognia_token.py`
Expected: `token segmenty: 5` (JWE RSA-OAEP) — potwierdza dowód z `playwright_build_headers_out.json`.

### Task 0.2: Replay test — curl_cffi build z przechwyconym tokenem

**Pliki:**
- Create: `vinted/testy_camoufox/tools/capture/replay_build_test.py`

- [ ] **Krok 1: Wyslij build przez curl_cffi z przechwyconym tokenem (read-only test)**

```python
"""Czy build przechodzi z przechwyconym tokenem JWE (rozstrzyga walidacje serwerowa)."""
import json
from pathlib import Path
from vintedbot.config import wczytaj_cookies, tls_kwargs
from curl_cffi import requests as cr

tok = json.loads(Path("vinted/testy_camoufox/docs/logs/harvest_incognia_token.json").read_text())["token"]
ck = wczytaj_cookies("bot/output/cookies_152_export.txt")
# ... (transakcja przez conversations, potem build z headerem x-incognia-request-token=tok)
# Wynik: 200 -> parametryzacja mozliwa; 403 -> serwer waliduje zywy SDK
```

- [ ] **Krok 2: Uruchom, zapisz wynik do captured_requests.json**

Expected: status 200 lub 403 → to rozstrzyga, czy Faza 4 ma sens.

---

## Faza 1: Warstwa kryptograficzna (adapter JWE dla bota)

**Cel:** wystawić w Node jedną funkcję `buildToken(sdkInstanceId, publicKeyPem, payload) → JWE`.

### Task 1.1: Wrapper Node na istniejący demo_node_crypto.js

**Pliki:**
- Modify: `bot/scripts/generate_incognia_token.js` (zastąpić tryb AES-GCM trybem JWE)
- Test: `bot/tests/test_incognia.py`

- [ ] **Krok 1: Dodaj tryb JWE do skryptu Node**

```javascript
// generate_incognia_token.js — nowy tryb: node generate_incognia_token.js --jwe <sdkId> <pubkeyPem> <payloadJson>
// Wewnatrz: wolaj jweEncrypt z demo_node_crypto.js (require lub skopiowana logika).
```

- [ ] **Krok 2: Test jednostkowy, że token ma 5 segmentow i header RSA-OAEP**

```python
# bot/tests/test_incognia.py
def test_token_jest_jwe_rsa_oaep():
    tok = wygeneruj_token_jwe("sdk-test", PUBKEY_FIXTURE, {})
    assert len(tok.split(".")) == 5
    assert b64url_json(tok.split(".")[0])["alg"] == "RSA-OAEP"
```

- [ ] **Krok 3: Uruchom test** — Run: `pytest bot/tests/test_incognia.py -v` → PASS.

---

## Faza 2: Transport Incognia przez curl_cffi (config → connectioncheck → cchd_config → consume)

### Task 2.1: Sekwencja transportowa w module bota

**Pliki:**
- Create: `bot/src/vintedbot/incognia_transport.py`
- Test: `bot/tests/test_incognia_transport.py`

- [ ] **Krok 1: Napisz funkcje sekwencji**

```python
def pobierz_config(cookies): ...      # GET /j3r4zw/v1/config -> sdkInstanceId, apiBaseUrl
def connectioncheck(cookies): ...     # POST conn-check -> public_key RSA
def pobierz_cchd_config(): ...        # GET cchd_config -> JWE (log, nie klucz)
def wyslij_snapshot(cookies, sdk_id, payload): ...  # POST consume type=pls
```

- [ ] **Krok 2: Test z mockiem HTTP (zgodnie z zasada: tylko siec mockowalna)**

```python
def test_sekwencja_parsuje_sdkid(mocker): ...
```

- [ ] **Krok 3: Uruchom testy** — PASS.

### Task 2.2: E2E sekwencji (realny HTTP, bez builda)

- [ ] **Krok 1:** `CliRunner().invoke(cli, ["incognia-warmup"])` → zapisz `sdkInstanceId`, status `consume=200`, surowy klucz RSA do `bot/output/incognia_session.json`.

---

## Faza 3: Harvest i spójność fingerprintu FF152

### Task 3.1: Zahardkoduj sygnały FF152 zamiast mocków Chrome

**Pliki:**
- Create: `bot/src/vintedbot/incognia_signals_ff152.py` (wartosci zgodne z Camoufox FF152)

- [ ] **Krok 1:** Podmien mocki: WebGL `ANGLE (AMD, Radeon R9 200 ...)` (zgodnie z `webgl_config`), UA `Firefox/152.0`, screen 1920x1080, canvas z deterministycznego seeda (NIE `Math.random()`).
- [ ] **Krok 2:** Test spójności: sygnały == oczekiwane wartości FF152. PASS.

### Task 3.2: Randomizacja tylko zmiennych

- [ ] **Krok 1:** Randomizuj `totalTimingMs`, `trigger`, seed — pola, które serwer uznaje za zmienne. NIE ruszaj `webgl_renderer`/`canvas_hash` (spójność tożsamości).

---

## Faza 4: Wpięcie do checkout (finalny krok, TYLKO po Fazie 0)

### Task 4.1: checkout.py używa JWE tokena

**Pliki:**
- Modify: `bot/src/vintedbot/checkout.py` (naglowek `x-incognia-request-token` = JWE)
- Modify: `bot/src/vintedbot/detection.py` (wywołanie sekwencji przed buildem)

- [ ] **Krok 1:** `zrealizuj_zakup` przed buildem: `sdk_id = pobierz_config(); pub = connectioncheck(); wyslij_snapshot(); token = wygeneruj_token_jwe(sdk_id, pub, {})` → build z tym tokenem.
- [ ] **Krok 2:** Test E2E (prawdziwy kod CLI, mock tylko sieci). PASS.

---

## Ograniczenia (twardy mur, do udokumentowania)

- **Behavioral `isTrusted=true`**: NIE generujemy. Randomizacja pokrywa tylko `consume`, nie kliknięcie. To jest świadome ograniczenie lekkiego silnika.
- **Walidacja serwerowa**: rozstrzyga Faza 0. Jeśli 403 → plan kończy się, wracamy do dokumentacji.

