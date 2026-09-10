
from dataclasses import dataclass

_CALIB_FULL_H: float = 1111.0
_CALIB_TB_PX: float = 31.0
_CALIB_CLIENT_H: float = 1080.0

_CALIB_TB_FRACTION: float = _CALIB_TB_PX / _CALIB_FULL_H
_CALIB_CLIENT_FRACTION: float = _CALIB_CLIENT_H / _CALIB_FULL_H

_CALIBRATION_TB_PX: int = 31


def calib_y_to_client_fraction(y_calib_pct: float) -> float:
    return max(0.0, min(1.0, (y_calib_pct / 100.0 - _CALIB_TB_FRACTION) / _CALIB_CLIENT_FRACTION))


def client_fraction_to_calib_y(y_client_fraction: float) -> float:
    return (
        _CALIB_TB_FRACTION + max(0.0, min(1.0, y_client_fraction)) * _CALIB_CLIENT_FRACTION
    ) * 100.0


@dataclass(frozen=True)
class ScreenCoord:

    x: int
    y: int


@dataclass(frozen=True)
class GamePercent:

    x_pct: float
    y_pct: float


@dataclass(frozen=True)
class GameROI:

    left: float
    top: float
    right: float
    bottom: float
    anchor: str = "stretch"

    @property
    def center(self) -> GamePercent:
        return GamePercent(
            (self.left + self.right) / 2,
            (self.top + self.bottom) / 2,
        )

    def to_pixels(self, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
        if self.anchor == "center":
            scale = frame_height / _CALIB_CLIENT_H
            center_x = frame_width / 2.0
            left_off_1080 = (self.left / 100.0 * 1920.0) - 960.0
            right_off_1080 = (self.right / 100.0 * 1920.0) - 960.0
            left = max(0, min(frame_width, int(round(center_x + left_off_1080 * scale))))
            right = max(0, min(frame_width, int(round(center_x + right_off_1080 * scale))))
        else:
            left = max(0, min(frame_width, int(round(frame_width * self.left / 100.0))))
            right = max(0, min(frame_width, int(round(frame_width * self.right / 100.0))))

        top = max(0, min(frame_height, int(round(frame_height * self.top / 100.0))))
        bottom = max(0, min(frame_height, int(round(frame_height * self.bottom / 100.0))))
        return (left, top, right, bottom)


@dataclass
class WindowContext:

    left: int
    top: int
    width: int
    height: int
    title_bar_height: int = 0
    hwnd: int = 0

    def to_screen(self, gp: GamePercent) -> ScreenCoord:
        x = int(round(self.left + self.width * gp.x_pct / 100.0))
        y = int(round(self.top + self.height * gp.y_pct / 100.0))
        return ScreenCoord(x, y)

    def roi_center_to_screen(self, roi: GameROI) -> ScreenCoord:
        if roi.anchor == "center":
            center_x = self.left + self.width / 2.0
            scale = self.height / _CALIB_CLIENT_H
            center_off_1080 = (roi.center.x_pct / 100.0 * 1920.0) - 960.0
            x = int(round(center_x + center_off_1080 * scale))
            y = int(round(self.top + self.height * roi.center.y_pct / 100.0))
            return ScreenCoord(x, y)
        return self.to_screen(roi.center)

    def roi_to_frame_pixels(
        self, roi: GameROI, frame_width: int, frame_height: int
    ) -> tuple[int, int, int, int]:
        return roi.to_pixels(frame_width, frame_height)


def game_to_screen(
    g: GamePercent,
    window_left: int,
    window_top: int,
    window_w: int,
    window_h: int,
) -> ScreenCoord:
    return ScreenCoord(
        int(window_left + window_w * g.x_pct / 100),
        int(window_top + window_h * g.y_pct / 100),
    )
