
from __future__ import annotations

import sys
import threading
import traceback
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


class CrashError(Exception):
    pass


@dataclass(frozen=True)
class CrashReport:

    timestamp: str
    app_version: str
    platform: str
    exc_type: str
    exc_value: str
    traceback: str
    context: Mapping[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "app_version": self.app_version,
            "platform": self.platform,
            "exc_type": self.exc_type,
            "exc_value": self.exc_value,
            "traceback": self.traceback,
            "context": dict(self.context),
        }


@runtime_checkable
class CrashReporterUploader(Protocol):

    def upload(self, bundle_path: Path) -> bool: ...


class CrashHandler:

    def __init__(
        self,
        *,
        app_version: str = "0.0.0",
        max_reports: int = 10,
    ) -> None:
        self._app_version = app_version
        self._max_reports = max_reports
        self.reports: list[CrashReport] = []
        self._sys_hook = None
        self._thread_hook = None

    @staticmethod
    def format_traceback(exc: BaseException) -> str:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    def capture_exception(
        self,
        exc: BaseException,
        context: Mapping[str, str] | None = None,
    ) -> CrashReport:
        report = CrashReport(
            timestamp=datetime.now().isoformat(),
            app_version=self._app_version,
            platform=sys.platform,
            exc_type=type(exc).__name__,
            exc_value=str(exc),
            traceback=self.format_traceback(exc),
            context=dict(context or {}),
        )
        self.reports.append(report)
        if len(self.reports) > self._max_reports:
            self.reports = self.reports[-self._max_reports :]
        return report

    def _handle_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_value is None:
            return
        self.capture_exception(exc_value)

    def install(self) -> None:
        self._sys_hook = sys.excepthook
        sys.excepthook = self._handle_exception
        self._thread_hook = threading.excepthook
        threading.excepthook = self._thread_hook_proxy

    def _thread_hook_proxy(self, args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            self.capture_exception(args.exc_value)

    def uninstall(self) -> None:
        if self._sys_hook is not None:
            sys.excepthook = self._sys_hook
            self._sys_hook = None
        if self._thread_hook is not None:
            threading.excepthook = self._thread_hook
            self._thread_hook = None


class CrashBundleBuilder:

    def __init__(
        self,
        *,
        crash_dir: Path,
        config_path: Path | None,
    ) -> None:
        self._crash_dir = crash_dir
        self._config_path = config_path

    def build(self, report: CrashReport) -> Path:
        import json

        self._crash_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = self._crash_dir / f"crash-{report.timestamp.replace(':', '-')}.zip"
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("report.json", json.dumps(report.to_dict(), indent=2))
            if self._config_path is not None and self._config_path.exists():
                zf.write(self._config_path, arcname="config.json")
        return bundle_path
