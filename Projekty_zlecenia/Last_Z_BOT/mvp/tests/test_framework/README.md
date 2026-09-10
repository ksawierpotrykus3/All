# Test Framework Documentation

## Overview

The Hybrid Macro Integration Test Framework validates the real bot macro engine against a simulated game environment. It generates randomized test scenarios with adaptive sampling, collecting comprehensive metrics on clicks, OCR precision, timer accuracy, CPU usage, and performance bottlenecks.

**Key Philosophy:** Real bot engine (WinAPI clicks, OCR, macro dispatch) + Simulated game (fast, deterministic, data-driven) = Production confidence without flakiness.

---

## Architecture

### Component Stack

```
Test Orchestrator (adaptive + CPU-aware sampling)
  ├─ Monitors system state, DPI, monitor layout
  ├─ Baseline phase (10 runs): establish performance targets
  ├─ Adaptive phase: decide sampling strategy
  └─ Sampling phase (10-20 runs): multi-monitor, clipped, edge cases

Scenario Randomizer
  ├─ Single-monitor (70%): standard window configs
  ├─ Multi-monitor (20%): DPI scaling, boundary cases
  └─ Clipped (10%): small windows with UI cut off

Bot Macro Engine (REAL)
  ├─ Real MacroEngine.dispatch_step()
  ├─ Real WinAPI clicks (to simulated hwnd)
  ├─ Real OCR on synthetic frames
  └─ CPU profiling: scalene traces every function

Game Simulator (SYNTHETIC)
  ├─ GameStateSimulator: manages chat, timers, events
  ├─ ScreenRenderer: PNG templates + dynamic content + viewport clipping
  ├─ MultiMonitorSimulator: 2+ monitors with independent DPI scaling
  └─ MockHTTPServer: localhost:8888 API responses

Metrics Collector
  ├─ Behavioral: click accuracy, OCR precision, timer accuracy
  ├─ CPU profiling: hot-spots, load classification, bottleneck detection
  ├─ Memory: peak usage, allocations, deallocations
  ├─ Multi-monitor: coordinate transform overhead, DPI mismatch impact
  └─ Adaptive thresholds: adjusted for clipped windows

Reporters
  ├─ Console: real-time summaries with hot-spots (when CPU > 50%)
  ├─ HTML: interactive dashboard (CPU trends, bottlenecks, multi-monitor results)
  └─ SQLite: structured data for queries and historical trends
```

---

## How to Run Tests

### Prerequisites

```bash
uv sync --extra dev
```

Ensures all dev dependencies are installed (pytest, pytest-cov, scalene, debugpy).

### Run Full Test Suite

```bash
cd /f:/PROJEKTY/joaxx
uv run pytest mvp/tests/test_framework/ -v
uv run pytest mvp/tests/integration/ -v
```

**Expected output:**
- ~50 framework unit tests (metrics, scenarios, profiling)
- ~300+ integration tests (smoke, hybrid macro scenarios)
- Total runtime: 10-15 seconds (no profiling overhead in unit tests)

### Run Only Framework Tests

```bash
uv run pytest mvp/tests/test_framework/ -v
```

Tests:
- `test_scenarios.py`: scenario randomizer, clipping logic, multi-monitor configs
- `test_metrics.py`: metrics collection, deviation detection, bottleneck classification
- `test_cpu_profiler.py`: CPU profiling integration with scalene
- `test_game_simulator.py`: game state simulation, frame rendering
- `test_multi_monitor_sim.py`: multi-monitor coordinate transforms, DPI scaling
- `test_orchestrator.py`: adaptive sampling, baseline vs sampling phases

### Run Only Integration Tests

```bash
uv run pytest mvp/tests/integration/ -v
```

Tests:
- `test_smoke.py`: quick validation (5-10 scenarios, <5s)
- `test_macro_hybrid.py`: full integration suite (30-50 scenarios, 3-5 min)

### Run Smoke Test (Fast)

```bash
uv run pytest mvp/tests/integration/test_smoke.py -v
```

**Runtime:** < 10 seconds  
**Scenarios:** 5-10 baseline runs (single-monitor, full-size, standard timers)  
**Use case:** Quick validation during development or CI

### Run Full Hybrid Test (Thorough)

```bash
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v
```

**Runtime:** 3-5 minutes  
**Scenarios:** 30-50 runs (baseline + adaptive sampling + multi-monitor)  
**Use case:** Pre-commit verification, nightly CI, release validation

### Run with Coverage

```bash
uv run pytest mvp/tests/ --cov=mvp --cov-report=html --cov-report=term-missing
```

**Output:** `htmlcov/index.html` (interactive coverage map)

### Run with Performance Profiling

```bash
# Profile a single test
uv run scalene mvp/tests/integration/test_smoke.py

# Profile with memory details
uv run scalene --memory --cpu mvp/tests/integration/test_macro_hybrid.py
```

**Output:** Terminal report with CPU/memory per line

---

## Interpreting Test Reports

### Console Output

Each run prints a summary:

```
Run #1: 1024x768 @ (448,136) [Monitor 0, 96 DPI] Timer=300s
✓ PASS
Clicks: 20/20 accurate (avg +5.2px deviation)
OCR: 85% precision (5 detections, 1 miss)
Timer: 300.0s ✓ perfect
Spam: 38.2 CPS (266/266 clicks delivered)
CPU: 35% avg (MEDIUM) ⚠️ Hot-spots:
  - bot.clicker.click_at: 42ms (35%)
  - bot.capture.get_frame: 28ms (23%)
  - bot.ocr.detect: 22ms (18%)
Memory: 145MB peak (normal)
Multi-Monitor: N/A (single monitor)
```

**Fields explained:**

- **PASS/FAIL:** Run outcome
- **Clicks:** Total sent vs accurate. Deviation = distance from center of target (px)
- **OCR:** Precision = correct_detections / attempts. Detectable elements adjusted for clipping
- **Timer:** Expected vs actual. Error % < 10% is acceptable
- **Spam:** Clicks per second (CPS). Expected 38.2 CPS on 60 FPS game. Lower on clipped windows
- **CPU:** Average CPU % during macro. Load class: IDLE (0-10%), LOW (10-30%), MEDIUM (30-50%), HIGH (50-70%), CRITICAL (70%+)
- **Hot-spots:** Functions consuming most CPU (only shown if CPU > 50%)
- **Memory:** Peak memory usage. Spike > 3x baseline triggers memory bottleneck detection

### Multi-Monitor Output Example

```
Run #8: 1024x768 @ (1900,100) [Monitor 1, 144 DPI] Timer=300s
✓ PASS (multi-monitor)
...
Multi-Monitor:
  - Monitor count: 2 (primary 96 DPI, secondary 144 DPI)
  - Coordinate transform: 3.2ms (normal)
  - Clicks: 19/20 on Monitor 1, 1/20 on Monitor 0 (expected routing)
  - DPI mismatch impact: none (scaling accurate)
  - OCR precision: 82% (slightly lower due to DPI scaling artifacts)
```

### Clipped Window Output Example

```
Run #10: 800x600 @ (100,100) [clipped] Timer=300s
✓ PASS (clipped)
...
OCR: 62% precision (detectable 60% of full UI)
  - Expected: 90% × 60% = 54% → result 62% is good
  - Timer visible: yes
  - Arrow visible: partially (top clipped)
  - Chat: clipped (open state undetectable)
Clicks: 18/20 accurate (only clickable elements reached)
Spam: 22.5 CPS (lower due to fewer visible targets)
```

---

## HTML Dashboard

Generated after suite completes: `test_results.html`

### Dashboard Sections

1. **Suite Summary**
   - Total runs, pass rate, duration
   - CPU distribution pie chart (IDLE / LOW / MEDIUM / HIGH / CRITICAL)
   - Memory trend line chart

2. **Scenario Breakdown**
   - Run type distribution (single-monitor, multi-monitor, clipped)
   - Pass rate by window size
   - Pass rate by DPI configuration

3. **Performance Metrics**
   - Click accuracy (mean ± stddev)
   - OCR precision (mean ± stddev)
   - Timer accuracy (error % distribution)
   - Spam CPS (mean ± stddev)

4. **Bottleneck Analysis**
   - Bottleneck timeline (which runs hit CPU/memory/IO limits)
   - Hot-spots table (function name, CPU ms, %, call count) — sortable
   - Bottleneck severity breakdown

5. **CPU Profiling Details** (when available)
   - Per-run CPU load over time
   - Aggregate hot-spots across all profiled runs
   - CPU load classification distribution

6. **Multi-Monitor Results** (if tested)
   - Single-monitor vs multi-monitor comparison (pass rate delta)
   - DPI mismatch impact (click drift comparison)
   - Coordinate transform latency (histogram)
   - Monitor-specific OCR precision

7. **Deviation Details**
   - Runs with warnings/errors listed
   - Deviation type, severity, threshold
   - Affected scenarios

---

## SQLite Database

Generated after suite completes: `test_results.db`

### Schema

**runs table:**
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    scenario_json TEXT,           -- Full scenario config
    metrics_json TEXT,            -- All collected metrics
    status TEXT,                  -- "PASS" or "FAIL"
    cpu_load_class TEXT,          -- IDLE, LOW, MEDIUM, HIGH, CRITICAL
    cpu_percent_avg REAL,
    cpu_percent_peak REAL,
    memory_peak_mb REAL,
    bottleneck_type TEXT          -- CPU, MEMORY, IO, NONE
);
```

**bottlenecks table:**
```sql
CREATE TABLE bottlenecks (
    id INTEGER PRIMARY KEY,
    run_id INTEGER,
    bottleneck_type TEXT,
    severity TEXT,                -- WARNING, ERROR, CRITICAL
    function_name TEXT,
    cpu_time_ms REAL,
    cpu_percent REAL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);
```

**multi_monitor_metrics table:**
```sql
CREATE TABLE multi_monitor_metrics (
    id INTEGER PRIMARY KEY,
    run_id INTEGER,
    monitor_count INTEGER,
    monitor_0_dpi REAL,
    monitor_1_dpi REAL,
    coord_transform_time_ms REAL,
    click_on_wrong_monitor INTEGER,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);
```

### Useful Queries

**Pass rate by CPU load class:**
```sql
SELECT cpu_load_class, COUNT(*) as run_count, 
       ROUND(100.0 * SUM(CASE WHEN status='PASS' THEN 1 ELSE 0 END) / COUNT(*), 1) as pass_rate
FROM runs
GROUP BY cpu_load_class
ORDER BY run_count DESC;
```

**Bottleneck frequency:**
```sql
SELECT bottleneck_type, severity, COUNT(*) as count, 
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT run_id) FROM bottlenecks), 1) as percent
FROM bottlenecks
GROUP BY bottleneck_type, severity
ORDER BY count DESC;
```

**Multi-monitor coordinate transform stats:**
```sql
SELECT COUNT(*) as run_count,
       ROUND(AVG(coord_transform_time_ms), 2) as avg_transform_ms,
       MAX(coord_transform_time_ms) as max_transform_ms,
       SUM(click_on_wrong_monitor) as wrong_monitor_clicks
FROM multi_monitor_metrics;
```

**CPU-intensive functions (hot-spots):**
```sql
SELECT function_name, ROUND(AVG(cpu_time_ms), 2) as avg_cpu_ms, 
       ROUND(AVG(cpu_percent), 1) as avg_cpu_percent, COUNT(*) as occurrences
FROM bottlenecks
WHERE bottleneck_type='CPU'
GROUP BY function_name
ORDER BY avg_cpu_ms DESC;
```

---

## Performance Targets

### Baseline (Single-Monitor, Full-Size)

- **Pass rate:** ≥ 95%
- **Click accuracy:** > 90% within 10px of target
- **OCR precision:** 85-90% (5+ detections)
- **Timer accuracy:** < 5% error
- **Spam CPS:** 38-39 CPS (±1 CPS)
- **CPU avg:** 25-35% (LOW to MEDIUM)
- **Memory peak:** 120-150 MB

### Multi-Monitor (Same DPI)

- **Pass rate:** ≥ 90%
- **Coordinate transform:** < 5ms
- **Click accuracy:** same as baseline (DPI scaling transparent)
- **CPU overhead:** +0-5% vs single-monitor

### Multi-Monitor (Different DPI)

- **Pass rate:** 80-85%
- **Coordinate transform:** 5-10ms
- **Click accuracy:** 85-90% (some DPI scaling artifacts expected)
- **CPU overhead:** +5-10% vs single-monitor
- **DPI mismatch errors:** < 5% of clicks on wrong monitor

### Clipped Windows (800x600, 640x480)

- **Pass rate:** 60-70% (lower due to off-screen UI)
- **OCR precision:** 50-65% (adjusted for detectable elements %)
- **Click accuracy:** limited to visible elements
- **Spam CPS:** 20-25 (fewer visible targets)
- **CPU:** unchanged (not a performance issue)

### Full Suite (Thorough Mode)

- **Per-run time:** 5-10 seconds (includes CPU profiling)
- **Total suite:** 20-30 runs × 8s = 160-240s (~3-4 minutes)
- **CPU profiling overhead:** +20-30% vs baseline
- **Report generation:** < 10s (console + HTML + SQLite)

---

## Scenario Breakdown

### Distribution (30-50 Total Runs)

| Type | Count | Purpose |
|------|-------|---------|
| **Single-monitor, full-size** | 10 | Baseline metrics, confidence |
| **Single-monitor, clipped** | 5 | Robustness with small windows |
| **Multi-monitor, same DPI** | 5 | Cross-monitor functionality |
| **Multi-monitor, different DPI** | 5 | DPI scaling, coordinate transforms |
| **Spanning/Offscreen** | 3 | Edge cases, error handling |
| **High jitter / glitches** | 3 | Resilience to input noise |
| **Extra (if needed)** | 4-14 | Adaptive sampling (if baseline weak) |

### Scenario Variables

**Window position:**
- Single-monitor: (0, 0), (center), (1900, 100), etc.
- Multi-monitor: on primary, on secondary, spanning both, offscreen

**Window size:**
- Full: 1024x768, 1280x720, 1920x1080, 2560x1440
- Clipped: 800x600, 640x480 (UI cut off)

**DPI scaling:**
- Single: 96, 120, 144 DPI (0.96x, 1.0x, 1.2x, 1.44x)
- Multi: Monitor 0 @ 96 DPI, Monitor 1 @ 144 DPI (mixed scaling)

**Game state:**
- Chat: closed, open, scrolled
- Timer: 5s, 30s, 300s (tests rapid vs slow spam)
- Jitter: 0ms, ±50ms, ±500ms

**Glitches:**
- None (clean run)
- Frame drop at tick #5 (early glitch)
- Frame drop at tick #50 (late glitch)
- Monitor disconnect (multi-monitor only)

---

## CPU Profiling Guide

### When Profiling Activates

CPU profiling runs automatically if:
1. Integration test detects CPU > 50%
2. Test explicitly enabled profiling
3. Running with `--profile` flag

### Interpreting Hot-Spots

Each hot-spot shows:
- **Function name:** Location in code (e.g., `bot.clicker.click_at`)
- **CPU ms:** Total CPU time spent in this function (milliseconds)
- **CPU %:** Percentage of total macro runtime
- **Calls:** Number of times function was called

**Example:**
```
Hot-spots (CPU 62%):
  1. bot.ocr.detect: 1240ms (52%) [42 calls]
  2. bot.clicker.click_at: 480ms (20%) [266 calls]
  3. bot.capture.get_frame: 360ms (15%) [42 calls]
  4. game_sim.process_click: 220ms (9%) [266 calls]
```

**Analysis:**
- OCR is bottleneck (52% of CPU). Consider caching template matches or using approximate matching
- Clicker takes 20% (expected for 266 clicks). Check WinAPI SendInput frequency
- Frame capture 15% (normal)

### Bottleneck Classification

| Load | CPU % | Threshold | Action |
|------|-------|-----------|--------|
| IDLE | 0-10% | N/A | No action |
| LOW | 10-30% | Normal | Monitor |
| MEDIUM | 30-50% | Normal | Monitor |
| HIGH | 50-70% | Warning | Profile, investigate |
| CRITICAL | 70%+ | Error | Profile immediately, identify bottleneck |

### Identifying Bottlenecks

**CPU Bottleneck** (CPU > 70%):
- Look for hot-spots > 30% CPU
- Typical culprits: OCR detection, click dispatch, frame rendering
- Action: cache results, batch operations, or use faster algorithm

**Memory Bottleneck** (peak > 3x baseline):
- Check memory allocations
- Typical culprits: frame cache, scenario history
- Action: implement LRU cache or streaming

**OCR Slow-down** (OCR > 300ms per call):
- Check image preprocessing time
- Action: reduce image size, use approximate matching

**Click Drift** (deviations > 100px):
- Check coordinate transforms (especially multi-monitor)
- Action: verify DPI scaling, monitor affinity

---

## Multi-Monitor Testing Guide

### Setup Requirements

**Single monitor:** No setup needed (default scenario)

**Dual monitor (same DPI):**
```
Monitor 0: 1920x1080 @ 96 DPI (primary)
Monitor 1: 1920x1080 @ 96 DPI (secondary, right of primary)
```

**Dual monitor (different DPI):**
```
Monitor 0: 1920x1080 @ 96 DPI (primary)
Monitor 1: 1920x1080 @ 144 DPI (secondary, scaled 1.5x)
```

### Expected Results

**Same DPI:**
- Pass rate: ≥ 90%
- Coordinate transform: < 5ms
- No DPI scaling artifacts

**Different DPI:**
- Pass rate: 80-85% (some click drift expected)
- Coordinate transform: 5-10ms (transform overhead visible)
- Click drift: < 5% misplaced clicks acceptable

**Spanning/Offscreen:**
- Pass rate: 50-60% (reduced visibility expected)
- Frame capture: may fail or return partial view
- Expected behavior: error handling, timeout

**Monitor hot-swap:**
- Pass rate: 70% (recovery takes time)
- Recovery time: < 1s expected
- Expected behavior: bot retries frame capture, continues macro

### Multi-Monitor Metrics Explained

- **Monitor count:** Number of displays detected
- **Monitor DPI:** Scaling factor per monitor (96 = 1.0x, 144 = 1.5x)
- **Coordinate transform:** Time to convert click coordinates between monitors (< 10ms expected)
- **Click on wrong monitor:** Count of misplaced clicks (should be ≈ 0)
- **OCR precision delta:** OCR precision on secondary monitor vs primary

---

## Bottleneck Analysis Techniques

### 1. Identify the Bottleneck

**Console output shows hot-spots. Example:**
```
CPU: 75% avg (CRITICAL) ⚠️ Hot-spots:
  - bot.ocr.detect: 1240ms (52%)
  - bot.clicker.click_at: 480ms (20%)
```

**Bottleneck identified:** OCR detection consuming 52% of runtime.

### 2. Check SQLite for Patterns

```sql
-- Find which runs have OCR bottleneck
SELECT run_id, cpu_percent_avg, function_name, cpu_time_ms
FROM bottlenecks
WHERE function_name LIKE '%ocr%'
ORDER BY cpu_time_ms DESC;
```

**Pattern check:** Is bottleneck consistent, or only on certain scenarios?

### 3. Examine Scenario Context

```sql
-- Get scenario details for bottleneck run
SELECT scenario_json
FROM runs
WHERE id = 123;
```

**Check:** Which scenario triggered bottleneck? (e.g., high-DPI, multi-monitor, large window)

### 4. Profile Specific Function

Enable detailed profiling for OCR:

```bash
uv run scalene --cpu --memory mvp/tests/integration/test_macro_hybrid.py
```

**Look for:** Which lines in `bot.ocr.detect` take most time? (Template matching, image preprocessing, etc.)

### 5. Optimize and Re-test

Common optimizations:
- **OCR:** Cache template matches, reduce image size, use approximate matching
- **Clicks:** Batch SendInput calls, reduce frequency
- **Memory:** Implement LRU cache, stream data instead of loading all
- **Coordinate transforms:** Pre-compute affine matrices, vectorize operations

Re-run suite to verify improvement:

```bash
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v
```

Compare CPU % before/after:

```sql
SELECT cpu_load_class, ROUND(AVG(cpu_percent_avg), 1) as avg_cpu
FROM runs
WHERE timestamp > '2025-01-XX'
GROUP BY cpu_load_class;
```

---

## Quick Reference

### Commands

```bash
# Run all tests
uv run pytest mvp/tests/ -v

# Run framework only
uv run pytest mvp/tests/test_framework/ -v

# Run integration (smoke only)
uv run pytest mvp/tests/integration/test_smoke.py -v

# Run integration (full)
uv run pytest mvp/tests/integration/test_macro_hybrid.py -v

# Profile
uv run scalene mvp/tests/integration/test_macro_hybrid.py

# Coverage
uv run pytest mvp/tests/ --cov=mvp --cov-report=html
```

### Key Metrics Targets

| Metric | Baseline | Clipped | Multi-Mon (same DPI) | Multi-Mon (diff DPI) |
|--------|----------|---------|----------------------|----------------------|
| Pass rate | ≥ 95% | 60-70% | ≥ 90% | 80-85% |
| Click acc | > 90% | varies | > 90% | 85-90% |
| OCR prec | 85-90% | 50-65% | 85-90% | 82-87% |
| Spam CPS | 38-39 | 20-25 | 38-39 | 38-39 |
| CPU avg | 25-35% | 25-35% | 25-35% | 30-40% |

### Report Files

- `test_results.html` — Interactive dashboard
- `test_results.db` — SQLite database
- `htmlcov/` — Code coverage (if run with `--cov`)
