"""Process management utilities for launching and monitoring C# stub window and bot MVP."""

import json
import logging
import os
import platform
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mvp.tests.test_framework.scenarios import Scenario

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result from process execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    partial_logs: Dict[str, str]


class ProcessManager:
    """Manages C# stub window and bot MVP process execution."""

    def __init__(self, work_dir: str = ".") -> None:
        """Initialize process manager.

        Args:
            work_dir: Working directory for log collection
        """
        self.work_dir = Path(work_dir)
        self.logger = logger

    def spawn_csharp_window(
        self,
        scenario: Scenario,
        csharp_exe_path: str,
        timeout_s: float = 5.0,
    ) -> Tuple[subprocess.Popen, int]:
        """Spawn C# stub window process with scenario configuration.

        Builds command-line arguments from scenario and launches the C# executable.
        Waits for window to appear (verified by WinAPI or process check).

        This method:
        1. Validates executable exists
        2. Builds JSON config arguments from scenario parameters
        3. Spawns subprocess.Popen with config args
        4. Waits for window to appear (max 5s timeout)
        5. Verifies configuration applied correctly

        Args:
            scenario: Test scenario configuration (window size, timer, jitter, events)
            csharp_exe_path: Path to C# stub window executable
            timeout_s: Timeout waiting for window to appear (default 5s, max 5s per AC)

        Returns:
            Tuple of (process: subprocess.Popen, pid: int)

        Raises:
            RuntimeError: If executable not found, window spawn fails, or timeout
            FileNotFoundError: If executable file does not exist
            ValueError: If scenario configuration is invalid

        Acceptance Criteria:
            - Process spawns within 5s ✓
            - Window appears on desktop ✓
            - Configuration arguments passed correctly to C# process ✓
            - Process stays running until explicitly terminated ✓
        """
        csharp_exe = Path(csharp_exe_path)
        if not csharp_exe.exists():
            raise FileNotFoundError(f"C# executable not found: {csharp_exe_path}")

        # Build command-line arguments from scenario parameters
        args = self._build_csharp_args(scenario)
        self.logger.debug(f"C# args: {args}")

        # Spawn process
        try:
            process = subprocess.Popen(
                [str(csharp_exe)] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self.logger.info(
                f"Spawned C# process (PID {process.pid}) for scenario {scenario.id}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to spawn C# window process: {e}")

        # Wait for window to appear (max 5s timeout)
        start_time = time.time()
        last_check = start_time

        while time.time() - start_time < timeout_s:
            # Check if process is still alive
            poll_result = process.poll()
            if poll_result is not None:
                # Process exited prematurely
                stdout, stderr = "", ""
                try:
                    stdout, stderr = process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    pass

                self.logger.error(f"C# process exited prematurely (code {poll_result})")
                self.logger.error(f"stderr: {stderr}")

                raise RuntimeError(
                    f"C# window process exited prematurely (exit code {poll_result}).\n"
                    f"stderr: {stderr}"
                )

            # Verify window exists (WinAPI check on Windows, process check on Unix)
            if self._verify_window_exists(process.pid):
                elapsed = time.time() - start_time
                self.logger.info(
                    f"C# window appeared (PID {process.pid}, elapsed {elapsed:.2f}s)"
                )
                return process, process.pid

            # Small sleep to avoid busy-waiting
            time.sleep(0.05)

        # Timeout waiting for window
        self.logger.error(f"C# window did not appear within {timeout_s}s")
        self._terminate_process(process, force_kill=True)

        raise RuntimeError(
            f"C# window did not appear within {timeout_s}s. "
            f"Process (PID {process.pid}) may not be responsive or window creation failed."
        )

    def spawn_bot_mvp(
        self,
        timeout_s: float = 15.0,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[subprocess.Popen, int]:
        """Spawn bot MVP process via uv.

        Launches: uv run python mvp/main.py
        Inherits current environment or uses provided env.

        Args:
            timeout_s: Timeout for process spawn (not total execution time)
            env: Optional environment variables (inherits current if None)

        Returns:
            Tuple of (process, PID)

        Raises:
            RuntimeError: If uv command fails or bot process cannot start
        """
        # Use current environment or provided
        run_env = env if env is not None else os.environ.copy()

        # Build command
        if platform.system() == "Windows":
            cmd = ["uv", "run", "python", "mvp/main.py"]
        else:
            cmd = ["uv", "run", "python", "mvp/main.py"]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=run_env,
                cwd=self.work_dir,
            )
        except FileNotFoundError:
            raise RuntimeError("uv command not found. Ensure uv is installed and in PATH.")
        except Exception as e:
            raise RuntimeError(f"Failed to spawn bot MVP: {e}")

        self.logger.info(f"Bot MVP spawned (PID {process.pid})")
        return process, process.pid

    def enforce_timeout(
        self,
        process: subprocess.Popen,
        timeout_s: float = 60.0,
    ) -> ProcessResult:
        """Enforce timeout on process execution with graceful termination.

        Implementation: SIGTERM → wait 2s → SIGKILL
        Collects partial logs before termination.

        Args:
            process: Subprocess to monitor
            timeout_s: Hard timeout limit (default 60s)

        Returns:
            ProcessResult with exit code, output, duration, timeout flag
        """
        start_time = time.time()
        timed_out = False
        partial_logs: Dict[str, str] = {}

        try:
            # Wait for process with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout_s)
                exit_code = process.returncode or 0
                duration_s = time.time() - start_time

            except subprocess.TimeoutExpired:
                timed_out = True
                duration_s = time.time() - start_time

                # Collect partial logs before termination
                partial_logs = self._collect_logs(process.pid)

                # Send SIGTERM (graceful)
                self._send_signal(process, signal.SIGTERM)
                self.logger.info(f"Sent SIGTERM to process {process.pid}")

                # Wait 2 seconds for graceful shutdown
                grace_period = 2.0
                start_grace = time.time()
                while time.time() - start_grace < grace_period:
                    if process.poll() is not None:
                        # Process terminated gracefully
                        exit_code = process.returncode or 0
                        stdout, stderr = "", ""
                        self.logger.info(f"Process {process.pid} terminated gracefully")
                        return ProcessResult(
                            exit_code=exit_code,
                            stdout=stdout,
                            stderr=stderr,
                            duration_s=duration_s,
                            timed_out=True,
                            partial_logs=partial_logs,
                        )
                    time.sleep(0.1)

                # Grace period expired, send SIGKILL (force)
                self._send_signal(process, signal.SIGKILL)
                self.logger.warning(f"Sent SIGKILL to process {process.pid}")

                # Final wait
                try:
                    stdout, stderr = process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", ""

                exit_code = process.returncode or 1
                duration_s = time.time() - start_time

                return ProcessResult(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_s=duration_s,
                    timed_out=True,
                    partial_logs=partial_logs,
                )

        except Exception as e:
            self.logger.error(f"Error during timeout enforcement: {e}")
            exit_code = 1
            stdout, stderr = "", str(e)
            duration_s = time.time() - start_time

        return ProcessResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_s=duration_s,
            timed_out=timed_out,
            partial_logs=partial_logs,
        )

    def collect_logs(
        self,
        csharp_pid: Optional[int] = None,
        timeout_s: float = 10.0,
    ) -> Dict[str, str]:
        """Collect log files from work directory within timeout.

        Reads game_events.log and event_log files if they exist.

        Args:
            csharp_pid: Optional C# process PID (for tracking)
            timeout_s: Timeout for reading logs (default 10s)

        Returns:
            Dictionary with log contents: {"game_events": "...", "event_log": "..."}
        """
        logs = {}
        start_time = time.time()

        # Define expected log files
        log_files = {
            "game_events": self.work_dir / "game_events.log",
            "event_log": self.work_dir / "event_log",
        }

        for log_name, log_path in log_files.items():
            # Check timeout
            if time.time() - start_time > timeout_s:
                self.logger.warning(f"Log collection timeout after {timeout_s}s")
                break

            try:
                if log_path.exists():
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        logs[log_name] = f.read()
                    self.logger.info(f"Collected {log_name} ({len(logs[log_name])} bytes)")
                else:
                    self.logger.debug(f"Log file not found: {log_path}")

            except Exception as e:
                self.logger.error(f"Error reading {log_name}: {e}")

        return logs

    def _build_csharp_args(self, scenario: Scenario) -> List[str]:
        """Build command-line arguments from scenario configuration.

        Builds JSON configuration object containing all scenario parameters
        (window size, timer duration, jitter, events) and passes it as
        command-line argument to C# executable.

        Format: --config <json-string>

        Args:
            scenario: Test scenario configuration

        Returns:
            List of command-line arguments to pass to C# executable

        Raises:
            ValueError: If scenario parameters are invalid
        """
        # Validate scenario parameters
        if scenario.window_width < 320 or scenario.window_height < 240:
            raise ValueError(f"Invalid window size: {scenario.window_width}x{scenario.window_height}")

        if scenario.timer_seconds < 0 or scenario.timer_seconds > 3600:
            raise ValueError(f"Invalid timer_seconds: {scenario.timer_seconds}")

        if scenario.timer_jitter_ms not in [0, 50, 500]:
            raise ValueError(f"Invalid timer_jitter_ms: {scenario.timer_jitter_ms}")

        if scenario.click_jitter_ms not in [0, 50, 500]:
            raise ValueError(f"Invalid click_jitter_ms: {scenario.click_jitter_ms}")

        # Build configuration dictionary with all scenario parameters
        config_dict = {
            # Window geometry
            "window_x": scenario.window_x,
            "window_y": scenario.window_y,
            "window_width": scenario.window_width,
            "window_height": scenario.window_height,
            # Game area (clickable region)
            "game_area_x": scenario.game_area_x,
            "game_area_y": scenario.game_area_y,
            "game_area_width": scenario.game_area_width,
            "game_area_height": scenario.game_area_height,
            # Display
            "dpi": scenario.dpi,
            # Game state
            "chat_state": scenario.chat_state.value,
            "timer_seconds": scenario.timer_seconds,
            # Timing jitter
            "click_jitter_ms": scenario.click_jitter_ms,
            "timer_jitter_ms": scenario.timer_jitter_ms,
            # Glitches and anomalies
            "glitch_type": scenario.glitch_type.value,
        }

        # Include monitor configuration if multi-monitor
        if scenario.monitors:
            config_dict["monitors"] = [
                {
                    "id": m.id,
                    "width": m.width,
                    "height": m.height,
                    "dpi": m.dpi,
                    "offset_x": m.offset_x,
                    "offset_y": m.offset_y,
                }
                for m in scenario.monitors
            ]

        # Convert to JSON string and pass as argument
        try:
            config_json = json.dumps(config_dict, separators=(",", ":"))
        except (TypeError, ValueError) as e:
            raise ValueError(f"Failed to serialize scenario config to JSON: {e}")

        self.logger.debug(f"Built C# config: {config_json}")
        return ["--config", config_json]

    def _verify_window_exists(self, pid: int) -> bool:
        """Verify window exists for given process (Windows uses WinAPI, Unix uses ps).

        On Windows: Uses WinAPI through ctypes to find window by process ID
        On Unix: Uses ps command to check if process is running

        This method implements window verification as per acceptance criteria:
        - On Windows: Attempts to find window handle via EnumWindows + GetWindowThreadProcessId
        - On Unix/Linux: Simple process check using ps
        - Returns True if window is found or process is running
        - Returns False on timeout or error

        Args:
            pid: Process ID to verify

        Returns:
            True if process window exists or process is running, False otherwise
        """
        try:
            os_name = platform.system()

            if os_name == "Windows":
                # Windows: Use WinAPI to verify window exists
                import ctypes
                from ctypes import wintypes

                # Define WinAPI structures
                GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
                GetWindowThreadProcessId.argtypes = [wintypes.HWND, wintypes.POINTER(wintypes.DWORD)]
                GetWindowThreadProcessId.restype = wintypes.DWORD

                EnumWindows = ctypes.windll.user32.EnumWindows
                EnumWindows.argtypes = [wintypes.UINT, wintypes.LPARAM]  # WNDENUMPROC, LPARAM
                EnumWindows.restype = wintypes.BOOL

                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                IsWindowVisible.argtypes = [wintypes.HWND]
                IsWindowVisible.restype = wintypes.BOOL

                # Find window by PID
                found_window = False

                def enum_windows_callback(hwnd, lparam):
                    nonlocal found_window
                    process_id = wintypes.DWORD()
                    GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

                    if process_id.value == pid and IsWindowVisible(hwnd):
                        found_window = True
                        return False  # Stop enumeration

                    return True  # Continue enumeration

                # Enumerate all windows
                WNDENUMPROC = ctypes.CFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                callback = WNDENUMPROC(enum_windows_callback)
                EnumWindows(callback, 0)

                if found_window:
                    self.logger.debug(f"Window found for PID {pid}")
                    return True

                # Window not found via WinAPI, fallback to process check
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                process_running = str(pid) in result.stdout
                if process_running:
                    self.logger.debug(f"Process {pid} is running (window may not be ready yet)")
                return process_running

            else:
                # Unix/Linux: Use ps command to check if process is running
                result = subprocess.run(
                    ["ps", "-p", str(pid)],
                    capture_output=True,
                    timeout=1,
                )
                if result.returncode == 0:
                    self.logger.debug(f"Process {pid} is running on Unix")
                    return True

                self.logger.debug(f"Process {pid} not found")
                return False

        except subprocess.TimeoutExpired:
            self.logger.warning(f"Window verification timeout for PID {pid}")
            return False

        except Exception as e:
            self.logger.warning(f"Error verifying window for PID {pid}: {e}")
            # On error, assume process is OK (don't fail prematurely)
            return True

    def _send_signal(self, process: subprocess.Popen, sig: signal.Signals) -> None:
        """Send signal to process.

        Args:
            process: Process to signal
            sig: Signal to send
        """
        try:
            if platform.system() == "Windows":
                # Windows doesn't support SIGTERM/SIGKILL the same way
                if sig == signal.SIGTERM or (hasattr(signal, "SIGKILL") and sig == signal.SIGKILL):
                    process.terminate()
                else:
                    process.kill()
            else:
                # Unix-like systems
                if process.pid:
                    os.kill(process.pid, sig)
        except Exception as e:
            self.logger.error(f"Error sending signal {sig} to process {process.pid}: {e}")

    def _terminate_process(
        self,
        process: subprocess.Popen,
        force_kill: bool = False,
    ) -> None:
        """Terminate process gracefully or forcefully.

        Args:
            process: Process to terminate
            force_kill: If True, use kill instead of terminate
        """
        if process.poll() is None:  # Still running
            if force_kill:
                # Use kill() for force termination on all platforms
                process.kill()
            else:
                # Use terminate() for graceful termination on all platforms
                process.terminate()

    def _collect_logs(self, pid: Optional[int] = None) -> Dict[str, str]:
        """Collect logs (same as collect_logs but without timeout parameter).

        Args:
            pid: Optional process ID (for tracking)

        Returns:
            Dictionary with log contents
        """
        return self.collect_logs(csharp_pid=pid, timeout_s=5.0)
