> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Build 5: Diagnostics – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement comprehensive diagnostics: trace JSON logging, post-install health check, and runtime initialization logging to enable debugging and health monitoring.

**Architecture:**
1. Trace logging: All build.ps1 steps logged to `dist/build-trace.json` (JSON structured logs)
2. Health check: Post-install script validates Tesseract, EasyOCR models, app startup
3. Runtime init log: mvp/main.py logs module imports, config loading, license verification to `mvp/runtime_init.json`

**Tech Stack:** PowerShell 5.1+, Python 3.11, JSON

---

## Task 1: Implement Health Check Script (health-check.ps1)

**Files:**
- Create: `mvp/build/health-check.ps1`

- [ ] **Step 1: Detect Tesseract installation**

```powershell
function Check-Tesseract {
    $paths = @(
        "C:\Program Files\Tesseract-OCR\tesseract.exe",
        "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    )
    foreach ($path in $paths) {
        if (Test-Path $path) {
            Log-Trace "INFO" "Tesseract found" @{path = $path}
            return @{status = "OK"; path = $path}
        }
    }
    Log-Trace "WARN" "Tesseract not found"
    return @{status = "FAIL"; error = "Tesseract not installed"}
}
```

- [ ] **Step 2: Detect EasyOCR models**

```powershell
function Check-EasyOCRModels {
    $models = @("craft_mlt_25k.zip", "english_g2.zip")
    $missing = @()
    foreach ($model in $models) {
        if (-not (Test-Path "vendor/$model")) {
            $missing += $model
        }
    }
    if ($missing.Count -eq 0) {
        Log-Trace "INFO" "EasyOCR models OK"
        return @{status = "OK"; models_count = 2}
    } else {
        Log-Trace "WARN" "EasyOCR models missing: $($missing -join ', ')"
        return @{status = "FAIL"; missing = $missing}
    }
}
```

- [ ] **Step 3: Check app startup**

```powershell
function Check-AppStartup {
    # Run: LastZBot.exe --version (or equivalent quick command)
    # Timeout: 5 seconds
    # Success: app exits cleanly with version output
}
```

- [ ] **Step 4: Commit**

```bash
git add mvp/build/health-check.ps1
git commit -m "feat(build): implement post-install health check script"
```

---

## Task 2: Integrate Health Check into build.ps1

**Files:**
- Modify: `mvp/build/build.ps1`

- [ ] **Step 1: Call health-check.ps1 after Inno Setup**

```powershell
Write-Host "==> Step 5/5: Post-install health check" -ForegroundColor Cyan

$HealthCheckScript = Join-Path $BuildDir 'health-check.ps1'
if (Test-Path $HealthCheckScript) {
    try {
        Log-Trace "INFO" "Running post-install health check"
        & $HealthCheckScript
        Log-Trace "INFO" "Health check completed"
    }
    catch {
        Log-Trace "WARN" "Health check failed (non-blocking)" @{error = $_.Exception.Message}
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add mvp/build/build.ps1
git commit -m "feat(build): call health-check after installer completion"
```

---

## Task 3: Implement Runtime Initialization Logging in mvp/main.py

**Files:**
- Create: `mvp/lib/runtime_logger.py`
- Modify: `mvp/main.py`

- [ ] **Step 1: Create runtime logger module**

```python
import logging
import json
from pathlib import Path
from datetime import datetime

class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage()
        }
        return json.dumps(log_entry)

def setup_runtime_logger(log_file="mvp/runtime_init.json"):
    handler = logging.FileHandler(log_file)
    handler.setFormatter(JSONLogFormatter())
    logger = logging.getLogger("mvp.init")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

- [ ] **Step 2: Integrate into mvp/main.py**

```python
from mvp.lib.runtime_logger import setup_runtime_logger

init_logger = setup_runtime_logger()

def main():
    init_logger.info("Application startup initiated")
    
    # Config loading
    init_logger.info("Loading configuration from mvp/config.py")
    # ...
    
    # Tesseract detection
    init_logger.info("Detecting Tesseract installation")
    # ...
    
    # EasyOCR models
    init_logger.info("Loading EasyOCR models")
    # ...
    
    # License verification
    init_logger.info("Verifying license")
    # ...
    
    init_logger.info("Application fully initialized")
```

- [ ] **Step 3: Commit**

```bash
git add mvp/lib/runtime_logger.py mvp/main.py
git commit -m "feat(runtime): add structured initialization logging to runtime_init.json"
```

---

## Task 4: Document Diagnostics Usage

**Files:**
- Create: `docs/DIAGNOSTICS.md`

- [ ] **Step 1: Document trace log usage**

```markdown
# Diagnostics Guide

## Build Trace Log (dist/build-trace.json)

Generated during build, contains:
- All build steps (fetch-vendor, build_cython, nuitka, inno)
- Timestamps for each step
- Cache hits/misses
- Compiler information
- Error details if build fails

Usage:
```bash
cat dist/build-trace.json | python -m json.tool | less
```

## Health Check Log

Run post-install to verify:
- Tesseract installation
- EasyOCR models presence
- Application startup

Usage:
```powershell
.\mvp\build\health-check.ps1
```

## Runtime Initialization Log (mvp/runtime_init.json)

Generated when app starts, logs:
- Config file loading
- Tesseract path detection
- EasyOCR model loading
- License verification status

Usage:
```bash
tail -f mvp/runtime_init.json
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/DIAGNOSTICS.md
git commit -m "docs: add diagnostics usage guide"
```

---

## Summary

- Task 1: Health check script (Tesseract, EasyOCR, app startup)
- Task 2: Integrate health check into build.ps1
- Task 3: Runtime initialization logging (mvp/runtime_init.json)
- Task 4: Documentation

**Expected Impact:**
- Complete build diagnostics trail (trace.json)
- Post-install health check for quick validation
- Runtime diagnostics for troubleshooting app issues
- Better debugging: all major events logged with timestamps

**Log Files Generated:**
1. `dist/build-trace.json` - Build process events
2. `mvp/runtime_init.json` - App initialization events
3. Health check output - Post-install validation results
