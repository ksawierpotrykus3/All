# Stealth Improvements — Design Spec

- **Date:** 2026-07-13
- **Project:** DeepSeek Proxy (modular)
- **Motivation:** Prevent DeepSeek from detecting automated traffic and muting accounts (`biz_code=14` / `"user is muted"`).

## 1. Problem

DeepSeek uses multi-layered anti-bot detection that flags proxies missing browser-like behavior. Research across multiple reverse-engineering projects (deepseek-free-api, ds2api) shows that DeepSeek detects automation through:

1. **Missing browser telemetry** — real browsers send events to `POST /api/v0/events` (heartbeat, page_loaded, visibility_changed, beforeunload)
2. **Incomplete browser headers** — missing `Accept-Encoding`, `Accept-Language`, `Sec-Fetch-*` headers
3. **Missing fingerprint cookies** — `_frid`, `_fr_ssid`, `_fr_pvid` cookies that real browsers carry
4. **TLS fingerprint inconsistencies** — mitigated by curl_cffi's `impersonate`, but requires header consistency

A mass mute wave on May 12-13, 2026 affected multiple projects including ds2api (which was subsequently archived).

## 2. Scope

All three anti-detection areas, implemented in a new `server/core/stealth.py` module:

- **Browser telemetry**: heartbeat (5-10s interval) + page_loaded + visibility_changed + beforeunload events
- **Extended headers**: Accept-Encoding, Accept-Language, Sec-Fetch-*, Priority
- **Fingerprint cookies**: `_frid`, `_fr_ssid`, `_fr_pvid` with periodic rotation of `_fr_pvid`

## 3. Architecture

### 3.1 Module: `server/core/stealth.py`

Single new file with three components and a wrapper:

```
server/core/stealth.py
├── augment_headers()    — pure function, adds browser-like headers
├── class FingerprintCookies — generates & rotates fingerprint cookies
├── class BrowserTelemetry   — sends browser events via async fire-and-forget
└── class StealthEngine      — wrapper that composes the above
```

### 3.2 Integration

- `DeepSeek.__init__()` creates `StealthEngine` as `self.stealth`
- `DeepSeek._headers()` calls `self.stealth.augment_headers()` before returning
- `DeepSeek.stream_completion()` calls `self.stealth.telemetry.start()` before streaming
- HTTP requests use `self.stealth.merge_cookies()` to inject fingerprint cookies

No changes to `proxy.py` or other services.

## 4. Component Details

### 4.1 `augment_headers()`

Pure function. No state, no side effects.

```python
def augment_headers(headers: dict, user_agent: str) -> dict:
    h = dict(headers)
    h.setdefault("accept-encoding", "gzip, deflate, br, zstd")
    h.setdefault("accept-language", "en-US,en;q=0.9")
    h.setdefault("sec-fetch-dest", "empty")
    h.setdefault("sec-fetch-mode", "cors")
    h.setdefault("sec-fetch-site", "same-origin")
    h.setdefault("priority", "u=1, i")
    return h
```

### 4.2 `FingerprintCookies`

One instance per slot. Generates random hex IDs on init.

- `_frid`: stable (never changes)
- `_fr_ssid`: stable (never changes)
- `_fr_pvid`: rotated every ~30 minutes

```python
class FingerprintCookies:
    def __init__(self):
        self._frid = self._random_hex(16)
        self._fr_ssid = self._random_hex(16)
        self._fr_pvid = self._random_hex(16)
        self._rotated_at = time.time()

    def get_cookies(self) -> dict:
        if time.time() - self._rotated_at > 1800:
            self._fr_pvid = self._random_hex(16)
            self._rotated_at = time.time()
        return {"_frid": self._frid, "_fr_ssid": self._fr_ssid, "_fr_pvid": self._fr_pvid}

    def merge_into(self, target: dict) -> dict:
        target.update(self.get_cookies())
        return target
```

### 4.3 `BrowserTelemetry`

Sends events to `POST /api/v0/events` on the same DeepSeek base URL (`https://chat.deepseek.com`) used by all other requests.

- **Event types**: `page_loaded`, `heartbeat`, `visibility_changed`, `beforeunload`
- **Heartbeat interval**: random 5-10 seconds
- **Visibility**: ~20% chance per heartbeat tick to send `visibility_changed`
- **Fire-and-forget**: failures are silently ignored, no impact on streaming

Uses `asyncio` tasks managed per slot. The `_headers_fn` callback is `DeepSeek._headers(slot)` returning the same auth+pow headers used for chat requests. Uses `asyncio.run_coroutine_threadsafe()` because `stream_completion()` runs in a synchronous thread — the event loop reference is obtained from `asyncio.get_event_loop()` during `DeepSeek.__init__()`.

```python
class BrowserTelemetry:
    def __init__(self, http_session, headers_fn):
        self._http = http_session
        self._headers_fn = headers_fn
        self._tasks: dict[int, asyncio.Task] = {}

    async def start(self, slot: int, cookies: dict):
        if slot in self._tasks:
            return
        await self._send_event(slot, "page_loaded", cookies)
        self._tasks[slot] = asyncio.create_task(self._loop(slot, cookies))

    async def _loop(self, slot: int, cookies: dict):
        try:
            while True:
                await asyncio.sleep(random.uniform(5, 10))
                await self._send_event(slot, "heartbeat", cookies)
                if random.random() < 0.2:
                    await self._send_event(slot, "visibility_changed", cookies)
        except asyncio.CancelledError:
            await self._send_event(slot, "beforeunload", cookies)

    async def _send_event(self, slot: int, event: str, cookies: dict):
        try:
            await self._http.post(
                "https://chat.deepseek.com/api/v0/events",
                headers=self._headers_fn(slot),
                json={"event_type": event, "event_data": {}},
                cookies=cookies,
                impersonate="chrome120",
                timeout=5,
            )
        except Exception:
            pass  # fire-and-forget

    def stop(self, slot: int):
        if slot in self._tasks:
            self._tasks[slot].cancel()
            del self._tasks[slot]
```

### 4.4 `StealthEngine`

Wrapper that composes the components:

```python
class StealthEngine:
    def __init__(self, http_session, base_headers_fn):
        self.telemetry = BrowserTelemetry(http_session, base_headers_fn)
        self.fingerprint = FingerprintCookies()

    def augment_headers(self, headers: dict, user_agent: str) -> dict:
        return _augment_headers(headers, user_agent)

    def merge_cookies(self, cookies: dict) -> dict:
        return self.fingerprint.merge_into(cookies)
```

## 5. Changes to Existing Code

### `server/core/deepseek_client.py`

1. **Constructor**: Create `StealthEngine`
2. **`_headers()`**: Call `self.stealth.augment_headers()` before returning
3. **`stream_completion()`**: Start telemetry before streaming, merge fingerprint cookies into request cookies
4. **Helper**: Store event loop reference for `asyncio.run_coroutine_threadsafe()` — get from `asyncio.get_event_loop()` at init time

### `server/core/__init__.py`

Add `from .stealth import StealthEngine` export.

## 6. Error Handling

- **Telemetry send failures**: silently ignored (fire-and-forget)
- **Fingerprint cookie generation**: deterministic, no failure mode beyond memory
- **Header augmentation**: pure function, no failure mode
- **Telemetry task cancellation**: clean shutdown with `beforeunload` event sent on cancel

## 7. Testing

- Unit test `augment_headers()` — verify all expected headers are present
- Unit test `FingerprintCookies` — verify rotation timing, cookie format
- Integration test `BrowserTelemetry` — verify events are sent (mock HTTP)
- Integration test full flow — verify headers+cookies appear in actual requests
