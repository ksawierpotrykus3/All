# Implementation Tasks — Watch Timer Spam Click Efficiency Bugfix

## Phase 1: Exploratory Bug Condition Testing

### Task 1. Write Bug Condition Exploration Tests

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - OCR Bottleneck and CPU Spike Detection
  - **CRITICAL**: Write this property-based test BEFORE implementing the fix
  - **GOAL**: Surface counterexamples that demonstrate the bug exists (unfixed code MUST FAIL this test)
  - **Why Property-Based**: Scope across multiple timer countdown scenarios to verify CPU spike and spam latency on unfixed code
  
  **Test Implementation Details from Bug Condition Specification:**
  - Simulate full countdown from 300s to 5s with mocked `read_timer_value()` returning real timer drops
  - Use unfixed OCR interval (stały 0.2s) throughout FAST phase
  - Measure:
    1. Total number of OCR queries executed (should be ~1475 on unfixed code)
    2. CPU load spike in last 5s before T0 (should be >80% on unfixed code)
    3. Time latency from timer≤5s to spam trigger (should be 0.3-0.8s on unfixed code)
  
  **Scoped PBT Approach** (deterministic bug):
  - Property: For any countdown sequence where fast_interval=0.2s and timer spans 300s→5s, the unfixed system SHALL exhibit CPU spike and delayed spam
  - Test asserts expected behavior: adapted system SHOULD reduce OCR queries to <100 and spam latency to <0.2s
  - Generate concrete failing cases: countdown(initial=300, threshold=5, interval=0.2, phases=IDLE→FAST→SPAM)
  
  **Run this test on UNFIXED code:**
  - EXPECTED OUTCOME: Test FAILS (this proves the bug exists)
  - DO NOT attempt to fix the code when it fails
  - Document counterexamples: "With fast_interval=0.2s over 295s, system accumulates ~1475 OCR queries, CPU spike >80%, spam latency 0.3-0.8s"
  
  **Test Expectations from Design**:
  - isBugCondition pseudocode: faza==FAST AND timer≤300s AND interval=0.2s AND NOT cpu_pause_window_active AND NOT proactive_spam_prepared
  - Expected behavior from expectedBehavior: interval should adapt 1.0s→0.2s, CPU pause active in last 1s, spam prepared proactively
  
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

---

## Phase 2: Preservation Property Testing

### Task 2. Write Preservation Property Tests (BEFORE implementing fix)

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Buggy Behavior Across All Input Domains
  - **IMPORTANT**: Follow observation-first methodology — observe behavior on UNFIXED code first
  - **GOAL**: Capture existing correct behaviors that MUST NOT change after fix
  
  **Observation Phase (Run on UNFIXED code):**
  
  **Observation 1 — Timer Jump Detection:**
  - Run unfixed code with timer sequence: [100, 99, 98, 103] (jump +5s)
  - Observed behavior: System detects jump≥3s, resets phase to IDLE, clears T0 estimate
  - Expected: Same behavior on fixed code
  
  **Observation 2 — Inactivity Timeout:**
  - Run unfixed code with stale timer (no change for 1800s)
  - Observed behavior: System returns "inactivity_timeout" without error
  - Expected: Same behavior on fixed code
  
  **Observation 3 — OCR Error Handling:**
  - Run unfixed code with `_read_timer_value()` returning None
  - Observed behavior: System falls back to `last_known_value`, continues countdown
  - Expected: Same behavior on fixed code
  
  **Observation 4 — Network T0 Priority:**
  - Run unfixed code with network signal `\x58\x01` arriving during FAST phase
  - Observed behavior: Spam triggered immediately, prioritized over OCR
  - Expected: Same behavior on fixed code
  
  **Observation 5 — Hysteresis Enforcement:**
  - Run unfixed code with 1 confirmation of timer≤5s (hysteresis_confirmations=2 required)
  - Observed behavior: Spam NOT triggered until 2nd confirmation arrives
  - Expected: Same behavior on fixed code
  
  **Property-Based Test Implementation:**
  - Generate diverse timer sequences using Hypothesis:
    - Monotonic descents (300s→5s)
    - Sequences with jumps (various ±ΔT values)
    - Sequences with None/missing values
    - Sequences with network T0 signals
  - For each sequence: Assert that fixed behavior matches observed unfixed behavior for all non-buggy cases
  - Parameterize across: hysteresis values (1, 2, 3), timeout thresholds, jump detection thresholds
  
  **Run on UNFIXED code:**
  - EXPECTED OUTCOME: Tests PASS (confirms baseline correct behavior)
  - Document observations: "Jump detection: [100,99,98,103] → reset IDLE", etc.
  
  **Run on FIXED code (after implementation):**
  - EXPECTED OUTCOME: Tests still PASS (confirms no regressions)
  
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

---

## Phase 3: Implementation

### Task 3. Implement Watch Timer Optimization Fix

#### Sub-task 3.1 Add ocr_dynamic_interval_config to MacroStep

- [x] 3.1 Add adaptive OCR interval configuration
  - Location: `mvp/bot/macro_engine.py`, class `MacroStep`
  - Add field: `ocr_dynamic_interval_config: Optional[Dict[str, float]] = None`
  - Default config (when None):
    ```python
    {
        "initial_interval": 1.0,      # interval at start of FAST (instead of fixed 0.2s)
        "accel_threshold": 10.0,      # seconds remaining to start acceleration
        "min_interval": 0.2,          # minimum OCR interval
        "cpu_pause_window": 1.0,      # seconds before T0 to pause OCR
    }
    ```
  - Add helper method: `get_ocr_interval_config()` that returns defaults if None
  - _Bug_Condition: isBugCondition(input) where faza==FAST and interval=0.2s_
  - _Expected_Behavior: ocr_dynamic_interval_config enables adaptive interval from expectedBehavior_
  - _Preservation: Configuration must not affect non-FAST phases or phases with hysteresis_
  - _Requirements: 2.1_

#### Sub-task 3.2 Implement adaptive interval calculation

- [x] 3.2 Implement calculate_adaptive_interval() function
  - Location: `mvp/bot/macro_engine.py` (module level or as private method in `_handle_watch_timer`)
  - Function signature: `calculate_adaptive_interval(time_remaining, initial_interval, accel_threshold, min_interval) -> float`
  - Logic:
    - If `time_remaining >= accel_threshold`: return `initial_interval` (1.0s)
    - If `time_remaining < accel_threshold`: return linear interpolation: `min_interval + (initial_interval - min_interval) * (time_remaining / accel_threshold)`
    - Clamp result between `min_interval` and `initial_interval`
  - Unit tests:
    - Test with time_remaining=300s (expect initial_interval)
    - Test with time_remaining=5s (expect min_interval or close to it)
    - Test with time_remaining=5.0s exactly (expect linear result)
  - _Expected_Behavior: Property 1 from design_
  - _Requirements: 2.1, 2.4_

#### Sub-task 3.3 Implement calculate_avg_delta() for monotonic T0 estimation

- [x] 3.3 Implement calculate_avg_delta() function
  - Location: `mvp/bot/macro_engine.py`
  - Function signature: `calculate_avg_delta(timer_history: List[Dict]) -> float`
  - Input format: `[{"value": timer_value, "time": timestamp}, ...]` (last 3-5 entries)
  - Logic: Calculate average time-delta between consecutive timer drops
    - Skip None values and jumps (|delta| > 2.0s)
    - Return average of valid deltas
  - Unit tests:
    - Test with smooth descent: [100, 99, 98] at 1s intervals → avg_delta ≈ 1.0
    - Test with varying intervals: [100, 98.5, 97.1] → avg_delta correctly weighted
  - _Expected_Behavior: Foundation for proactive T0 estimate (Property 3)_
  - _Requirements: 2.3_

#### Sub-task 3.4 Implement should_trigger_spam() decision logic

- [x] 3.4 Implement should_trigger_spam() function
  - Location: `mvp/bot/macro_engine.py`
  - Function signature: `should_trigger_spam(network_t0_triggered, ocr_timer_value, estimated_t0_mono, confirmed_count, hysteresis_confirmations, spam_threshold, ...) -> bool`
  - Priority order (first match wins):
    1. If `network_t0_triggered` (from `\x58\x01` in network packet): return True immediately
    2. If `ocr_timer_value <= spam_threshold` AND `confirmed_count >= hysteresis_confirmations`: return True
    3. If `estimated_t0_mono` is not None AND `abs(now() - estimated_t0_mono) <= 0.2s`: return True
    4. Otherwise: return False
  - Unit tests:
    - Test network priority: network_t0_triggered=True should return True regardless of other flags
    - Test hysteresis: confirmed_count=1 with hysteresis=2 should return False
    - Test T0 estimate timing: check with various time_to_t0 values
  - _Expected_Behavior: should_trigger_spam logic from Property 3_
  - _Preservation: network T0 always has priority (3.4), hysteresis is enforced (3.5)_
  - _Requirements: 2.3, 3.4, 3.5_

#### Sub-task 3.5 Refactor _handle_watch_timer to integrate adaptive interval and CPU pause

- [x] 3.5 Refactor _handle_watch_timer() with new state management
  - Location: `mvp/bot/macro_engine.py`, function `_handle_watch_timer`
  - Add state dictionaries:
    ```python
    ocr_interval_state = {
        "current_interval": initial_interval,
        "last_query_time": None,
        "timer_history": [],  # List of {"value": ..., "time": ...}
    }
    
    spam_prep_state = {
        "confirmed_count": 0,  # Number of confirmed timer <= spam_threshold
        "estimated_t0_mono": None,
        "spam_prepared": False,
    }
    
    cpu_pause_state = {
        "active": False,
        "start_time": None,
    }
    ```
  - Main FAST loop changes:
    - Calculate `time_since_last_query = now() - ocr_interval_state.last_query_time`
    - Check if `time_since_last_query >= ocr_interval_state.current_interval`
    - If yes: update interval via `calculate_adaptive_interval()`
    - Call `_read_timer_value(skip_ocr=cpu_pause_state.active)` with skip_ocr flag
    - Update `ocr_interval_state.timer_history` with new reading
    - Check if `cpu_pause_state.active` should be enabled (when estimated_t0_mono is close)
    - Call `should_trigger_spam()` with all necessary flags
  - _Bug_Condition: isBugCondition where phase==FAST_
  - _Expected_Behavior: Adaptive interval (Property 1), CPU pause (Property 2), proactive prep (Property 3)_
  - _Preservation: Existing logic for jumps, inactivity, hysteresis is unchanged (Property 4)_
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5_

#### Sub-task 3.6 Update _read_timer_value() to respect skip_ocr flag

- [x] 3.6 Update _read_timer_value() to support CPU pause window
  - Location: `mvp/bot/macro_engine.py`, function `_read_timer_value`
  - Add parameter: `skip_ocr: bool = False`
  - Logic:
    - If `skip_ocr=True`: return `last_known_value` without executing new OCR query
    - If `skip_ocr=False`: execute OCR query as normal
  - _Expected_Behavior: CPU pause window (Property 2)_
  - _Preservation: When skip_ocr=False, behavior is identical to original_
  - _Requirements: 2.2, 2.4_

#### Sub-task 3.7 Add proactive spam preparation using monotonic T0 estimate

- [x] 3.7 Implement monotonic T0 estimate and proactive spam prep
  - Location: `mvp/bot/macro_engine.py`, in _handle_watch_timer FAST loop
  - Logic:
    - When timer value arrives: check if `timer <= spam_threshold`
    - If yes: increment `spam_prep_state.confirmed_count`
    - If `confirmed_count >= hysteresis_confirmations` (and first time reaching this):
      - Calculate `avg_delta = calculate_avg_delta(ocr_interval_state.timer_history)`
      - Extrapolate: `estimated_t0_mono = now() + (timer_value / avg_delta)` 
      - Set `spam_prep_state.estimated_t0_mono` (once set, lock it until phase change)
      - Set `spam_prep_state.spam_prepared = True`
    - Use `estimated_t0_mono` in `should_trigger_spam()` decision
  - _Expected_Behavior: Proactive spam preparation (Property 3)_
  - _Requirements: 2.3_

---

## Phase 4: Verification

### Task 4. Verify Bug Condition Exploration Test Now Passes

- [x] 4. Verify bug condition exploration test now passes
  - **Property 1: Expected Behavior** - OCR Bottleneck and CPU Spike Resolution
  - **CRITICAL**: Re-run the SAME test from Task 1 — do NOT write a new test
  - **Why**: The test from Task 1 encodes the expected behavior; when it passes, the bug is fixed
  
  - Run exploration test from Task 1 on FIXED code
  - EXPECTED OUTCOME: Test NOW PASSES (this confirms the bug is fixed and expected behavior is satisfied)
  - Assert on fixed code:
    - Total OCR queries: <100 (reduced from ~1475)
    - CPU load in last 5s: <30% (reduced from >80%)
    - Spam trigger latency: <0.2s (reduced from 0.3-0.8s)
  
  - _Requirements: Expected Behavior Properties 1, 2, 3 from design_

### Task 5. Verify Preservation Tests Still Pass

- [x] 5. Verify preservation tests still pass
  - **Property 2: Preservation** - Non-Buggy Behaviors Remain Unchanged
  - **CRITICAL**: Re-run the SAME tests from Task 2 — do NOT write new tests
  - **Why**: These tests confirm no regressions in other features
  
  - Run preservation tests from Task 2 on FIXED code
  - EXPECTED OUTCOME: All tests PASS (confirms no regressions)
  - Verify:
    - Jump detection still works identically
    - Inactivity timeout still works identically
    - OCR error handling still works identically
    - Network T0 priority still works identically
    - Hysteresis enforcement still works identically
  
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

---

## Phase 5: Unit & Integration Testing

### Task 6. Unit Tests for Adaptive Interval Calculations

- [x] 6. Unit tests for new calculation functions
  - Test `calculate_adaptive_interval()`:
    - Test case 1: time_remaining=300s, initial_interval=1.0s → expect 1.0s
    - Test case 2: time_remaining=5s, accel_threshold=10s, min_interval=0.2s → expect interpolated value
    - Test case 3: time_remaining=0s → expect min_interval
    - Edge case: time_remaining > accel_threshold → expect initial_interval
    - Edge case: time_remaining = accel_threshold → expect somewhere between
  
  - Test `calculate_avg_delta()`:
    - Test case 1: smooth descent [100s, 99s, 98s] at 1s intervals → avg_delta ≈ 1.0s
    - Test case 2: varying intervals [100s, 98.5s, 97.1s] → correct weighted average
    - Test case 3: with None values → skip gracefully
    - Test case 4: with jumps (|delta|>2s) → skip jumps, average only smooth deltas
  
  - Test `should_trigger_spam()`:
    - Test case 1: network_t0_triggered=True → return True (regardless of other params)
    - Test case 2: network_t0_triggered=False, ocr_timer_value=3s, confirmed_count=2, hysteresis=2 → return True
    - Test case 3: network_t0_triggered=False, ocr_timer_value=3s, confirmed_count=1, hysteresis=2 → return False (hysteresis not met)
    - Test case 4: estimated_t0_mono set, current_time ≈ T0 (within ±0.2s) → return True
    - Edge case: all flags False → return False
  
  - Test CPU pause window state machine:
    - Test activation when estimated_t0_mono known and close
    - Test deactivation after CPU pause window expires
  
  - _Requirements: 2.1, 2.3, 2.4_

### Task 7. Property-Based Tests with Hypothesis (Preservation Guarantees)

- [x] 7. Property-based tests for broader coverage
  - Property A: Monotonic Timer Descent → Adaptive Interval Scaling
    - Generate sequences: monotonic descents from 300s to spam_threshold with random intervals
    - Assert: For each FAST phase interval, interval <= previous interval (monotonic decrease OR resets on jump)
    - Assert: No OCR query fires before calculated interval has passed
  
  - Property B: Multiple Confirmations → T0 Estimate Locked
    - Generate sequences with 2+ confirmations of timer ≤ spam_threshold
    - Assert: `estimated_t0_mono` is calculated and doesn't change across subsequent confirmations
    - Assert: Extrapolated T0 is within ±1s of simulated ground truth
  
  - Property C: Spam Trigger Timing
    - Generate sequences with known T0 (simulated dropout)
    - Assert: Spam is triggered within ±0.3s of T0
    - Assert: Network T0 signal (`\x58\x01`) always takes priority
  
  - Property D: Non-Buggy Inputs Preserved
    - Generate timer sequences WITHOUT bug conditions (timer > fast_threshold, or error cases)
    - Assert: Fixed behavior matches original behavior for all non-buggy inputs
  
  - Use Hypothesis strategies: random timer values, jump patterns, None/error patterns
  - Run with Hypothesis profile: 200+ examples per property
  
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

### Task 8. Integration Tests

- [x] 8. Integration tests for full countdown scenarios
  
  - Test 8.1: Full Countdown 300s → 0s
    - Simulate complete countdown with mocked network and OCR
    - Assert: Spam triggered within ±0.3s of T0
    - Assert: CPU load remains <40% throughout (adaptive interval + CPU pause)
  
  - Test 8.2: Countdown with Timer Jump
    - Simulate countdown, inject jump (e.g., +5s at 50s remaining)
    - Assert: Phase resets to IDLE, T0 estimate clears, confirmed_count resets
    - Assert: System recovers and continues countdown normally
  
  - Test 8.3: Countdown with OCR Errors
    - Simulate countdown, inject `_read_timer_value()` returning None periodically
    - Assert: System falls back to `last_known_value`
    - Assert: Countdown continues, spam triggers correctly despite errors
  
  - Test 8.4: Multiple Countdowns in Sequence
    - Simulate IDLE → FAST → SPAM → IDLE → FAST → SPAM
    - Assert: State resets properly between countdowns
    - Assert: Each countdown completes normally with adaptive behavior
  
  - Test 8.5: Network T0 Signal Priority
    - Simulate countdown with network `\x58\x01` arriving mid-FAST
    - Assert: Spam triggered immediately on network signal
    - Assert: Spam trigger time matches network signal time (within ±0.1s)
  
  - _Requirements: All properties validated end-to-end_

---

## Phase 6: Documentation & Finalization

### Task 9. Documentation and Code Comments

- [x] 9. Add comprehensive documentation
  - Document new fields in `MacroStep` with examples
  - Document new state dictionaries in `_handle_watch_timer` with initialization code
  - Add inline comments explaining:
    - Adaptive interval calculation and threshold logic
    - CPU pause window conditions and skip_ocr flag
    - Monotonic T0 estimation algorithm
    - Priority order in `should_trigger_spam()`
  - Document breaking changes or configuration impacts (if any)
  - Add example configuration snippets in docstring
  
  - _Requirements: Code maintainability and understanding_

### Task 10. Final Verification & PR Preparation

- [x] 10. Final verification before PR
  - Run full test suite: `uv run pytest -m "not slow"`
  - Verify all tests pass (exploration, preservation, unit, integration)
  - Check code style: `uv run ruff check .` and `uv run ruff format --check .`
  - Verify no regressions: Compare test results on original code vs fixed code
  - Confirm all requirements (2.1-2.4, 3.1-3.5) are met
  - Prepare commit message and PR description
  
  - _Requirements: All acceptance criteria validated_

---

## Summary

**Task Structure:**
1. ✓ Exploratory bug condition test (Task 1) — FAILS on unfixed code
2. ✓ Preservation property tests (Task 2) — PASS on unfixed code
3. ✓ Implementation (Task 3) — 7 sub-tasks covering all 7 changes from design
4. ✓ Bug verification (Task 4) — Re-run Task 1, now PASSES on fixed code
5. ✓ Preservation verification (Task 5) — Re-run Task 2, still PASS on fixed code
6. ✓ Unit tests (Task 6) — New functions and state machines
7. ✓ Property-based tests (Task 7) — Broader coverage with Hypothesis
8. ✓ Integration tests (Task 8) — Full countdown scenarios
9. ✓ Documentation (Task 9) — Code comments and docstrings
10. ✓ Final verification (Task 10) — Test suite, code style, PR prep

**Test Validation Order:**
- Before fix: Property 1 FAILS (confirms bug), Property 2 PASS (baseline)
- After fix: Property 1 PASS (bug fixed), Property 2 still PASS (no regressions)
- Unit/Integration: All passing, requirements 2.1-2.4 and 3.1-3.5 validated
