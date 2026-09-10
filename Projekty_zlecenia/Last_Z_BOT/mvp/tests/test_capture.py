"""Tests for ``mvp.bot.capture.ScreenCapture`` DXGI access loss watchdog.

L1: ``ScreenCapture.grab()`` must survive ``DXGI_ERROR_ACCESS_LOSS``
    (0x887A0026) — return the last known frame or ``None``.

L2 (#6): Watchdog detects a "zombie camera" — grab() returns the same frame
    for >N seconds without a new frame. In that state the camera is dead and
    must be restarted automatically by ``health_check()`` + ``_restart_camera()``.

L3 (#6): After ``_max_recoveries`` consecutive restarts without improvement the
    camera enters LOCKED state — ``health_check()`` returns ``False`` and logs
    an ERROR instead of restarting forever.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest


class _FakeDXCamera:
    """Minimal stub for ``dxcam.DXCamera`` used by the watchdog tests."""

    def __init__(
        self, *, frame_seq: list[Any] | None = None, raise_on_grab: Exception | None = None
    ) -> None:
        self._frame_seq = list(frame_seq or [])
        self._raise_on_grab = raise_on_grab
        self.released = False
        self.grab_calls = 0

    def grab(self, region: tuple[int, int, int, int] | None = None):
        self.grab_calls += 1
        if self._raise_on_grab is not None:
            raise self._raise_on_grab
        if self._frame_seq:
            return self._frame_seq.pop(0)
        return None

    def release(self) -> None:
        self.released = True


@pytest.fixture
def patched_dxcam(monkeypatch):
    """Patch ``dxcam.create`` to return controlled fakes."""

    created_cameras: list[_FakeDXCamera] = []

    def fake_create(output_idx: int | None = None, output_color: str = "BGR"):
        cam = _FakeDXCamera()
        created_cameras.append(cam)
        return cam

    monkeypatch.setattr("mvp.bot.capture.dxcam.create", fake_create)
    return created_cameras


class TestHealthyState:
    def test_capture_starts_healthy(self, patched_dxcam):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100))
        cap.start()

        # Before the first grab() there is no frame yet — but the camera
        # exists, so it is not "dead".
        assert cap.is_healthy is True

    def test_fresh_frame_marks_healthy(self, patched_dxcam):
        from mvp.bot.capture import ScreenCapture

        # Default grab() returns None (empty frame_seq), so no frame is stored.
        # Provide a concrete frame instead.
        patched_dxcam.clear()
        import numpy as np

        cam_with_frame = _FakeDXCamera(frame_seq=[np.zeros((10, 10, 3), dtype=np.uint8)])
        patched_dxcam.append(cam_with_frame)

        from mvp.bot import capture as cap_mod

        cap_mod.dxcam.create = lambda *a, **k: cam_with_frame  # type: ignore[assignment]

        cap = ScreenCapture(region=(0, 0, 100, 100))
        cap.start()
        frame = cap.grab()
        assert frame is not None
        assert cap.is_healthy is True

    def test_healthy_grab_does_not_trigger_recovery(self, patched_dxcam):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100))
        cap.start()

        # First health_check without grab() — freshly created camera, OK
        result = cap.health_check()
        assert result is True
        assert cap.recovery_count == 0


class TestDeadCameraDetection:
    def test_capture_detects_dead_when_no_frame_for_too_long(self, patched_dxcam, monkeypatch):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100), dead_threshold_s=0.5)
        cap.start()
        # Force a timestamp from the past
        cap._latest_frame_ts = time.monotonic() - 10.0
        cap._latest_frame = object()

        assert cap.is_healthy is False

    def test_capture_alive_when_frame_fresh(self, patched_dxcam):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100), dead_threshold_s=1.0)
        cap.start()
        cap._latest_frame_ts = time.monotonic()
        cap._latest_frame = object()

        assert cap.is_healthy is True


class TestAutoRecovery:
    def test_health_check_restarts_dead_camera(self, patched_dxcam, monkeypatch):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100), dead_threshold_s=0.5)
        cap.start()

        # First camera: "old" with a dead timestamp
        first_cam = patched_dxcam[0]
        cap._latest_frame_ts = time.monotonic() - 10.0
        cap._latest_frame = object()

        result = cap.health_check()

        assert result is True  # recovery performed
        assert cap.recovery_count == 1
        assert first_cam.released is True  # old one released
        assert cap._camera is not None and cap._camera is not first_cam

    def test_recovery_counter_increments(self, patched_dxcam, monkeypatch):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100), dead_threshold_s=0.5)
        cap.start()

        # Simulate: 3 times detected "dead" and recovered
        for _ in range(3):
            cap._latest_frame_ts = time.monotonic() - 10.0
            cap._latest_frame = object()
            cap.health_check()

        assert cap.recovery_count == 3

    def test_recovery_preserves_region_and_output_idx(self, patched_dxcam):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(100, 200, 800, 600))
        cap._output_idx = 1
        cap.start()
        original_region = cap._region
        original_output = cap._output_idx

        cap._latest_frame_ts = time.monotonic() - 10.0
        cap._latest_frame = object()
        cap.health_check()

        assert cap._region == original_region
        assert cap._output_idx == original_output


class TestRecoveryLockout:
    def test_after_max_recoveries_health_check_returns_false(self, patched_dxcam, caplog):
        import logging

        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(
            region=(0, 0, 100, 100),
            dead_threshold_s=0.5,
            max_recoveries=3,
        )
        cap.start()

        # Force continuous "dead" (frame from the past)
        for _ in range(5):
            cap._latest_frame_ts = time.monotonic() - 10.0
            cap._latest_frame = object()
            cap.health_check()

        # After 3 recoveries the 4th health_check must return False and not restart
        initial_cameras = len(patched_dxcam)
        cap._latest_frame_ts = time.monotonic() - 10.0
        cap._latest_frame = object()

        with caplog.at_level(logging.ERROR, logger="mvp.bot.capture"):
            result = cap.health_check()

        assert result is False
        assert cap.recovery_count == 3
        assert len(patched_dxcam) == initial_cameras  # no new camera

    def test_locked_state_is_exposed(self, patched_dxcam):
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100), dead_threshold_s=0.5, max_recoveries=2)
        cap.start()

        # 2x recovery → camera locked
        for _ in range(2):
            cap._latest_frame_ts = time.monotonic() - 10.0
            cap._latest_frame = object()
            cap.health_check()

        assert cap.is_locked is True


class TestExistingDXGIAccessLossBehavior:
    def test_grab_returns_last_frame_on_dxgi_access_loss(self, patched_dxcam):
        import numpy as np

        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100))
        cap.start()

        # Force a concrete first frame
        first_frame = np.zeros((10, 10, 3), dtype=np.uint8)
        first_frame[0, 0] = 99  # marker
        cap._camera._frame_seq = [first_frame]  # type: ignore[attr-defined]

        frame1 = cap.grab()
        assert frame1 is not None
        assert int(frame1[0, 0, 0]) == 99

        # Now grab() raises DXGI access loss — must return the last frame
        cap._camera._raise_on_grab = OSError("0x887A0026 DXGI_ERROR_ACCESS_LOSS")  # type: ignore[attr-defined]
        frame2 = cap.grab()
        assert frame2 is not None
        assert int(frame2[0, 0, 0]) == 99


class TestThreadSafety:
    def test_health_check_thread_safe_with_concurrent_grabs(self, patched_dxcam):
        """health_check and grab() may run concurrently — no race condition."""
        from mvp.bot.capture import ScreenCapture

        cap = ScreenCapture(region=(0, 0, 100, 100), dead_threshold_s=0.1)
        cap.start()

        errors: list[Exception] = []

        def grabber():
            try:
                for _ in range(20):
                    cap.grab()
                    time.sleep(0.001)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        def watcher():
            try:
                for _ in range(20):
                    cap.health_check()
                    time.sleep(0.001)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        t1 = threading.Thread(target=grabber, daemon=True)
        t2 = threading.Thread(target=watcher, daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert errors == []