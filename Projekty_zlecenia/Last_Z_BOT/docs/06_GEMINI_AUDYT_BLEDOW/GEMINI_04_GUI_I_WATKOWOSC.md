# GEMINI AUDYT CZĘŚĆ 4: INTERFEJS GRAFICZNY (GUI), WĄTKOWOŚĆ I SKRÓTY KLAWISZOWE
**Pliki audytowane:** `mvp/gui/main_window.py`, `mvp/gui/global_hotkey.py`, `mvp/bot/runner.py`

---

## 1. BŁĄD KRYTYCZNY: Wywoływanie funkcji DearPyGui z wątków tła (Crashe `0xC0000005`)

### Dowód w kodzie
Plik: `mvp/gui/main_window.py:813-830`

```python
    def _on_step_event(self, event: str, step_num: int, step, **kwargs) -> None:
        self._event_logger.log(event, {"step": step_num, "label": getattr(step, "label", "")})
        if event == "running":
            dpg.set_value("step_value_text", step.label)
        elif event == "phase_transition":
            self._phase = kwargs.get("phase", "")
            dpg.set_value("phase_text", self._phase.upper())
            if self._phase == "spam":
                dpg.configure_item("phase_text", color=(34, 197, 94))
```

Oraz w `mvp/bot/macro_engine.py:304` (`self._emit("running", i, step)`):
`MacroEngine` działa na wydzielonym wątku roboczym `Thread(target=_main_loop)`.

### Mechanizm awarii
1. Silnik graficzny DearPyGui (oparty na bibliotece ImGui w C++) **nie jest bezpieczny wątkowo** (not thread-safe) przy bezpośrednich modyfikacjach stanu kontrolek (`dpg.set_value`, `dpg.configure_item`, `dpg.bind_item_theme`).
2. Gdy wątek bota wywołuje `dpg.set_value()` w tym samym ułamku milisekundy, w którym główny wątek renderuje klatkę (`dpg.render_dearpygui_frame()`), dochodzi do wyścigu pamięci (data race) w strukturach wewnętrznych C++.
3. Skutek:
   - Aplikacja nagle znika z ekranu bez żadnego komunikatu w Pythonie (błąd systemowy `0xC0000005 ACCESS_VIOLATION` w pliku `dearpygui.pyd`).
   - To bezpośrednia przyczyna zgłaszanego przez klienta **„zawieszania się programu”**.

---

## 2. BŁĄD POWAŻNY: Wyścig wątków i blokada rejestracji hotkeyi (`RegisterHotKey`)

### Dowód w kodzie
Plik: `mvp/gui/global_hotkey.py:49-58`

```python
    def stop(self) -> None:
        self._running = False
        thread_id = self._thread.ident if self._thread is not None else None
        if thread_id is not None:
            try:
                _user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
            except Exception:
                logger.debug("GlobalHotkey: PostThreadMessageW failed", exc_info=True)
        self._thread = None
```

Oraz w `mvp/gui/main_window.py:663-680`:
```python
    def _register_hotkeys(self) -> None:
        for hotkey in self._hotkeys:
            hotkey.stop()
        self._hotkeys = []
        bindings = [
            (self.config.hotkey_spam, self._on_global_spam_hotkey, 1),
            (self.config.hotkey_start_stop, self._on_start_stop, 2),
            (self.config.hotkey_emergency, self._on_emergency_stop, 3),
        ]
        for name, callback, hotkey_id in bindings:
            ...
            hotkey = GlobalHotkey(vk=vk, callback=callback, hotkey_id=hotkey_id)
            hotkey.start()
            self._hotkeys.append(hotkey)
```

### Mechanizm awarii
1. Metoda `stop()` wysyła asynchroniczny komunikat `WM_QUIT`, ale **nie czeka na zakończenie starego wątku** (brak `self._thread.join()`).
2. Przy kliknięciu „Save” lub rekonfiguracji bot natychmiast tworzy nowy obiekt `GlobalHotkey` i próbuje zarejestrować ten sam klawisz (`RegisterHotKey` z identycznym VK i ID).
3. Ponieważ stary wątek jeszcze nie zdążył wywołać `UnregisterHotKey()`, WinAPI zwraca błąd `ERROR_HOTKEY_ALREADY_REGISTERED` (kod 1409).
4. Nowy wątek rejestracji kończy się niepowodzeniem, a skróty klawiszowe (F1, F6, F8) **trwale przestają działać** aż do restartu całej aplikacji.

---

## 3. BŁĄD POWAŻNY: Blokowanie pętli renderowania UI przy zatrzymaniu bota (Stop Freeze)

### Dowód w kodzie
Plik: `mvp/gui/main_window.py:730` i `mvp/bot/runner.py:368-379`

```python
    # main_window.py (Główny wątek GUI):
    elif self.bot_runner.is_running:
        self.bot_runner.stop()
        ...

    # runner.py:
    def stop(self, timeout: float = 2.5) -> None:
        self._stop_event.set()
        self.macro_engine.stop()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout) # <--- Blokuje główny wątek do 2.5s
```

### Mechanizm awarii
- Kliknięcie przycisku `STOP` na interfejsie powoduje synchroniczne zablokowanie wątku GUI na czas oczekiwania na zakończenie długich operacji w `macro_engine` (np. uśpienia `precise_sleep` lub trwającego OCR).
- Okno aplikacji przechodzi w systemowy stan „Brak odpowiedzi” (Not Responding) na 2–3 sekundy przy każdej próbie zatrzymania.
