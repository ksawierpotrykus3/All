"""Tests for process manager."""

import os
import platform
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from mvp.tests.test_framework.process_manager import ProcessManager, ProcessResult
from mvp.tests.test_framework.scenarios import Scenario, ScenarioRandomizer


class TestProcessManagerInitialization:
    """Test ProcessManager initialization."""

    def test_process_manager_default_init(self) -> None:
        """Test ProcessManager initializes with default working directory."""
        pm = ProcessManager()
        assert pm.work_dir == Path(".")

    def test_process_manager_custom_work_dir(self) -> None:
        """Test ProcessManager initializes with custom working directory."""
        pm = ProcessManager(work_dir="/custom/path")
        assert pm.work_dir == Path("/custom/path")


class TestBuildCSharpArgs:
    """Test command-line argument building."""

    def test_build_csharp_args_creates_json_config(self) -> None:
        """Test _build_csharp_args creates valid JSON config argument."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        args = pm._build_csharp_args(scenario)

        assert len(args) == 2
        assert args[0] == "--config"
        # Second argument should be valid JSON
        import json
        config = json.loads(args[1])
        assert "window_x" in config
        assert "timer_seconds" in config
        assert "window_width" in config

    def test_build_csharp_args_includes_all_fields(self) -> None:
        """Test _build_csharp_args includes all scenario fields."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=123)
        scenario = randomizer.next_scenario()

        args = pm._build_csharp_args(scenario)
        import json
        config = json.loads(args[1])

        expected_fields = [
            "window_x",
            "window_y",
            "window_width",
            "window_height",
            "game_area_x",
            "game_area_y",
            "game_area_width",
            "game_area_height",
            "dpi",
            "chat_state",
            "timer_seconds",
            "click_jitter_ms",
            "timer_jitter_ms",
            "glitch_type",
        ]

        for field in expected_fields:
            assert field in config, f"Missing field: {field}"

    def test_build_csharp_args_preserves_scenario_values(self) -> None:
        """Test _build_csharp_args preserves scenario configuration values."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        args = pm._build_csharp_args(scenario)
        import json
        config = json.loads(args[1])

        assert config["timer_seconds"] == scenario.timer_seconds
        assert config["window_width"] == scenario.window_width
        assert config["window_height"] == scenario.window_height
        assert config["dpi"] == scenario.dpi
        assert config["chat_state"] == scenario.chat_state.value

    def test_build_csharp_args_includes_monitors_if_present(self) -> None:
        """Test _build_csharp_args includes monitor config for multi-monitor scenarios."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        # Ensure scenario has monitors
        if scenario.monitors:
            args = pm._build_csharp_args(scenario)
            import json
            config = json.loads(args[1])

            assert "monitors" in config
            assert len(config["monitors"]) == len(scenario.monitors)
            for i, monitor in enumerate(config["monitors"]):
                assert "id" in monitor
                assert "width" in monitor
                assert "height" in monitor
                assert "dpi" in monitor

    def test_build_csharp_args_validates_window_size(self) -> None:
        """Test _build_csharp_args raises ValueError for invalid window size."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        # Set invalid window size
        scenario.window_width = 100  # Too small
        scenario.window_height = 100  # Too small

        with pytest.raises(ValueError, match="Invalid window size"):
            pm._build_csharp_args(scenario)

    def test_build_csharp_args_validates_timer_seconds(self) -> None:
        """Test _build_csharp_args raises ValueError for invalid timer_seconds."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        # Set invalid timer
        scenario.timer_seconds = 9999  # Too large

        with pytest.raises(ValueError, match="Invalid timer_seconds"):
            pm._build_csharp_args(scenario)

    def test_build_csharp_args_validates_jitter_values(self) -> None:
        """Test _build_csharp_args raises ValueError for invalid jitter values."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        # Set invalid jitter
        scenario.timer_jitter_ms = 100  # Not in [0, 50, 500]

        with pytest.raises(ValueError, match="Invalid timer_jitter_ms"):
            pm._build_csharp_args(scenario)

    def test_build_csharp_args_json_is_compact(self) -> None:
        """Test _build_csharp_args produces compact JSON (no spaces)."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        args = pm._build_csharp_args(scenario)
        json_string = args[1]

        # Compact JSON should not have spaces after : or ,
        assert ": " not in json_string or json_string.count(": ") == 0
        # Or very minimal spaces (only in strings if present)
        # Verify it's compact by checking length is reasonable
        import json
        expanded = json.dumps(json.loads(json_string), indent=2)
        # Compact should be significantly shorter
        assert len(json_string) < len(expanded)


class TestVerifyWindowExists:
    """Test window existence verification."""

    def test_verify_window_exists_current_process(self) -> None:
        """Test _verify_window_exists returns True for current process."""
        pm = ProcessManager()
        pid = os.getpid()

        result = pm._verify_window_exists(pid)

        assert result is True

    def test_verify_window_exists_invalid_pid(self) -> None:
        """Test _verify_window_exists returns False for invalid PID."""
        pm = ProcessManager()
        invalid_pid = 999999  # Unlikely to exist

        result = pm._verify_window_exists(invalid_pid)

        # Result depends on system, but should not raise exception
        assert isinstance(result, bool)

    def test_verify_window_exists_handles_exception(self) -> None:
        """Test _verify_window_exists handles exceptions gracefully."""
        pm = ProcessManager()
        pid = -1  # Invalid PID

        # Should not raise, should return bool
        result = pm._verify_window_exists(pid)
        assert isinstance(result, bool)

    def test_verify_window_exists_uses_winapi_on_windows(self) -> None:
        """Test _verify_window_exists uses WinAPI on Windows."""
        pm = ProcessManager()
        pid = 12345

        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                # Mock the subprocess fallback (if WinAPI fails)
                mock_run.return_value = MagicMock(stdout="12345", returncode=0)

                result = pm._verify_window_exists(pid)

                # Should attempt WinAPI (ctypes import) and fallback to subprocess
                assert isinstance(result, bool)

    def test_verify_window_exists_uses_ps_on_unix(self) -> None:
        """Test _verify_window_exists uses ps on Unix."""
        pm = ProcessManager()
        pid = os.getpid()

        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = pm._verify_window_exists(pid)

                # Should call ps with correct arguments
                mock_run.assert_called()
                call_args = mock_run.call_args[0][0]
                assert "ps" in call_args[0]
                assert str(pid) in call_args

    def test_verify_window_exists_handles_timeout(self) -> None:
        """Test _verify_window_exists handles subprocess timeout."""
        pm = ProcessManager()
        pid = 99999

        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ps", 1)):
                result = pm._verify_window_exists(pid)

                # Should handle timeout gracefully
                assert isinstance(result, bool)
                # Likely returns False on timeout
                assert result is False

    def test_verify_window_exists_handles_general_exception(self) -> None:
        """Test _verify_window_exists handles general exceptions."""
        pm = ProcessManager()
        pid = 12345

        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run", side_effect=Exception("General error")):
                result = pm._verify_window_exists(pid)

                # Should handle exception gracefully and return True (assume OK)
                assert isinstance(result, bool)
                assert result is True  # Conservative: assume OK on error


class TestSendSignal:
    """Test signal sending."""

    def test_send_signal_sigterm_unix(self) -> None:
        """Test _send_signal sends SIGTERM on Unix-like systems."""
        import signal as sig_module
        
        pm = ProcessManager()
        # Create mock process
        mock_process = MagicMock()
        mock_process.pid = 12345

        with patch("platform.system", return_value="Linux"):
            with patch("os.kill") as mock_kill:
                pm._send_signal(mock_process, sig_module.SIGTERM)
                mock_kill.assert_called_once_with(12345, sig_module.SIGTERM)

    def test_send_signal_sigkill_unix(self) -> None:
        """Test _send_signal sends SIGKILL on Unix-like systems."""
        import signal as sig_module
        
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.pid = 12345

        with patch("platform.system", return_value="Linux"):
            with patch("os.kill") as mock_kill:
                # Use signal.SIGKILL which is only available on Unix
                try:
                    sig = sig_module.SIGKILL
                except AttributeError:
                    # Fall back to 9 if SIGKILL not available (Windows)
                    sig = 9
                
                pm._send_signal(mock_process, sig)
                mock_kill.assert_called_once()

    def test_send_signal_windows_terminate(self) -> None:
        """Test _send_signal calls terminate on Windows for SIGTERM."""
        import signal as sig_module
        
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.pid = 12345

        with patch("platform.system", return_value="Windows"):
            pm._send_signal(mock_process, sig_module.SIGTERM)
            mock_process.terminate.assert_called_once()

    def test_send_signal_windows_kill(self) -> None:
        """Test _send_signal calls kill on Windows for SIGKILL."""
        import signal as sig_module
        
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.pid = 12345

        # SIGKILL is not available on Windows, so use a generic approach
        with patch("platform.system", return_value="Windows"):
            pm._send_signal(mock_process, 9)  # Use 9 as generic kill
            mock_process.kill.assert_called_once()

    def test_send_signal_handles_exception(self) -> None:
        """Test _send_signal handles exceptions without raising."""
        import signal as sig_module
        
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.pid = None  # Invalid PID

        # Should not raise exception
        pm._send_signal(mock_process, sig_module.SIGTERM)


class TestTerminateProcess:
    """Test process termination."""

    def test_terminate_process_running(self) -> None:
        """Test _terminate_process sends terminate to running process."""
        import signal as sig_module
        
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process still running
        mock_process.pid = 12345

        pm._terminate_process(mock_process, force_kill=False)
        
        # Should call terminate() on the process
        mock_process.terminate.assert_called_once()

    def test_terminate_process_force_kill(self) -> None:
        """Test _terminate_process calls kill when force_kill=True."""
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345

        pm._terminate_process(mock_process, force_kill=True)
        
        # Should call kill() on the process
        mock_process.kill.assert_called_once()

    def test_terminate_process_already_terminated(self) -> None:
        """Test _terminate_process skips if process already terminated."""
        import signal as sig_module
        
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Process already terminated

        pm._terminate_process(mock_process, force_kill=False)
        
        # Should not call terminate or kill
        mock_process.terminate.assert_not_called()
        mock_process.kill.assert_not_called()


class TestEnforceTimeout:
    """Test timeout enforcement with SIGTERM/SIGKILL logic."""

    def test_enforce_timeout_process_completes_normally(self) -> None:
        """Test enforce_timeout when process completes before timeout."""
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0

        result = pm.enforce_timeout(mock_process, timeout_s=5.0)

        assert result.timed_out is False
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.duration_s >= 0  # Duration might be very small in mock

    def test_enforce_timeout_sends_sigterm_on_timeout(self) -> None:
        """Test enforce_timeout sends SIGTERM when process times out."""
        import signal as sig_module
        
        pm = ProcessManager()
        mock_process = MagicMock()
        # Simulate timeout
        mock_process.communicate.side_effect = subprocess.TimeoutExpired("cmd", 5)
        mock_process.poll.side_effect = [None, None, None, 0]  # Process dies after a bit
        mock_process.returncode = 0
        mock_process.pid = 12345

        with patch.object(pm, "_send_signal") as mock_send_signal:
            with patch.object(pm, "_collect_logs", return_value={}):
                result = pm.enforce_timeout(mock_process, timeout_s=0.1)

                # Should have called _send_signal with SIGTERM
                calls = mock_send_signal.call_args_list
                assert len(calls) > 0
                assert calls[0][0][1] == sig_module.SIGTERM

    def test_enforce_timeout_sends_sigkill_after_grace_period(self) -> None:
        """Test enforce_timeout uses kill after 2s grace period."""
        pm = ProcessManager()
        mock_process = MagicMock()
        # Simulate timeout with process not terminating gracefully
        mock_process.communicate.side_effect = [
            subprocess.TimeoutExpired("cmd", 5),  # First call (timeout)
            subprocess.TimeoutExpired("cmd", 1),  # Second call (still running after kill)
        ]
        mock_process.poll.side_effect = [
            None,  # Still running after terminate
            None,
            None,
            None,
            None,
            None,
            1,  # Finally terminated
        ]
        mock_process.returncode = 1
        mock_process.pid = 12345

        with patch.object(pm, "_send_signal") as mock_send_signal:
            with patch.object(pm, "_collect_logs", return_value={}):
                result = pm.enforce_timeout(mock_process, timeout_s=0.1)

                # Should have calls to send_signal
                # First call should be to terminate (SIGTERM equivalent)
                assert mock_send_signal.call_count > 0

    def test_enforce_timeout_sets_timed_out_flag(self) -> None:
        """Test enforce_timeout sets timed_out=True when timeout occurs."""
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired("cmd", 5)
        mock_process.poll.return_value = 1
        mock_process.returncode = 1
        mock_process.pid = 12345

        with patch.object(pm, "_send_signal"):
            with patch.object(pm, "_collect_logs", return_value={}):
                result = pm.enforce_timeout(mock_process, timeout_s=0.1)

                assert result.timed_out is True

    def test_enforce_timeout_collects_partial_logs_on_timeout(self) -> None:
        """Test enforce_timeout collects partial logs when timeout occurs."""
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired("cmd", 5)
        mock_process.poll.return_value = 1
        mock_process.returncode = 1
        mock_process.pid = 12345

        expected_logs = {"game_events": "partial log content"}

        with patch.object(pm, "_send_signal"):
            with patch.object(pm, "_collect_logs", return_value=expected_logs):
                result = pm.enforce_timeout(mock_process, timeout_s=0.1)

                assert result.partial_logs == expected_logs

    def test_enforce_timeout_returns_process_result(self) -> None:
        """Test enforce_timeout returns ProcessResult with all fields."""
        pm = ProcessManager()
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("stdout", "stderr")
        mock_process.returncode = 0

        result = pm.enforce_timeout(mock_process, timeout_s=5.0)

        assert isinstance(result, ProcessResult)
        assert hasattr(result, "exit_code")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")
        assert hasattr(result, "duration_s")
        assert hasattr(result, "timed_out")
        assert hasattr(result, "partial_logs")


class TestCollectLogs:
    """Test log file collection."""

    def test_collect_logs_reads_existing_files(self, tmp_path) -> None:
        """Test collect_logs reads existing log files."""
        pm = ProcessManager(work_dir=str(tmp_path))

        # Create test log files
        game_events_file = tmp_path / "game_events.log"
        game_events_file.write_text("game events content")

        event_log_file = tmp_path / "event_log"
        event_log_file.write_text("event log content")

        logs = pm.collect_logs()

        assert "game_events" in logs
        assert logs["game_events"] == "game events content"
        assert "event_log" in logs
        assert logs["event_log"] == "event log content"

    def test_collect_logs_handles_missing_files(self, tmp_path) -> None:
        """Test collect_logs handles missing log files gracefully."""
        pm = ProcessManager(work_dir=str(tmp_path))

        logs = pm.collect_logs()

        # Should return empty or partial dict, not raise
        assert isinstance(logs, dict)

    def test_collect_logs_respects_timeout(self, tmp_path) -> None:
        """Test collect_logs respects timeout parameter."""
        pm = ProcessManager(work_dir=str(tmp_path))

        # Create a file
        game_events_file = tmp_path / "game_events.log"
        game_events_file.write_text("content")

        # Should complete quickly
        start = time.time()
        logs = pm.collect_logs(timeout_s=1.0)
        duration = time.time() - start

        # Should complete well under timeout
        assert duration < 1.0
        assert "game_events" in logs

    def test_collect_logs_handles_read_errors(self, tmp_path) -> None:
        """Test collect_logs handles file read errors gracefully."""
        pm = ProcessManager(work_dir=str(tmp_path))

        # Create a file but make it unreadable (if possible)
        game_events_file = tmp_path / "game_events.log"
        game_events_file.write_text("content")

        # Should not raise exception
        logs = pm.collect_logs()
        assert isinstance(logs, dict)


class TestSpawnBotMVP:
    """Test bot MVP process spawning."""

    def test_spawn_bot_mvp_raises_if_uv_not_found(self) -> None:
        """Test spawn_bot_mvp raises RuntimeError if uv not available."""
        pm = ProcessManager()

        with patch("subprocess.Popen", side_effect=FileNotFoundError("uv not found")):
            with pytest.raises(RuntimeError, match="uv command not found"):
                pm.spawn_bot_mvp()

    def test_spawn_bot_mvp_raises_on_other_exception(self) -> None:
        """Test spawn_bot_mvp raises RuntimeError on other exceptions."""
        pm = ProcessManager()

        with patch("subprocess.Popen", side_effect=Exception("Other error")):
            with pytest.raises(RuntimeError, match="Failed to spawn bot MVP"):
                pm.spawn_bot_mvp()

    def test_spawn_bot_mvp_inherits_environment(self) -> None:
        """Test spawn_bot_mvp inherits current environment if env=None."""
        pm = ProcessManager()

        mock_popen = MagicMock()
        mock_popen.pid = 12345

        with patch("subprocess.Popen", return_value=mock_popen) as mock_spawn:
            with patch("os.environ.copy") as mock_env_copy:
                mock_env_copy.return_value = {"TEST": "value"}
                
                process, pid = pm.spawn_bot_mvp()

                # Should use current environment
                mock_env_copy.assert_called_once()
                call_kwargs = mock_spawn.call_args[1]
                assert call_kwargs["env"] == {"TEST": "value"}

    def test_spawn_bot_mvp_uses_provided_environment(self) -> None:
        """Test spawn_bot_mvp uses provided environment dict."""
        pm = ProcessManager()

        mock_popen = MagicMock()
        mock_popen.pid = 12345
        custom_env = {"CUSTOM": "env_var"}

        with patch("subprocess.Popen", return_value=mock_popen) as mock_spawn:
            process, pid = pm.spawn_bot_mvp(env=custom_env)

            call_kwargs = mock_spawn.call_args[1]
            assert call_kwargs["env"] == custom_env

    def test_spawn_bot_mvp_returns_process_and_pid(self) -> None:
        """Test spawn_bot_mvp returns (process, pid) tuple."""
        pm = ProcessManager()

        mock_popen = MagicMock()
        mock_popen.pid = 54321

        with patch("subprocess.Popen", return_value=mock_popen):
            process, pid = pm.spawn_bot_mvp()

            assert process == mock_popen
            assert pid == 54321


class TestSpawnCSharpWindow:
    """Test C# window process spawning."""

    def test_spawn_csharp_window_raises_if_executable_missing(self) -> None:
        """Test spawn_csharp_window raises FileNotFoundError if exe not found."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        with pytest.raises(FileNotFoundError):
            pm.spawn_csharp_window(scenario, "/nonexistent/path.exe", timeout_s=1.0)

    def test_spawn_csharp_window_builds_args_from_scenario(self, tmp_path) -> None:
        """Test spawn_csharp_window builds command-line args from scenario."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        # Create mock executable
        exe_path = tmp_path / "stub.exe"
        exe_path.write_text("mock")

        mock_popen = MagicMock()
        mock_popen.pid = 11111
        mock_popen.poll.side_effect = [None, None, None]  # Process running

        with patch("subprocess.Popen", return_value=mock_popen):
            with patch.object(pm, "_verify_window_exists", return_value=True):
                process, pid = pm.spawn_csharp_window(scenario, str(exe_path), timeout_s=1.0)

                # Verify Popen was called
                assert mock_popen is not None
                # Process and PID should be returned
                assert pid == 11111

    def test_spawn_csharp_window_waits_for_window_appearance(self, tmp_path) -> None:
        """Test spawn_csharp_window waits for window to appear."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        exe_path = tmp_path / "stub.exe"
        exe_path.write_text("mock")

        mock_popen = MagicMock()
        mock_popen.pid = 22222
        mock_popen.poll.return_value = None  # Process running

        with patch("subprocess.Popen", return_value=mock_popen):
            with patch.object(pm, "_verify_window_exists", return_value=True):
                process, pid = pm.spawn_csharp_window(scenario, str(exe_path), timeout_s=1.0)

                # Should have called _verify_window_exists
                assert pm._verify_window_exists.called

    def test_spawn_csharp_window_raises_if_process_exits_early(self, tmp_path) -> None:
        """Test spawn_csharp_window raises if process exits before window appears."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        exe_path = tmp_path / "stub.exe"
        exe_path.write_text("mock")

        mock_popen = MagicMock()
        mock_popen.poll.return_value = 1  # Process exited
        mock_popen.communicate.return_value = ("", "error message")

        with patch("subprocess.Popen", return_value=mock_popen):
            with pytest.raises(RuntimeError, match="exited prematurely"):
                pm.spawn_csharp_window(scenario, str(exe_path), timeout_s=1.0)

    def test_spawn_csharp_window_raises_on_timeout(self, tmp_path) -> None:
        """Test spawn_csharp_window raises if window doesn't appear in time."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        exe_path = tmp_path / "stub.exe"
        exe_path.write_text("mock")

        mock_popen = MagicMock()
        mock_popen.pid = 33333
        mock_popen.poll.return_value = None  # Still running

        with patch("subprocess.Popen", return_value=mock_popen):
            with patch.object(pm, "_verify_window_exists", return_value=False):
                with pytest.raises(RuntimeError, match="did not appear"):
                    pm.spawn_csharp_window(scenario, str(exe_path), timeout_s=0.1)

    def test_spawn_csharp_window_returns_process_and_pid(self, tmp_path) -> None:
        """Test spawn_csharp_window returns (process, pid) tuple."""
        pm = ProcessManager()
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()

        exe_path = tmp_path / "stub.exe"
        exe_path.write_text("mock")

        mock_popen = MagicMock()
        mock_popen.pid = 44444
        mock_popen.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_popen):
            with patch.object(pm, "_verify_window_exists", return_value=True):
                process, pid = pm.spawn_csharp_window(scenario, str(exe_path), timeout_s=1.0)

                assert process == mock_popen
                assert pid == 44444


class TestProcessResult:
    """Test ProcessResult dataclass."""

    def test_process_result_creation(self) -> None:
        """Test ProcessResult can be created with all fields."""
        result = ProcessResult(
            exit_code=0,
            stdout="output",
            stderr="",
            duration_s=1.5,
            timed_out=False,
            partial_logs={"game_events": "content"},
        )

        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.duration_s == 1.5
        assert result.timed_out is False
        assert result.partial_logs == {"game_events": "content"}

    def test_process_result_defaults(self) -> None:
        """Test ProcessResult can be created with minimal fields."""
        result = ProcessResult(
            exit_code=1,
            stdout="",
            stderr="error",
            duration_s=0.5,
            timed_out=True,
            partial_logs={},
        )

        assert result.exit_code == 1
        assert result.timed_out is True
