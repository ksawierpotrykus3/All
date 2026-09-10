"""Klient HTTP: curl_cffi z TLS impersonation chrome124 (obejscie CloudFront).

Obsluguje:
  - 403 -> ERR_BANNED (blokada IP)
  - 429 -> ERR_RATELIMIT + Retry-After (globalny stan do wstrzymania bota)
  - błędy sieci -> ERR_NET z retry i backoffem
"""
import asyncio
import time

from curl_cffi.requests import AsyncSession

from . import config


# Globalny timestamp, do kiedy bot ma czekać po 429 (Retry-After).
LAST_RETRY_AFTER = 0.0


def _until_ratelimit_clear() -> float:
    """Ile sekund jeszcze czekać po 429. Zwraca 0, gdy nie ma limitu."""
    return max(0.0, LAST_RETRY_AFTER - time.time())


async def _sleep_ratelimit():
    """Jeśli jest aktywny rate-limit, poczekaj zanim bot wyśle cokolwiek."""
    wait = _until_ratelimit_clear()
    if wait > 0:
        await asyncio.sleep(wait)


async def get_offer(session, oid):
    """Pobierz pelna oferte po ID. Zwraca (status_code, data).

    status_code może być jednym z config.ERR_* (liczby ujemne).
    """
    await _sleep_ratelimit()
    r = await session.get(config.API + str(oid) + "/")
    if r.status_code == 200:
        return 200, r.json().get("data")
    if r.status_code == 403:
        return config.ERR_BANNED, None
    if r.status_code == 429:
        _set_ratelimit(r.headers.get("Retry-After"))
        return config.ERR_RATELIMIT, None
    return r.status_code, None


def _set_ratelimit(retry_after):
    """Ustaw globalny czas wstrzymania po 429."""
    global LAST_RETRY_AFTER
    try:
        ra = float(retry_after)
    except (TypeError, ValueError):
        ra = 5.0
    LAST_RETRY_AFTER = time.time() + ra


async def _get_with_status(session, oid):
    """Pojedynczy request. Wyjątki sieciowe zwracają ERR_NET."""
    try:
        return await get_offer(session, oid)
    except Exception:  # noqa: BLE001
        return (config.ERR_NET, None)


async def _fetch_with_retry(session, oid):
    """Pobierz ofertę z retry przy błędzie sieci (ERR_NET)."""
    result = await _get_with_status(session, oid)
    code, _ = result
    if code != config.ERR_NET:
        return result

    # retry z backoffem przy błędzie sieci
    for attempt in range(config.RETRY_COUNT):
        await asyncio.sleep(config.RETRY_BACKOFF_BASE * (attempt + 1))
        result = await _get_with_status(session, oid)
        code, _ = result
        if code != config.ERR_NET:
            return result
    return (config.ERR_NET, None)


async def scan_batch(start_id, count, concurrency):
    """Skanuje zakres ID. Zwraca slownik {oid: (code, data)}."""
    sem = asyncio.Semaphore(concurrency)
    results = {}

    async def fetch(oid):
        async with sem:
            return oid, await _fetch_with_retry(session, oid)

    async with AsyncSession(
        impersonate=config.IMP, timeout=config.TIMEOUT
    ) as session:
        tasks = [fetch(start_id + i) for i in range(count)]
        gathered = await asyncio.gather(*tasks)

    for oid, result in gathered:
        results[oid] = result

    return results


async def scan_ids(id_list, concurrency=None):
    """Skanuje podana liste ID (np. bufor dziur). Zwraca {oid: (code, data)}."""
    if not id_list:
        return {}
    conc = concurrency or config.HOLE_CONCURRENCY
    sem = asyncio.Semaphore(conc)
    results = {}

    async def fetch(oid):
        async with sem:
            return oid, await _fetch_with_retry(session, oid)

    async with AsyncSession(
        impersonate=config.IMP, timeout=config.TIMEOUT
    ) as session:
        tasks = [fetch(oid) for oid in id_list]
        gathered = await asyncio.gather(*tasks)

    for oid, result in gathered:
        results[oid] = result

    return results


async def get_max_id():
    """Seed: najwyzsze ID z listy top 50. Z retry i backoffem."""
    await _sleep_ratelimit()
    for attempt in range(config.SEED_RETRY_COUNT):
        try:
            async with AsyncSession(
                impersonate=config.IMP, timeout=config.TIMEOUT
            ) as session:
                r = await session.get(config.API + "?offset=0&limit=50")
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    return max(d["id"] for d in data)
            elif r.status_code == 403:
                return config.ERR_BANNED
            elif r.status_code == 429:
                _set_ratelimit(r.headers.get("Retry-After"))
                await _sleep_ratelimit()
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(config.SEED_RETRY_BACKOFF * (attempt + 1))
    return None


async def search(query, category_id, offset=0):
    """Wyszukiwanie w publicznym API (dla komparatora). Zwraca liste ID."""
    url = (
        f"{config.API}?offset={offset}&limit=50"
        f"&query={query}&category_id={category_id}"
    )
    await _sleep_ratelimit()
    async with AsyncSession(
        impersonate=config.IMP, timeout=config.TIMEOUT
    ) as session:
        r = await session.get(url)
    if r.status_code != 200:
        return []
    return [d["id"] for d in r.json().get("data", [])]