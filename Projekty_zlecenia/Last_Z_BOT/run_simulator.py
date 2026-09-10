#!/usr/bin/env python3
"""Game Simulator Testing Framework — single entry point.

By default runs the simulator as an interactive game loop (no bot). Pass
`--bot` to start the real macro bot and have it drive the simulator through its
own clicks (frames are fed from the simulator, clicks replayed back).

Usage:
    uv run python run_simulator.py                        # interactive game loop
    uv run python run_simulator.py --bot                  # run the macro bot
    uv run python run_simulator.py --bot --variant default
"""

import argparse
import logging
import threading

from mvp.config import MVPConfig
from mvp.simulator.bot_bridge import BotBridge
from mvp.simulator.game import GameSimulator, SimulatorUI
from mvp.simulator.sim_metrics import SimulationMetricsCollector

logger = logging.getLogger(__name__)


def _run_bot(bot_runner) -> None:
    try:
        bot_runner.start()
    except Exception as exc:  # noqa: BLE001 - surface any startup error to the log
        logger.error("Bot failed to start: %s", exc, exc_info=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Game Simulator Testing Framework")
    parser.add_argument(
        "--variant", default="default",
        choices=["default", "hard_mode", "stress_test"],
    )
    parser.add_argument("--config", default=None, help="Path to a bot config JSON")
    parser.add_argument(
        "--bot", action="store_true",
        help="Start the macro bot loop (default: interactive game loop only)",
    )
    args = parser.parse_args()

    sim = GameSimulator()
    sim.apply_variant(args.variant)

    # Interactive mode has no bot pipeline, so there is nothing to measure; only
    # the --bot mode attaches the metrics collector (BotBridge records per
    # SCROLL/WATCH success). This avoids per-click metric writes corrupting the
    # per-iteration aggregates exported by the bridge.
    metrics = None
    if args.bot:
        metrics = SimulationMetricsCollector(session_id=sim.current_variant.get(
            "bot_config", "session"
        ))
        sim.metrics = metrics

    # The bot is created once the simulator window exists (so the title-based
    # window fallback can find it). These closures are wired into SimulatorUI.
    bot_runner_holder: dict = {}

    def start_bot() -> None:
        config = MVPConfig.load_or_default(args.config) if args.config else MVPConfig.default()
        # Simulator testing does not need anti-debug/spam-foreground hardening.
        config.preview_enabled = True
        config.anti_detect_enabled = False

        from mvp.bot.runner import BotRunner

        bot = BotRunner(config)
        bridge = BotBridge(sim, metrics=metrics)
        bridge.connect(bot)
        bot_runner_holder["bot"] = bot
        bot_runner_holder["bridge"] = bridge

        thread = threading.Thread(
            target=_run_bot, args=(bot,), daemon=True, name="simulator-bot"
        )
        thread.start()
        bot_runner_holder["thread"] = thread
        logger.info("Bot started and connected to simulator")

    def stop_bot() -> None:
        bot = bot_runner_holder.get("bot")
        if bot is not None:
            try:
                bot.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Bot shutdown error: %s", exc)

        # Export collected metrics on exit (bot mode only).
        if metrics is not None:
            try:
                from pathlib import Path

                metrics.export(Path("results"))
                logger.info("Metrics exported for session")
            except Exception as exc:  # noqa: BLE001
                logger.debug("Metrics export error: %s", exc)

    # Interactive game loop by default; only attach the bot hooks when --bot.
    on_start = start_bot if args.bot else None
    on_stop = stop_bot if args.bot else None

    ui = SimulatorUI(sim, on_start=on_start, on_stop=on_stop)
    ui.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
