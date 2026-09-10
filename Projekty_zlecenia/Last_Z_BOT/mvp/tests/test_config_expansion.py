"""Tests for the MVP config expansion: hotkeys, notify, event log, network."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mvp.config import MVPConfig


def test_parse_key_maps_f_keys():
    from mvp.gui.global_hotkey import parse_key

    assert parse_key("F1") == 0x70
    assert parse_key("F6") == 0x75
    assert parse_key("F8") == 0x77
    assert parse_key("F12") == 0x7B


def test_parse_key_maps_letter_case_insensitive():
    from mvp.gui.global_hotkey import parse_key

    assert parse_key("a") == 0x41
    assert parse_key("A") == 0x41


def test_parse_key_raises_on_invalid():
    import pytest

    from mvp.gui.global_hotkey import parse_key

    with pytest.raises(ValueError):
        parse_key("NotAKey")


def test_new_config_fields_default():
    cfg = MVPConfig.default()
    assert cfg.hotkey_spam == "F1"
    assert cfg.hotkey_start_stop == "F6"
    assert cfg.hotkey_emergency == "F8"
    assert cfg.notify_enabled is True
    assert cfg.log_to_file is False


def test_validate_rejects_empty_hotkey():
    cfg = MVPConfig.default()
    cfg.hotkey_spam = ""
    valid, errors = cfg.validate()
    assert valid is False
    assert any("hotkey_spam" in e for e in errors)


def test_validate_rejects_invalid_hotkey():
    cfg = MVPConfig.default()
    cfg.hotkey_spam = "CTRL+F1"
    valid, errors = cfg.validate()
    assert valid is False
    assert any("hotkey_spam" in e for e in errors)


def test_notify_alert_calls_beep_when_no_sound_path():
    from mvp.gui.notify import notify_alert

    with patch("mvp.gui.notify.winsound.MessageBeep") as beep:
        notify_alert(enabled=True, sound_path="")
        beep.assert_called_once()


def test_notify_alert_is_noop_when_disabled():
    from mvp.gui.notify import notify_alert

    with patch("mvp.gui.notify.winsound.MessageBeep") as beep:
        notify_alert(enabled=False)
        beep.assert_not_called()


def test_event_logger_appends_and_flushes(tmp_path: Path):
    from mvp.bot.event_log import EventLogger

    logger = EventLogger(log_dir=tmp_path)
    logger.log("alert", {"step": 1})
    logger.flush()
    files = list(tmp_path.glob("session_*.csv"))
    assert len(files) == 1
    assert "alert" in files[0].read_text(encoding="utf-8")




def test_validate_rejects_negative_click_jitter():
    cfg = MVPConfig.default()
    cfg.click_jitter_ms = -1.0
    valid, errors = cfg.validate()
    assert valid is False
    assert any("click_jitter" in e for e in errors)


def test_event_logger_writes_json_encoded_data(tmp_path: Path):
    import csv
    import json

    from mvp.bot.event_log import EventLogger

    logger = EventLogger(log_dir=tmp_path)
    logger.log("alert", {"step": 1, "label": "krok"})
    logger.flush()
    files = list(tmp_path.glob("session_*.csv"))
    assert len(files) == 1
    with files[0].open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == 2  # header + 1 row
    data = json.loads(rows[1][2])
    assert data == {"step": 1, "label": "krok"}
