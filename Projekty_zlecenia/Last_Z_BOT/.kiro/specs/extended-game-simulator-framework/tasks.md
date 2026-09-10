# Extended Game Simulator Framework — Implementation Plan

> For agentic workers: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build an interactive framework for testing full game loop with live metrics, multiple variants, and analysis reports.

**Architecture:** Three-layer system (SimulationEngine, InteractiveUI, ReportingEngine)

**Tech Stack:** Python 3.11, Tkinter, matplotlib, pandas, psutil, threading

---

## File Structure

New files to create:

    mvp/simulator/
    ├── __init__.py
    ├── core.py                    (GameStateManager, phase transitions)
    ├── metrics.py                 (MetricsCollector, per-iteration & aggregated)
    ├── variants.py                (VariantExecutor, variant configs)
    ├── bot_integration.py         (BotIntegrationLayer, hooks)
    ├── ui/
    │   ├── __init__.py
    │   ├── interactive_ui.py      (Main Tkinter window)
    │   ├── canvas_renderer.py     (Game state visualization)
    │   ├── metrics_dashboard.py   (Real-time metrics panel)
    │   ├── timeline_widget.py     (Event timeline)
    │   └── controls_panel.py      (Hotkeys, buttons, perturb menu)
    ├── reporting/
    │   ├── __init__.py
    │   ├── report_generator.py    (Post-session reports)
    │   ├── heatmaps.py            (Click position, OCR confidence heatmaps)
    │   ├── timelines.py           (Phase timelines, CPU/RAM trends)
    │   ├── comparisons.py         (Variant comparisons)
    │   └── trend_analysis.py      (Degradation, anomaly detection)
    ├── config.py                  (Variant definitions)
    └── utils.py                   (Helper functions)

    tests/simulator/
    ├── __init__.py
    ├── test_core.py
    ├── test_metrics.py
    ├── test_variants.py
    ├── test_ui.py
    ├── test_reporting.py
    └── test_integration.py

    run_simulator_extended.py      (New entry point)

---

## PHASE 1: Core Engine (Tasks 1-5)

### Task 1: Create SimulationEngine Core Structure

Files: mvp/simulator/core.py, __init__.py, utils.py

- [x] Step 1: Implement GameStateManager class with state machine (chat, alert_animation, treasure, scanning)
- [x] Step 2: Add threading-safe state transitions with callbacks
- [x] Step 3: Implement click logging and session metrics storage
- [x] Step 4: Create basic utils module with logger and path helpers
- [x] Step 5: Commit with message: "feat: add core GameStateManager and basic structure"

### Task 2: Implement MetricsCollector

Files: mvp/simulator/metrics.py, tests/simulator/test_metrics.py

- [x] Step 1: Write tests for MetricsCollector init, start_iteration, record_phase, end_iteration, aggregate
- [x] Step 2: Implement MetricsCollector class with per-iteration metrics collection
- [x] Step 3: Implement phase recording (setup, alert_detection, click_latency, cpu_spike, chat_recovery)
- [x] Step 4: Implement aggregation: accuracy, avg_latency, max_latency, chat_recovery_failures
- [x] Step 5: Run all tests to verify they pass
- [x] Step 6: Commit with message: "feat: implement MetricsCollector for per-iteration and aggregated metrics"

### Task 3: Implement VariantExecutor

Files: mvp/simulator/variants.py, config.py, tests/simulator/test_variants.py

- [x] Step 1: Write VariantExecutor tests: apply_preset, apply_variant, get_state_params, validation
- [x] Step 2: Create config.py with VARIANT_DIMENSIONS (chat, heli, load, timing, cps, eye_tracking)
- [x] Step 3: Create VARIANT_PRESETS: default, hard_mode, stress_test
- [x] Step 4: Implement VariantExecutor.apply_preset and apply_variant with validation
- [x] Step 5: Implement get_state_params to convert variants to game parameters
- [x] Step 6: Run tests and commit with message: "feat: implement VariantExecutor with presets"

### Task 4: Implement BotIntegrationLayer

Files: mvp/simulator/bot_integration.py

- [x] Step 1: Write tests for bot frame queue connection, OCR confidence reading, click logging
- [x] Step 2: Implement BotIntegrationLayer: connect to BotRunner, hook click events
- [x] Step 3: Implement OCR confidence reading from bot logs or API
- [x] Step 4: Implement CPU/RAM monitoring with psutil
- [x] Step 5: Run tests and commit with message: "feat: implement BotIntegrationLayer"

### Task 5: Integrate Core Components

Files: Create integration test, modify run_simulator_extended.py (stub)

- [x] Step 1: Write integration test: GameStateManager + MetricsCollector + VariantExecutor + BotIntegrationLayer
- [x] Step 2: Create SimulationEngine facade combining all 4 components
- [x] Step 3: Test full flow: apply variant -> phase transitions -> metrics collection -> aggregation
- [x] Step 4: Create stub for run_simulator_extended.py
- [x] Step 5: Commit with message: "feat: integrate core components into SimulationEngine"

---

## PHASE 2: Interactive UI (Tasks 6-10)

### Task 6: Tkinter UI Foundation

Files: mvp/simulator/ui/__init__.py, interactive_ui.py, canvas_renderer.py

- [x] Step 1: Write tests for UI initialization, window creation, canvas rendering
- [x] Step 2: Implement InteractiveUI class (Tkinter root window, 1400x900)
- [x] Step 3: Implement CanvasRenderer for game state visualization (alert, treasure, chat states)
- [x] Step 4: Create left panel (game canvas 600x700) and right panel (metrics dashboard 400x700)
- [-] Step 5: Run tests and commit with message: "feat: implement Tkinter UI foundation"

### Task 7: Metrics Dashboard Widget

Files: mvp/simulator/ui/metrics_dashboard.py

- [x] Step 1: Write tests for dashboard rendering, metric updates, gauge rendering
- [x] Step 2: Implement MetricsDashboard: accuracy gauge, latency meter, CPU monitor, state indicator
- [x] Step 3: Create real-time update mechanism (thread-safe queue from SimulationEngine)
- [x] Step 4: Implement text rendering for current variant, CPS, load
- [x] Step 5: Commit with message: "feat: implement real-time metrics dashboard"

### Task 8: Timeline Widget

Files: mvp/simulator/ui/timeline_widget.py

- [x] Step 1: Write tests for timeline rendering, event scrolling, timestamp formatting
- [x] Step 2: Implement TimelineWidget: scrollable event list with phase indicators
- [x] Step 3: Implement event formatting: [HH:MM:SS.mmm] Phase Name -> Status
- [x] Step 4: Thread-safe event queue from SimulationEngine
- [x] Step 5: Commit with message: "feat: implement timeline widget for phase visualization"

### Task 9: Controls Panel & Hotkeys

Files: mvp/simulator/ui/controls_panel.py, modify interactive_ui.py

- [x] Step 1: Write tests for hotkey handling, button clicks, perturbation menu
- [x] Step 2: Implement ControlsPanel: Pause, Skip, Perturb buttons
- [x] Step 3: Implement hotkey bindings: Space (alert), P (pause), R (reset), C (change_variant), S (cpu_spike), Q (quit)
- [x] Step 4: Implement perturbation menu: block_clicks, inject_cpu, change_chat, delay_alert, add_ocr_noise
- [x] Step 5: Commit with message: "feat: implement controls panel with hotkeys and perturbations"

### Task 10: UI Threading & Update Loop

Files: Modify mvp/simulator/core.py, interactive_ui.py

- [~] Step 1: Write test for UI update loop: metrics queue, state changes, rendering
- [~] Step 2: Implement SimulationEngine.start_ui_thread() for non-blocking updates
- [~] Step 3: Implement thread-safe queues: metrics_queue, state_queue, event_queue
- [~] Step 4: Implement InteractiveUI update loop (50ms refresh rate)
- [~] Step 5: Commit with message: "feat: implement UI threading and update loop"

---

## PHASE 3: Reporting Engine (Tasks 11-13)

### Task 11: Report Generator

Files: mvp/simulator/reporting/report_generator.py

- [~] Step 1: Write tests for report generation, HTML output, data serialization
- [~] Step 2: Implement ReportGenerator: session summary, variant config, metrics aggregates
- [~] Step 3: Implement HTML template generation with CSS styling
- [~] Step 4: Generate summary section: total iterations, accuracy, latency, CPU, reliability
- [~] Step 5: Commit with message: "feat: implement base report generator"

### Task 12: Analysis Visualizations (Heatmaps, Timelines, Comparisons)

Files: mvp/simulator/reporting/heatmaps.py, timelines.py, comparisons.py, trend_analysis.py

- [~] Step 1: Implement Heatmaps: click position XY, OCR confidence by variant, latency distribution
- [~] Step 2: Implement Timelines: per-iteration phases, CPU/RAM trend, accuracy curve, OCR confidence trend
- [~] Step 3: Implement Comparisons: variant A vs B table, CPS comparison, load comparison, before/after
- [~] Step 4: Implement TrendAnalysis: accuracy degradation, chat_recovery rate, anomaly detection
- [~] Step 5: Commit with message: "feat: implement analysis visualizations (heatmaps, timelines, comparisons)"

### Task 13: Report Integration

Files: Modify reporting/report_generator.py, create test_reporting.py

- [~] Step 1: Write integration tests for full report generation
- [~] Step 2: Integrate all visualizations into ReportGenerator
- [~] Step 3: Generate HTML report with all sections
- [~] Step 4: Test with sample data, verify output
- [~] Step 5: Commit with message: "feat: integrate all visualizations into final report"

---

## PHASE 4: Integration & Entry Point (Tasks 14-16)

### Task 14: Create run_simulator_extended.py Entry Point

Files: run_simulator_extended.py (full implementation)

- [~] Step 1: Implement CLI parser: config, variant_preset, num_iterations, output_dir
- [~] Step 2: Initialize SimulationEngine with config
- [~] Step 3: Initialize InteractiveUI
- [~] Step 4: Implement main loop: apply variant -> iterate -> collect metrics -> update UI
- [~] Step 5: Commit with message: "feat: create extended simulator entry point"

### Task 15: Full Integration Test

Files: tests/simulator/test_integration.py

- [~] Step 1: Write end-to-end test: bot + simulator + metrics + UI (headless mode)
- [~] Step 2: Run multiple iterations with variant_preset=default
- [~] Step 3: Verify metrics are collected correctly
- [~] Step 4: Verify report generation works
- [~] Step 5: Commit with message: "test: add full integration test"

### Task 16: Documentation & Examples

Files: docs/simulator/README.md, docs/simulator/USAGE.md

- [~] Step 1: Write README: architecture overview, component descriptions
- [~] Step 2: Write USAGE guide: CLI options, variant configuration, interpreting reports
- [~] Step 3: Add example runs: default preset, hard_mode preset, stress_test preset
- [~] Step 4: Document hotkeys, perturbations, output directory structure
- [~] Step 5: Commit with message: "docs: add simulator documentation and usage guide"

---

## PHASE 5: Optimization & Polish (Tasks 17-18)

### Task 17: Performance Optimization

Files: Modify core components for speed

- [~] Step 1: Profile UI update loop, identify bottlenecks
- [~] Step 2: Optimize metrics aggregation (cache calculations)
- [~] Step 3: Optimize canvas rendering (dirty rect tracking)
- [~] Step 4: Run performance benchmarks, ensure <100ms frame times
- [~] Step 5: Commit with message: "perf: optimize UI and metrics collection"

### Task 18: Error Handling & Edge Cases

Files: Modify all components

- [~] Step 1: Add error handling for missing macro images, bot disconnection
- [~] Step 2: Handle variant validation errors gracefully
- [~] Step 3: Handle UI threading errors (deadlocks, race conditions)
- [~] Step 4: Test with invalid inputs, missing config, network failures
- [~] Step 5: Commit with message: "fix: add comprehensive error handling"

---

## Execution Checklist

Run: uv run pytest tests/simulator/ -v --cov=mvp/simulator --cov-report=term-missing

Expected: All tests pass, >80% coverage

Build Report: python run_simulator_extended.py --variant_preset hard_mode --iterations 20 --output_dir reports/

Verify: reports/ contains HTML report with all sections (heatmaps, timelines, comparisons)

---

## Total Tasks: 18
## Estimated Time: 40-50 hours of agentic work
## Deliverable: Full interactive simulator framework with reporting and analysis

---

## AMENDMENT: Timer Animation Tasks (insert into appropriate phases)

### Task 3b: Add Timer Animation Support to VariantExecutor (INSERT AFTER Task 3)

**Files:** mvp/simulator/config.py (modify), mvp/simulator/ui/timer_animator.py (new)

**Purpose:** Support dynamic timer animation and all 6 visualization states

- [~] Step 1: Add STATE_IMAGE_MAPPING to config.py (chat, chat_focus, alert_animation, treasure, reward_details, chat_unavailable)

- [~] Step 2: Create timer_animator.py module with TimerAnimator class

- [~] Step 3: Implement TimerAnimator.render_countdown(elapsed_ms, total_ms=60000) returning PIL Image with overlay

- [~] Step 4: Implement color logic: T-60→T-30 green, T-30→T-10 yellow, T-10→T-0 red, T-0 blink

- [~] Step 5: Add timer metrics to IterationMetrics (timer_prediction_ms, timer_accuracy_percent, timer_is_early_click, timer_is_late_click)

- [~] Step 6: Commit with message: "feat: add timer animation support and STATE_IMAGE_MAPPING"

### Task 6b: Update CanvasRenderer for All 6 States (MODIFY Task 6)

**Files:** mvp/simulator/ui/canvas_renderer.py (modify), mvp/simulator/ui/timer_animator.py (integrate)

**Add to Task 6:**

- [~] Step 3b: Implement render_state(state_name) method to display correct image from macro_testing/

- [~] Step 4b: Implement render_timer_overlay(timer_animator, elapsed_ms) to draw timer countdown on treasure state

- [~] Step 5b: Handle all 6 states: CHAT (static), CHAT_FOCUS (arrow pulse), ALERT_ANIMATION (fade-in+drop), TREASURE (with timer), REWARD_DETAILS (fade-in), CHAT_UNAVAILABLE (pulsing border)

- [~] Step 6b: Test each state transition visually in test window

### Task 9b: Add Timer Perturbations (MODIFY Task 9 Controls Panel)

**Files:** mvp/simulator/ui/controls_panel.py (modify)

**Add to Task 9:**

- [~] Step 4b: Add timer-specific perturbations to Perturb Menu:
  - Chaotic Timer (jump ±5-20s randomly)
  - Frozen Timer (stop for N seconds)
  - Accelerated Timer (2x or 4x speed)
  - Hidden Timer (render invisible)
  - Distracted Chat (show chat during timer)

### Task 12b: Add Timer Responsiveness Analysis (MODIFY Task 12)

**Files:** mvp/simulator/reporting/heatmaps.py, timelines.py (modify)

**Add to Task 12:**

- [~] Step 1b: Implement timer_prediction_accuracy_heatmap: X-axis ΔT (ms vs expiry), Y-axis iteration, color accuracy%

- [~] Step 2b: Implement timeline with timer events: bot click position + timer expiry line

- [~] Step 3b: Implement trend analysis: timer_accuracy over session, degradation under load correlation

---

## Total Tasks (Updated): 18 + 5 amendments = comprehensive timer + visualization coverage

