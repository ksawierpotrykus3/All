"""Strażnik: alarmuje gdy bot przestaje dostawać 200 przez X sekund.

Użycie:
    watchdog = Watchdog(notifier)
    await watchdog.mark_success()  # przy każdym 200
    await watchdog.run()           # osobne zadanie w asyncio.gather
"""
import asyncio
import time

from . import config


class Watchdog:
    """Monitoruje czas od ostatniego sukcesu (HTTP 200)."""

    def __init__(self, notifier=None, threshold: float = None, stop_event=None):
        self.notifier = notifier
        self.threshold = threshold or config.WATCHDOG_THRESHOLD
        self.last_success = time.time()
        self._fired = False
        self.stop = asyncio.Event()
        self.stop_event = stop_event

    def mark_success(self):
        """Wywołuj przy każdym 200. Resetuje licznik i alarm."""
        self.last_success = time.time()
        self._fired = False

    async def run(self):
        """Pętla sprawdzająca co 30 s, czy bot żyje."""
        while not self.stop.is_set() and not (
            self.stop_event and self.stop_event.is_set()
        ):
            await asyncio.sleep(30)
            idle = time.time() - self.last_success
            if idle > self.threshold and not self._fired:
                self._fired = True  # nie spamuj alarmem
                if self.notifier:
                    await self.notifier.critical(
                        f"WATCHDOG: brak 200 od {idle:.0f}s — bot prawdopodobnie martwy"
                    )