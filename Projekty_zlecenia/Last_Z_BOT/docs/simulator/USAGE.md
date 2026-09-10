# Extended Game Simulator - Usage Guide

## Installation

### Prerequisites
- Python 3.11+
- uv package manager

### Setup

```bash
# Clone repository (if needed)
git clone <repository>
cd joaxx

# Install dependencies
uv sync --extra dev

# Verify installation
uv run python -m mvp.simulator --help
```

## Quick Start

### Minimal Example

Run a simulation with default settings:

```bash
uv run python -m mvp.simulator
```

This runs:
- 100 iterations
- Default variant
- Output to `./reports/`
- INFO level logging

### With Custom Parameters

```bash
uv run python -m mvp.simulator \
  --variant hard_mode \
  --iterations 50 \
  --output ./my_reports
```

### Headless Mode (No UI)

```bash
uv run python -m mvp.simulator \
  --headless \
  --verbose \
  --iterations 100
```

## Running Simulations

### Using Variant Presets

The simulator includes three built-in variants:

#### Default Variant
Standard configuration for balanced testing:

```bash
uv run python -m mvp.simulator --variant default
```

#### Hard Mode
Aggressive configuration with higher CPS and stress:

```bash
uv run python -m mvp.simulator --variant hard_mode --iterations 25
```

#### Stress Test
Extreme configuration for bottleneck testing:

```bash
uv run python -m mvp.simulator --variant stress_test --iterations 10
```

### Using Configuration Files

Create a `config.json`:

```json
{
  "simulator": {
    "iterations": 50,
    "variant": "hard_mode",
    "phases": ["SETUP", "ALERT", "CLICK", "TREASURE", "SCAN"],
    "enable_ui": false
  },
  "reporting": {
    "output_dir": "./reports",
    "formats": ["html", "json"],
    "include_heatmaps": true,
    "include_timelines": true,
    "include_comparisons": true
  },
  "logging": {
    "level": "DEBUG",
    "file": "./simulator.log"
  }
}
```

Run with config:

```bash
uv run python -m mvp.simulator --config config.json
```

### Programmatic Usage

Use the simulator in your Python code:

```python
from mvp.simulator.cli import SimulatorCLI
from mvp.simulator.metrics import MetricsCollector

# Method 1: Using CLI
cli = SimulatorCLI()
exit_code = cli.run(['--variant', 'default', '--iterations', '100'])

# Method 2: Using MetricsCollector directly
collector = MetricsCollector(session_id='experiment_1')

for i in range(100):
    collector.start_iteration(iteration=i, variant='default')
    
    # Simulate phases
    collector.record_phase("setup", setup_ms=100)
    collector.record_phase("alert_detection", detection_ms=750)
    collector.record_phase("click_latency", latency_ms=120, hit=True)
    collector.record_phase("cpu_spike", cpu_spike_percent=65)
    collector.record_phase("chat_recovery", recovery_ms=1200, state_verified=True)
    
    collector.end_iteration(total_ms=2170, cpu_avg=55, ram_mb=512)

metrics = collector.aggregate()
print(f"Accuracy: {metrics['accuracy_percent']:.1f}%")
```

## Viewing Reports

### HTML Reports

After simulation completes, open the HTML report:

```bash
# On Windows
start ./reports/report.html

# On macOS
open ./reports/report.html

# On Linux
xdg-open ./reports/report.html
```

The HTML report includes:
1. **Summary** - Session overview and key metrics
2. **Heatmaps** - Click position distribution, OCR confidence
3. **Timelines** - Phase timelines, CPU/RAM trends, accuracy curves
4. **Comparisons** - Variant-to-variant comparisons
5. **Trends** - Degradation analysis, anomaly detection
6. **Raw Data** - Complete iteration data in table format

### JSON Reports

For programmatic analysis, use the JSON export:

```bash
# View JSON data
cat ./reports/report.json | python -m json.tool
```

JSON structure:

```json
{
  "session_id": "20260902_143012",
  "metadata": {
    "title": "Simulation Report",
    "timestamp": "2026-09-02T14:30:00Z"
  },
  "summary": {
    "total_iterations": 100,
    "accuracy_percent": 95.2,
    "reliability_percent": 98.5
  },
  "metrics": {
    "latency_avg_ms": 125.3,
    "latency_std_ms": 45.2,
    "latency_p95_ms": 189.4,
    "latency_p99_ms": 215.7,
    "cpu_max_percent": 87.2,
    "chat_recovery_failures": 1
  }
}
```

## Interpreting Metrics

### Accuracy
Percentage of successful clicks / total attempts.
- 100% = All clicks registered
- < 90% = May indicate performance issues

### Latency
Time between alert and click registration in milliseconds.
- Avg Latency: Average response time
- P95/P99: 95th and 99th percentile latencies

### Reliability
Percentage of successful chat state recoveries.
- 100% = All recoveries successful
- < 95% = May indicate detection issues

### CPU/RAM
Resource usage during simulation.
- CPU Max: Peak CPU usage (percent)
- RAM Avg: Average memory usage (MB)

## Troubleshooting

### Simulation Hangs

If the simulator hangs:

1. Press `Ctrl+C` to terminate gracefully
2. Check `./logs/simulator_*.log` for errors
3. Verify bot integration is connected

### Reports Not Generated

Verify:

```bash
# Check output directory exists
ls -la ./reports/

# Check logs
tail ./logs/simulator_*.log

# Run with verbose logging
uv run python -m mvp.simulator --verbose
```

### Memory Issues

If memory usage is high:

```bash
# Reduce iterations
uv run python -m mvp.simulator --iterations 10

# Run in headless mode (no UI)
uv run python -m mvp.simulator --headless

# Monitor memory
uv run scalene mvp/simulator/engine.py
```

### Configuration Errors

Verify your `config.json`:

```bash
# Validate JSON syntax
python -m json.tool config.json

# Check required fields
# simulator.iterations must be > 0
# variant must be one of: default, hard_mode, stress_test, custom
```

## Common Workflows

### A/B Testing Variants

Run multiple variants and compare:

```bash
# Run variant A
uv run python -m mvp.simulator \
  --variant default \
  --iterations 50 \
  --output ./reports_variant_a

# Run variant B
uv run python -m mvp.simulator \
  --variant hard_mode \
  --iterations 50 \
  --output ./reports_variant_b

# Compare reports
# Open ./reports_variant_a/report.html and ./reports_variant_b/report.html
```

### Performance Profiling

Profile performance bottlenecks:

```bash
# Run with debug logging
uv run python -m mvp.simulator \
  --headless \
  --log-level DEBUG \
  --iterations 20

# Profile CPU usage
uv run scalene mvp/simulator/engine.py

# Check memory leaks
uv run python -m memory_profiler mvp/simulator/engine.py
```

### Batch Testing

Run multiple simulations automatically:

```bash
#!/bin/bash

for variant in default hard_mode stress_test; do
  for iter in 10 20 50; do
    uv run python -m mvp.simulator \
      --variant "$variant" \
      --iterations "$iter" \
      --output "./reports/${variant}_${iter}iter"
  done
done
```

### Session Tracking

Track simulation sessions with custom IDs:

```bash
uv run python -m mvp.simulator \
  --session-id my_experiment_20260902_001 \
  --iterations 50 \
  --output ./reports/my_experiment
```

The session ID is included in all output files and logs.

## Advanced Usage

### Custom Variant

For advanced users, modify the configuration:

```bash
# Edit config.json with custom variant settings
uv run python -m mvp.simulator \
  --config custom_config.json \
  --variant custom
```

### Integration with Existing Pipelines

```python
from mvp.simulator.cli import SimulatorCLI
from mvp.simulator.metrics import MetricsCollector
import json

def run_simulation_batch(variants, iterations_per_variant):
    """Run simulations for multiple variants."""
    all_results = {}
    
    for variant in variants:
        collector = MetricsCollector(session_id=f"{variant}_batch")
        
        for i in range(iterations_per_variant):
            collector.start_iteration(iteration=i, variant=variant)
            # ... record metrics ...
            collector.end_iteration(total_ms=250, cpu_avg=45, ram_mb=256)
        
        all_results[variant] = collector.aggregate()
    
    # Save results
    with open('batch_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    return all_results
```

## FAQs

**Q: How many iterations should I run?**
A: Start with 10-20 for quick testing, 50-100 for standard runs, 1000+ for detailed analysis.

**Q: What's the difference between variants?**
A: Default is balanced, Hard Mode increases CPS and stress, Stress Test maxes all parameters.

**Q: How long does a simulation take?**
A: ~5-10 seconds for 100 iterations with UI. ~1-2 seconds in headless mode.

**Q: Can I interrupt a simulation?**
A: Yes, press Ctrl+C. The simulator gracefully shuts down and saves metrics collected so far.

**Q: How are reports stored?**
A: Reports go to the `--output` directory as HTML and JSON files, with logs in `./logs/`.

**Q: Can I run multiple simulations in parallel?**
A: Yes, but use different `--output` directories and `--session-id` values to avoid conflicts.

**Q: What if a metric is missing in the report?**
A: Check logs for errors. Some metrics may be unavailable in headless mode or if phases were skipped.

## Getting Help

For issues or questions:

1. Check logs: `tail ./logs/simulator_*.log`
2. Run with verbose logging: `--verbose --log-level DEBUG`
3. Review configuration: `python -m json.tool config.json`
4. See API documentation: `docs/simulator/API.md`
