# mvp/simulator/core.py
"""
GameStateManager: Core simulation engine for managing game state transitions,
click logging, and session metrics storage.

Provides thread-safe state machine with callbacks for monitoring game flow:
chat → alert_animation → treasure → scanning → chat_recovery
"""

from enum import Enum
from typing import Callable, List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from threading import Lock, RLock, Thread
from datetime import datetime
import json
from pathlib import Path
import time

from mvp.simulator.utils import setup_logger, timestamp_ms, format_timestamp_ms


logger = setup_logger(__name__)


class GameState(Enum):
    """Valid game states in the state machine."""
    CHAT = 'chat'
    CHAT_FOCUS = 'chat_focus'
    ALERT_ANIMATION = 'alert_animation'
    TREASURE = 'treasure'
    REWARD_DETAILS = 'reward_details'
    SCANNING = 'scanning'
    CHAT_UNAVAILABLE = 'chat_unavailable'
    CHAT_RECOVERY = 'chat_recovery'


@dataclass
class ClickEvent:
    """Single click event with timing, position, and result."""
    timestamp_ms: int
    position_x: float
    position_y: float
    hit: bool
    phase: str
    iteration: int
    variant: Optional[str] = None
    ocr_confidence: Optional[float] = None
    latency_ms: Optional[int] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class IterationMetrics:
    """Metrics collected during a single iteration."""
    iteration: int
    variant: Optional[str]
    phase_1_setup_ms: Optional[int] = None
    phase_2_alert_detection_ms: Optional[int] = None
    phase_3_click_latency_ms: Optional[int] = None
    phase_3_hit: Optional[bool] = None
    phase_4_cpu_spike_percent: Optional[int] = None
    phase_5_chat_recovery_ms: Optional[int] = None
    phase_5_ocr_confidence: Optional[float] = None
    phase_5_state_verified: Optional[bool] = None
    total_iteration_ms: Optional[int] = None
    cpu_avg: Optional[int] = None
    ram_mb: Optional[int] = None
    # Timer animation metrics (Task 3b)
    timer_prediction_ms: Optional[int] = None  # ms before/after ideal expiry
    timer_accuracy_percent: Optional[float] = None  # accuracy vs ideal window
    timer_is_early_click: Optional[bool] = None  # clicked before expiry
    timer_is_late_click: Optional[bool] = None  # clicked after expiry
    # State recovery metrics
    state_transitions_count: Optional[int] = None
    unexpected_state_changes: Optional[int] = None
    state_error_recovery_ms: Optional[int] = None
    clicks: List[ClickEvent] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['clicks'] = [c.to_dict() for c in self.clicks]
        return data

    @property
    def success(self) -> bool:
        """True if iteration completed without critical anomalies."""
        return self.phase_5_state_verified and not any(
            'critical' in a.lower() for a in self.anomalies
        )


class GameStateManager:
    """
    Thread-safe state machine for managing game simulation state.

    States: chat → alert_animation → treasure → scanning → chat_recovery
    Thread-safe transitions with callback system for state changes and phase completion.
    Tracks click events and aggregates session metrics.
    """

    # State transition graph with all 8 states
    STATE_GRAPH = {
        GameState.CHAT: [
            GameState.CHAT_FOCUS,
            GameState.ALERT_ANIMATION,
            GameState.CHAT_UNAVAILABLE,
        ],
        GameState.CHAT_FOCUS: [
            GameState.ALERT_ANIMATION,
            GameState.CHAT,
        ],
        GameState.ALERT_ANIMATION: [
            GameState.TREASURE,
            GameState.CHAT,
            GameState.CHAT_UNAVAILABLE,
        ],
        GameState.TREASURE: [
            GameState.REWARD_DETAILS,
            GameState.SCANNING,
            GameState.CHAT_RECOVERY,
            GameState.CHAT,
        ],
        GameState.REWARD_DETAILS: [
            GameState.SCANNING,
            GameState.CHAT_RECOVERY,
            GameState.CHAT,
        ],
        GameState.SCANNING: [
            GameState.CHAT_RECOVERY,
            GameState.CHAT,
        ],
        GameState.CHAT_UNAVAILABLE: [
            GameState.CHAT,
            GameState.CHAT_RECOVERY,
        ],
        GameState.CHAT_RECOVERY: [
            GameState.CHAT,
            GameState.CHAT_RECOVERY,
        ],
    }

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize GameStateManager.

        Args:
            session_id: Optional session identifier. If None, generated from timestamp.
        """
        self._state_lock = RLock()
        self._metrics_lock = RLock()
        self._callbacks_lock = Lock()

        # State management
        self._current_state = GameState.CHAT
        self._state_history: List[Tuple[GameState, int]] = [
            (GameState.CHAT, timestamp_ms())
        ]

        # Session data
        self.session_id = session_id or datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_start_ms = timestamp_ms()

        # Metrics storage
        self.iterations: Dict[int, IterationMetrics] = {}
        self.current_iteration: int = 0
        self.all_clicks: List[ClickEvent] = []

        # Callbacks
        self._on_state_change_callbacks: List[
            Callable[[GameState, GameState, int], None]
        ] = []
        self._on_phase_complete_callbacks: List[
            Callable[[str, Dict[str, Any]], None]
        ] = []
        self._on_click_callbacks: List[Callable[[ClickEvent], None]] = []

        logger.info(
            f'GameStateManager initialized | session_id={self.session_id}'
        )

    @property
    def current_state(self) -> GameState:
        """Get current game state (thread-safe read)."""
        with self._state_lock:
            return self._current_state

    @property
    def state_duration_ms(self) -> int:
        """Get time spent in current state (milliseconds)."""
        with self._state_lock:
            if not self._state_history:
                return 0
            _, entered_at = self._state_history[-1]
            return timestamp_ms() - entered_at

    def transition_to(self, new_state: GameState, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Attempt state transition (thread-safe).

        Valid transitions defined in STATE_GRAPH class constant:
        - chat → alert_animation
        - alert_animation → treasure
        - treasure → scanning, chat_recovery
        - scanning → chat_recovery
        - chat_recovery → chat
        - Any state → chat (reset)

        Args:
            new_state: Target state
            metadata: Optional metadata for transition (logged)

        Returns:
            True if transition successful, False if invalid
        """
        with self._state_lock:
            old_state = self._current_state

            # Check valid transition using class constant STATE_GRAPH
            if new_state not in self.STATE_GRAPH.get(old_state, []):
                logger.warning(
                    f'Invalid transition: {old_state.value} → {new_state.value}'
                )
                return False

            # Execute transition
            self._current_state = new_state
            now_ms = timestamp_ms()
            self._state_history.append((new_state, now_ms))

            logger.debug(
                f'State transition: {old_state.value} → {new_state.value} '
                f'(duration in old state: {self.state_duration_ms}ms)'
            )

            # Invoke callbacks (outside lock)
        self._invoke_state_change_callbacks(old_state, new_state, now_ms, metadata)
        return True

    def log_click(
        self,
        position_x: float,
        position_y: float,
        hit: bool,
        phase: str = 'unknown',
        ocr_confidence: Optional[float] = None,
        latency_ms: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> ClickEvent:
        """
        Log a click event (thread-safe).

        Args:
            position_x: Click X coordinate
            position_y: Click Y coordinate
            hit: Whether click registered a hit
            phase: Phase name (e.g., 'phase_3_click')
            ocr_confidence: Optional OCR confidence (0-1)
            latency_ms: Optional latency in milliseconds
            notes: Optional additional notes

        Returns:
            ClickEvent object created
        """
        click = ClickEvent(
            timestamp_ms=timestamp_ms(),
            position_x=position_x,
            position_y=position_y,
            hit=hit,
            phase=phase,
            iteration=self.current_iteration,
            variant=self.iterations.get(
                self.current_iteration, IterationMetrics(self.current_iteration, None)
            ).variant,
            ocr_confidence=ocr_confidence,
            latency_ms=latency_ms,
            notes=notes,
        )

        with self._metrics_lock:
            self.all_clicks.append(click)
            if self.current_iteration in self.iterations:
                self.iterations[self.current_iteration].clicks.append(click)

        logger.debug(
            f'Click logged | iteration={self.current_iteration} | '
            f'pos=({position_x:.1f}, {position_y:.1f}) | hit={hit} | '
            f'latency={latency_ms}ms'
        )

        # Invoke callbacks (outside lock)
        self._invoke_click_callbacks(click)
        return click

    def start_iteration(
        self,
        iteration: int,
        variant: Optional[str] = None,
    ) -> IterationMetrics:
        """
        Start a new iteration and initialize metrics storage.

        Args:
            iteration: Iteration number
            variant: Optional variant configuration identifier

        Returns:
            IterationMetrics object for this iteration
        """
        with self._metrics_lock:
            self.current_iteration = iteration
            metrics = IterationMetrics(iteration, variant)
            self.iterations[iteration] = metrics
            logger.info(f'Iteration started | #{iteration} | variant={variant}')
            return metrics

    def complete_iteration(self, total_time_ms: int, cpu_avg: int, ram_mb: int) -> IterationMetrics:
        """
        Complete current iteration and update metrics.

        Args:
            total_time_ms: Total time for this iteration
            cpu_avg: Average CPU usage (percent)
            ram_mb: RAM usage (megabytes)

        Returns:
            Updated IterationMetrics
        """
        with self._metrics_lock:
            if self.current_iteration not in self.iterations:
                logger.error(f'Iteration #{self.current_iteration} not started')
                return None

            metrics = self.iterations[self.current_iteration]
            metrics.total_iteration_ms = total_time_ms
            metrics.cpu_avg = cpu_avg
            metrics.ram_mb = ram_mb

            logger.info(
                f'Iteration completed | #{self.current_iteration} | '
                f'time={total_time_ms}ms | cpu_avg={cpu_avg}% | ram={ram_mb}MB | '
                f'success={metrics.success}'
            )
            return metrics

    def log_phase_metric(
        self,
        phase_name: str,
        metric_name: str,
        value: Any,
    ) -> None:
        """
        Log a metric for a specific phase of current iteration.

        Args:
            phase_name: Phase name (e.g., 'phase_2_alert_detection')
            metric_name: Metric name (e.g., 'detection_ms')
            value: Metric value

        Returns:
            None
        """
        with self._metrics_lock:
            if self.current_iteration not in self.iterations:
                logger.warning(f'No active iteration for phase metric: {phase_name}')
                return

            metrics = self.iterations[self.current_iteration]

            # Map phase_name + metric_name to IterationMetrics field
            if phase_name == 'setup' and metric_name == 'setup_ms':
                metrics.phase_1_setup_ms = value
            elif phase_name == 'alert' and metric_name == 'detection_ms':
                metrics.phase_2_alert_detection_ms = value
            elif phase_name == 'click' and metric_name == 'latency_ms':
                metrics.phase_3_click_latency_ms = value
            elif phase_name == 'click' and metric_name == 'hit':
                metrics.phase_3_hit = value
            elif phase_name == 'treasure' and metric_name == 'cpu_spike_percent':
                metrics.phase_4_cpu_spike_percent = value
            elif phase_name == 'chat_recovery' and metric_name == 'recovery_ms':
                metrics.phase_5_chat_recovery_ms = value
            elif phase_name == 'chat_recovery' and metric_name == 'ocr_confidence':
                metrics.phase_5_ocr_confidence = value
            elif phase_name == 'chat_recovery' and metric_name == 'state_verified':
                metrics.phase_5_state_verified = value

            logger.debug(
                f'Phase metric logged | phase={phase_name} | {metric_name}={value}'
            )

    def log_anomaly(self, iteration: int, reason: str, severity: str = 'warning') -> None:
        """
        Log an anomaly for a specific iteration.

        Args:
            iteration: Iteration number
            reason: Description of anomaly
            severity: 'warning' or 'critical'

        Returns:
            None
        """
        with self._metrics_lock:
            if iteration not in self.iterations:
                logger.warning(f'Iteration #{iteration} not found for anomaly log')
                return

            self.iterations[iteration].anomalies.append(
                f'[{severity.upper()}] {reason}'
            )
            logger.warning(
                f'Anomaly logged | iteration=#{iteration} | severity={severity} | {reason}'
            )

    def register_on_state_change(
        self,
        callback: Callable[[GameState, GameState, int], None],
    ) -> None:
        """
        Register callback for state change events.

        Callback signature: callback(old_state, new_state, timestamp_ms)

        Args:
            callback: Function to invoke on state change

        Returns:
            None
        """
        with self._callbacks_lock:
            self._on_state_change_callbacks.append(callback)

    def register_on_click(
        self,
        callback: Callable[[ClickEvent], None],
    ) -> None:
        """
        Register callback for click events.

        Callback signature: callback(click_event)

        Args:
            callback: Function to invoke on click

        Returns:
            None
        """
        with self._callbacks_lock:
            self._on_click_callbacks.append(callback)

    def register_on_phase_complete(
        self,
        callback: Callable[[str, Dict[str, Any]], None],
    ) -> None:
        """
        Register callback for phase completion.

        Callback signature: callback(phase_name, metrics_dict)

        Args:
            callback: Function to invoke on phase completion

        Returns:
            None
        """
        with self._callbacks_lock:
            self._on_phase_complete_callbacks.append(callback)

    def _invoke_state_change_callbacks(
        self,
        old_state: GameState,
        new_state: GameState,
        timestamp_ms_val: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Invoke all state change callbacks with timeout (Issue #7)."""
        with self._callbacks_lock:
            for callback in self._on_state_change_callbacks:
                try:
                    self._invoke_with_timeout(
                        callback,
                        args=(old_state, new_state, timestamp_ms_val),
                        timeout_ms=100,
                    )
                except Exception as e:
                    logger.error(f'Error in state change callback: {e}')

    def _invoke_click_callbacks(self, click: ClickEvent) -> None:
        """Invoke all click callbacks with timeout (Issue #7)."""
        with self._callbacks_lock:
            for callback in self._on_click_callbacks:
                try:
                    self._invoke_with_timeout(
                        callback,
                        args=(click,),
                        timeout_ms=100,
                    )
                except Exception as e:
                    logger.error(f'Error in click callback: {e}')

    def _invoke_phase_complete_callbacks(
        self,
        phase_name: str,
        metrics: Dict[str, Any],
    ) -> None:
        """Invoke all phase completion callbacks with timeout (Issue #7)."""
        with self._callbacks_lock:
            for callback in self._on_phase_complete_callbacks:
                try:
                    self._invoke_with_timeout(
                        callback,
                        args=(phase_name, metrics),
                        timeout_ms=100,
                    )
                except Exception as e:
                    logger.error(f'Error in phase complete callback: {e}')

    @staticmethod
    def _invoke_with_timeout(
        callback: Callable,
        args: Tuple = (),
        timeout_ms: int = 100,
    ) -> None:
        """
        Invoke callback with timeout to prevent hanging (Issue #7).

        If callback takes longer than timeout_ms, logs warning but continues.

        Args:
            callback: Callable to invoke
            args: Arguments tuple to pass to callback
            timeout_ms: Timeout in milliseconds (default: 100ms)
        """
        start_ms = time.time() * 1000
        try:
            callback(*args)
            elapsed_ms = (time.time() * 1000) - start_ms
            if elapsed_ms > timeout_ms:
                logger.warning(
                    f'Callback took {elapsed_ms:.1f}ms (threshold: {timeout_ms}ms) - '
                    f'consider optimizing: {callback.__name__}'
                )
        except Exception as e:
            logger.error(f'Callback failed: {e}')

    def get_session_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated session metrics (thread-safe).

        Returns:
            Dictionary with session-level statistics
        """
        with self._metrics_lock:
            total_iterations = len(self.iterations)
            successful_iterations = sum(
                1 for m in self.iterations.values() if m.success
            )

            accuracy_pct = (
                (successful_iterations / total_iterations * 100)
                if total_iterations > 0
                else 0
            )

            all_latencies = [
                c.latency_ms
                for c in self.all_clicks
                if c.latency_ms is not None
            ]
            avg_latency = (
                sum(all_latencies) / len(all_latencies)
                if all_latencies
                else None
            )

            all_ocr_confidences = [
                c.ocr_confidence
                for c in self.all_clicks
                if c.ocr_confidence is not None
            ]
            avg_ocr_confidence = (
                sum(all_ocr_confidences) / len(all_ocr_confidences)
                if all_ocr_confidences
                else None
            )

            return {
                'session_id': self.session_id,
                'session_start_ms': self.session_start_ms,
                'session_duration_ms': timestamp_ms() - self.session_start_ms,
                'total_iterations': total_iterations,
                'successful_iterations': successful_iterations,
                'accuracy_percent': accuracy_pct,
                'average_latency_ms': avg_latency,
                'average_ocr_confidence': avg_ocr_confidence,
                'total_clicks': len(self.all_clicks),
                'total_hits': sum(1 for c in self.all_clicks if c.hit),
            }

    def save_session_data(self, filepath: Path) -> None:
        """
        Save all session data to JSON file.

        Args:
            filepath: Path to save session data JSON

        Returns:
            None
        """
        with self._metrics_lock:
            data = {
                'session_id': self.session_id,
                'session_start_ms': self.session_start_ms,
                'session_metrics': self.get_session_metrics(),
                'iterations': {
                    k: v.to_dict() for k, v in self.iterations.items()
                },
            }

            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f'Session data saved to {filepath}')



