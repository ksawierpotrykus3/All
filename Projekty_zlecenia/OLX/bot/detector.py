"""Detektor: przewidywanie ID + sliding window + bufor wsteczny (Zero-Miss).

Odporny na 24/7:
  - 403 (ERR_BANNED) -> alarm + stop
  - 429 (ERR_RATELIMIT) -> czeka (obsłużone w http_client)
  - trafienia zapisywane do logs/hits.json (persystencja)
  - pending_holes ma twardy sufit (MAX_PENDING_HOLES)
  - watchdog.mark_success() przy każdym 200
"""
import asyncio
import json
import time

from . import classifier, config, http_client
from .logger import LOG_APP, LOG_DETECT


def extract(offer, label):
    """Zbuduj slownik hitu z oferty."""
    price = None
    for p in offer.get("params", []) or []:
        if p.get("key") == "price":
            price = p.get("value", {}).get("value")
    return {
        "id": offer.get("id"),
        "title": offer.get("title"),
        "label": label,
        "price": classifier.parse_price(price),
        "region": (offer.get("location") or {}).get("region", {}).get("name", ""),
        "created": offer.get("created_time"),
        "url": offer.get("url"),
        "category_id": (offer.get("category") or {}).get("id"),
    }


class Detector:
    """Skanuje przewidywane ID w 2 warstwach: Czołówka + Zamiatacz dziur."""

    def __init__(self, notifier=None, watchdog=None):
        self.notifier = notifier
        self.watchdog = watchdog
        self.hits = self._load_hits()
        self.lock = asyncio.Lock()
        self.stop = asyncio.Event()
        self.scanned = 0
        self.head = 0
        # oid -> {'first_seen': float, 'attempts': int, 'next_retry': float}
        self.pending_holes = {}
        self.holes_recovered = 0
        self.holes_expired = 0
        self._last_save = time.time()

    # --- Persystencja trafień ---

    def _load_hits(self):
        try:
            with open(config.HITS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # klucze były intami, JSON je zamienia na stringi
                    return {int(k): v for k, v in data.items()}
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            pass
        return {}

    def _save_hits(self):
        try:
            with open(config.HITS_FILE, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in self.hits.items()}, f, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            LOG_APP.error(f"DETEKTOR: nie udało się zapisać hits: {e}")

    async def _maybe_save_hits(self):
        now = time.time()
        if now - self._last_save >= config.HITS_SAVE_INTERVAL:
            self._last_save = now
            await asyncio.to_thread(self._save_hits)

    # --- Przetwarzanie oferty ---

    async def _process_offer(self, oid, data, source_tag="FRONTIER"):
        """Klasyfikuj i rejestruj hit jesli pasuje."""
        if not data:
            return
        res = classifier.classify(data)
        if res:
            query, label = res
            hit = extract(data, label)
            hit["query"] = query
            hit["search"] = classifier.search_phrase(hit["title"])
            hit["t_detect"] = time.time()
            hit["source"] = source_tag
            async with self.lock:
                if oid in self.hits:
                    return
                self.hits[oid] = hit
            LOG_DETECT.info(
                f"TRAFIENIE [{source_tag}] id={hit['id']} [{hit['label']}] "
                f"cena={hit['price']} region={hit['region']} "
                f"tytul={hit['title']} created={hit['created']}"
            )
            if self.notifier:
                await self.notifier.hit(hit)

    # --- Limity kolejek ---

    def _add_hole(self, oid, first_seen, next_retry):
        """Dodaj dziurę z twardym sufitem kolejki."""
        if oid in self.hits:
            return
        if len(self.pending_holes) >= config.MAX_PENDING_HOLES:
            oldest = min(self.pending_holes, key=lambda o: self.pending_holes[o]["first_seen"])
            self.pending_holes.pop(oldest, None)
            self.holes_expired += 1
        self.pending_holes[oid] = {
            "first_seen": first_seen,
            "attempts": 0,
            "next_retry": next_retry,
        }

    # --- Fazy skanowania ---

    async def _scan_phase(self, head, batch_size, timeout):
        """Skanuje do krawedzi (same 404) albo do timeout."""
        scanned = 0
        while time.time() < timeout and not self.stop.is_set():
            codes = await http_client.scan_batch(
                head, batch_size, config.CONCURRENCY
            )
            max_seen = None
            any_200 = False
            saw_banned = False
            for oid, (code, data) in sorted(codes.items()):
                scanned += 1
                if code == 200:
                    any_200 = True
                    if self.watchdog:
                        self.watchdog.mark_success()
                    if max_seen is None or oid > max_seen:
                        max_seen = oid
                elif code == config.ERR_BANNED:
                    saw_banned = True
            if saw_banned:
                await self._on_banned()
                break
            if max_seen is not None:
                head = max_seen + 1
            if not any_200:
                break
        return head, scanned

    async def _on_banned(self):
        """Zatrzymaj bota i zaalarmuj przy 403."""
        LOG_APP.error("DETEKTOR: BAN IP (403) — zatrzymuję")
        if self.notifier:
            await self.notifier.critical("BAN IP: 403 na olx.pl — bot zatrzymany")
        self.stop.set()

    async def _frontier_loop(self):
        """Czołówka: skanuje krawędź najnowszych ID i rejestruje dziury."""
        LOG_APP.info("DETEKTOR: start czołówki (Frontier)")
        while not self.stop.is_set():
            codes = await http_client.scan_batch(
                self.head, config.BATCH_SIZE, config.CONCURRENCY
            )
            max_seen = None
            saw_net_err = False
            saw_banned = False
            saw_ratelimit = False
            now = time.time()

            for oid, (code, data) in sorted(codes.items()):
                self.scanned += 1
                if code == config.ERR_NET:
                    saw_net_err = True
                    if oid not in self.pending_holes and oid not in self.hits:
                        self._add_hole(oid, now, now + 1.0)
                elif code == config.ERR_BANNED:
                    saw_banned = True
                elif code == config.ERR_RATELIMIT:
                    saw_ratelimit = True
                elif code == 200 and data:
                    if self.watchdog:
                        self.watchdog.mark_success()
                    if max_seen is None or oid > max_seen:
                        max_seen = oid
                    self.pending_holes.pop(oid, None)
                    await self._process_offer(oid, data, source_tag="FRONTIER")
                elif code == 404:
                    if oid not in self.pending_holes and oid not in self.hits:
                        self._add_hole(oid, now, now + config.HOLE_RETRY_DELAYS[0])

            if saw_banned:
                await self._on_banned()
                break

            if saw_net_err:
                await asyncio.sleep(config.WAIT_NET_ERR)
            elif saw_ratelimit:
                # http_client już ustawił LAST_RETRY_AFTER; poczekaj aż minie
                await asyncio.sleep(1.0)
            elif max_seen is not None:
                self.head = max_seen + 1
            else:
                await asyncio.sleep(config.WAIT_NO_NEW)

            await self._maybe_save_hits()

            if self.scanned % 500 == 0:
                LOG_APP.info(
                    f"DETEKTOR: skan={self.scanned}, head={self.head}, "
                    f"trafienia={len(self.hits)}, dziury_w_kolejce={len(self.pending_holes)}, "
                    f"odzyskane_z_dziur={self.holes_recovered}"
                )

    async def _hole_sweeper_loop(self):
        """Zamiatacz dziur: weryfikuje opóźnione numery 404 (Zero-Miss)."""
        LOG_APP.info("DETEKTOR: start zamiatacza dziur (Hole Sweeper)")
        while not self.stop.is_set():
            now = time.time()
            ready_ids = [
                oid
                for oid, item in self.pending_holes.items()
                if now >= item["next_retry"] and oid not in self.hits
            ][: config.HOLE_BATCH_SIZE]

            if not ready_ids:
                await asyncio.sleep(0.3)
                continue

            codes = await http_client.scan_ids(
                ready_ids, config.HOLE_CONCURRENCY
            )
            saw_banned = False
            for oid, (code, data) in codes.items():
                item = self.pending_holes.get(oid)
                if not item:
                    continue

                if code == config.ERR_BANNED:
                    saw_banned = True
                elif code == 200 and data:
                    if self.watchdog:
                        self.watchdog.mark_success()
                    self.holes_recovered += 1
                    self.pending_holes.pop(oid, None)
                    await self._process_offer(oid, data, source_tag="HOLE_SWEEP")
                elif code == config.ERR_RATELIMIT:
                    # poczekaj, nie wywalaj z kolejki
                    item["next_retry"] = now + 5.0
                elif code == config.ERR_NET:
                    # sieć padła — ponów później, nie karz jeszcze
                    item["next_retry"] = now + config.HOLE_RETRY_DELAYS[0]
                else:
                    age = now - item["first_seen"]
                    att = item["attempts"] + 1
                    if att < len(config.HOLE_RETRY_DELAYS) and age < config.HOLE_MAX_AGE:
                        item["attempts"] = att
                        item["next_retry"] = now + config.HOLE_RETRY_DELAYS[att]
                    else:
                        self.holes_expired += 1
                        self.pending_holes.pop(oid, None)

            if saw_banned:
                await self._on_banned()
                break

            await asyncio.sleep(0.1)

    async def run(self):
        """Glowna petla detektora."""
        LOG_APP.info("DETEKTOR: start (async dual-tier)")

        mx = await http_client.get_max_id()
        if mx == config.ERR_BANNED:
            await self._on_banned()
            return
        if mx is None:
            LOG_APP.error("DETEKTOR: seed zawiódł po retry — czekam i próbuję ponownie")
            if self.notifier:
                await self.notifier.critical("SEED FAIL: brak max_id — czekam 60s")
            await asyncio.sleep(config.SEED_RETRY_LONG)
            mx = await http_client.get_max_id()
        if mx == config.ERR_BANNED:
            await self._on_banned()
            return
        if mx is None:
            LOG_APP.error("DETEKTOR: brak seed max_id po dwóch turach — koniec")
            if self.notifier:
                await self.notifier.critical("SEED FAIL: bot nie wystartował")
            return

        head = mx - 40
        if head < 0:
            head = 0
        LOG_APP.info(f"DETEKTOR: seed z listy={mx}, szukam krawedzi od {head}...")

        # Faza 1: dojdz do krawedzi
        head, sc = await self._scan_phase(head, config.BATCH_SIZE, time.time() + 300)
        self.scanned += sc
        self.head = head
        LOG_APP.info(f"DETEKTOR: krawedz przy oid={head}")

        if self.stop.is_set():
            await self._finalize()
            return

        # Faza 2: współbieżna czołówka + zamiatacz dziur
        await asyncio.gather(
            self._frontier_loop(),
            self._hole_sweeper_loop(),
        )

        await self._finalize()

    async def _finalize(self):
        """Zapisz trafienia przed końcem."""
        await asyncio.to_thread(self._save_hits)
        LOG_APP.info(
            f"DETEKTOR: koniec, przeskanowano={self.scanned}, "
            f"trafienia={len(self.hits)}, odzyskane={self.holes_recovered}"
        )

    def get_hits(self):
        return dict(self.hits)