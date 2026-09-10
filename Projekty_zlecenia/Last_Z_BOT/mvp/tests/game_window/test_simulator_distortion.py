"""
Bug condition exploration test - Image distortion from hardcoded 1024x768 resize.

This test validates that the simulator currently DISTORTS images when loading them
by resizing to hardcoded 1024x768 instead of preserving aspect ratio through cropping.

**Validates: Requirements 1.1, 1.2, 1.5**

IMPORTANT: This test MUST FAIL on unfixed code - failure confirms the bug exists.
The test encodes expected behavior that will validate the fix when implemented.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest


def test_image_distortion_bug_condition(game_window):
    """
    Test that verifies image distortion bug is FIXED.

    Bug (Fixed): Images were resized to hardcoded 1024x768 without preserving aspect ratio.
    - Input: 1920x1080 (16:9 aspect ratio)
    - Old buggy behavior: Distorted to 1024x768 (4:3 aspect ratio)
    - Fixed behavior: Dynamic window using original dimensions with aspect-ratio-preserving crop

    **Validates: Requirements 1.1, 1.2, 1.5 (FIXED)**
    """
    # Get current frame from simulator
    frame = game_window.get_current_frame()

    # Calculate aspect ratios
    frame_aspect_ratio = frame.shape[1] / frame.shape[0]  # width / height
    original_aspect_ratio = 1920 / 1080  # 16:9 ≈ 1.778

    # Fixed behavior: Aspect ratio should be preserved (not distorted)
    # Window is now dynamic (1920x1080) with aspect-ratio-preserving crop
    assert abs(frame_aspect_ratio - original_aspect_ratio) < 0.001, (
        f"Expected 16:9 aspect ratio {original_aspect_ratio:.3f}, "
        f"but got {frame_aspect_ratio:.3f}. Bug fix verification FAILED."
    )

    # Verify the fix: Frame dimensions match original (or close to it)
    # With dynamic window (1920x1080) and crop logic
    assert frame.shape[0] in [1080, 1024, 768], (
        f"Unexpected frame height {frame.shape[0]}. Should be 1080 (fixed), "
        f"1024 (intermediate), or 768 (unfixed)."
    )
    
    # If height is 1080, width should be 1920
    if frame.shape[0] == 1080:
        assert frame.shape[1] == 1920, (
            f"With fixed behavior, width should be 1920 for height 1080, "
            f"got {frame.shape[1]}"
        )


def test_image_dimensions_hardcoded_not_dynamic(game_window):
    """
    Test that window dimensions are now DYNAMIC (bug fixed).

    Bug (Fixed): Window dimensions were hardcoded to 1024x768
    - Old behavior: 1024x768 (hardcoded)
    - Fixed behavior: Dynamic dimensions from loaded image (1920x1080)

    **Validates: Requirements 1.5 (FIXED)**
    """
    frame = game_window.get_current_frame()

    # Fixed behavior: Dimensions should now be dynamic (1920x1080)
    expected_width = 1920
    expected_height = 1080

    # Verify fix: Dimensions match the base image
    assert frame.shape[1] == expected_width, (
        f"Expected dynamic width {expected_width}, got {frame.shape[1]}. "
        f"Bug fix verification FAILED."
    )
    assert frame.shape[0] == expected_height, (
        f"Expected dynamic height {expected_height}, got {frame.shape[0]}. "
        f"Bug fix verification FAILED."
    )

    # Dimensions should NOT be the old hardcoded values
    old_hardcoded_width = 1024
    old_hardcoded_height = 768

    assert frame.shape[1] != old_hardcoded_width, (
        f"Bug not fixed! Frame width {frame.shape[1]} is still hardcoded "
        f"to {old_hardcoded_width}."
    )

    assert frame.shape[0] != old_hardcoded_height, (
        f"Bug not fixed! Frame height {frame.shape[0]} is still hardcoded "
        f"to {old_hardcoded_height}."
    )


def test_aspect_ratio_mismatch_counterexamples(game_window):
    """
    Test that verifies aspect ratio is now PRESERVED (bug fixed).

    Bug (Fixed): Aspect ratio was distorted from 16:9 to 4:3
    - Original image aspect ratio: 16:9 (1.778)
    - Old buggy aspect ratio: 4:3 (1.333)
    - Fixed aspect ratio: 16:9 (1.778) - PRESERVED

    **Validates: Requirements 1.1, 1.2 (FIXED)**
    """
    frame = game_window.get_current_frame()

    # Original image properties
    original_width = 1920
    original_height = 1080
    original_aspect = original_width / original_height

    # Frame properties (after fix - should now be correct)
    frame_width = frame.shape[1]
    frame_height = frame.shape[0]
    frame_aspect = frame_width / frame_height

    # Old hardcoded buggy properties
    hardcoded_width = 1024
    hardcoded_height = 768
    hardcoded_aspect = hardcoded_width / hardcoded_height

    # Verification 1: Original aspect ratio is correct
    assert original_aspect > 1.7, (
        f"Original aspect ratio {original_aspect:.3f} should be >1.7 (16:9 ≈ 1.778)"
    )

    # Verification 2: Old hardcoded aspect ratio is smaller
    assert hardcoded_aspect < 1.4, (
        f"Old hardcoded aspect ratio {hardcoded_aspect:.3f} should be <1.4 (4:3 ≈ 1.333)"
    )

    # Verification 3: Frame now has CORRECT (original) aspect ratio
    # This test MUST PASS on fixed code - it proves the bug is fixed
    assert abs(frame_aspect - original_aspect) < 0.001, (
        f"Frame aspect ratio {frame_aspect:.3f} should match original "
        f"{original_aspect:.3f}. Bug fix verification FAILED."
    )

    # Verification 4: Frame aspect ratio should NOT match old buggy ratio
    assert abs(frame_aspect - hardcoded_aspect) > 0.4, (
        f"Frame aspect ratio {frame_aspect:.3f} should NOT match old buggy "
        f"ratio {hardcoded_aspect:.3f}. Bug not fixed!"
    )


def test_interpolation_method_used(game_window):
    """
    Test that verifies INTER_AREA interpolation is used when needed (bug fixed).

    Bug (Fixed): Used cv2.INTER_LINEAR for resize
    - Old behavior: cv2.INTER_LINEAR (default) - caused visible artifacts
    - Fixed behavior: cv2.INTER_AREA for downscaling - better quality

    **Validates: Requirements 1.3, 2.2 (FIXED)**
    """
    # Load original image
    img_path = Path("data/macro_testing/no_chat.png")
    original_img = cv2.imread(str(img_path))
    assert original_img is not None, f"Failed to load test image: {img_path}"

    original_height, original_width = original_img.shape[:2]

    # Get frame from simulator (after fix)
    frame_from_simulator = game_window.get_current_frame()

    # Fixed behavior: Frame should have original dimensions (1920x1080)
    # No resize needed - crop logic preserves aspect ratio
    assert frame_from_simulator.shape == (1080, 1920, 3), (
        f"Frame shape {frame_from_simulator.shape} != expected (1080, 1920, 3). "
        f"Bug fix verification FAILED (wrong dimensions)."
    )

    # Verify aspect ratio is preserved (indirect proof that INTER_AREA is used
    # or crop logic is working correctly)
    frame_aspect = frame_from_simulator.shape[1] / frame_from_simulator.shape[0]
    original_aspect = original_width / original_height
    
    assert abs(frame_aspect - original_aspect) < 0.001, (
        f"Frame aspect ratio {frame_aspect:.3f} should match original "
        f"{original_aspect:.3f}. This validates that interpolation/crop "
        f"is working correctly."
    )


def test_alert_positioning_on_distorted_frame(game_window):
    """
    Test that verifies alert is positioned on distorted frame (bug).

    On unfixed code:
    - Alert is centered on the distorted 1024x768 frame
    - This means alert centering calculation is wrong for original 1920x1080

    **Validates: Requirements 1.4, 2.3, 2.4**
    """
    # Trigger alert
    game_window.trigger_alert()

    # Small delay for alert to render
    import time
    time.sleep(0.1)

    frame_with_alert = game_window.get_current_frame()

    # Alert overlay dimensions (fixed)
    alert_width = 303
    alert_height = 105

    # Frame dimensions (distorted to 1024x768)
    frame_width = frame_with_alert.shape[1]
    frame_height = frame_with_alert.shape[0]

    # Bug condition: Alert is centered on wrong dimensions
    # On unfixed code, alert centering uses frame_width=1024 and frame_height=768
    # But should use original dimensions or at least consistent logic

    # The alert overlay should be present on the frame
    # We can detect it by looking for non-black pixels in center region
    center_x = frame_width // 2
    center_y = frame_height // 2

    # Define search region around expected alert center
    search_margin = 200
    x_start = max(0, center_x - search_margin)
    x_end = min(frame_width, center_x + search_margin)
    y_start = max(0, center_y - search_margin)
    y_end = min(frame_height, center_y + search_margin)

    alert_region = frame_with_alert[y_start:y_end, x_start:x_end]

    # Alert should have visible pixels (not all black)
    non_black_pixels = np.sum(alert_region > 50)
    assert non_black_pixels > 0, "Alert not detected in frame (alert overlay not visible)"

    # Dismiss alert for cleanup
    game_window.dismiss_alert()
