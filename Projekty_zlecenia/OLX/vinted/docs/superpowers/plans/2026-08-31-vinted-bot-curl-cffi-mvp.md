# Vinted Bot — przebudowa MVP na czysty curl_cffi (firefox135) — Plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przebudować `bot/` tak, aby cała ścieżka zakupowa (detekcja → transakcja → build → payment) działała w 100% przez `curl_cffi` (impersonacja `firefox135`), usuwając Camoufox i przestarzałe endpointy.

**Architecture:** Moduły o jednej odpowiedzialności: `config` (stałe/ścieżki), `models` (typy), `detection` (monitoring + endpoint transakcji), `incognia` (token Node.js), `checkout` (sekwencja curl_cffi), `measurement` (pomiar), `cli` (orkiestracja). Camoufox usunięty całkowicie.

**Tech Stack:** Python 3.11, `click`, `curl_cffi`, `pydantic`, `pytest`. Node.js (tylko do tokenu Incognia).

**Referencja implementacyjna:** `vinted/testy_camoufox/.bin/benchmark/flow_optimized.py` (działająca sekwencja curl_cffi firefox135) oraz `vinted/testy_camoufox/core/crypto/generate_incognia_token.js` (token Incognia).

---

## Ważne fakty domenowe (nie zmieniać)

- Impersonacja: `"firefox135"` (nie `chrome`).
- Endpoint transakcji: `POST https://api.vinted.pl/messaging/main/inquiries` z body
  `{"item_ids": [str(item_id)], "receiver_id": str(seller_id)}` → odpowiedź zawiera `transaction_id`.
- Metoda płatności: karta = `pay_in_method_id: "1"`.
- Token Incognia: `GET https://api.vinted.pl/j3r4zw/v1/config` → `sdk_instance_id`,
  potem `node generate_incognia_token.js <sdk_instance_id>` → token (stdout).
- `checksum` w odpowiedziach ma postać pojedynczego stringa `"a|b"`; łapiemy rekurencyjnie.

---

## Struktura plików

```
bot/
├── pyproject.toml                      # usunąć camoufox
├── scripts/
│   └── generate_incognia_token.js      # skopiowany z testy_camoufox/core/crypto/
├── src/vintedbot/
│   ├── config.py                       # NOWY: stałe + wczytaj_cookies (uniwersalny)
│   ├── incognia.py                     # NOWY: token Incognia
│   ├── models.py                       # dodać seller_id, KonfiguracjaKonta, WynikCheckoutu
│   ├── detection.py                    # firefox135 + utworz_transakcje
│   ├── checkout.py                     # przepisać na curl_cffi (usunąć Camoufox)
│   ├── measurement.py                  # dodać StepTimings, usunąć CheckoutTimer
│   └── cli.py                          # autocop bez engine, --payment
└── tests/
    ├── conftest.py                     # rozszerzyć o mock POST/PUT
    ├── test_models.py
    ├── test_detection.py
    ├── test_checkout.py                # przepisać
    ├── test_incognia.py                # NOWY
    └── test_cli_e2e.py
```

---

### Task 1: `config.py` — stałe i ładowanie cookies

**Files:**
- Create: `bot/src/vintedbot/config.py`
- Create: `bot/scripts/generate_incognia_token.js` (skopiowany)
- Test: `bot/tests/test_config.py`

- [ ] **Step 1: Skopiuj skrypt tokenu Incognia**

Skopiuj zawartość `vinted/testy_camoufox/core/crypto/generate_incognia_token.js` do
`bot/scripts/generate_incognia_token.js` (Create, pełna kopia — nie importuj z testy_camoufox).

- [ ] **Step 2: Napisz test konfiguracji**

```python
# bot/tests/test_config.py
from vintedbot import config


def test_stale_domyslne():
    assert config.IMPERSONATE == "firefox135"
    assert config.PAY_IN_METHOD == "1"


def test_wczytaj_cookies_json(tmp_path):
    import json
    p = tmp_path / "c.json"
    p.write_text(json.dumps([
        {"name": "a", "value": "1"},
        {"name": "b", "value": "2"},
    ]), encoding="utf-8")
    c = config.wczytaj_cookies(p)
    assert c == {"a": "1", "b": "2"}


def test_wczytaj_cookies_netscape(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text(
        "# Netscape HTTP Cookie File\n\n"
        ".vinted.pl\tTRUE\t/\tTRUE\t0\taccess_token_web\txyz\n",
        encoding="utf-8",
    )
    c = config.wczytaj_cookies(p)
    assert c["access_token_web"] == "xyz"


def test_wczytaj_cookies_json_pomija_bez_name(tmp_path):
    import json
    p = tmp_path / "c.json"
    p.write_text(json.dumps([{"value": "no-name"}, {"name": "a", "value": "1"}]), encoding="utf-8")
    assert config.wczytaj_cookies(p) == {"a": "1"}
```

- [ ] **Step 3: Uruchom testy — FAIL (brak modułu)**

Run: `cd bot && pytest tests/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'vintedbot.config'`

- [ ] **Step 4: Zaimplementuj `config.py`**

```python
"""Stałe konfiguracyjne i ładowanie cookies (JSON lub Netscape)."""
import json
from pathlib import Path

IMPERSONATE = "firefox135"
PAY_IN_METHOD = "1"  # karta

CSRF_DEFAULT = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON_DEFAULT = "98c6af5a-87da-45f2-9be5-24cf9345b003"

INQUIRIES_URL = "https://api.vinted.pl/messaging/main/inquiries"
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
CHECKOUT_URL = "https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
PAYMENT_URL = "https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
PICKUP_URL = ("https://api.vinted.pl/shipping-estimation/external/shipping_orders/"
              "{shipping_order_id}/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
SDK_CONFIG_URL = "https://api.vinted.pl/j3r4zw/v1/config"

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
NODE_TOKEN_SCRIPT = SCRIPTS_DIR / "generate_incognia_token.js"


def wczytaj_cookies(path: str | Path) -> dict[str, str]:
    """Wczytuje cookies z pliku JSON (lista obiektów) lub Netscape."""
    data = Path(path).read_text(encoding="utf-8").lstrip()
    if data.startswith("["):
        return {c["name"]: c["value"] for c in json.loads(data) if c.get("name")}
    cookies: dict[str, str] = {}
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies
```

- [ ] **Step 5: Uruchom testy — PASS**

Run: `cd bot && pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add bot/src/vintedbot/config.py bot/scripts/generate_incognia_token.js bot/tests/test_config.py
git commit -m "feat: config (firefox135) + universal cookie loader + node token script"
```

---

### Task 2: `models.py` — seller_id, KonfiguracjaKonta, WynikCheckoutu

**Files:**
- Modify: `bot/src/vintedbot/models.py`
- Test: `bot/tests/test_models.py`

- [ ] **Step 1: Napisz testy**

```python
# bot/tests/test_models.py — dopisz do istniejącego pliku
from vintedbot.models import Filtry, Oferta, KonfiguracjaKonta, WynikCheckoutu


def test_oferta_parsuje_seller_id():
    raw = {"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"},
           "user": {"id": 99}}
    o = Oferta.model_validate(raw)
    assert o.seller_id == 99


def test_oferta_bez_user():
    raw = {"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}}
    o = Oferta.model_validate(raw)
    assert o.seller_id is None


def test_konfiguracja_konta():
    k = KonfiguracjaKonta(cookies={"a": "1"})
    assert k.csrf == "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
    assert k.cookies == {"a": "1"}


def test_wynik_checkoutu_timings():
    w = WynikCheckoutu(purchase_id="p1")
    w.timings["build"] = 100.0
    assert w.timings["build"] == 100.0
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && pytest tests/test_models.py -v`
Expected: FAIL (brak `seller_id`, `KonfiguracjaKonta`, `WynikCheckoutu`)

- [ ] **Step 3: Zaimplementuj**

```python
from pydantic import BaseModel, Field

from .config import CSRF_DEFAULT, ANON_DEFAULT, IMPERSONATE


class Filtry(BaseModel):
    # ... bez zmian (istniejąca treść) ...


class Oferta(BaseModel):
    id: int
    title: str
    price: dict
    brand_title: str | None = None
    seller_id: int | None = None

    @property
    def cena(self) -> float:
        return float(self.price.get("amount", 0))


class KonfiguracjaKonta(BaseModel):
    csrf: str = CSRF_DEFAULT
    anon_id: str = ANON_DEFAULT
    impersonate: str = IMPERSONATE
    cookies: dict[str, str] = Field(default_factory=dict)


class WynikCheckoutu(BaseModel):
    purchase_id: str | None = None
    checkout_id: str | None = None
    transaction_id: str | None = None
    status_build: int | None = None
    status_payment_method: int | None = None
    status_pickup_details: int | None = None
    status_payment: int | None = None
    payment_status: str | None = None
    redirect_url: str | None = None
    error_code: int | None = None
    timings: dict[str, float] = Field(default_factory=dict)
```

**Uwaga:** dopasuj dokładnie istniejącą treść `Filtry` i `Oferta` — nie zmieniaj `Filtry`; do `Oferta` dodaj tylko `seller_id` i zachowaj `model_validator` z istniejącego pliku (jeśli jest).

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && pytest tests/test_models.py -v`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/models.py bot/tests/test_models.py
git commit -m "feat: Oferta.seller_id + KonfiguracjaKonta + WynikCheckoutu"
```

---

### Task 3: `incognia.py` — token Incognia przez Node.js

**Files:**
- Create: `bot/src/vintedbot/incognia.py`
- Test: `bot/tests/test_incognia.py`

- [ ] **Step 1: Napisz testy**

```python
# bot/tests/test_incognia.py
import subprocess

from vintedbot import incognia


def test_wygeneruj_token_wolaj_node(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = "TOKEN\n"
            stderr = ""
        return R()

    monkeypatch.setattr(incognia.subprocess, "run", fake_run)
    tok = incognia.wygeneruj_token("sid-1")
    assert tok == "TOKEN"
    assert calls[0][0] == "node"
    assert calls[0][2] == "sid-1"


def test_wygeneruj_token_blad_node(monkeypatch):
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
            stderr = "boom"
        return R()

    monkeypatch.setattr(incognia.subprocess, "run", fake_run)
    try:
        incognia.wygeneruj_token("sid-1")
        assert False, "powinno rzucić RuntimeError"
    except RuntimeError as e:
        assert "boom" in str(e)
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && pytest tests/test_incognia.py -v`
Expected: FAIL (brak `vintedbot.incognia`)

- [ ] **Step 3: Zaimplementuj**

```python
"""Generowanie tokenu Incognia przez zewnętrzny proces Node.js (AES-GCM)."""
import subprocess

from .config import NODE_TOKEN_SCRIPT


def wygeneruj_token(sdk_instance_id: str) -> str:
    res = subprocess.run(
        ["node", str(NODE_TOKEN_SCRIPT), sdk_instance_id],
        capture_output=True, text=True, timeout=30,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Node.js error: {res.stderr}")
    return res.stdout.strip()
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && pytest tests/test_incognia.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/incognia.py bot/tests/test_incognia.py
git commit -m "feat: incognia token via Node.js subprocess"
```

---

### Task 4: `detection.py` — firefox135 + `utworz_transakcje`

**Files:**
- Modify: `bot/src/vintedbot/detection.py`
- Test: `bot/tests/test_detection.py`

- [ ] **Step 1: Napisz testy**

```python
# bot/tests/test_detection.py — dopisz
import json

from vintedbot.detection import utworz_transakcje
from vintedbot.models import KonfiguracjaKonta


def test_utworz_transakcje_buduje_body(monkeypatch):
    captured = {}

    class _Resp:
        status_code = 200
        content = json.dumps({"transaction_id": "T123"}).encode()

    def fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw["json"]
        return _Resp()

    monkeypatch.setattr("vintedbot.detection.creq.post", fake_post)
    txn = utworz_transakcje(item_id=7, seller_id=9, konto=KonfiguracjaKonta())
    assert txn == "T123"
    assert captured["url"] == "https://api.vinted.pl/messaging/main/inquiries"
    assert captured["json"] == {"item_ids": ["7"], "receiver_id": "9"}
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && pytest tests/test_detection.py -v`
Expected: FAIL (brak `utworz_transakcje`)

- [ ] **Step 3: Zmień import i impersonację w `detection.py`**

Na górze pliku dodaj import config i modele:

```python
from .config import IMPERSONATE, INQUIRIES_URL
from .models import Filtry, Oferta, KonfiguracjaKonta
```

Zamień wszystkie wystąpienia `impersonate="chrome"` na `impersonate=IMPERSONATE` (3 miejsca:
`pobierz_oferty`, `odswiez_token`, `monitoruj` nie ma — sprawdź `odswiez_token` i `pobierz_oferty`).

- [ ] **Step 4: Dodaj `utworz_transakcje`**

```python
def utworz_transakcje(item_id: int, seller_id: int, konto: KonfiguracjaKonta) -> str:
    """Nowy endpoint /messaging/main/inquiries -> transaction_id (unika 429)."""
    r = creq.post(
        INQUIRIES_URL,
        json={"item_ids": [str(item_id)], "receiver_id": str(seller_id)},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-CSRF-Token": konto.csrf,
            "x-anon-id": konto.anon_id,
            "Origin": "https://www.vinted.pl",
            "Referer": "https://www.vinted.pl/",
        },
        cookies=konto.cookies,
        impersonate=IMPERSONATE,
        timeout=30,
    )
    r.raise_for_status()
    return json.loads(r.content).get("transaction_id")
```

- [ ] **Step 5: Usuń `wczytaj_cookies` z detection (przeniesione do config)**

Wyrzuć funkcję `wczytaj_cookies` z `detection.py`; zaimportuj z config tam, gdzie potrzebna
(w `cli.py`). Zachowaj `odswiez_token`, `utrzymuj_sesje`, `pobierz_oferty`, `monitoruj`,
`_nastepny_interwal`, `_sesja_aktywna`, `_wymagany_csrf_token`.

- [ ] **Step 6: Uruchom — PASS**

Run: `cd bot && pytest tests/test_detection.py -v`
Expected: wszystkie przechodzą (istniejące + nowy)

- [ ] **Step 7: Commit**

```bash
git add bot/src/vintedbot/detection.py bot/tests/test_detection.py
git commit -m "feat: firefox135 impersonation + nowy endpoint transakcji (inquiries)"
```

---

### Task 5: `checkout.py` — przepisać na sekwencję curl_cffi

**Files:**
- Overwrite: `bot/src/vintedbot/checkout.py`
- Test: `bot/tests/test_checkout.py` (przepisać)

- [ ] **Step 1: Napisz nowe testy (mock HTTP per URL)**

```python
# bot/tests/test_checkout.py — ZASTĄP całą treść
import json

from vintedbot.checkout import zrealizuj_zakup, _find_checksum
from vintedbot.models import KonfiguracjaKonta


def test_find_checksum_rekurencyjnie():
    obj = {"checkout": {"checksum": "a|b", "nested": {"checksum": "c|d"}}}
    assert _find_checksum(obj) == ["a|b", "c|d"]


def _resp(body, status=200):
    class R:
        status_code = status
        content = json.dumps(body).encode()
        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")
    return R()


def test_zrealizuj_zakup_bez_payment(monkeypatch):
    calls = []
    build_body = {
        "checkout": {
            "id": "CK1",
            "checksum": "a|b",
            "components": {
                "shipping_pickup_details": {"pickup_details": {"selected_rate_uuid": "RATE"}},
                "shipping_address": {"shipping_order_id": 123, "address": {"coordinates": {"latitude": 1.0, "longitude": 2.0}}},
            },
        }
    }

    def fake(method, url, **kw):
        calls.append((method, url))
        if "inquiries" in url:
            return _resp({"transaction_id": "T1"})
        if "checkout/build" in url:
            return _resp(build_body)
        if url.endswith("/checkout") and method == "PUT":
            return _resp({"checkout": {"checksum": "x|y"}})
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if "checkout/payment" in url:
            return _resp({"payment": {"status": "pending"}})
        return _resp({})

    for m, fn in [("get", "creq.get"), ("post", "creq.post"), ("put", "creq.put")]:
        monkeypatch.setattr("vintedbot.checkout.creq." + m, lambda *a, _m=m, **kw: fake(_m, *a, **kw))

    k = KonfiguracjaKonta(cookies={"a": "1"})
    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=k, proba_payment=False)

    assert w.transaction_id == "T1"
    assert w.checkout_id == "CK1"
    assert w.purchase_id is None  # build nie ma purchase_id w tym teście
    # payment NIE wywołane
    assert not any("payment" in u and "payment" != u.split("/")[-1] for _, u in calls)


def test_zrealizuj_zakup_z_payment(monkeypatch):
    calls = []
    build_body = {
        "checkout": {
            "id": "CK1", "checksum": "a|b",
            "components": {
                "shipping_pickup_details": {"pickup_details": {"selected_rate_uuid": "RATE"}},
                "shipping_address": {"shipping_order_id": 123, "address": {"coordinates": {"latitude": 1.0, "longitude": 2.0}}},
            },
        }
    }
    def fake(method, url, **kw):
        calls.append((method, url))
        if "inquiries" in url:
            return _resp({"transaction_id": "T1"})
        if "checkout/build" in url:
            return _resp(build_body)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout/payment"):
            return _resp({"payment": {"status": "pending"}, "action": {"parameters": {"url": "https://adyen/redir"}}})
        if url.endswith("/checkout"):
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    monkeypatch.setattr("vintedbot.checkout.creq.get", lambda *a, **kw: fake("get", *a, **kw))
    monkeypatch.setattr("vintedbot.checkout.creq.post", lambda *a, **kw: fake("post", *a, **kw))
    monkeypatch.setattr("vintedbot.checkout.creq.put", lambda *a, **kw: fake("put", *a, **kw))

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    assert w.status_payment == 200
    assert w.payment_status == "pending"
    assert w.redirect_url == "https://adyen/redir"
    assert any("/checkout/payment" in u for _, u in calls)
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && pytest tests/test_checkout.py -v`
Expected: FAIL (brak `zrealizuj_zakup`, `_find_checksum`)

- [ ] **Step 3: Napisz `checkout.py`**

```python
"""Sekwencja zakupowa w 100% przez curl_cffi (firefox135). Bez Camoufox."""
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

from curl_cffi import requests as creq

from .config import INQUIRIES_URL, BUILD_URL, CHECKOUT_URL, PAYMENT_URL, PICKUP_URL
from .detection import utworz_transakcje
from .models import KonfiguracjaKonta, WynikCheckoutu
from .incognia import wygeneruj_token


def _headers(konto: KonfiguracjaKonta, extra=None) -> dict:
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": konto.csrf,
        "x-anon-id": konto.anon_id,
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    if extra:
        h.update(extra)
    return h


def _find_checksum(obj):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(_find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(_find_checksum(v))
    return hits


def _sdk_instance_id() -> str:
    r = creq.get("https://api.vinted.pl/j3r4zw/v1/config", timeout=30)
    return (r.json() or {}).get("sdk_instance_id")


def _build(txn_id: int, token: str, konto: KonfiguracjaKonta):
    r = creq.post(
        BUILD_URL,
        json={"purchase_items": [{"id": int(txn_id), "type": "transaction"}]},
        headers=_headers(konto, {"x-incognia-request-token": token}),
        cookies=konto.cookies,
        impersonate=konto.impersonate,
        timeout=30,
    )
    return r


def _put_payment_method(checkout_id: str, konto: KonfiguracjaKonta, pay_in_method: str):
    url = CHECKOUT_URL.format(checkout_id=checkout_id)
    r = creq.put(url, json={"components": {
        "additional_service": {},
        "payment_method": {"card_id": None, "pay_in_method_id": pay_in_method},
        "shipping_address": {},
        "shipping_pickup_options": {"pickup_type": 1},
        "shipping_pickup_details": {},
    }}, headers=_headers(konto), cookies=konto.cookies,
        impersonate=konto.impersonate, timeout=30)
    return r


def _get_pickup_point(shipping_order_id, lat, lon, konto: KonfiguracjaKonta):
    url = PICKUP_URL.format(shipping_order_id=shipping_order_id, lat=lat, lon=lon)
    r = creq.get(url, headers=_headers(konto), cookies=konto.cookies,
                 impersonate=konto.impersonate, timeout=30)
    pp = r.json()
    spoints = (pp or {}).get("shipping_points") or []
    sug = (pp or {}).get("suggested_shipping_point_code")
    for cand in spoints:
        sp = cand.get("point", {})
        if sug and sp.get("code") == sug:
            return sp
    return spoints[0].get("point", {}) if spoints else {}


def _put_pickup_details(checkout_id: str, details: dict, konto: KonfiguracjaKonta):
    url = CHECKOUT_URL.format(checkout_id=checkout_id)
    r = creq.put(url, json={"components": {
        "additional_service": {},
        "payment_method": {},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": details,
    }}, headers=_headers(konto), cookies=konto.cookies,
        impersonate=konto.impersonate, timeout=30)
    return r


def _payment(checkout_id: str, checksum: str, konto: KonfiguracjaKonta):
    url = PAYMENT_URL.format(checkout_id=checkout_id)
    r = creq.post(url, json={
        "checksum": checksum,
        "payment_options": {"browser_info": {
            "language": "pl", "color_depth": 24, "java_enabled": False,
            "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
        }},
    }, headers=_headers(konto), cookies=konto.cookies,
        impersonate=konto.impersonate, timeout=30)
    return r


def zrealizuj_zakup(item_id: int, seller_id: int, konto: KonfiguracjaKonta,
                    *, proba_payment: bool = False, pay_in_method: str = "1") -> WynikCheckoutu:
    w = WynikCheckoutu()

    t0 = time.monotonic()
    token = wygeneruj_token(_sdk_instance_id())
    w.transaction_id = utworz_transakcje(item_id, seller_id, konto)
    w.timings["token+inquiries"] = round((time.monotonic() - t0) * 1000)

    t0 = time.monotonic()
    r_build = _build(int(w.transaction_id), token, konto)
    w.timings["build"] = round((time.monotonic() - t0) * 1000)
    w.status_build = r_build.status_code
    if r_build.status_code != 200:
        w.error_code = r_build.status_code
        return w

    bj = r_build.json()
    checkout = bj.get("checkout") or {}
    w.checkout_id = checkout.get("id")
    comps = checkout.get("components") or {}
    rate_uuid = ((comps.get("shipping_pickup_details") or {}).get("pickup_details") or {}).get("selected_rate_uuid")
    so_id = (comps.get("shipping_address") or {}).get("shipping_order_id")
    coords = ((comps.get("shipping_address") or {}).get("address") or {}).get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    checksum_build = (_find_checksum(bj) or [""])[0]

    t0 = time.monotonic()
    if so_id:
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_put = ex.submit(_put_payment_method, w.checkout_id, konto, pay_in_method)
            f_pts = ex.submit(_get_pickup_point, so_id, lat, lon, konto)
            r_put = f_put.result()
            point = f_pts.result()
    else:
        r_put = _put_payment_method(w.checkout_id, konto, pay_in_method)
        point = {}
    w.status_payment_method = r_put.status_code
    checksum_put = (_find_checksum(r_put.json()) or [""])[0] if r_put.status_code == 200 else ""
    w.timings["payment_method|pickup"] = round((time.monotonic() - t0) * 1000)

    details = {}
    if rate_uuid:
        details["rate_uuid"] = rate_uuid
    if point.get("code"):
        details["point_code"] = point["code"]
    if point.get("uuid"):
        details["point_uuid"] = point["uuid"]

    checksum = checksum_put or checksum_build
    if details:
        t0 = time.monotonic()
        r_pd = _put_pickup_details(w.checkout_id, details, konto)
        w.timings["pickup_details"] = round((time.monotonic() - t0) * 1000)
        w.status_pickup_details = r_pd.status_code
        if r_pd.status_code == 200:
            checksum = (_find_checksum(r_pd.json()) or [""])[0] or checksum

    if proba_payment:
        t0 = time.monotonic()
        r_pay = _payment(w.checkout_id, checksum, konto)
        w.timings["payment"] = round((time.monotonic() - t0) * 1000)
        w.status_payment = r_pay.status_code
        if r_pay.status_code == 200:
            pj = r_pay.json()
            w.payment_status = ((pj.get("payment") or {}).get("status"))
            w.redirect_url = (((pj.get("action") or {}).get("parameters") or {}).get("url") or "")
        else:
            w.error_code = (r_pay.json() or {}).get("code")

    return w
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && pytest tests/test_checkout.py -v`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/checkout.py bot/tests/test_checkout.py
git commit -m "feat: checkout w 100% curl_cffi (inquiries->build->payment), bez Camoufox"
```

---

### Task 6: `measurement.py` — `StepTimings` zamiast `CheckoutTimer`

**Files:**
- Modify: `bot/src/vintedbot/measurement.py`
- Test: `bot/tests/test_measurement.py`

- [ ] **Step 1: Napisz test**

```python
# bot/tests/test_measurement.py — dopisz
from vintedbot.measurement import StepTimings


def test_step_timings_suma():
    st = StepTimings()
    st["a"] = 10.0
    st["b"] = 20.0
    assert st.suma == 30.0
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && pytest tests/test_measurement.py -v`
Expected: FAIL (brak `StepTimings`)

- [ ] **Step 3: Dodaj `StepTimings`, usuń `CheckoutTimer`**

Dodaj klasę:

```python
class StepTimings(dict):
    """Rejestruje czas kroków checkoutu (ms)."""
    @property
    def suma(self) -> float:
        return round(sum(v for v in self.values() if isinstance(v, (int, float))), 3)
```

Usuń klasę `CheckoutTimer` (wyparta — pomiar kroków jest w `WynikCheckoutu.timings`).

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && pytest tests/test_measurement.py -v`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/measurement.py bot/tests/test_measurement.py
git commit -m "feat: StepTimings; usuń CheckoutTimer (wyparty przez pomiar kroków)"
```

---

### Task 7: `cli.py` — `autocop` bez silnika, z `--payment`

**Files:**
- Modify: `bot/src/vintedbot/cli.py`
- Test: `bot/tests/test_cli_e2e.py`

- [ ] **Step 1: Zaktualizuj testy E2E**

Zastąp `test_autocop_konczy_po_detekcji` nowym testem (bez silnika):

```python
def test_autocop_no_checkout_po_detekcji(fake_http):
    payload = '{"items":[{"id":42,"title":"T","price":{"amount":"9.0","currency_code":"PLN"}}]}'
    url = "https://www.vinted.pl/api/v2/catalog/items?brand_ids=53&per_page=96&order=newest_first"
    fake_http(url, payload)

    runner = CliRunner()
    result = runner.invoke(cli, ["autocop", "--brand", "53", "--max-iter", "1", "--no-checkout"])

    assert result.exit_code == 0
    assert "42" in result.output
```

Zaktualizuj import na górze: `from vintedbot import config` (dla `wczytaj_cookies`).

- [ ] **Step 2: Uruchom — FAIL (opcjonalnie)**

Run: `cd bot && pytest tests/test_cli_e2e.py -v`
Expected: może przechodzić na starym kodzie; po zmianie CLI nadal musi przechodzić.

- [ ] **Step 3: Przepisz `autocop` (usuń `--engine`)**

```python
from .config import wczytaj_cookies
from .checkout import zrealizuj_zakup
from .models import Filtry, KonfiguracjaKonta


@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--max-iter", default=None, type=int)
@click.option("--no-checkout", is_flag=True, help="Nie rezerwuj — tylko wykryj")
@click.option("--cookies", default=None, type=click.Path(exists=True), help="Cookies (JSON lub Netscape)")
@click.option("--payment", is_flag=True, help="Po rezerwacji spróbuj dojść do próby payment")
def autocop(brand, search, max_iter, no_checkout, cookies, payment):
    """Monitoruj i (opcjonalnie) rezerwuj + próbuj zapłacić (curl_cffi)."""
    from .detection import monitoruj

    f = Filtry(brand_ids=list(brand), search_text=search)
    ck = wczytaj_cookies(cookies) if cookies else {}
    konto = KonfiguracjaKonta(cookies=ck)

    def on_nowe(nowe):
        for o in nowe:
            click.echo(f"NOWA: {o.id} {o.title} {o.cena}")
            if no_checkout:
                continue
            if o.seller_id is None:
                click.echo("(pominięto — brak seller_id)")
                continue
            w = zrealizuj_zakup(o.id, o.seller_id, konto, proba_payment=payment)
            if w.checkout_id:
                click.echo(f"REZERWACJA: checkout={w.checkout_id} build={w.status_build}")
            if payment:
                click.echo(f"PAYMENT: status={w.status_payment} redirect={w.redirect_url}")

    monitoruj(f, interwal=1.0, callback=on_nowe, max_iter=max_iter, cookies=ck)
```

Zastąp też import `from .checkout import zarezerwuj` na powyższy (usuń `zarezerwuj_api`).
Komenda `monitor`, `bench`, `keepalive` — bez zmian poza importem `wczytaj_cookies` z config.

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && pytest tests/test_cli_e2e.py -v`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/cli.py bot/tests/test_cli_e2e.py
git commit -m "feat: autocop curl_cffi (bez engine) + flaga --payment"
```

---

### Task 8: `pyproject.toml` — usuń Camoufox

**Files:**
- Modify: `bot/pyproject.toml`

- [ ] **Step 1: Usuń zależność `camoufox`**

Usuń linię `"camoufox>=0.4",` z listy `dependencies`. Zostaw `click`, `curl_cffi`, `pydantic`.

- [ ] **Step 2: Zweryfikuj, że brak importów camoufox w projekcie**

Run: `cd bot && grep -r "camoufox" src tests --include="*.py"`
Expected: brak wyników.

- [ ] **Step 3: Commit**

```bash
git add bot/pyproject.toml
git commit -m "chore: usuń zależność camoufox (ścieżka zakupowa = curl_cffi)"
```

---

### Task 9: Pełny przebieg testów + weryfikacja spójności

- [ ] **Step 1: Uruchom całą suitę**

Run: `cd bot && pytest -q`
Expected: wszystkie testy przechodzą, 0 błędów.

- [ ] **Step 2: Sprawdź diagnostykę IDE**

Otwórz zmienione pliki i zweryfikuj, że `GetDiagnostics` nie zgłasza błędów typów/importu.

- [ ] **Step 3: Commit (jeśli zostały luźne pliki)**

```bash
git add -A bot/
git commit -m "test: zielona suita po przebudowie na curl_cffi firefox135"
```

---

## Self-Review

**1. Spec coverage:**
- "100% curl_cffi, bez Camoufox" → Task 5 (checkout) + Task 8 (zależność).
- "nowy endpoint transakcji" → Task 4 (`utworz_transakcje`).
- "karta id=1" → Task 5 (`pay_in_method`).
- "token Incognia" → Task 3 (`incognia.py`).
- "flaga payment off" → Task 7 (`--payment`).
- "filtry bez humanizacji" → Task 4 (bez zmian filtrów) — zgodne.
- "1 konto, CLI" → zachowane w `cli.py`.

**2. Placeholder scan:** brak TBD/TODO; każdy krok ma pełny kod.

**3. Type consistency:** `zrealizuj_zakup(...) -> WynikCheckoutu` używany w Task 5 i 7 spójnie.
`KonfiguracjaKonta(cookies=...)` zdefiniowane w Task 2, używane w Task 4/5/7.
`wczytaj_cookies` z `config` (Task 1), używane w `cli` (Task 7) — spójne.
`Oferta.seller_id` (Task 2), używane w Task 7 (`o.seller_id`).

**Uwaga wykonawcza:** w Task 2 i 4 należy dopasować treść do istniejących fragmentów
(`Filtry`, istniejące `test_models.py`, `test_detection.py`), zachowując działające funkcje.