"""Tests dla #24 — Crash reporter.

Architektura:
- ``CrashReport`` — frozen dataclass z polami:
  - ``timestamp: str`` (ISO 8601)
  - ``app_version: str``
  - ``platform: str``
  - ``exc_type: str``
  - ``exc_value: str``
  - ``traceback: str``
  - ``context: dict[str, str]``
- ``CrashHandler`` — instaluje globalny ``sys.excepthook`` / ``threading.excepthook``.
- ``CrashBundleBuilder`` — pakuje raport + plik konfiguracyjny w ZIP.
- ``CrashReporterUploader`` (Protocol) — abstrakcja uploadu (None = suchy).

Functionality:
- ``install()`` / ``uninstall()``
- ``capture_exception(exc, context=None) -> CrashReport``
- ``format_traceback(exc) -> str``
- ``to_dict(report) -> dict``
- ``bundle_path(report) -> Path``
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

from mvp.bot.crash import (
    CrashBundleBuilder,
    CrashError,
    CrashHandler,
    CrashReport,
    CrashReporterUploader,
)

# ── CrashReport basics ────────────────────────────────────────────


class TestCrashReport:
    def test_creation_basic(self):
        r = CrashReport(
            timestamp="2025-01-15T12:00:00",
            app_version="1.2.3",
            platform="windows",
            exc_type="ValueError",
            exc_value="bad",
            traceback="Traceback...",
            context={},
        )
        assert r.exc_type == "ValueError"
        assert r.context == {}

    def test_frozen(self):
        r = CrashReport(
            timestamp="x",
            app_version="1",
            platform="linux",
            exc_type="E",
            exc_value="v",
            traceback="t",
            context={},
        )
        with pytest.raises((AttributeError, TypeError)):
            r.app_version = "2"  # type: ignore[misc]

    def test_to_dict(self):
        r = CrashReport(
            timestamp="t",
            app_version="1",
            platform="p",
            exc_type="E",
            exc_value="v",
            traceback="tr",
            context={"k": "v"},
        )
        d = r.to_dict()
        assert d["exc_type"] == "E"
        assert d["context"] == {"k": "v"}


# ── CrashHandler.format_traceback ─────────────────────────────────


class TestFormatTraceback:
    def test_format_simple(self):
        try:
            raise ValueError("oops")
        except ValueError as e:
            tb = CrashHandler.format_traceback(e)
        assert "ValueError" in tb
        assert "oops" in tb

    def test_format_chained(self):
        try:
            try:
                raise RuntimeError("inner")
            except RuntimeError as inner:
                raise ValueError("outer") from inner
        except ValueError as e:
            tb = CrashHandler.format_traceback(e)
        assert "outer" in tb
        assert "inner" in tb


# ── CrashHandler.capture_exception ────────────────────────────────


class TestCaptureException:
    def test_capture_returns_report(self):
        h = CrashHandler(app_version="1.0.0")
        try:
            raise ValueError("captured")
        except ValueError as e:
            report = h.capture_exception(e)
        assert isinstance(report, CrashReport)
        assert report.exc_type == "ValueError"
        assert "captured" in report.exc_value
        assert report.app_version == "1.0.0"

    def test_capture_with_context(self):
        h = CrashHandler(app_version="1.0")
        try:
            raise RuntimeError("x")
        except RuntimeError as e:
            report = h.capture_exception(e, context={"k": "v"})
        assert report.context == {"k": "v"}

    def test_capture_timestamp_iso(self):
        h = CrashHandler(app_version="1.0")
        try:
            raise ValueError("x")
        except ValueError as e:
            report = h.capture_exception(e)
        # ISO format: 2025-01-15T12:00:00.123456
        datetime.fromisoformat(report.timestamp)

    def test_capture_stores_reports(self):
        h = CrashHandler(app_version="1.0")
        try:
            raise ValueError("x")
        except ValueError as e:
            h.capture_exception(e)
            h.capture_exception(e)
        assert len(h.reports) == 2

    def test_capture_max_reports_limit(self):
        """``max_reports=3`` — the 5th report replaces the oldest one."""
        h = CrashHandler(app_version="1.0", max_reports=3)
        try:
            raise ValueError("x")
        except ValueError as e:
            for _ in range(5):
                h.capture_exception(e)
        assert len(h.reports) == 3


# ── CrashHandler install/uninstall ───────────────────────────────


class TestInstallUninstall:
    def test_install_sets_excepthook(self):
        h = CrashHandler(app_version="1.0")
        original = sys.excepthook
        try:
            h.install()
            assert sys.excepthook is not h._handle_exception  # not yet
            # Make sure the handler registered the new hook:
            assert sys.excepthook != original
        finally:
            sys.excepthook = original

    def test_install_thread_hook(self):
        h = CrashHandler(app_version="1.0")
        original = threading.excepthook
        try:
            h.install()
            assert threading.excepthook != original
        finally:
            threading.excepthook = original

    def test_uninstall_restores(self):
        h = CrashHandler(app_version="1.0")
        original = sys.excepthook
        h.install()
        h.uninstall()
        assert sys.excepthook is original

    def test_uninstall_thread_restores(self):
        h = CrashHandler(app_version="1.0")
        original = threading.excepthook
        h.install()
        h.uninstall()
        assert threading.excepthook is original

    def test_uninstall_without_install_no_error(self):
        h = CrashHandler(app_version="1.0")
        h.uninstall()  # should not raise


# ── handle_exception hook ─────────────────────────────────────────


class TestExcepthook:
    def test_excepthook_captures(self):
        h = CrashHandler(app_version="1.0")
        try:
            raise ValueError("from-hook")
        except ValueError as e:
            # Simulate invoking the hook directly:
            h._handle_exception(type(e), e, e.__traceback__)
        assert len(h.reports) == 1
        assert "from-hook" in h.reports[0].exc_value


# ── CrashBundleBuilder ────────────────────────────────────────────


class TestBundleBuilder:
    def test_build_zip(self, tmp_path: Path):
        r = CrashReport(
            timestamp="2025-01-15T12:00:00",
            app_version="1.0",
            platform="windows",
            exc_type="ValueError",
            exc_value="bad",
            traceback="Traceback...",
            context={"k": "v"},
        )
        config_path = tmp_path / "config.json"
        config_path.write_text('{"a": 1}', encoding="utf-8")
        builder = CrashBundleBuilder(
            crash_dir=tmp_path / "bundles",
            config_path=config_path,
        )
        bundle = builder.build(r)
        assert bundle.exists()
        assert bundle.suffix == ".zip"
        assert bundle.stat().st_size > 0

    def test_bundle_contains_report_json(self, tmp_path: Path):
        r = CrashReport(
            timestamp="t",
            app_version="1",
            platform="p",
            exc_type="E",
            exc_value="v",
            traceback="tr",
            context={},
        )
        config_path = tmp_path / "config.json"
        config_path.write_text('{"a": 1}', encoding="utf-8")
        builder = CrashBundleBuilder(crash_dir=tmp_path / "bundles", config_path=config_path)
        bundle = builder.build(r)
        import zipfile

        with zipfile.ZipFile(bundle) as z:
            names = z.namelist()
        assert "report.json" in names

    def test_bundle_contains_config(self, tmp_path: Path):
        r = CrashReport(
            timestamp="t",
            app_version="1",
            platform="p",
            exc_type="E",
            exc_value="v",
            traceback="tr",
            context={},
        )
        config_path = tmp_path / "config.json"
        config_path.write_text('{"myconfig": true}', encoding="utf-8")
        builder = CrashBundleBuilder(crash_dir=tmp_path / "bundles", config_path=config_path)
        bundle = builder.build(r)
        import zipfile

        with zipfile.ZipFile(bundle) as z, z.open("config.json") as f:
            content = f.read().decode("utf-8")
        assert "myconfig" in content


# ── CrashError ────────────────────────────────────────────────────


class TestCrashError:
    def test_inherits_exception(self):
        assert issubclass(CrashError, Exception)


# ── CrashReporterUploader ─────────────────────────────────────────


class TestUploader:
    def test_uploader_protocol_callable(self):
        """A stub implementing the Protocol is accepted."""

        class FakeUploader:
            def __init__(self) -> None:
                self.uploaded: list[Path] = []

            def upload(self, bundle_path: Path) -> bool:
                self.uploaded.append(bundle_path)
                return True

        uploader = FakeUploader()
        assert isinstance(uploader, CrashReporterUploader)
        assert uploader.upload(Path("dummy.zip")) is True
        assert len(uploader.uploaded) == 1
