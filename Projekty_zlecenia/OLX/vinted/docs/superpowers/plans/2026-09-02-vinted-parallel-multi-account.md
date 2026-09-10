# Vinted Bot — Parallel Multi-Account (tryb wyścigu o przedmiot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Umożliwić daemonowi równoległy zakup tego samego przedmiotu na N kontach (tryb Parallel), aby wygrać wyścig o ofertę — dokładnie to, co kops.gg trzyma za paywallem Pro.

**Architecture:** Rozszerzamy `run_daemon`, by przyjmował listę kont (każde = plik cookies + profil Camoufox). Dla każdego konta startuje własny `RefreshLoop` (podtrzymywanie sesji) i własny `PurchaseLoop` (polling + checkout). Każde konto niezależnie wykrywa nową ofertę i próbuje ją zarezerwować; pierwsze konto, które dostanie `build=200`, wygrywa — pozostałe dostaną naturalnie 404/409 (przedmiot już zajęty). Bez globalnego locka: istniejące per-checkout executory (FIX Issue 2) już gwarantują brak blokowania między wątkami.

**Tech Stack:** Python 3.11, `click`, `curl_cffi`, `camoufox`, `pydantic`, `pytest`, `threading`.

---

## Ważne fakty domenowe (nie zmieniać)

- `run_daemon(profile, filtry, proba_payment, refresh_interval_min, cookies_path, timing, screenshot, dry_run)` — [daemon.py:111](f:/PROJEKTY/vinted/bot/src/vintedbot/daemon.py#L111). Obecnie przyjmuje JEDNO konto.
- `PurchaseLoop(state, filtry, proba_payment, timing, screenshot, profil, dry_run)` — [daemon.py:25](f:/PROJEKTY/vinted/bot/src/vintedbot/daemon.py#L25). Ma własną kolejkę i worker.
- `RefreshLoop(profile, interval_min)` — [refresh.py:103](f:/PROJEKTY/vinted/bot/src/vintedbot/refresh.py#L103). Podtrzymuje sesję przez Camoufox.
- `SessionState` — [session_state.py:28](f:/PROJEKTY/vinted/bot/src/vintedbot/session_state.py#L28). Trzyma cookies/login/user_id per konto.
- `zrealizuj_zakup` NIE jest thread-safe względem tej samej sesji, ale każde konto ma własną sesję (`pobierz_sesje(konto)` kluczowane `anon_id`), więc N niezależnych kont = N niezależnych sesji = bezpieczne równolegle.
- Checkout pojedynczego konta to ~3.3–3.5s (limit sieci Vinted). Parallel NIE skraca pojedynczego checkoutu — zwiększa szansę wygranej w wyścigu.
- Rate-limit Vinted ~0.83 req/s na IP. Parallel na N kontach z JEDNEGO IP zwiększa ryzyko 429/bana. Wymagane: 1 IP = 1 konto (AGENTS.md) + proxy rezydencjalne w produkcji. To plan kodu, nie konfiguracji proxy.

---

## Struktura plików

```
bot/
├── src/vintedbot/
│   ├── daemon.py                # MODIFY: lista kont, N PurchaseLoop + N RefreshLoop
│   └── cli.py                   # MODIFY: --cookies/--profil jako multiple (pary)
└── tests/
    ├── test_daemon.py           # MODIFY: testy multi-konto
    └── test_cli_e2e.py          # MODIFY: test komendy z wieloma kontami
```

---

### Task 1: Wprowadź listę kont w `daemon.py`

**Files:**
- Modify: `bot/src/vintedbot/daemon.py:111-155`

- [ ] **Step 1: Napisz test — `run_daemon` przyjmuje listę kont i startuje N pętli**

```python
# bot/tests/test_daemon.py (dopisz na końcu)
import threading

def test_run_daemon_startuje_n_kont(monkeypatch):
    from vintedbot import daemon as d

    started_refresh = []
    started_purchase = []

    class FakeRefreshLoop:
        def __init__(self, profile, interval_min):
            self.profile = profile
            self.interval_min = interval_min
        def run(self, state, stop):
            started_refresh.append(self.profile)

    class FakePurchaseLoop:
        def __init__(self, state, filtry, proba_payment, timing, screenshot, profil, dry_run):
            self.profil = profil
        def run(self, stop):
            started_purchase.append(self.profil)

    monkeypatch.setattr(d, "RefreshLoop", FakeRefreshLoop)
    monkeypatch.setattr(d, "PurchaseLoop", FakePurchaseLoop)
    monkeypatch.setattr(d, "SessionState", lambda: type("S", (), {"cookies": {}, "is_ready": lambda: False, "set_status": lambda s: None})())
    # wczytaj_cookies zwraca puste — od razu pomija prewarm
    monkeypatch.setattr("vintedbot.config.wczytaj_cookies", lambda p: {})

    konta = [
        {"cookies_path": "/tmp/c1.txt", "profil": "/tmp/p1"},
        {"cookies_path": "/tmp/c2.txt", "profil": "/tmp/p2"},
    ]

    d.run_daemon_multi(konta, filtry=d.Filtry(), proba_payment=False,
                       refresh_interval_min=4, timing=False, screenshot=False,
                       dry_run=True)

    assert len(started_refresh) == 2
    assert len(started_purchase) == 2
    assert {p for p in started_purchase} == {"/tmp/p1", "/tmp/p2"}
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && python -m pytest tests/test_daemon.py::test_run_daemon_startuje_n_kont -q`
Expected: FAIL `AttributeError: module 'vintedbot.daemon' has no attribute 'run_daemon_multi'`

- [ ] **Step 3: Zaimplementuj `run_daemon_multi` + refactor `run_daemon`**

Dodaj na końcu [daemon.py](f:/PROJEKTY/vinted/bot/src/vintedbot/daemon.py) (przed niczym — to koniec pliku). Wstaw też import `Filtry` u góry, jeśli go nie ma:

```python
def run_daemon_multi(konta, filtry, proba_payment, refresh_interval_min,
                     timing=True, screenshot=False, dry_run=False) -> None:
    """Parallel multi-konto: dla każdego konta osobny RefreshLoop + PurchaseLoop.

    konta: lista dict z kluczami `cookies_path` (str) i `profil` (str).
    Każde konto rywalizuje o tę samą ofertę niezależnie; pierwsze build=200 wygrywa.
    """
    stop = threading.Event()
    threads = []

    for k in konta:
        state = SessionState()
        from .config import wczytaj_cookies
        try:
            state.cookies = wczytaj_cookies(k["cookies_path"])
            if state.is_ready():
                state.set_status(SessionStatus.READY)
        except Exception:
            pass

        if state.status == SessionStatus.READY:
            try:
                prewarm_sesje(KonfiguracjaKonta(cookies=state.cookies))
            except Exception as exc:
                print(f"[daemon] prewarm sesji nie powiódł się: {exc}", flush=True)

        refresh = RefreshLoop(profile=k["profil"], interval_min=refresh_interval_min)
        purchase = PurchaseLoop(state=state, filtry=filtry, proba_payment=proba_payment,
                                timing=timing, screenshot=screenshot, profil=k["profil"],
                                dry_run=dry_run)

        t_refresh = threading.Thread(target=refresh.run, args=(state, stop), daemon=True,
                                     name=f"refresh-{k['profil']}")
        t_purchase = threading.Thread(target=purchase.run, args=(stop,), daemon=True,
                                      name=f"purchase-{k['profil']}")
        threads.extend([t_refresh, t_purchase])
        t_refresh.start()
        t_purchase.start()

    def _shutdown(signum, frame):
        print(f"[daemon] sygnał {signum}, zamykam...", flush=True)
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while not stop.is_set():
        stop.wait(10.0)

    print("[daemon] zakończono (multi-konto).", flush=True)
```

Następnie przepisz `run_daemon`, by delegował do `run_daemon_multi` (zachowujemy stare wywołanie jako pojedyncze konto):

```python
def run_daemon(profile, filtry, proba_payment, refresh_interval_min, cookies_path,
               timing: bool = True, screenshot: bool = False, dry_run: bool = False) -> None:
    """Backward-compat: pojedyncze konto deleguje do run_daemon_multi."""
    run_daemon_multi(
        [{"cookies_path": cookies_path, "profil": profile}],
        filtry=filtry, proba_payment=proba_payment,
        refresh_interval_min=refresh_interval_min,
        timing=timing, screenshot=screenshot, dry_run=dry_run,
    )
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && python -m pytest tests/test_daemon.py -q`
Expected: wszystkie przechodzą (stare 3 + nowy 1 = 4)

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/daemon.py bot/tests/test_daemon.py
git commit -m "feat(daemon): run_daemon_multi — parallel multi-konto"
```

---

### Task 2: CLI `daemon` — akceptuj wiele kont

**Files:**
- Modify: `bot/src/vintedbot/cli.py:158-166`
- Test: `bot/tests/test_cli_e2e.py`

- [ ] **Step 1: Napisz test — komenda `daemon` przyjmuje powtarzalne `--cookies`/`--profil`**

Dopisz do [test_cli_e2e.py](f:/PROJEKTY/vinted/bot/tests/test_cli_e2e.py):

```python
def test_cli_daemon_multi_konta_help():
    from click.testing import CliRunner
    from vintedbot.cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "multiple" in result.output or "--cookies" in result.output
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `cd bot && python -m pytest tests/test_cli_e2e.py::test_cli_daemon_multi_konta_help -q`
Expected: FAIL (bieżąca opcja `--cookies` nie jest `multiple=True`) — albo test przechodzi, wtedy przejdź do Step 3 bez zmiany oczekiwań.

- [ ] **Step 3: Zmień `--cookies` i `--profil` na `multiple=True`**

W [cli.py](f:/PROJEKTY/vinted/bot/src/vintedbot/cli.py#L158) zamień dekoratory i ciało komendy `daemon`:

```python
@cli.command()
@click.option("--brand", multiple=True, type=int, help="ID marki (powtarzalny)")
@click.option("--search", default=None, help="Słowa kluczowe")
@click.option("--cookies", "cookies_paths", multiple=True, required=True,
              type=click.Path(exists=True), help="Plik cookies (powtarzalny; 1 na konto)")
@click.option("--profil", "profile", multiple=True, required=True,
              type=click.Path(exists=False), help="Katalog profilu Camoufox (powtarzalny; 1 na konto)")
@click.option("--interval", default=4, type=int, help="Interwał refresh sesji (minuty)")
@click.option("--payment", is_flag=True, help="Próbuj dojść do kroku payment po rezerwacji")
@click.option("--timing/--no-timing", default=True, help="Zapisuj czasy kroków (ms) z timestampem (domyślnie włączone)")
@click.option("--screenshot/--no-screenshot", default=False, help="Screenshot checkoutu/bramki przez Camoufox (koszt ~8-15 s; domyślnie WYŁĄCZONY, wykonuje się w tle)")
@click.option("--dry-run", is_flag=True, help="Wykrywaj oferty, ale NIE rezerwuj (test bezpieczny)")
def daemon(brand, search, cookies_paths, profile, interval, payment, timing, screenshot, dry_run):
    """Uruchom daemon: podtrzymuj sesję i automatycznie rezerwuj pasujące oferty (multi-konto)."""
    from .daemon import run_daemon_multi
    from .models import Filtry

    if len(cookies_paths) != len(profile):
        raise click.UsageError("Liczba --cookies musi być równa liczbie --profil (1 plik cookies na 1 profil).")

    f = Filtry(brand_ids=list(brand), search_text=search)
    konta = [{"cookies_path": c, "profil": p} for c, p in zip(cookies_paths, profile)]
    run_daemon_multi(konta, filtry=f, proba_payment=payment,
                     refresh_interval_min=interval,
                     timing=timing, screenshot=screenshot, dry_run=dry_run)
```

- [ ] **Step 4: Uruchom — PASS**

Run: `cd bot && python -m pytest tests/test_cli_e2e.py -q`
Expected: wszystkie przechodzą

- [ ] **Step 5: Commit**

```bash
git add bot/src/vintedbot/cli.py bot/tests/test_cli_e2e.py
git commit -m "feat(cli): daemon --cookies/--profil multiple (multi-konto)"
```

---

### Task 3: Pełna suita + diagnostyka

- [ ] **Step 1: Uruchom całą suitę**

Run: `cd bot && python -m pytest -q`
Expected: wszystkie przechodzą, 0 błędów (obecne 106+ + nowe ~2).

- [ ] **Step 2: Sprawdź diagnostykę IDE**

Otwórz [daemon.py](f:/PROJEKTY/vinted/bot/src/vintedbot/daemon.py) i [cli.py](f:/PROJEKTY/vinted/bot/src/vintedbot/cli.py), uruchom `GetDiagnostics` — brak błędów.

- [ ] **Step 3: Commit (jeśli są luźne pliki)**

```bash
git add bot/
git commit -m "test: zielona suita po dodaniu parallel multi-konto"
```

---

## Self-Review

**1. Spec coverage:**
- „równoległy zakup na N kontach" → Task 1 (`run_daemon_multi` startuje N `PurchaseLoop`).
- „każde konto własny RefreshLoop" → Task 1 (N `RefreshLoop`).
- „CLI multi-konto" → Task 2 (`--cookies`/`--profil` jako `multiple`).
- „backward compat pojedyncze konto" → Task 1 (`run_daemon` deleguje do `run_daemon_multi`).

**2. Placeholder scan:** brak TBD/TODO; każdy krok ma pełny kod i komendę z oczekiwanym wynikiem.

**3. Type consistency:**
- `run_daemon_multi(konta, filtry, proba_payment, refresh_interval_min, timing, screenshot, dry_run)` — sygnatura spójna między Task 1 a Task 2.
- `konta` to lista dict `{"cookies_path": str, "profil": str}` — używane identycznie w Task 1 i Task 2.
- `PurchaseLoop(state, filtry, proba_payment, timing, screenshot, profil, dry_run)` — zachowane istniejące pola z [daemon.py:25](f:/PROJEKTY/vinted/bot/src/vintedbot/daemon.py#L25).
- `RefreshLoop(profile, interval_min)` — zachowane z [refresh.py:103](f:/PROJEKTY/vinted/bot/src/vintedbot/refresh.py#L103).
- Test w Task 1 mockuje `d.Filtry` — `daemon.py` już importuje `Filtry` z `.models` (sprawdź: [daemon.py:16](f:/PROJEKTY/vinted/bot/src/vintedbot/daemon.py#L16) importuje `Filtry, KonfiguracjaKonta`). Jeśli nie ma `Filtry`, dodaj do importu.

**Uwaga produkcyjna:** Parallel na N kontach z jednego IP przekroczy rate-limit Vinted (~0.83 req/s) i podniesie ryzyko bana. W produkcji każdy `PurchaseLoop` musi iść przez osobne proxy rezydencjalne (1 IP = 1 konto). To poza zakresem tego planu kodowego — wymagane osobno (AGENTS.md, „jak_zejsc_ponizej_kopsa.md" pkt 7).