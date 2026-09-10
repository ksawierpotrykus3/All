"""Tests for modal_detector.find_march_confirm_modal."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from mvp.bot.modal_detector import find_march_confirm_modal


def test_find_march_confirm_modal_none_on_empty() -> None:
    assert find_march_confirm_modal(None) is None
    assert find_march_confirm_modal(np.zeros((0, 0, 3), dtype=np.uint8)) is None


def test_find_march_confirm_modal_none_on_blank_frame() -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    assert find_march_confirm_modal(frame) is None


def test_find_march_confirm_modal_detects_synthetic_yellow_button() -> None:
    # 1920x1080 frame
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # Put yellow button at x=800, y=600, w=180, h=50
    # Yellow in BGR: (0, 215, 255)
    frame[600:650, 800:980] = (0, 215, 255)

    res = find_march_confirm_modal(frame)
    assert res is not None
    confirm_x, confirm_y, cb_x, cb_y = res
    assert 880 <= confirm_x <= 900
    assert 620 <= confirm_y <= 630
    assert cb_y < confirm_y  # checkbox is above button


def test_find_march_confirm_modal_on_real_user_paint_screenshot() -> None:
    path = (
        Path.home()
        / ".gemini/antigravity/brain/b34187b8-4544-450e-8c26-84edfe23c72b/.user_uploaded/media_1788623136550.png"
    )
    if not path.exists():
        return
    img = cv2.imread(str(path))
    res = find_march_confirm_modal(img)
    assert res is not None
    confirm_x, confirm_y, cb_x, cb_y = res
    assert 440 <= confirm_x <= 480
    assert 310 <= confirm_y <= 340


def test_find_march_confirm_modal_none_on_clean_screen() -> None:
    path = (
        Path.home()
        / ".gemini/antigravity/brain/b34187b8-4544-450e-8c26-84edfe23c72b/.user_uploaded/media_1788622902804.jpg"
    )
    if not path.exists():
        return
    img = cv2.imread(str(path))
    res = find_march_confirm_modal(img)
    assert res is None, "Clean screen without modal must return None"


def test_find_march_confirm_modal_handles_grayscale() -> None:
    frame_2d = np.zeros((1080, 1920), dtype=np.uint8)
    assert find_march_confirm_modal(frame_2d) is None

