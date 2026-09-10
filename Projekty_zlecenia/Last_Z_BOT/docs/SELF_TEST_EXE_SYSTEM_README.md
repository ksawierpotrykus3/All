# Self-Testing EXE System - Complete Guide

## Overview

System do automatycznego testowania głównego bota (Python) z stub game executable (C#/.NET 8.0) bez potrzeby rzeczywistej gry.

**Status: Zadanie 3 COMPLETED** (all 3 tasks implemented)

## Tasks Completed

### Task 1: Stub Game EXE ✅
- **Status**: DONE
- **Location**: `LastZBot-SelfTest/` (C# .NET 8.0 project)
- **Output**: `LastZBot-SelfTest/bin/Release/net8.0-windows/win-x64/LastZBot-SelfTest.exe` (~151 KB)
- **Features**:
  - WinAPI window (1024x768, title "LastZ Game [SELFTEST]")
  - Click reception (WM_LBUTTONDOWN handler)
  - Event logging to `game_events.log`
  - Game state simulation (timer, clicks, treasures)
  - HTTP mock server on `localhost:8888`

### Task 2: Network Mock Server ✅
- **Status**: DONE
- **Location**: `LastZBot-SelfTest/NetworkMock.cs`
- **Features**:
  - HTTP server on `localhost:8888`
  - Endpoints:
    - `GET /api/game/state` → returns game metrics (timer, clicks, treasures)
    - `GET /api/treasure/check` → returns treasure location or "not found"
  - Thread-safe, async request handling
  - Supports bot's GET requests without authentication

### Task 3: PowerShell Orchestration Script ✅
- **Status**: DONE
- **Location**: `auto-test-self-test.ps1` (project root)
- **Features**:
  - Starts stub exe (waits for window)
  - Starts main bot (Python via `run.py`)
  - Monitors test execution (default 300 seconds)
  - Parses stub log file
  - Tracks metrics: clicks, treasures
  - Generates PASS/FAIL report
  - Cleanup: stops both processes

## Quick Start

### 1. Verify Prerequisites

```powershell
# Check .NET 8.0 installed
dotnet --version

# Check Python 3.11+
python --version

# Check uv available
uv --version
```

### 2. Build Stub EXE (if not already built)

```bash
cd LastZBot-SelfTest
dotnet build -c Release
cd ..
```

### 3. Run End-to-End Test

```powershell
# Run with default 300 seconds (5 minutes)
.\auto-test-self-test.ps1

# Or with custom duration
.\auto-test-self-test.ps1 -TestDurationSeconds 600

# With verbose output
.\auto-test-self-test.ps1 -Verbose
```

### 4. Check Results

Script outputs colored report:
- ✓ GREEN = PASS (clicks > 0 AND treasures > 0)
- ✗ RED = FAIL (clicks == 0 OR treasures == 0 OR crash)

Exit codes:
- `0` = PASS
- `1` = FAIL

## Test Execution Flow

```
1. Orchestration Script Starts
   ↓
2. Check stub exe exists
   ↓
3. Start Stub EXE
   ├─ Window appears (1024x768)
   ├─ Log file created: game_events.log
   └─ HTTP server starts: localhost:8888
   ↓
4. Wait 1 second
   ↓
5. Start Main Bot (Python run.py)
   ├─ Bot connects to bot
   ├─ Bot finds window: "LastZ Game [SELFTEST]"
   └─ Bot starts sending clicks & HTTP requests
   ↓
6. Wait 2 seconds (for connection)
   ↓
7. Monitor Test (configurable duration, default 300s)
   ├─ Every 500ms: read & parse log file
   ├─ Every 30s: report progress
   ├─ Track: clicks, treasures, process health
   └─ Stop if either process crashes
   ↓
8. Test Duration Complete
   ↓
9. Generate Report
   ├─ Total duration
   ├─ Clicks received
   ├─ Treasures collected
   ├─ Clicks/second
   └─ PASS/FAIL verdict
   ↓
10. Cleanup
    ├─ Stop main bot process
    ├─ Stop stub exe process
    └─ Report exit code
```

## Log File Format

Stub exe creates `game_events.log` in same directory as exe:

```
[HH:MM:SS.mmm] EVENT_TYPE: Details

Example entries:
[12:41:28.202] STARTUP: LastZ SelfTest EXE v1.0
[12:41:28.304] HTTP: Server started on http://localhost:8888/
[12:41:28.324] WINDOW: Created window: LastZ Game [SELFTEST] (size 1024x768)
[12:41:28.341] TIMER: Started countdown: 300 seconds
[12:41:30.100] CLICK: x=512, y=384
[12:41:30.200] WM_LBUTTONDOWN: x=512, y=384
[12:41:31.345] TREASURE: Total treasures: 1
[12:41:32.100] SPAWN: Treasure spawned at 300, 200
[12:41:32.567] FOUND: Treasure found at 310, 205
```

**Metrics tracked by orchestration script:**
- `CLICK:` or `WM_LBUTTONDOWN:` → click count
- `TREASURE:` with `Total treasures: N` → treasure count
- `FOUND:` (fallback if no `TREASURE:` events) → treasure count

## Success Criteria

**Test PASSES if:**
- `clicks > 0` (bot successfully sent at least 1 click)
- `treasures > 0` (stub detected at least 1 treasure collection)

**Test FAILS if:**
- `clicks == 0` (bot not connecting or not clicking)
- `treasures == 0` (stub not registering treasure finds)
- Either process crashes before duration complete

## Example Output

```
============================================================
LASTZ BOT SELF-TESTING EXE
============================================================
[INFO] Starting test sequence...
[INFO] Test Duration: 300 seconds
[INFO] Checking stub exe...
[✓] Stub exe started (PID: 12345)
[INFO] Stub window ready
[INFO] Starting main bot (run.py)...
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

## Troubleshooting

### Port 8888 Already in Use

```powershell
# Kill process using port 8888
Get-NetTCPConnection -LocalPort 8888 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### .NET 8.0 Not Installed

```powershell
# Install .NET 8.0 WindowsDesktop Runtime from:
# https://dotnet.microsoft.com/download/dotnet/8.0
```

### Stub EXE Won't Start

Check if exe exists:
```powershell
Test-Path ".\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\LastZBot-SelfTest.exe"
```

Rebuild if needed:
```bash
cd LastZBot-SelfTest
dotnet build -c Release
```

### Bot Process Crashes

Check bot's logs (if available):
```powershell
Get-Content "LOGS.txt" -Tail 50  # bot logs
```

Verify bot can find window:
```powershell
# Run stub exe first
.\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\LastZBot-SelfTest.exe

# In another PowerShell, run bot
python run.py
```

### No Metrics Recorded

Check if log file was created:
```powershell
Test-Path ".\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\game_events.log"

# View log contents
Get-Content ".\LastZBot-SelfTest\bin\Release\net8.0-windows\win-x64\game_events.log"
```

## Architecture Details

### Stub EXE Components

| File | Purpose |
|------|---------|
| `Program.cs` | Entry point, window initialization |
| `GameWindow.cs` | WinAPI window, WM_LBUTTONDOWN handler, UI rendering |
| `GameState.cs` | Game state (timer, clicks, treasures), thread-safe |
| `Logger.cs` | Event logging to file + stdout |
| `NetworkMock.cs` | HTTP server (localhost:8888) |

### Orchestration Script Functions

| Function | Purpose |
|----------|---------|
| `Start-StubExe` | Start stub, wait for window |
| `Start-MainBot` | Start main bot (Python run.py) |
| `Monitor-TestExecution` | Read log, track metrics, report progress |
| `Read-GameLog` | Read stub log file |
| `Parse-GameMetrics` | Extract click/treasure counts |
| `Generate-Report` | Format final report |
| `Cleanup` | Stop both processes |

## Integration Points

### Stub EXE ↔ Main Bot

1. **Window Discovery**: Bot finds window titled "LastZ Game [SELFTEST]"
2. **Click Injection**: Bot sends WinAPI messages (WM_LBUTTONDOWN, WM_LBUTTONUP)
3. **HTTP Requests**: Bot makes GET requests to `localhost:8888`:
   - `GET /api/game/state` → game metrics
   - `GET /api/treasure/check` → treasure location

### Orchestration Script ↔ Stub EXE

1. **Process Management**: Start/stop stub exe process
2. **Log File Reading**: Parse `game_events.log` continuously
3. **Metrics Extraction**: Count clicks and treasures from log events

## Performance Notes

- **Test Duration**: Default 300s (5 min), configurable
- **Log Read Interval**: 500ms
- **Report Interval**: 30s
- **Process Startup Delay**: 1s (stub) + 2s (bot connection)
- **Typical Click Rate**: 4-5 clicks/second (depends on bot implementation)

## Next Steps

1. **Automate in CI/CD**: Integrate with GitHub Actions or Azure DevOps
2. **Regression Detection**: Store baseline metrics, alert on degradation
3. **Performance Analysis**: Track latency percentiles (p50, p95, p99)
4. **Multiple Runs**: Run test N times, compute statistics
5. **Visualization**: Create dashboard for test results over time

## Related Documentation

- `docs/SELF_TEST_EXE_ORCHESTRATION.md` — Detailed orchestration script guide
- `LastZBot-SelfTest/README.md` — Stub EXE architecture
- `LastZBot-SelfTest.Tests/` — Unit tests (10 passing tests)

## Status Summary

| Component | Status | Location |
|-----------|--------|----------|
| Stub EXE | ✅ DONE | `LastZBot-SelfTest/bin/Release/...` |
| Network Mock | ✅ DONE | `LastZBot-SelfTest/NetworkMock.cs` |
| Orchestration Script | ✅ DONE | `auto-test-self-test.ps1` |
| Documentation | ✅ DONE | `docs/SELF_TEST_EXE_*.md` |

**System Ready for End-to-End Testing** 🎉
