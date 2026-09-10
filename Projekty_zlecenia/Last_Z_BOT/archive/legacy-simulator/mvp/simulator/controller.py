"""
SimulatorController — Orchestrator Facade for Extended Game Simulator.

Responsibilities:
- Initialize and manage SimulationEngine lifecycle
- Coordinate variant application and iteration execution
- Provide high-level API for session control
- Handle session export and report generation
- Manage UI threading (optional)

This is the main interface for task execution and integration.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from mvp.simulator.engine import SimulationEngine
from mvp.simulator.utils import setup_logger


logger = setup_logger(__name__)


class SimulatorController:
    """
    High-level orchestrator for Extended Game Simulator Framework.

    Provides a clean API for:
    1. Initialization and configuration
    2. Variant management (preset selection, custom variants)
    3. Iteration execution
    4. Metrics aggregation and retrieval
    5. Session export and report generation
    6. Lifecycle management (initialize → run → export → shutdown)

    Usage:
        controller = SimulatorController(
            config={'skip_bot_integration': True},
            enable_ui=False
        )
        controller.initialize()
        controller.set_variant_preset('default')
        results = controller.run_iterations(num_iterations=10)
        metrics = controller.get_final_metrics()
        controller.export_session(output_dir='results/')
        controller.shutdown()
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        enable_ui: bool = False,
        session_id: Optional[str] = None,
    ):
        """
        Initialize SimulatorController.

        Args:
            config: Configuration dict for SimulationEngine
                   (e.g., {'skip_bot_integration': True})
            enable_ui: Whether to enable interactive UI (Phase 2 feature)
            session_id: Optional session identifier; auto-generated if not provided
        """
        self.config = config or {}
        self.enable_ui = enable_ui
        self.session_id = session_id

        # Create engine
        self.engine = SimulationEngine(
            session_id=session_id,
            config=self.config
        )

        self._is_initialized = False
        self._iteration_results: List[Dict[str, Any]] = []

        logger.info(
            f'SimulatorController initialized (session={self.session_id}, '
            f'ui={enable_ui})'
        )

    def initialize(self) -> bool:
        """
        Initialize the simulation engine.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            result = self.engine.initialize()
            self._is_initialized = result

            if self._is_initialized:
                logger.info('SimulatorController: Engine initialized successfully')

                # Start UI thread if enabled
                if self.enable_ui:
                    logger.info('Starting UI thread...')
                    self.engine.start_ui_thread()
            else:
                logger.error('SimulatorController: Failed to initialize engine')

            return result
        except Exception as e:
            logger.error(f'SimulatorController: Initialization error: {e}')
            return False

    def shutdown(self) -> bool:
        """
        Shutdown the simulation engine.

        Returns:
            True if shutdown successful, False otherwise
        """
        try:
            if self.enable_ui:
                logger.info('Stopping UI thread...')
                self.engine.stop_ui_thread()

            result = self.engine.shutdown()

            if result:
                self._is_initialized = False
                logger.info('SimulatorController: Engine shut down successfully')
            else:
                logger.error('SimulatorController: Failed to shut down engine')

            return result
        except Exception as e:
            logger.error(f'SimulatorController: Shutdown error: {e}')
            return False

    def set_variant_preset(self, preset_name: str) -> None:
        """
        Apply a variant preset.

        Valid presets: "default", "hard_mode", "stress_test"

        Args:
            preset_name: Name of preset to apply

        Raises:
            RuntimeError: If engine not initialized
            ValueError: If preset not recognized
        """
        if not self._is_initialized:
            raise RuntimeError('Engine not initialized. Call initialize() first.')

        self.engine.apply_variant_preset(preset_name)
        logger.info(f'Applied variant preset: {preset_name}')

    def set_custom_variant(self, variant_config: Dict[str, str]) -> None:
        """
        Apply a custom variant configuration.

        Args:
            variant_config: Dictionary with variant configuration

        Raises:
            RuntimeError: If engine not initialized
            ValueError: If configuration invalid
        """
        if not self._is_initialized:
            raise RuntimeError('Engine not initialized. Call initialize() first.')

        self.engine.apply_variant(variant_config)
        logger.info(f'Applied custom variant')

    def run_iterations(self, num_iterations: int) -> List[Dict[str, Any]]:
        """
        Run specified number of iterations.

        Each iteration:
        1. Executes full game loop (alert → click → treasure → chat_recovery)
        2. Collects metrics for all phases
        3. Returns result dict with success status and metrics

        Args:
            num_iterations: Number of iterations to run

        Returns:
            List of result dicts (one per iteration)

        Raises:
            RuntimeError: If engine not initialized
        """
        if not self._is_initialized:
            raise RuntimeError('Engine not initialized. Call initialize() first.')

        results = []

        for i in range(num_iterations):
            try:
                logger.info(f'Running iteration {i + 1}/{num_iterations}...')

                result = self.engine.run_iteration(iteration_num=i)
                results.append(result)

                self._iteration_results.append(result)

                # Log result
                if result.get('success'):
                    logger.info(f'  ✓ Iteration {i} completed successfully')
                else:
                    logger.warning(f'  ✗ Iteration {i} completed with status: '
                                 f'{result.get("status", "unknown")}')

            except Exception as e:
                logger.error(f'Iteration {i} error: {e}')
                results.append({
                    'iteration': i,
                    'success': False,
                    'error': str(e),
                })

        logger.info(f'Completed {num_iterations} iterations')
        return results

    def get_final_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics for all completed iterations.

        Returns dictionary with:
        - iterations_total: Total iteration count
        - iterations_hit: Successful hits
        - accuracy_percent: Success rate (%)
        - latency_avg_ms: Average latency (ms)
        - latency_std_ms: Latency std dev (ms)
        - latency_p95_ms: 95th percentile latency (ms)
        - latency_p99_ms: 99th percentile latency (ms)
        - cpu_spike_max_percent: Max CPU spike (%)
        - cpu_spike_avg_percent: Avg CPU spike (%)
        - reliability_percent: Reliability rate (%)
        - chat_recovery_failures: Count of failed chat recoveries
        - anomalies: List of anomalies detected

        Returns:
            Dictionary with aggregated metrics

        Raises:
            RuntimeError: If engine not initialized
        """
        if not self._is_initialized:
            raise RuntimeError('Engine not initialized. Call initialize() first.')

        metrics = self.engine.get_aggregated_metrics()
        logger.info(f'Aggregated metrics: {len(self._iteration_results)} iterations')
        return metrics

    def export_session(self, output_dir: str) -> str:
        """
        Export session data to JSON file.

        Saves:
        - Session metadata
        - Variant configuration
        - Per-iteration metrics
        - Aggregated metrics
        - Anomalies

        Args:
            output_dir: Directory path for export file

        Returns:
            Path to exported file

        Raises:
            RuntimeError: If engine not initialized
        """
        if not self._is_initialized:
            raise RuntimeError('Engine not initialized. Call initialize() first.')

        export_file = self.engine.export_session(output_dir=output_dir)
        logger.info(f'Session exported: {export_file}')
        return export_file

    def generate_report(self, output_dir: str) -> str:
        """
        Generate HTML report of session results.

        Creates HTML report with:
        - Session summary
        - Variant configuration
        - Metrics tables and charts
        - Heatmaps (click positions, OCR confidence)
        - Timelines (phases, CPU/RAM trends)
        - Anomaly analysis

        Args:
            output_dir: Directory path for report file

        Returns:
            Path to generated report file

        Raises:
            RuntimeError: If engine not initialized or report generation fails
        """
        if not self._is_initialized:
            raise RuntimeError('Engine not initialized. Call initialize() first.')

        # Import reporting engine
        try:
            from mvp.simulator.reporting.report_generator import ReportGenerator
        except ImportError:
            logger.error('ReportGenerator not available (Phase 3 feature)')
            raise RuntimeError('Report generation not available in this build')

        try:
            # Create report generator
            generator = ReportGenerator(
                session_data=self.engine.get_session_metrics(),
                output_dir=output_dir
            )

            # Generate report
            report_file = generator.generate_report()
            logger.info(f'Report generated: {report_file}')
            return report_file

        except Exception as e:
            logger.error(f'Report generation failed: {e}')
            raise RuntimeError(f'Failed to generate report: {e}')

    def get_engine(self) -> SimulationEngine:
        """
        Get reference to underlying SimulationEngine.

        Useful for advanced usage or direct metric access.

        Returns:
            SimulationEngine instance
        """
        return self.engine

    def get_session_id(self) -> str:
        """
        Get session identifier.

        Returns:
            Session ID string
        """
        return self.engine.session_id

    @property
    def is_initialized(self) -> bool:
        """Check if controller is initialized."""
        return self._is_initialized

    @property
    def iteration_count(self) -> int:
        """Get number of completed iterations."""
        return len(self._iteration_results)
