"""Bot OLX - punkt startowy.

Uruchom: python -m bot
"""
import asyncio
import signal

from .comparator import Comparator
from .detector import Detector
from .logger import LOG_APP
from .notifier import Notifier
from .watchdog import Watchdog


async def _status_loop(detector, comparator):
    """Okresowa tabela wynikow w konsoli."""
    while not detector.stop.is_set():
        await asyncio.sleep(60)
        s = comparator.stats()
        LOG_APP.info(
            "=== STATUS === "
            f"skan={detector.scanned} head={detector.head} "
            f"trafienia={len(detector.hits)} (z_dziur={detector.holes_recovered}, w_kolejce_dziur={len(detector.pending_holes)}) "
            f"porownane={s['n']} miss={s['miss']} timeout={s['timeout']} "
            f"avg={s['avg']:.2f}min mediana={s['median']:.2f}min "
            f"max={s['max']:.2f}min"
        )


async def _main():
    LOG_APP.info("BOT OLX: start")

    notifier = Notifier()
    detector = Detector(notifier=notifier, watchdog=None)
    watchdog = Watchdog(notifier, stop_event=detector.stop)
    detector.watchdog = watchdog
    comparator = Comparator(detector)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, detector.stop.set)
        except (NotImplementedError, RuntimeError):
            pass  # Windows: SIGTERM/SIGBREAK nie zawsze dostępne

    if notifier.enabled:
        await notifier.send("🤖 BOT OLX: uruchomiony")

    await asyncio.gather(
        detector.run(),
        comparator.run(),
        watchdog.run(),
        _status_loop(detector, comparator),
    )


def main():
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        LOG_APP.info("BOT OLX: zatrzymany przez uzytkownika")


if __name__ == "__main__":
    main()