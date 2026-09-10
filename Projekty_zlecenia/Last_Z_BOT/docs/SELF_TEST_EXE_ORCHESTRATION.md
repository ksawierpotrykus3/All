# Self-Testing EXE Orchestration Script

## Overview

`auto-test-self-test.ps1` — PowerShell orchestration script dla automatycznego end-to-end testowania głównego bota z stub game executable.

**Architektura testingu:**
```
1. Start Stub EXE (C#, .NET 8.0)
   ↓
2. Start Main Bot (Python, dist\LastZBot.exe)
   ↓
3. Monitor test execution (300 sec default)
   ↓
4. Parse stub log file (game_events.log)
   ↓
5. Track metrics: clicks, treasures
   ↓
6. Generate PASS/FAIL report
   ↓
7. Cleanup: stop both processes
```

## File Structure

```
project_root/
├── auto-test-self-test.ps1         ← Orchestration script
├── run.py                           ← Main bot entry point
├── LastZBot-SelfTest/
│   ├── bin/Release/
│   │   └── net8.0-windows/win-x64/
│   │       ├── LastZBot-SelfTest.exe      ← Stub EXE
│   │       └── game_events.log             ← Log file (created at runtime)
│   └── ... (C# source)
├── src/
│   └── ... (Python bot source)
└── docs/
    └── SELF_TEST_EXE_ORCHESTRATION.md
```

## Usage

### Basic Run (300 seconds)

```powershell
.\auto-test-self-test.ps1
```

### Custom Duration (600 seconds = 10 minutes)

```powershell
.\auto-test-self-test.ps1 -TestDurationSeconds 600
```

### With Verbose Output

```powershell
.\auto-test-self-test.ps1 -Verbose
```

### Example Output

```
============================================================
LASTZ BOT SELF-TESTING EXE
============================================================
[INFO] Starting test sequence...
[INFO] Test Duration: 300 seconds
[INFO] Checking stub exe...
[✓] Stub exe started (PID: 12345)
[INFO] Stub window ready
[INFO] Starting main bot exe...
[✓] Main bot started (PID: 12346)
[INFO] Waiting for bot to connect to stub...
[INFO] Monitoring test for 300 seconds...
[INFO] [30s] Clicks: 142, Treasures: 5
[INFO] [60s] Clicks: 284, Treasures: 10
[INFO] [90s] Clicks: 426, Treasures: 15
...
[INFO] Test duration complete

============================================================
TEST EXECUTION REPORT
============================================================
Test Duration: 300 seconds
Clicks Received: 1420
Treasures Collected: 50
Clicks/Second: 4.73

------------------------------------------------------------
[✓] RESULT: PASSED
```

## Test Success Criteria

**PASS** = `clicks > 0 AND treasures > 0`

**FAIL** if:
- `clicks == 0` (bot not sending clicks to stub)
- `treasures == 0` (stub not registering treasure collection)
- Either process crashes during test
- Log file not created or not readable

## Implementation Details

### Key Functions

| Function | Purpose |
|----------|---------|
| `Start-StubExe` | Start stub game exe, wait for window |
| `Start-MainBot` | Build (if needed) + start main bot exe |
| `Monitor-TestExecution` | Read log, parse metrics, report every 30s |
| `Read-GameLog` | Read stub log file (game_events.log) |
| `Parse-GameMetrics` | Extract click/treasure counts from log |
| `Generate-Report` | Format PASS/FAIL report with metrics |
| `Cleanup` | Stop both processes gracefully |

### Log Parsing

Stub exe logs events in format:
```
[TIMESTAMP] EVENT_TYPE: Details

Examples:
[12:41:28.202] STARTUP: LastZ SelfTest EXE v1.0
[12:41:28.324] WINDOW: Created window: LastZ Game [SELFTEST] (size 1024x768)
[12:41:28.341] TIMER: Started countdown: 300 seconds
[12:41:30.100] CLICK: x=512, y=384
[12:41:30.200] WM_LBUTTONDOWN: x=512, y=384
[12:41:31.345] TREASURE: Total treasures: 1
[12:41:32.100] SPAWN: Treasure spawned at 300, 200
[12:41:32.567] FOUND: Treasure found at 310, 205
```

Script searches for:
- `CLICK:` or `WM_LBUTTONDOWN:` in line → increment clicks counter
- `TREASURE:` with `Total treasures: N` in line → extract treasure count
- `FOUND:` in line → alternative treasure tracking (if no `TREASURE:` events)

### Exit Codes

```
0  = Test PASSED (clicks > 0 AND treasures > 0)
1  = Test FAILED (clicks == 0 OR treasures == 0 OR process crash)
```

## Troubleshooting

### Port 8888 Already in Use

Stub exe runs HTTP server on `localhost:8888`. If port is in use:

```powershell
# Find process using port 8888
Get-NetTCPConnection -LocalPort 8888 | Select-Object OwningProcess
# Kill the process
Stop-Process -Id <PID> -Force
```

### Stub EXE Not Found

```
[✗] Stub exe not found: ...\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\LastZBot-SelfTest.exe
```

**Fix:** Ensure stub C# project was built:

```bash
cd LastZBot-SelfTest
dotnet build -c Release
```

### Main Bot EXE Not Found / Build Failed

Script runs main bot directly via `uv run python run.py`:

```
[INFO] Starting main bot (run.py)...
[✓] Main bot started (PID: 12346)
```

**If Python not found:**

```powershell
# Install Python 3.11+
python --version

# Install uv if not available
pip install uv
```

**If uv not available:**

Script falls back to direct Python execution:
```powershell
python run.py  # in project root
```

### Log File Not Created

Check stub exe stderr or permissions:

```powershell
# Run stub exe directly to see output
.\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\LastZBot-SelfTest.exe
# Check if game_events.log is created
Get-ChildItem ".\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\game_events.log"
```

### Test Takes Too Long / No Metrics

Usually indicates:
1. Bot not connecting to stub (check `localhost:8888` is reachable)
2. Bot crashed after startup (check bot's own logs)
3. Stub window not receiving click messages

**Debug:**
```powershell
# Monitor in real-time
Get-Content ".\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\game_events.log" -Wait
```

### Process Terminated Unexpectedly

```
[⚠] Process terminated unexpectedly
[✗] Stub exe crashed
```

Check why stub crashed:
- .NET runtime not installed: `dotnet --version`
- Missing dependencies: reinstall .NET 8.0 WindowsDesktop runtime
- Window creation failed: check if display is available

## Architecture Notes

### Why Two Processes?

1. **Stub EXE (C#)**: Simulates game window, receives clicks via WinAPI, logs events
2. **Main Bot (Python, run.py)**: Actual bot logic, finds window, sends clicks, reads responses

This approach:
- ✓ Tests full integration (bot→window communication)
- ✓ Isolates bot from real game
- ✓ Repeatable & deterministic
- ✓ Fast (5 min per run)
- ✓ No exe building required (runs Python directly)

### Why Parse Log Instead of Direct API?

- Log is side-effect of event processing (trustworthy)
- Avoids adding test-only APIs to stub exe
- Can replay/debug logs later
- Thread-safe (log file is atomic writes)

## Next Steps

1. **Metrics Dashboard**: Add live metrics visualization (PowerShell format table)
2. **Multiple Runs**: Loop `N` times, collect statistics (average clicks/sec, success rate)
3. **Regression Detection**: Store baseline metrics, alert if performance degrades
4. **CI Integration**: Call from GitHub Actions / Azure DevOps
5. **Performance Profiling**: Track latency percentiles (p50, p95, p99)

## Related Files

- `LastZBot-SelfTest\` — Stub game exe source (C#, .NET 8.0)
- `LastZBot-SelfTest.Tests\` — Stub unit tests (10 passing)
- `src/` — Main bot source (Python)
- `docs/SELF_TEST_EXE_ARCHITECTURE.md` — Overall system design
