from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np

from mvp.bot.clicker import precise_sleep, precise_sleep_until
from mvp.bot.ocr import ChatOCR, TimerOCR
from mvp.bot.runner import BotRunner
from mvp.bot.window_finder import _find_process_pids, _pid_cache
from mvp.config import MVPConfig
from mvp.gui.main_window import MainWindow
from mvp.gui.state import GuiState


def test_timer_ocr_fast_hash_avoids_tobytes_allocation():
    """Verify that TimerOCR.read_timer caches results with sampling without error."""
    ocr = TimerOCR()
    img = np.zeros((50, 100, 3), dtype=np.uint8)

    with patch.object(ocr, "_read_timer_uncached", return_value=42) as mock_uncached:
        res1 = ocr.read_timer(img)
        assert res1 == 42
        assert mock_uncached.call_count == 1

        # Second call with identical image should return cached value without calling _read_timer_uncached
        res2 = ocr.read_timer(img)
        assert res2 == 42
        assert mock_uncached.call_count == 1


def test_window_finder_pid_cache():
    """Verify that _find_process_pids caches and reuses results."""
    from mvp.bot import window_finder

    _pid_cache.clear()
    with patch.object(
        window_finder, "_find_process_pids_toolhelp", return_value={12345}
    ) as mock_toolhelp, patch("psutil.pid_exists", return_value=True):
        pids1 = _find_process_pids("Survival.exe")
        assert 12345 in pids1
        assert mock_toolhelp.call_count == 1

        # Second call within TTL should reuse cache without re-enumerating.
        pids2 = _find_process_pids("Survival.exe")
        assert 12345 in pids2
        assert mock_toolhelp.call_count == 1


def test_precise_sleep_tolerances():
    """Verify precise_sleep and precise_sleep_until finish accurately with yields."""
    t0 = time.perf_counter()
    precise_sleep(0.005)
    elapsed = time.perf_counter() - t0
    assert elapsed >= 0.0045

    t1 = time.perf_counter()
    precise_sleep_until(t1 + 0.005)
    elapsed2 = time.perf_counter() - t1
    assert elapsed2 >= 0.0045


def test_main_window_frame_queue_drained_when_preview_disabled():
    """Verify that _update_frame_texture drains frame_queue when preview is disabled."""
    config = MVPConfig.default()
    config.preview_enabled = False
    state = GuiState()
    # Put frames in queue
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    state.frame_queue.put_nowait(dummy_frame)
    state.frame_queue.put_nowait(dummy_frame)

    win = MainWindow(config, state)
    with patch("dearpygui.dearpygui.set_value"):
        win._update_frame_texture()

    assert state.frame_queue.empty()


def test_bot_runner_shutdown_stops_anti_detect():
    """Verify that BotRunner.shutdown stops anti_detect."""
    config = MVPConfig.default()
    runner = BotRunner(config)
    with patch.object(runner.anti_detect, "stop") as mock_stop, \
         patch.object(runner, "stop"), \
         patch.object(runner, "stop_window_monitor"), \
         patch.object(runner._frame_producer, "stop"), \
         patch.object(runner.capture, "stop"), \
         patch.object(runner.clicker, "shutdown"), \
         patch.object(runner.sleep_guard, "shutdown"):
        runner.shutdown()
        mock_stop.assert_called_once()


def test_chat_ocr_avoids_rapid_fallback_when_winocr_succeeds():
    """Verify that ChatOCR does not trigger heavy RapidOCR when WinOCR produces valid lines."""
    from mvp.bot.ocr import ChatOCR

    ocr = ChatOCR()
    ocr._winocr_ok = True
    ocr._winocr_lang = "en-US"
    ocr._rapid = MagicMock()

    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch("winocr.recognize_cv2_sync", return_value={"lines": [{"text": "Just regular random text"}]}):
        # find_helicopter_alert
        res = ocr.find_helicopter_alert(dummy_img)
        assert res is None
        ocr._rapid.assert_not_called()

        # is_alliance_chat_open
        res_alliance = ocr.is_alliance_chat_open(dummy_img)
        assert res_alliance is False
        ocr._rapid.assert_not_called()

        # is_chat_window_open
        res_chat = ocr.is_chat_window_open(dummy_img)
        assert res_chat is False
        ocr._rapid.assert_not_called()

        # is_details_dialog_open
        res_details = ocr.is_details_dialog_open(dummy_img)
        assert res_details is False
        ocr._rapid.assert_not_called()

    # When hint is present in WinOCR lines, RapidOCR SHOULD be called as fallback
    ocr._rapid.return_value = ([], None)
    with patch("winocr.recognize_cv2_sync", return_value={"lines": [{"text": "I found a new treasure spot!"}]}):
        ocr.find_helicopter_alert(dummy_img)
        ocr._rapid.assert_called_once()


def test_sendinput_metrics_cache():
    """Verify that SendInputBackend caches GetSystemMetrics within TTL."""
    from mvp.bot.input.sendinput_backend import SendInputBackend

    backend = SendInputBackend()
    backend._user32 = MagicMock()
    backend._user32.GetSystemMetrics.side_effect = lambda metric: 0 if metric in (76, 77) else (1920 if metric == 78 else 1080)

    nx1, ny1 = backend._to_normalized_coords(500, 500)
    assert backend._user32.GetSystemMetrics.call_count == 4

    # Second call within TTL should NOT call GetSystemMetrics again
    nx2, ny2 = backend._to_normalized_coords(600, 600)
    assert backend._user32.GetSystemMetrics.call_count == 4
    assert nx1 > 0 and ny1 > 0


def test_window_finder_wndenumproc_singleton():
    """Verify that _WNDENUMPROC is defined on module level."""
    from mvp.bot.window_finder import _WNDENUMPROC
    assert _WNDENUMPROC is not None


def test_arrow_detector_template_cache():
    """Verify that ChatArrowDetector caches resized templates across find_arrow calls."""
    from mvp.bot.arrow_detector import ChatArrowDetector

    detector = ChatArrowDetector()
    detector._template_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    detector._template_mask = None
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    assert len(detector._template_cache) == 0
    detector.find_arrow(frame)
    cached_len = len(detector._template_cache)
    assert cached_len > 0

    with patch("cv2.resize") as mock_resize:
        detector.find_arrow(frame)
        mock_resize.assert_not_called()


def test_macro_engine_checkpoint_skips_redundant_writes(tmp_path):
    """Verify that MacroEngine._save_checkpoint skips writing if state is unchanged."""
    from mvp.bot.macro_engine import MacroEngine

    ckpt_file = tmp_path / "ckpt.json"
    engine = MacroEngine(
        clicker=MagicMock(),
        chat_ocr=MagicMock(),
        timer_ocr=MagicMock(),
        capture=MagicMock(),
        checkpoint_path=ckpt_file,
    )
    engine.total_steps = 5

    with patch("pathlib.Path.write_text") as mock_write, patch("os.replace"):
        engine._save_checkpoint(1)
        assert mock_write.call_count == 1

        # Second save with identical state should NOT write to disk
        engine._save_checkpoint(1)
        assert mock_write.call_count == 1


def test_main_window_event_log_flush_guard():
    """Verify that MainWindow does not spawn duplicate flush threads when flush is in progress."""
    config = MVPConfig.default()
    state = GuiState()
    win = MainWindow(config, state)
    win._event_logger = MagicMock()
    win._event_logger._buffer = [("test", {})]
    win._event_log_flush_in_progress = True
    win._event_log_last_flush = time.monotonic() - 10.0

    with patch("threading.Thread") as mock_thread, \
         patch("mvp.gui.main_window.dpg"):
        win._render_loop()
        mock_thread.assert_not_called()

        # When not in progress, it should start a thread
        win._event_log_flush_in_progress = False
        win._render_loop()
        mock_thread.assert_called_once()


def test_chat_ocr_bounty_truck_clean_exit_without_rapidocr():
    """Verify that messages with 'State' like Bounty Missions or Truck do not trigger heavy RapidOCR."""
    ocr = ChatOCR()
    ocr._winocr_ok = True
    ocr._winocr_lang = "pl"
    ocr._rapid = MagicMock()

    # Simulated WinOCR lines containing State from Bounty Missions, but NO explore/treasure cues
    mock_winocr_res = {
        "lines": [
            {"text": "Bounty Missions", "words": []},
            {"text": "Rescue Survivors [State 746 X:392 Y:576]", "words": []},
            {"text": "Truck @10.33M State 746", "words": []},
        ]
    }

    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch("winocr.recognize_cv2_sync", return_value=mock_winocr_res):
        res = ocr.find_helicopter_alert(dummy_img)

    assert res is None
    # RapidOCR must NEVER be called for Bounty Missions / Truck announcements
    ocr._rapid.assert_not_called()
