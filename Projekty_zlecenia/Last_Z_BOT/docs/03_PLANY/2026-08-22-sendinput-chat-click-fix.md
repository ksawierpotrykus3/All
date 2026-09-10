# Fix SendInput Chat Bar Entry and Bottom Click Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Fix unreliable chat entry and bottom-bar clicking in `SendInput` backend after `spam_click` in `mvp`.

**Architecture:** 
1. Enhance `SendInputBackend` to emit normalized absolute coordinates (`MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE`) directly in `LEFTDOWN`/`LEFTUP` events so clicks never land at stale coordinates.
2. Adjust `_ROI_CHAT_BAR` vertical bounds to stay safely within the game's chat bar and well clear of the Windows taskbar and window borders.
3. Add focus and settling stabilization buffers after spam click transitions.

**Tech Stack:** Python 3.11, ctypes Win32 API (`SendInput`, `GetSystemMetrics`), pytest, ruff.

---

### Task 1: Enhance `SendInputBackend` with absolute coordinates

**Files:**
- Modify: `mvp/bot/input/sendinput_backend.py`
- Test: `mvp/tests/test_input_backend.py`

**Step 1: Write the failing unit tests**
Add tests asserting that `SendInputBackend._mouse_input` and click primitives construct `_INPUT` with `MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE` and scaled `dx`, `dy`.

**Step 2: Run test to verify it fails**
Run: `uv run pytest mvp/tests/test_input_backend.py -k test_sendinput_absolute -v`

**Step 3: Implement absolute coordinate mapping in `SendInputBackend`**
Update `_to_absolute_coords(x, y)` and pass flags in `mouse_down_left`, `mouse_up_left`, `spam_down`, `spam_up`.

**Step 4: Run test to verify it passes**
Run: `uv run pytest mvp/tests/test_input_backend.py -v`

---

### Task 2: Adjust `_ROI_CHAT_BAR` and synchronization

**Files:**
- Modify: `mvp/macro_def.py`
- Modify: `assets/macros/custom.macro.json`
- Test: `mvp/tests/test_macro_def.py`

**Step 1: Write test checking `_ROI_CHAT_BAR` bounds**
Verify `_ROI_CHAT_BAR["bottom"] <= 96.0` and `_ROI_CHAT_BAR["top"] >= 90.0`.

**Step 2: Update `_ROI_CHAT_BAR` in `mvp/macro_def.py` and `assets/macros/custom.macro.json`**
Set `top: 91.0, bottom: 95.0, left: 66.0, right: 93.0`.

**Step 3: Run tests to verify**
Run: `uv run pytest mvp/tests/test_macro_def.py -v`

---

### Task 3: Macro Engine stabilization buffer

**Files:**
- Modify: `mvp/bot/macro_engine.py`
- Test: `mvp/tests/test_macro_engine.py`

**Step 1: Add settle pause in `_handle_scroll_listen_chat` after `force_foreground`**
Ensure 0.1s settle time before `_click_chat_roi`.

**Step 2: Run full test suite**
Run: `uv run pytest mvp/tests`
Run: `uv run ruff check mvp`
