# Precision Clicker & T0 Spawn Synchronization Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Przywrócenie pełnej prędkości spamu (30.0–38.46 CPS) bez opóźnień planisty Windowsa oraz zsynchronizowanie startu klikania dokładnie z momentem spawnu skrzynki ($T_0$).

**Architecture:** Wprowadzenie hybrydowego timera mikrosekundowego `precise_sleep` w pętli `Clicker.spam_click` oraz przebudowa maszyny stanów `watch_timer` w `MacroEngine` na precyzyjne odliczanie do $T_0$.

**Tech Stack:** Python 3.11, `time.perf_counter`, `time.monotonic`, SendInput API, Pytest.

---

### Task 1: Precyzyjny Sleep w `Clicker`
- Pliki: `mvp/bot/clicker.py`, `mvp/tests/test_clicker.py`
- Wdrożenie `precise_sleep(duration_s: float)` eliminującej jitter scheduler-a Windows.

### Task 2: Synchronizacja Spamu z $T_0$ w `_handle_watch_timer`
- Pliki: `mvp/bot/macro_engine.py`, `mvp/tests/test_macro_engine.py`
- Odliczanie do punktu $T_0 - 0.2\text{ s}$ zamiast natychmiastowego klikania przy odczycie 3s/4s.

### Task 3: Pełna Weryfikacja
- Uruchomienie testów jednostkowych i lintera.
