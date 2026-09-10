> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# CPU Optimization and Chat Guard Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Drastically reduce bot CPU utilization (from 80%+ down to <10-15%) and prevent accidental chat closing / desynchronization during overnight runs.

**Architecture:** 
1. Adaptively throttle EasyOCR/PyTorch timer polling (relax intervals and fast phase thresholds, cap PyTorch CPU threads, skip unchanged frames).
2. Throttle GUI preview rendering texture conversions when preview is enabled.
3. Replace blind `chat_bar_roi` clicks in chat watchdog with non-destructive tab clicks and robust chat visibility verification.

**Tech Stack:** Python 3.11, PyTorch/EasyOCR, OpenCV, DearPyGui, Pytest.

---

### Task 1: Relax Watch Timer & Idle Polling Intervals in MVPConfig

**Files:**
- Modify: `mvp/config.py:40-60`
- Test: `mvp/tests/test_config.py`

**Step 1: Write the failing test**
Add tests asserting optimized default intervals:
- `idle_check_interval_s`: 1.5s (was 0.5s)
- `fast_check_interval_s`: 0.3s (was 0.1s)
- `fast_threshold_s`: 30s (was 300s)

**Step 2: Run test to verify it fails**
Run: `uv run pytest mvp/tests/test_config.py`

**Step 3: Update `mvp/config.py` defaults and validation**
Update default values and bounds in `MVPConfig`.

**Step 4: Run test to verify it passes**
Run: `uv run pytest mvp/tests/test_config.py`

---

### Task 2: Implement Frame Diffing & Inference Optimization for OCR Engines

**Files:**
- Modify: `mvp/bot/ocr.py`
- Modify: `mvp/bot/macro_engine.py:960-1170`
- Test: `mvp/tests/test_ocr.py`

**Step 1: Write unit tests for crop diffing and inference guard**
Ensure `read_timer` and `find_helicopter_alert` don't invoke expensive PyTorch inference when consecutive frames are identical or when inference is already in progress.

**Step 2: Implement frame diffing and PyTorch thread limit**
- Limit PyTorch threads to 1 or 2 with `torch.set_num_threads(1)` during background polling.
- In `TimerOCR.read_timer`, compare crop hash/diff with the previous crop; if unchanged, return cached result without running CRAFT+CRNN.
- In `_handle_watch_timer`, use monotonic clock projection between OCR reads to reduce polling rate.

**Step 3: Run OCR test suite**
Run: `uv run pytest mvp/tests/test_ocr.py`

---

### Task 3: Throttle GUI Texture Updates

**Files:**
- Modify: `mvp/gui/main_window.py:1150-1180`
- Test: `mvp/tests/test_main_window_integration.py`

**Step 1: Write test for GUI preview frame rate limiting**
Ensure `_update_frame_texture()` drops frame conversion frequency to ~15 FPS max instead of running on every single 60 FPS DPG frame.

**Step 2: Implement timestamp-based throttle in `_update_frame_texture`**
Add `_last_texture_update` time check (min interval 0.066s = 15 FPS) in `_update_frame_texture`.

**Step 3: Run GUI tests**
Run: `uv run pytest mvp/tests/test_main_window_integration.py`

---

### Task 4: Fix Chat Keep-Alive Watchdog & Safe Chat Tab Recovery

**Files:**
- Modify: `mvp/bot/macro_engine.py:640-840`
- Modify: `mvp/bot/ocr.py:264-290`
- Test: `mvp/tests/test_macro_engine.py`

**Step 1: Write failing test for non-destructive chat restore**
Assert that `_handle_scroll_listen_chat` and watchdog do not click `chat_bar_roi` when the chat window or tab bar is already open.

**Step 2: Implement safe non-destructive chat recovery**
- In `_is_alliance_chat_open`, add fuzzy / substring matching and check if general chat container is open.
- If chat is suspected open but on wrong tab, click ONLY `step.alliance_tab_roi`.
- Only click `step.chat_bar_roi` if verified that neither chat dialog nor alliance tab is visible.

**Step 3: Run macro engine tests**
Run: `uv run pytest mvp/tests/test_macro_engine.py`

---

### Task 5: Full Suite Verification

**Step 1: Run complete test suite and linters**
- Run: `uv run pytest`
- Run: `uv run ruff check .`
- Verify zero regressions across the codebase.
