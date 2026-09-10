from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from mvp.bot.capture import setup_dpi_awareness
from mvp.bot.monitor_mapper import validate_environment
from mvp.bot.runner import BotRunner
from mvp.bot.window_finder import find_game_window
from mvp.config import MVPConfig
from mvp.gui.main_window import MainWindow
from mvp.gui.state import GuiState
from mvp.logger import setup_dev_logging
from mvp.logging_setup import setup_logging

logger = logging.getLogger("mvp.main")

CONFIG_PATH = Path("config.json")

# PHASE 10: Structured initialization logging to JSON
class InitializationLogger:
    """Logs application initialization events to structured JSON."""

    def __init__(self, log_path: Path = None):
        if log_path is None:
            log_path = Path("runtime_init.json")
        self.log_path = Path(log_path)
        self.entries = []

    def log(self, level: str, message: str, **context) -> None:
        """Log an initialization event."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
        }
        # Flatten context into entry
        if context:
            entry.update(context)

        self.entries.append(entry)

        # Optionally also log to logger
        getattr(logger, level.lower(), logger.info)(message)

    def save(self) -> None:
        """Save all entries to JSON file."""
        try:
            # Create parent directory if needed
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

            self.log_path.write_text(
                "\n".join(json.dumps(e) for e in self.entries), encoding="utf-8"
            )
            logger.info(f"Initialization log saved: {self.log_path}")
        except Exception as e:
            logger.error(f"Failed to save initialization log: {e}")

    def info(self, message: str, **context) -> None:
        self.log("INFO", message, **context)

    def warn(self, message: str, **context) -> None:
        self.log("WARNING", message, **context)

    def error(self, message: str, **context) -> None:
        self.log("ERROR", message, **context)


def _resolve_app_dir() -> Path:
    nuitka_dir = globals().get("__nuitka_binary_dir")
    if nuitka_dir:
        return Path(nuitka_dir)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()




def _detect_ocr_engine() -> dict:
    """Detect available Fast OCR engines (WinOCR / RapidOCR)."""
    engines = []
    rapidocr = False
    winocr = False

    # CRITICAL Windows import order (see AGENTS.md): onnxruntime MUST be loaded
    # before any winrt module, otherwise onnxruntime_pybind11_state DLL init
    # collides with the COM/WinRT multithreaded init.
    try:
        import rapidocr_onnxruntime

        rapidocr = True
        engines.append(
            "RapidOCR ONNX v" + getattr(rapidocr_onnxruntime, "__version__", "?")
        )
    except Exception:
        pass

    try:
        from winrt.windows.media.ocr import OcrEngine

        langs = [lang.language_tag for lang in OcrEngine.available_recognizer_languages]
        if langs:
            winocr = True
            engines.append(f"WinOCR ({', '.join(langs)})")
    except Exception:
        pass

    return {
        "status": "found" if engines else "not_found",
        "engines": engines,
        "winocr": winocr,
        "rapidocr": rapidocr,
    }


def main() -> None:
    # Initialize logging BEFORE any other code
    setup_dev_logging()

    # PHASE 10.1: Initialize structured logging
    init_logger = InitializationLogger()
    init_logger.info("Application startup started")

    with contextlib.suppress(OSError):
        os.chdir(_resolve_app_dir())

    setup_logging(debug="--debug" in sys.argv)
    init_logger.info(f"Working directory: {os.getcwd()}")

    logger.info("Starting LastZBot...")
    init_logger.info("Logging setup complete")

    try:
        setup_dpi_awareness()
        init_logger.info("DPI awareness setup complete")
    except OSError as exc:
        logger.warning("DPI awareness already set or unavailable: %s", exc)
        init_logger.warn("DPI awareness setup warning", error=str(exc))

    # Load configuration
    init_logger.info(f"Loading config from: {CONFIG_PATH.resolve()}")
    config = MVPConfig.load_or_default(CONFIG_PATH)
    valid, errors = config.validate()
    if not valid:
        logger.warning("Config validation errors: %s", errors)
        init_logger.warn("Config validation errors", errors=errors)
    init_logger.info("Config loaded and validated", process_name=config.process_name)

    # PHASE 10.2: Detect external dependencies
    logger.info("Detecting Fast OCR engines...")
    ocr_status = _detect_ocr_engine()
    if ocr_status["status"] == "found":
        init_logger.info(
            "Fast OCR engines detected",
            engines=ocr_status["engines"],
        )

    # Zbieramy wszystkie ostrzeżenia (OCR + środowisko), aby pokazać je w GUI.
    all_warnings: list[str] = []

    if not ocr_status["winocr"] and not ocr_status["rapidocr"]:
        msg = "OCR niedostępny, makro nie zadziała"
        logger.warning(msg)
        init_logger.warn(msg)
        all_warnings.append(msg)
    elif not ocr_status["winocr"] and ocr_status["rapidocr"]:
        msg = "Wolniejszy OCR (brak WinOCR). Upewnij się, że Windows ma pakiet językowy OCR."
        logger.warning(msg)
        init_logger.warn(msg)
        all_warnings.append(msg)

    # Search for game window
    logger.info("Searching for game window '%s'...", config.process_name)
    init_logger.info(f"Searching for game window: {config.process_name}")
    window_info = find_game_window(config.process_name)
    if window_info is not None:
        logger.info(
            "Found game window: '%s' (%dx%d)",
            window_info.title,
            window_info.width,
            window_info.height,
        )
        init_logger.info(
            "Game window found",
            title=window_info.title,
            width=window_info.width,
            height=window_info.height,
        )
    else:
        logger.warning("Game window not found. Start the game before running the bot.")
        init_logger.warn("Game window not found")

    # Validate monitor/window environment (multi-monitor, DPI, aspect ratio).
    # DPI i liczba monitorów istnieją niezależnie od tego, czy gra jest włączona,
    # więc walidujemy zawsze — nawet gdy gra nie została jeszcze uruchomiona.
    env_warnings = validate_environment(
        window_info.width if window_info is not None else 0,
        window_info.height if window_info is not None else 0,
    )
    for warn in env_warnings:
        logger.warning("Środowisko: %s", warn)
        init_logger.warn("Środowisko", warning=warn)
    all_warnings.extend(env_warnings)

    # Initialize bot and GUI
    state = GuiState()
    bot_runner = BotRunner(config, frame_queue=state.frame_queue)
    init_logger.info("Bot runner initialized")

    bot_runner.start_window_monitor()
    init_logger.info("Window monitor started")

    bot_runner.prewarm_ocr()
    init_logger.info("OCR prewarmed")

    gui = MainWindow(config, state, bot_runner, window_info)
    gui.setup()
    init_logger.info("GUI setup complete")

    if all_warnings:
        gui.set_env_warnings(all_warnings)

    if window_info is not None:
        gui.set_game_status(True, f"{window_info.width}x{window_info.height}")

    init_logger.info("Application startup complete")

    try:
        gui.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        init_logger.info("Shutdown triggered by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        init_logger.error(f"Application error: {e}", error_type=type(e).__name__)
    finally:
        gui.shutdown()
        # Save initialization log before exiting
        init_logger.save()
        sys.exit(0)



if __name__ == "__main__":
    main()
