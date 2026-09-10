# Extended Game Simulator Framework — Documentation

**Status:** Phase 4+5 Complete (Integration & Entry Point + Documentation)  
**Version:** 1.0  
**Date:** 2 września 2026

## Quick Overview

The Extended Game Simulator Framework is a comprehensive testing platform for the game bot. It provides:

- **SimulationEngine**: Core orchestrator for multi-phase game loop simulation
- **Interactive UI**: Real-time visualization of game state, metrics, and events
- **Metrics Collection**: Per-iteration and aggregated metrics across multiple dimensions
- **Variant Testing**: Test matrix with 6 configurable dimensions (chat state, heli visibility, system load, etc.)
- **Report Generation**: Post-session HTML reports with heatmaps, timelines, and trend analysis
- **CLI Entry Point**: Simple command-line interface for running simulations

## Architecture Overview

### Component Layers

```
┌────────────────────────────────────────────────┐
│         run_simulator_extended.py              │
│         (CLI Entry Point)                      │
├────────────────────────────────────────────────┤
│         SimulatorController                    │
│         (Orchestrator Facade)                  │
├────────────────────────────────────────────────┤
│  SimulationEngine  │  InteractiveUI  │  Reports│
│  - Game State      │  - Tkinter UI   │ - HTML  │
│  - Phase Loop      │  - Metrics Dash │ - Charts│
│  - Metrics         │  - Timeline     │ - Trends│
│  - Bot Integration │  - Controls     │ - Analysis
├────────────────────────────────────────────────┤
│  Core Components                               │
│  - GameStateManager    (state machine)        │
│  - MetricsCollector    (metrics tracking)     │
│  - VariantExecutor     (variant management)   │
│  - BotIntegrationLayer (bot communication)    │
└────────────────────────────────────────────────┘
```

### Single Iteration Loop (6 Phases)

Each iteration follows this standardized 6-phase cycle:

1. **Setup** (~100ms)
   - Apply variant configuration (chat state, CPU load, alert timing)
   - Initialize phase metrics

2. **Alert** (~1-5s)
   - Display alert animation
   - Bot performs OCR detection
   - Measure detection time and confidence

3. **Click** (~50-200ms)
   - Bot sends click to simulator
   - Verify hit/miss
   - Measure latency (OCR done → click received)

4. **Treasure** (~500ms)
   - Simulate treasure opening
   - Measure CPU spike
   - Animate reward

5. **Chat Recovery** (~1-2s)
   - Return to chat view
   - Verify bot returns to chat state
   - Measure recovery time and OCR confidence
   - **CRITICAL**: Chat recovery failure = iteration failure

6. **Metrics** (~50ms)
   - Aggregate all phase data
   - Update dashboard
   - Store to session log

## Test Variants — Configuration Matrix

The framework supports testing across 6 configurable dimensions:

| Dimension | Options | Purpose |
|-----------|---------|---------|
| **Chat Cleanliness** | clean, cluttered, spam | Simulates different chat states |
| **Heli Visibility** | visible, hidden, partial | Tests with obstruction scenarios |
| **System Load** | idle, medium, high | Simulates CPU/memory pressure |
| **Alert Timing** | immediate, delayed, overlapped | Tests timing sensitivity |
| **Bot Config** | 30_cps, 38_cps, aggressive | Different bot click rates |
| **Eye Tracking** | focused, distracted, loss_event | Tests attention levels |

### Predefined Presets

- **default**: Clean chat, visible heli, idle load, immediate alert, 38 CPS, focused
- **hard_mode**: Cluttered chat, hidden heli, medium load, delayed alert, 38 CPS, distracted
- **stress_test**: Spam chat, partial heli, high load, overlapped alert, aggressive CPS, loss event

## Key Metrics

### Per-Iteration Metrics

```python
{
    "iteration": 5,
    "variant": "clean_visible_idle_immediate_38_focused",
    "phase_1_setup_ms": 98,
    "phase_2_alert_detection_ms": 145,
    "phase_3_click_latency_ms": 78,
    "phase_3_hit": True,
    "phase_4_cpu_spike_percent": 45,
    "phase_5_chat_recovery_ms": 890,
    "phase_5_ocr_confidence": 0.87,
    "phase_5_state_verified": True,
    "total_iteration_ms": 1356,
    "cpu_avg": 42,
    "ram_mb": 256
}
```

### Aggregated Session Metrics

```python
{
    "session_id": "2026-09-02_14-35-12",
    "iterations_total": 100,
    "iterations_hit": 80,
    "accuracy_percent": 80.0,
    "latency_avg_ms": 95,
    "latency_std_ms": 18,
    "latency_p95_ms": 145,
    "latency_p99_ms": 189,
    "cpu_spike_max_percent": 62,
    "cpu_spike_avg_percent": 42,
    "reliability_percent": 98.0,  # No chat recovery failures
    "chat_recovery_failures": 2,
    "anomalies": [
        {
            "iteration": 23,
            "reason": "Chat not recovered",
            "severity": "critical"
        }
    ]
}
```

## Entry Point — run_simulator_extended.py

### Basic Usage

```bash
# Run 10 iterations with default preset
uv run python run_simulator_extended.py

# Run with custom settings
uv run python run_simulator_extended.py \
    --variant_preset hard_mode \
    --iterations 20 \
    --output_dir results/

# Run stress test with verbose logging
uv run python run_simulator_extended.py \
    --variant_preset stress_test \
    --iterations 50 \
    --verbose
```

### CLI Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--variant_preset` | str | default | Preset: default, hard_mode, stress_test |
| `--iterations` | int | 10 | Number of iterations to run |
| `--output_dir` | str | results/ | Output directory for results |
| `--session_id` | str | auto | Optional session identifier |
| `--log_level` | str | INFO | Logging level: DEBUG, INFO, WARNING, ERROR |
| `--no_ui` | flag | False | Disable interactive UI |
| `--verbose` | flag | False | Enable verbose logging |

### Example Runs

```bash
# Quick test (5 iterations)
uv run python run_simulator_extended.py --iterations 5 --output_dir /tmp/quick_test

# Full test session (100 iterations, hard mode)
uv run python run_simulator_extended.py \
    --variant_preset hard_mode \
    --iterations 100 \
    --output_dir /tmp/hard_mode_session

# Stress test with verbose output
uv run python run_simulator_extended.py \
    --variant_preset stress_test \
    --iterations 50 \
    --verbose \
    --output_dir /tmp/stress_test
```

## Output Files

After running a simulation, the output directory contains:

```
results/
├── session_{session_id}.json          # Full session data (metrics + iterations)
├── summary_{session_id}.txt           # Text summary of results
├── report_{session_id}.html           # Interactive HTML report (Phase 3)
├── heatmap_clicks_{session_id}.png    # Click position heatmap
├── heatmap_ocr_{session_id}.png       # OCR confidence heatmap
├── timeline_phases_{session_id}.png   # Phase timeline chart
├── timeline_metrics_{session_id}.png  # Metrics trend chart
└── comparison_variants.html           # Multi-variant comparison (if available)
```

### JSON Export Format

```json
{
  "session_id": "2026-09-02_14-35-12",
  "timestamp": "2026-09-02T14:35:12.123Z",
  "variant_preset": "default",
  "iterations": [
    {
      "iteration": 0,
      "variant": "clean_visible_idle_immediate_38_focused",
      "metrics": { ... },
      "duration_ms": 1356,
      "success": true
    },
    ...
  ],
  "aggregated_metrics": {
    "iterations_total": 100,
    "accuracy_percent": 80.0,
    ...
  }
}
```

## SimulatorController API

The `SimulatorController` is the high-level orchestrator facade for programmatic access:

```python
from mvp.simulator.controller import SimulatorController

# Initialize
controller = SimulatorController(
    config={'skip_bot_integration': True},
    enable_ui=False,
    session_id='my_session_001'
)

# Lifecycle
assert controller.initialize()

# Configure and run
controller.set_variant_preset('default')
results = controller.run_iterations(num_iterations=20)

# Get metrics
metrics = controller.get_final_metrics()
print(f"Accuracy: {metrics['accuracy_percent']:.1f}%")
print(f"Avg Latency: {metrics['latency_avg_ms']:.1f}ms")

# Export and report
session_file = controller.export_session(output_dir='results/')
report_file = controller.generate_report(output_dir='results/')

# Cleanup
controller.shutdown()
```

## Testing

### Run All Tests

```bash
# Run full simulator test suite
uv run pytest tests/simulator/ -v

# Run with coverage
uv run pytest tests/simulator/ --cov=mvp.simulator --cov-report=term-missing

# Run specific test class
uv run pytest tests/simulator/test_integration.py::TestSimulatorControllerIntegration -v
```

### Test Structure

- `test_integration.py`: SimulationEngine + SimulatorController integration tests
- `test_cli_and_documentation.py`: CLI parsing and report generation tests
- `test_core.py`: GameStateManager tests
- `test_metrics.py`: MetricsCollector tests
- `test_variants.py`: VariantExecutor tests
- `test_bot_integration.py`: BotIntegrationLayer tests
- `test_ui_*.py`: UI component tests
- `test_reporting.py`: Report generation tests

## Architecture Decision Records

### Task 14: Full Integration
- Created `SimulatorController` as orchestrator facade
- Provides high-level session management API
- Decouples CLI from engine details
- Enables programmatic access

### Task 15: CLI Entry Point
- `run_simulator_extended.py` provides simple command-line interface
- Supports all variant presets and customizable iteration counts
- Generates text summaries and exports JSON session data
- Built on `SimulatorController` API

### Task 16: Documentation & Polish
- Comprehensive README with architecture overview
- Usage examples and CLI reference
- API documentation for `SimulatorController`
- Inline code comments and docstrings

## Performance Characteristics

- **Single Iteration Duration**: ~1200-1500ms (6 phases)
- **Metrics Collection Overhead**: <1% CPU
- **UI Update Frequency**: 50ms (20 FPS)
- **Session Export Time**: ~100ms (100 iterations)
- **Report Generation**: ~5 seconds (100 iterations, with charts)

## Troubleshooting

### Common Issues

1. **"SimulationEngine not initialized"**
   - Call `controller.initialize()` before `run_iterations()`

2. **"Report generation not available"**
   - Report generation is a Phase 3 feature
   - May not be available in all builds
   - Use `try/except RuntimeError` when calling `generate_report()`

3. **Output directory not found**
   - Entry point auto-creates output directory
   - Ensure parent directory exists and has write permissions

4. **Bot integration errors**
   - Use `config={'skip_bot_integration': True}` for testing without bot
   - In production, ensure bot runner is available

## Future Enhancements

- Real-time UI with live metric updates
- Advanced perturbation controls (inject failures, delays, etc.)
- Multi-variant comparison reports
- Machine learning anomaly detection
- Performance profiling and optimization
- Distributed test execution across multiple machines

---

**Documentation Version:** 1.0  
**Last Updated:** 2 września 2026  
**Phase:** 4+5 Complete (Integration & Entry Point + Documentation)
