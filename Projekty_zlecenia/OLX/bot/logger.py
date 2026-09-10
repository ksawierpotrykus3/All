"""Logger: konsola + pliki z rotacja. Zero powiadomien zewnetrznych."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from . import config


def _make_handler(path, level=logging.INFO):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    h = RotatingFileHandler(
        path,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    h.setLevel(level)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    return h


def setup():
    """Konfiguruje loggery: console + detect/compare/app/errors."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    app = logging.getLogger("app")
    app.setLevel(logging.INFO)
    if not app.handlers:
        app.addHandler(console)
        app.addHandler(_make_handler(config.APP_LOG))
        app.addHandler(_make_handler(config.ERROR_LOG, logging.ERROR))

    det = logging.getLogger("detect")
    det.setLevel(logging.INFO)
    if not det.handlers:
        det.addHandler(console)
        det.addHandler(_make_handler(config.DETECT_LOG))

    cmp_ = logging.getLogger("compare")
    cmp_.setLevel(logging.INFO)
    if not cmp_.handlers:
        cmp_.addHandler(console)
        cmp_.addHandler(_make_handler(config.COMPARE_LOG))

    return app, det, cmp_


LOG_APP, LOG_DETECT, LOG_COMPARE = setup()