# Integration Tests Documentation

## Overview

Integration tests validate real bot macro engine functionality against simulated game environment. Two tiers available:

- **Smoke tests** (5-10 scenarios, <10s): Quick validation during development
- **Full hybrid tests** (30-50 scenarios, 3-5 min): Comprehensive validation with multi-monitor, clipping, CPU profiling

---

## Smoke Test vs Full Test

### Smoke Test (`test_smoke.py`)

**Purpose:** Quick validation that basic macro flow works correctly

**Coverage:**
- 5-10 scenarios, all single-monitor, full-size (1024x768+)
- Standard timers (5s, 30s, 300s)
- No clipping, no multi-monitor, no edge cases
- Basic metrics: clicks, OCR, timer, spam CPS

**Runtime:** < 10 seconds

**Metrics collected:**
- Click accuracy (expected > 90%)
- OCR precision (expected 85-90%)
- Timer accuracy (expected < 5% error)
- Spam CPS (expected 38-39)
- Basic CPU % (no detailed profiling)

**When to use:**
- Quick sanity check during development
- CI pipeline (pre-commit validation)
- Before running expensive full suite

**Expected outcome:**
```
test_smoke.py::test_smoke_baseline PASSED
test_smoke.py::test_smoke_timer_variants PASSED
test_smoke.py::test_smoke_chat_states PASSED
test_smoke.py::test_smoke_window_positions PASSED
test_smoke.py::test_smoke_dpi_scaling PASSED

===== 5 passed in 8.43s =====
Pass rate: 100% (5/5)
```

### Full Hybrid Test (`test_macro_hybrid.py`)

**Purpose:** Comprehensive validation with adaptive sampling, multi-monitor, clipping, CPU profiling

**Coverage:**
- 30-50 scenarios generated with adaptive sampling
- 70% single-monitor (baseline)
- 20% multi-monitor (same DPI + different DPI)
- 10% clipped windows (800x600, 640x480)
- Edge cases: spanning, offscreen, high jitter, glitches
- Full CPU profiling: hot-spots, bottleneck detection
- Memory monitoring

**Runtime:** 3-5 minutes (includes CPU profiling overhead)

**Metrics collected:**
- Click accuracy, deviation distribution
- OCR precision, detectable elements %
- Timer accuracy, error distribution
- Spam CPS, delivery rate
- CPU: load classification, hot-spots, bottleneck detection
- Memory: peak, allocations, deallocations
- Multi-monitor: coordinate transform latency, DPI mismatch impact
- Clipping: detectable elements %, adjusted thresholds

**Reporting:**
- Console: per-run summaries + hot-spots
- HTML dashboard: metrics distribution, bottleneck timeline, multi-monitor results
- SQLite: structured data for queries and trend analysis

**When to use:**
- Pre-commit validation (comprehensive)
- Nightly CI runs
- Release validation
- Performance regression detection
- Multi-monitor validation
- Bottleneck investigation

**Expected outcome:**
```
test_macro_hybrid.py::test_orchestrator_baseline PASSED
test_macro_hybrid.py::test_orchestrator_sampling PASSED

===== 2 passed in 234.56s =====

=== Hybrid Macro Integration Test Suite Summary ===
Total runs: 45
Passed: 43 (95.6%)
Failed: 2

CPU Distribution:
  IDLE: 5 runs (11%)
  LOW: 15 runs (33%)
  MEDIUM: 18 runs (40%)
  HIGH: 5 runs (11%)
  CRITICAL: 2 runs (4%) ⚠️

Multi-Monitor Tests: 9 runs (20%)
Clipped Tests: 4 runs (9%)

Reports:
  - test_results.html (dashboard)
  - test_results.db (SQLite)
  - htmlcov/ (coverage)
```

### Choosing Between Tests

| Scenario | Test | Runtime | Reason |
|----------|------|---------|--------|
| Quick check during development | Smoke | <10s | Fast feedback loop |
| Pre-commit validation | Smoke | <10s | Gates commits |
| Pre-release validation | Full | 3-5 min | Comprehensive validation |
| Nightly CI | Full | 3-5 min | Catch regressions, trends |
| Performance investigation | Full | 3-5 min | CPU profiling, bottlenecks |
| Multi-monitor testing | Full | 3-5 min | Multi-monitor scenarios included |
| Quick PR check (CI) | Smoke | <10s | Fast CI pipeline |
| Detailed regression report | Full | 3-5 min | SQLite trends, comparisons |

---

## Running Tests

### Smoke Test

```bash
cd /f:/PROJEKTY/joaxx
uv run pytest mvp/tests/integration/test_smoke.py -v
```

**Output:**
```
mvp/tests/integration/test_smoke.py::test_smoke_baseline PASSED                [ 20%]
mvp/tests/integration/test_smoke.py::test_smoke_timer_variants PASSED         [ 40%]
mvp/tests/integration/test_smoke.py::test_smoke_chat_states PASSED            [ 60%]
mvp/tests/integration/test_smoke.py::test_smoke_window_positions PASSED       [ 80%]
mvp/tests/integration/test_smoke.py::test_smoke_dpi_scaling PASSED            [100%]

===== 5 passed in 8.43s =====
```

### Full Hybrid Test

```bash
cd /f:/PROJEKTY/joaxx
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v
```

**Output includes:**
- Per-run metrics (baseline phase)
- Per-run metrics (sampling phase)
- HTML report path
- SQLite database path

### With Coverage

```bash
uv run pytest mvp/tests/integration/ --cov=mvp --cov-report=html
```

Opens `htmlcov/index.html` with interactive coverage map.

### With Memory Profiling

```bash
uv run scalene mvp/tests/integration/test_smoke.py
```

Shows per-line CPU and memory usage.

---

## Multi-Monitor Testing

### System Requirements

**Single monitor (baseline):**
- No setup needed
- Scenario randomizer simulates monitor state

**Dual physical monitors (recommended):**
- Monitor 0: 1920x1080 @ 96 DPI (primary)
- Monitor 1: 1920x1080 @ 96 DPI (secondary)

**Dual monitors with different DPI (advanced):**
- Monitor 0: 1920x1080 @ 96 DPI (primary)
- Monitor 1: 1920x1080 @ 144 DPI (secondary, 1.5x scaling)

### How Tests Handle Multi-Monitor

**Automatic:** Framework detects system monitors and generates appropriate scenarios

**Simulated:** If only one physical monitor exists:
- Scenarios still include multi-monitor configs
- `MultiMonitorSimulator` creates virtual monitors
- Bounding boxes and coordinate transforms simulated
- Tests remain valid (coordinate transform logic verified)

### Setup for Actual Multi-Monitor Testing

**Step 1: Configure monitors in Windows**
```
Settings > System > Display > Multiple displays
  Position displays in logical arrangement
  Configure scaling per monitor (100%, 125%, 150%)
```

**Step 2: Run full hybrid test**
```bash
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v
```

**Step 3: Check multi-monitor metrics in HTML report**
- Dashboard shows multi-monitor results separate from single-monitor
- Coordinate transform latency measured
- DPI scaling impact quantified

### Expected Results

**Same-DPI monitors:**
- Pass rate: ≥ 90%
- Click accuracy: unchanged (coordinate transform transparent)
- OCR precision: unchanged
- Coordinate transform latency: < 5ms
- CPU overhead: +0-5% vs single-monitor

**Different-DPI monitors:**
- Pass rate: 80-85%
- Click accuracy: 85-90% (some DPI scaling artifacts)
- OCR precision: 82-87%
- Coordinate transform latency: 5-10ms
- CPU overhead: +5-10% vs single-monitor
- DPI mismatch errors: < 5% of clicks acceptable

### Interpreting Multi-Monitor Metrics

**From console output:**
```
Multi-Monitor:
  - Monitor count: 2 (primary 96 DPI, secondary 144 DPI)
  - Coordinate transform: 3.2ms ✓
  - Clicks: 19/20 accurate
  - DPI mismatch: none
  - OCR precision: 85% (vs 87% baseline)
```

**From SQLite:**
```sql
SELECT monitor_count, ROUND(AVG(coord_transform_time_ms), 2), click_on_wrong_monitor
FROM multi_monitor_metrics
GROUP BY monitor_count;
```

**From HTML dashboard:**
- Graph: DPI mismatch impact on click accuracy
- Table: Monitor-specific OCR precision
- Timeline: Which runs tested multi-monitor

---

## CPU Bottleneck Analysis

### When Bottlenecks Detected

Framework automatically identifies and reports:
1. **CPU bottleneck** — macro taking > 70% CPU
2. **Memory bottleneck** — peak memory > 3x baseline
3. **OCR slow-down** — OCR call > 300ms
4. **Click drift** — coordinate transform errors
5. **Coordinate transform overhead** — transform taking > 20ms

### Example: Diagnosing OCR Bottleneck

**Console output:**
```
Run #8: [CPU 75% (CRITICAL)] ⚠️ Hot-spots:
  - bot.ocr.detect: 1240ms (52%)
  - bot.clicker.click_at: 480ms (20%)
  - bot.capture.get_frame: 360ms (15%)
  - game_sim.process_click: 220ms (9%)
```

**Analysis:**
1. OCR consuming 52% of runtime → bottleneck identified
2. Check SQLite for pattern:
   ```sql
   SELECT scenario_json, cpu_time_ms
   FROM bottlenecks b JOIN runs r ON b.run_id=r.id
   WHERE function_name LIKE '%ocr%'
   ORDER BY cpu_time_ms DESC;
   ```
3. Check which scenarios trigger high OCR time (e.g., high-DPI, large window?)
4. Profile OCR specifically:
   ```bash
   uv run scalene --cpu mvp/bot/ocr.py
   ```
5. Identify slow lines (template matching, image preprocessing)
6. Optimize identified lines
7. Re-run suite and verify CPU % improvement

### Example: Diagnosing Click Drift

**Symptom:** Console shows click accuracy < 85% on multi-monitor run

**Investigation:**
```sql
-- Get multi-monitor run details
SELECT run_id, click_on_wrong_monitor, coord_transform_time_ms
FROM multi_monitor_metrics
WHERE click_on_wrong_monitor > 0;
```

**Check:**
1. Are clicks landing on wrong monitor? (click_on_wrong_monitor > 0)
2. Is coordinate transform slow? (coord_transform_time_ms > 10ms)
3. What DPI mismatch? (different scaling factors?)

**Common fixes:**
- Verify monitor detection (WinAPI GetMonitorInfo)
- Check coordinate transform matrix calculation
- Ensure click target valid before sending to WinAPI

### Example: Diagnosing Memory Spike

**Symptom:** Memory baseline 100MB, spike to 400MB on run #12

**Investigation:**
```sql
-- Find run with memory spike
SELECT id, memory_peak_mb, scenario_json
FROM runs
WHERE memory_peak_mb > 300;
```

**Check:**
1. What scenario triggered spike?
2. Is it repeatable? (run same scenario again)
3. Which component allocating memory? (check profiling logs)

**Common fixes:**
- Implement LRU cache for frame storage
- Stream results instead of accumulating all
- Release frame buffers after processing

### Hot-Spot Interpretation

**Per-function breakdown:**

```
Hot-spot: bot.ocr.detect: 1240ms (52%)
```

Means: Of 2400ms total macro runtime, OCR took 1240ms (52%)

**Action table:**

| Hot-spot % | Action |
|-----------|--------|
| < 20% | Normal, monitor |
| 20-30% | Watch, may become bottleneck |
| 30-50% | Concerning, profile function |
| > 50% | Bottleneck, optimize immediately |

### Common Bottleneck Causes

| Bottleneck | Cause | Fix |
|-----------|-------|-----|
| OCR high | Template matching slow | Cache results, reduce image size |
| Click high | WinAPI frequency high | Batch operations, throttle |
| Memory spike | Frame cache unbounded | Implement LRU, limit history |
| Coordinate transform slow | Matrix calculation inefficient | Pre-compute, vectorize |
| Frame capture slow | Large window, slow renderer | Reduce resolution, simplify rendering |

---

## Test Execution Examples

### Example 1: Quick Smoke Test

```bash
$ uv run pytest mvp/tests/integration/test_smoke.py -v
```

**Output:**
```
mvp/tests/integration/test_smoke.py::test_smoke_baseline PASSED          [100%]

===== 1 passed in 8.12s =====

Suite passed! ✓
```

### Example 2: Full Hybrid with CPU Profiling

```bash
$ uv run pytest mvp/tests/integration/test_macro_hybrid.py -v
```

**Output (first 5 runs):**
```
Run #1: 1024x768 @ (448,136) [Monitor 0, 96 DPI] Timer=300s
✓ PASS
Clicks: 20/20 accurate (avg +5.2px)
OCR: 87% precision (5 detections)
Timer: 300.0s ✓
Spam: 38.2 CPS
CPU: 32% avg (LOW)
Memory: 138MB peak

Run #2: 1024x768 @ (100,200) [Monitor 0, 96 DPI] Timer=30s
✓ PASS
Clicks: 4/4 accurate (avg +2.1px)
OCR: 100% precision (2 detections)
Timer: 30.0s ✓
Spam: 38.5 CPS
CPU: 29% avg (LOW)
Memory: 142MB peak

... 3 more baseline runs ...

===== Baseline Phase Complete (5/5 passed) =====
CPU Distribution: 100% LOW (0-30%)
Memory: 120-150MB (normal)

Starting Sampling Phase...

Run #6: 800x600 @ (100,100) [clipped] Timer=300s
✓ PASS (clipped)
OCR: 68% precision (detectable 60% of UI)
Clicks: 18/20 accurate (on visible elements)
Spam: 22.1 CPS (lower due to clipping)
CPU: 31% avg (LOW)
Memory: 145MB peak

Run #7: 1024x768 @ (1900,100) [Monitor 1, 96 DPI] Timer=300s
✓ PASS (multi-monitor)
Coordinate transform: 2.8ms ✓
Clicks: 20/20 accurate
OCR: 86% precision
CPU: 35% avg (MEDIUM)
Memory: 149MB peak

... 38 more sampling runs ...

===== Sampling Phase Complete (40/40 passed) =====
```

**Final summary:**
```
=== Hybrid Macro Integration Test Suite ===
Total runs: 45
Passed: 44 (97.8%)
Failed: 1

CPU Distribution:
  IDLE: 8 (18%)
  LOW: 18 (40%)
  MEDIUM: 14 (31%)
  HIGH: 4 (9%)
  CRITICAL: 1 (2%) ⚠️

Reports generated:
  - test_results.html (dashboard)
  - test_results.db (SQLite)

===== 2 passed in 234.56s =====
```

### Example 3: With Coverage Report

```bash
$ uv run pytest mvp/tests/integration/ --cov=mvp --cov-report=html
```

**Output:**
```
coverage: platform win32, Python 3.11.5, pytest-8.0.0, py-1.13.0, pluggy-1.1.1
cachedir: .pytest_cache
rootdir: /f:/PROJEKTY/joaxx

mvp/tests/integration/test_smoke.py::test_smoke_baseline PASSED
mvp/tests/integration/test_macro_hybrid.py::test_orchestrator_baseline PASSED
mvp/tests/integration/test_macro_hybrid.py::test_orchestrator_sampling PASSED

===== 3 passed in 243.67s =====

Coverage report:
  mvp/bot/clicker.py: 98%
  mvp/bot/ocr.py: 95%
  mvp/bot/engine.py: 92%
  ... (full coverage matrix)

HTML report generated: htmlcov/index.html
```

Open `htmlcov/index.html` in browser to see interactive coverage map.

---

## Framework Fixtures (conftest.py)

### Available Fixtures

#### `bot_runner`

Provides real MacroEngine instance with simulated game environment.

```python
def test_macro_step(bot_runner):
    """Test macro step execution."""
    # bot_runner.macro_engine — real MacroEngine instance
    # bot_runner.game_simulator — simulated game state
    # bot_runner.renderer — screen renderer
    
    scenario = bot_runner.create_scenario(
        window_size=(1024, 768),
        timer_seconds=300
    )
    result = bot_runner.execute_step()
    assert result.success
```

#### `macro_engine`

Real bot MacroEngine configured for testing.

```python
def test_click_dispatch(macro_engine):
    """Test click dispatch through macro engine."""
    macro_engine.dispatch_step()  # Execute one macro step
```

#### `game_simulator`

Simulated game environment with state management.

```python
def test_game_state(game_simulator):
    """Test game state updates."""
    game_simulator.tick()  # Advance game state
    state = game_simulator.get_state()
    assert state.timer_seconds > 0
```

#### `metrics_collector`

Metrics collection with deviations and bottleneck detection.

```python
def test_metrics_collection(metrics_collector):
    """Test metrics collection."""
    metrics = metrics_collector.collect()
    assert metrics.click_accuracy > 0.80
    assert metrics.cpu_percent < 70
```

#### `orchestrator`

Test orchestrator with adaptive sampling.

```python
def test_orchestrator(orchestrator):
    """Test orchestrator adaptive logic."""
    result = orchestrator.run_suite()
    assert result.pass_rate >= 0.90
```

### Using Fixtures in Tests

```python
def test_macro_with_high_dpi(bot_runner, metrics_collector):
    """Test macro execution at high DPI."""
    scenario = bot_runner.scenario_randomizer.generate(
        dpi=144,
        window_size=(1920, 1080)
    )
    bot_runner.execute_scenario(scenario)
    metrics = metrics_collector.collect()
    
    # Verify high-DPI handling
    assert metrics.click_accuracy > 0.85
    assert metrics.coordinate_transform_ms < 10
```

---

## Troubleshooting

### Test Hangs or Times Out

**Symptom:** Test runs > 15s per scenario

**Causes:**
1. Game simulator stuck waiting for condition
2. Macro engine infinite loop
3. Frame rendering slow on low-end hardware

**Fix:**
1. Check timeout setting (default 15s per run)
2. Profile frame rendering: `uv run scalene test_macro_hybrid.py`
3. Reduce scenario complexity (window size, DPI)

### Tests Fail with OCR Errors

**Symptom:** "OCR detection failed" or precision < 50%

**Causes:**
1. Clipped window (element off-screen) — expected
2. OCR model not loaded
3. Synthetic frame generation issue

**Fix:**
1. Check if scenario marked as `viewport_clip=True` (expected)
2. Verify OCR model file exists: `mvp/assets/ocr_model.onnx`
3. Run `test_game_simulator.py` to verify frame rendering

### Tests Fail with Click Accuracy < 80%

**Symptom:** Clicks landing far from targets

**Causes:**
1. Coordinate transform error (multi-monitor)
2. Window position changed during test
3. DPI scaling factor wrong

**Fix:**
1. Check multi-monitor config in scenario
2. Verify window stays at same position during test
3. Run `test_multi_monitor_sim.py` to debug coordinate transforms

### Memory Grows Over Tests

**Symptom:** Memory increases from 100MB to 500MB+ over suite

**Causes:**
1. Frame cache unbounded
2. Scenario history accumulated
3. Profiling data not cleaned up

**Fix:**
1. Check `metrics_collector.cleanup()` called after each run
2. Verify frame cache has size limit
3. Run `uv run pytest --cov` to test with coverage (may use more memory)

### HTML Report Missing or Broken

**Symptom:** `test_results.html` not created or shows errors

**Causes:**
1. Reporter not initialized
2. SQLite database locked
3. File permission issue

**Fix:**
1. Check test completed without errors
2. Verify `mvp/tests/integration/` writable
3. Check SQLite database not corrupted: `sqlite3 test_results.db "SELECT COUNT(*) FROM runs;"`

---

## Performance Tips

### Faster Smoke Test Iteration

```bash
# Run only baseline smoke test (< 5s)
uv run pytest mvp/tests/integration/test_smoke.py::test_smoke_baseline -v
```

### Faster Full Suite

```bash
# Skip profiling for quick pass/fail check
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v --tb=short
```

### Parallel Test Execution

Framework does NOT use parallel execution (tests write to shared files). Run sequentially:

```bash
uv run pytest mvp/tests/ -v -n 1
```

### Reduce Memory Usage

```bash
# Limit test suite size
export MAX_RUNS=10
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v
```

---

## Quick Reference

### Commands

```bash
# Smoke test (quick)
uv run pytest mvp/tests/integration/test_smoke.py -v

# Full hybrid (thorough)
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v

# With coverage
uv run pytest mvp/tests/integration/ --cov=mvp --cov-report=html

# With profiling
uv run scalene mvp/tests/integration/test_smoke.py

# Framework tests only
uv run pytest mvp/tests/test_framework/ -v
```

### Files Generated

| File | Purpose |
|------|---------|
| `test_results.html` | Interactive dashboard (pass rate, CPU, bottlenecks) |
| `test_results.db` | SQLite database (structured data for analysis) |
| `htmlcov/` | Code coverage report (if run with `--cov`) |

### Key Metrics

| Metric | Smoke | Full |
|--------|-------|------|
| Pass rate | ≥ 95% | ≥ 90% |
| Click accuracy | > 90% | > 90% |
| OCR precision | 85-90% | 85-90% |
| Spam CPS | 38-39 | 38-39 |
| Runtime | < 10s | 3-5 min |

### When to Use Which

| Task | Test | Time |
|------|------|------|
| Development iteration | Smoke | <10s |
| Pre-commit gate | Smoke | <10s |
| Bottleneck diagnosis | Full | 3-5 min |
| Multi-monitor validation | Full | 3-5 min |
| Regression detection | Full | 3-5 min |
| Performance trend | Full | 3-5 min |
