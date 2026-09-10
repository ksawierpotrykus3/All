"""Tests for #2 — anti-detect ptrace / anti-debug.

Goals:
- Cross-platform: Windows (``CheckRemoteDebuggerPresent``) + Linux/Proton
  (``/proc/self/status`` TracerPid, ``prctl(PR_SET_DUMPABLE, 0)``).
- Best-effort hardening — no crash when a function is unavailable.
- Background detection (optional loop every N seconds with a callback).
- Hook: ``on_debugger_detected`` called on detection.

Mocking strategy:
- ``sys.platform`` monkeypatched to 'win32' / 'linux'.
- ``ctypes.windll.kernel32`` — fake object with ``CheckRemoteDebuggerPresent``.
- ``open()`` — fake file for ``/proc/self/status``.
- ``AntiDetect`` picks the implementation per platform once at construction.
"""

from __future__ import annotations

import pytest

from mvp.bot.anti_detect import (
    AntiDetect,
    AntiDetectError,
)


class FakeKernel32:
    """Stub for ``ctypes.windll.kernel32`` with a controlled detection result."""

    def __init__(self, debugger_present: bool = False):
        self._debugger_present = debugger_present
        self.call_count = 0

    def __getattr__(self, name):
        if name == "CheckRemoteDebuggerPresent":
            return self._check_remote_debugger_present
        if name == "GetCurrentProcess":
            # Windows returns a pseudo-handle (-1); tests don't need the real one.
            return lambda: -1
        raise AttributeError(name)

    def _check_remote_debugger_present(self, *args, **kwargs):
        self.call_count += 1
        if len(args) >= 2:
            target = args[1]
            new_value = 1 if self._debugger_present else 0
            obj = getattr(target, "_obj", None)
            if obj is not None and hasattr(obj, "value"):
                obj.value = new_value
            elif hasattr(target, "value"):
                target.value = new_value
        return 1  # nonzero = success


class FakeProcFile:
    """Stub for the ``/proc/self/status`` file with a controlled TracerPid."""

    def __init__(self, tracer_pid: int = 0):
        self._content = f"Name:\tpython\nTracerPid:\t{tracer_pid}\nUid:\t1000\t1000\t1000\t1000\n"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self._content.splitlines(keepends=True))

    def read(self) -> str:
        return self._content

    def readline(self):
        return self._content.splitlines()[0] + "\n"

    def readlines(self):
        return self._content.splitlines(keepends=True)

    def close(self) -> None:
        pass


class TestAntiDetectWindowsDebuggerDetection:
    """Debugger detection on Windows — ``CheckRemoteDebuggerPresent``."""

    def test_no_debugger_detected(self, monkeypatch):
        """No debugger → ``detect_debugger()`` returns False."""
        monkeypatch.setattr("sys.platform", "win32")
        fake_k32 = FakeKernel32(debugger_present=False)
        monkeypatch.setattr("mvp.bot.anti_detect._kernel32", fake_k32)

        ad = AntiDetect()
        assert ad.detect_debugger() is False

    def test_debugger_detected(self, monkeypatch):
        """With a debugger → ``detect_debugger()`` returns True."""
        monkeypatch.setattr("sys.platform", "win32")
        fake_k32 = FakeKernel32(debugger_present=True)
        monkeypatch.setattr("mvp.bot.anti_detect._kernel32", fake_k32)

        ad = AntiDetect()
        assert ad.detect_debugger() is True

    def test_uses_cached_handle(self, monkeypatch):
        """The process handle is cached (1× GetCurrentProcess)."""
        monkeypatch.setattr("sys.platform", "win32")
        fake_k32 = FakeKernel32(debugger_present=False)
        monkeypatch.setattr("mvp.bot.anti_detect._kernel32", fake_k32)

        ad = AntiDetect()
        ad.detect_debugger()
        ad.detect_debugger()
        ad.detect_debugger()

        # Check multiple calls — should be efficient
        assert fake_k32.call_count == 3

    def test_check_remote_fails_silently(self, monkeypatch):
        """When ``CheckRemoteDebuggerPresent`` returns 0 (failure) → no crash."""
        monkeypatch.setattr("sys.platform", "win32")

        class BrokenKernel32:
            def __getattr__(self, name):
                def fail(*a, **k):
                    return 0  # failure

                return fail

        monkeypatch.setattr("mvp.bot.anti_detect._kernel32", BrokenKernel32())

        ad = AntiDetect()
        # Should not raise — returns False (assume no debugger)
        assert ad.detect_debugger() is False


class TestAntiDetectLinuxDebuggerDetection:
    """Debugger detection on Linux/Proton — ``/proc/self/status`` TracerPid."""

    def test_no_debugger_when_tracer_pid_zero(self, monkeypatch):
        """TracerPid=0 → no debugger."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("builtins.open", lambda *a, **k: FakeProcFile(tracer_pid=0))

        ad = AntiDetect()
        assert ad.detect_debugger() is False

    def test_debugger_detected_when_tracer_pid_nonzero(self, monkeypatch):
        """TracerPid != 0 → debugger attached."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("builtins.open", lambda *a, **k: FakeProcFile(tracer_pid=1234))

        ad = AntiDetect()
        assert ad.detect_debugger() is True

    def test_proc_file_missing_returns_false(self, monkeypatch):
        """When ``/proc/self/status`` is unavailable → False (safe fallback)."""
        monkeypatch.setattr("sys.platform", "linux")

        def raise_oserror(*a, **k):
            raise OSError("no /proc")

        monkeypatch.setattr("builtins.open", raise_oserror)

        ad = AntiDetect()
        assert ad.detect_debugger() is False

    def test_malformed_proc_returns_false(self, monkeypatch):
        """Malformed file format → False (safe fallback)."""
        monkeypatch.setattr("sys.platform", "linux")

        class GarbageFile:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return "no tracer info here\n"

            def close(self):
                pass

        monkeypatch.setattr("builtins.open", lambda *a, **k: GarbageFile())

        ad = AntiDetect()
        assert ad.detect_debugger() is False


class TestAntiDetectHardenProcess:
    """Process hardening — disable ptrace / core dumps."""

    def test_windows_harden_is_best_effort(self, monkeypatch):
        """Windows harden does not crash when the function is unavailable."""
        monkeypatch.setattr("sys.platform", "win32")

        class BrokenKernel32:
            def __getattr__(self, name):
                raise OSError("not supported")

        monkeypatch.setattr("mvp.bot.anti_detect._kernel32", BrokenKernel32())

        ad = AntiDetect()
        # Should not raise
        ad.harden_process()

    def test_linux_harden_calls_prctl_when_available(self, monkeypatch):
        """Linux harden calls ``prctl`` with the appropriate flags."""
        monkeypatch.setattr("sys.platform", "linux")

        prctl_calls = []

        class FakeLibc:
            def prctl(self, option, *args):
                prctl_calls.append((option, args))
                return 0

        monkeypatch.setattr("ctypes.CDLL", lambda name, **kw: FakeLibc())

        ad = AntiDetect()
        ad.harden_process()

        # Should call prctl with PR_SET_DUMPABLE=4
        assert any(call[0] == 4 for call in prctl_calls)

    def test_linux_harden_silent_when_prctl_unavailable(self, monkeypatch):
        """No libc → harden silently skips (best effort)."""
        monkeypatch.setattr("sys.platform", "linux")

        def raise_oserror(name):
            raise OSError(f"no {name}")

        monkeypatch.setattr("ctypes.CDLL", raise_oserror)

        ad = AntiDetect()
        # Should not raise
        ad.harden_process()

    def test_unknown_platform_is_noop(self, monkeypatch):
        """Darwin / other → harden is a no-op (does not crash)."""
        monkeypatch.setattr("sys.platform", "darwin")

        ad = AntiDetect()
        ad.harden_process()  # no-op


class TestAntiDetectPlatformSelection:
    """Platform selection at construction."""

    def test_uses_windows_backend_on_win32(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "win32")
        ad = AntiDetect()
        assert ad.platform == "win32"

    def test_uses_linux_backend_on_linux(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        ad = AntiDetect()
        assert ad.platform == "linux"

    def test_unsupported_platform_is_noop(self, monkeypatch):
        """Unsupported platform (darwin) constructs fine and detect_debugger returns False."""
        monkeypatch.setattr("sys.platform", "darwin")
        ad = AntiDetect()
        assert ad.platform == "darwin"
        assert ad.detect_debugger() is False


class TestAntiDetectPeriodicCheck:
    """Background thread — checks for a debugger every N seconds."""

    def test_periodic_check_calls_callback_when_debugger_found(self, monkeypatch):
        """After a debugger is detected — callback with ``detected=True``."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("builtins.open", lambda *a, **k: FakeProcFile(tracer_pid=999))

        callback_calls = []

        ad = AntiDetect(check_interval_s=0.01)
        ad.start_periodic_check(callback=lambda d: callback_calls.append(d))
        # Give the thread time to run 1-2 cycles
        import time

        time.sleep(0.05)
        ad.stop()

        assert len(callback_calls) >= 1
        assert all(c is True for c in callback_calls)

    def test_periodic_check_stops_cleanly(self, monkeypatch):
        """``stop()`` ends the thread in <1s."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("builtins.open", lambda *a, **k: FakeProcFile(tracer_pid=0))

        ad = AntiDetect(check_interval_s=0.05)
        ad.start_periodic_check(callback=lambda d: None)
        import time

        time.sleep(0.05)
        ad.stop()
        # Should return in <0.5s
        t0 = time.monotonic()
        ad.join(timeout=0.5)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5

    def test_periodic_check_double_start_idempotent(self, monkeypatch):
        """A second ``start_periodic_check`` call does not create a second thread."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("builtins.open", lambda *a, **k: FakeProcFile(tracer_pid=0))

        ad = AntiDetect(check_interval_s=0.05)
        ad.start_periodic_check(callback=lambda d: None)
        first_thread = ad._thread
        ad.start_periodic_check(callback=lambda d: None)
        assert ad._thread is first_thread
        ad.stop()


class TestAntiDetectConstructor:
    """Constructor — parameters."""

    def test_default_check_interval(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        ad = AntiDetect()
        assert ad.check_interval_s == 30.0

    def test_custom_check_interval(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        ad = AntiDetect(check_interval_s=5.0)
        assert ad.check_interval_s == 5.0

    def test_negative_interval_raises(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        with pytest.raises(ValueError):
            AntiDetect(check_interval_s=-1.0)


class TestAntiDetectError:
    def test_anti_detect_error_is_exception(self):
        assert issubclass(AntiDetectError, Exception)


class TestAntiDetectRunOnceAtStartup:
    """``check_and_harden_on_startup()`` — typical use case at bot startup."""

    def test_returns_status_dict(self, monkeypatch):
        """Returns ``{'debugger_detected': bool, 'hardened': bool}``."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("builtins.open", lambda *a, **k: FakeProcFile(tracer_pid=0))

        ad = AntiDetect()
        result = ad.check_and_harden_on_startup()
        assert "debugger_detected" in result
        assert "hardened" in result
        assert isinstance(result["debugger_detected"], bool)
        assert isinstance(result["hardened"], bool)

    def test_debugger_detected_flag_propagated(self, monkeypatch):
        """When a debugger is present — the ``debugger_detected=True`` flag in the result."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("builtins.open", lambda *a, **k: FakeProcFile(tracer_pid=42))

        ad = AntiDetect()
        result = ad.check_and_harden_on_startup()
        assert result["debugger_detected"] is True
