"""Tests for MVP configuration."""

from pathlib import Path

from mvp.config import MVPConfig


def test_defaults_match_spec() -> None:
    cfg = MVPConfig.default()
    assert cfg.process_name == "Survival.exe"
    assert cfg.spam_clicks_per_sec == 30
    assert cfg.spam_duration_s == 6.0
    assert cfg.spam_threshold_s == 5
    assert cfg.spam_noise_px == 3.0
    assert cfg.click_jitter_ms == 0.5
    assert cfg.idle_check_interval_s == 3.0
    assert cfg.fast_check_interval_s == 0.2
    assert cfg.fast_threshold_s == 60
    # Anti-sleep defaults: enabled, block display+system, no away mode.
    assert cfg.prevent_sleep is True
    assert cfg.prevent_display_off is True
    assert cfg.anti_sleep_away_mode is False


def test_validate_accepts_defaults() -> None:
    valid, errors = MVPConfig.default().validate()
    assert valid is True
    assert errors == []


def test_validate_rejects_bad_fast_threshold() -> None:
    for bad in (0, 3601):
        cfg = MVPConfig.default()
        cfg.fast_threshold_s = bad
        valid, errors = cfg.validate()
        assert valid is False
        assert any("fast_threshold_s" in e for e in errors)


def test_validate_rejects_max_delay_below_min() -> None:
    cfg = MVPConfig.default()
    cfg.click_min_delay_ms = 400
    cfg.click_max_delay_ms = 100
    valid, errors = cfg.validate()
    assert valid is False
    assert any("click" in e for e in errors)


def test_validate_rejects_bad_spam_cps() -> None:
    for bad in (0, 39):
        cfg = MVPConfig.default()
        cfg.spam_clicks_per_sec = bad
        valid, errors = cfg.validate()
        assert valid is False
        assert any("spam_clicks_per_sec" in e for e in errors)


def test_from_dict_ignores_unknown_keys() -> None:
    cfg = MVPConfig.from_dict({"foo": 1, "scan_fps": 15})
    assert cfg.scan_fps == 15


def test_load_or_default_returns_default_for_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    cfg = MVPConfig.load_or_default(path)
    assert cfg == MVPConfig.default()
    # The default config is now written so the GUI has a persisted baseline.
    assert path.exists()


def test_load_or_default_falls_back_on_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{ not valid json", encoding="utf-8")
    cfg = MVPConfig.load_or_default(path)
    assert cfg == MVPConfig.default()
    # The corrupt file is overwritten with a valid default config.
    assert MVPConfig.load(path) == MVPConfig.default()


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = MVPConfig.default()
    cfg.spam_clicks_per_sec = 35
    cfg.save(path)
    loaded = MVPConfig.load(path)
    assert loaded.spam_clicks_per_sec == 35
    assert loaded == cfg


def test_validate_rejects_cps_over_limit_in_60fps() -> None:
    cfg = MVPConfig.default()
    cfg.spam_clicks_per_sec = 60
    valid, errors = cfg.validate()
    assert valid is False
    assert any("spam_clicks_per_sec" in e and "35" in e for e in errors)


def test_save_accepts_string_path(tmp_path: Path) -> None:
    cfg = MVPConfig.default()
    path = tmp_path / "str_path.json"
    cfg.save(str(path))
    assert path.exists()
    assert MVPConfig.load(path) == cfg


def test_anti_sleep_roundtrip(tmp_path) -> None:
    """Anti-sleep settings survive JSON serialisation (used by ``save``/``load``)."""
    cfg = MVPConfig.default()
    cfg.prevent_sleep = False
    cfg.prevent_display_off = False
    cfg.anti_sleep_away_mode = True

    path = tmp_path / "anti_sleep.json"
    cfg.save(path)
    loaded = MVPConfig.load(path)

    assert loaded.prevent_sleep is False
    assert loaded.prevent_display_off is False
    assert loaded.anti_sleep_away_mode is True


def test_validate_accepts_anti_sleep_disabled() -> None:
    cfg = MVPConfig.default()
    cfg.prevent_sleep = False
    cfg.prevent_display_off = False
    valid, errors = cfg.validate()
    assert valid, errors


def test_validate_process_priority() -> None:
    cfg = MVPConfig.default()
    assert cfg.process_priority == "normal"

    for valid_val in ("normal", "below_normal", "idle"):
        cfg.process_priority = valid_val
        valid, errors = cfg.validate()
        assert valid is True, errors

    cfg.process_priority = "invalid_priority"
    valid, errors = cfg.validate()
    assert valid is False
    assert any("process_priority" in e for e in errors)
