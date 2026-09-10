"""DEV build logging module with exception capture."""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tempfile import gettempdir

# Singleton logger instance and initialization lock
_logger: logging.Logger | None = None
_logger_lock = threading.Lock()


def is_dev_mode() -> bool:
    """
    Detect if running in DEV mode.
    
    Returns True if:
    1. LASTZBOT_DEV=1 environment variable is set, OR
    2. Executable name contains 'dev', OR
    3. Running as a script (not frozen)
    
    Returns:
        bool: True if in DEV mode, False otherwise.
    """
    # Check environment variable first
    if os.environ.get("LASTZBOT_DEV") == "1":
        return True
    
    # Check executable name for 'dev'
    if len(sys.argv) > 0:
        exe_name = Path(sys.argv[0]).name.lower()
        if "dev" in exe_name:
            return True
    
    # Check if running as script (not frozen)
    if not getattr(sys, "frozen", False):
        return True
    
    return False


def _get_log_directory() -> Path:
    """
    Get the log directory path.
    
    Returns:
        Path: Log directory, with fallback to temp directory if creation fails.
    """
    try:
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LastZBot"
        else:
            # Running as script
            base = Path(__file__).resolve().parent / "logs"
        
        # Ensure directory exists
        base.mkdir(parents=True, exist_ok=True)
        return base
    except PermissionError:
        # Insufficient permissions to create directory
        return Path(gettempdir()) / "LastZBot"
    except OSError:
        # Other OS-level failures (disk full, etc.)
        return Path(gettempdir()) / "LastZBot"


def _exception_hook(exc_type, exc_value, exc_traceback) -> None:
    """
    Capture unhandled exceptions to log file.
    
    Args:
        exc_type: Exception type.
        exc_value: Exception value.
        exc_traceback: Exception traceback.
    """
    if _logger is None:
        return
    
    # Log the exception with traceback
    _logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


def setup_dev_logging(log_dir: Path | None = None) -> logging.Logger:
    """
    Initialize DEV build logging with file and console handlers.
    
    Args:
        log_dir: Override log directory (for testing). If None, uses _get_log_directory().
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    global _logger
    
    if _logger is not None:
        return _logger
    
    # Create logger
    _logger = logging.getLogger("dev_build")
    _logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    _logger.handlers.clear()
    
    # Determine log directory
    if log_dir is None:
        log_dir = _get_log_directory()
    else:
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # Log format: YYYY-MM-DD HH:MM:SS.mmm | LEVEL | module.function:line | message
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Error handler for file write failures
    def handle_error(record):
        """Fallback handler for file write failures."""
        # Attempt to log to console as fallback
        try:
            print(f"ERROR: Failed to write log: {record.getMessage()}", file=sys.stderr)
        except Exception:
            pass
    
    # File handler (rotating)
    log_file = log_dir / "dev_build_debug.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.handleError = handle_error
    _logger.addHandler(file_handler)
    
    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)
    
    # Set exception hook
    sys.excepthook = _exception_hook
    
    return _logger


def get_logger(log_dir: Path | None = None) -> logging.Logger:
    """
    Get or create the DEV build logger (singleton pattern).
    
    Args:
        log_dir: Override log directory (for testing). If None, uses _get_log_directory().
    
    Returns:
        logging.Logger: Logger instance.
    """
    global _logger
    
    if _logger is None:
        with _logger_lock:
            # Double-check pattern: another thread may have initialized while waiting for lock
            if _logger is None:
                _logger = setup_dev_logging(log_dir=log_dir)
    
    return _logger
