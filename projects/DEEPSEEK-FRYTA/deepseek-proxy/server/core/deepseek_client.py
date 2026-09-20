"""DeepSeek web API client — V0 API, PoW, streaming.

Ported from the original working server.py (V0 API).
V2 API (/api/v2/*) is deprecated by DeepSeek and returns HTML.
"""

from __future__ import annotations

import json
import threading
import time
import random
import uuid
from itertools import chain
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests
from fastapi import HTTPException
from pow import DeepSeekPOW

from server.services.state_service import (
    conv_state as _conv_state,
    conv_lock as _conv_lock,
)
from server.services.rate_limiter import rate_limiter
from server.config import MAX_ACCOUNTS
from server.logging import get_logger


logger = get_logger(__name__)


class DeepSeekRateLimitError(Exception):
    """Raised when DeepSeek returns rate limit / server busy error.

    Includes retry_after seconds for Retry-After header.
    """

    def __init__(self, message: str, retry_after: int = 30):
        super().__init__(message)
        self.retry_after = retry_after


_pow_cache: dict[tuple[int, str], str] = {}
_pow_expires: dict[tuple[int, str], float] = {}
_pow_lock = threading.Lock()


@dataclass
class Session:
    auth_token: str
    cookies: dict
    user_agent: str = ""
    created_at: float = 0.0
    last_validated_at: float = 0.0
    device_id: str = ""


class AccountPool:
    """Manages DeepSeek web session accounts (slots)."""

    def __init__(self):
        self.slots: list[Session | None] = [None] * MAX_ACCOUNTS
        self._load_all()

    def _slot_path(self, slot: int) -> Path:
        return Path(__file__).parent.parent / f"session_{slot}.json"

    def _migrate_old_session(self, slot: int) -> None:
        old = Path(f"cookies_{slot}.json")
        if old.exists():
            try:
                data = json.loads(old.read_text(encoding="utf-8"))
                self.slots[slot] = Session(
                    auth_token=data.get("auth_token", ""),
                    cookies=data.get("cookies", {}),
                    user_agent=data.get("user_agent", ""),
                    created_at=data.get("created_at", 0.0),
                    last_validated_at=data.get("last_validated_at", 0.0),
                )
                self.save(slot)
                old.unlink()
                logger.info(f"[MIGRATE] slot {slot}: migrated from cookies_{slot}.json")
            except Exception as e:
                logger.info(f"[MIGRATE] slot {slot}: error {e}")

    def _load_all(self) -> None:
        for i in range(MAX_ACCOUNTS):
            self._migrate_old_session(i)
            p = self._slot_path(i)
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        self.slots[i] = Session(
                            auth_token=data.get("auth_token", ""),
                            cookies=data.get("cookies", {}),
                            user_agent=data.get("user_agent", ""),
                            created_at=data.get("created_at", 0.0),
                            last_validated_at=data.get("last_validated_at", 0.0),
                        )
                        logger.info(f"[LOAD] slot {i}: loaded session")
                except Exception as e:
                    logger.info(f"[LOAD] slot {i}: error {e}")

    def save(self, slot: int) -> None:
        s = self.slots[slot]
        if s is None:
            return
        try:
            data = {
                "auth_token": s.auth_token,
                "cookies": s.cookies,
                "user_agent": s.user_agent,
                "created_at": s.created_at,
                "last_validated_at": s.last_validated_at,
            }
            self._slot_path(slot).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.info(f"[SAVE] slot {slot}: error {e}")

    def is_valid(self, slot: int) -> bool:
        if slot < 0 or slot >= MAX_ACCOUNTS:
            return False
        s = self.slots[slot]
        if s is None:
            return False
        if not s.auth_token:
            return False
        return True

    def reset_slot(self, slot: int) -> None:
        """Remove slot session, delete its file and purge conv_state entries for this slot."""
        self.slots[slot] = None
        p = self._slot_path(slot)
        if p.exists():
            try:
                p.unlink()
                logger.info(f"[RESET] slot {slot}: session file deleted")
            except Exception as e:
                logger.info(f"[RESET] slot {slot}: error deleting session file: {e}")
        # Purge all conversation state entries bound to this account slot
        with _conv_lock:
            to_del = [h for h, v in _conv_state.items() if v.get("account") == slot]
            for h in to_del:
                del _conv_state[h]
        if to_del:
            logger.info(f"[RESET] slot {slot}: purged {len(to_del)} conv_state entries")
        # Reset rate limit timer for the slot
        rate_limiter.reset(slot)


class DeepSeek:
    """DeepSeek V0 web chat API client using curl_cffi + PoW."""

    BASE_URL = "https://chat.deepseek.com"
    # Minimum interval between requests to the same account (seconds).
    # Prevents bot-like request bursts that trigger DeepSeek's rate limiter.
    # Uses jitter (random delay) so the pattern looks human-made rather than
    # a fixed clock interval. DeepSeek mutes accounts when traffic looks
    # mechanically regular (every ~3s).
    _MIN_BASE_DELAY = 15.0  # Increased from 8.0 due to aggressive rate limiting (2026-09-07)
    _MAX_JITTER = 5.0  # additional random jitter on top of base

    def __init__(self, pool: AccountPool):
        self.pool = pool
        self.pow = DeepSeekPOW()
        # One HTTP session PER account slot — prevents cookie cross-contamination.
        # A shared session would mix cookies from different accounts, causing
        # DeepSeek to see multiple auth tokens in a single request → mute.
        self._http: list[requests.Session] = []
        for i in range(MAX_ACCOUNTS):
            sess = requests.Session()
            # Minimalist headers matching legacy server.py (which never got muted).
            # Deliberately omitting sec-ch-ua, x-client-bundle-id, accept-language
            # and other "browser simulation" headers that trigger bot-detection.
            sess.headers.update(
                {
                    "accept": "*/*",
                    "content-type": "application/json",
                    "origin": "https://chat.deepseek.com",
                    "referer": "https://chat.deepseek.com/",
                    "x-app-version": "2.0.0",
                    "x-client-locale": "en_US",
                    "x-client-platform": "web",
                    "x-client-version": "2.0.0",
                }
            )
            self._http.append(sess)
        # Per-account request timing for rate limiting
        self._last_request_time: list[float] = [0.0] * MAX_ACCOUNTS
        self._throttle_lock = threading.Lock()

    def reset_http_session(self, slot: int) -> None:
        """Recreate the curl_cffi HTTP session for a slot to clear all cookies.

        Must be called after re-login so stale session cookies don't leak into
        the new authenticated session.
        """
        sess = requests.Session()
        # Same minimalist headers as __init__ — must stay in sync.
        sess.headers.update(
            {
                "accept": "*/*",
                "content-type": "application/json",
                "origin": "https://chat.deepseek.com",
                "referer": "https://chat.deepseek.com/",
                "x-app-version": "2.0.0",
                "x-client-locale": "en_US",
                "x-client-platform": "web",
                "x-client-version": "2.0.0",
            }
        )
        self._http[slot] = sess
        self._last_request_time[slot] = 0.0
        logger.info(f"[RESET] slot {slot}: HTTP session recreated (cookies cleared)")

    def _throttle(
        self, slot: int, is_retry: bool = False, is_interim: bool = False, is_resume: bool = False
    ) -> None:
        """Enforce minimum interval between requests to the same account.

        If the last request to *slot* was less than target delay ago, sleep for
        the remaining time. For retries (stream_continue), interim chunks, and
        tool call resume turns, use a short delay (1.0s) so agentic tool execution
        does not suffer massive artificial multi-second freezes.
        """
        with self._throttle_lock:
            if is_interim or is_resume:
                target = 1.0
            elif is_retry:
                target = 2.0
            else:
                target = self._MIN_BASE_DELAY + random.uniform(0, self._MAX_JITTER)
            elapsed = time.time() - self._last_request_time[slot]
            if elapsed < target:
                wait = target - elapsed
                import asyncio
                try:
                    asyncio.get_running_loop()
                    in_async_loop = True
                except RuntimeError:
                    in_async_loop = False

                if in_async_loop and wait > 0.5:
                    logger.warning(
                        f"[THROTTLE GUARD] Prevented blocking time.sleep({wait:.1f}s) inside running asyncio loop for account={slot}. Use async_throttle instead."
                    )
                else:
                    logger.info(
                        f"[THROTTLE] account={slot} waiting {wait:.1f}s (target={target:.1f}s, elapsed={elapsed:.1f}s, retry={is_retry}, interim={is_interim}, resume={is_resume})"
                    )
                    time.sleep(wait)
            self._last_request_time[slot] = time.time()

    async def async_throttle(
        self, slot: int, is_retry: bool = False, is_interim: bool = False, is_resume: bool = False
    ) -> None:
        """Asynchronously enforce minimum spacing without blocking the asyncio event loop."""
        import asyncio

        with self._throttle_lock:
            if is_interim or is_resume:
                target = 1.0
            elif is_retry:
                target = 2.0
            else:
                target = self._MIN_BASE_DELAY + random.uniform(0, self._MAX_JITTER)
            elapsed = time.time() - self._last_request_time[slot]
            wait = target - elapsed if elapsed < target else 0.0

        if wait > 0:
            logger.info(
                f"[THROTTLE] account={slot} async waiting {wait:.1f}s (target={target:.1f}s, elapsed={elapsed:.1f}s, retry={is_retry}, interim={is_interim}, resume={is_resume})"
            )
            await asyncio.sleep(wait)

        with self._throttle_lock:
            self._last_request_time[slot] = time.time()

    def _ses(self, slot: int) -> Session:

        s = self.pool.slots[slot]
        if s is None:
            raise HTTPException(401, f"Slot {slot} not logged in")
        return s

    # Fallback UA when session does not have a stored user_agent.
    # Must match curl_cffi impersonate="chrome120" (same as legacy server.py).
    _PINNED_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def _headers(
        self,
        slot: int,
        pow_resp: str | None = None,
        chat_session_id: str | None = None,
    ) -> dict:
        """Build request headers matching official DeepSeek Web client v2.5.0 fingerprint."""
        s = self._ses(slot)
        device_id = getattr(s, "device_id", "") or str(
            uuid.uuid5(uuid.NAMESPACE_DNS, s.auth_token)
        )
        referer = (
            f"https://chat.deepseek.com/a/chat/s/{chat_session_id}"
            if chat_session_id
            else "https://chat.deepseek.com/"
        )
        h = {
            "accept": "*/*",
            "authorization": f"Bearer {s.auth_token}",
            "content-type": "application/json",
            "origin": "https://chat.deepseek.com",
            "referer": referer,
            "user-agent": s.user_agent or self._PINNED_UA,
            "x-client-bundle-id": "com.deepseek.chat",
            "x-client-locale": "en_US",
            "x-client-platform": "web",
            "x-client-timezone-offset": "7200",
            "x-client-version": "2.5.0",
            "x-device-id": device_id,
            "x-device-model": "",
        }
        if pow_resp:
            h["x-ds-pow-response"] = pow_resp
        return h

    # ─── PoW ───────────────────────────────────────────

    def _invalidate_pow(self, slot: int, target_path: str | None = None) -> None:
        with _pow_lock:
            if target_path:
                _pow_cache.pop((slot, target_path), None)
                _pow_expires.pop((slot, target_path), None)
            else:
                to_pop = [k for k in _pow_cache if k[0] == slot]
                for k in to_pop:
                    _pow_cache.pop(k, None)
                    _pow_expires.pop(k, None)

    def _get_challenge(self, slot: int, target_path: str = "/api/v0/chat/completion") -> dict:
        s = self._ses(slot)
        r = requests.post(
            f"{self.BASE_URL}/api/v0/chat/create_pow_challenge",
            headers=self._headers(slot),
            json={"target_path": target_path},
            cookies=s.cookies,
            impersonate="chrome120",
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"Failed to create PoW challenge (HTTP {r.status_code}): {r.text[:300]}"
            )
        try:
            resp_json = r.json()
        except Exception:
            raise RuntimeError(
                f"Non-JSON response for PoW challenge (HTTP {r.status_code}): {r.text[:300]}"
            )
        if not isinstance(resp_json, dict):
            raise RuntimeError(f"Invalid JSON for PoW challenge: {resp_json}")
        data = resp_json.get("data")
        if not isinstance(data, dict):
            msg = resp_json.get("msg") or "No data field in response"
            raise RuntimeError(f"DeepSeek PoW challenge failed: {msg} (full: {resp_json})")
        biz_data = data.get("biz_data")
        if not isinstance(biz_data, dict):
            raise RuntimeError(f"DeepSeek PoW challenge missing biz_data: {resp_json}")
        challenge = biz_data.get("challenge")
        if not isinstance(challenge, dict):
            raise RuntimeError(f"DeepSeek PoW challenge missing challenge dict: {resp_json}")
        return challenge

    def _get_pow(
        self,
        slot: int,
        target_path: str = "/api/v0/chat/completion",
        force_refresh: bool = False,
    ) -> str:
        now = time.time()
        key = (slot, target_path)
        # Upload PoW tokens are single-use nonces on DeepSeek cluster — NEVER cache them!
        is_upload = (target_path == "/api/v0/file/upload_file")
        if not force_refresh and not is_upload:
            with _pow_lock:
                cached = _pow_cache.pop(key, None)
                expires = _pow_expires.pop(key, 0)
                if cached and now < expires:
                    # PoW tokens on DeepSeek cluster are single-use nonces.
                    # Once consumed from cache, immediately replenish in background for the next request.
                    if target_path == "/api/v0/chat/completion":
                        threading.Thread(target=self._prefetch_pow, args=(slot,), daemon=True).start()
                    return cached
        # Cache miss, expired, or upload: solve challenge synchronously
        challenge = self._get_challenge(slot, target_path=target_path)
        t0 = time.time()
        pow_resp = self.pow.solve_challenge(challenge)
        elapsed = time.time() - t0
        logger.info(f"[POW] account={slot} path={target_path} solved in {elapsed:.1f}s")
        # Notice: The synchronously solved token is consumed immediately by the caller,
        # so we do NOT store it in _pow_cache. Instead, prefetch generates a fresh token for next call.
        if target_path == "/api/v0/chat/completion":
            threading.Thread(target=self._prefetch_pow, args=(slot,), daemon=True).start()
        return pow_resp

    def _prefetch_pow(self, slot: int) -> None:
        target_path = "/api/v0/chat/completion"
        key = (slot, target_path)
        with _pow_lock:
            existing = _pow_cache.get(key)
            exp = _pow_expires.get(key, 0)
            if existing and exp > time.time() + 15:
                # Already have a valid pre-computed token
                return
        try:
            challenge = self._get_challenge(slot, target_path=target_path)
            if not challenge:
                logger.warning(
                    f"[POW] prefetch got empty challenge for account={slot}, skipped"
                )
                return
            pow_resp = self.pow.solve_challenge(challenge)
            if not pow_resp:
                logger.warning(
                    f"[POW] prefetch solve returned empty for account={slot}, skipped"
                )
                return
            expiry_s = challenge.get("expire_at", 0) / 1000
            if expiry_s > time.time() + 5:
                with _pow_lock:
                    _pow_cache[key] = pow_resp
                    _pow_expires[key] = expiry_s
                logger.info(
                    f"[POW] prefetched for account={slot} (expires in {int(expiry_s - time.time())}s)"
                )
        except Exception as e:
            logger.error(f"[POW] prefetch failed for account={slot}: {e}")

    # ─── File Upload ───────────────────────────────────

    def upload_file(
        self,
        slot: int,
        file_data: bytes,
        filename: str = "image.png",
        mime_type: str = "image/png",
        model_type: str = "default",
    ) -> str:
        """Upload an image file to DeepSeek Web API and return the file_id (e.g. file-xxxx)."""
        from curl_cffi import CurlMime

        max_upload_retries = 3
        for attempt in range(max_upload_retries):
            pow_resp = self._get_pow(
                slot, target_path="/api/v0/file/upload_file", force_refresh=True
            )
            s = self._ses(slot)

            h = self._headers(slot, pow_resp=pow_resp)
            h.pop("content-type", None)
            h["x-file-size"] = str(len(file_data))
            h["x-model-type"] = model_type or "default"
            h["x-thinking-enabled"] = "1"

            mp = CurlMime.from_list([
                {
                    "name": "file",
                    "filename": filename,
                    "content_type": mime_type,
                    "data": file_data,
                }
            ])
            try:
                r = requests.post(
                    f"{self.BASE_URL}/api/v0/file/upload_file",
                    headers=h,
                    multipart=mp,
                    cookies=s.cookies,
                    impersonate="chrome120",
                    timeout=60,
                )
                if hasattr(r, "cookies") and r.cookies:
                    s.cookies.update(r.cookies)
            finally:
                mp.close()

            raw = r.text[:1000]
            if r.status_code != 200:
                if attempt + 1 < max_upload_retries and "INVALID_POW_RESPONSE" in raw:
                    logger.warning(
                        f"[UPLOAD] INVALID_POW_RESPONSE (attempt {attempt + 1}/{max_upload_retries}) – retrying with fresh PoW..."
                    )
                    time.sleep(0.5)
                    continue
                raise Exception(f"DeepSeek file upload error {r.status_code}: {raw}")
            try:
                data = r.json()
            except Exception:
                raise Exception(f"DeepSeek file upload non-JSON response ({r.status_code}): {raw}")

            if not isinstance(data, dict):
                raise Exception(f"DeepSeek file upload invalid JSON response ({r.status_code}): {raw}")

            code = data.get("code")
            if code is not None and code != 0:
                msg = data.get("msg") or raw
                if attempt + 1 < max_upload_retries and (code == 40301 or "INVALID_POW_RESPONSE" in msg):
                    logger.warning(
                        f"[UPLOAD] PoW rejected code={code} (attempt {attempt + 1}/{max_upload_retries}) – retrying with fresh PoW..."
                    )
                    time.sleep(0.5)
                    continue
                raise Exception(f"DeepSeek file upload failed (code={code}): {msg}")

            d_data = data.get("data")
            biz_data = d_data.get("biz_data") if isinstance(d_data, dict) else {}
            if not isinstance(biz_data, dict):
                biz_data = {}

            file_id = (
                biz_data.get("id")
                or (d_data.get("id") if isinstance(d_data, dict) else None)
                or data.get("id")
            )
            if not file_id:
                raise Exception(f"DeepSeek file upload missing file id in response: {raw}")
            logger.info(f"[UPLOAD] Uploaded {filename} ({len(file_data)} bytes) for slot {slot} -> {file_id}")
            self.wait_for_file_ready(slot, file_id)
            return file_id

    def wait_for_file_ready(self, slot: int, file_id: str, timeout: float = 15.0) -> bool:
        """Poll DeepSeek API until uploaded file has status SUCCESS (audit passed)."""
        s = self._ses(slot)
        start_t = time.time()
        poll_interval = 0.5
        while time.time() - start_t < timeout:
            try:
                r = self._http[slot].get(
                    f"{self.BASE_URL}/api/v0/file/fetch_files?file_ids={file_id}",
                    headers=self._headers(slot),
                    cookies=s.cookies,
                    impersonate="chrome120",
                    timeout=10,
                )
                if r.status_code == 200:
                    resp = r.json()
                    files = resp.get("data", {}).get("biz_data", {}).get("files", [])
                    if files and isinstance(files, list):
                        f_info = files[0]
                        st = f_info.get("status")
                        audit = f_info.get("audit_result")
                        if st == "SUCCESS":
                            logger.info(
                                f"[UPLOAD] File {file_id} ready (status={st}, audit={audit}, elapsed={time.time()-start_t:.1f}s)"
                            )
                            return True
                        elif st == "FAILED":
                            err_code = f_info.get("error_code")
                            raise RuntimeError(
                                f"DeepSeek file {file_id} processing failed: status=FAILED, error_code={err_code}"
                            )
            except (RuntimeError, Exception) as e:
                if isinstance(e, RuntimeError):
                    raise
                logger.warning(f"[UPLOAD] Polling file {file_id} status error: {e}")
            time.sleep(poll_interval)

        logger.warning(
            f"[UPLOAD] Timeout waiting for file {file_id} status SUCCESS after {timeout}s — proceeding anyway"
        )
        return False

    # ─── Session ───────────────────────────────────────

    def create_session(self, slot: int, throttle: bool = True) -> str:
        if throttle:
            self._throttle(slot)
        s = self._ses(slot)
        r = self._http[slot].post(
            f"{self.BASE_URL}/api/v0/chat_session/create",
            headers=self._headers(slot),
            json={},
            cookies=s.cookies,
            impersonate="chrome120",
            timeout=30,
        )
        resp_json = r.json()
        data = resp_json.get("data")
        if data is None:
            raise HTTPException(
                502,
                f"Create session failed: {json.dumps(resp_json, ensure_ascii=False)[:300]}",
            )
        chat_session_id = data["biz_data"]["chat_session"]["id"]
        logger.info(f"[CREATE SESSION] account={slot} {chat_session_id}")
        return chat_session_id

    def stop_stream(self, slot: int, chat_session_id: str, message_id: int) -> bool:
        """Send stop_stream signal to DeepSeek Web API to halt generation and commit the message node."""
        s = self._ses(slot)
        try:
            r = self._http[slot].post(
                f"{self.BASE_URL}/api/v0/chat/stop_stream",
                headers=self._headers(slot, chat_session_id=chat_session_id),
                json={"chat_session_id": chat_session_id, "message_id": message_id},
                cookies=s.cookies,
                impersonate="chrome120",
                timeout=10,
            )
            if r.status_code == 200:
                logger.info(
                    f"[STOP_STREAM] slot={slot} session={chat_session_id[:12] if chat_session_id else ''} msg_id={message_id} stopped successfully"
                )
                return True
            else:
                logger.warning(
                    f"[STOP_STREAM] slot={slot} session={chat_session_id[:12] if chat_session_id else ''} msg_id={message_id} returned HTTP {r.status_code}"
                )
                return False
        except Exception as e:
            logger.warning(
                f"[STOP_STREAM] slot={slot} session={chat_session_id[:12] if chat_session_id else ''} msg_id={message_id} error: {e}"
            )
            return False

    def get_last_message_id(self, slot: int, chat_session_id: str) -> int | None:
        """Query DeepSeek Web API for existing messages in session and return highest message_id."""
        s = self._ses(slot)
        try:
            r = self._http[slot].get(
                f"{self.BASE_URL}/api/v0/chat/history_messages?chat_session_id={chat_session_id}",
                headers=self._headers(slot, chat_session_id=chat_session_id),
                cookies=s.cookies,
                impersonate="chrome120",
                timeout=10,
            )
            if r.status_code != 200:
                return None
            data = r.json().get("data", {})
            biz_data = data.get("biz_data") if isinstance(data, dict) else {}
            msgs = biz_data.get("chat_messages", []) if isinstance(biz_data, dict) else []
            if not msgs:
                return None
            valid_ids = [m.get("message_id") for m in msgs if m.get("message_id") is not None]
            return max(valid_ids) if valid_ids else None
        except Exception as e:
            logger.warning(f"[SESSION_SYNC] Failed to fetch history for {chat_session_id}: {e}")
            return None

    # ─── Streaming ─────────────────────────────────────

    def stream_completion(
        self,
        slot: int,
        chat_session_id: str,
        prompt: str,
        parent_message_id: int | None = None,
        model_type: str = "expert",
        ref_file_ids: list[str] | None = None,
        thinking_enabled: bool = True,
        search_enabled: bool = False,
        reasoning_effort: str | None = None,
        max_tokens: int = 65536,
        temperature: float = 1.0,
        top_p: float = 1.0,
        is_chunk_continuation: bool = False,
        _retry: int = 0,
        throttle: bool = True,
    ) -> tuple:
        if _retry > 0:
            logger.info(
                f"[RETRY] Attempt {_retry} for session={chat_session_id[:12]}..."
            )
        from curl_cffi.requests.exceptions import RequestException as CurlError

        if parent_message_id is not None:
            try:
                parent_message_id = int(parent_message_id)
            except (ValueError, TypeError):
                parent_message_id = None

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                pow_resp = self._get_pow(slot)
                s = self._ses(slot)
                req_model_type = model_type if parent_message_id is None else None
                body = {
                    "chat_session_id": chat_session_id,
                    "parent_message_id": parent_message_id,
                    "model_type": req_model_type,
                    "prompt": prompt,
                    "ref_file_ids": ref_file_ids or [],
                    "thinking_enabled": thinking_enabled,
                    "search_enabled": search_enabled,
                    "action": None,
                    "preempt": False,
                }
                if reasoning_effort:
                    body["reasoning_effort"] = reasoning_effort
                if throttle:
                    self._throttle(slot, is_interim=is_chunk_continuation)
                r = requests.post(
                    f"{self.BASE_URL}/api/v0/chat/completion",
                    headers=self._headers(
                        slot,
                        pow_resp,
                        chat_session_id=chat_session_id,
                    ),
                    json=body,
                    cookies=s.cookies,
                    impersonate="chrome120",
                    stream=True,
                    timeout=600,
                )
                break
            except CurlError as e:
                if attempt < max_retries:
                    logger.info(
                        f"[RETRY] curl error (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(5)
                    continue
                raise
        if r.status_code == 401:
            raise RuntimeError(f"DeepSeek auth error: HTTP 401 Unauthorized for account {slot}")
        if r.status_code != 200:
            error_text = next(r.iter_lines(), b"").decode("utf-8", "ignore")
            raise RuntimeError(f"DeepSeek API error {r.status_code}: {error_text}")

        it = r.iter_lines()
        resp_msg_id: str | int | None = ""
        pre_lines: list[bytes] = []
        rate_limit_detected = False
        preamble_data_count = 0
        for line in it:
            pre_lines.append(line)
            if not line:
                continue
            decoded = line.decode("utf-8", "ignore")
            if decoded.startswith("data: "):
                preamble_data_count += 1
                try:
                    d = json.loads(decoded[6:])
                    if not isinstance(d, dict):
                        continue
                    if d.get("type") == "error":
                        err = d.get("content", "Unknown error")
                        logger.error(f"[ERROR] DeepSeek error: {err}")
                        if (
                            "length limit" in err.lower()
                            or "start a new chat" in err.lower()
                            or "context_length" in err.lower()
                        ):
                            raise RuntimeError(f"DeepSeek error: {err}")
                        rate_limit_detected = True
                        break
                    rid = d.get("response_message_id")
                    if rid is not None:
                        resp_msg_id = str(rid)
                        break
                except json.JSONDecodeError:
                    pass

        if preamble_data_count == 0 and pre_lines:
            raw_body = b"".join(pre_lines).decode("utf-8", "ignore")
            if "INVALID_POW_RESPONSE" in raw_body:
                logger.info(
                    f"[POW] INVALID_POW_RESPONSE (attempt {_retry + 1}) – clearing PoW cache and retrying..."
                )
                self._invalidate_pow(slot)
                return self.stream_completion(
                    slot,
                    chat_session_id,
                    prompt,
                    parent_message_id,
                    model_type=model_type,
                    ref_file_ids=ref_file_ids,
                    thinking_enabled=thinking_enabled,
                    search_enabled=search_enabled,
                    reasoning_effort=reasoning_effort,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    _retry=_retry + 1,
                )

        if rate_limit_detected:
            rate_limiter.set_limited(slot, time.time() + 30)
            # Raise custom exception with retry_after for HTTP Retry-After header
            raise DeepSeekRateLimitError(
                f"DeepSeek rate limit: Server is busy. Try again later.", retry_after=30
            )

        resp_msg_id = int(resp_msg_id) if resp_msg_id else None
        if preamble_data_count == 0:
            logger.warning(
                f"[WARN] No data lines from DeepSeek for session={chat_session_id} parent={parent_message_id}"
            )
            if pre_lines:
                raw_first = b"".join(pre_lines[:5]).decode("utf-8", "ignore")[:500]
                logger.warning(
                    f"[WARN] pre_lines (first 5, {len(pre_lines)} total): {raw_first!r}"
                )
                try:
                    err_data = json.loads(raw_first)
                    if isinstance(err_data, dict):
                        err_d = err_data.get("data")
                        err_d_dict = err_d if isinstance(err_d, dict) else {}
                        biz_code = err_d_dict.get("biz_code")
                        biz_msg = err_d_dict.get("biz_msg", "")
                        if biz_msg:
                            logger.info(f"[DS_API] account={slot} biz_msg={biz_msg}")
                        if (biz_code == 26 or "invalid message id" in biz_msg.lower()) and _retry < 3:
                            logger.warning(
                                f"[PARENT_DESYNC] stream_completion invalid parent_id={parent_message_id} for session={chat_session_id}. Querying session history..."
                            )
                            real_last_id = self.get_last_message_id(slot, chat_session_id)
                            if real_last_id != parent_message_id:
                                logger.info(
                                    f"[PARENT_AUTOCORRECT] stream_completion auto-correcting parent_id from {parent_message_id} to {real_last_id}. Retrying..."
                                )
                                return self.stream_completion(
                                    slot,
                                    chat_session_id,
                                    prompt,
                                    real_last_id,
                                    model_type=model_type,
                                    ref_file_ids=ref_file_ids,
                                    thinking_enabled=thinking_enabled,
                                    search_enabled=search_enabled,
                                    reasoning_effort=reasoning_effort,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                    top_p=top_p,
                                    _retry=_retry + 1,
                                    throttle=False,
                                )
                        biz_data = err_d_dict.get("biz_data")
                        biz_data_dict = biz_data if isinstance(biz_data, dict) else {}
                        mute_until = biz_data_dict.get("mute_until", 0)
                        if biz_msg == "user is muted" and mute_until:
                            from datetime import datetime

                            dt = datetime.fromtimestamp(mute_until)
                            logger.info(
                                f"[DS_API] account={slot} MUTED until {dt.strftime('%Y-%m-%d %H:%M:%S')} — marking account as rate-limited until then"
                            )
                            rate_limiter.set_limited(slot, mute_until)
                            retry_after = int(mute_until - time.time())
                            if retry_after < 1:
                                retry_after = 30
                            raise DeepSeekRateLimitError(
                                f"DeepSeek account muted until {dt.strftime('%Y-%m-%d %H:%M:%S')}",
                                retry_after=retry_after,
                            )
                except (RuntimeError, DeepSeekRateLimitError):
                    raise
                except Exception:
                    pass
        elif resp_msg_id is None:
            logger.warning(
                f"[WARN] No response_message_id in {preamble_data_count} data lines for session={chat_session_id}"
            )

        return self._build_stream_iterator(
            it=it,
            pre_lines=pre_lines,
            resp_msg_id=resp_msg_id,
            thinking_enabled=thinking_enabled,
            chat_session_id=chat_session_id,
            preamble_data_count=preamble_data_count,
        )

    def _build_stream_iterator(
        self,
        it: Iterator[bytes],
        pre_lines: list[bytes],
        resp_msg_id: int | None,
        thinking_enabled: bool,
        chat_session_id: str,
        preamble_data_count: int,
    ) -> tuple[Iterator[str], dict]:
        """Unified SSE stream consumer for completion and continue streams."""
        remaining_it = it
        result_meta: dict = {
            "resp_msg_id": resp_msg_id,
            "no_data": preamble_data_count == 0,
            "thinking_fallback": "",
            "is_finished": False,
        }

        def _stream():
            nonlocal resp_msg_id
            content_buffer = ""
            response_started = False
            prev_yielded = 0
            raw_count = 0
            total_yielded = 0
            stream_ended_naturally = True
            try:
                for line in chain(pre_lines, remaining_it):
                    if not line:
                        continue
                    decoded = line.decode("utf-8", "ignore")
                    if not decoded.startswith("data: "):
                        continue
                    payload = decoded[6:]
                    raw_count += 1
                    if raw_count <= 100:
                        _is_tool = any(
                            m in payload
                            for m in [
                                "<tool_calls>",
                                "<tool_call",
                                "<invoke",
                                "FINAL ANSWER",
                                "<function_call",
                            ]
                        )
                        _tag = "[RAW_TOOL]" if _is_tool else f"[RAW#{raw_count}]"
                        if _is_tool or raw_count <= 3:
                            logger.info(f"{_tag} {payload[:300]}")
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    if data.get("type") == "error":
                        err_msg = data.get("content", "Unknown error")
                        logger.error(
                            f"[ERROR] DeepSeek SSE error mid-stream: {err_msg}"
                        )
                        clear_resp = data.get("clear_response", False)
                        result_meta["is_error"] = True
                        result_meta["clear_response"] = clear_resp
                        if clear_resp:
                            result_meta.pop("resp_msg_id", None)
                        else:
                            # Preserve resp_msg_id so stream_continue can resume this incomplete message on DeepSeek!
                            if resp_msg_id:
                                result_meta["resp_msg_id"] = resp_msg_id
                        raise RuntimeError(f"DeepSeek error: {err_msg}")
                    if data.get("o") == "BATCH" and isinstance(data.get("v"), list):
                        items = data["v"]
                    else:
                        items = [data]

                    stream_finished = False
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if isinstance(item.get("v"), dict) and "response" in item["v"]:
                            resp_dict = item["v"]["response"]
                            mid = resp_dict.get("message_id")
                            if mid is not None:
                                try:
                                    resp_msg_id = int(mid)
                                    result_meta["resp_msg_id"] = resp_msg_id
                                except (ValueError, TypeError):
                                    pass
                            for frag in resp_dict.get("fragments", []):
                                if isinstance(frag, dict) and frag.get("type") == "RESPONSE":
                                    response_started = True
                                    fc = frag.get("content", "")
                                    if fc:
                                        content_buffer = fc
                                        inc = content_buffer[prev_yielded:]
                                        if inc:
                                            prev_yielded = len(content_buffer)
                                            total_yielded += len(inc)
                                            yield inc
                            continue

                        path = item.get("p", "")
                        val = item.get("v")
                        op = item.get("o", "")

                        rid = item.get("response_message_id")
                        if rid is not None:
                            try:
                                resp_msg_id = int(rid)
                                result_meta["resp_msg_id"] = resp_msg_id
                            except (ValueError, TypeError):
                                pass

                        if path == "response/status" and op == "SET" and val == "FINISHED":
                            stream_ended_naturally = False
                            logger.info(
                                f"[DS_END] FINISHED signal received (response_started={response_started}, content_buffer_chars={len(content_buffer)}, total_yielded={total_yielded})"
                            )
                            stream_finished = True
                            result_meta["is_finished"] = True
                            break

                        if (path == "quasi_status" and val == "FINISHED") or (
                            item.get("quasi_status") == "FINISHED"
                        ):
                            logger.info(
                                f"[DS_QUASI] quasi stage completed (response_started={response_started}, content_buffer_chars={len(content_buffer)})"
                            )
                            continue

                        if not path and isinstance(val, str) and val:
                            content_buffer += val
                            if response_started:
                                inc = content_buffer[prev_yielded:]
                                if inc:
                                    prev_yielded = len(content_buffer)
                                    total_yielded += len(inc)
                                    yield inc
                            continue

                        if path == "response/fragments" and isinstance(val, list):
                            for fragment in val:
                                if (
                                    isinstance(fragment, dict)
                                    and fragment.get("type") == "RESPONSE"
                                ):
                                    response_started = True
                                    fc = fragment.get("content", "")
                                    if fc:
                                        content_buffer = fc
                                        prev_yielded = len(fc)
                                        total_yielded += len(fc)
                                        yield fc
                            continue

                        if (
                            path.endswith("/content")
                            and isinstance(val, str)
                            and response_started
                        ):
                            content_buffer += val
                            inc = content_buffer[prev_yielded:]
                            if inc:
                                prev_yielded = len(content_buffer)
                                total_yielded += len(inc)
                                yield inc
                            continue

                    if stream_finished:
                        break
                if not response_started:
                    result_meta["thinking_fallback"] = content_buffer
                    remaining = content_buffer[prev_yielded:]
                    if remaining:
                        if not thinking_enabled:
                            logger.info(
                                f"[FALLBACK] yielding {len(remaining)} chars of pre-response text (thinking_enabled=False)"
                            )
                            total_yielded += len(remaining)
                            yield remaining
                        else:
                            logger.warning(
                                f"[WARN] Stream finished without explicit RESPONSE header (chars={len(remaining)}). "
                                f"Preserving pre-response thoughts in thinking_fallback instead of leaking as response."
                            )
                if stream_ended_naturally:
                    logger.info(
                        f"[DS_END] stream iterator exhausted (response_started={response_started}, content_buffer_chars={len(content_buffer)}, total_yielded={total_yielded})"
                    )
                else:
                    logger.info(
                        f"[DS_END] FINISHED — stream completed (response_started={response_started}, total_yielded={total_yielded})"
                    )

                # Mark as empty if FINISHED arrived without any content (stale resume)
                result_meta["empty_stream"] = (
                    not response_started and total_yielded == 0
                )
            except Exception as e:
                logger.error(
                    f"[DS_STREAM_ERR] exception during streaming: {type(e).__name__}: {e} (response_started={response_started}, total_yielded={total_yielded})"
                )
                raise
            finally:
                # CRITICAL: Always close the curl_cffi response to release the TLS/HTTP
                # connection back to the pool. Without this, Windows libcurl blocks ALL
                # subsequent HTTPS requests to the same host (deadlock on TLS session pool)
                # when the stream is abandoned mid-way (e.g. on Length limit reached error).
                try:
                    r.close()
                except Exception:
                    pass

            logger.info(
                f"[TIMING] DS stream done, resp_id={result_meta.get('resp_msg_id', resp_msg_id)}"
            )

        return _stream(), result_meta

    def stream_continue(
        self,
        slot: int,
        chat_session_id: str,
        message_id: int,
        model_type: str = "default",
        thinking_enabled: bool = True,
        _retry: int = 0,
        throttle: bool = True,
    ) -> tuple[Iterator[str], dict]:
        """Call DeepSeek POST /api/v0/chat/continue to resume generation for message_id."""
        from curl_cffi.requests.exceptions import RequestException as CurlError

        try:
            message_id = int(message_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid message_id for stream_continue: {message_id}")

        max_curl_retries = 3
        r = None
        for curl_attempt in range(max_curl_retries + 1):
            try:
                s = self._ses(slot)
                body = {
                    "chat_session_id": chat_session_id,
                    "message_id": message_id,
                    "fallback_to_resume": True,
                }
                if throttle:
                    self._throttle(slot, is_retry=True)
                r = requests.post(
                    f"{self.BASE_URL}/api/v0/chat/continue",
                    headers=self._headers(
                        slot,
                        None,
                        chat_session_id=chat_session_id,
                    ),
                    json=body,
                    cookies=s.cookies,
                    impersonate="chrome120",
                    stream=True,
                    timeout=120,
                )
                break
            except CurlError as e:
                if curl_attempt < max_curl_retries:
                    logger.info(
                        f"[RETRY] curl error in stream_continue (attempt {curl_attempt + 1}/{max_curl_retries}): {e}"
                    )
                    time.sleep(3)
                    continue
                raise

        if r is None:
            raise RuntimeError("Failed to establish connection for stream_continue")

        if r.status_code == 401:
            r.close()
            raise RuntimeError(f"DeepSeek auth error 401 for stream_continue (account {slot})")

        if r.status_code != 200:
            error_text = next(r.iter_lines(), b"").decode("utf-8", "ignore")
            r.close()
            raise RuntimeError(
                f"DeepSeek API error {r.status_code} in stream_continue: {error_text}"
            )

        it = r.iter_lines()
        pre_lines: list[bytes] = []
        resp_msg_id = message_id
        rate_limit_detected = False
        preamble_data_count = 0
        for _ in range(10):
            line = next(it, None)
            if line is None:
                break
            pre_lines.append(line)
            if not line:
                continue
            decoded = line.decode("utf-8", "ignore")
            if not decoded.startswith("data: "):
                try:
                    d = json.loads(decoded)
                    if isinstance(d, dict):
                        d_data = d.get("data")
                        d_data_dict = d_data if isinstance(d_data, dict) else {}
                        biz_msg = d_data_dict.get("biz_msg") or d.get("msg", "")
                        biz_code = d_data_dict.get("biz_code")
                        if biz_code == 22 or "invalid message status" in str(biz_msg):
                            logger.info(
                                f"[CONTINUE] message_id={message_id} is already FINISHED on DeepSeek cluster (biz_msg={biz_msg})"
                            )
                            return iter([]), {
                                "resp_msg_id": message_id,
                                "no_data": False,
                                "already_finished": True,
                                "thinking_fallback": "",
                            }
                except Exception:
                    pass
                continue
            preamble_data_count += 1
            try:
                d = json.loads(decoded[6:])
                if not isinstance(d, dict):
                    continue
                if d.get("type") == "error":
                    err = d.get("content", "Unknown error")
                    logger.error(f"[ERROR] DeepSeek error in continue: {err}")
                    rate_limit_detected = True
                    break
                rid = d.get("response_message_id")
                if rid is not None:
                    resp_msg_id = int(rid)
                    break
            except json.JSONDecodeError:
                pass

        if rate_limit_detected:
            rate_limiter.set_limited(slot, time.time() + 30)
            try:
                r.close()
            except Exception:
                pass
            raise DeepSeekRateLimitError(
                "DeepSeek rate limit: Server is busy in continue", retry_after=30
            )

        return self._build_stream_iterator(
            it=it,
            pre_lines=pre_lines,
            resp_msg_id=resp_msg_id,
            thinking_enabled=thinking_enabled,
            chat_session_id=chat_session_id,
            preamble_data_count=preamble_data_count,
        )

    def send_interim_chunk(
        self,
        slot: int,
        chat_session_id: str,
        prompt: str,
        parent_message_id: int | None,
        model_type: str = "expert",
        _retry: int = 0,
        throttle: bool = True,
    ) -> int:
        """Send an interim prompt chunk to DeepSeek, extract response_message_id,
        and immediately terminate the stream without waiting for assistant generation.

        This registers the chunk in the cloud conversation tree and returns the
        new response_message_id to be used as parent_message_id for the subsequent chunk.
        """
        from curl_cffi.requests.exceptions import RequestException as CurlError

        if parent_message_id is not None:
            try:
                parent_message_id = int(parent_message_id)
            except (ValueError, TypeError):
                parent_message_id = None

        max_curl_retries = 3
        r = None
        for curl_attempt in range(max_curl_retries + 1):
            try:
                pow_resp = self._get_pow(slot)
                s = self._ses(slot)
                body = {
                    "chat_session_id": chat_session_id,
                    "parent_message_id": parent_message_id,
                    "model_type": model_type,
                    "prompt": prompt,
                    "ref_file_ids": [],
                    "thinking_enabled": False,
                    "search_enabled": False,
                    "action": None,
                    "preempt": False,
                }
                if throttle:
                    self._throttle(slot, is_interim=True)
                r = requests.post(
                    f"{self.BASE_URL}/api/v0/chat/completion",
                    headers=self._headers(
                        slot,
                        pow_resp,
                        chat_session_id=chat_session_id,
                    ),
                    json=body,
                    cookies=s.cookies,
                    impersonate="chrome120",
                    stream=True,
                    timeout=120,
                )
                break
            except CurlError as e:
                if curl_attempt < max_curl_retries:
                    logger.info(
                        f"[RETRY] curl error in interim chunk (attempt {curl_attempt + 1}/{max_curl_retries}): {e}"
                    )
                    time.sleep(3)
                    continue
                raise

        if r is None:
            raise RuntimeError("Failed to establish connection for interim chunk")

        if r.status_code == 401:
            r.close()
            raise RuntimeError(f"DeepSeek auth error 401 for interim chunk (account {slot})")

        if r.status_code != 200:
            error_text = next(r.iter_lines(), b"").decode("utf-8", "ignore")
            r.close()
            raise RuntimeError(
                f"DeepSeek API error {r.status_code} in interim chunk: {error_text}"
            )

        resp_msg_id = None
        pre_lines: list[bytes] = []
        rate_limit_detected = False
        received_tokens = []
        try:
            for line in r.iter_lines():
                pre_lines.append(line)
                if not line:
                    continue
                decoded = line.decode("utf-8", "ignore")
                if decoded.startswith("data: "):
                    try:
                        d = json.loads(decoded[6:])
                        if not isinstance(d, dict):
                            continue
                        if d.get("type") == "error":
                            err = d.get("content", "Unknown error")
                            logger.error(f"[ERROR] DeepSeek error in interim chunk: {err}")
                            if any(k in err.lower() for k in ["rate limit", "server is busy", "try again", "unavailable"]):
                                rate_limit_detected = True
                                break
                            raise RuntimeError(f"DeepSeek interim error: {err}")
                        rid = d.get("response_message_id")
                        if rid is not None and resp_msg_id is None:
                            resp_msg_id = int(rid)
                        if "response" in d:
                            received_tokens.append(d["response"])
                            # Break once ACK is received or 3-5 tokens consumed so the message node is finalized
                            if "ACK" in "".join(received_tokens) or len(received_tokens) >= 5:
                                break
                    except json.JSONDecodeError:
                        pass
        finally:
            r.close()

        # Handle PoW invalidation and retries (similar to stream_completion)
        if resp_msg_id is None and pre_lines:
            raw_body = b"".join(pre_lines).decode("utf-8", "ignore")
            if "INVALID_POW_RESPONSE" in raw_body:
                logger.info(
                    f"[POW] INVALID_POW_RESPONSE in interim chunk (attempt {_retry + 1}) – clearing PoW cache and retrying..."
                )
                self._invalidate_pow(slot)
                if _retry < 3:
                    return self.send_interim_chunk(
                        slot,
                        chat_session_id,
                        prompt,
                        parent_message_id,
                        model_type=model_type,
                        _retry=_retry + 1,
                    )

        if rate_limit_detected:
            rate_limiter.set_limited(slot, time.time() + 30)
            raise DeepSeekRateLimitError(
                "DeepSeek rate limit: Server is busy in interim chunk", retry_after=30
            )

        if resp_msg_id is None:
            raw_snippet = b"".join(pre_lines[:5]).decode("utf-8", "ignore")[:500]
            if ("invalid message id" in raw_snippet.lower() or "biz_code\":26" in raw_snippet or "biz_code\": 26" in raw_snippet):
                logger.warning(
                    f"[PARENT_DESYNC] Detected invalid message id (parent={parent_message_id}) in interim chunk for session={chat_session_id}. Querying session history..."
                )
                real_last_id = self.get_last_message_id(slot, chat_session_id)
                if real_last_id != parent_message_id and _retry < 3:
                    logger.info(
                        f"[PARENT_AUTOCORRECT] Auto-corrected parent_message_id from {parent_message_id} to {real_last_id}. Retrying interim chunk..."
                    )
                    return self.send_interim_chunk(
                        slot,
                        chat_session_id,
                        prompt,
                        real_last_id,
                        model_type=model_type,
                        _retry=_retry + 1,
                    )
            logger.error(
                f"[CHUNK_INTERIM_ERROR] No response_message_id for interim chunk. Server output: {raw_snippet!r}"
            )
            raise RuntimeError(
                f"DeepSeek did not return response_message_id for interim chunk: {raw_snippet}"
            )

        logger.info(
            f"[CHUNK_INTERIM] Injected interim chunk ({len(prompt)} chars), "
            f"new parent_message_id={resp_msg_id}"
        )
        return resp_msg_id


# Global instances (moved from _server_legacy)
ap = AccountPool()
ds = DeepSeek(ap)
