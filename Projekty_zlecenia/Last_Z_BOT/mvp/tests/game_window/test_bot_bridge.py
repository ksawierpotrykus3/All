from mvp.simulator.bot_bridge import BotBridge


def test_bridge_wraps_step_callback():
    calls = []

    def original(event, step_num, step, **kw):
        calls.append(("orig", event))

    class FakeSim:
        frame = "FRAME"
        def get_current_frame_raw(self):
            return self.frame

    sim = FakeSim()
    bridge = BotBridge(sim)
    bridge.attach_step_callback(original)

    bridge.on_step_event("success", 1, _FakeStep("SCROLL_LISTEN_CHAT"))
    assert ("orig", "success") in calls
    assert bridge.last_detection_mono is not None


def test_bridge_connect_and_metrics():
    class FakeSim:
        def __init__(self):
            self.connected_bot = None
            self.alert_start_time = 100.0

        def connect_to_bot(self, bot):
            self.connected_bot = bot

        def get_current_frame_raw(self):
            return None

    class FakeMetrics:
        def __init__(self):
            self.records = []

        def record_alert_metrics(self, iteration, hit, latency_ms, detection_ms):
            self.records.append((iteration, hit, latency_ms, detection_ms))

    class FakeCapture:
        def __init__(self):
            self.source = None

        def set_frame_source(self, src):
            self.source = src

    class FakeMacroEngine:
        def __init__(self):
            self.step_callback = None
            self.memory = {}

    class FakeBot:
        def __init__(self):
            self.capture = FakeCapture()
            self.macro_engine = FakeMacroEngine()

    sim = FakeSim()
    metrics = FakeMetrics()
    bridge = BotBridge(sim, metrics=metrics)
    bot = FakeBot()

    bridge.connect(bot)
    assert sim.connected_bot is bot
    assert bot.macro_engine.step_callback == bridge.on_step_event

    bridge.on_step_event("success", 1, _FakeStep("SCROLL_LISTEN_CHAT"))
    assert len(metrics.records) == 1
    assert metrics.records[0][0] == 1  # iteration
    assert metrics.records[0][1] is True  # hit


class _FakeStep:
    def __init__(self, type_name):
        self.type = _FakeType(type_name)


class _FakeType:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name
