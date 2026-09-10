"""Unit tests for ChatArrowDetector (transparent arrow template matching)."""

import cv2
import numpy as np
import pytest

from mvp.bot.arrow_detector import ROI_CHAT_ARROW, ChatArrowDetector


def test_arrow_detector_loads_template() -> None:
    detector = ChatArrowDetector()
    assert detector._template_bgr is not None
    assert detector._template_bgr.shape[:2] == (20, 25)
    assert detector._template_mask is not None
    assert detector._template_mask.shape == (20, 25)


def test_arrow_detector_returns_none_when_no_arrow() -> None:
    detector = ChatArrowDetector()
    blank = np.zeros((200, 200, 3), dtype=np.uint8)
    blank[:] = (100, 100, 100)
    found = detector.find_arrow(blank, threshold=0.90)
    assert found is None


def test_arrow_detector_rejects_translation_icon() -> None:
    """Translation icon (A/T square badge) must NEVER trigger arrow detection."""
    for path in [
        r"C:/Users/maksk/.gemini/antigravity/brain/68739702-dc9b-4aaa-837b-967b9b648d52/.user_uploaded/media_1787361116285.png",
        r"C:/Users/maksk/.gemini/antigravity/brain/68739702-dc9b-4aaa-837b-967b9b648d52/.user_uploaded/media_1787374887908.png",
    ]:
        bad_img = cv2.imread(path)
        if bad_img is None:
            continue
        detector = ChatArrowDetector()
        found = detector.find_arrow(bad_img, threshold=0.85)
        assert found is None


def test_arrow_detector_on_real_chat_screenshot() -> None:
    chat_img = cv2.imread("data/images/analysis/chat.png")
    if chat_img is None:
        pytest.skip("data/images/analysis/chat.png not found")

    detector = ChatArrowDetector()
    h, w = chat_img.shape[:2]
    left = int(ROI_CHAT_ARROW["left"] / 100.0 * w)
    top = int(ROI_CHAT_ARROW["top"] / 100.0 * h)
    right = int(ROI_CHAT_ARROW["right"] / 100.0 * w)
    bottom = int(ROI_CHAT_ARROW["bottom"] / 100.0 * h)

    found = detector.find_arrow(chat_img, roi_rect=(left, top, right, bottom))
    assert found is not None
    cx, cy, score = found
    # Center of arrow in chat.png is at (1176, 937)
    assert abs(cx - 1176) <= 2
    assert abs(cy - 937) <= 2
    assert score >= 0.95


def test_arrow_detector_on_windowed_screenshot_with_message_background() -> None:
    """Arrow must be detected on windowed (1024x538) screenshots where message bubble is behind it."""
    win_img = cv2.imread(
        r"C:/Users/maksk/.gemini/antigravity/brain/68739702-dc9b-4aaa-837b-967b9b648d52/.user_uploaded/media_1787374573986.png"
    )
    if win_img is None:
        pytest.skip("media_1787374573986.png not found")

    detector = ChatArrowDetector()
    h, w = win_img.shape[:2]
    left = int(ROI_CHAT_ARROW["left"] / 100.0 * w)
    top = int(ROI_CHAT_ARROW["top"] / 100.0 * h)
    right = int(ROI_CHAT_ARROW["right"] / 100.0 * w)
    bottom = int(ROI_CHAT_ARROW["bottom"] / 100.0 * h)

    found = detector.find_arrow(win_img, roi_rect=(left, top, right, bottom), threshold=0.92)
    assert found is not None
    cx, cy, score = found
    assert abs(cx - 616) <= 2
    assert abs(cy - 470) <= 2
    assert score >= 0.95


def test_arrow_detector_on_scaled_viewport() -> None:
    """Arrow must be detected on downscaled / arbitrary resolution windows."""
    chat_img = cv2.imread("data/images/analysis/chat.png")
    if chat_img is None:
        pytest.skip("data/images/analysis/chat.png not found")

    # Downscale by 0.6x (e.g. 720p window)
    scaled = cv2.resize(chat_img, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA)
    detector = ChatArrowDetector()
    h, w = scaled.shape[:2]
    left = int(ROI_CHAT_ARROW["left"] / 100.0 * w)
    top = int(ROI_CHAT_ARROW["top"] / 100.0 * h)
    right = int(ROI_CHAT_ARROW["right"] / 100.0 * w)
    bottom = int(ROI_CHAT_ARROW["bottom"] / 100.0 * h)

    found = detector.find_arrow(scaled, roi_rect=(left, top, right, bottom), threshold=0.92)
    assert found is not None
    cx, cy, score = found
    assert abs(cx - int(1176 * 0.6)) <= 2
    assert abs(cy - int(937 * 0.6)) <= 2
    assert score >= 0.95
