# mvp/simulator/metrics.py
"""
MetricsCollector: Per-iteration metrics collection and session-wide aggregation.

Collects metrics for each iteration phase (setup, alert, click, treasure, chat recovery)
and aggregates data to compute session-level statistics (accuracy, latency, reliability).

Thread-safe metrics storage with support for:
- Per-iteration phase recording
- Aggregation functions (accuracy, latency percentiles, reliability)
- Session metadata (session_id, variant configuration)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
import statistics
from threading import Lock

from mvp.simulator.utils import setup_logger


logger = setup_logger(__name__)


def percentile(data: List[float], p: float) -> float:
    """
    Calculate percentile value from sorted data.

    Args:
        data: List of numeric values
        p: Percentile (0-100)

    Returns:
        Percentile value
    """
    if not data:
        return None
    sorted_data = sorted(data)
    index = (p / 100) * (len(sorted_data) - 1)
    lower = int(index)
    upper = lower + 1

    if upper >= len(sorted_data):
        return sorted_data[lower]

    weight = index - lower
    return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


class MetricsCollector:
    """
    Collects per-iteration metrics and computes session-wide aggregations.

    Per-Iteration Metrics (6 phases):
    - Phase 1: Setup (~100ms) — setup_ms
    - Phase 2: Alert Detection (~1-5s) — detection_ms, ocr_confidence
    - Phase 3: Click (~50-200ms) — latency_ms, hit
    - Phase 4: Treasure (~500ms) — cpu_spike_percent
    - Phase 5: Chat Recovery (~1-2s) — recovery_ms, ocr_confidence, state_verified
    - Phase 6: Finalize (~50ms) — total_iteration_ms, cpu_avg, ram_mb

    Aggregated Metrics:
    - Accuracy: hit count / total clicks
    - Latency stats: avg, std, p95, p99
    - Reliability: 1 - (chat_recovery_failures / total)
    - Chat recovery failures
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize MetricsCollector.

        Args:
            session_id: Optional session identifier. If None, generated from timestamp.
        """
        self._lock = Lock()

        # Session metadata
        self.session_id = (
            session_id
            if session_id is not None
            else datetime.now().strftime('%Y%m%d_%H%M%S')
        )
        self.session_start_ms = int(datetime.now().timestamp() * 1000)

        # Iterations storage: { iteration_num: { phase data } }
        self.iterations: Dict[int, Dict[str, Any]] = {}
        self.current_iteration = -1

        logger.info(
            f'MetricsCollector initialized | session_id={self.session_id}'
        )

    def start_iteration(
        self,
        iteration: int,
        variant: Optional[str] = None,
    ) -> None:
        """
        Start a new iteration and initialize phase metrics storage.

        Args:
            iteration: Iteration number (typically 0-indexed or 1-indexed)
            variant: Optional variant identifier (e.g., 'clean_30cps', 'cluttered_38cps')

        Returns:
            None
        """
        with self._lock:
            self.current_iteration = iteration

            # Initialize all phase fields to None
            self.iterations[iteration] = {
                'iteration': iteration,
                'variant': variant,
                # Phase 1: Setup
                'phase_1_setup_ms': None,
                # Phase 2: Alert Detection
                'phase_2_alert_detection_ms': None,
                'phase_2_ocr_confidence': None,
                # Phase 3: Click Latency
                'phase_3_click_latency_ms': None,
                'phase_3_hit': None,
                # Phase 4: CPU Spike (Treasure)
                'phase_4_cpu_spike_percent': None,
                # Phase 5: Chat Recovery
                'phase_5_chat_recovery_ms': None,
                'phase_5_ocr_confidence': None,
                'phase_5_state_verified': None,
                # Phase 6: Finalize (totals)
                'total_iteration_ms': None,
                'cpu_avg': None,
                'ram_mb': None,
            }

            logger.debug(
                f'Iteration started | #{iteration} | variant={variant}'
            )

    def record_phase(
        self,
        phase_name: str,
        **metrics_dict: Any,
    ) -> None:
        """
        Record metrics for a specific phase.

        Phase names:
        - 'setup': phase_1 — kwargs: setup_ms
        - 'alert_detection': phase_2 — kwargs: detection_ms, ocr_confidence
        - 'click_latency': phase_3 — kwargs: latency_ms, hit
        - 'cpu_spike': phase_4 — kwargs: cpu_spike_percent
        - 'chat_recovery': phase_5 — kwargs: recovery_ms, ocr_confidence, state_verified

        Args:
            phase_name: Name of the phase
            **metrics_dict: Phase-specific metrics as keyword arguments

        Returns:
            None
        """
        with self._lock:
            if self.current_iteration not in self.iterations:
                logger.warning(
                    f'No active iteration for phase recording: {phase_name}'
                )
                return

            iter_data = self.iterations[self.current_iteration]

            # Map phase_name to phase fields and update from metrics_dict
            if phase_name == 'setup':
                if 'setup_ms' in metrics_dict:
                    iter_data['phase_1_setup_ms'] = metrics_dict['setup_ms']

            elif phase_name == 'alert_detection':
                if 'detection_ms' in metrics_dict:
                    iter_data['phase_2_alert_detection_ms'] = metrics_dict[
                        'detection_ms'
                    ]
                if 'ocr_confidence' in metrics_dict:
                    iter_data['phase_2_ocr_confidence'] = metrics_dict[
                        'ocr_confidence'
                    ]

            elif phase_name == 'click_latency':
                if 'latency_ms' in metrics_dict:
                    iter_data['phase_3_click_latency_ms'] = metrics_dict['latency_ms']
                if 'hit' in metrics_dict:
                    iter_data['phase_3_hit'] = metrics_dict['hit']

            elif phase_name == 'cpu_spike':
                if 'cpu_spike_percent' in metrics_dict:
                    iter_data['phase_4_cpu_spike_percent'] = metrics_dict[
                        'cpu_spike_percent'
                    ]

            elif phase_name == 'chat_recovery':
                if 'recovery_ms' in metrics_dict:
                    iter_data['phase_5_chat_recovery_ms'] = metrics_dict[
                        'recovery_ms'
                    ]
                if 'ocr_confidence' in metrics_dict:
                    iter_data['phase_5_ocr_confidence'] = metrics_dict[
                        'ocr_confidence'
                    ]
                if 'state_verified' in metrics_dict:
                    iter_data['phase_5_state_verified'] = metrics_dict[
                        'state_verified'
                    ]

            logger.debug(
                f'Phase recorded | iteration={self.current_iteration} | '
                f'phase={phase_name} | metrics={metrics_dict}'
            )

    def end_iteration(
        self,
        total_ms: int,
        cpu_avg: int,
        ram_mb: int,
    ) -> None:
        """
        Complete current iteration and record finalize metrics.

        Args:
            total_ms: Total iteration duration (milliseconds)
            cpu_avg: Average CPU usage (percent)
            ram_mb: RAM usage (megabytes)

        Returns:
            None
        """
        with self._lock:
            if self.current_iteration not in self.iterations:
                logger.warning(
                    f'No active iteration #{self.current_iteration} to finalize'
                )
                return

            iter_data = self.iterations[self.current_iteration]
            iter_data['total_iteration_ms'] = total_ms
            iter_data['cpu_avg'] = cpu_avg
            iter_data['ram_mb'] = ram_mb

            logger.debug(
                f'Iteration finalized | #{self.current_iteration} | '
                f'total_ms={total_ms} | cpu_avg={cpu_avg}% | ram_mb={ram_mb}'
            )

    def aggregate(self) -> Dict[str, Any]:
        """
        Compute session-wide aggregated metrics.

        Returns dictionary with:
        - session_id: Session identifier
        - iterations_total: Total iterations
        - iterations_hit: Count of successful clicks
        - accuracy_percent: (hits / total) * 100
        - latency_avg_ms: Average click latency
        - latency_std_ms: Standard deviation of latency
        - latency_p95_ms: 95th percentile latency
        - latency_p99_ms: 99th percentile latency
        - chat_recovery_failures: Count of failed chat recoveries
        - reliability_percent: (successful_recoveries / total) * 100

        Returns:
            Dictionary with aggregated metrics
        """
        with self._lock:
            total_iterations = len(self.iterations)

            if total_iterations == 0:
                logger.debug('No iterations to aggregate')
                return {
                    'session_id': self.session_id,
                    'iterations_total': 0,
                    'iterations_hit': 0,
                    'accuracy_percent': 0.0,
                    'latency_avg_ms': None,
                    'latency_std_ms': None,
                    'latency_p95_ms': None,
                    'latency_p99_ms': None,
                    'chat_recovery_failures': 0,
                    'reliability_percent': 0.0,
                }

            # Count hits
            hit_count = 0
            latencies: List[float] = []
            recovery_failures = 0

            for iter_data in self.iterations.values():
                # Count hits (phase_3_hit == True)
                if iter_data.get('phase_3_hit') is True:
                    hit_count += 1

                # Collect latencies
                latency = iter_data.get('phase_3_click_latency_ms')
                if latency is not None:
                    latencies.append(float(latency))

                # Count recovery failures (state_verified == False)
                if iter_data.get('phase_5_state_verified') is False:
                    recovery_failures += 1

            # Accuracy: (hits / total) * 100
            accuracy_pct = (hit_count / total_iterations * 100) if total_iterations > 0 else 0.0

            # Latency statistics
            latency_avg = None
            latency_std = None
            latency_p95 = None
            latency_p99 = None

            if latencies:
                latency_avg = sum(latencies) / len(latencies)
                if len(latencies) > 1:
                    latency_std = statistics.stdev(latencies)
                else:
                    latency_std = 0.0
                latency_p95 = percentile(latencies, 95.0)
                latency_p99 = percentile(latencies, 99.0)

            # Reliability: (total - recovery_failures) / total * 100
            successful_recoveries = total_iterations - recovery_failures
            reliability_pct = (
                (successful_recoveries / total_iterations * 100)
                if total_iterations > 0
                else 0.0
            )

            result = {
                'session_id': self.session_id,
                'iterations_total': total_iterations,
                'iterations_hit': hit_count,
                'accuracy_percent': accuracy_pct,
                'latency_avg_ms': latency_avg,
                'latency_std_ms': latency_std,
                'latency_p95_ms': latency_p95,
                'latency_p99_ms': latency_p99,
                'chat_recovery_failures': recovery_failures,
                'reliability_percent': reliability_pct,
            }

            logger.info(
                f'Metrics aggregated | total_iterations={total_iterations} | '
                f'accuracy={accuracy_pct:.1f}% | reliability={reliability_pct:.1f}% | '
                f'avg_latency={latency_avg}ms'
            )

            return result

    def get_predictions(self) -> Dict[str, Any]:
        """
        Get ML predictions for next iteration using collected metrics.

        Returns:
            Dictionary with predicted_accuracy_pct and anomaly_score
        """
        try:
            from mvp.simulator.ml_predictor import MLPredictor, AnomalyScorer

            with self._lock:
                # Prepare history for predictor
                history = []
                for iter_num in sorted(self.iterations.keys()):
                    iter_data = self.iterations[iter_num]
                    if iter_data.get('phase_3_click_latency_ms') is not None:
                        accuracy = 1.0 if iter_data.get('phase_3_hit') else 0.0
                        history.append({
                            'accuracy': accuracy,
                            'latency_ms': iter_data.get('phase_3_click_latency_ms'),
                            'iteration': iter_num
                        })

                if len(history) < 2:
                    return {
                        'predicted_accuracy_pct': 50.0,
                        'anomaly_score': 0,
                        'confidence': 0.0
                    }

                # Train predictor
                predictor = MLPredictor(window_size=min(20, len(history)))
                if not predictor.train(history):
                    return {
                        'predicted_accuracy_pct': 50.0,
                        'anomaly_score': 0,
                        'confidence': 0.0
                    }

                # Get prediction
                predicted_accuracy = predictor.predict_next_accuracy() * 100
                confidence = predictor.get_prediction_confidence()

                # Score latest iteration
                scorer = AnomalyScorer(sensitivity=2.0)
                latest_iter = self.iterations.get(self.current_iteration, {})
                anomaly_score = scorer.score_iteration({
                    'accuracy': latest_iter.get('phase_3_hit', False),
                    'latency_ms': latest_iter.get('phase_3_click_latency_ms', 100),
                    'cpu_percent': latest_iter.get('cpu_avg', 50),
                    'ocr_confidence': latest_iter.get('phase_5_ocr_confidence', 0.95)
                })

                return {
                    'predicted_accuracy_pct': predicted_accuracy,
                    'anomaly_score': anomaly_score,
                    'confidence': confidence
                }

        except Exception as e:
            logger.error(f"Error getting predictions: {e}")
            return {
                'predicted_accuracy_pct': 50.0,
                'anomaly_score': 0,
                'confidence': 0.0
            }
