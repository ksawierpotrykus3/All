# Tasks

| Task | Description | Status |
| --- | --- | --- |
| 1 | High-precision `precise_sleep` in Clicker for 30-38 CPS (`mvp/bot/clicker.py`) | completed |
| 2 | Add `t0_lead_time_s` config & macro step parameter (`mvp/config.py`, `mvp/macro_def.py`) | completed |
| 3 | Exact Monotonic $T_0$ Countdown & Trigger in `_handle_watch_timer` (`mvp/bot/macro_engine.py`) | completed |
| 4 | Unit & Integration Tests for Precise CPS and $T_0$ Trigger (`mvp/tests/`) | completed |
| 5 | Full Verification (pytest, ruff) | completed |
| 6 | GUI frame texture memory & queue draining optimization (`mvp/gui/main_window.py`) | completed |
| 7 | GUI log console throttling & dirty checking (`mvp/gui/main_window.py`) | completed |
| 8 | Asynchronous bot stop & background CSV flush (`mvp/gui/main_window.py`) | completed |
| 9 | Precise sleep yield (<0.4ms spinlock) & PID caching (`mvp/bot/clicker.py`, `window_finder.py`) | completed |
| 10 | Fast TimerOCR sampling hash & thread shutdown cleanup (`mvp/bot/ocr.py`, `runner.py`, `global_hotkey.py`) | completed |
| 11 | Comprehensive unit & integration verification (`mvp/tests/test_perf_optimizations.py`) | completed |
