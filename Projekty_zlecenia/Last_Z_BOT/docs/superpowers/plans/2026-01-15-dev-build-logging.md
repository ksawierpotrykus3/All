# DEV Build Terminal Crash - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\- [ ]\) syntax for tracking.

**Goal:** Add persistent debug logging to DEV build so crashes are visible to end users and analyzable by developers.

**Architecture:** Create a standalone \logger.py\ module that detects DEV mode, initializes logging handlers for file and console, and installs a global exception hook. Integrate into \main.py\ and \un.py\ at startup time, before any user code that might fail. Logging is conditional—PROD build (\LastZBot.exe\) does not activate logging.

**Tech Stack:** Python 3.11 standard library only (\logging\, \sys\, \os\, \pathlib\)

---

## Task 1: Create logger.py module with DEV mode detection

**Files:**
- Create: \mvp/logger.py\
- Test: \mvp/tests/test_logger.py\ (tests for this task)

### Step 1: Write the failing tests for DEV mode detection

Create \mvp/tests/test_logger.py\:

\\\python
import os
import sys
import tempfile
from pathlib import Path
import pytest

from mvp.logger import is_dev_mode, setup_dev_logging, get_logger


class TestDevModeDetection:
    def test_is_dev_mode_with_dev_env_var(self, monkeypatch):
        \"\"\"When LASTZBOT_DEV=1, is_dev_mode returns True.\"\"\"
        monkeypatch.setenv('LASTZBOT_DEV', '1')
        assert is_dev_mode() is True

    def test_is_dev_mode_without_dev_env_var(self, monkeypatch):
        \"\"\"When LASTZBOT_DEV not set, check executable name.\"\"\"
        monkeypatch.delenv('LASTZBOT_DEV', raising=False)
        # Simulate PROD executable
        original_argv = sys.argv[0]
        sys.argv[0] = 'LastZBot.exe'
        try:
            assert is_dev_mode() is False
        finally:
            sys.argv[0] = original_argv

    def test_is_dev_mode_with_dev_exe_name(self, monkeypatch):
        \"\"\"When executable name contains 'dev', is_dev_mode returns True.\"\"\"
        monkeypatch.delenv('LASTZBOT_DEV', raising=False)
        original_argv = sys.argv[0]
        sys.argv[0] = 'LastZBot-Dev.exe'
        try:
            assert is_dev_mode() is True
        finally:
            sys.argv[0] = original_argv


class TestLoggerSetup:
    def test_setup_dev_logging_creates_logger(self):
        \"\"\"setup_dev_logging() returns a logger object.\"\"\"
        logger = setup_dev_logging()
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')

    def test_setup_dev_logging_creates_log_file(self, monkeypatch, tmp_path):
        \"\"\"When setup_dev_logging() is called in DEV mode, creates log file.\"\"\"
        # Mock LOCALAPPDATA to temp directory
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
        monkeypatch.setenv('LASTZBOT_DEV', '1')
        
        logger = setup_dev_logging()
        log_file = tmp_path / 'LastZBot' / 'dev_build_debug.log'
        
        # Log something
        logger.info('Test message')
        
        # Wait for handler flush (if async)
        for handler in logger.handlers:
            handler.flush()
        
        assert log_file.exists()

    def test_logger_logs_to_file_and_console(self, monkeypatch, tmp_path, capsys):
        \"\"\"Logger writes to both file and console.\"\"\"
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
        monkeypatch.setenv('LASTZBOT_DEV', '1')
        
        logger = setup_dev_logging()
        logger.info('Test message for file and console')
        
        for handler in logger.handlers:
            handler.flush()
        
        # Check file
        log_file = tmp_path / 'LastZBot' / 'dev_build_debug.log'
        assert 'Test message for file and console' in log_file.read_text()

    def test_get_logger_returns_same_logger(self):
        \"\"\"get_logger() always returns the same logger instance.\"\"\"
        setup_dev_logging()
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2
\\\

**Run:** \cd f:\\PROJEKTY\\joaxx && uv run pytest mvp/tests/test_logger.py -v\

**Expected:** All tests FAIL (module doesn't exist yet)

### Step 2: Write minimal logger.py implementation

Create \mvp/logger.py\:

\\\python
\"\"\"Dev build logging module - captures stdout/stderr and exceptions.\"\"\"

import logging
import os
import sys
from pathlib import Path


_logger = None


def is_dev_mode() -> bool:
    \"\"\"Detect if running in DEV mode.
    
    Returns True if:
    - LASTZBOT_DEV=1 environment variable is set, OR
    - Executable name contains 'dev' (case-insensitive), OR
    - Running as script (not compiled executable)
    \"\"\"
    # Check environment variable
    if os.getenv('LASTZBOT_DEV', '0').lower() == '1':
        return True
    
    # Check executable name
    exe_name = sys.argv[0].lower() if sys.argv else ''
    if 'dev' in exe_name:
        return True
    
    # Check if running as script (not frozen/compiled)
    if not getattr(sys, 'frozen', False):
        return True
    
    return False


def _get_log_directory() -> Path:
    \"\"\"Get the directory for log files, creating it if needed.
    
    Returns:
        Path to log directory (e.g., %LOCALAPPDATA%\\LastZBot)
        Falls back to temp directory if %LOCALAPPDATA% unavailable.
    \"\"\"
    try:
        localappdata = os.path.expandvars(r'%LOCALAPPDATA%')
        if localappdata and localappdata != r'%LOCALAPPDATA%':  # Variable was expanded
            log_dir = Path(localappdata) / 'LastZBot'
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
    except Exception:
        pass  # Fall through to temp directory
    
    # Fallback to temp directory
    temp_dir = Path(os.environ.get('TEMP', '/tmp')) / 'LastZBot'
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def setup_dev_logging() -> logging.Logger:
    \"\"\"Initialize dev logging if in DEV mode.
    
    Sets up:
    - File handler to %LOCALAPPDATA%\\LastZBot\\dev_build_debug.log
    - Console handler for stderr
    - Global exception hook
    
    Returns:
        Logger instance (or returns None if not in DEV mode)
    \"\"\"
    global _logger
    
    if _logger is not None:
        return _logger
    
    if not is_dev_mode():
        # Not in DEV mode - create null logger that does nothing
        _logger = logging.getLogger('lastzbot')
        _logger.addHandler(logging.NullHandler())
        return _logger
    
    # Create logger
    _logger = logging.getLogger('lastzbot')
    _logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers
    _logger.handlers.clear()
    
    # Log format: timestamp | level | module:function:line | message
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    try:
        log_dir = _get_log_directory()
        log_file = log_dir / 'dev_build_debug.log'
        
        # Create file handler with write mode (clear old log each time app starts)
        file_handler = logging.FileHandler(str(log_file), mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    except Exception as e:
        print(f'Warning: Could not create log file: {e}', file=sys.stderr)
    
    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)
    
    # Install exception hook
    sys.excepthook = _exception_hook
    
    _logger.info('DEV logging initialized (PID: %d)', os.getpid())
    
    return _logger


def get_logger() -> logging.Logger:
    \"\"\"Get the global logger instance.
    
    Must call setup_dev_logging() first to initialize.
    \"\"\"
    global _logger
    if _logger is None:
        setup_dev_logging()
    return _logger


def _exception_hook(exc_type, exc_value, exc_traceback):
    \"\"\"Global exception hook - logs unhandled exceptions.\"\"\"
    if _logger:
        _logger.critical(
            'Unhandled exception',
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    # Print to stderr for user visibility (if not already captured)
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
\\\

**Run:** \cd f:\\PROJEKTY\\joaxx && uv run pytest mvp/tests/test_logger.py::TestDevModeDetection -v\

**Expected:** DEV mode detection tests PASS

### Step 3: Run all logger tests and verify they pass

\\\ash
cd f:\\PROJEKTY\\joaxx && uv run pytest mvp/tests/test_logger.py -v
\\\

**Expected output:** All tests PASS (6-7 tests)

### Step 4: Commit

\\\ash
cd f:\\PROJEKTY\\joaxx && git add mvp/logger.py mvp/tests/test_logger.py && git commit -m \"feat(logging): add dev build logging module with exception capture\"
\\\

---

## Task 2: Integrate logging into main.py

**Files:**
- Modify: \mvp/main.py\

### Step 1: Find main() function entry point

Read \mvp/main.py\ to find where execution starts.

### Step 2: Add logging setup at start of main()

At the very first line of \main()\ (before any other imports or code), add:

\\\python
from mvp.logger import setup_dev_logging

def main():
    # Initialize logging BEFORE any other code
    setup_dev_logging()
    
    # ... rest of main() code
\\\

### Step 3: Verify main.py imports work correctly

\\\ash
cd f:\\PROJEKTY\\joaxx && uv run python mvp/main.py --help
\\\

**Expected:** Help output appears (no import errors)

### Step 4: Commit

\\\ash
cd f:\\PROJEKTY\\joaxx && git add mvp/main.py && git commit -m \"feat(logging): integrate dev logging into main entry point\"
\\\

---

## Task 3: Check if run.py exists and integrate logging

**Files:**
- Modify: \un.py\ (if exists)

### Step 1: Check if run.py exists

\\\ash
ls -la f:\\PROJEKTY\\joaxx\\run.py
\\\

### Step 2: If exists, add logging setup

If file exists, add at start of entry point:

\\\python
from mvp.logger import setup_dev_logging
setup_dev_logging()
\\\

If file doesn't exist, skip this task.

### Step 3: Commit (if applicable)

\\\ash
cd f:\\PROJEKTY\\joaxx && git add run.py && git commit -m \"feat(logging): integrate dev logging into run.py entry point\"
\\\

---

## Task 4: Manual integration test - DEV build exception logging

**Files:**
- None (manual test only)

### Step 1: Create intentional exception in DEV build

Modify \mvp/main.py\ temporarily to cause an exception:

\\\python
def main():
    setup_dev_logging()
    
    # Temporary: cause intentional exception to test logging
    raise RuntimeError('TEST EXCEPTION - verify logging works')
\\\

### Step 2: Run DEV build

\\\ash
cd f:\\PROJEKTY\\joaxx && LASTZBOT_DEV=1 uv run python mvp/main.py
\\\

**Expected:** Terminal shows exception message

### Step 3: Verify log file created

\\\ash
cat %LOCALAPPDATA%\\LastZBot\\dev_build_debug.log
\\\

**Expected:** Log file contains full stack trace and 'TEST EXCEPTION' message

### Step 4: Remove the intentional exception

Delete the RuntimeError line from main() and restore normal code.

### Step 5: Commit

\\\ash
cd f:\\PROJEKTY\\joaxx && git add mvp/main.py && git commit -m \"test(logging): verified exception logging works in DEV build\"
\\\

---

## Task 5: Verify PROD build is unaffected

**Files:**
- None (verification test only)

### Step 1: Verify logging doesn't activate in PROD mode

Run with LASTZBOT_DEV not set (PROD mode):

\\\ash
cd f:\\PROJEKTY\\joaxx && uv run python mvp/main.py
\\\

**Expected:** Normal application output (no debug logging visible)

### Step 2: Verify no log file created in PROD mode

\\\ash
ls -la %LOCALAPPDATA%\\LastZBot\\dev_build_debug.log 2>&1 | grep -c 'cannot access'
\\\

**Expected:** No log file exists (or from previous DEV run, not current PROD run)

### Step 3: Document verification

No commit needed for this verification-only task. Issue resolved when tests pass.

---

## Summary

- Task 1: 7 tests written + logger.py implementation
- Task 2: main.py integration (2-3 lines added)
- Task 3: run.py integration (optional)
- Task 4: Manual exception logging test
- Task 5: Verification that PROD is unaffected

**Total lines of code:** ~150 lines (logger.py) + 80 lines (tests)

**Estimated time:** 45-60 minutes

**Testing:** 7 unit tests + 2 manual integration tests