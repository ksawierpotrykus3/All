# mvp/simulator/bot_integration.py
"""
Bot Integration Layer for Extended Game Simulator Framework.

Handles communication between bot and simulator:
- Frame queue connection to BotRunner
- OCR confidence reading from bot logs/API
- Click event logging and hooking
- CPU/RAM monitoring with psutil
- Thread-safe metrics collection
- Worker pool for async click queueing
"""

import threading
import queue
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from collections import deque
import psutil

from mvp.simulator.core import GameStateManager, ClickEvent
from mvp.simulator.worker_pool import WorkerPool


logger = logging.getLogger(__name__)


class BotIntegrationLayer:
    """
    Integration layer between MVP bot and game simulator.

    Manages:
    - Frame streaming from bot (queue-based)
    - Click event logging and callbacks
    - OCR confidence metrics
    - CPU/RAM monitoring
    - Thread-safe communication
    """

    def __init__(
        self,
        game_state_manager: GameStateManager,
        config: Optional[Dict[str, Any]] = None,
        use_worker_pool: bool = True
    ):
        """
        Initialize BotIntegrationLayer.

        Args:
            game_state_manager: GameStateManager instance for state management
            config: Optional configuration dict with keys:
                - bot_process_name: Process name to monitor (default: 'game.exe')
                - frame_queue_size: Max frame queue size (default: 100)
                - monitoring_interval_ms: Monitoring thread interval (default: 100)
                - cpu_threshold_percent: CPU warning threshold (default: 80)
                - worker_pool_enabled: Enable async click queueing (default: True)
                - worker_pool_workers: Number of workers (default: 4)
                - worker_pool_queue_size: Worker pool queue size (default: 100)
            use_worker_pool: Whether to enable worker pool for async clicks
        """
        self.game_state_manager = game_state_manager
        self._lock = threading.RLock()

        # Configuration
        config = config or {}
        self.bot_process_name = config.get('bot_process_name', 'game.exe')
        self.frame_queue_max_size = config.get('frame_queue_size', 100)
        self.monitoring_interval_ms = config.get('monitoring_interval_ms', 100)
        self.cpu_threshold_percent = config.get('cpu_threshold_percent', 80)
        self.use_worker_pool = use_worker_pool and config.get('worker_pool_enabled', True)

        # Connection state
        self.is_connected = False
        self.is_monitoring = False

        # Frame queue (thread-safe)
        self.frame_queue: queue.Queue = queue.Queue(maxsize=self.frame_queue_max_size)
        self.click_queue: queue.Queue = queue.Queue()

        # Worker pool for async click queueing
        if self.use_worker_pool:
            worker_pool_workers = config.get('worker_pool_workers', 4)
            worker_pool_queue = config.get('worker_pool_queue_size', 100)
            self.worker_pool = WorkerPool(num_workers=worker_pool_workers, queue_size=worker_pool_queue)
        else:
            self.worker_pool = None

        # Metrics
        self.ocr_confidence = 0.0
        self.cpu_percent = 0
        self.ram_mb = 0

        # Last bot click decision (coordinates + confidence) captured from
        # the actual bot. Used by SimulationEngine to validate hits against
        # the true decision target instead of hardcoded mock coordinates.
        self._last_click_target: Optional[tuple[int, int, float]] = None

        # History tracking (for trends)
        self._ocr_history: deque = deque(maxlen=1000)
        self._resource_history: deque = deque(maxlen=1000)

        # Monitoring thread
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_stop_event = threading.Event()

        # Bot process reference
        self._bot_process: Optional[psutil.Process] = None

        # State change callbacks
        self._on_state_change_callbacks: List[Callable] = []

        # Register for state changes from GameStateManager
        self.game_state_manager.register_on_state_change(self._on_gsm_state_change)

        logger.info(
            f"BotIntegrationLayer initialized (queue_size={self.frame_queue_max_size}, "
            f"worker_pool={'enabled' if self.use_worker_pool else 'disabled'})"
        )

    # =========================================================================
    # Frame Queue Connection
    # =========================================================================

    def connect_to_bot(self) -> bool:
        """
        Establish connection to bot.

        Returns:
            True if connection successful, False otherwise
        """
        with self._lock:
            try:
                # Try to find and attach to bot process
                try:
                    # Look for bot process by name
                    for proc in psutil.process_iter(['pid', 'name']):
                        if self.bot_process_name.lower() in proc.info['name'].lower():
                            self._bot_process = psutil.Process(proc.info['pid'])
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # If specific process not found, create dummy for monitoring
                    self._bot_process = None

                self.is_connected = True
                logger.info(f"Connected to bot (process: {self.bot_process_name})")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to bot: {e}")
                return False

    def disconnect_from_bot(self) -> bool:
        """
        Disconnect from bot and cleanup.

        Returns:
            True if disconnection successful
        """
        with self._lock:
            try:
                # Stop monitoring
                if self.is_monitoring:
                    self.stop_monitoring()

                # Shutdown worker pool
                if self.worker_pool is not None:
                    self.worker_pool.shutdown(wait=True)

                # Clear queues
                while not self.frame_queue.empty():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        break

                while not self.click_queue.empty():
                    try:
                        self.click_queue.get_nowait()
                    except queue.Empty:
                        break

                self._bot_process = None
                self.is_connected = False
                logger.info("Disconnected from bot")
                return True
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
                return False

    def push_frame(self, frame_data: Dict[str, Any]) -> bool:
        """
        Push frame from bot to simulator queue.

        Args:
            frame_data: Frame data dict with timestamp, image, etc.

        Returns:
            True if frame queued, False if not connected or queue full
        """
        if not self.is_connected:
            return False

        try:
            self.frame_queue.put_nowait(frame_data)
            return True
        except queue.Full:
            logger.warning("Frame queue full, dropping frame")
            return False

    def pop_frame(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Pop frame from simulator queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Frame data dict or None if timeout
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # =========================================================================
    # OCR Confidence Tracking
    # =========================================================================

    def get_ocr_confidence(self) -> float:
        """
        Get current OCR confidence value.

        Returns:
            OCR confidence (0.0 to 1.0)
        """
        with self._lock:
            return self.ocr_confidence

    def get_last_click_target(self) -> Optional[tuple[int, int, float]]:
        """
        Return the last bot click decision target as (x, y, confidence).

        Returns:
            Tuple (x, y, confidence) or None if the bot has not clicked yet.
        """
        with self._lock:
            return self._last_click_target

    def update_ocr_confidence(self, confidence: float) -> None:
        """
        Update OCR confidence value.

        Args:
            confidence: OCR confidence value (0.0 to 1.0)
        """
        with self._lock:
            # Clamp to valid range
            self.ocr_confidence = max(0.0, min(1.0, confidence))
            self._ocr_history.append({
                'timestamp': time.time(),
                'confidence': self.ocr_confidence
            })
            logger.debug(f"OCR confidence updated: {self.ocr_confidence:.2%}")

    def get_ocr_confidence_history(self) -> List[float]:
        """
        Get OCR confidence history.

        Returns:
            List of confidence values
        """
        with self._lock:
            return [h['confidence'] for h in self._ocr_history]

    def read_ocr_confidence_from_api(self) -> Optional[float]:
        """
        Read OCR confidence from bot API/logs.

        Returns:
            OCR confidence or None if unavailable
        """
        try:
            data = self._fetch_from_bot_api()
            if data and 'ocr_confidence' in data:
                confidence = data['ocr_confidence']
                self.update_ocr_confidence(confidence)
                return confidence
            return None
        except Exception as e:
            logger.error(f"Failed to read OCR confidence from API: {e}")
            return None

    def _fetch_from_bot_api(self) -> Optional[Dict[str, Any]]:
        """
        Fetch data from bot API (stub for now).

        Returns:
            API response dict or None
        """
        # Placeholder for actual bot API integration
        return None

    # =========================================================================
    # Click Event Integration
    # =========================================================================

    def send_async_click(self, x: int, y: int, click_data: Dict[str, Any]) -> Optional[Any]:
        """
        Submit click to worker pool for async processing.

        Args:
            x: Click X position
            y: Click Y position
            click_data: Additional click data (hit, phase, latency_ms, ocr_confidence)

        Returns:
            Future object or None if pool not enabled
        """
        if not self.use_worker_pool or self.worker_pool is None:
            return None

        try:
            # Prepare complete click data
            complete_click_data = {
                'x': x,
                'y': y,
                **click_data,
                'timestamp': time.time()
            }

            # Submit to worker pool
            future = self.worker_pool.submit_click(complete_click_data)
            logger.debug(f"Async click submitted to worker pool: ({x}, {y})")
            return future

        except Exception as e:
            logger.error(f"Failed to submit async click: {e}")
            return None

    def log_bot_click(
        self,
        position_x: float,
        position_y: float,
        hit: bool,
        phase: str = 'phase_3_click',
        latency_ms: int = 0,
        ocr_confidence: Optional[float] = None
    ) -> Optional[ClickEvent]:
        """
        Log click event from bot.

        Args:
            position_x: Click X position
            position_y: Click Y position
            hit: Whether click hit target
            phase: Phase name
            latency_ms: Click latency in milliseconds
            ocr_confidence: OCR confidence at click time

        Returns:
            ClickEvent or None
        """
        try:
            with self._lock:
                # Use provided confidence or current value
                if ocr_confidence is None:
                    ocr_confidence = self.ocr_confidence

                # Capture the bot's decision target so the engine can validate
                # hits against the actual coordinates the bot chose.
                self._last_click_target = (int(position_x), int(position_y), float(ocr_confidence))

                # Log click through GameStateManager
                click = self.game_state_manager.log_click(
                    position_x=position_x,
                    position_y=position_y,
                    hit=hit,
                    phase=phase,
                    ocr_confidence=ocr_confidence,
                    latency_ms=latency_ms
                )

                logger.debug(
                    f"Bot click logged: ({position_x:.1f}, {position_y:.1f}) "
                    f"hit={hit} latency={latency_ms}ms confidence={ocr_confidence:.2%}"
                )
                return click
        except Exception as e:
            logger.error(f"Failed to log bot click: {e}")
            return None

    def register_on_state_change(self, callback: Callable) -> None:
        """
        Register callback for state changes.

        Args:
            callback: Callback function(old_state, new_state, timestamp)
        """
        with self._lock:
            self._on_state_change_callbacks.append(callback)

    def _on_gsm_state_change(self, old_state, new_state, timestamp):
        """
        Internal handler for GameStateManager state changes.
        Invokes registered callbacks.
        """
        with self._lock:
            for callback in self._on_state_change_callbacks:
                try:
                    callback(old_state, new_state, timestamp)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")

    # =========================================================================
    # CPU/RAM Monitoring
    # =========================================================================

    def get_cpu_percent(self) -> float:
        """
        Get bot process CPU usage percentage.

        Returns:
            CPU percent (0-100)
        """
        try:
            if self._bot_process:
                return self._bot_process.cpu_percent(interval=0.1)
            return 0.0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def get_memory_mb(self) -> float:
        """
        Get bot process memory usage in MB.

        Returns:
            Memory in MB
        """
        try:
            if self._bot_process:
                return self._bot_process.memory_info().rss / (1024 * 1024)
            return 0.0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def get_system_cpu_percent(self) -> float:
        """
        Get system-wide CPU usage percentage.

        Returns:
            CPU percent (0-100)
        """
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception:
            return 0.0

    def get_system_memory_percent(self) -> float:
        """
        Get system-wide memory usage percentage.

        Returns:
            Memory percent (0-100)
        """
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0

    def update_resource_metrics(
        self,
        cpu_percent: Optional[float] = None,
        ram_mb: Optional[float] = None
    ) -> None:
        """
        Update CPU/RAM metrics.

        Args:
            cpu_percent: CPU usage percentage
            ram_mb: Memory usage in MB
        """
        with self._lock:
            if cpu_percent is not None:
                self.cpu_percent = cpu_percent
            if ram_mb is not None:
                self.ram_mb = ram_mb

            self._resource_history.append({
                'timestamp': time.time(),
                'cpu_percent': self.cpu_percent,
                'ram_mb': self.ram_mb
            })

    def get_resource_metrics(self) -> Dict[str, Any]:
        """
        Get current CPU/RAM metrics.

        Returns:
            Dict with cpu_percent and ram_mb
        """
        with self._lock:
            return {
                'cpu_percent': self.cpu_percent,
                'ram_mb': self.ram_mb,
                'timestamp': time.time()
            }

    def get_resource_metrics_history(self) -> List[Dict[str, Any]]:
        """
        Get resource metrics history.

        Returns:
            List of metric dicts
        """
        with self._lock:
            return list(self._resource_history)

    def start_monitoring(self) -> bool:
        """
        Start CPU/RAM monitoring thread.

        Returns:
            True if started successfully
        """
        if self.is_monitoring:
            return False

        try:
            self._monitoring_stop_event.clear()
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_worker,
                daemon=True
            )
            self._monitoring_thread.start()
            self.is_monitoring = True
            logger.info("Started resource monitoring thread")
            return True
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            return False

    def stop_monitoring(self) -> bool:
        """
        Stop CPU/RAM monitoring thread.

        Returns:
            True if stopped successfully
        """
        if not self.is_monitoring:
            return False

        try:
            self._monitoring_stop_event.set()
            if self._monitoring_thread:
                self._monitoring_thread.join(timeout=2.0)
            self.is_monitoring = False
            logger.info("Stopped resource monitoring thread")
            return True
        except Exception as e:
            logger.error(f"Failed to stop monitoring: {e}")
            return False

    def _monitoring_worker(self) -> None:
        """
        Background worker for CPU/RAM monitoring.
        """
        while not self._monitoring_stop_event.is_set():
            try:
                cpu = self.get_cpu_percent()
                ram = self.get_memory_mb()
                self.update_resource_metrics(cpu_percent=cpu, ram_mb=ram)

                # Log warning if CPU threshold exceeded
                if cpu > self.cpu_threshold_percent:
                    logger.warning(f"CPU usage high: {cpu:.1f}%")

                interval_s = self.monitoring_interval_ms / 1000.0
                self._monitoring_stop_event.wait(interval_s)
            except Exception as e:
                logger.error(f"Monitoring worker error: {e}")
                time.sleep(0.1)

    # =========================================================================
    # Context Manager Support
    # =========================================================================

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.disconnect_from_bot()
        return False
