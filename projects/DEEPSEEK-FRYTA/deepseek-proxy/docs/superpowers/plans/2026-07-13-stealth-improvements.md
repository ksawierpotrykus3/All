# Stealth Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement browser-like behavior (telemetry events, extended headers, fingerprint cookies) to prevent DeepSeek from detecting automated traffic and muting accounts.

**Architecture:** New `server/core/stealth.py` module with `StealthEngine` wrapper, integrated into `DeepSeek` client by composition. Three components: `augment_headers()` (pure function), `FingerprintCookies` (stateful cookie generator), `BrowserTelemetry` (async fire-and-forget event sender).

**Tech Stack:** Python 3.10+, asyncio, requests (curl_cffi), existing DeepSeek client infrastructure.

**Spec:** [2026-07-13-stealth-improvements-design.md](../specs/2026-07-13-stealth-improvements-design.md)

---

## File Structure

- **Create** `server/core/stealth.py` — all new components (augment_headers, FingerprintCookies, BrowserTelemetry, StealthEngine)
- **Modify** `server/core/deepseek_client.py` — integrate StealthEngine into DeepSeek class (~15 lines)
- **Modify** `server/core/__init__.py` — export StealthEngine

---

### Task 1: Write stealth module tests

**Files:**
- Create: `tests/test_stealth.py`
- Create: `server/core/stealth.py` (stub)

- [ ] **Step 1: Create test file with all test cases**

```python
"""Tests for server/core/stealth.py"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from server.core.stealth import (
    augment_headers,
    FingerprintCookies,
    BrowserTelemetry,
    StealthEngine,
)


class TestAugmentHeaders:
    def test_adds_missing_headers(self):
        base = {"accept": "*/*", "user-agent": "test"}
        result = augment_headers(base, "test")
        assert result["accept-encoding"] == "gzip, deflate, br, zstd"
        assert result["accept-language"] == "en-US,en;q=0.9"
        assert result["sec-fetch-dest"] == "empty"
        assert result["sec-fetch-mode"] == "cors"
        assert result["sec-fetch-site"] == "same-origin"
        assert result["priority"] == "u=1, i"

    def test_preserves_existing_headers(self):
        base = {"accept": "*/*", "accept-encoding": "custom"}
        result = augment_headers(base, "")
        assert result["accept-encoding"] == "custom"

    def test_does_not_mutate_input(self):
        base = {"accept": "*/*"}
        result = augment_headers(base, "")
        assert base == {"accept": "*/*"}
        assert result != base


class TestFingerprintCookies:
    def test_generates_all_fields(self):
        fc = FingerprintCookies()
        cookies = fc.get_cookies()
        assert "_frid" in cookies
        assert "_fr_ssid" in cookies
        assert "_fr_pvid" in cookies
        assert len(cookies["_frid"]) == 32  # 16 hex bytes = 32 chars
        assert cookies["_frid"] != cookies["_fr_ssid"]

    def test_merge_into_updates_target(self):
        fc = FingerprintCookies()
        target = {"existing": "val"}
        result = fc.merge_into(target)
        assert result["existing"] == "val"
        assert "_frid" in result

    def test_rotates_pvid_after_timeout(self):
        fc = FingerprintCookies()
        old_pvid = fc._fr_pvid
        fc._rotated_at = 0  # force immediate rotation
        cookies = fc.get_cookies()
        assert cookies["_fr_pvid"] != old_pvid
        assert cookies["_frid"] == fc._frid  # stable
        assert cookies["_fr_ssid"] == fc._fr_ssid  # stable

    def test_stable_ids(self):
        fc = FingerprintCookies()
        c1 = fc.get_cookies()
        c2 = fc.get_cookies()
        assert c1["_frid"] == c2["_frid"]
        assert c1["_fr_ssid"] == c2["_fr_ssid"]

    def test_different_instances_different_ids(self):
        fc1 = FingerprintCookies()
        fc2 = FingerprintCookies()
        assert fc1.get_cookies()["_frid"] != fc2.get_cookies()["_frid"]


class TestBrowserTelemetry:
    @pytest.mark.asyncio
    async def test_start_sends_page_loaded(self):
        mock_http = AsyncMock()
        mock_headers_fn = MagicMock(return_value={"accept": "*/*"})
        bt = BrowserTelemetry(mock_http, mock_headers_fn)

        await bt.start(0, {})

        mock_http.post.assert_awaited_once()
        call_kwargs = mock_http.post.call_args.kwargs
        assert call_kwargs["json"]["event_type"] == "page_loaded"

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        mock_http = AsyncMock()
        bt = BrowserTelemetry(mock_http, MagicMock(return_value={}))

        await bt.start(0, {})
        await bt.start(0, {})  # same slot again

        mock_http.post.assert_awaited_once()  # only one page_loaded

    @pytest.mark.asyncio
    async def test_stop_cancels_task_and_sends_beforeunload(self):
        mock_http = AsyncMock()
        bt = BrowserTelemetry(mock_http, MagicMock(return_value={}))
        await bt.start(0, {})

        bt.stop(0)

        assert 0 not in bt._tasks
        # sleep enough for cancellation to propagate
        await asyncio.sleep(0.1)
        # beforeunload sent
        beforeunload_calls = [
            c for c in mock_http.post.await_args_list
            if c.kwargs.get("json", {}).get("event_type") == "beforeunload"
        ]
        assert len(beforeunload_calls) >= 1

    @pytest.mark.asyncio
    async def test_send_failure_does_not_raise(self):
        mock_http = AsyncMock()
        mock_http.post.side_effect = Exception("connection error")
        bt = BrowserTelemetry(mock_http, MagicMock(return_value={}))

        # should not raise
        await bt._send_event(0, "test", {})


class TestStealthEngine:
    def test_augment_headers_delegates(self):
        engine = StealthEngine(None, None)
        base = {"accept": "*/*"}
        result = engine.augment_headers(base, "")
        assert "accept-encoding" in result

    def test_merge_cookies_delegates(self):
        engine = StealthEngine(None, None)
        result = engine.merge_cookies({"existing": "val"})
        assert "_frid" in result
        assert "existing" in result

    def test_has_telemetry_and_fingerprint(self):
        engine = StealthEngine(None, None)
        assert hasattr(engine, "telemetry")
        assert hasattr(engine, "fingerprint")
```

- [ ] **Step 2: Create stub stealth.py with empty classes that tests can import**

```python
"""Stealth module — browser-like behavior to avoid DeepSeek anti-bot detection."""
import asyncio
import random
import time
import secrets

DEEPSEEK_BASE = "https://chat.deepseek.com"


def augment_headers(headers: dict, user_agent: str) -> dict:
    """Add browser-like headers missing from minimal requests."""
    raise NotImplementedError


class FingerprintCookies:
    """Generates and rotates browser fingerprint cookies (_frid, _fr_ssid, _fr_pvid)."""
    def __init__(self):
        raise NotImplementedError

    def get_cookies(self) -> dict:
        raise NotImplementedError

    def merge_into(self, target: dict) -> dict:
        raise NotImplementedError


class BrowserTelemetry:
    """Sends browser lifecycle events to DeepSeek's /api/v0/events endpoint."""
    def __init__(self, http_session, headers_fn):
        raise NotImplementedError

    async def start(self, slot: int, cookies: dict):
        raise NotImplementedError

    async def _send_event(self, slot: int, event: str, cookies: dict):
        raise NotImplementedError

    def stop(self, slot: int):
        raise NotImplementedError


class StealthEngine:
    """Wrapper composing BrowserTelemetry + FingerprintCookies + header augmentation."""
    def __init__(self, http_session=None, base_headers_fn=None):
        raise NotImplementedError

    def augment_headers(self, headers: dict, user_agent: str) -> dict:
        raise NotImplementedError

    def merge_cookies(self, cookies: dict) -> dict:
        raise NotImplementedError
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_stealth.py -v`
Expected: All tests fail with NotImplementedError or import error

---

### Task 2: Implement `augment_headers()` and `FingerprintCookies`

**Files:**
- Modify: `server/core/stealth.py`

- [ ] **Step 1: Implement `augment_headers()` and `FingerprintCookies`**

Replace `raise NotImplementedError` stubs with real implementations:

```python
def augment_headers(headers: dict, user_agent: str) -> dict:
    """Add browser-like headers missing from minimal requests.

    Returns a new dict; does not mutate the input.
    """
    h = dict(headers)
    h.setdefault("accept-encoding", "gzip, deflate, br, zstd")
    h.setdefault("accept-language", "en-US,en;q=0.9")
    h.setdefault("sec-fetch-dest", "empty")
    h.setdefault("sec-fetch-mode", "cors")
    h.setdefault("sec-fetch-site", "same-origin")
    h.setdefault("priority", "u=1, i")
    return h


class FingerprintCookies:
    """Generates and rotates browser fingerprint cookies.

    - _frid: stable (fixed per instance)
    - _fr_ssid: stable (fixed per instance)
    - _fr_pvid: rotated every 1800 seconds (~30 min)
    """

    def __init__(self):
        self._frid = secrets.token_hex(16)
        self._fr_ssid = secrets.token_hex(16)
        self._fr_pvid = secrets.token_hex(16)
        self._rotated_at = time.time()

    def _random_hex(self, nbytes: int = 16) -> str:
        return secrets.token_hex(nbytes)

    def get_cookies(self) -> dict:
        """Return current fingerprint cookies, rotating _fr_pvid if needed."""
        if time.time() - self._rotated_at > 1800:
            self._fr_pvid = self._random_hex(16)
            self._rotated_at = time.time()
        return {
            "_frid": self._frid,
            "_fr_ssid": self._fr_ssid,
            "_fr_pvid": self._fr_pvid,
        }

    def merge_into(self, target: dict) -> dict:
        """Merge fingerprint cookies into an existing cookie dict (in-place)."""
        target.update(self.get_cookies())
        return target
```

- [ ] **Step 2: Run augmented_headers tests**

Run: `pytest tests/test_stealth.py::TestAugmentHeaders -v`
Expected: 3 PASS

- [ ] **Step 3: Run FingerprintCookies tests**

Run: `pytest tests/test_stealth.py::TestFingerprintCookies -v`
Expected: 5 PASS

- [ ] **Step 4: Commit**

```bash
git add server/core/stealth.py tests/test_stealth.py
git commit -m "feat: add header augmentation and fingerprint cookies"
```

---

### Task 3: Implement `BrowserTelemetry`

**Files:**
- Modify: `server/core/stealth.py`

- [ ] **Step 1: Implement `BrowserTelemetry` class**

Replace stubs with real implementation:

```python
class BrowserTelemetry:
    """Sends browser lifecycle events to DeepSeek's /api/v0/events endpoint.

    Events are fire-and-forget (failures silently ignored).
    One task per slot, cancelled on stop().
    """

    def __init__(self, http_session, headers_fn):
        """http_session: async HTTP client with .post()
           headers_fn: callable(slot) -> dict of auth/pow headers
        """
        self._http = http_session
        self._headers_fn = headers_fn
        self._tasks: dict[int, asyncio.Task] = {}

    async def start(self, slot: int, cookies: dict):
        """Begin telemetry for a slot. Sends page_loaded immediately,
        then starts heartbeat loop. Idempotent per slot."""
        if slot in self._tasks:
            return
        await self._send_event(slot, "page_loaded", cookies)
        self._tasks[slot] = asyncio.create_task(
            self._heartbeat_loop(slot, cookies)
        )

    async def _heartbeat_loop(self, slot: int, cookies: dict):
        try:
            while True:
                await asyncio.sleep(random.uniform(5, 10))
                await self._send_event(slot, "heartbeat", cookies)
                # ~20% chance to also send visibility_changed
                if random.random() < 0.2:
                    await self._send_event(slot, "visibility_changed", cookies)
        except asyncio.CancelledError:
            await self._send_event(slot, "beforeunload", cookies)

    async def _send_event(self, slot: int, event: str, cookies: dict):
        """Fire-and-forget POST to /api/v0/events. Silently ignores failures."""
        try:
            headers = self._headers_fn(slot)
            await self._http.post(
                f"{DEEPSEEK_BASE}/api/v0/events",
                headers=headers,
                json={"event_type": event, "event_data": {}},
                cookies=cookies,
                impersonate="chrome120",
                timeout=5,
            )
        except Exception:
            pass  # fire-and-forget — telemetry must not break chat

    def stop(self, slot: int):
        """Stop telemetry for a slot. Sends beforeunload event on cancel."""
        if slot in self._tasks:
            self._tasks[slot].cancel()
            del self._tasks[slot]
```

- [ ] **Step 2: Implement `StealthEngine` wrapper**

Replace stub with:

```python
class StealthEngine:
    """Wrapper composing BrowserTelemetry + FingerprintCookies + header augmentation."""

    def __init__(self, http_session=None, base_headers_fn=None):
        self.telemetry = BrowserTelemetry(http_session, base_headers_fn)
        self.fingerprint = FingerprintCookies()

    def augment_headers(self, headers: dict, user_agent: str) -> dict:
        """Add browser-like headers."""
        return augment_headers(headers, user_agent)

    def merge_cookies(self, cookies: dict) -> dict:
        """Merge fingerprint cookies into an existing cookie dict."""
        return self.fingerprint.merge_into(cookies)
```

- [ ] **Step 3: Run BrowserTelemetry tests**

Run: `pytest tests/test_stealth.py::TestBrowserTelemetry -v`
Expected: 4 PASS (test_start_sends_page_loaded, test_start_is_idempotent, test_stop_cancels_task_and_sends_beforeunload, test_send_failure_does_not_raise)

- [ ] **Step 4: Run StealthEngine tests**

Run: `pytest tests/test_stealth.py::TestStealthEngine -v`
Expected: 3 PASS

- [ ] **Step 5: Run all stealth tests**

Run: `pytest tests/test_stealth.py -v`
Expected: 15 PASS

- [ ] **Step 6: Commit**

```bash
git add server/core/stealth.py
git commit -m "feat: add browser telemetry events and StealthEngine wrapper"
```

---

### Task 4: Integrate StealthEngine into DeepSeek client

**Files:**
- Modify: `server/core/deepseek_client.py`
- Modify: `server/core/__init__.py`

- [ ] **Step 1: Read existing DeepSeek class to understand integration points**

Read `server/core/deepseek_client.py` to find `__init__`, `_headers()`, and `stream_completion()` locations.

- [ ] **Step 2: Import and add StealthEngine to DeepSeek.__init__()**

Add import and create StealthEngine in constructor:

```python
from server.core.stealth import StealthEngine

class DeepSeek:
    def __init__(self, pool: AccountPool):
        self.pool = pool
        self.pow = DeepSeekPOW()
        self._http = requests.Session()
        self._http.headers.update({...})
        self._loop = asyncio.get_event_loop()
        self.stealth = StealthEngine(self._http, self._headers)
```

- [ ] **Step 3: Modify _headers() to augment with stealth headers**

Find the `_headers()` method and add `self.stealth.augment_headers()` call before returning:

```python
def _headers(self, slot: int, pow_resp: str | None = None) -> dict:
    s = self._ses(slot)
    h = {
        "accept": "*/*",
        "authorization": f"Bearer {s.auth_token}",
        "content-type": "application/json",
        "origin": "https://chat.deepseek.com",
        "referer": "https://chat.deepseek.com/",
        "user-agent": s.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "x-app-version": "2.0.0",
        "x-client-locale": "en_US",
        "x-client-platform": "web",
        "x-client-version": "2.0.0",
    }
    h = self.stealth.augment_headers(h, h.get("user-agent", ""))
    if pow_resp:
        h["x-ds-pow-response"] = pow_resp
    return h
```

- [ ] **Step 4: Merge fingerprint cookies into stream request cookies**

In `stream_completion()`, before `_http.post(...)`, merge fingerprint cookies:

```python
# After getting existing cookies
cookies = dict(s.cookies)
self.stealth.merge_cookies(cookies)
# Use cookies in the POST call
```

- [ ] **Step 5: Start telemetry in stream_completion()**

Before the streaming loop, start browser telemetry for the slot:

```python
# Start browser telemetry (fire-and-forget via event loop)
asyncio.run_coroutine_threadsafe(
    self.stealth.telemetry.start(slot, dict(s.cookies)),
    self._loop
)
```

Note: Since `stream_completion()` is a synchronous generator running in a thread pool, we use `asyncio.run_coroutine_threadsafe` with the main event loop captured in `__init__`.

- [ ] **Step 6: Export StealthEngine from server/core/__init__.py**

```python
from .stealth import StealthEngine
```

- [ ] **Step 7: Commit**

```bash
git add server/core/deepseek_client.py server/core/__init__.py
git commit -m "feat: integrate StealthEngine into DeepSeek client"
```

---

### Task 5: Integration test — verify headers and cookies in live requests

**Files:**
- Modify: `tests/test_stealth.py` (add integration tests)

- [ ] **Step 1: Add integration test for stealth+cookies in HTTP requests**

```python
class TestStealthIntegration:
    """Verify that augment_headers and fingerprint cookies appear in actual requests."""

    @pytest.mark.asyncio
    async def test_augment_headers_appear_in_outgoing_request(self):
        """Mock the HTTP session and verify all stealth headers are present."""
        from server.core.stealth import StealthEngine

        mock_http = AsyncMock()
        headers_fn = MagicMock(return_value={
            "accept": "*/*",
            "authorization": "Bearer test",
            "user-agent": "test-agent",
        })
        engine = StealthEngine(mock_http, headers_fn)

        headers = headers_fn(0)
        augmented = engine.augment_headers(headers, "test-agent")
        cookies = engine.merge_cookies({"existing": "val"})

        assert "accept-encoding" in augmented
        assert "accept-language" in augmented
        assert "sec-fetch-dest" in augmented
        assert "_frid" in cookies
        assert "_fr_ssid" in cookies
        assert "_fr_pvid" in cookies

    @pytest.mark.asyncio
    async def test_telemetry_uses_correct_endpoint(self):
        """Verify telemetry sends to the correct DeepSeek endpoint."""
        from server.core.stealth import StealthEngine

        mock_http = AsyncMock()
        engine = StealthEngine(mock_http, MagicMock(return_value={"accept": "*/*"}))

        await engine.telemetry.start(0, {"_frid": "test"})

        mock_http.post.assert_awaited_once()
        call_url = mock_http.post.call_args.args[0]
        assert "/api/v0/events" in call_url
        assert "chat.deepseek.com" in call_url

    def test_fingerprint_cookies_are_unique_per_engine(self):
        from server.core.stealth import StealthEngine
        e1 = StealthEngine()
        e2 = StealthEngine()
        assert e1.merge_cookies({})["_frid"] != e2.merge_cookies({})["_frid"]
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_stealth.py::TestStealthIntegration -v`
Expected: 3 PASS

- [ ] **Step 3: Run all tests**

Run: `pytest tests/test_stealth.py -v`
Expected: 18 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_stealth.py
git commit -m "test: add integration tests for stealth engine"
```

---

### Task 6: Restart server and verify live

- [ ] **Step 1: Stop the current server**

Run (in terminal with server PID):
StopCommand on the running server terminal.

- [ ] **Step 2: Restart server with stealth module**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -u -m server.main`

- [ ] **Step 3: Send test request to verify server works**

```bash
curl -s -X POST http://localhost:4570/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"say HELLO and nothing else"}],"stream":true}'
```

Expected: Returns a response with "HELLO" content.

- [ ] **Step 4: Check server logs for stealth activity**

Verify that `[AUGMENT]`, `[COOKIES]`, or `[TELEMETRY]` prefixed log lines appear.

- [ ] **Step 5: Commit final integration**

```bash
git add -A
git commit -m "chore: restart server with stealth improvements"
```
