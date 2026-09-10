"""Tests for ``mvp.gui.viewport_state`` (#11) — window pos/size persistence.

Pure logic: save/load + validation of "does it fit on screen".
No DPG side effects — DPG integration is tested separately.
"""

from __future__ import annotations

import json

import pytest

from mvp.gui.viewport_state import (
    ViewportState,
    load_viewport_state,
    save_viewport_state,
    validate_viewport_state,
)


def test_default_state_has_sensible_values():
    """No arguments: a sensible default (1920x1080, centered-ish)."""
    s = ViewportState()
    assert s.width > 0
    assert s.height > 0
    assert s.maximized is False
    # x/y may be 0 (default = DPG position) — accept both None and 0


class TestRoundTrip:
    def test_save_then_load_roundtrips(self, tmp_path):
        path = tmp_path / "vp.json"
        state = ViewportState(x=100, y=200, width=1280, height=720, maximized=False)

        save_viewport_state(path, state)
        loaded = load_viewport_state(path)

        assert loaded is not None
        assert loaded.x == 100
        assert loaded.y == 200
        assert loaded.width == 1280
        assert loaded.height == 720
        assert loaded.maximized is False

    def test_roundtrip_with_maximized_flag(self, tmp_path):
        path = tmp_path / "vp.json"
        state = ViewportState(x=0, y=0, width=1920, height=1080, maximized=True)

        save_viewport_state(path, state)
        loaded = load_viewport_state(path)

        assert loaded is not None
        assert loaded.maximized is True

    def test_save_creates_parent_directory(self, tmp_path):
        path = tmp_path / "nested" / "subdir" / "vp.json"
        assert not path.parent.exists()

        save_viewport_state(path, ViewportState(x=0, y=0, width=800, height=600))

        assert path.exists()
        assert path.parent.exists()


class TestLoadFailures:
    def test_load_returns_none_when_file_missing(self, tmp_path):
        path = tmp_path / "does_not_exist.json"
        assert load_viewport_state(path) is None

    def test_load_returns_none_when_corrupted_json(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{this is not valid json", encoding="utf-8")
        assert load_viewport_state(path) is None

    def test_load_returns_none_when_empty_file(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("", encoding="utf-8")
        assert load_viewport_state(path) is None

    def test_load_returns_none_when_missing_keys(self, tmp_path):
        path = tmp_path / "partial.json"
        # Brak klucza "width" / "height"
        path.write_text(json.dumps({"x": 0, "y": 0}), encoding="utf-8")
        assert load_viewport_state(path) is None

    def test_load_returns_none_when_width_is_string(self, tmp_path):
        path = tmp_path / "wrong_types.json"
        path.write_text(
            json.dumps({"x": 0, "y": 0, "width": "1920", "height": 1080}),
            encoding="utf-8",
        )
        assert load_viewport_state(path) is None


class TestValidateViewport:
    """Validation: the viewport must fit within the screen bounds."""

    def test_valid_state_passes(self):
        s = ViewportState(x=100, y=100, width=1280, height=720)
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is True

    def test_window_starting_offscreen_rejected(self):
        """Negative x (partially off-screen) → rejected."""
        s = ViewportState(x=-100, y=100, width=1280, height=720)
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is False

    def test_window_offscreen_right_rejected(self):
        s = ViewportState(x=1800, y=100, width=1280, height=720)
        # 1800 + 1280 = 3080 > 1920 → rejected
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is False

    def test_window_offscreen_bottom_rejected(self):
        s = ViewportState(x=100, y=900, width=1280, height=720)
        # 900 + 720 = 1620 > 1080 → odrzucone
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is False

    def test_zero_width_rejected(self):
        s = ViewportState(x=100, y=100, width=0, height=720)
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is False

    def test_zero_height_rejected(self):
        s = ViewportState(x=100, y=100, width=1280, height=0)
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is False

    def test_negative_width_rejected(self):
        s = ViewportState(x=100, y=100, width=-100, height=720)
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is False

    def test_maximized_window_passes_validation(self):
        """A maximized window need not stay within screen bounds — it will be
        maximized. Validation is for the state BEFORE maximizing."""
        s = ViewportState(x=0, y=0, width=1920, height=1080, maximized=True)
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is True

    def test_partial_offscreen_within_tolerance_accepted(self):
        """~20px tolerance on each side (part of the window behind the taskbar is OK)."""
        s = ViewportState(x=-15, y=-10, width=1280, height=720)
        assert validate_viewport_state(s, screen_width=1920, screen_height=1080) is True


class TestIntegrationWithValidation:
    """Full cycle: save → load → validate."""

    def test_load_validates_against_current_screen(self, tmp_path):
        path = tmp_path / "vp.json"
        # Save state for a small 1280x720 screen
        save_viewport_state(path, ViewportState(x=0, y=0, width=1280, height=720))

        loaded = load_viewport_state(path)
        assert loaded is not None
        # On a large screen OK
        assert validate_viewport_state(loaded, 1920, 1080) is True
        # On an 800x600 screen - rejected
        assert validate_viewport_state(loaded, 800, 600) is False


class TestEdgeCases:
    def test_very_small_minimum_size(self, tmp_path):
        """A minimal 320x200 size is acceptable (DPG minimum)."""
        path = tmp_path / "vp.json"
        s = ViewportState(x=0, y=0, width=320, height=200)
        save_viewport_state(path, s)
        loaded = load_viewport_state(path)
        assert loaded is not None
        assert loaded.width == 320
        assert loaded.height == 200

    def test_load_handles_extra_unknown_keys(self, tmp_path):
        """Unknown keys in JSON are ignored (forward-compat)."""
        path = tmp_path / "vp.json"
        path.write_text(
            json.dumps(
                {
                    "x": 50,
                    "y": 60,
                    "width": 1024,
                    "height": 768,
                    "maximized": False,
                    "future_feature": "ignored",
                }
            ),
            encoding="utf-8",
        )
        loaded = load_viewport_state(path)
        assert loaded is not None
        assert loaded.width == 1024


@pytest.mark.parametrize(
    "state, screen_w, screen_h, expected",
    [
        # inside
        (ViewportState(x=0, y=0, width=800, height=600), 1920, 1080, True),
        # exactly fullscreen
        (ViewportState(x=0, y=0, width=1920, height=1080), 1920, 1080, True),
        # too wide
        (ViewportState(x=0, y=0, width=2000, height=1080), 1920, 1080, False),
        # too tall
        (ViewportState(x=0, y=0, width=1920, height=2000), 1920, 1080, False),
    ],
)
def test_validate_viewport_state_parametrized(state, screen_w, screen_h, expected):
    assert validate_viewport_state(state, screen_w, screen_h) is expected
