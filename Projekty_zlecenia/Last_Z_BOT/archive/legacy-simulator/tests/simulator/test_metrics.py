# tests/simulator/test_metrics.py
"""
Unit tests for MetricsCollector: per-iteration metrics collection and aggregation.

Tests:
- Initialization with session ID
- start_iteration, record_phase, end_iteration workflow
- Phase recording for all 6 phases
- Aggregation calculations (accuracy, latency stats, reliability)
- Edge cases (empty iterations, single iteration, no hits)
"""

import pytest
import statistics
from typing import Dict, Any

from mvp.simulator.metrics import MetricsCollector


class TestMetricsCollectorInit:
    """Test MetricsCollector initialization."""

    def test_init_with_session_id(self):
        """MetricsCollector should initialize with provided session_id."""
        mc = MetricsCollector(session_id='test_session_1')
        assert mc.session_id == 'test_session_1'
        assert mc.iterations == {}
        assert mc.current_iteration == -1

    def test_init_generates_default_session_id(self):
        """MetricsCollector should generate session_id if not provided."""
        mc = MetricsCollector()
        assert mc.session_id is not None
        assert len(mc.session_id) > 0


class TestStartIteration:
    """Test iteration initialization."""

    def test_start_iteration_basic(self):
        """start_iteration should initialize iteration metrics."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='clean_30cps')

        assert mc.current_iteration == 1
        assert 1 in mc.iterations
        assert mc.iterations[1]['iteration'] == 1
        assert mc.iterations[1]['variant'] == 'clean_30cps'

    def test_start_iteration_without_variant(self):
        """start_iteration should handle None variant."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant=None)

        assert mc.current_iteration == 1
        assert mc.iterations[1]['variant'] is None

    def test_start_multiple_iterations(self):
        """MetricsCollector should track multiple iterations."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='var1')
        mc.start_iteration(iteration=2, variant='var2')
        mc.start_iteration(iteration=3, variant='var3')

        assert mc.current_iteration == 3
        assert len(mc.iterations) == 3
        assert mc.iterations[1]['variant'] == 'var1'
        assert mc.iterations[2]['variant'] == 'var2'
        assert mc.iterations[3]['variant'] == 'var3'


class TestRecordPhase:
    """Test phase metric recording."""

    def test_record_phase_setup(self):
        """record_phase should record setup metrics."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.record_phase('setup', setup_ms=98)

        assert mc.iterations[1]['phase_1_setup_ms'] == 98

    def test_record_phase_alert_detection(self):
        """record_phase should record alert detection metrics."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.record_phase('alert_detection', detection_ms=145, ocr_confidence=0.92)

        assert mc.iterations[1]['phase_2_alert_detection_ms'] == 145
        assert mc.iterations[1]['phase_2_ocr_confidence'] == 0.92

    def test_record_phase_click_latency(self):
        """record_phase should record click metrics."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.record_phase('click_latency', latency_ms=78, hit=True)

        assert mc.iterations[1]['phase_3_click_latency_ms'] == 78
        assert mc.iterations[1]['phase_3_hit'] is True

    def test_record_phase_cpu_spike(self):
        """record_phase should record treasure phase CPU spike."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.record_phase('cpu_spike', cpu_spike_percent=45)

        assert mc.iterations[1]['phase_4_cpu_spike_percent'] == 45

    def test_record_phase_chat_recovery(self):
        """record_phase should record chat recovery metrics."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.record_phase(
            'chat_recovery',
            recovery_ms=890,
            ocr_confidence=0.87,
            state_verified=True,
        )

        assert mc.iterations[1]['phase_5_chat_recovery_ms'] == 890
        assert mc.iterations[1]['phase_5_ocr_confidence'] == 0.87
        assert mc.iterations[1]['phase_5_state_verified'] is True

    def test_record_phase_multiple_in_sequence(self):
        """record_phase should handle multiple phase recordings in sequence."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')

        mc.record_phase('setup', setup_ms=100)
        mc.record_phase('alert_detection', detection_ms=150, ocr_confidence=0.90)
        mc.record_phase('click_latency', latency_ms=80, hit=True)
        mc.record_phase('cpu_spike', cpu_spike_percent=50)
        mc.record_phase(
            'chat_recovery',
            recovery_ms=900,
            ocr_confidence=0.88,
            state_verified=True,
        )

        iter_data = mc.iterations[1]
        assert iter_data['phase_1_setup_ms'] == 100
        assert iter_data['phase_2_alert_detection_ms'] == 150
        assert iter_data['phase_3_click_latency_ms'] == 80
        assert iter_data['phase_4_cpu_spike_percent'] == 50
        assert iter_data['phase_5_chat_recovery_ms'] == 900

    def test_record_phase_partial_data(self):
        """record_phase should handle partial phase data gracefully."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.record_phase('click_latency', latency_ms=75)  # Only latency, no hit

        assert mc.iterations[1]['phase_3_click_latency_ms'] == 75
        assert mc.iterations[1]['phase_3_hit'] is None


class TestEndIteration:
    """Test iteration completion."""

    def test_end_iteration_records_totals(self):
        """end_iteration should record total duration and resource metrics."""
        mc = MetricsCollector(session_id='test')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.end_iteration(total_ms=1356, cpu_avg=42, ram_mb=256)

        assert mc.iterations[1]['total_iteration_ms'] == 1356
        assert mc.iterations[1]['cpu_avg'] == 42
        assert mc.iterations[1]['ram_mb'] == 256

    def test_end_iteration_multiple_iterations(self):
        """end_iteration should correctly finalize multiple iterations."""
        mc = MetricsCollector(session_id='test')

        mc.start_iteration(iteration=1, variant='var1')
        mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        mc.start_iteration(iteration=2, variant='var2')
        mc.end_iteration(total_ms=1200, cpu_avg=45, ram_mb=260)

        assert mc.iterations[1]['total_iteration_ms'] == 1000
        assert mc.iterations[2]['total_iteration_ms'] == 1200


class TestAggregate:
    """Test aggregation calculations."""

    def test_aggregate_accuracy_all_hits(self):
        """aggregate should calculate 100% accuracy when all clicks hit."""
        mc = MetricsCollector(session_id='test')

        for i in range(5):
            mc.start_iteration(iteration=i, variant='test')
            mc.record_phase('click_latency', latency_ms=80, hit=True)
            mc.record_phase('chat_recovery', state_verified=True)
            mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['accuracy_percent'] == 100.0
        assert agg['iterations_hit'] == 5
        assert agg['iterations_total'] == 5

    def test_aggregate_accuracy_partial_hits(self):
        """aggregate should calculate partial accuracy correctly."""
        mc = MetricsCollector(session_id='test')

        for i in range(5):
            mc.start_iteration(iteration=i, variant='test')
            hit = (i < 4)  # First 4 hit, last one misses
            mc.record_phase('click_latency', latency_ms=80, hit=hit)
            mc.record_phase('chat_recovery', state_verified=True)
            mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['accuracy_percent'] == 80.0  # 4/5 = 80%
        assert agg['iterations_hit'] == 4

    def test_aggregate_accuracy_no_hits(self):
        """aggregate should handle 0% accuracy."""
        mc = MetricsCollector(session_id='test')

        for i in range(3):
            mc.start_iteration(iteration=i, variant='test')
            mc.record_phase('click_latency', latency_ms=80, hit=False)
            mc.record_phase('chat_recovery', state_verified=True)
            mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['accuracy_percent'] == 0.0
        assert agg['iterations_hit'] == 0

    def test_aggregate_latency_stats(self):
        """aggregate should calculate latency statistics correctly."""
        mc = MetricsCollector(session_id='test')

        latencies = [80, 85, 90, 95, 100]  # 5 latencies
        for i, lat in enumerate(latencies):
            mc.start_iteration(iteration=i, variant='test')
            mc.record_phase('click_latency', latency_ms=lat, hit=True)
            mc.record_phase('chat_recovery', state_verified=True)
            mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['latency_avg_ms'] == pytest.approx(90.0, rel=1e-2)
        assert agg['latency_std_ms'] == pytest.approx(
            statistics.stdev(latencies), rel=1e-2
        )
        # P95 of [80, 85, 90, 95, 100] ≈ 95.6
        assert agg['latency_p95_ms'] >= 95
        # P99 of [80, 85, 90, 95, 100] ≈ 99.4
        assert agg['latency_p99_ms'] >= 95

    def test_aggregate_latency_single_value(self):
        """aggregate should handle single latency (std=0)."""
        mc = MetricsCollector(session_id='test')

        mc.start_iteration(iteration=0, variant='test')
        mc.record_phase('click_latency', latency_ms=100, hit=True)
        mc.record_phase('chat_recovery', state_verified=True)
        mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['latency_avg_ms'] == 100.0
        assert agg['latency_std_ms'] == 0.0
        assert agg['latency_p95_ms'] == 100.0

    def test_aggregate_chat_recovery_failures(self):
        """aggregate should count chat recovery failures."""
        mc = MetricsCollector(session_id='test')

        # 5 iterations: 3 successful, 2 failures
        for i in range(5):
            mc.start_iteration(iteration=i, variant='test')
            mc.record_phase('click_latency', latency_ms=80, hit=True)
            state_verified = (i < 3)  # First 3 succeed
            mc.record_phase('chat_recovery', state_verified=state_verified)
            mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['chat_recovery_failures'] == 2
        assert agg['reliability_percent'] == 60.0  # 3/5 = 60%

    def test_aggregate_reliability_all_successful(self):
        """aggregate should show 100% reliability when all recover successfully."""
        mc = MetricsCollector(session_id='test')

        for i in range(5):
            mc.start_iteration(iteration=i, variant='test')
            mc.record_phase('click_latency', latency_ms=80, hit=True)
            mc.record_phase('chat_recovery', state_verified=True)
            mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['chat_recovery_failures'] == 0
        assert agg['reliability_percent'] == 100.0

    def test_aggregate_empty_collector(self):
        """aggregate should handle empty MetricsCollector gracefully."""
        mc = MetricsCollector(session_id='test')
        agg = mc.aggregate()

        assert agg['iterations_total'] == 0
        assert agg['iterations_hit'] == 0
        assert agg['accuracy_percent'] == 0.0
        assert agg['latency_avg_ms'] is None
        assert agg['latency_std_ms'] is None
        assert agg['chat_recovery_failures'] == 0
        assert agg['reliability_percent'] == 0.0

    def test_aggregate_includes_session_info(self):
        """aggregate should include session metadata."""
        mc = MetricsCollector(session_id='my_session')
        mc.start_iteration(iteration=1, variant='test_var')
        mc.record_phase('click_latency', latency_ms=80, hit=True)
        mc.record_phase('chat_recovery', state_verified=True)
        mc.end_iteration(total_ms=1000, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()
        assert agg['session_id'] == 'my_session'
        assert 'iterations_total' in agg
        assert 'accuracy_percent' in agg

    def test_aggregate_complex_scenario(self):
        """aggregate should correctly process complex multi-iteration scenario."""
        mc = MetricsCollector(session_id='complex_test')

        # Iteration 1: hit, recovered
        mc.start_iteration(iteration=1, variant='clean_30cps')
        mc.record_phase('setup', setup_ms=100)
        mc.record_phase('alert_detection', detection_ms=150, ocr_confidence=0.92)
        mc.record_phase('click_latency', latency_ms=80, hit=True)
        mc.record_phase('cpu_spike', cpu_spike_percent=45)
        mc.record_phase(
            'chat_recovery',
            recovery_ms=900,
            ocr_confidence=0.88,
            state_verified=True,
        )
        mc.end_iteration(total_ms=1356, cpu_avg=42, ram_mb=256)

        # Iteration 2: miss, recovered
        mc.start_iteration(iteration=2, variant='clean_30cps')
        mc.record_phase('setup', setup_ms=102)
        mc.record_phase('alert_detection', detection_ms=155, ocr_confidence=0.90)
        mc.record_phase('click_latency', latency_ms=120, hit=False)
        mc.record_phase('cpu_spike', cpu_spike_percent=42)
        mc.record_phase(
            'chat_recovery',
            recovery_ms=950,
            ocr_confidence=0.85,
            state_verified=True,
        )
        mc.end_iteration(total_ms=1400, cpu_avg=43, ram_mb=258)

        # Iteration 3: hit, recovery failure
        mc.start_iteration(iteration=3, variant='cluttered_38cps')
        mc.record_phase('setup', setup_ms=98)
        mc.record_phase('alert_detection', detection_ms=145, ocr_confidence=0.85)
        mc.record_phase('click_latency', latency_ms=75, hit=True)
        mc.record_phase('cpu_spike', cpu_spike_percent=50)
        mc.record_phase(
            'chat_recovery',
            recovery_ms=1200,
            ocr_confidence=0.70,
            state_verified=False,
        )
        mc.end_iteration(total_ms=1410, cpu_avg=48, ram_mb=270)

        agg = mc.aggregate()

        # Accuracy: 2/3 = 66.67%
        assert agg['accuracy_percent'] == pytest.approx(66.67, abs=0.1)
        assert agg['iterations_hit'] == 2

        # Latency: [80, 120, 75], avg=91.67, std≈22.67
        assert agg['latency_avg_ms'] == pytest.approx(91.67, abs=1)
        assert agg['latency_std_ms'] > 0

        # Chat recovery: 1 failure
        assert agg['chat_recovery_failures'] == 1
        assert agg['reliability_percent'] == pytest.approx(66.67, abs=0.1)

    def test_aggregate_returns_dict(self):
        """aggregate should always return a dictionary."""
        mc = MetricsCollector(session_id='test')
        agg = mc.aggregate()
        assert isinstance(agg, dict)


class TestMetricsCollectorIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow_single_iteration(self):
        """Full workflow: init → start → record phases → end → aggregate."""
        mc = MetricsCollector(session_id='workflow_test')

        mc.start_iteration(iteration=1, variant='test_variant')
        mc.record_phase('setup', setup_ms=100)
        mc.record_phase('alert_detection', detection_ms=150, ocr_confidence=0.92)
        mc.record_phase('click_latency', latency_ms=85, hit=True)
        mc.record_phase('cpu_spike', cpu_spike_percent=45)
        mc.record_phase(
            'chat_recovery',
            recovery_ms=900,
            ocr_confidence=0.88,
            state_verified=True,
        )
        mc.end_iteration(total_ms=1356, cpu_avg=42, ram_mb=256)

        agg = mc.aggregate()

        assert agg['session_id'] == 'workflow_test'
        assert agg['iterations_total'] == 1
        assert agg['accuracy_percent'] == 100.0
        assert agg['latency_avg_ms'] == 85.0
        assert agg['reliability_percent'] == 100.0

    def test_full_workflow_multiple_variants(self):
        """Full workflow with multiple variants."""
        mc = MetricsCollector(session_id='multi_variant_test')

        variants = ['clean_30cps', 'cluttered_38cps', 'spam_high_load']

        for iter_num, variant in enumerate(variants):
            mc.start_iteration(iteration=iter_num, variant=variant)
            mc.record_phase(
                'click_latency', latency_ms=80 + iter_num * 5, hit=(iter_num < 2)
            )
            mc.record_phase(
                'chat_recovery',
                state_verified=(iter_num < 2),
            )
            mc.end_iteration(total_ms=1000 + iter_num * 100, cpu_avg=40, ram_mb=250)

        agg = mc.aggregate()

        assert agg['iterations_total'] == 3
        assert agg['iterations_hit'] == 2
        assert agg['accuracy_percent'] == pytest.approx(66.67, abs=0.1)
