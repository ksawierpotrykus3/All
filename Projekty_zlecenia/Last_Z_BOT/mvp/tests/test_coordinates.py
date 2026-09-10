"""Tests for MVP coordinate conversions and title-bar compensation."""

import pytest

from mvp.bot.coordinates import (
    GamePercent,
    GameROI,
    ScreenCoord,
    WindowContext,
    calib_y_to_client_fraction,
    client_fraction_to_calib_y,
    game_to_screen,
)


def test_game_roi_to_pixels_basic() -> None:
    roi = GameROI(left=10.0, top=20.0, right=30.0, bottom=40.0)
    left, top, right, bottom = roi.to_pixels(1000, 500)
    assert left == 100
    assert top == 100
    assert right == 300
    assert bottom == 200


def test_calib_client_fraction_roundtrip() -> None:
    """Converting calibration Y to client fraction and back should be accurate."""
    for y_calib in [5.0, 20.0, 36.2, 50.0, 75.0, 95.0]:
        frac = calib_y_to_client_fraction(y_calib)
        assert 0.0 <= frac <= 1.0
        y_back = client_fraction_to_calib_y(frac)
        assert pytest.approx(y_back, abs=1e-5) == y_calib


def test_window_context_roi_to_frame_pixels_calibration_normalization() -> None:
    """Regardless of actual window title_bar_height (windowed 31px or borderless 0px),
    roi_to_frame_pixels maps client-space % to DXcam frame pixels with exact parity.
    """
    roi = GameROI(left=47.7, top=36.2, right=52.2, bottom=38.5)

    # Windowed mode: title_bar_height = 31
    win_windowed = WindowContext(left=0, top=31, width=1921, height=1080, title_bar_height=31)
    l1, t1, r1, b1 = win_windowed.roi_to_frame_pixels(roi, 1921, 1080)

    # Borderless mode: title_bar_height = 0
    win_borderless = WindowContext(left=0, top=0, width=1921, height=1080, title_bar_height=0)
    l2, t2, r2, b2 = win_borderless.roi_to_frame_pixels(roi, 1921, 1080)

    # Both modes must yield the exact same crop on the DXcam frame
    assert (l1, t1, r1, b1) == (l2, t2, r2, b2)
    assert l1 == int(round(1921 * 47.7 / 100.0))  # 916
    assert r1 == int(round(1921 * 52.2 / 100.0))  # 1003
    assert t1 == int(round(1080 * 36.2 / 100.0))  # 391
    assert b1 == int(round(1080 * 38.5 / 100.0))  # 416


def test_linear_scaling_across_different_resolutions() -> None:
    """ROI pixel locations must scale linearly with viewport height (e.g. 720p, 540p, 1440p)."""
    roi = GameROI(left=47.7, top=36.2, right=52.2, bottom=38.5)

    win = WindowContext(left=0, top=0, width=1920, height=1080)
    _l1080, t1080, _r1080, b1080 = win.roi_to_frame_pixels(roi, 1920, 1080)
    assert t1080 == int(round(1080 * 36.2 / 100.0))  # 391
    assert b1080 == int(round(1080 * 38.5 / 100.0))  # 416

    # 540p (half of 1080p)
    _l540, t540, _r540, b540 = win.roi_to_frame_pixels(roi, 960, 540)
    assert t540 == int(round(540 * 36.2 / 100.0))  # 195
    assert b540 == int(round(540 * 38.5 / 100.0))  # 208


def test_window_context_to_screen_mapping() -> None:
    """to_screen maps client-space percentages directly to the client area on desktop."""
    win = WindowContext(left=100, top=200, width=1000, height=1080, title_bar_height=31)

    # Point at top=36.2% client space corresponds to client row 391
    sc = win.to_screen(GamePercent(50.0, 36.2))
    assert sc == ScreenCoord(100 + 500, 200 + 391)


def test_game_to_screen() -> None:
    sc = game_to_screen(GamePercent(10.0, 20.0), 100, 200, 1000, 500)
    assert sc == ScreenCoord(200, 300)


def test_center_anchored_roi_on_custom_viewport() -> None:
    """Center-anchored ROI (e.g. Chat) must stay centered and preserve dialog width across arbitrary aspect ratios."""
    # Chat listen ROI: left=38.2, right=61.7 on 1080p base -> 733px..1185px (452px wide)
    roi = GameROI(left=38.2, top=20.2, right=61.7, bottom=91.0, anchor="center")

    win_1080 = WindowContext(left=0, top=0, width=1920, height=1080)
    l1080, t1080, r1080, b1080 = win_1080.roi_to_frame_pixels(roi, 1920, 1080)
    assert abs(l1080 - 733) <= 1
    assert abs(r1080 - 1185) <= 1
    assert abs((r1080 - l1080) - 452) <= 1

    # Narrow / tablet viewport (1024x884)
    win_narrow = WindowContext(left=0, top=0, width=1024, height=884)
    ln, tn, rn, bn = win_narrow.roi_to_frame_pixels(roi, 1024, 884)
    # Expected width: 452 * (884/1080) ≈ 370px, centered around 512px -> 327px..697px
    assert abs(ln - 327) <= 2
    assert abs(rn - 697) <= 2
    assert abs((rn - ln) - 370) <= 2
