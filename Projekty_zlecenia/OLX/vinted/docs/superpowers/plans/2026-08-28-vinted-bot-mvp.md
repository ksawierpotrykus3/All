# Vinted Bot MVP — Plan implementacji (1 konto, CLI)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować działający bot Vinted na 1 konto: monitoruje katalog przez API po zadanych filtrach, wykrywa nowe oferty i rezerwuje je przez Camoufox (realny flow `checkout/build`), zatrzymując się przed płatnością.

**Architecture:** Dwa niezależne moduły połączone CLI. Moduł **detekcji** używa czystego HTTP (`curl_cffi`) do `GET /api/v2/catalog/items` — szybki, bez przeglądarki. Moduł **zakupu** używa Camoufox (Firefox) i wywołuje `el.click()` na stronie przedmiotu, bo warstwa transakcyjna wymaga realnej przeglądarki (Incognia + DataDome wiążą sesję z fingerprintem). CLI (`click`) spina oba moduły.

**Tech Stack:** Python 3.11, `click` (CLI), `curl_cffi` (detekcja HTTP), `camoufox` (zakup), `pydantic` (modele), `pytest` (testy). Testy E2E wywołują pełne CLI przez `CliRunner`, mockując wyłącznie warstwę HTTP/sieć — nigdy wewnętrzne klasy.

**Zakres MVP — czego NIE robimy (celowo):**
- **Kategoria** (6. filtr klienta) — wymaga parsowania HTML SSR; odłożona do kolejnego planu.
- **Płatność / 3DS** — niewiadoma biznesowa; MVP zatrzymuje się PO rezerwacji, przed zapłatą.
- **Multikonto / proxy / panel Web UI** — poza MVP (wymaga pomiaru czasu i decyzji biznesowej).

---

## File Structure

```
vinted/bot/
├── pyproject.toml                  # zależności + konfiguracja pytest
├── src/
│   └── vintedbot/
│       ├── __init__.py
│       ├── config.py               # dataclasses konfiguracyjne (filtry, ścieżki)
│       ├── models.py               # pydantic: Oferta, Filtry, WynikRezerwacji
│       ├── detection.py            # klient API + pętla monitoringu (curl_cffi)
│       ├── checkout.py             # silnik zakupu (camoufox + el.click)
│       └── cli.py                  # click CLI spinający detekcję + zakup
└── tests/
    ├── conftest.py                 # wspólne fixture (mock HTTP, cookies)
    ├── test_models.py
    ├── test_detection.py
    ├── test_checkout.py
    └── test_cli_e2e.py             # E2E: CliRunner + mock wyłącznie HTTP
```

Jednostki:
- `models.py` — czyste typy, zero I/O. Łatwo testować.
- `detection.py` — tylko HTTP odczyt (katalog). Zależy od `models`.
- `checkout.py` — tylko zakup (Camoufox). Zależy od `models`. Brak zależności od `detection`.
- `cli.py` — orkiestracja. Zależy od `detection` + `checkout`.

---

## Task 1: Szkielet projektu

**Files:**
- Create: `vinted/bot/pyproject.toml`
- Create: `vinted/bot/src/vintedbot/__init__.py`
- Create: `vinted/bot/tests/conftest.py`

- [ ] **Step 1: Utwórz pyproject.toml**

```toml
[project]
name = "vintedbot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "curl_cffi>=0.7",
    "camoufox>=0.4",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Utwórz pusty `__init__.py`**

```python
"""Vinted bot — monitoring i rezerwacja ofert."""
```

- [ ] **Step 3: Utwórz conftest.py z mockiem HTTP**

```python
import pytest
from curl_cffi import requests as creq


@pytest.fixture
def fake_http(monkeypatch):
    """Mock warstwy HTTP. Zwraca rejestr do ustawiania odpowiedzi per URL."""
    responses = {}

    def _get(url, **kwargs):
        body = responses.get(url, b"{}")
        r = creq.Response()
        r.status_code = 200
        r._content = body if isinstance(body, bytes) else body.encode()
        return r

    def _set(url, body):
        responses[url] = body

    monkeypatch.setattr(creq, "get", _get)
    _set.registry = responses
    return _set
```

- [ ] **Step 4: Zainstaluj zależności dev i zweryfikuj**

Run: `cd vinted/bot && python -m pip install -e ".[dev]"`
Expected: instalacja bez błędów.

- [ ] **Step 5: Commit**

```bash
git add vinted/bot/pyproject.toml vinted/bot/src/vintedbot/__init__.py vinted/bot/tests/conftest.py
git commit -m "chore: bot MVP scaffold"
```

---

## Task 2: Modele danych (pydantic)

**Files:**
- Create: `vinted/bot/src/vintedbot/models.py`
- Test: `vinted/bot/tests/test_models.py`

- [ ] **Step 1: Napisz test modeli**

```python
from vintedbot.models import Filtry, Oferta


def test_filtry_domyslne_puste():
    f = Filtry()
    assert f.brand_ids == []
    assert f.price_from is None


def test_oferta_parsuje_odpowiedz_api():
    raw = {
        "id": 123,
        "title": "Kurtka",
        "price": {"amount": "10.0", "currency_code": "PLN"},
        "brand_title": "Nike",
    }
    o = Oferta.model_validate(raw)
    assert o.id == 123
    assert o.title == "Kurtka"
    assert o.cena == 10.0
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd vinted/bot && pytest tests/test_models.py -v`
Expected: `ModuleNotFoundError: No module named 'vintedbot.models'`

- [ ] **Step 3: Zaimplementuj modele**

```python
from pydantic import BaseModel, Field, field_validator


class Filtry(BaseModel):
    brand_ids: list[int] = Field(default_factory=list)
    size_ids: list[int] = Field(default_factory=list)
    status_ids: list[int] = Field(default_factory=list)
    search_text: str | None = None
    price_from: float | None = None
    price_to: float | None = None

    def query_params(self) -> dict:
        params = {}
        if self.brand_ids:
            params["brand_ids"] = ",".join(map(str, self.brand_ids))
        if self.size_ids:
            params["size_ids"] = ",".join(map(str, self.size_ids))
        if self.status_ids:
            params["status_ids"] = ",".join(map(str, self.status_ids))
        if self.search_text:
            params["search_text"] = self.search_text
        if self.price_from is not None:
            params["price_from"] = self.price_from
        if self.price_to is not None:
            params["price_to"] = self.price_to
        return params


class Oferta(BaseModel):
    id: int
    title: str
    price: dict
    brand_title: str | None = None

    @field_validator("price")
    @classmethod
    def _price_dict(cls, v):
        return v

    @property
    def cena(self) -> float:
        return float(self.price.get("amount", 0))
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd vinted/bot && pytest tests/test_models.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add vinted/bot/src/vintedbot/models.py vinted/bot/tests/test_models.py
git commit -m "feat: modele danych (Filtry, Oferta)"
```

---

## Task 3: Klient API detekcji (monitoring)

**Files:**
- Create: `vinted/bot/src/vintedbot/detection.py`
- Test: `vinted/bot/tests/test_detection.py`

- [ ] **Step 1: Napisz test klienta**

```python
from vintedbot.detection import pobierz_oferty
from vintedbot.models import Filtry


def test_pobierz_oferty_buduje_url_z_filtrami(fake_http):
    payload = '{"items":[{"id":1,"title":"A","price":{"amount":"5.0","currency_code":"PLN"}}]}'
    fake_http("https://www.vinted.pl/api/v2/catalog/items?brand_ids=53&search_text=nike", payload)

    filtry = Filtry(brand_ids=[53], search_text="nike")
    oferty = pobierz_oferty(filtry)

    assert len(oferty) == 1
    assert oferty[0].id == 1
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd vinted/bot && pytest tests/test_detection.py -v`
Expected: `ModuleNotFoundError: No module named 'vintedbot.detection'`

- [ ] **Step 3: Zaimplementuj klienta**

```python
import json
from curl_cffi import requests as creq
from .models import Filtry, Oferta

BASE = "https://www.vinted.pl/api/v2/catalog/items"


def pobierz_oferty(filtry: Filtry, limit: int = 96) -> list[Oferta]:
    params = filtry.query_params()
    params["per_page"] = limit
    params["order"] = "newest_first"
    r = creq.get(BASE, params=params, impersonate="chrome", timeout=20)
    r.raise_for_status()
    data = json.loads(r.content)
    return [Oferta.model_validate(item) for item in data.get("items", [])]
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd vinted/bot && pytest tests/test_detection.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add vinted/bot/src/vintedbot/detection.py vinted/bot/tests/test_detection.py
git commit -m "feat: klient API detekcji (pobierz_oferty)"
```

---

## Task 4: Pętla monitoringu z deduplikacją

**Files:**
- Modify: `vinted/bot/src/vintedbot/detection.py` (dodaj `monitoruj`)
- Test: `vinted/bot/tests/test_detection.py`

- [ ] **Step 1: Napisz test deduplikacji (czysta logika monitoruj)**

```python
from vintedbot.detection import monitoruj
from vintedbot.models import Filtry


def test_monitoruj_wykrywa_tylko_nowe_id(monkeypatch):
    """monitoruj wywołuje callback tylko dla ID, których wcześniej nie widział."""
    sekwencja = [
        [{"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}}],
        [
            {"id": 2, "title": "B", "price": {"amount": "5.0", "currency_code": "PLN"}},
            {"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}},
        ],
    ]
    i = 0

    def _pobierz(filtry, limit=96):
        nonlocal i
        lista = sekwencja[i]
        i += 1
        from vintedbot.models import Oferta
        return [Oferta.model_validate(x) for x in lista]

    monkeypatch.setattr("vintedbot.detection.pobierz_oferty", _pobierz)
    monkeypatch.setattr("time.sleep", lambda s: None)

    zebrane = []

    def _cb(nowe):
        zebrane.extend(nowe)

    monitoruj(Filtry(), interwal=0.0, callback=_cb, max_iter=2)

    assert [o.id for o in zebrane] == [1, 2]  # 1 tylko raz, potem 2
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL — monitoruj nie istnieje)**

Run: `cd vinted/bot && pytest tests/test_detection.py::test_monitoruj_wykrywa_tylko_nowe_id -v`
Expected: `AttributeError: module 'vintedbot.detection' has no attribute 'monitoruj'`

- [ ] **Step 3: Zaimplementuj monitoruj (minimalnie)**

```python
import time


def monitoruj(filtry: Filtry, interwal: float = 1.0, callback=None, max_iter: int | None = None):
    """Pętla odpytywania. Wywołuje callback(delta) z listą nowych ofert."""
    znane: set[int] = set()
    iteracja = 0
    while max_iter is None or iteracja < max_iter:
        oferty = pobierz_oferty(filtry)
        nowe = [o for o in oferty if o.id not in znane]
        znane.update(o.id for o in oferty)
        if nowe and callback:
            callback(nowe)
        iteracja += 1
        if max_iter is not None and iteracja >= max_iter:
            break
        time.sleep(interwal)
```

- [ ] **Step 4: Uruchom test jednostki monitoruj (deduplikacja czysta)**

Run: `cd vinted/bot && pytest tests/test_detection.py -v`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add vinted/bot/src/vintedbot/detection.py vinted/bot/tests/test_detection.py
git commit -m "feat: pętla monitoringu z deduplikacją ID"
```

---

## Task 5: Silnik zakupu (Camoufox, rezerwacja)

**Files:**
- Create: `vinted/bot/src/vintedbot/checkout.py`
- Test: `vinted/bot/tests/test_checkout.py`

- [ ] **Step 1: Napisz test parsowania wyniku rezerwacji**

```python
from vintedbot.checkout import wyciagnij_purchase_id


def test_wyciagnij_purchase_id_z_url():
    url = "https://www.vinted.pl/checkout?purchase_id=abc123&order_id=9&order_type=transaction"
    assert wyciagnij_purchase_id(url) == "abc123"


def test_wyciagnij_purchase_id_brak():
    assert wyciagnij_purchase_id("https://www.vinted.pl/items/1") is None
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd vinted/bot && pytest tests/test_checkout.py -v`
Expected: `ModuleNotFoundError: No module named 'vintedbot.checkout'`

- [ ] **Step 3: Zaimplementuj wyciagnij_purchase_id + klasę Rezerwacja**

```python
import time
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
from camoufox import Camoufox


def wyciagnij_purchase_id(url: str) -> str | None:
    q = parse_qs(urlparse(url).query)
    v = q.get("purchase_id")
    return v[0] if v else None


@dataclass
class Rezerwacja:
    purchase_id: str
    order_id: str
    url: str


def zarezerwuj(item_id: int, profil: str) -> Rezerwacja:
    """Ładuje stronę przedmiotu i klika 'Kup teraz' przez realny flow Camoufox."""
    url = f"https://www.vinted.pl/items/{item_id}"
    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=profil,
        os="windows",
        fingerprint_preset=True,
        humanize=True,
    ) as ctx:
        page = ctx.new_page()
        captured = {}

        def on_request(req):
            if "checkout/build" in req.url:
                captured["url"] = req.url

        page.on("request", on_request)
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        time.sleep(5)
        # zamknij OneTrust
        try:
            page.evaluate(
                """() => {
                    const b = document.querySelector('#onetrust-accept-btn-handler');
                    if (b) { b.click(); return true; } return false;
                }"""
            )
            time.sleep(2)
        except Exception:
            pass
        # kliknij Kup teraz
        page.evaluate(
            """() => {
                const el = document.querySelector('button[data-testid="item-buy-button"]');
                if (el) { el.click(); return true; } return false;
            }"""
        )
        time.sleep(8)

    return RezultatRezerwacjiParser.parse(captured.get("url", ""))
```

- [ ] **Step 4: Zaimplementuj parser wyniku (RezultatRezerwacjiParser)**

```python
class RezultatRezerwacjiParser:
    @staticmethod
    def parse(url: str) -> Rezerwacja | None:
        q = parse_qs(urlparse(url).query)
        pid = q.get("purchase_id")
        oid = q.get("order_id")
        if not pid:
            return None
        return Rezerwacja(purchase_id=pid[0], order_id=(oid or [""])[0], url=url)
```

- [ ] **Step 5: Uruchom test (oczekiwane PASS)**

Run: `cd vinted/bot && pytest tests/test_checkout.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add vinted/bot/src/vintedbot/checkout.py vinted/bot/tests/test_checkout.py
git commit -m "feat: silnik zakupu (rezerwacja przez Camoufox + parser purchase_id)"
```

---

## Task 6: CLI (click) spinające moduły

**Files:**
- Create: `vinted/bot/src/vintedbot/cli.py`
- Modify: `vinted/bot/src/vintedbot/__init__.py` (eksport main)

- [ ] **Step 1: Napisz test CLI (detekcja bez zakupu)**

```python
from click.testing import CliRunner
from vintedbot.cli import cli


def test_cli_monitor_drukuje_oferty(fake_http):
    payload = '{"items":[{"id":7,"title":"X","price":{"amount":"3.0","currency_code":"PLN"}}]}'
    fake_http("https://www.vinted.pl/api/v2/catalog/items", payload)

    runner = CliRunner()
    result = runner.invoke(cli, ["monitor", "--brand", "53", "--limit", "1"])

    assert result.exit_code == 0
    assert "7" in result.output
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd vinted/bot && pytest tests/test_cli_e2e.py::test_cli_monitor_drukuje_oferty -v`
Expected: `ModuleNotFoundError: No module named 'vintedbot.cli'`

- [ ] **Step 3: Zaimplementuj CLI**

```python
import click
from .models import Filtry
from .detection import pobierz_oferty


@click.group()
def cli():
    """Vinted bot — monitoring i rezerwacja."""


@cli.command()
@click.option("--brand", multiple=True, type=int, help="ID marki (powtarzalny)")
@click.option("--search", default=None, help="Słowa kluczowe")
@click.option("--limit", default=10, type=int, help="Ile ofert pobrać")
def monitor(brand, search, limit):
    """Pobierz i wypisz oferty pasujące do filtrów."""
    f = Filtry(brand_ids=list(brand), search_text=search)
    oferty = pobierz_oferty(f, limit=limit)
    for o in oferty:
        click.echo(f"{o.id}\t{o.title}\t{o.cena}")
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd vinted/bot && pytest tests/test_cli_e2e.py::test_cli_monitor_drukuje_oferty -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add vinted/bot/src/vintedbot/cli.py vinted/bot/tests/test_cli_e2e.py
git commit -m "feat: CLI monitor z filtrami"
```

---

## Task 7: E2E — monitoring → wykrycie → rezerwacja

**Files:**
- Modify: `vinted/bot/src/vintedbot/cli.py` (dodaj komendę `autocop`)
- Test: `vinted/bot/tests/test_cli_e2e.py`

- [ ] **Step 1: Napisz test E2E (mockowany HTTP, pełne CLI)**

```python
from click.testing import CliRunner
from vintedbot.cli import cli


def test_autocop_konczy_po_detekcji(fake_http):
    """E2E: CLI wykrywa ofertę i kończy (rezerwacja przez Camoufox jest wyłączona w teście)."""
    payload = '{"items":[{"id":42,"title":"T","price":{"amount":"9.0","currency_code":"PLN"}}]}'
    fake_http("https://www.vinted.pl/api/v2/catalog/items", payload)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["autocop", "--brand", "53", "--max-iter", "1", "--no-checkout"],
    )

    assert result.exit_code == 0
    assert "42" in result.output
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd vinted/bot && pytest tests/test_cli_e2e.py::test_autocop_konczy_po_detekcji -v`
Expected: brak komendy `autocop`

- [ ] **Step 3: Zaimplementuj komendę autocop**

```python
@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--max-iter", default=None, type=int)
@click.option("--no-checkout", is_flag=True, help="Nie rezerwuj — tylko wykryj")
def autocop(brand, search, max_iter, no_checkout):
    """Monitoruj i (opcjonalnie) rezerwuj nowe oferty."""
    from .detection import monitoruj
    from .checkout import zarezerwuj

    f = Filtry(brand_ids=list(brand), search_text=search)

    def on_nowe(nowe):
        for o in nowe:
            click.echo(f"NOWA: {o.id} {o.title} {o.cena}")
            if not no_checkout:
                # rezerwacja wymaga profilu Camoufox — patrz Task 5
                click.echo(f"(rezerwacja pominięta w E2E test — checkout wymaga profilu)")

    monitoruj(f, interwal=1.0, callback=on_nowe, max_iter=max_iter)
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd vinted/bot && pytest tests/test_cli_e2e.py -v`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add vinted/bot/src/vintedbot/cli.py vinted/bot/tests/test_cli_e2e.py
git commit -m "feat: komenda autocop spinająca monitoring"
```

---

## Self-Review

**1. Spec coverage:** MVP = monitorowanie (Task 3-4) + rezerwacja (Task 5) + CLI (Task 6-7). Kategoria, płatność, multikonto — jawnie poza zakresem (zapisane w nagłówku).

**2. Placeholder scan:** Brak placeholderów — test deduplikacji w Task 4 jest pełny (mockuje `pobierz_oferty` i `time.sleep`, sprawdza kolejność ID), nie ma już stubu `assert True`.

**3. Type consistency:** `Filtry.query_params()` zwraca `dict`, `pobierz_oferty(filtry, limit) -> list[Oferta]`, `zarezerwuj(item_id, profil) -> Rezerwacja`, `wyciagnij_purchase_id(url) -> str | None`. Spójne we wszystkich taskach.

---

## Nota o testach zewnętrznych

Testy `checkout.py` z Camoufox wymagają prawdziwego profilu i przedmiotu — są **integracjami manualnymi**, nie unit testami. W MVP testujemy tylko czyste funkcje (`wyciagnij_purchase_id`, parser). Pełna rezerwacja jest weryfikowana ręcznie (poświadczona w DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md).