# Extended Game Simulator - API Documentation

## Overview

The Extended Game Simulator Framework provides a comprehensive Python API for simulating game interactions, collecting metrics, and analyzing performance across variants.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  SimulatorCLI (Entry Point)             │
└───────────────┬─────────────────────────────────────────┘
                │
    ┌───────────┴───────────┬──────────────┐
    │                       │              │
┌───▼──────┐      ┌────────▼────┐   ┌────▼──────────┐
│ ConfigLd │      │  Engine     │   │  ReportGen    │
│  Service │      │ (Core)      │   │  Service      │
└─────────┬┘      └────┬────┬───┘   └────┬──────────┘
          │            │    │             │
    ┌─────▼────────────▼─┐  │      ┌──────▼─────┐
    │ GameStateManager   │  │      │ Visualizer │
    │ + MetricsCollector │  │      │ (Charts)   │
    └────────────────────┘  │      └────────────┘
                            │
                    ┌───────▼─────┐
                    │  Bot Layer  │
                    │ Integration │
                    └─────────────┘
```

## Core Classes

### SimulatorCLI

Command-line interface for the Extended Game Simulator.

```python
from mvp.simulator.cli import SimulatorCLI

cli = SimulatorCLI()
exit_code = cli.run(['--variant', 'default', '--iterations', '100'])
```

#### Methods

**`__init__(argv: Optional[list] = None)`**
- Initialize CLI parser
- Args: `argv` - Command-line arguments (defaults to sys.argv[1:])
- Returns: None

**`parse_args(argv: Optional[list] = None) -> argparse.Namespace`**
- Parse command-line arguments
- Args: `argv` - Command-line arguments
- Returns: Parsed arguments namespace
- Raises: `SystemExit` if arguments are invalid

**`validate_config(config: Dict[str, Any]) -> bool`**
- Validate loaded configuration
- Args: `config` - Configuration dictionary
- Returns: True if valid
- Raises: `ValueError` if configuration is invalid

**`load_config(config_path: str) -> Dict[str, Any]`**
- Load configuration from JSON file
- Args: `config_path` - Path to configuration file
- Returns: Loaded configuration dictionary
- Raises: `FileNotFoundError`, `json.JSONDecodeError`, `ValueError`

**`setup_logging(args: argparse.Namespace) -> logging.Logger`**
- Configure logging based on CLI arguments
- Args: `args` - Parsed CLI arguments
- Returns: Configured logger instance

**`run(argv: Optional[list] = None) -> int`**
- Execute simulator from CLI
- Args: `argv` - Command-line arguments
- Returns: Exit code (0 for success, 1 for error)

### SimulationEngine

Core simulation engine combining all components.

```python
from mvp.simulator.engine import SimulationEngine

engine = SimulationEngine(session_id='my_session')
# ... configuration and execution
```

### MetricsCollector

Collects per-iteration metrics and computes session-wide aggregations.

```python
from mvp.simulator.metrics import MetricsCollector

collector = MetricsCollector(session_id='test')

# For each iteration:
collector.start_iteration(iteration=0)
collector.record_phase("setup", setup_ms=100)
collector.record_phase("alert_detection", detection_ms=50)
collector.record_phase("click_latency", latency_ms=150, hit=True)
collector.end_iteration(total_ms=300, cpu_avg=45, ram_mb=256)

# Get aggregated results
metrics = collector.aggregate()
```

#### Methods

**`start_iteration(iteration: int, variant: Optional[str] = None) -> None`**
- Start a new iteration and initialize phase metrics storage
- Args:
  - `iteration` - Iteration number (0-indexed)
  - `variant` - Optional variant identifier
- Returns: None

**`record_phase(phase_name: str, **metrics_dict: Any) -> None`**
- Record metrics for a specific phase
- Args:
  - `phase_name` - Name of the phase (setup, alert_detection, click_latency, cpu_spike, chat_recovery)
  - `**metrics_dict` - Phase-specific metrics as keyword arguments
- Returns: None

**`end_iteration(total_ms: int, cpu_avg: int, ram_mb: int) -> None`**
- Complete current iteration and record finalize metrics
- Args:
  - `total_ms` - Total iteration duration (milliseconds)
  - `cpu_avg` - Average CPU usage (percent)
  - `ram_mb` - RAM usage (megabytes)
- Returns: None

**`aggregate() -> Dict[str, Any]`**
- Compute session-wide aggregated metrics
- Args: None
- Returns: Dictionary with aggregated metrics:
  - `session_id` - Session identifier
  - `iterations_total` - Total iterations
  - `iterations_hit` - Count of successful clicks
  - `accuracy_percent` - (hits / total) * 100
  - `latency_avg_ms` - Average click latency
  - `latency_std_ms` - Standard deviation of latency
  - `latency_p95_ms` - 95th percentile latency
  - `latency_p99_ms` - 99th percentile latency
  - `chat_recovery_failures` - Count of failed chat recoveries
  - `reliability_percent` - (successful_recoveries / total) * 100

### GameStateManager

Manages game state transitions and callbacks.

```python
from mvp.simulator.core import GameStateManager

gsm = GameStateManager()
gsm.transition_to("ALERT_ANIMATION")
```

### VariantExecutor

Applies variant configurations to game parameters.

```python
from mvp.simulator.variants import VariantExecutor

executor = VariantExecutor()
executor.apply_preset("hard_mode")
params = executor.get_state_params()
```

## Configuration File Format

Configuration files are JSON-based and follow this structure:

```json
{
  "simulator": {
    "iterations": 50,
    "variant": "default",
    "phases": ["SETUP", "ALERT", "CLICK", "TREASURE", "SCAN"],
    "enable_ui": true
  },
  "reporting": {
    "output_dir": "./reports",
    "formats": ["html", "json"],
    "include_heatmaps": true,
    "include_timelines": true,
    "include_comparisons": true
  },
  "logging": {
    "level": "INFO",
    "file": "./simulator.log"
  }
}
```

### Configuration Options

**simulator section:**
- `iterations` (int): Number of iterations to run (required)
- `variant` (str): Preset variant name: "default", "hard_mode", "stress_test", "custom" (default: "default")
- `phases` (list): Phases to include in simulation (default: all 5 phases)
- `enable_ui` (bool): Enable interactive UI (default: true)

**reporting section:**
- `output_dir` (str): Directory for report output (default: "./reports")
- `formats` (list): Report formats: "html", "json" (default: both)
- `include_heatmaps` (bool): Include heatmap visualizations (default: true)
- `include_timelines` (bool): Include timeline visualizations (default: true)
- `include_comparisons` (bool): Include variant comparisons (default: true)

**logging section:**
- `level` (str): Log level: "DEBUG", "INFO", "WARNING", "ERROR" (default: "INFO")
- `file` (str): Log file path (default: "./simulator.log")

## Command-Line Arguments

### Required Arguments
None - all arguments are optional with sensible defaults

### Optional Arguments

**`--config CONFIG`**
- Path to configuration JSON file
- Example: `--config config.json`

**`--variant {default|stress_test|hard_mode|custom}`**
- Variant preset to run (default: "default")
- Example: `--variant stress_test`

**`--iterations ITERATIONS`**
- Number of iterations to run (default: 100)
- Example: `--iterations 50`

**`--output OUTPUT`**
- Directory for report output (default: "./reports")
- Example: `--output ./my_reports`

**`--session-id SESSION_ID`**
- Custom session ID (default: auto-generated from timestamp)
- Example: `--session-id my_session_001`

**`--log-level {DEBUG|INFO|WARNING|ERROR}`**
- Logging level (default: "INFO")
- Example: `--log-level DEBUG`

**`--headless`**
- Run without interactive UI (flag)
- Example: `--headless`

**`--verbose`**
- Enable verbose (DEBUG) logging (flag, overrides --log-level)
- Example: `--verbose`

**`--help`**
- Show help message and exit (flag)
- Example: `--help`

## Common Usage Patterns

### Running a Simulation with Default Settings

```python
from mvp.simulator.cli import SimulatorCLI

cli = SimulatorCLI()
exit_code = cli.run()
```

### Running with Custom Configuration

```python
cli = SimulatorCLI()
exit_code = cli.run([
    '--config', 'config.json',
    '--output', './test_reports',
    '--verbose'
])
```

### Programmatic Usage

```python
from mvp.simulator.metrics import MetricsCollector

collector = MetricsCollector(session_id='experiment_001')

for iteration in range(10):
    collector.start_iteration(iteration=iteration, variant='default')
    
    # Simulate phases
    collector.record_phase("setup", setup_ms=100)
    collector.record_phase("alert_detection", detection_ms=750, ocr_confidence=0.95)
    collector.record_phase("click_latency", latency_ms=120, hit=True)
    collector.record_phase("cpu_spike", cpu_spike_percent=65)
    collector.record_phase("chat_recovery", recovery_ms=1200, ocr_confidence=0.92, state_verified=True)
    
    collector.end_iteration(total_ms=2170, cpu_avg=55, ram_mb=512)

# Get aggregated metrics
metrics = collector.aggregate()
print(f"Accuracy: {metrics['accuracy_percent']:.1f}%")
print(f"Avg Latency: {metrics['latency_avg_ms']:.1f}ms")
```

## Error Handling

The API uses typed exceptions for error handling:

- `FileNotFoundError` - Configuration file not found
- `json.JSONDecodeError` - Invalid JSON in configuration
- `ValueError` - Configuration validation failed
- `OSError` - Directory creation failed
- `SystemExit` - Invalid command-line arguments

Example:

```python
from mvp.simulator.cli import SimulatorCLI

cli = SimulatorCLI()

try:
    exit_code = cli.run(['--config', 'nonexistent.json'])
except FileNotFoundError as e:
    print(f"Configuration error: {e}")
```

## Thread Safety

The MetricsCollector and related classes use thread-safe operations:

- All metric updates use locks
- Safe for concurrent iteration recording
- Safe for concurrent UI updates

## Logging

Logging is configured with:

- File output to `./logs/simulator_YYYY-MM-DD_HH-MM-SS.log`
- Console output (disabled in headless mode)
- Log levels: DEBUG, INFO, WARNING, ERROR

```python
import logging

logger = logging.getLogger('simulator')
logger.info("Starting simulation")
```

## Performance Considerations

- Metrics collection is O(1) for per-iteration operations
- Aggregation is O(n) where n is number of iterations
- Report generation is typically < 5 seconds for < 1000 iterations
- Memory usage is linear with iteration count (~1KB per iteration)
