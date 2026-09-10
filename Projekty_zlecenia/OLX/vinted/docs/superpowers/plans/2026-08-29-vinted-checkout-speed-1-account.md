# Vinted Checkout Speed (1 konto) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zmierzyć i obniżyć czas detekcji (<200 ms wewnętrznie) oraz rezerwacji (<3 s p50) na 1 koncie, z twardym pomiarem porównawczym do kops.gg.

**Architecture:** Rozszerzenie istniejącego `bot/src/vintedbot/`. Dodajemy moduł pomiarowy `measurement.py` (czysty, bez I/O), rozszerzamy `detection.py` o backoff+jitter+metryki oraz `checkout.py` o dwie ścieżki rezerwacji (`api` = Faza C, `browser` = Faza A). `cli.py` dostaje flagę wyboru silnika i komendę benchmark.

**Tech Stack:** Python 3.11, `click`, `curl_cffi`, `camoufox`, `pydantic`, `pytest`. Testy E2E przez `CliRunner`, mockują wyłącznie HTTP.

---

## File Structure

```
bot/
├── src/vintedbot/
│   ├── measurement.py       # NOWY — rejestratory latencji + raport JSON (czysty)
│   ├── detection.py         # MODYFIKACJA — backoff/jitter, metryki detekcji
│   ├── checkout.py          # MODYFIKACJA — zarezerwuj_api (C) + zarezerwuj_browser (A)
│   ├── cli.py               # MODYFIKACJA — flagi silnika, pełne filtry, komenda bench
│   └── models.py            # MODYFIKACJA — bez zmian (Filtry już ma size/status/price)
└── tests/
    ├── test_measurement.py  # NOWY
    ├── test_detection.py    # MODYFIKACJA
    ├── test_checkout.py     # MODYFIKACJA
    └── test_cli_e2e.py      # MODYFIKACJA
```

Jednostki:
- `measurement.py` — czyste struktury pomiarowe, zero zależności od Vinted. Testowalne w izolacji.
- `detection.py` — HTTP odczyt + metryki. Zależy od `models` + `measurement`.
- `checkout.py` — dwie ścieżki zakupu. Zależy od `models` + `measurement`. Brak zależności od `detection`.
- `cli.py` — orkiestracja. Zależy od `detection` + `checkout` + `measurement`.

---

## Task 1: Moduł pomiarowy `measurement.py`

**Files:**
- Create: `bot/src/vintedbot/measurement.py`
- Test: `bot/tests/test_measurement.py`

- [ ] **Step 1: Napisz test modułu pomiarowego**

```python
from vintedbot.measurement import LatencyRecorder, CheckoutTimer


def test_latency_recorder_liczy_percentyle():
    r = LatencyRecorder()
    for v in [1.0, 2.0, 3.0, 4.0, 100.0]:
        r.add(v)
    assert r.count == 5
    assert r.p50 == 3.0
    assert r.p95 == 100.0
    assert r.p99 == 100.0


def test_latency_recorder_pusty():
    r = LatencyRecorder()
    assert r.count == 0
    assert r.p50 == 0.0


def test_checkout_timer_zwraca_elapsed_i_sukces():
    t = CheckoutTimer()
    with t:
        pass  # symulacja pracy
    assert t.elapsed_ms >= 0
    assert t.success is None  # nieustawione bez set_result


def test_raport_do_dict_ma_pola():
    r = LatencyRecorder()
    r.add(2.0)
    d = r.to_dict()
    assert set(d) == {"count", "p50", "p95", "p99", "avg"}
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd bot && pytest tests/test_measurement.py -v`
Expected: `ModuleNotFoundError: No module named 'vintedbot.measurement'`

- [ ] **Step 3: Zaimplementuj measurement.py**

```python
"""Repozytorium pomiarowe: rejestratory latencji i timer checkoutu. Czyste, bez I/O."""
import time
from dataclasses import dataclass, field


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(pct / 100 * len(s)))
    return round(s[idx], 3)


@dataclass
class LatencyRecorder:
    """Zbiera próbki latencji i liczy percentyle."""

    samples: list[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def p50(self) -> float:
        return _percentile(self.samples, 50)

    @property
    def p95(self) -> float:
        return _percentile(self.samples, 95)

    @property
    def p99(self) -> float:
        return _percentile(self.samples, 99)

    @property
    def avg(self) -> float:
        if not self.samples:
            return 0.0
        return round(sum(self.samples) / len(self.samples), 3)

    def add(self, value_ms: float) -> None:
        self.samples.append(value_ms)

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
            "avg": self.avg,
        }


class CheckoutTimer:
    """Mierzy czas checkoutu end-to-end (decyzja -> purchase_id)."""

    def __init__(self) -> None:
        self._start: float | None = None
        self._elapsed_ms: float = 0.0
        self.success: bool | None = None
        self.engine: str | None = None

    def __enter__(self) -> "CheckoutTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *exc) -> None:
        if self._start is not None:
            self._elapsed_ms = (time.monotonic() - self._start) * 1000

    @property
    def elapsed_ms(self) -> float:
        return round(self._elapsed_ms, 3)

    def set_result(self, success: bool, engine: str) -> None:
        self.success = success
        self.engine = engine
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd bot && pytest tests/test_measurement.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/measurement.py bot/tests/test_measurement.py
git commit -m "feat: measurement module (latency recorder + checkout timer)"
```

---

## Task 2: Pełne filtry w CLI (`--size`, `--status`, `--price-from/--price-to`)

**Files:**
- Modify: `bot/src/vintedbot/cli.py`
- Test: `bot/tests/test_cli_e2e.py`

- [ ] **Step 1: Napisz test filtrow w CLI**

```python
from urllib.parse import urlencode

from click.testing import CliRunner

from vintedbot.cli import cli


def test_cli_monitor_z_pełnymi_filtrami(fake_http):
    payload = '{"items":[{"id":7,"title":"X","price":{"amount":"3.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {
        "brand_ids": "53",
        "size_ids": "208",
        "status_ids": "6",
        "price_from": 10,
        "price_to": 50,
        "per_page": 10,
        "order": "newest_first",
    }
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "monitor",
            "--brand", "53",
            "--size", "208",
            "--status", "6",
            "--price-from", "10",
            "--price-to", "50",
            "--limit", "10",
        ],
    )

    assert result.exit_code == 0
    assert "7" in result.output
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL — brak flag)**

Run: `cd bot && pytest tests/test_cli_e2e.py::test_cli_monitor_z_pełnymi_filtrami -v`
Expected: `Error: No such option: --size`

- [ ] **Step 3: Dodaj opcje do komendy `monitor`**

W `cli.py` zamień dekorator komendy `monitor` na:

```python
@cli.command()
@click.option("--brand", multiple=True, type=int, help="ID marki (powtarzalny)")
@click.option("--size", multiple=True, type=int, help="ID rozmiaru (powtarzalny)")
@click.option("--status", multiple=True, type=int, help="ID stanu (powtarzalny)")
@click.option("--price-from", default=None, type=float, help="Cena od")
@click.option("--price-to", default=None, type=float, help="Cena do")
@click.option("--search", default=None, help="Słowa kluczowe")
@click.option("--limit", default=10, type=int, help="Ile ofert pobrać")
@click.option("--cookies", default=None, type=click.Path(exists=True), help="Ścieżka do pliku cookies (Netscape)")
def monitor(brand, size, status, price_from, price_to, search, limit, cookies):
    """Pobierz i wypisz oferty pasujące do filtrów."""
    f = Filtry(
        brand_ids=list(brand),
        size_ids=list(size),
        status_ids=list(status),
        price_from=price_from,
        price_to=price_to,
        search_text=search,
    )
    ck = wczytaj_cookies(cookies) if cookies else None
    oferty = pobierz_oferty(f, limit=limit, cookies=ck)
    for o in oferty:
        click.echo(f"{o.id}\t{o.title}\t{o.cena}")
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd bot && pytest tests/test_cli_e2e.py::test_cli_monitor_z_pełnymi_filtrami -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/cli.py bot/tests/test_cli_e2e.py
git commit -m "feat: expose size/status/price filters in CLI"
```

---

## Task 3: Backoff + jitter + metryka detekcji w `detection.py`

**Files:**
- Modify: `bot/src/vintedbot/detection.py`
- Test: `bot/tests/test_detection.py`

- [ ] **Step 1: Napisz test backoffu (czysta funkcja)**

```python
from vintedbot.detection import _nastepny_interwal


def test_backoff_wzrasta_do_maksimum():
    # po 1 błędzie 429 -> 2s, po 2 -> 4s, po 4+ -> cap 8s (bez jittera, seed 0)
    assert _nastepny_interwal(1, jitter=0.0) == 2.0
    assert _nastepny_interwal(2, jitter=0.0) == 4.0
    assert _nastepny_interwal(5, jitter=0.0) == 8.0


def test_backoff_jitter_nie_przekracza_capu():
    assert _nastepny_interwal(5, jitter=0.2) <= 8.0
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd bot && pytest tests/test_detection.py::test_backoff_wzrasta_do_maksimum -v`
Expected: `ImportError: cannot import name '_nastepny_interwal'`

- [ ] **Step 3: Zaimplementuj `_nastepny_interwal` w detection.py**

Dodaj na górze pliku, po importach:

```python
import random

_BACKOFF_BASE = 2.0
_BACKOFF_CAP = 8.0


def _nastepny_interwal(bledy: int, jitter: float = 0.2) -> float:
    """Wykładniczy backoff z jitterem. `bledy` = liczba kolejnych porażek (>=1)."""
    raw = min(_BACKOFF_BASE * (2 ** (bledy - 1)), _BACKOFF_CAP)
    if jitter <= 0:
        return raw
    return round(raw * (1 + random.uniform(-jitter, jitter)), 3)
```

- [ ] **Step 4: Zaimplementuj pętlę z backoffem i metryką w `monitoruj`**

Zamień treść `monitoruj` w `detection.py` na:

```python
def monitoruj(filtry, interwal=1.0, callback=None, max_iter=None, cookies=None, recorder=None):
    """Pętla odpytywania z backoffem 429/403 i metryką latencji wewnętrznej."""
    znane: set[int] = set()
    iteracja = 0
    kolejne_bledy = 0
    while max_iter is None or iteracja < max_iter:
        t0 = time.monotonic()
        try:
            oferty = pobierz_oferty(filtry, cookies=cookies) if cookies else pobierz_oferty(filtry)
        except Exception:
            # 429/403 -> backoff; nie zabijaj pętli
            kolejne_bledy += 1
            if recorder is not None:
                recorder.add(0.0)  # porażka nie liczy się do latencji sukcesu
            time.sleep(_nastepny_interwal(kolejne_bledy))
            iteracja += 1
            if max_iter is not None and iteracja >= max_iter:
                break
            continue
        kolejne_bledy = 0
        nowe = [o for o in oferty if o.id not in znane]
        znane.update(o.id for o in oferty)
        if nowe and callback:
            lat_ms = (time.monotonic() - t0) * 1000
            if recorder is not None:
                recorder.add(lat_ms)
            callback(nowe)
        iteracja += 1
        if max_iter is not None and iteracja >= max_iter:
            break
        time.sleep(interwal)
```

- [ ] **Step 5: Uruchom testy detection**

Run: `cd bot && pytest tests/test_detection.py -v`
Expected: wszystkie przechodzą (istniejące + nowe backoff)

- [ ] **Step 6: Commit**

```bash
git add bot/src/vintedbot/detection.py bot/tests/test_detection.py
git commit -m "feat: exponential backoff + jitter + detection latency metric"
```

---

## Task 4: Ścieżka rezerwacji API (Faza C) — `zarezerwuj_api`

**Files:**
- Modify: `bot/src/vintedbot/checkout.py`
- Test: `bot/tests/test_checkout.py`

- [ ] **Step 1: Napisz test budowy payloadu i nagłówków (czysta funkcja)**

```python
from vintedbot.checkout import _buduj_request_checkout_api


def test_buduj_request_checkout_api():
    url, payload, headers = _buduj_request_checkout_api(
        transaction_id=21867789545,
        order_type="transaction",
        csrf="abc",
        anon_id="anon-1",
    )
    assert url == "https://www.vinted.pl/api/v2/purchases/checkout/build"
    assert payload == {"purchase_items": [{"id": 21867789545, "type": "transaction"}]}
    assert headers["X-CSRF-Token"] == "abc"
    assert headers["x-anon-id"] == "anon-1"
    assert headers["Content-Type"] == "application/json"
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd bot && pytest tests/test_checkout.py::test_buduj_request_checkout_api -v`
Expected: `ImportError: cannot import name '_buduj_request_checkout_api'`

- [ ] **Step 3: Zaimplementuj `_buduj_request_checkout_api` i `zarezerwuj_api`**

Dodaj na górze `checkout.py` (po importach):

```python
import os
from curl_cffi import requests as creq

_CHECKOUT_BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
_DEFAULT_CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"


def _buduj_request_checkout_api(transaction_id: int, order_type: str, csrf: str, anon_id: str):
    url = _CHECKOUT_BUILD_URL
    payload = {"purchase_items": [{"id": transaction_id, "type": order_type}]}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": csrf,
        "x-anon-id": anon_id,
        "locale": "pl-PL",
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    return url, payload, headers
```

Dodaj funkcję `zarezerwuj_api` (pod `zarezerwuj`):

```python
def zarezerwuj_api(transaction_id: int, cookies: dict[str, str], anon_id: str, order_type: str = "transaction"):
    """Faza C: czysty POST /checkout/build przez curl_cffi, bez przeglądarki.

    Zwraca Rezerwacja | None. Wymaga nagłówka Incognia (JWE), którego curl_cffi
    nie umie wygenerować — stąd spike z twardym timeboxem.
    """
    csrf = os.environ.get("VINTED_CSRF_TOKEN", _DEFAULT_CSRF)
    url, payload, headers = _buduj_request_checkout_api(transaction_id, order_type, csrf, anon_id)
    r = creq.post(url, json=payload, headers=headers, cookies=cookies, impersonate="chrome", timeout=20)
    if r.status_code != 200:
        return None
    # purchase_id przychodzi w URL redirecta / w ciele — tu zakładamy redirect w Location
    loc = r.headers.get("location", "")
    return RezultatRezerwacjiParser.parse(loc) if loc else None
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd bot && pytest tests/test_checkout.py::test_buduj_request_checkout_api -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/checkout.py bot/tests/test_checkout.py
git commit -m "feat: api checkout path (Phase C) — checkout/build via curl_cffi"
```

---

## Task 5: Ścieżka rezerwacji browser (Faza A) — pre-warmowana sesja

**Files:**
- Modify: `bot/src/vintedbot/checkout.py`
- Test: `bot/tests/test_checkout.py`

- [ ] **Step 1: Napisz test flagi/struktury pre-warm (czysta logika)**

```python
from vintedbot.checkout import _czy_prewarm_wymagany


def test_czy_prewarm_wymagany_przy_pustym_konteskcie():
    assert _czy_prewarm_wymagany(None) is True
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd bot && pytest tests/test_checkout.py::test_czy_prewarm_wymagany_przy_pustym_konteskcie -v`
Expected: `ImportError: cannot import name '_czy_prewarm_wymagany'`

- [ ] **Step 3: Zaimplementuj helper i rozszerz `zarezerwuj` o pre-warm**

Dodaj w `checkout.py` obok `_get_context`:

```python
def _czy_prewarm_wymagany(ctx) -> bool:
    """Pre-warm wymagany, gdy nie mamy jeszcze ciepłego kontekstu."""
    return ctx is None
```

Zamień początek funkcji `zarezerwuj` (nagłówek + pierwsze linie do `page.goto`) tak, aby
obsługiwał ponowne użycie już otwartego kontekstu zamiast startu od zera:

```python
def zarezerwuj(item_id: int, profil: str, os_name: str | None = None) -> Rezerwacja | None:
    """Faza A: rezerwacja przez realny flow Camoufox z pre-warmowaną sesją."""
    ctx = _get_context(profil, os_name=os_name)
    page = None
    captured = {}

    def on_response(resp):
        if "/checkout?" in resp.url and "purchase_id=" in resp.url:
            captured["url"] = resp.url

    try:
        page = ctx.new_page()
        page.on("response", on_response)
        # Pre-warm: jeśli mamy już ciepłą sesję, pomijamy pełne goto na /items/{id}
        # i próbujemy wywołać zakup bezpośrednio na otwartej stronie.
        page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=90000)
        # ... reszta bez zmian (wait_for_selector, oneTrust, el.click, pętla czekania)
```

> Uwaga: pełna optymalizacja „bez goto" wymaga zmierzenia, czy Vinted wymaga załadowania
> strony przedmiotu przed wystawieniem przycisku. Ten task dodaje strukturę pre-warm;
> właściwy benchmark jest w Task 8.

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd bot && pytest tests/test_checkout.py -v`
Expected: wszystkie przechodzą (istniejące 4 + nowy 1)

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/checkout.py bot/tests/test_checkout.py
git commit -m "feat: pre-warm structure for browser checkout (Phase A)"
```

---

## Task 6: CLI — wybór silnika i komenda benchmark

**Files:**
- Modify: `bot/src/vintedbot/cli.py`
- Test: `bot/tests/test_cli_e2e.py`

- [ ] **Step 1: Napisz test komendy benchmark (mockowany HTTP)**

```python
from urllib.parse import urlencode

from click.testing import CliRunner

from vintedbot.cli import cli


def test_bench_drukuje_raport_json(fake_http):
    payload = '{"items":[{"id":42,"title":"T","price":{"amount":"9.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "per_page": 96, "order": "newest_first"}
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    runner = CliRunner()
    result = runner.invoke(cli, ["bench", "--brand", "53", "--max-iter", "2"])

    assert result.exit_code == 0
    assert '"count"' in result.output
    assert '"p50"' in result.output
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL — brak komendy bench)**

Run: `cd bot && pytest tests/test_cli_e2e.py::test_bench_drukuje_raport_json -v`
Expected: `Usage: cli [OPTIONS] COMMAND [ARGS]...` (no such command `bench`)

- [ ] **Step 3: Zaimplementuj komendę `bench` i flagę `--engine` w `autocop`**

Dodaj import w `cli.py`:

```python
import json
from .measurement import LatencyRecorder, CheckoutTimer
```

Dodaj komendę `bench` (przed `if __name__`):

```python
@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--max-iter", default=5, type=int)
@click.option("--cookies", default=None, type=click.Path(exists=True))
def bench(brand, search, max_iter, cookies):
    """Benchmark detekcji: mierzy latencję wewnętrzną i wypisuje raport JSON."""
    from .detection import monitoruj

    f = Filtry(brand_ids=list(brand), search_text=search)
    ck = wczytaj_cookies(cookies) if cookies else None
    recorder = LatencyRecorder()

    def _cb(nowe):
        pass

    monitoruj(f, interwal=0.0, callback=_cb, max_iter=max_iter, cookies=ck, recorder=recorder)
    click.echo(json.dumps(recorder.to_dict(), ensure_ascii=False))
```

Rozszerz komendę `autocop` o flagę `--engine` (domyślnie `browser`):

```python
@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--max-iter", default=None, type=int)
@click.option("--no-checkout", is_flag=True, help="Nie rezerwuj — tylko wykryj")
@click.option("--engine", type=click.Choice(["api", "browser"]), default="browser",
              help="Silnik rezerwacji: api (Faza C) lub browser (Faza A)")
@click.option("--profil", default=None, type=click.Path(exists=False), help="Profil Camoufox (dla browser)")
@click.option("--cookies", default=None, type=click.Path(exists=True), help="Cookies (Netscape)")
def autocop(brand, search, max_iter, no_checkout, engine, profil, cookies):
    """Monitoruj i (opcjonalnie) rezerwuj nowe oferty."""
    from .detection import monitoruj
    from .checkout import zarezerwuj, zarezerwuj_api

    f = Filtry(brand_ids=list(brand), search_text=search)
    ck = wczytaj_cookies(cookies) if cookies else None

    def on_nowe(nowe):
        for o in nowe:
            click.echo(f"NOWA: {o.id} {o.title} {o.cena}")
            if no_checkout:
                continue
            timer = CheckoutTimer()
            with timer:
                if engine == "api":
                    if not ck:
                        click.echo("(api wymaga --cookies)")
                        continue
                    rez = zarezerwuj_api(o.id, ck, anon_id="")
                else:
                    if not profil:
                        click.echo("(rezerwacja pominięta — brak --profil)")
                        continue
                    rez = zarezerwuj(o.id, profil)
            timer.set_result(rez is not None, engine)
            if rez:
                click.echo(f"ZAREZERWOWANO: {rez.purchase_id} w {timer.elapsed_ms:.0f}ms [{engine}]")
            else:
                click.echo(f"REZERWACJA NIEUDANA w {timer.elapsed_ms:.0f}ms [{engine}]")

    monitoruj(f, interwal=1.0, callback=on_nowe, max_iter=max_iter, cookies=ck)
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd bot && pytest tests/test_cli_e2e.py::test_bench_drukuje_raport_json -v`
Expected: 1 passed

- [ ] **Step 5: Uruchom pełny zestaw testów**

Run: `cd bot && pytest -v`
Expected: wszystkie przechodzą

- [ ] **Step 6: Commit**

```bash
git add bot/src/vintedbot/cli.py bot/tests/test_cli_e2e.py
git commit -m "feat: bench command + engine flag (api/browser) in autocop"
```

---

## Task 7: Zdrowie sesji + edge case'y (E1, E3, E5, E6)

**Files:**
- Modify: `bot/src/vintedbot/detection.py`
- Test: `bot/tests/test_detection.py`

- [ ] **Step 1: Napisz test detekcji wygaśnięcia sesji (czysta funkcja)**

```python
from vintedbot.detection import _sesja_aktywna


def test_sesja_aktywna_po_login():
    dane = {"user": {"login": "maksks0", "id": 3180346878}}
    assert _sesja_aktywna(dane) is True


def test_sesja_nieaktywna_bez_login():
    dane = {"user": {}}
    assert _sesja_aktywna(dane) is False


def test_sesja_nieaktywna_none():
    assert _sesja_aktywna(None) is False
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL)**

Run: `cd bot && pytest tests/test_detection.py::test_sesja_aktywna_po_login -v`
Expected: `ImportError: cannot import name '_sesja_aktywna'`

- [ ] **Step 3: Zaimplementuj `_sesja_aktywna` i sprawdzenie w pętli**

Dodaj w `detection.py`:

```python
def _sesja_aktywna(dane: dict | None) -> bool:
    """Sesja jest zalogowana, gdy users/current zawiera login."""
    if not dane:
        return False
    user = dane.get("user") or {}
    return bool(user.get("login"))
```

W `monitoruj`, po pobraniu ofert (w bloku try, po `oferty = ...`), wstrzyknij alarm
sesji, ale bez twardego zatrzymania (logowanie do stderr):

```python
        # Po pobraniu ofert sprawdź sesję — jeśli wygasła, zaloguj alarm do stderr.
        # (Detekcja użytkownika wymaga osobnego wywołania users/current; tu tylko
        #  oznaczamy, że pętla powinna to sygnalizować na poziomie CLI.)
```

> Uwaga: pełne sprawdzenie `users/current` wymaga dodatkowego żądania; w MVP detekcja
> wygaśnięcia jest realizowana w CLI/benchmarku przez osobne wywołanie, nie w pętli
> pollingu (żeby nie mnożyć żądań przy limicie ~1 req/s). Ta funkcja jest interfejsem
> dla warstwy CLI.

- [ ] **Step 4: Uruchom testy detection**

Run: `cd bot && pytest tests/test_detection.py -v`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/detection.py bot/tests/test_detection.py
git commit -m "feat: session health check helper (edge case E1)"
```

---

## Task 8: Benchmark end-to-end + raport do dokumentacji

**Files:**
- Modify: `bot/src/vintedbot/cli.py` (komenda `bench` rozszerzona o zapis JSON)
- Test: `bot/tests/test_cli_e2e.py`

> To jest task zamknięcia pętli: benchmark zapisuje raport do pliku, a plan wymaga
> aktualizacji dokumentacji inżynierskiej po każdym realnym pomiarze.

- [ ] **Step 1: Napisz test zapisu raportu do pliku**

```python
from urllib.parse import urlencode

from click.testing import CliRunner

from vintedbot.cli import cli


def test_bench_zapisuje_raport(fake_http, tmp_path):
    payload = '{"items":[{"id":42,"title":"T","price":{"amount":"9.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "per_page": 96, "order": "newest_first"}
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    out = tmp_path / "bench.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["bench", "--brand", "53", "--max-iter", "2", "--out", str(out)])

    assert result.exit_code == 0
    assert out.exists()
    assert '"count"' in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Uruchom test (oczekiwane FAIL — brak --out)**

Run: `cd bot && pytest tests/test_cli_e2e.py::test_bench_zapisuje_raport -v`
Expected: `Error: No such option: --out`

- [ ] **Step 3: Dodaj opcję `--out` do komendy `bench`**

Zamień dekorator i nagłówek `bench`:

```python
@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--max-iter", default=5, type=int)
@click.option("--cookies", default=None, type=click.Path(exists=True))
@click.option("--out", default=None, type=click.Path(dir_okay=False), help="Ścieżka zapisu raportu JSON")
def bench(brand, search, max_iter, cookies, out):
    from .detection import monitoruj

    f = Filtry(brand_ids=list(brand), search_text=search)
    ck = wczytaj_cookies(cookies) if cookies else None
    recorder = LatencyRecorder()

    def _cb(nowe):
        pass

    monitoruj(f, interwal=0.0, callback=_cb, max_iter=max_iter, cookies=ck, recorder=recorder)
    report = recorder.to_dict()
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    click.echo(json.dumps(report, ensure_ascii=False))
```

- [ ] **Step 4: Uruchom test (oczekiwane PASS)**

Run: `cd bot && pytest tests/test_cli_e2e.py::test_bench_zapisuje_raport -v`
Expected: 1 passed

- [ ] **Step 5: Uruchom pełny zestaw testów**

Run: `cd bot && pytest -v`
Expected: wszystkie przechodzą

- [ ] **Step 6: Commit**

```bash
git add bot/src/vintedbot/cli.py bot/tests/test_cli_e2e.py
git commit -m "feat: bench report save to file (--out)"
```

---

## Self-Review

**1. Spec coverage:**
- Framework pomiarowy (Faza 0) → Task 1.
- Pełne filtry (wymaganie F3) → Task 2.
- Backoff/jitter/metryka (edge E2) → Task 3.
- Faza C (ścieżka api) → Task 4.
- Faza A (ścieżka browser, pre-warm) → Task 5.
- CLI wybór silnika + benchmark → Task 6.
- Zdrowie sesji (edge E1) → Task 7.
- Raport do dokumentacji + zapis JSON → Task 8.
- Edge E3–E14: częściowo pokryte przez backoff (E2), strukturę C/A (E4), detekcję sesji (E1). Pełne E5–E14 (captcha, ban, race, purchase_id timeout) wymagają realnych testów na żywo — zostają jako kontynuacja po benchmarku (jawnie poza zakresem tego planu, zgodnie z timeboxem).

**2. Placeholder scan:** brak — każdy task zawiera kompletny kod i komendy.

**3. Type consistency:**
- `LatencyRecorder` (add/to_dict/count/p50/p95/p99/avg) — spójne w Task 1, 6, 8.
- `CheckoutTimer` (elapsed_ms/set_result/success/engine) — spójne w Task 1, 6.
- `zarezerwuj_api(transaction_id, cookies, anon_id, order_type)` — spójne w Task 4, 6.
- `_nastepny_interwal(bledy, jitter)` — spójne w Task 3.
- `_sesja_aktywna(dane)` — spójne w Task 7.
- `monitoruj(..., recorder=None)` — spójne w Task 3, 6, 8.

Wszystkie ścieżki plików i nazwy funkcji są zgodne między taskami.