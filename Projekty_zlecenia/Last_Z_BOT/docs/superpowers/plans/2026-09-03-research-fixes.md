# Research Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wdrożyć trzy zatwierdzone usprawnienia z weryfikacji referencji badawczych: powiązanie płatności Stripe przez `client_reference_id`, eliminację deadlocku DearPyGui przez kolejkę UI oraz blokadę startu bota przy wykryciu niezgodności UIPI.

**Architecture:** Trzy niezależne, małe zmiany w istniejącym kodzie. Każda jest samodzielna i testowalna osobno. Nie wprowadzamy nowych zależności ani restrukturyzacji.

**Tech Stack:** Python 3.11, FastAPI + SQLAlchemy + Stripe (backend), DearPyGui + threading (GUI), ctypes/WinAPI (UIPI).

---

## Zakres i stan faktyczny (co już jest, czego brakuje)

Weryfikacja kodu potwierdziła, że większość rekomendacji z badań **jest już wdrożona**:

- **Stripe idempotencja** — już jest (`_check_event_idempotent` w `backend/main.py:74`).
- **Stripe `invoice.paid` / `invoice.payment_failed` / `subscription.*`** — już obsługiwane (`backend/main.py:362-427`).
- **Stripe kolejność webhook** — już poprawna: `body()` → `construct_event()` → idempotencja → 200.
- **DPG wzorzec queue dla logów** — już jest (`GuiLogHandler` → `GuiState.log_queue` → `MainWindow._update_logs`).
- **Clicker `spam_click` + hold 18ms + ruch tylko przy pierwszym kliku** — już wdrożone.

Pozostały **trzy realne luki**:

1. **Stripe:** `checkout.session.completed` wyszukuje użytkownika po **emailu** (`backend/main.py:337-340`), co research uznaje za niewiarygodne. Trzeba przejść na `client_reference_id`.
2. **DearPyGui:** `MainWindow._on_step_event` wywołuje `dpg.set_value()` z **wątku bota** (`macro_engine.run` → `_emit` → `step_callback`). To dokładnie scenariusz deadlocku GIL↔mutex opisany w issue #2053.
3. **UIPI:** `check_uipi_elevation_mismatch` już istnieje i jest poprawny, ale `runner.py` tylko loguje ostrzeżenie i **kontynuuje start**, zamiast zablokować uruchomienie bota.

---

### Task 1: Stripe — powiązanie płatności przez `client_reference_id`

**Files:**
- Modify: `mvp/backend/main.py:190-218` (tworzenie sesji checkout)
- Modify: `mvp/backend/main.py:336-360` (obsługa `checkout.session.completed`)
- Test: `mvp/tests/backend/test_api.py` (dodać testy)

- [ ] **Step 1: Napisz test upadający dla `client_reference_id`**

W `mvp/tests/backend/test_api.py`, w klasie `TestCheckoutSession`, dodaj test sprawdzający, że `checkout.session.completed` aktywuje licencję po `client_reference_id`, a NIE po emailu:

```python
    def test_checkout_completed_activates_by_client_reference_id(self, client, db_session):
        import mvp.backend.main as main_module
        from mvp.backend.models import License, User

        u = User(email="cr@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-CR1", is_active=False)
        db_session.add(lic)
        db_session.commit()

        main_module.redis_client = _FakeRedis()
        try:
            event = {
                "id": "evt_cr_1",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        # Adres email celowo NIEZGODNY z kontem,
                        # aby udowodnić, że nie wyszukujemy po emailu.
                        "customer_email": "inny@x.com",
                        "customer": "cs_cr",
                        "client_reference_id": u.id,
                    }
                },
            }
            with patch("stripe.Webhook.construct_event", return_value=event):
                resp = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
            assert resp.status_code == 200
        finally:
            main_module.redis_client = None

        from mvp.backend.models import StripeCustomer

        sc = db_session.query(StripeCustomer).filter(StripeCustomer.user_id == u.id).first()
        assert sc is not None
        assert sc.stripe_customer_id == "cs_cr"
        db_session.refresh(lic)
        assert lic.is_active is True
```

- [ ] **Step 2: Uruchom test — ma upaść**

Run: `uv run pytest mvp/tests/backend/test_api.py::TestCheckoutSession::test_checkout_completed_activates_by_client_reference_id -v`

Expected: FAIL. Obecny kod szuka `User.email == "inny@x.com"`, nie znajduje, licencja pozostaje `is_active=False`.

- [ ] **Step 3: Dodaj `client_reference_id` przy tworzeniu sesji**

W `mvp/backend/main.py`, w `create_checkout_session` (linia 207-214), dodaj parametr `client_reference_id`:

```python
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            customer_email=user.email,
            success_url=str(data.success_url),
            cancel_url=str(data.cancel_url),
            client_reference_id=user.id,
            metadata={"user_id": user.id},
        )
```

- [ ] **Step 4: Przepisz obsługę `checkout.session.completed` na `client_reference_id`**

W `mvp/backend/main.py` zamień blok `if event_type == "checkout.session.completed":` (linie 336-360):

```python
    if event_type == "checkout.session.completed":
        user_id = data.get("client_reference_id")
        stripe_customer_id = data.get("customer")
        if user_id and stripe_customer_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                existing = (
                    db.query(StripeCustomer).filter(StripeCustomer.user_id == user.id).first()
                )
                if existing:
                    existing.stripe_customer_id = stripe_customer_id
                    existing.subscription_status = "active"
                else:
                    db.add(
                        StripeCustomer(
                            user_id=user.id,
                            stripe_customer_id=stripe_customer_id,
                            subscription_status="active",
                        )
                    )
                for lic in user.licenses:
                    lic.is_active = True
                    if not lic.expires_at:
                        lic.expires_at = datetime.now(UTC) + timedelta(days=30)
                db.commit()
```

- [ ] **Step 5: Uruchom test — ma przejść**

Run: `uv run pytest mvp/tests/backend/test_api.py::TestCheckoutSession::test_checkout_completed_activates_by_client_reference_id -v`

Expected: PASS.

- [ ] **Step 6: Uruchom całą klasę webhook, żeby nie było regresji**

Run: `uv run pytest mvp/tests/backend/test_api.py::TestWebhook mvp/tests/backend/test_api.py::TestCheckoutSession -v`

Expected: PASS (wszystkie istniejące testy).

- [ ] **Step 7: Commit**

```bash
git add mvp/backend/main.py mvp/tests/backend/test_api.py
git commit -m "fix(backend): link Stripe checkout to user via client_reference_id"
```

---

### Task 2: DearPyGui — eliminacja deadlocku przez kolejkę UI

**Files:**
- Modify: `mvp/gui/state.py` (dodać `ui_queue` i `push_ui`)
- Modify: `mvp/gui/main_window.py` (callback wrzuca do kolejki, `_render_loop` odbiera)
- Test: `mvp/tests/test_main_window_integration.py`

**Krytyczne tło:** `MacroEngine.run` (`mvp/bot/macro_engine.py:449`) uruchamia się w wątku bota (`BotRunner._main_loop`). `_emit` → `step_callback` → `MainWindow._on_step_event` (linia 813). `_on_step_event` robi `dpg.set_value` bezpośrednio → wywołanie DPG z wątku nie-GUI → deadlock (issue #2053).

- [ ] **Step 1: Napisz test upadający**

W `mvp/tests/test_main_window_integration.py` dodaj test, że `_on_step_event` nie wywołuje `dpg.set_value` bezpośrednio, tylko wrzuca do `ui_queue`:

```python
    def test_step_event_uses_ui_queue_not_direct_dpg(self):
        from queue import Queue

        from mvp.gui.state import GuiState

        class _StubRunner:
            class _Engine:
                def __init__(self):
                    self.reset_session_stats = lambda: None
            def __init__(self):
                self.macro_engine = self._Engine()

        # Konstruujemy MainWindow bez pełnego DPG (nie wolno dotykać DPG w teście).
        state = GuiState()
        state.ui_queue = Queue()
        # Ustawiamy callback bezpośrednio, tak jak robi to setup().
        from mvp.gui.main_window import MainWindow

        # Wywołujemy logikę callbacku przez odwołanie do klasy (nie instancję DPG).
        handler = MainWindow._on_step_event.__get__(_DummyMainWindow(), MainWindow)
        handler(state, "phase_transition", 0, _FakeStep(), phase="spam")

        # Callback musiał wrzucić zdarzenie do kolejki, a nie robić dpg.set_value.
        assert not state.ui_queue.empty()
        item = state.ui_queue.get_nowait()
        assert item[0] == "phase_transition"
```

Ponieważ `_on_step_event` w nowej wersji będzie wymagać `self.state`, `_DummyMainWindow` musi wystawiać `state` i `_event_logger` (no-op). Zdefiniuj helpery na górze pliku testowego:

```python
class _FakeStep:
    label = "spam"

class _DummyMainWindow:
    state = None
    def __init__(self):
        class _NoopLogger:
            def log(self, *a, **k):
                pass
        self._event_logger = _NoopLogger()
```

- [ ] **Step 2: Uruchom test — ma upaść**

Run: `uv run pytest mvp/tests/test_main_window_integration.py::test_step_event_uses_ui_queue_not_direct_dpg -v`

Expected: FAIL (metoda jeszcze nie istnieje w nowej formie / brak `ui_queue`).

- [ ] **Step 3: Dodaj `ui_queue` do `GuiState`**

W `mvp/gui/state.py` dodaj pole i metodę:

```python
@dataclass
class GuiState:
    running: bool = False

    latest_frame: np.ndarray | None = field(default=None, repr=False)

    log_queue: Queue = field(default_factory=lambda: Queue(maxsize=500))

    frame_queue: Queue = field(default_factory=lambda: Queue(maxsize=2))

    ui_queue: Queue = field(default_factory=lambda: Queue(maxsize=500))

    def push_log(self, message: str) -> None:
        with contextlib.suppress(Exception):
            self.log_queue.put_nowait(message)

    def push_ui(self, event: str, *args, **kwargs) -> None:
        with contextlib.suppress(Exception):
            self.ui_queue.put_nowait((event, args, kwargs))
```

- [ ] **Step 4: Przepisz `_on_step_event`, żeby tylko wrzucał do kolejki**

W `mvp/gui/main_window.py`, zamień `_on_step_event` (linie 813-828):

```python
    def _on_step_event(self, event: str, step_num: int, step, **kwargs) -> None:
        self._event_logger.log(event, {"step": step_num, "label": getattr(step, "label", "")})
        self.state.push_ui(event, step_num, step, **kwargs)

    def _apply_ui_event(self, event: str, step_num: int, step, **kwargs) -> None:
        if event == "running":
            dpg.set_value("step_value_text", step.label)
        elif event == "phase_transition":
            self._phase = kwargs.get("phase", "")
            dpg.set_value("phase_text", self._phase.upper())
            if self._phase == "spam":
                dpg.configure_item("phase_text", color=(34, 197, 94))
                from mvp.gui.notify import notify_alert

                notify_alert(self.config.notify_enabled, self.config.notify_sound_path)
            elif self._phase == "fast":
                dpg.configure_item("phase_text", color=(245, 158, 11))
            else:
                dpg.configure_item("phase_text", color=(245, 158, 11))
```

- [ ] **Step 5: Opróżniaj `ui_queue` w pętli GUI**

W `mvp/gui/main_window.py`, w `_render_loop` (linia 974), dodaj na początku odbiór zdarzeń UI:

```python
    def _render_loop(self) -> None:
        self._drain_ui_queue()
        self._update_logs()
        self._update_frame_texture()
        self._update_status_bar()
        self._update_dashboard()
        self._update_game_detection()
        self._resize_dashboard_preview()
        self._flush_preview_config_if_needed()
        now = time.monotonic()
        if now - self._event_log_last_flush > 5.0:
            self._event_log_last_flush = now
            self._event_logger.flush()

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                event, args, kwargs = self.state.ui_queue.get_nowait()
            except Exception:
                break
            try:
                self._apply_ui_event(event, *args, **kwargs)
            except Exception:
                logger.debug("UI event %s failed", event, exc_info=True)
```

- [ ] **Step 6: Uruchom test — ma przejść**

Run: `uv run pytest mvp/tests/test_main_window_integration.py::test_step_event_uses_ui_queue_not_direct_dpg -v`

Expected: PASS.

- [ ] **Step 7: Uruchom istniejące testy GUI, żeby nie było regresji**

Run: `uv run pytest mvp/tests/test_main_window_integration.py mvp/tests/test_gui.py -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add mvp/gui/state.py mvp/gui/main_window.py mvp/tests/test_main_window_integration.py
git commit -m "fix(gui): route step events through queue to avoid DPG deadlock"
```

---

### Task 3: UIPI — blokada startu bota przy niezgodności poziomów integralności

**Files:**
- Modify: `mvp/bot/runner.py:200-214` (zmiana ostrzeżenia na blokadę)
- Test: `mvp/tests/test_runner.py`

**Tło:** `check_uipi_elevation_mismatch` (`mvp/bot/window_finder.py:293`) już poprawnie wykrywa, że gra działa jako admin a bot jako zwykły użytkownik (błąd `GetLastError()==5` = ACCESS_DENIED przy `OpenProcess`). Obecnie `runner.py` tylko loguje ostrzeżenie i startuje bota, przez co kliknięcia są po cichu odrzucane przez Windows.

- [ ] **Step 1: Napisz test upadający**

W `mvp/tests/test_runner.py` dodaj test, że start podnosi `RuntimeError` przy wykryciu UIPI:

```python
    def test_start_raises_on_uipi_mismatch(self, runner, monkeypatch):
        import mvp.bot.runner as runner_module

        runner.clicker.initialize = lambda: None
        runner.clicker.is_initialized = True

        monkeypatch.setattr(
            runner_module.window_finder, "check_uipi_elevation_mismatch", lambda _: True
        )
        import pytest

        with pytest.raises(RuntimeError, match="UIPI"):
            runner.start()
```

Uwaga: jeśli `runner` fixture w `test_runner.py` ma inną sygnaturę, dostosuj konstrukcję do istniejącego fixture (sprawdź plik przed edycją). Zachowaj istotę testu: `check_uipi_elevation_mismatch == True` → `RuntimeError` z "UIPI".

- [ ] **Step 2: Uruchom test — ma upaść**

Run: `uv run pytest mvp/tests/test_runner.py::test_start_raises_on_uipi_mismatch -v`

Expected: FAIL (obecnie start przebiega mimo `True`).

- [ ] **Step 3: Zablokuj start przy UIPI**

W `mvp/bot/runner.py`, w metodzie `start`, zamień blok sprawdzający UIPI (linie 200-214). Sprawdź, czy `window_finder` jest importowane jako moduł — w pliku są importy `from mvp.bot.window_finder import find_game_window`, więc do funkcji `check_uipi_elevation_mismatch` odwołuj się przez lokalny import:

```python
            try:
                from mvp.bot import window_finder

                if window_finder.check_uipi_elevation_mismatch(self.config.process_name):
                    raise RuntimeError(
                        "UIPI BLOCKED: game (%s) runs as Administrator while the bot runs as "
                        "a standard user. Windows will silently discard SendInput clicks. "
                        "Run the bot as Administrator (or the game without Administrator "
                        "rights) and try again." % self.config.process_name
                    )
            except RuntimeError:
                raise
            except Exception as uipi_exc:
                logger.debug("UIPI check failed: %s", uipi_exc)
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `uv run pytest mvp/tests/test_runner.py::test_start_raises_on_uipi_mismatch -v`

Expected: PASS.

- [ ] **Step 5: Uruchom pozostałe testy runnera**

Run: `uv run pytest mvp/tests/test_runner.py -v`

Expected: PASS (bez regresji).

- [ ] **Step 6: Commit**

```bash
git add mvp/bot/runner.py mvp/tests/test_runner.py
git commit -m "fix(bot): block start on UIPI elevation mismatch instead of logging only"
```

---

## Self-Review

**1. Spec coverage:** Trzy luki z weryfikacji (Stripe `client_reference_id`, DPG deadlock, UIPI blokada) mają po jednym tasku. Pozostałe rekomendacje researchu (OCR, DXGI, Locale `float`, Stripe idempotencja) są już w kodzie — celowo pominięte.

**2. Placeholder scan:** Brak. Każdy krok zawiera kompletny kod lub dokładne polecenie.

**3. Type consistency:** `GuiState.ui_queue` zdefiniowane w Task 2 Step 3, używane w Step 4 i 5 — spójne. `client_reference_id` w Task 1 Step 3 (zapis) i Step 4 (odczyt) — spójne nazwy pól Stripe.