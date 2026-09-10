from mvp.simulator.sim_metrics import SimulationMetricsCollector


def test_record_alert_metrics():
    c = SimulationMetricsCollector(session_id="s1")
    c.record_alert_metrics(
        iteration=0,
        hit=True,
        latency_ms=120.0,
        detection_ms=80.0,
    )
    c.record_reliability(iteration=0, recovered=True)
    agg = c.aggregate()
    assert agg["iterations_total"] == 1
    assert agg["iterations_hit"] == 1
    assert agg["latency_avg_ms"] == 120.0
    assert agg["detection_avg_ms"] == 80.0
    assert agg["reliability_percent"] == 100.0


def test_export_empty(tmp_path):
    c = SimulationMetricsCollector(session_id="s2")
    path = c.export(tmp_path)
    assert path.exists()