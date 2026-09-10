
import contextlib
import ctypes
import logging
import threading
import time

import dxcam
import numpy as np

logger = logging.getLogger(__name__)

logging.getLogger("dxcam").setLevel(logging.ERROR)
logging.getLogger("dxcam.core.dxgi_duplicator").setLevel(logging.ERROR)
logging.getLogger("dxcam.dxcam").setLevel(logging.ERROR)

DPI_AWARENESS_PER_MONITOR = 2

_MAX_FRAME_AGE_SECONDS = 5.0


def setup_dpi_awareness() -> None:
    ctypes.windll.shcore.SetProcessDpiAwareness(DPI_AWARENESS_PER_MONITOR)


class ScreenCapture:
    def __init__(
        self,
        region: tuple[int, int, int, int] | None = None,
        dead_threshold_s: float = 5.0,
        max_recoveries: int = 5,
    ) -> None:
        self._region = region
        self._camera: dxcam.DXCamera | None = None
        self._output_idx: int | None = None
        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._latest_frame_ts: float = 0.0
        self._dead_threshold_s = float(dead_threshold_s)
        self._max_recoveries = int(max_recoveries)
        self._recovery_count = 0
        self._is_locked = False
        self._frame_source = None

    def __del__(self) -> None:
        self.stop()

    @property
    def region(self) -> tuple[int, int, int, int] | None:
        with self._lock:
            return self._region

    @region.setter
    def region(self, value: tuple[int, int, int, int] | None) -> None:
        with self._lock:
            self._region = value

    def set_frame_source(self, source) -> None:
        """
        Set an external callable returning a BGR frame (np.ndarray) or None.

        When set, grab() returns frames from this source instead of capturing
        the screen via dxcam. Used for simulator-driven bot testing.
        """
        self._frame_source = source

    def start(self) -> None:
        with self._lock:
            if self._camera is not None:
                return
            idx = self._output_idx if self._output_idx is not None else 0
            try:
                self._camera = dxcam.create(output_idx=idx, output_color="BGR")
            except Exception as exc:
                logger.error("DXcam create failed for output %s: %s", idx, exc)
                self._camera = None
        logger.info("ScreenCapture started (region=%s)", self._region)

    def grab(self) -> np.ndarray | None:
        # Prefer the external frame source (simulator) over real screen capture.
        if self._frame_source is not None:
            try:
                frame = self._frame_source()
                if frame is not None:
                    with self._lock:
                        self._latest_frame = frame
                        self._latest_frame_ts = time.monotonic()
                    return frame
            except Exception as exc:
                logger.warning("frame source grab failed: %s", exc)

        with self._lock:
            if self._camera is None:
                return None
            camera = self._camera
            region = self._region
            try:
                frame = camera.grab(region=region)
            except Exception as exc:
                err_str = str(exc)
                if (
                    "0x887A0026" in err_str
                    or "access loss" in err_str.lower()
                    or "access_loss" in err_str.lower()
                ):
                    logger.debug(
                        "DXcam access loss detected, returning last frame (recovery handled by dxcam)"
                    )
                else:
                    logger.warning("DXcam grab failed: %s", exc)
                if (
                    self._latest_frame is not None
                    and (time.monotonic() - self._latest_frame_ts) < _MAX_FRAME_AGE_SECONDS
                ):
                    return self._latest_frame
                return None

            if frame is not None:
                self._latest_frame = frame
                self._latest_frame_ts = time.monotonic()
                return frame
            if (
                self._latest_frame is not None
                and (time.monotonic() - self._latest_frame_ts) < _MAX_FRAME_AGE_SECONDS
            ):
                return self._latest_frame
            return None

    def stop(self) -> None:
        with self._lock:
            if self._camera is not None:
                cam = self._camera
                self._camera = None
                with contextlib.suppress(Exception):
                    cam.release()
        logger.info("ScreenCapture stopped")


    @property
    def is_healthy(self) -> bool:
        if not self.is_running:
            return False
        if self._is_locked:
            return False
        with self._lock:
            if self._latest_frame is None:
                return True
            return (time.monotonic() - self._latest_frame_ts) < self._dead_threshold_s

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    def reset_lockout(self) -> None:
        with self._lock:
            self._is_locked = False
            self._recovery_count = 0

    def health_check(self) -> bool:
        with self._lock:
            if self._is_locked:
                logger.error(
                    "ScreenCapture is LOCKED after %d restarts — "
                    "check the game window and click 'Reset camera' in the GUI.",
                    self._recovery_count,
                )
                return False

            if self._camera is None:
                return False

            if self._latest_frame is None:
                return True

            age = time.monotonic() - self._latest_frame_ts
            if age < self._dead_threshold_s:
                return True

            logger.warning(
                "DXcam did not deliver a frame for %.1fs (threshold %.1fs) — restarting camera",
                age,
                self._dead_threshold_s,
            )
            old_cam = self._camera
            self._camera = None
            with contextlib.suppress(Exception):
                old_cam.release()

            idx = self._output_idx if self._output_idx is not None else 0
            try:
                self._camera = dxcam.create(output_idx=idx, output_color="BGR")
            except Exception as exc:
                logger.error("DXcam restart failed for output %s: %s", idx, exc)
                self._camera = None
                self._is_locked = True
                return False

            self._recovery_count += 1
            self._latest_frame = None
            self._latest_frame_ts = 0.0

            if self._recovery_count >= self._max_recoveries:
                logger.warning(
                    "DXcam restarted %d times — entering LOCKED state "
                    "(further recovery disabled, requires manual intervention).",
                    self._recovery_count,
                )
                self._is_locked = True
                return True

            return True

    def set_output(self, output_idx: int) -> None:
        with self._lock:
            if output_idx != self._output_idx:
                self._restart_camera(output_idx)
                logger.info("ScreenCapture output switched to %d", output_idx)

    def _restart_camera(self, output_idx: int | None = None) -> None:
        if self._camera is not None:
            cam = self._camera
            self._camera = None
            with contextlib.suppress(Exception):
                cam.release()
        idx = output_idx if output_idx is not None else self._output_idx
        try:
            self._camera = (
                dxcam.create(output_idx=idx, output_color="BGR")
                if idx is not None
                else dxcam.create(output_color="BGR")
            )
        except Exception as exc:
            logger.error("DXcam create/restart failed for output %s: %s", idx, exc)
            self._camera = None
        self._output_idx = idx

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._camera is not None
