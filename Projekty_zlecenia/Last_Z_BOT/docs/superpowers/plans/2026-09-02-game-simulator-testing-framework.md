# Game Simulator Testing Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować jeden działający framework testujący macro bota helikoptera realnymi kliknięciami OS w okno symulatora Tkinter i mierzący 4 metryki (celność, latency, czas detekcji, niezawodność).

**Architecture:** Bot pozostaje niezmieniony poza fallbackiem `window_finder.py` po tytule okna. Symulator (`GameSimulator`, Tkinter) jest jedynym źródłem prawdy: serwuje klatki botowi przez `ScreenCapture.set_frame_source`, wyzwala alert, weryfikuje kliknięcia względem ROI i zbiera metryki. Nowe moduły trafiają do `mvp/simulator/` pod unikalnymi nazwami, aby nie kolidować z istniejącym (nieużywanym) headless engine.

**Tech Stack:** Python 3.11, Tkinter, OpenCV/numpy, `mvp.bot` (macro engine, clicker, ScreenCapture, window_finder).

---

## Ważna decyzja wdrożeniowa (odstępstwo od spec)

Spec zakładał nowy `mvp/simulator/metrics.py`, ale ten plik **już istnieje** jako headless `MetricsCollector` importowany przez `mvp/simulator/engine.py` i testy `tests/simulator/`. Nadpisanie go spowodowałoby regresję w nieużywanej (ale wciąż obecnej) ścieżce headless. Dlatego nowy kolektor nazywa się `sim_metrics.py` z klasą `SimulationMetricsCollector`. Headless engine pozostaje fizycznie nietknięty i nieużywany. `variants.py` i `config.py` są współdzielone bez zmian.

---

## File Structure

- `mvp/simulator/game.py` — NOWY: `GameSimulator` (przeniesiony z `game_window_simulator_advanced.AdvancedGameSimulator`) + `SimulatorUI`. Dodaje fazę skrzynki (treasure) i podpięcie wariantów.
- `mvp/simulator/sim_metrics.py` — NOWY: `SimulationMetricsCollector` (celność, latency, detekcja, niezawodność; eksport JSON + raport).
- `mvp/simulator/bot_bridge.py` — NOWY: `BotBridge` (opakowuje `step_callback` bota, ustawia `set_frame_source`).
- `mvp/bot/window_finder.py` — MODYFIKACJA: fallback wyszukiwania okna po tytule.
- `run_simulator.py` — NOWY (root): jedyny entry point CLI.
- `mvp/tests/game_window/test_simulator_e2e.py` — MODYFIKACJA: nowe importy.

---

## Task 1: Fallback wyszukiwania okna po tytule w `window_finder.py`

**Files:**
- Modify: `mvp/bot/window_finder.py`

- [ ] **Step 1: Dodaj test jednostkowy**

Create: `tests/test_window_finder_title_fallback.py`

```python
from mvp.bot.window_finder import _find_window_by_title, WindowInfo


def test_find_window_by_title_returns_none_when_absent(monkeypatch):
    def fake_enum(proc, lparam):
        return True
    monkeypatch.setattr("mvp.bot.window_finder.user32.EnumWindows", fake_enum)
    assert _find_window_by_title("Brak takiego okna") is None


def test_find_window_by_title_returns_window(monkeypatch):
    captured = []

    def fake_enum(proc, lparam):
        # Symuluj jedno okno: hwnd=42, widoczne, tytuł pasuje
        hwnd = 42
        # IsWindowVisible -> True
        captured.append(hwnd)
        return False  # przestań enumerować po pierwszym znalezieniu

    monkeypatch.setattr("mvp.bot.window_finder.user32.EnumWindows", fake_enum)
    # Stubujemy szczegóły geometrii; wersja produkcyjna zbuduje WindowInfo.
    monkeypatch.setattr(
        "mvp.bot.window_finder._refresh_window_geometry",
        lambda hwnd, pid: WindowInfo(hwnd, 0, 0, 800, 600, "LastZ Simulator", 0),
    )
    result = _find_window_by_title("LastZ Simulator")
    assert result is not None
    assert result.title == "LastZ Simulator"
```

- [ ] **Step 2: Uruchom testy, oczekiwany FAIL**

Run: `uv run pytest tests/test_window_finder_title_fallback.py -v`
Expected: FAIL — `ImportError: cannot import name '_find_window_by_title'`

- [ ] **Step 3: Dodaj `_find_window_by_title` i fallback w `find_game_window`**

W `mvp/bot/window_finder.py`, po `_find_process_pids`, dodaj:

```python
_SIMULATOR_WINDOW_TITLE = "LastZ Simulator"


def _find_window_by_title(title: str) -> "WindowInfo | None":
    result: WindowInfo | None = None

    def enum_callback(hwnd: int, lparam: int) -> bool:
        nonlocal result
        if not user32.IsWindowVisible(hwnd):
            return True
        if _get_window_title(hwnd) != title:
            return True
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        refreshed = _refresh_window_geometry(hwnd, process_id.value)
        if refreshed is not None:
            result = refreshed
            return False
        return True

    window_enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(window_enum_proc(enum_callback), 0)
    return result
```

W `find_game_window`, po `pids = _find_process_pids(process_name)` i `if not pids:`, zamień blok `return None` na fallback:

```python
    pids = _find_process_pids(process_name)
    if not pids:
        # Fallback: gdy gra nie działa, symulator udaje okno gry po tytule.
        sim_info = _find_window_by_title(_SIMULATOR_WINDOW_TITLE)
        if sim_info is not None:
            _hwnd_cache[process_name] = (0, time.monotonic(), sim_info)
            return sim_info
        _hwnd_cache[process_name] = (0, time.monotonic(), None)
        return None
```

- [ ] **Step 4: Uruchom testy, oczekiwany PASS**

Run: `uv run pytest tests/test_window_finder_title_fallback.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mvp/bot/window_finder.py tests/test_window_finder_title_fallback.py
git commit -m "feat(window_finder): fallback to window title for simulator"
```

---

## Task 2: Przenieś symulator do `mvp/simulator/game.py` z fazą skrzynki i wariantami

**Files:**
- Create: `mvp/simulator/game.py`

- [ ] **Step 1: Skopiuj istniejący symulator do nowego modułu, zmień nazwę klasy**

Skopiuj zawartość `game_window_simulator_advanced.py` do `mvp/simulator/game.py`, po czym:
- Zmień nazwę klasy `AdvancedGameSimulator` → `GameSimulator`.
- Zmień `SimulatorUI` — pozostaje.
- Dodaj na górze importy wariantów:
  ```python
  from mvp.simulator.config import VARIANT_PRESETS
  from mvp.simulator.variants import VariantExecutor
  ```

- [ ] **Step 2: Dodaj stan skrzynki (treasure) i warianty do `GameSimulator.__init__`**

W `__init__`, po `self._crop_offset = (0, 0)`, dodaj:

```python
        # Treasure (skrzynka) state
        self.treasure_active = False
        self.treasure_start_time = None
        self.treasure_duration = 5.0

        # Variant configuration
        self.variant_executor = VariantExecutor(session_id=getattr(self, "session_id", None))
        self.current_variant = None
```

W `images` dodaj wczytanie obrazu skrzynki `"treasure"` z `"helka_scrolled.png"` (już załadowane jako `"helka"`), użyj istniejącego klucza `"helka"` jako tła skrzynki.

- [ ] **Step 3: Dodaj metodę `apply_variant` i `set_treasure`**

```python
    def apply_variant(self, preset_name: str) -> None:
        self.variant_executor.apply_preset(preset_name)
        self.current_variant = self.variant_executor.current_variant

    def set_treasure(self) -> None:
        self.treasure_active = True
        self.treasure_start_time = time.time()
        self.current_state = "helka"
```

- [ ] **Step 4: Rozszerz `get_current_frame_raw` o stan `treasure`**

W `get_current_frame_raw`, w `elif self.current_state == "helka":` (już istnieje) — to jest stan skrzynki; pozostaw obraz `"helka"`. Dodaj ustawianie `treasure_active` przy wejściu w `helka` przez `set_treasure` (Step 3). Bez zmian w rysowaniu poza istniejącym.

- [ ] **Step 5: Dodaj test przeniesienia**

Create: `mvp/tests/game_window/test_game_simulator_module.py`

```python
from mvp.simulator.game import GameSimulator


def test_game_simulator_importable():
    sim = GameSimulator()
    assert sim is not None
    assert hasattr(sim, "apply_variant")
    assert hasattr(sim, "set_treasure")


def test_apply_variant_default():
    sim = GameSimulator()
    sim.apply_variant("default")
    assert sim.current_variant["bot_config"] == "38_cps"
```

- [ ] **Step 6: Uruchom testy, oczekiwany PASS**

Run: `uv run pytest mvp/tests/game_window/test_game_simulator_module.py -v`
Expected: PASS (wymaga dostępnych assetów `data/macro_testing`).

- [ ] **Step 7: Commit**

```bash
git add mvp/simulator/game.py mvp/tests/game_window/test_game_simulator_module.py
git commit -m "feat(simulator): move GameSimulator into mvp.simulator with treasure phase"
```

---

## Task 3: Nowy `SimulationMetricsCollector` w `sim_metrics.py`

**Files:**
- Create: `mvp/simulator/sim_metrics.py`

- [ ] **Step 1: Napisz test**

Create: `mvp/tests/game_window/test_sim_metrics.py`

```python
from mvp.simulator.sim_metrics import SimulationMetricsCollector


def test_record_alert_metrics():
    c = SimulationMetricsCollector(session_id="s1")
    c.record_alert_metrics(
        iteration=0,
        hit=True,
        latency_ms=120.0,
        detection_ms=80.0,
    )
    c.record_reliability(iteration=0, recovered=True)
    agg = c.aggregate()
    assert agg["iterations_total"] == 1
    assert agg["iterations_hit"] == 1
    assert agg["latency_avg_ms"] == 120.0
    assert agg["detection_avg_ms"] == 80.0
    assert agg["reliability_percent"] == 100.0


def test_export_empty(tmp_path):
    c = SimulationMetricsCollector(session_id="s2")
    path = c.export(tmp_path)
    assert path.exists()
```

- [ ] **Step 2: Uruchom testy, oczekiwany FAIL**

Run: `uv run pytest mvp/tests/game_window/test_sim_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: mvp.simulator.sim_metrics`

- [ ] **Step 3: Zaimplementuj `SimulationMetricsCollector`**

```python
import json
from pathlib import Path
from typing import Any


class SimulationMetricsCollector:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.iterations: dict[int, dict[str, Any]] = {}

    def record_alert_metrics(
        self,
        iteration: int,
        hit: bool,
        latency_ms: float,
        detection_ms: float,
    ) -> None:
        self.iterations.setdefault(iteration, {})
        self.iterations[iteration].update(
            hit=hit, latency_ms=latency_ms, detection_ms=detection_ms
        )

    def record_reliability(self, iteration: int, recovered: bool) -> None:
        self.iterations.setdefault(iteration, {})
        self.iterations[iteration]["recovered"] = recovered

    def aggregate(self) -> dict[str, Any]:
        total = len(self.iterations)
        if total == 0:
            return {
                "iterations_total": 0,
                "iterations_hit": 0,
                "accuracy_percent": 0.0,
                "latency_avg_ms": None,
                "detection_avg_ms": None,
                "reliability_percent": 0.0,
            }
        hits = sum(1 for it in self.iterations.values() if it.get("hit"))
        lat = [it["latency_ms"] for it in self.iterations.values() if it.get("latency_ms") is not None]
        det = [it["detection_ms"] for it in self.iterations.values() if it.get("detection_ms") is not None]
        recovered = sum(1 for it in self.iterations.values() if it.get("recovered"))
        return {
            "iterations_total": total,
            "iterations_hit": hits,
            "accuracy_percent": (hits / total * 100),
            "latency_avg_ms": (sum(lat) / len(lat)) if lat else None,
            "detection_avg_ms": (sum(det) / len(det)) if det else None,
            "reliability_percent": (recovered / total * 100),
        }

    def export(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"session_{self.session_id}.json"
        path.write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "aggregate": self.aggregate(),
                    "iterations": self.iterations,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path
```

- [ ] **Step 4: Uruchom testy, oczekiwany PASS**

Run: `uv run pytest mvp/tests/game_window/test_sim_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mvp/simulator/sim_metrics.py mvp/tests/game_window/test_sim_metrics.py
git commit -m "feat(simulator): add SimulationMetricsCollector"
```

---

## Task 4: `BotBridge` opakowujący `step_callback` i ustawiający `set_frame_source`

**Files:**
- Create: `mvp/simulator/bot_bridge.py`

- [ ] **Step 1: Napisz test**

Create: `mvp/tests/game_window/test_bot_bridge.py`

```python
from mvp.simulator.bot_bridge import BotBridge


def test_bridge_wraps_step_callback():
    calls = []
    original = lambda event, step_num, step, **kw: calls.append(("orig", event))

    class FakeSim:
        frame = "FRAME"
        def get_current_frame_raw(self):
            return self.frame

    sim = FakeSim()
    bridge = BotBridge(sim)
    bridge.attach_step_callback(original)

    bridge.on_step_event("success", 1, _FakeStep("SCROLL_LISTEN_CHAT"))
    assert ("orig", "success") in calls
    assert bridge.last_detection_mono is not None


class _FakeStep:
    def __init__(self, type_name):
        self.type = _FakeType(type_name)


class _FakeType:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name
```

- [ ] **Step 2: Uruchom testy, oczekiwany FAIL**

Run: `uv run pytest mvp/tests/game_window/test_bot_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: mvp.simulator.bot_bridge`

- [ ] **Step 3: Zaimplementuj `BotBridge`**

```python
import time


class BotBridge:
    def __init__(self, simulator) -> None:
        self._simulator = simulator
        self._original_callback = None
        self.last_detection_mono = None

    def attach_step_callback(self, original_callback) -> None:
        self._original_callback = original_callback

    def on_step_event(self, event, step_num, step, **kwargs) -> None:
        # Wywołaj oryginalny logger (MacroStepLogger), nie zastępuj go.
        if self._original_callback is not None:
            self._original_callback(event, step_num, step, **kwargs)

        step_type = str(getattr(step, "type", "")).split(".")[-1]
        if step_type == "SCROLL_LISTEN_CHAT" and event == "success":
            self.last_detection_mono = time.monotonic()

    def connect(self, bot_runner) -> None:
        # Symulator serwuje klatki botowi.
        if getattr(bot_runner, "capture", None) is not None:
            bot_runner.capture.set_frame_source(self._simulator.get_current_frame_raw)
        # Opakuj istniejący step_callback.
        if bot_runner.macro_engine is not None:
            self.attach_step_callback(bot_runner.macro_engine.step_callback)
            bot_runner.macro_engine.step_callback = self.on_step_event
```

- [ ] **Step 4: Uruchom testy, oczekiwany PASS**

Run: `uv run pytest mvp/tests/game_window/test_bot_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mvp/simulator/bot_bridge.py mvp/tests/game_window/test_bot_bridge.py
git commit -m "feat(simulator): add BotBridge for step callback + frame source"
```

---

## Task 5: Jedyny entry point `run_simulator.py`

**Files:**
- Create: `run_simulator.py`

- [ ] **Step 1: Napisz CLI**

```python
#!/usr/bin/env python3
import argparse

from mvp.simulator.game import GameSimulator, SimulatorUI


def main() -> int:
    parser = argparse.ArgumentParser(description="Game Simulator Testing Framework")
    parser.add_argument("--variant", default="default",
                        choices=["default", "hard_mode", "stress_test"])
    parser.add_argument("--config", default=None, help="Path to bot config (unused in MVP)")
    args = parser.parse_args()

    sim = GameSimulator()
    sim.apply_variant(args.variant)

    ui = SimulatorUI(sim)
    ui.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Uruchom test importu (bez GUI)**

Run: `uv run python -c "import ast; ast.parse(open('run_simulator.py').read())"`
Expected: brak błędu składni.

- [ ] **Step 3: Commit**

```bash
git add run_simulator.py
git commit -m "feat(simulator): add single run_simulator.py entry point"
```

---

## Task 6: Aktualizacja testów i usunięcie starych entry pointów

**Files:**
- Modify: `mvp/tests/game_window/test_simulator_e2e.py:17`
- Delete: `run_simulator_extended.py`, `run_simulator_integrated_full.py`

- [ ] **Step 1: Zmień import w testach**

W `mvp/tests/game_window/test_simulator_e2e.py` zamień linię 16-17:

```python
# Import simulator from root directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from game_window_simulator_advanced import AdvancedGameSimulator
```

na:

```python
from mvp.simulator.game import GameSimulator as AdvancedGameSimulator
```

- [ ] **Step 2: Uruchom całą suity testów symulatora**

Run: `uv run pytest mvp/tests/game_window/ tests/test_window_finder_title_fallback.py -v`
Expected: PASS (wszystkie).

- [ ] **Step 3: Usuń stare entry pointy**

Run: `uv run python -c "import pathlib; [p.unlink() for p in [pathlib.Path('run_simulator_extended.py'), pathlib.Path('run_simulator_integrated_full.py')] if p.exists()]"`

- [ ] **Step 4: Commit**

```bash
git add mvp/tests/game_window/test_simulator_e2e.py
git commit -m "chore(simulator): update imports, remove legacy entry points"
```

---

## Self-Review

- **Spec coverage:** fallback tytułu (Task 1), GameSimulator + faza skrzynki + warianty (Task 2), metryki (Task 3), BotBridge detekcja + frame source (Task 4), single CLI (Task 5), aktualizacja testów (Task 6). Wszystkie wymagania spec mają zadanie.
- **Placeholder scan:** brak TBD/TODO; każdy krok ma pełny kod lub komendę.
- **Type consistency:** `GameSimulator.get_current_frame_raw`, `set_treasure`, `apply_variant` używane spójnie w Task 2 i 4. `SimulationMetricsCollector.record_alert_metrics/record_reliability/aggregate/export` spójne w Task 3. `BotBridge.on_step_event/connect/attach_step_callback` spójne w Task 4.

**Znane ograniczenie (nie blokuje):** `find_game_window` po fallbacku ustawia pid `0` w cache; `force_foreground` i `is_foreground` polegają na `_find_process_pids`, które dla pid `0` może nie zadziałać przy ponownym sprawdzeniu. W MVP testujemy ścieżkę wyszukiwania i geometrię; ewentualne doszlifowanie `force_foreground` dla tytułu to follow-up.