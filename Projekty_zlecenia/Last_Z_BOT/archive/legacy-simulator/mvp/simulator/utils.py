# mvp/simulator/utils.py
"""
Utility functions and helpers for the simulation framework.
Provides logging, path management, and common utilities.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
import sys
from datetime import datetime


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.

    Args:
        name: Logger name (typically __name__)
        log_file: Optional path to log file. If None, console-only logging.
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Console handler (always)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_project_root() -> Path:
    """Get the root directory of the project (mvp or src)."""
    current = Path(__file__).resolve()
    # mvp/simulator/utils.py -> mvp/
    return current.parent.parent


def get_simulator_root() -> Path:
    """Get the simulator module root directory (mvp/simulator)."""
    current = Path(__file__).resolve()
    return current.parent


def get_data_dir() -> Path:
    """Get the data directory (project_root/data)."""
    return get_project_root().parent / 'data'


def get_assets_dir() -> Path:
    """Get the assets directory (project_root/assets)."""
    return get_project_root().parent / 'assets'


def get_logs_dir() -> Path:
    """Get or create the logs directory for simulator."""
    logs_dir = get_simulator_root() / 'logs'
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def get_session_log_file(session_id: Optional[str] = None) -> Path:
    """
    Get path to session log file.

    Args:
        session_id: Optional session identifier. If None, generates timestamp-based ID.

    Returns:
        Path to log file
    """
    if session_id is None:
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')

    logs_dir = get_logs_dir()
    return logs_dir / f'session_{session_id}.log'


def format_timestamp_ms(ms: float) -> str:
    """Format milliseconds as MM:SS.mmm string."""
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f'{minutes:02d}:{seconds:06.3f}'


def timestamp_ms() -> int:
    """Get current timestamp in milliseconds (epoch-based)."""
    return int(datetime.now().timestamp() * 1000)
