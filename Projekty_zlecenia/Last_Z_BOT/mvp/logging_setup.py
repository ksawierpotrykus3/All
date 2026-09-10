
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _log_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LastZBot"
    else:
        base = Path(__file__).resolve().parent / "logs"
    return base


def setup_logging(debug: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    if getattr(setup_logging, "_installed", False):
        return
    setup_logging._installed = True

    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", "%H:%M:%S")

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "lastz_bot.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Ensure stdout/stderr use UTF-8 regardless of the Windows ANSI code page
    # (CP1250/CP1252), preventing UnicodeEncodeError on non-ASCII log output.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    for name in ("dxcam", "dxcam.core.dxgi_duplicator", "rapidocr_onnxruntime", "PIL", "asyncio"):
        logging.getLogger(name).setLevel(logging.ERROR)
