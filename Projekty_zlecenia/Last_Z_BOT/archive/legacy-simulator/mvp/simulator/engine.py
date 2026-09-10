# mvp/simulator/engine.py
"""
SimulationEngine: Facade combining all 4 core components.

Coordinates:
- GameStateManager: State machine (chat → alert → treasure → scanning)
- MetricsCollector: Per-iteration and aggregated metrics collection
- VariantExecutor: Test variant configuration and application
- BotIntegrationLayer: Communication with MVP bot, OCR, click logging

Provides unified API for:
- Initializing and running complete simulation iterations
- Applying variants and managing state transitions
- Collecting and aggregating metrics across full session
- Exporting results and session data
"""

from typing import Dict, Any, Optional, List, Tuple
from threading import Lock, RLock, Thread
import logging
import time
import random
from pathlib import Path
from datetime import datetime
import json
from queue import Queue

from mvp.simulator.core import GameStateManager, GameState, ClickEvent
from mvp.simulator.metrics import MetricsCollector
from mvp.simulator.variants import VariantExecutor
from mvp.simulator.bot_integration import BotIntegrationLayer
from mvp.simulator.config import MOCK_PHASE_PARAMS
from mvp.simulator.utils import setup_logger, timestamp_ms


logger = setup_logger(__name__)


class SimulationEngine:
    """
    Main facade for Extended Game Simulator Framework.

    Orchestrates all 4 components:
    1. GameStateManager: State transitions (chat → alert → treasure → scanning)
    2. MetricsCollector: Metrics for each iteration phase
    3. VariantExecutor: Apply test variants
    4. BotIntegrationLayer: Bot communication and click logging

    Usage:
    ```python
    engine = SimulationEngine(session_id="test_session_1")
    engine.apply_variant_preset("default")
    engine.initialize()

    for i in range(10):
        engine.run_iteration(i)

    results = engine.get_aggregated_metrics()
    engine.export_session(output_dir="results/")
    ```

    Iteration Loop (6 phases):
    1. Setup: Apply variant, reset state
    2. Alert: Show alert animation, wait for detection
    3. Click: Log bot click, measure latency
    4. Treasure: Simulate treasure opening, measure CPU
    5. Chat Recovery: Verify bot returned to chat
    6. Metrics: Aggregate and store metrics for iteration
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize SimulationEngine.

        Args:
            session_id: Optional session identifier. Generated from timestamp if None.
            config: Optional configuration dict with keys:
                - skip_bot_integration: Skip BotIntegrationLayer (default: False)
                - bot_config: Dict passed to BotIntegrationLayer
                - enable_logging: Enable detailed phase logging (default: True)
                - phase_timeout_ms: Timeout for phase completion (default: 10000ms)
        """
        self._lock = RLock()

        # Session identity
        self.session_id = (
            session_id or datetime.now().strftime('%Y%m%d_%H%M%S')
        )
        self.session_start_ms = timestamp_ms()

        # Configuration
        config = config or {}
        self.skip_bot_integration = config.get('skip_bot_integration', False)
        self.enable_logging = config.get('enable_logging', True)
        self.phase_timeout_ms = config.get('phase_timeout_ms', 10000)

        # Initialize 4 core components
        self.game_state_manager = GameStateManager(session_id=self.session_id)
        self.metrics_collector = MetricsCollector(session_id=self.session_id)
        self.variant_executor = VariantExecutor(session_id=self.session_id)

        if not self.skip_bot_integration:
            self.bot_integration = BotIntegrationLayer(
                game_state_manager=self.game_state_manager,
                config=config.get('bot_config', {})
            )
        else:
            self.bot_integration = None

        # State
        self.is_initialized = False
        self.is_running = False
        self.current_iteration = -1

        # UI Threading - thread-safe queues for background updates
        # Bounded queues (maxsize=100) with drop-oldest-on-full policy
        self.metrics_queue = Queue(maxsize=100)  # Metrics updates to UI
        self.state_queue = Queue(maxsize=100)    # State changes to UI
        self.event_queue = Queue(maxsize=100)    # Timeline events to UI

        # UI thread management
        self._ui_thread = None
        self._ui_thread_running = False

        logger.info(
            f'SimulationEngine initialized | session_id={self.session_id} '
            f'| skip_bot={self.skip_bot_integration}'
        )

    # =========================================================================
    # Initialization
    # =========================================================================

    def initialize(self) -> bool:
        """
        Initialize all components and connect to bot (if enabled).

        Returns:
            True if initialization successful, False otherwise
        """
        with self._lock:
            try:
                if self.is_initialized:
                    logger.warning('SimulationEngine already initialized')
                    return True

                # Connect bot integration (if enabled)
                if self.bot_integration:
                    if not self.bot_integration.connect_to_bot():
                        logger.warning('Failed to connect bot, continuing without bot')
                        # Non-fatal; continue without bot

                self.is_initialized = True
                logger.info('SimulationEngine initialized successfully')
                return True
            except Exception as e:
                logger.error(f'SimulationEngine initialization failed: {e}')
                # Explicit cleanup on error: disconnect bot and join monitoring thread
                try:
                    if self.bot_integration:
                        self.bot_integration.disconnect_from_bot()
                except Exception as cleanup_err:
                    logger.error(f'Failed to cleanup bot on init error: {cleanup_err}')
                return False

    def shutdown(self) -> bool:
        """
        Shutdown all components and disconnect from bot.

        Returns:
            True if shutdown successful
        """
        with self._lock:
            try:
                if self.bot_integration:
                    self.bot_integration.disconnect_from_bot()

                self.is_running = False
                logger.info('SimulationEngine shutdown complete')
                return True
            except Exception as e:
                logger.error(f'SimulationEngine shutdown failed: {e}')
                return False

    # =========================================================================
    # Variant Management
    # =========================================================================

    def apply_variant_preset(self, preset_name: str) -> None:
        """
        Apply a predefined variant preset (default, hard_mode, stress_test).

        Args:
            preset_name: Name of preset to apply

        Raises:
            ValueError: If preset name is invalid
        """
        with self._lock:
            self.variant_executor.apply_preset(preset_name)
            current = self.variant_executor.current_variant
            logger.info(
                f'Variant preset applied | {preset_name} | {current}'
            )

    def apply_variant(self, variant_config: Dict[str, str]) -> None:
        """
        Apply a custom variant configuration.

        Args:
            variant_config: Variant configuration dict

        Raises:
            ValueError: If configuration is invalid
        """
        with self._lock:
            self.variant_executor.apply_variant(variant_config)
            logger.info(f'Custom variant applied | {variant_config}')

    def get_current_variant(self) -> Dict[str, Any]:
        """
        Get current variant configuration and parameters.

        Returns:
            Dict with variant config and computed parameters
        """
        with self._lock:
            return self.variant_executor.get_state_params()

    # =========================================================================
    # Iteration Execution
    # =========================================================================

    def run_iteration(self, iteration_num: int) -> Dict[str, Any]:
        """
        Run a complete simulation iteration with all 6 phases.

        Phases:
        1. Setup (100ms): Apply variant, initialize state
        2. Alert (1-5s): Show alert, wait for detection
        3. Click (50-200ms): Log click, measure latency
        4. Treasure (500ms): Treasure opening, CPU measurement
        5. Chat Recovery (1-2s): Verify bot returned to chat
        6. Metrics (50ms): Aggregate and store results

        Args:
            iteration_num: Iteration number (0-indexed)

        Returns:
            Dict with iteration results {
                'iteration': int,
                'success': bool,
                'variant': str,
                'metrics': IterationMetrics dict,
                'duration_ms': int,
            }
        """
        with self._lock:
            if not self.is_initialized:
                raise RuntimeError('SimulationEngine not initialized')

            self.current_iteration = iteration_num
            iteration_start_ms = timestamp_ms()

            try:
                # Get current variant config
                variant_config = self.variant_executor.current_variant
                variant_name = '_'.join(
                    f"{k}={v}" for k, v in variant_config.items()
                )[:50]  # Truncate for logging

                # Start metrics collection for this iteration
                self.metrics_collector.start_iteration(
                    iteration=iteration_num,
                    variant=variant_name,
                )

                # Log iteration start
                if self.enable_logging:
                    logger.info(
                        f'[ITERATION {iteration_num}] Starting | variant={variant_name}'
                    )

                # === PHASE 1: Setup ===
                self._phase_setup(iteration_num, variant_config)

                # === PHASE 2: Alert Detection ===
                self._phase_alert_detection(iteration_num)

                # === PHASE 3: Click ===
                hit = self._phase_click(iteration_num)

                # === PHASE 4: Treasure ===
                self._phase_treasure(iteration_num)

                # === PHASE 5: Chat Recovery ===
                chat_recovered = self._phase_chat_recovery(iteration_num)

                # === PHASE 6: Finalize Metrics ===
                iteration_metrics = self._phase_finalize_metrics(
                    iteration_num, hit, chat_recovered, iteration_start_ms
                )

                iteration_duration_ms = timestamp_ms() - iteration_start_ms

                if self.enable_logging:
                    logger.info(
                        f'[ITERATION {iteration_num}] Complete | '
                        f'hit={hit} | recovered={chat_recovered} | '
                        f'duration={iteration_duration_ms}ms'
                    )

                return {
                    'iteration': iteration_num,
                    'success': hit and chat_recovered,
                    'variant': variant_name,
                    'metrics': iteration_metrics,
                    'duration_ms': iteration_duration_ms,
                }

            except Exception as e:
                logger.error(f'Iteration {iteration_num} failed: {e}')
                # Always finalize metrics even on error to prevent partial data
                try:
                    self.metrics_collector.end_iteration(
                        total_ms=timestamp_ms() - iteration_start_ms,
                        cpu_avg=0,
                        ram_mb=0,
                    )
                except Exception as finalize_err:
                    logger.error(f'Failed to finalize metrics on error: {finalize_err}')
                return {
                    'iteration': iteration_num,
                    'success': False,
                    'error': str(e),
                }

    # =========================================================================
    # Phase Implementations
    # =========================================================================

    def _phase_setup(
        self,
        iteration_num: int,
        variant_config: Dict[str, str],
    ) -> None:
        """Phase 1: Setup (100ms) — Apply variant, initialize state."""
        phase_start_ms = timestamp_ms()

        # Transition to initial state (chat) — skip if already in chat
        if self.game_state_manager.current_state != GameState.CHAT:
            self.game_state_manager.transition_to(GameState.CHAT)

        # Get state parameters from variant
        state_params = self.variant_executor.get_state_params()

        phase_duration_ms = timestamp_ms() - phase_start_ms
        self.metrics_collector.record_phase('setup', setup_ms=phase_duration_ms)

        if self.enable_logging:
            logger.debug(
                f'  [PHASE 1] Setup complete | {phase_duration_ms}ms | '
                f'chat_state={variant_config.get("chat_cleanliness")}'
            )

    def _phase_alert_detection(self, iteration_num: int) -> None:
        """Phase 2: Alert Detection (1-5s) — Show alert, wait for bot detection."""
        phase_start_ms = timestamp_ms()

        # Transition to alert state
        self.game_state_manager.transition_to(GameState.ALERT_ANIMATION)

        # Get duration from variant-aware config (replaces hardcoded mock)
        current_variant = self.get_current_variant()
        detection_time_ms = self._get_phase_duration('alert_detection', current_variant)
        ocr_confidence = self._get_click_accuracy_for_variant(current_variant)

        time.sleep(detection_time_ms / 1000.0)  # Simulate detection time

        self.metrics_collector.record_phase(
            'alert_detection',
            detection_ms=detection_time_ms,
            ocr_confidence=ocr_confidence,
        )

        if self.enable_logging:
            logger.debug(
                f'  [PHASE 2] Alert detected | {detection_time_ms}ms | '
                f'OCR: {ocr_confidence:.1%}'
            )

    def _phase_click(self, iteration_num: int) -> bool:
        """
        Phase 3: Click (50-200ms) — Log bot click, measure latency.

        Returns:
            True if click was a hit, False otherwise
        """
        phase_start_ms = timestamp_ms()

        # Transition to treasure state (click registered)
        self.game_state_manager.transition_to(GameState.TREASURE)

        # Get parameters from variant-aware config (replaces hardcoded mock)
        current_variant = self.get_current_variant()
        click_latency_ms = self._get_phase_duration('click', current_variant)
        click_accuracy = self._get_click_accuracy_for_variant(current_variant)

        # Prefer the bot's real decision target when integration is enabled.
        # This ties hit/miss validation to the coordinates the bot actually
        # chose instead of hardcoded mock positions.
        if self.bot_integration is not None:
            last_target = self.bot_integration.get_last_click_target()
            if last_target is not None:
                click_position_x, click_position_y, bot_confidence = last_target
                ocr_confidence = bot_confidence
                # Validate against the simulator's alert ROI using the bot's
                # chosen coordinates (delegated to the game-state manager).
                hit = self._validate_click_against_target(
                    click_position_x, click_position_y, current_variant
                )
            else:
                click_position_x = MOCK_PHASE_PARAMS['click']['click_position_x']
                click_position_y = MOCK_PHASE_PARAMS['click']['click_position_y']
                ocr_confidence = click_accuracy
                hit = random.random() < click_accuracy
        else:
            click_position_x = MOCK_PHASE_PARAMS['click']['click_position_x']
            click_position_y = MOCK_PHASE_PARAMS['click']['click_position_y']
            ocr_confidence = click_accuracy
            hit = random.random() < click_accuracy

        # Log click event
        self.game_state_manager.log_click(
            position_x=click_position_x,
            position_y=click_position_y,
            hit=hit,
            phase='click',
            ocr_confidence=ocr_confidence,
            latency_ms=click_latency_ms,
        )

        self.metrics_collector.record_phase(
            'click_latency',
            latency_ms=click_latency_ms,
            hit=hit,
        )

        if self.enable_logging:
            logger.debug(
                f'  [PHASE 3] Click registered | latency={click_latency_ms}ms | '
                f'hit={hit}'
            )

        return hit

    def _phase_treasure(self, iteration_num: int) -> None:
        """Phase 4: Treasure (500ms) — Simulate treasure opening, measure CPU."""
        phase_start_ms = timestamp_ms()

        # Already in TREASURE state from phase 3

        # Get parameters from variant-aware config (replaces hardcoded mock)
        current_variant = self.get_current_variant()
        cpu_spike_percent = self._get_cpu_load_for_variant(current_variant) * 100.0
        
        treasure_params = MOCK_PHASE_PARAMS['treasure']  # Still use for animation duration
        animation_duration_ms = treasure_params['animation_duration_ms']

        time.sleep(animation_duration_ms / 1000.0)  # Simulate treasure animation

        self.metrics_collector.record_phase(
            'cpu_spike',
            cpu_spike_percent=cpu_spike_percent,
        )

        if self.enable_logging:
            logger.debug(
                f'  [PHASE 4] Treasure opened | CPU spike: {cpu_spike_percent}%'
            )

    def _phase_chat_recovery(self, iteration_num: int) -> bool:
        """
        Phase 5: Chat Recovery (1-2s) — Verify bot returned to chat.

        Returns:
            True if chat recovered successfully, False otherwise
        """
        phase_start_ms = timestamp_ms()

        # Transition back to chat state
        self.game_state_manager.transition_to(GameState.CHAT_RECOVERY)

        # Get parameters from variant-aware config (replaces hardcoded mock)
        current_variant = self.get_current_variant()
        chat_recovery_ms = self._get_phase_duration('chat_recovery', current_variant)
        ocr_confidence = self._get_click_accuracy_for_variant(current_variant)
        
        recovery_params = MOCK_PHASE_PARAMS['chat_recovery']  # Still use for default state_verified
        state_verified = recovery_params['state_verified']

        time.sleep(0.05)  # Simulate recovery time

        self.metrics_collector.record_phase(
            'chat_recovery',
            recovery_ms=chat_recovery_ms,
            ocr_confidence=ocr_confidence,
            state_verified=state_verified,
        )

        if self.enable_logging:
            logger.debug(
                f'  [PHASE 5] Chat recovery | {chat_recovery_ms}ms | '
                f'verified={state_verified} | OCR: {ocr_confidence:.1%}'
            )

        return state_verified

    def _phase_finalize_metrics(
        self,
        iteration_num: int,
        hit: bool,
        chat_recovered: bool,
        iteration_start_ms: int,
    ) -> Dict[str, Any]:
        """
        Phase 6: Finalize Metrics (50ms) — Aggregate and store results.

        Uses the real wall-clock duration of this iteration instead of a
        hardcoded mock value, so exported totals reflect actual timing.

        Returns:
            Dict with iteration metrics
        """
        phase_start_ms = timestamp_ms()

        total_iteration_ms = max(0, phase_start_ms - iteration_start_ms)

        # CPU/RAM from the bot integration layer when available; otherwise 0.
        cpu_avg = 0
        ram_mb = 0
        if self.bot_integration is not None:
            cpu_avg = int(self.bot_integration.get_cpu_percent())
            ram_mb = int(self.bot_integration.get_memory_mb())

        # Call end_iteration to finalize metrics in MetricsCollector
        self.metrics_collector.end_iteration(
            total_ms=total_iteration_ms,
            cpu_avg=cpu_avg,
            ram_mb=ram_mb,
        )

        # Build iteration metrics dict
        iteration_data = self.metrics_collector.iterations.get(iteration_num, {})

        # Return to CHAT state for next iteration
        self.game_state_manager.transition_to(GameState.CHAT)

        if self.enable_logging:
            logger.debug(
                f'  [PHASE 6] Metrics finalized | '
                f'total={total_iteration_ms}ms | CPU_avg={cpu_avg}% | RAM={ram_mb}MB | '
                f'returning to CHAT for next iteration'
            )

        return iteration_data

    # =========================================================================
    # Results & Aggregation
    # =========================================================================

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get session-wide aggregated metrics.

        Returns:
            Dict with {
                'session_id': str,
                'variant': dict,
                'iterations_total': int,
                'iterations_hit': int,
                'accuracy_percent': float,
                'latency_avg_ms': float,
                'latency_std_ms': float,
                'latency_p95_ms': float,
                'latency_p99_ms': float,
                'cpu_spike_max_percent': int,
                'cpu_spike_avg_percent': int,
                'reliability_percent': float,
                'chat_recovery_failures': int,
                'anomalies': List[dict],
            }
        """
        with self._lock:
            iterations = self.metrics_collector.iterations
            if not iterations:
                return {}

            # Extract metrics from all iterations
            hits = sum(
                1 for it in iterations.values()
                if it.get('phase_3_hit') is True
            )
            total = len(iterations)
            accuracy_percent = (hits / total * 100) if total > 0 else 0

            # Latency stats (skip None values)
            latencies = [
                it['phase_3_click_latency_ms']
                for it in iterations.values()
                if it.get('phase_3_click_latency_ms') is not None
            ]
            latency_avg = sum(latencies) / len(latencies) if latencies else 0
            latency_std = (
                (sum((x - latency_avg) ** 2 for x in latencies) / len(latencies)) ** 0.5
                if latencies
                else 0
            )

            # CPU stats
            cpu_spikes = [
                it['phase_4_cpu_spike_percent']
                for it in iterations.values()
                if it.get('phase_4_cpu_spike_percent') is not None
            ]
            cpu_max = max(cpu_spikes) if cpu_spikes else 0
            cpu_avg = sum(cpu_spikes) / len(cpu_spikes) if cpu_spikes else 0

            # Chat recovery failures
            chat_failures = sum(
                1 for it in iterations.values()
                if it.get('phase_5_state_verified') is False
            )

            # Reliability
            reliability_percent = (
                ((total - chat_failures) / total * 100) if total > 0 else 0
            )

            return {
                'session_id': self.session_id,
                'variant': self.variant_executor.current_variant,
                'iterations_total': total,
                'iterations_hit': hits,
                'accuracy_percent': accuracy_percent,
                'latency_avg_ms': latency_avg,
                'latency_std_ms': latency_std,
                'latency_p95_ms': (
                    sorted(latencies)[min(int(len(latencies) * 0.95), len(latencies) - 1)]
                    if latencies else 0
                ),
                'latency_p99_ms': (
                    sorted(latencies)[min(int(len(latencies) * 0.99), len(latencies) - 1)]
                    if latencies else 0
                ),
                'cpu_spike_max_percent': cpu_max,
                'cpu_spike_avg_percent': cpu_avg,
                'reliability_percent': reliability_percent,
                'chat_recovery_failures': chat_failures,
                'anomalies': [],
            }

    # =========================================================================
    # UI Threading - Background Updates
    # =========================================================================

    def start_ui_thread(self) -> None:
        """
        Start background thread for non-blocking UI updates.

        Thread runs at 50ms refresh rate and processes queues without blocking
        the main simulation loop.
        """
        with self._lock:
            if self._ui_thread is not None and self._ui_thread.is_alive():
                logger.warning('UI thread already running')
                return

            self._ui_thread_running = True
            self._ui_thread = Thread(target=self._ui_thread_worker, daemon=True)
            self._ui_thread.start()
            logger.info('UI thread started')

    def stop_ui_thread(self) -> None:
        """Stop background UI thread."""
        with self._lock:
            self._ui_thread_running = False
            if self._ui_thread is not None:
                self._ui_thread.join(timeout=2.0)
                self._ui_thread = None
                logger.info('UI thread stopped')

    def _ui_thread_worker(self) -> None:
        """
        Background thread worker: process queues at 50ms refresh rate.

        Continuously drains metrics, state, and event queues to prevent blocking
        the main simulation thread.
        """
        refresh_interval_ms = 50
        refresh_interval_s = refresh_interval_ms / 1000.0

        while self._ui_thread_running:
            try:
                # Process all queued items (non-blocking drains)
                self._drain_queue(self.metrics_queue)
                self._drain_queue(self.state_queue)
                self._drain_queue(self.event_queue)

                # Sleep for refresh interval
                time.sleep(refresh_interval_s)
            except Exception as e:
                logger.error(f'Error in UI thread worker: {e}')

    def _drain_queue(self, q: Queue) -> List[Any]:
        """
        Drain all items from queue without blocking.

        Returns:
            List of dequeued items
        """
        items = []
        try:
            while True:
                item = q.get_nowait()
                items.append(item)
        except:
            pass  # Queue is empty
        return items

    def send_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Send metrics update to UI queue (thread-safe).

        Uses drop-oldest-on-full policy to prevent backpressure blocking.

        Args:
            metrics: Metrics dict to queue for UI display
        """
        try:
            # Drop oldest item if queue is full (backpressure mitigation)
            if self.metrics_queue.full():
                try:
                    self.metrics_queue.get_nowait()
                except:
                    pass  # Queue became non-full in race condition
            self.metrics_queue.put_nowait(metrics)
        except Exception as e:
            logger.warning(f'Failed to queue metrics: {e}')

    def push_metrics(self, metrics_dict: Dict[str, Any]) -> None:
        """
        Push metrics to UI queue for real-time display (thread-safe).

        Alias for send_metrics() with more intuitive naming.
        Sends accuracy, latency_ms, cpu_percent, current_state, variant, cps_current, system_load to UI.
        
        Uses non-blocking put with drop-oldest-on-full policy for graceful
        degradation if queue is full.

        Args:
            metrics_dict: Dictionary with keys:
                - accuracy: float (0-100%)
                - latency_ms: float (milliseconds)
                - cpu_percent: float (0-100%)
                - current_state: str or GameState (current game state)
                - variant: str (current variant name)
                - cps_current: float (clicks per second)
                - system_load: float (system load 0-100%)
        """
        self.send_metrics(metrics_dict)

    def send_state(self, state_update: Dict[str, Any]) -> None:
        """
        Send state update to UI queue (thread-safe).

        Uses drop-oldest-on-full policy to prevent backpressure blocking.

        Args:
            state_update: State change dict
        """
        try:
            # Drop oldest item if queue is full (backpressure mitigation)
            if self.state_queue.full():
                try:
                    self.state_queue.get_nowait()
                except:
                    pass  # Queue became non-full in race condition
            self.state_queue.put_nowait(state_update)
        except Exception as e:
            logger.warning(f'Failed to queue state: {e}')

    def send_event(self, event: Dict[str, Any]) -> None:
        """
        Send timeline event to UI queue (thread-safe).

        Uses drop-oldest-on-full policy to prevent backpressure blocking.

        Args:
            event: Event dict with timestamp, phase, status
        """
        try:
            # Drop oldest item if queue is full (backpressure mitigation)
            if self.event_queue.full():
                try:
                    self.event_queue.get_nowait()
                except:
                    pass  # Queue became non-full in race condition
            self.event_queue.put_nowait(event)
        except Exception as e:
            logger.warning(f'Failed to queue event: {e}')

    def get_metrics_queue(self) -> Queue:
        """Return metrics queue for UI attachment."""
        return self.metrics_queue

    def get_state_queue(self) -> Queue:
        """Return state queue for UI attachment."""
        return self.state_queue

    def get_event_queue(self) -> Queue:
        """Return event queue for UI attachment."""
        return self.event_queue

    def export_session(
        self,
        output_dir: Optional[str] = None,
    ) -> str:
        """
        Export session data to JSON file.

        Args:
            output_dir: Output directory path. If None, uses current working directory.

        Returns:
            Path to exported JSON file
        """
        with self._lock:
            if output_dir is None:
                output_dir = '.'

            output_path = Path(output_dir) / f'session_{self.session_id}.json'
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare export data
            export_data = {
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'aggregated_metrics': self.get_aggregated_metrics(),
                'iterations': self.metrics_collector.iterations,
            }

            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            logger.info(f'Session exported to {output_path}')
            return str(output_path)

    # =========================================================================
    # Context Manager Support (Issue #10)
    # =========================================================================

    def __enter__(self):
        """
        Context manager entry: Initialize engine on entry.

        Usage:
            with SimulationEngine(session_id='test') as engine:
                engine.apply_variant_preset('default')
                engine.run_iteration(0)
        """
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: Cleanup resources on exit."""
        try:
            self.stop_ui_thread()
        except Exception as e:
            logger.error(f'Failed to stop UI thread in __exit__: {e}')
        
        try:
            self.shutdown()
        except Exception as e:
            logger.error(f'Failed to shutdown engine in __exit__: {e}')
        
        return False  # Don't suppress exceptions


    def _get_phase_duration(self, phase_name: str, variant: Optional[Dict[str, str]] = None) -> int:
        """
        Get phase duration based on variant configuration.
        
        Args:
            phase_name: Phase name (e.g., 'click', 'alert_detection')
            variant: Current variant config dict
            
        Returns:
            Duration in milliseconds
        """
        # Base duration from MOCK_PHASE_PARAMS
        base_duration = MOCK_PHASE_PARAMS.get(phase_name, {}).get('duration_ms', 100)
        
        if variant is None:
            return base_duration
        
        # Adjust based on variant dimensions
        multiplier = 1.0
        
        # Alert timing affects alert_detection and click phases
        if phase_name in ('alert_detection', 'click'):
            alert_timing = variant.get('alert_timing', 'immediate')
            if alert_timing == 'delayed':
                multiplier *= 1.5  # 50% longer
            elif alert_timing == 'overlapped':
                multiplier *= 2.0  # 100% longer
        
        # System load affects CPU spike and overall timing
        if phase_name == 'cpu_spike':
            system_load = variant.get('system_load', 'idle')
            if system_load == 'medium':
                multiplier *= 1.3
            elif system_load == 'high':
                multiplier *= 1.8
        
        # Bot config affects click latency
        if phase_name == 'click':
            bot_config = variant.get('bot_config', '38_cps')
            if bot_config == '30_cps':
                multiplier *= 1.2  # Slower clicks
            elif bot_config == 'aggressive':
                multiplier *= 0.7  # Faster clicks
        
        return int(base_duration * multiplier)

    def _get_cpu_load_for_variant(self, variant: Optional[Dict[str, str]] = None) -> float:
        """Get CPU load percentage based on variant system_load."""
        if variant is None:
            return 0.1  # Idle
        
        system_load = variant.get('system_load', 'idle')
        load_map = {
            'idle': 0.1,
            'medium': 0.5,
            'high': 0.75,
        }
        return load_map.get(system_load, 0.1)

    def _validate_click_against_target(
        self,
        click_x: int,
        click_y: int,
        variant: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Validate a bot click against the simulator's alert target.

        The headless SimulationEngine does not render frames, so it has no
        pixel-accurate alert bounding box to test against. Until the engine is
        connected to a rendered simulator frame, fall back to the
        variant-influenced accuracy as the hit probability. The dedicated GUI
        simulator (mvp/simulator/game.py) performs real pixel
        hit-testing in verify_click().

        Args:
            click_x: Click X coordinate
            click_y: Click Y coordinate
            variant: Current variant configuration

        Returns:
            True if the click is considered a hit, False otherwise.
        """
        accuracy = self._get_click_accuracy_for_variant(variant)
        return random.random() < accuracy

    def _get_click_accuracy_for_variant(self, variant: Optional[Dict[str, str]] = None) -> float:
        """Get click accuracy percentage based on variant."""
        if variant is None:
            return 0.95  # 95% accuracy baseline
        
        accuracy = 0.95
        
        # Chat cleanliness affects OCR and thus accuracy
        chat_state = variant.get('chat_cleanliness', 'clean')
        if chat_state == 'cluttered':
            accuracy *= 0.90  # 10% degradation
        elif chat_state == 'spam':
            accuracy *= 0.75  # 25% degradation
        
        # Heli visibility
        heli_visible = variant.get('heli_visibility', 'visible')
        if heli_visible == 'hidden':
            accuracy *= 0.80  # 20% degradation
        elif heli_visible == 'partial':
            accuracy *= 0.85  # 15% degradation
        
        # Eye tracking
        eye_tracking = variant.get('eye_tracking', 'focused')
        if eye_tracking == 'distracted':
            accuracy *= 0.85  # 15% degradation
        elif eye_tracking == 'loss_event':
            accuracy *= 0.60  # 40% degradation
        
        return max(0.1, min(1.0, accuracy))


    def apply_timer_perturbation(self, perturbation_name: str) -> bool:
        """
        Apply timer perturbation to current variant.
        
        Perturbations:
        - chaotic_timer: Random timer jumps ±5-20 seconds during phase
        - frozen_timer: Timer freeze for 2s mid-phase
        - accelerated_timer: 2x countdown speed
        - hidden_timer: Timer invisible but still counting
        - distracted_chat: Chat visible alongside timer overlay
        
        Args:
            perturbation_name: Name of perturbation to apply
            
        Returns:
            True if applied successfully, False if unknown perturbation
        """
        with self._lock:
            valid_perturbations = [
                'chaotic_timer',
                'frozen_timer', 
                'accelerated_timer',
                'hidden_timer',
                'distracted_chat'
            ]
            
            if perturbation_name not in valid_perturbations:
                logger.warning(f'Unknown perturbation: {perturbation_name}')
                return False
            
            # Get current variant from executor
            current_raw = self.variant_executor.current_variant.copy()
            
            # Apply perturbation using VariantExecutor method
            modified = self.variant_executor.apply_timer_perturbation(
                perturbation_name, 
                current_raw
            )
            
            # Update executor's current_variant directly
            self.variant_executor.current_variant = modified
            
            logger.info(f'Applied timer perturbation: {perturbation_name}')
            self.send_event({
                'type': 'perturbation_applied',
                'perturbation': perturbation_name,
                'timestamp_ms': timestamp_ms()
            })
            
            return True

    def _apply_timer_perturbation_during_phase(self, elapsed_ms: int, total_ms: int = 60000) -> Dict[str, Any]:
        """
        Apply timer perturbation effects during phase execution.
        
        Args:
            elapsed_ms: Milliseconds elapsed in phase
            total_ms: Total phase duration (default 60s for treasure phase)
            
        Returns:
            Dict with perturbation effects (adjusted_elapsed, visual_state, etc.)
        """
        current_variant = self.get_current_variant()
        timer_mode = current_variant.get('timer_mode', None)
        
        if not timer_mode:
            return {'adjusted_elapsed_ms': elapsed_ms, 'effects': {}}
        
        effects = {}
        adjusted_elapsed = elapsed_ms
        
        # Chaotic Timer: Random jumps ±5-20s
        if timer_mode == 'chaotic':
            jump_range = current_variant.get('timer_jump_range_ms', (5000, 20000))
            if elapsed_ms % 1000 < 50:  # Trigger jump every ~1s
                jump = random.randint(jump_range[0], jump_range[1])
                if random.random() < 0.5:
                    adjusted_elapsed = max(0, adjusted_elapsed - jump)
                else:
                    adjusted_elapsed = min(total_ms, adjusted_elapsed + jump)
                effects['jumped'] = True
                effects['jump_amount_ms'] = jump
        
        # Frozen Timer: Halt for N seconds
        elif timer_mode == 'frozen':
            freeze_duration = current_variant.get('freeze_duration_ms', 2000)
            if elapsed_ms > total_ms // 2:  # Freeze in middle
                adjusted_elapsed = total_ms // 2
                effects['frozen'] = True
                effects['freeze_duration_ms'] = freeze_duration
        
        # Accelerated Timer: 2x-4x speed
        elif timer_mode == 'accelerated':
            speed = current_variant.get('speed_multiplier', 2.0)
            adjusted_elapsed = int(elapsed_ms * speed)
            effects['speed_multiplier'] = speed
        
        # Hidden Timer: No visual change, but metric tracked
        elif timer_mode == 'hidden':
            effects['render_visible'] = False
            effects['still_counting'] = True
        
        # Distracted Chat: Show chat during timer
        elif timer_mode == 'distracted':
            effects['show_chat'] = True
            effects['show_timer'] = True
            effects['chat_distraction'] = True
        
        # Cap adjusted elapsed at total
        adjusted_elapsed = min(total_ms, max(0, adjusted_elapsed))
        
        return {
            'adjusted_elapsed_ms': adjusted_elapsed,
            'effects': effects,
            'timer_mode': timer_mode
        }
