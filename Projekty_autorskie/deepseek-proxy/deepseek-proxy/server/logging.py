"""Structured logging configuration using structlog.

Dual-output: stdlib logging with console (stdout) + optional file handler.
File writes are buffered by Python's FileHandler — negligible perf overhead.
"""

from __future__ import annotations

import sys
import logging
import structlog
from structlog.stdlib import ProcessorFormatter
from structlog.types import EventDict, WrappedLogger

from server.config.settings import settings


def _add_service_name(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add service name to all log entries."""
    event_dict["service"] = "deepseek-proxy"
    return event_dict


def _add_timestamp(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO timestamp to all log entries."""
    from datetime import datetime, timezone

    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def configure_logging(
    log_level: str | None = None,
    log_format: str | None = None,
    log_file: str | None = None,
) -> None:
    """Configure structlog for the application with console + optional file output."""
    level = (log_level or settings.log_level).upper()
    fmt = (log_format or settings.log_format).lower()

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        _add_service_name,
        _add_timestamp,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if fmt == "json":
        renderer_processors = [
            ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        renderer_processors = [
            ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    formatter = ProcessorFormatter(
        processors=renderer_processors,
        foreign_pre_chain=shared_processors,
    )

    # --- root logger: console handler + optional file handler ---
    root = logging.getLogger()
    root.setLevel(getattr(logging, level))

    # Clear existing handlers — prevents duplicates when configure is called
    # multiple times (e.g. in tests) and avoids double-write on re-init.
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # --- structlog: stdlib integration (routes through root handlers) ---
    structlog.configure(
        processors=shared_processors + [ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance for the given module name."""
    return structlog.get_logger(name)


def log_proxy_request(logger: structlog.BoundLogger, **kwargs) -> None:
    logger.info("proxy_request", **kwargs)


def log_stream_start(logger: structlog.BoundLogger, **kwargs) -> None:
    logger.info("stream_start", **kwargs)


def log_stream_end(logger: structlog.BoundLogger, **kwargs) -> None:
    logger.info("stream_end", **kwargs)


def log_rate_limit(logger: structlog.BoundLogger, **kwargs) -> None:
    logger.warning("rate_limit", **kwargs)


def log_tool_call(logger: structlog.BoundLogger, **kwargs) -> None:
    logger.info("tool_call", **kwargs)


def log_error(logger: structlog.BoundLogger, **kwargs) -> None:
    logger.error("error", **kwargs)
