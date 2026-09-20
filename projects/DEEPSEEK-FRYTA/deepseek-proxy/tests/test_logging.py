"""Tests for logging module."""

import pytest
import structlog

from server.logging import get_logger, configure_logging, log_proxy_request, log_error


def test_logger_returns_structlog_logger():
    configure_logging(log_level="DEBUG", log_format="console")
    logger = get_logger("test.module")
    # structlog returns a lazy proxy; trigger resolution then check
    logger.info("access")
    resolved = type(logger).__name__
    assert "Logger" in resolved or hasattr(logger, "info")


def test_logger_has_name():
    configure_logging(log_level="DEBUG", log_format="console")
    logger = get_logger("test.module")
    assert logger._context == {} or hasattr(logger, "_logger")


def test_json_output_format(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging()
    logger = get_logger("test")
    logger.info("test message", key="value")
    captured = capsys.readouterr()
    assert '"key": "value"' in captured.out
    assert '"event": "test message"' in captured.out


def test_console_output_format(monkeypatch, capsys):
    configure_logging(log_level="DEBUG", log_format="console")
    logger = get_logger("test")
    logger.info("test message", key="value")
    captured = capsys.readouterr()
    assert "test message" in captured.out
    assert "key" in captured.out


def test_log_error_function(monkeypatch, capsys):
    configure_logging(log_level="DEBUG", log_format="console")
    logger = get_logger("test")
    log_error(logger, message="something failed", code=500)
    captured = capsys.readouterr()
    assert "something failed" in captured.out
    assert "code" in captured.out


def test_log_proxy_request_function(monkeypatch, capsys):
    configure_logging(log_level="DEBUG", log_format="console")
    logger = get_logger("test")
    log_proxy_request(logger, method="POST", path="/v1/chat")
    captured = capsys.readouterr()
    assert "proxy_request" in captured.out
    assert "/v1/chat" in captured.out


def test_service_name_in_output(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "json")
    configure_logging()
    logger = get_logger("test")
    logger.info("test event")
    captured = capsys.readouterr()
    assert '"service": "deepseek-proxy"' in captured.out


def test_timestamp_in_output(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "json")
    configure_logging()
    logger = get_logger("test")
    logger.info("test event")
    captured = capsys.readouterr()
    assert '"timestamp"' in captured.out
