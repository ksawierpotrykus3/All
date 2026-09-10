"""Komparator: nasza detekcja vs wyszukiwarka, z liczeniem minut przewagi."""

import asyncio
import time

from . import config, http_client
from .logger import LOG_APP, LOG_COMPARE


class Comparator:
    """Rzadziej pyta wyszukiwarke i liczy przewage dla wykrytych ofert."""

    def __init__(self, detector):
        self.detector = detector
        self.stop = asyncio.Event()
        # id -> czas wejscia do wyszukiwarki
        self.browser_times = {}
        # id -> (przewaga_min, label)
        self.results = {}
        # id -> czas wykrycia (do liczenia TTL)
        self._detect_times = {}

    async def _poll(self, hit):
        """Sprawdz, czy hit juz jest w wyszukiwarce (top wynikow)."""
        cat_id = hit["category_id"]
        query = hit["search"] or hit["query"]
        for offset in config.COMPARE_OFFSETS:
            ids = await http_client.search(query, cat_id, offset=offset)
            if hit["id"] in ids:
                return True
        # Sprawdz takze ogolna liste najnowszych w kategorii
        if cat_id:
            ids = await http_client.search("", cat_id, offset=0)
            if hit["id"] in ids:
                return True
        return False


    async def run(self):
        LOG_APP.info(
            f"KOMPARATOR: start, interwal={config.COMPARE_INTERVAL}s"
        )
        while not self.stop.is_set() and not self.detector.stop.is_set():
            hits = self.detector.get_hits()
            pending = {
                oid: hit
                for oid, hit in hits.items()
                if oid not in self.browser_times and oid not in self.results
            }
            now_ts = time.time()
            for oid, hit in pending.items():
                # TTL: po COMPARE_TTL s uznaj, ze oferta nie weszla do wyszukiwarki.
                if oid in self._detect_times:
                    if now_ts - self._detect_times[oid] > config.COMPARE_TTL:
                        self.results[oid] = (None, hit["label"])
                        LOG_COMPARE.info(
                            f"id={hit['id']} [{hit['label']}] "
                            f"nie pojawilo sie w wyszukiwarce przez "
                            f"{config.COMPARE_TTL // 60} min"
                        )
                        continue
                else:
                    self._detect_times[oid] = hit["t_detect"]
                try:
                    found = await self._poll(hit)
                except Exception as e:  # noqa: BLE001
                    LOG_APP.error(f"KOMPARATOR: blad poll id={oid}: {e}")
                    continue
                if found:
                    now = time.time()
                    self.browser_times[oid] = now
                    delta_min = (now - hit["t_detect"]) / 60.0
                    self.results[oid] = (delta_min, hit["label"])
                    if delta_min > 0:
                        LOG_COMPARE.info(
                            f"id={hit['id']} [{hit['label']}] "
                            f"detect={time.strftime('%H:%M:%S', time.localtime(hit['t_detect']))} "
                            f"browser={time.strftime('%H:%M:%S', time.localtime(now))} "
                            f"przewaga=+{delta_min:.2f} min"
                        )
                    else:
                        LOG_COMPARE.info(
                            f"id={hit['id']} [{hit['label']}] "
                            f"przewaga={delta_min:.2f} min (miss)"
                        )
            await asyncio.sleep(config.COMPARE_INTERVAL)
        LOG_APP.info("KOMPARATOR: koniec")

    def stats(self):
        """Statystyki przewag."""
        vals = [v[0] for v in self.results.values() if v[0] is not None and v[0] > 0]
        miss = sum(1 for v in self.results.values() if v[0] is not None and v[0] <= 0)
        timeout = sum(1 for v in self.results.values() if v[0] is None)
        if not vals:
            return {
                "n": 0, "miss": miss, "timeout": timeout,
                "avg": 0.0, "median": 0.0, "max": 0.0,
            }
        vals.sort()
        n = len(vals)
        median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        return {
            "n": n,
            "miss": miss,
            "timeout": timeout,
            "avg": sum(vals) / n,
            "median": median,
            "max": vals[-1],
        }