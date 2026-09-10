# Vinted Bot Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać długo żyjący daemon, który podtrzymuje sesję (Camoufox) i automatycznie rezerwuje pasujące oferty (curl_cffi), znając i raportując swój stan.

**Architecture:** Jeden proces, dwa wątki: pętla refresh (Camoufox → eksport cookies) i pętla zakupowa (curl_cffi → rezerwacja). Współdzielony `SessionState` (maszyna stanów) chroniony lockiem. Zakup gated stanem `READY`.

**Tech Stack:** Python 3.11, `click`, `curl_cffi`, `camoufox`, `pydantic`, `pytest`, `threading`.

---

## Ważne fakty domenowe (nie zmieniać)

- Monitoring + zakup = `curl_cffi`, impersonacja `"firefox135"` (już w `detection.py`/`checkout.py`).
- Podtrzymywanie sesji = Camoufox na trwałym profilu `profil_firefox_135`; frontend sam odświeża `refresh_token_web` przy załadowaniu strony.
- Walidacja zalogowania: `GET https://www.vinted.pl/api/v2/users/current` → 200 + `user.login`.
- Zakup = `zrealizuj_zakup(item_id, seller_id, konto, proba_payment=...)` (istnieje w `checkout.py`).
- Pobieranie ofert = `pobierz_oferty(filtry, cookies=cookies)` (istnieje w `detection.py`).
- `Oferta` ma pola `id`, `seller_id`, `title`, `cena`. `seller_id` może być `None`.

---

## Struktura plików

```
bot/
├── pyproject.toml               # MODIFY: przywrócić camoufox
├── src/vintedbot/
│   ├── session_state.py         # NOWY: SessionState + walidacja users/current
│   ├── refresh.py               # NOWY: pętla refresh Camoufox
│   ├── daemon.py                # NOWY: spina pętle (wątki + graceful shutdown)
│   └── cli.py                   # MODIFY: komenda `daemon`
└── tests/
    ├── test_session_state.py    # NOWY
    ├── test_refresh.py          # NOWY
    ├── test_daemon.py           # NOWY
    └── test_cli_e2e.py          # MODIFY: test komendy daemon
```

---

### Task 1: Przywróć zależność `camoufox`

**Files:**
- Modify: `bot/pyproject.toml`

- [ ] **Step 1: Dodaj `camoufox` z powrotem do `dependencies`**

```toml
dependencies = [
    "click>=8.1",
    "curl_cffi>=0.7",
    "camoufox>=0.4",
    "pydantic>=2.0",
]
```

- [ ] **Step 2: Zweryfikuj instalację (best effort, nie blokuje)**

Run: `cd bot && python -m pip install -e ".[dev]" 2>&1 | Select-Object -Last 5`
Expected: instalacja kończy się bez błędu (lub camoufox już zainstalowany).

- [ ] **Step 3: Commit**

```bash
git add bot/pyproject.toml
git commit -m "chore: przywróć camoufox (pętla refresh daemona)"
```

---

### Task 2: `session_state.py` — maszyna stanów sesji

**Files:**
- Create: `bot/src/vintedbot/session_state.py`
- Test: `bot/tests/test_session_state.py`

- [ ] **Step 1: Napisz testy**

```python
# bot/tests/test_session_state.py
import json

from vintedbot.session_state import SessionState, SessionStatus


def test_start_unknown():
    s = SessionState()
    assert s.status == SessionStatus.UNKNOWN
    assert s.cookies == {}
    assert s.reservations == 0


def test_set_status_i_snapshot():
    s = SessionState()
    s.set_status(SessionStatus.READY)
    snap = s.snapshot()
    assert snap["status"] == "ready"
    assert snap["reservations"] == 0


def test_record_reservation():
    s = SessionState()
    s.record_reservation()
    s.record_reservation()
    assert s.reservations == 2


def test_record_error():
    s = SessionState()
    s.record_error("boom")
    assert s.errors == ["boom"]


def test_is_ready_true(monkeypatch):
    import vintedbot.session_state as ss

    class R:
        status_code = 200
        content = json.dumps({"user": {"login": "maksks0", "id": 1}}).encode()

    monkeypatch.setattr(ss.creq, "get", lambda url, **kw: R())
    s = SessionState()
    s.cookies = {"a": "1"}
    assert s.is_ready() is True


def test_is_ready_false_401(monkeypatch):
    import vintedbot.session_state as ss

    class R:
        status_code = 401
        content = b"{}"

    monkeypatch.setattr(ss.creq, "get", lambda url, **kw: R())
    s = SessionState()
    s.cookies = {"a": "1"}
    assert s.is_ready() is False


def test_is_ready_false_anon(monkeypatch):
    import vintedbot.session_state as ss

    class R:
        status_code = 200
        content = json.dumps({"user": {}}).encode()

    monkeypatch.setattr(ss.creq, "get", lambda url, **kw: R())
    s = SessionState()
    s.cookies = {"a": "1"}
    assert s.is_ready() is False
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && python -m pytest tests/test_session_state.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'vintedbot.session_state'`

- [ ] **Step 3: Zaimplementuj**

```python
"""Maszyna stanów sesji Vinted + walidacja zalogowania przez curl_cffi."""
import json
import threading
import time
from enum import Enum

from curl_cffi import requests as creq

from .config import IMPERSONATE

USERS_CURRENT_URL = "https://www.vinted.pl/api/v2/users/current"


class SessionStatus(Enum):
    UNKNOWN = "unknown"
    READY = "ready"
    REFRESHING = "refreshing"
    NEEDS_LOGIN = "needs_login"


class SessionState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.status = SessionStatus.UNKNOWN
        self.cookies: dict[str, str] = {}
        self.login: str | None = None
        self.last_refresh_ts = 0.0
        self.reservations = 0
        self.errors: list[str] = []

    def set_status(self, status: SessionStatus) -> None:
        with self._lock:
            self.status = status

    def record_reservation(self) -> None:
        with self._lock:
            self.reservations += 1

    def record_error(self, msg: str) -> None:
        with self._lock:
            self.errors.append(msg)

    def set_cookies(self, cookies: dict[str, str], login: str | None) -> None:
        with self._lock:
            self.cookies = cookies
            self.login = login
            self.last_refresh_ts = time.time()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status": self.status.value,
                "login": self.login,
                "reservations": self.reservations,
                "errors": list(self.errors),
                "cookies_count": len(self.cookies),
            }

    def is_ready(self) -> bool:
        with self._lock:
            cookies = dict(self.cookies)
        if not cookies:
            return False
        r = creq.get(USERS_CURRENT_URL, headers={"Accept": "application/json"},
                     cookies=cookies, impersonate=IMPERSONATE, timeout=20)
        if r.status_code != 200:
            return False
        data = json.loads(r.content)
        user = data.get("user") or {}
        login = user.get("login") or data.get("login")
        if login:
            with self._lock:
                self.login = login
            return True
        return False
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && python -m pytest tests/test_session_state.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/session_state.py bot/tests/test_session_state.py
git commit -m "feat: SessionState (maszyna stanów + walidacja users/current)"
```

---

### Task 3: `refresh.py` — pętla refresh Camoufox

**Files:**
- Create: `bot/src/vintedbot/refresh.py`
- Test: `bot/tests/test_refresh.py`

- [ ] **Step 1: Napisz testy (mock Camoufox)**

```python
# bot/tests/test_refresh.py
from vintedbot.refresh import RefreshLoop, _eksportuj_cookies
from vintedbot.session_state import SessionState, SessionStatus


def test_eksportuj_cookies_z_listy():
    raw = [
        {"name": "a", "value": "1", "domain": ".vinted.pl", "path": "/",
         "expires": -1, "httpOnly": False, "secure": False, "sameSite": "Lax"},
        {"name": "b", "value": "2", "domain": ".vinted.pl", "path": "/",
         "expires": -1, "httpOnly": True, "secure": True, "sameSite": "Lax"},
    ]
    assert _eksportuj_cookies(raw) == {"a": "1", "b": "2"}


def test_run_once_ready(monkeypatch):
    class FakePage:
        def goto(self, url, **kw):
            return None

    class FakeCtx:
        def new_page(self):
            return FakePage()
        def cookies(self):
            return [{"name": "access_token_web", "value": "TOK", "domain": ".vinted.pl",
                     "path": "/", "expires": -1, "httpOnly": True, "secure": True, "sameSite": "Lax"}]

    class FakeCamoufox:
        def __init__(self, **kw):
            pass
        def __enter__(self):
            return FakeCtx()
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("vintedbot.refresh.Camoufox", FakeCamoufox)
    monkeypatch.setattr("vintedbot.refresh._czy_zalogowany", lambda page: ("maksks0", 1))

    state = SessionState()
    loop = RefreshLoop(profile="profil", interval_min=4)
    ok = loop.run_once(state)

    assert ok is True
    assert state.status == SessionStatus.READY
    assert state.cookies["access_token_web"] == "TOK"
    assert state.login == "maksks0"


def test_run_once_needs_login(monkeypatch):
    class FakePage:
        def goto(self, url, **kw):
            return None

    class FakeCtx:
        def new_page(self):
            return FakePage()
        def cookies(self):
            return []

    class FakeCamoufox:
        def __init__(self, **kw):
            pass
        def __enter__(self):
            return FakeCtx()
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("vintedbot.refresh.Camoufox", FakeCamoufox)
    monkeypatch.setattr("vintedbot.refresh._czy_zalogowany", lambda page: (None, None))

    state = SessionState()
    loop = RefreshLoop(profile="profil", interval_min=4)
    ok = loop.run_once(state)

    assert ok is False
    assert state.status == SessionStatus.NEEDS_LOGIN
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && python -m pytest tests/test_refresh.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'vintedbot.refresh'`

- [ ] **Step 3: Zaimplementuj**

```python
"""Pętla refresh sesji przez Camoufox (frontend-driven token refresh)."""
import json
import threading
import time

from camoufox import Camoufox

from .session_state import SessionState, SessionStatus

LOGIN_URL = "https://www.vinted.pl/"
TIMEOUT_S = 90


def _eksportuj_cookies(raw_cookies) -> dict[str, str]:
    return {c.get("name", ""): c.get("value", "") for c in raw_cookies if c.get("name")}


def _czy_zalogowany(page):
    """Zwraca (login, id) z /users/current w kontekście przeglądarki lub (None, None)."""
    data = page.evaluate(
        """async () => {
            const r = await fetch('/api/v2/users/current', {headers: {'Accept': 'application/json'}});
            return JSON.stringify({status: r.status, body: await r.text()});
        }"""
    )
    obj = json.loads(data)
    if obj.get("status") != 200:
        return (None, None)
    body = json.loads(obj.get("body", "{}"))
    user = body.get("user") or {}
    login = user.get("login") or body.get("login")
    uid = user.get("id") or body.get("id")
    if login and uid:
        return (login, uid)
    return (None, None)


class RefreshLoop:
    def __init__(self, profile: str, interval_min: int = 4) -> None:
        self.profile = profile
        self.interval = interval_min * 60

    def run_once(self, state: SessionState) -> bool:
        state.set_status(SessionStatus.REFRESHING)
        try:
            with Camoufox(
                persistent_context=True, headless=True,
                user_data_dir=self.profile, os="windows",
                fingerprint_preset=True, humanize=True,
            ) as ctx:
                page = ctx.new_page()
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
                start = time.time()
                account = (None, None)
                while time.time() - start < TIMEOUT_S:
                    account = _czy_zalogowany(page)
                    if account[0]:
                        break
                    time.sleep(2)
                if not account[0]:
                    state.set_status(SessionStatus.NEEDS_LOGIN)
                    return False
                cookies = _eksportuj_cookies(ctx.cookies())
                state.set_cookies(cookies, account[0])
                state.set_status(SessionStatus.READY)
                return True
        except Exception as exc:
            state.record_error(f"refresh error: {exc}")
            state.set_status(SessionStatus.NEEDS_LOGIN)
            return False

    def run(self, state: SessionState, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.run_once(state)
            stop_event.wait(self.interval)
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && python -m pytest tests/test_refresh.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/refresh.py bot/tests/test_refresh.py
git commit -m "feat: RefreshLoop (Camoufox) — podtrzymywanie sesji"
```

---

### Task 4: `daemon.py` — spina pętle

**Files:**
- Create: `bot/src/vintedbot/daemon.py`
- Test: `bot/tests/test_daemon.py`

- [ ] **Step 1: Napisz testy (mock pętli i zakupu)**

```python
# bot/tests/test_daemon.py
import threading

from vintedbot.daemon import PurchaseLoop
from vintedbot.session_state import SessionState, SessionStatus
from vintedbot.models import Filtry, Oferta


def _oferta(id, seller):
    return Oferta.model_validate({"id": id, "title": "A",
                                  "price": {"amount": "5", "currency_code": "PLN"},
                                  "user": {"id": seller}})


def test_purchase_loop_nie_rezerwuje_gdy_nie_ready(monkeypatch):
    state = SessionState()
    state.status = SessionStatus.REFRESHING

    calls = []

    def fake_zrealizuj(*a, **kw):
        calls.append(a)
        return None

    monkeypatch.setattr("vintedbot.daemon.zrealizuj_zakup", fake_zrealizuj)

    loop = PurchaseLoop(state=state, filtry=Filtry(), proba_payment=False)
    loop._kup(_oferta(1, 10))

    assert calls == []


def test_purchase_loop_rezerwuje_gdy_ready(monkeypatch):
    state = SessionState()
    state.status = SessionStatus.READY
    state.cookies = {"a": "1"}

    calls = []

    def fake_zrealizuj(*a, **kw):
        calls.append(a)
        return None

    monkeypatch.setattr("vintedbot.daemon.zrealizuj_zakup", fake_zrealizuj)
    monkeypatch.setattr("vintedbot.daemon.KonfiguracjaKonta", lambda cookies: type("K", (), {"cookies": cookies})())

    loop = PurchaseLoop(state=state, filtry=Filtry(), proba_payment=False)
    loop._kup(_oferta(1, 10))

    assert len(calls) == 1
    assert calls[0][0] == 1  # item_id
    assert calls[0][1] == 10  # seller_id
    assert state.reservations == 1


def test_purchase_loop_pomija_brak_seller(monkeypatch):
    state = SessionState()
    state.status = SessionStatus.READY
    state.cookies = {"a": "1"}

    calls = []

    def fake_zrealizuj(*a, **kw):
        calls.append(a)
        return None

    monkeypatch.setattr("vintedbot.daemon.zrealizuj_zakup", fake_zrealizuj)
    monkeypatch.setattr("vintedbot.daemon.KonfiguracjaKonta", lambda cookies: type("K", (), {"cookies": cookies})())

    loop = PurchaseLoop(state=state, filtry=Filtry(), proba_payment=False)
    o = Oferta.model_validate({"id": 2, "title": "B",
                               "price": {"amount": "5", "currency_code": "PLN"}})
    loop._kup(o)

    assert calls == []
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && python -m pytest tests/test_daemon.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'vintedbot.daemon'`

- [ ] **Step 3: Zaimplementuj**

```python
"""Daemon: spina pętlę refresh (Camoufox) i pętlę zakupową (curl_cffi)."""
import signal
import threading
import time

from .checkout import zrealizuj_zakup
from .models import Filtry, KonfiguracjaKonta
from .refresh import RefreshLoop
from .session_state import SessionState, SessionStatus


class PurchaseLoop:
    def __init__(self, state: SessionState, filtry: Filtry, proba_payment: bool) -> None:
        self.state = state
        self.filtry = filtry
        self.proba_payment = proba_payment

    def _kup(self, oferta) -> None:
        if self.state.status != SessionStatus.READY:
            return
        if oferta.seller_id is None:
            return
        konto = KonfiguracjaKonta(cookies=self.state.cookies)
        zrealizuj_zakup(oferta.id, oferta.seller_id, konto, proba_payment=self.proba_payment)
        self.state.record_reservation()

    def run(self, stop_event: threading.Event) -> None:
        from .detection import monitoruj

        def _cb(nowe):
            for o in nowe:
                self._kup(o)

        while not stop_event.is_set():
            if self.state.status == SessionStatus.READY:
                try:
                    monitoruj(self.filtry, interwal=1.0, callback=_cb,
                              max_iter=1, cookies=self.state.cookies)
                except Exception as exc:
                    self.state.record_error(f"purchase loop error: {exc}")
                    self.state.set_status(SessionStatus.REFRESHING)
            stop_event.wait(1.0)


def run_daemon(profile, filtry, proba_payment, refresh_interval_min, cookies_path) -> None:
    state = SessionState()
    # wstępne cookies z pliku (jeśli świeże, od razu READY po walidacji)
    from .config import wczytaj_cookies
    try:
        state.cookies = wczytaj_cookies(cookies_path)
        if state.is_ready():
            state.set_status(SessionStatus.READY)
    except Exception:
        pass

    stop = threading.Event()

    refresh = RefreshLoop(profile=profile, interval_min=refresh_interval_min)
    t_refresh = threading.Thread(target=refresh.run, args=(state, stop), daemon=True)

    purchase = PurchaseLoop(state=state, filtry=filtry, proba_payment=proba_payment)
    t_purchase = threading.Thread(target=purchase.run, args=(stop,), daemon=True)

    def _shutdown(signum, frame):
        print(f"[daemon] sygnał {signum}, zamykam...", flush=True)
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    t_refresh.start()
    t_purchase.start()

    while not stop.is_set():
        print(f"[daemon] stan: {state.snapshot()}", flush=True)
        stop.wait(10.0)

    print("[daemon] zakończono.", flush=True)
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && python -m pytest tests/test_daemon.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/daemon.py bot/tests/test_daemon.py
git commit -m "feat: Daemon (pętla refresh + pętla zakupowa z gatingiem stanu)"
```

---

### Task 5: `cli.py` — komenda `daemon`

**Files:**
- Modify: `bot/src/vintedbot/cli.py`
- Test: `bot/tests/test_cli_e2e.py`

- [ ] **Step 1: Napisz test komendy**

Dopisz do `bot/tests/test_cli_e2e.py`:

```python
def test_cli_daemon_rejestruje_sie():
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "--payment" in result.output
    assert "--interval" in result.output
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && python -m pytest tests/test_cli_e2e.py::test_cli_daemon_rejestruje_sie -q`
Expected: FAIL (brak komendy `daemon`)

- [ ] **Step 3: Dodaj komendę `daemon` do `cli.py`**

Dodaj na końcu pliku (przed `if __name__ == "__main__":`):

```python
@cli.command()
@click.option("--brand", multiple=True, type=int, help="ID marki (powtarzalny)")
@click.option("--search", default=None, help="Słowa kluczowe")
@click.option("--cookies", required=True, type=click.Path(exists=True), help="Cookies (JSON lub Netscape)")
@click.option("--profil", required=True, type=click.Path(exists=False), help="Katalog profilu Camoufox")
@click.option("--interval", default=4, type=int, help="Interwał refresh sesji (minuty)")
@click.option("--payment", is_flag=True, help="Próbuj dojść do kroku payment po rezerwacji")
def daemon(brand, search, cookies, profil, interval, payment):
    """Uruchom daemon: podtrzymuj sesję i automatycznie rezerwuj pasujące oferty."""
    from .daemon import run_daemon
    from .models import Filtry

    f = Filtry(brand_ids=list(brand), search_text=search)
    run_daemon(profile=profil, filtry=f, proba_payment=payment,
               refresh_interval_min=interval, cookies_path=cookies)
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && python -m pytest tests/test_cli_e2e.py -q`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/cli.py bot/tests/test_cli_e2e.py
git commit -m "feat: komenda daemon (podtrzymywanie sesji + auto-zakup)"
```

---

### Task 6: Pełny przebieg testów

- [ ] **Step 1: Uruchom całą suitę**

Run: `cd bot && python -m pytest -q`
Expected: wszystkie przechodzą, 0 błędów (wcześniejsze 35 + nowe ~19 = ~54).

- [ ] **Step 2: Sprawdź diagnostykę IDE**

Otwórz `session_state.py`, `refresh.py`, `daemon.py` i zweryfikuj `GetDiagnostics` = brak błędów.

- [ ] **Step 3: Commit (luźne pliki, jeśli są)**

```bash
git add bot/
git commit -m "test: zielona suita po dodaniu daemona"
```

---

## Self-Review

**1. Spec coverage:**
- „podtrzymuje sesję" → Task 3 (`refresh.py`).
- „monitoruje + rezerwuje" → Task 4 (`daemon.py` → `PurchaseLoop`).
- „zna i raportuje stan" → Task 2 (`SessionState` + snapshot w `run_daemon`).
- „płatność tylko przy --payment" → Task 4/5 (`proba_payment`).
- „maszyna stanów READY/REFRESHING/NEEDS_LOGIN" → Task 2.
- „camoufox przywrócone" → Task 1.
- „gating zakupem w READY" → Task 4 (test `_kup` nie rezerwuje gdy nie ready).

**2. Placeholder scan:** brak TBD/TODO; każdy krok ma pełny kod.

**3. Type consistency:** `SessionState`, `SessionStatus`, `RefreshLoop`, `PurchaseLoop`,
`run_daemon(profile, filtry, proba_payment, refresh_interval_min, cookies_path)` — nazwy spójne
między taskami. `_kup(oferta)` używa `oferta.id`, `oferta.seller_id` (z `models.py`).
`run_daemon` używa `wczytaj_cookies` z `config` (istnieje). `KonfiguracjaKonta(cookies=...)`
z `models` (istnieje).

**Uwaga wykonawcza:** w Task 4 test `_kup` mockuje `KonfiguracjaKonta` przez atrybut
`vintedbot.daemon.KonfiguracjaKonta` — import w `daemon.py` musi być `from .models import
KonfiguracjaKonta` (jest). W `run_daemon` sygnały `signal.signal` są wywoływane tylko w wątku
głównym — zgodnie z Python; testy nie wywołują `run_daemon` (tylko `PurchaseLoop`).