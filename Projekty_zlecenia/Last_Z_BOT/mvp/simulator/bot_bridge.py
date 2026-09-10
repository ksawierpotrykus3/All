import time

from mvp.bot.window_finder import find_game_window


class BotBridge:
    """Connects the simulator to the bot and drives it with real bot clicks.

    The simulator is a deterministic state machine. Transitions are triggered by
    the bot's own clicks (click_at) rather than by frame-queue heuristics, so the
    macro loop replays exactly: no_chat -> chat -> alert -> helka -> reset.
    """

    def __init__(self, simulator, metrics=None) -> None:
        self._simulator = simulator
        self._metrics = metrics
        self._original_callback = None
        self._original_click_at = None
        self.last_detection_mono = None
        self.current_iteration = 0

    def attach_step_callback(self, original_callback) -> None:
        self._original_callback = original_callback

    def on_step_event(self, event, step_num, step, **kwargs) -> None:
        if self._original_callback is not None:
            self._original_callback(event, step_num, step, **kwargs)

        step_type = str(getattr(step, "type", "")).split(".")[-1]

        if step_type == "SCROLL_LISTEN_CHAT" and event == "success":
            self.last_detection_mono = time.monotonic()
            self.current_iteration += 1

            # Give the simulator the OCR-detected alert position so its "alert"
            # state verifies the bot's Step-2 click lands on the alert.
            engine = getattr(self, "_engine", None)
            if engine is not None:
                gx = engine.memory.get("step_1_click_x")
                gy = engine.memory.get("step_1_click_y")
                if gx is not None and gy is not None:
                    self._simulator.expected_chat_click_pct = (float(gx), float(gy))

            if self._metrics is not None:
                det_ms = 0.0
                if getattr(self._simulator, "alert_start_time", None):
                    det_ms = max(
                        0.0, (time.time() - self._simulator.alert_start_time) * 1000.0
                    )
                self._metrics.record_alert_metrics(
                    iteration=self.current_iteration,
                    hit=True,
                    latency_ms=det_ms,
                    detection_ms=det_ms,
                )

        if step_type == "WATCH_TIMER" and event == "success":
            if self._metrics is not None:
                self._metrics.record_reliability(
                    iteration=self.current_iteration, recovered=True
                )
            if hasattr(self._simulator, "reset_to_chat"):
                self._simulator.reset_to_chat()

    def connect(self, bot_runner) -> None:
        # In bot mode the alert transition requires a click on the exact
        # OCR-detected position (verified against Step-2's click target).
        if hasattr(self._simulator, "strict_alert_hit"):
            self._simulator.strict_alert_hit = True

        if hasattr(self._simulator, "connect_to_bot"):
            self._simulator.connect_to_bot(bot_runner)
        elif getattr(bot_runner, "capture", None) is not None:
            bot_runner.capture.set_frame_source(self._simulator.get_current_frame_raw)

        engine = getattr(bot_runner, "macro_engine", None)
        if engine is not None:
            self._engine = engine
            self.attach_step_callback(engine.step_callback)
            engine.step_callback = self.on_step_event

        # Hook the clicker so every macro click is replayed into the simulator.
        clicker = getattr(bot_runner, "clicker", None)
        if clicker is not None:
            self._hook_clicker(clicker, process_name=getattr(bot_runner.config, "process_name", "Survival.exe"))

    def _hook_clicker(self, clicker, process_name: str) -> None:
        original = clicker.click_at
        self._original_click_at = original
        simulator = self._simulator

        def hooked_click_at(x, y, times=1):
            # Map screen coords (bot's SendInput target) back to simulator frame
            # coords using the simulator window's client origin.
            info = find_game_window(process_name)
            if info is not None:
                fx = int(x) - info.left
                fy = int(y) - info.top
                if hasattr(simulator, "handle_click"):
                    simulator.handle_click(fx, fy)
            return original(x, y, times)

        clicker.click_at = hooked_click_at