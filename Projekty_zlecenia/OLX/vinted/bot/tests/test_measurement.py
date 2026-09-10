from vintedbot.measurement import LatencyRecorder, StepTimings


def test_latency_recorder_liczy_percentyle():
    r = LatencyRecorder()
    for v in [1.0, 2.0, 3.0, 4.0, 100.0]:
        r.add(v)
    assert r.count == 5
    assert r.p50 == 3.0
    assert r.p95 == 100.0
    assert r.p99 == 100.0


def test_latency_recorder_pusty():
    r = LatencyRecorder()
    assert r.count == 0
    assert r.p50 == 0.0


def test_step_timings_suma():
    st = StepTimings()
    st["a"] = 10.0
    st["b"] = 20.0
    assert st.suma == 30.0


def test_raport_do_dict_ma_pola():
    r = LatencyRecorder()
    r.add(2.0)
    d = r.to_dict()
    assert set(d) == {"count", "errors", "p50", "p95", "p99", "avg"}