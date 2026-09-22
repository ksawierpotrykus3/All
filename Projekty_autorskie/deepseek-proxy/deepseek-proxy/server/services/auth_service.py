"""Authentication service.

Handles Chrome/Playwright-based login flows to authenticate DeepSeek
web chat sessions.
"""

from __future__ import annotations

import os
import time
from typing import Any

from server.core.deepseek_client import Session
from server.logging import get_logger

logger = get_logger(__name__)


def _apply_stealth_patches(driver: "ChromiumPage") -> None:
    """Patch automation-detection markers in the browser JS context.

    Without these patches navigator.webdriver === true, which Cloudflare
    Turnstile and DeepSeek's bot-detection reads to flag automated browsers.
    """
    patches = """
        // 1. Hide webdriver flag
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });

        // 2. Fix navigator.plugins — empty in headless Chromium
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
            configurable: true
        });

        // 3. Fix navigator.languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        });

        // 4. Ensure window.chrome exists (absent in Chromium, present in Chrome retail)
        if (!window.chrome) {
            window.chrome = {
                runtime: { onMessage: { addListener: () => {} }, sendMessage: () => {} },
                loadTimes: function() {},
                csi: function() {}
            };
        }

        // 5. Remove Automation CDP Runtime marker
        delete window.__cdc_adoQpoasnfa76pfcZLmcfl_;
        delete window.__selenium_unwrapped;
        delete window.__webdriver_script_func;
    """
    try:
        driver.run_js(patches)
    except Exception as e:
        logger.info(f"[STEALTH] patch warning: {e}")


def authenticate_via_playwright(ap: Any, slot: int) -> str:
    """Open Chrome for manual sign-in, wait for completion, save session.

    This is a blocking sync function — call via asyncio.to_thread().
    """
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
    except ImportError:
        raise Exception("DrissionPage not installed. Run:  pip install DrissionPage")

    from server.utils.cloudflare import CloudflareBypasser
    from DrissionPage.errors import PageDisconnectedError

    data_dir = os.path.join(os.path.dirname(__file__), "..", ".chrome_slot", f"slot_{slot}")
    data_dir = os.path.normpath(data_dir)
    
    # ── Automatic Session & Profile Cleanup ─────────────────────────
    # Clear the memory cache and delete active slot session files
    ap.reset_slot(slot)
    
    # Delete the profile directory if it exists to guarantee a clean slate
    if os.path.exists(data_dir):
        logger.info(f"[AUTH] slot={slot} cleaning up old profile directory: {data_dir}")
        import shutil
        try:
            shutil.rmtree(data_dir)
        except Exception as cleanup_err:
            logger.info(f"[AUTH] slot={slot} profile cleanup error: {cleanup_err}")
            
    os.makedirs(data_dir, exist_ok=True)

    chrome_opt = (
        ChromiumOptions()
        .set_argument("--user-data-dir", data_dir)
        # Prevent automation detection flags
        .set_argument("--disable-blink-features=AutomationControlled")
        .set_argument("--no-sandbox")
        .set_argument("--disable-dev-shm-usage")
        # Prevent DrissionPage from attaching to an already-running Chrome instance.
        # auto_port=True picks a random free debugging port, guaranteeing isolation.
        .set_argument("--no-first-run")
        .set_argument("--no-default-browser-check")
        # Match Chrome 120 UA to remain consistent with curl_cffi impersonate="chrome120"
        .set_argument(
            "--user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        .auto_port()  # random free port → never attaches to existing Chrome window
    )
    driver = ChromiumPage(chrome_opt)
    try:
        # Apply stealth JS before any navigation so patches are active on page load
        _apply_stealth_patches(driver)

        driver.get("https://chat.deepseek.com/sign_in")

        # Re-apply after navigation (page context resets on navigation)
        _apply_stealth_patches(driver)

        cf = CloudflareBypasser(driver, max_retries=10, log=True)
        cf.bypass()

        logger.info(f"[AUTH] slot={slot} Waiting for user to sign in... (DO NOT close Chrome)")
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > 180:
                raise Exception("Authentication timed out after 180 seconds")
            try:
                url = driver.url
                if "/a/chat" in url or url.rstrip("/") == "https://chat.deepseek.com":
                    break
            except PageDisconnectedError:
                raise Exception("Browser was closed before sign-in completed.")
            time.sleep(2)

        token = driver.run_js(
            "try { return JSON.parse(localStorage.getItem('userToken')).value } catch(e) { return null }"
        )
        cookies = {c["name"]: c["value"] for c in driver.cookies()}
        user_agent = driver.user_agent
        driver.quit()

        ap.slots[slot] = Session(
            auth_token=token,
            cookies=cookies,
            user_agent=user_agent,
            created_at=time.time(),
            last_validated_at=time.time(),
        )
        ap.save(slot)
        # Reset the curl_cffi HTTP session so stale cookies from the old session
        # are not carried over into requests made with the new token.
        try:
            from server.core.deepseek_client import ds as _ds
            _ds.reset_http_session(slot)
        except Exception as e:
            logger.info(f"[AUTH] slot={slot} http session reset failed: {e}")
        # Reset pow cache on DeepSeek client
        if hasattr(ap, "_cached_pow"):
            ap._cached_pow = {}
        if hasattr(ap, "_pow_expires"):
            ap._pow_expires = {}
        # Flush ALL conv_state entries to prevent stale cross-slot chat IDs
        # (from other accounts) from causing 'invalid chat session id' on the
        # freshly-authenticated account.
        try:
            from server.services.state_service import conv_state, conv_lock
            with conv_lock:
                conv_state.clear()
            logger.info(f"[AUTH] slot={slot} conv_state fully cleared after login")
        except Exception as e:
            logger.info(f"[AUTH] slot={slot} conv_state clear failed: {e}")
        return f"Slot {slot} authenticated successfully"
    except Exception as e:
        import traceback

        traceback.print_exc()
        try:
            driver.quit()
        except Exception:
            pass
        raise



class AuthService:
    """Handles Chrome/Playwright-based authentication for DeepSeek web chat.

    Provides async methods wrapping the legacy sync authenticate_via_playwright.
    Uses a shared AccountPool instance (not creating new ones).
    """

    def __init__(self, pool: Any = None) -> None:
        """Initialize with an optional shared AccountPool.

        If pool is None, a new AccountPool is created (legacy fallback).
        """
        if pool is not None:
            self._pool = pool
        else:
            from server.core.deepseek_client import AccountPool
            self._pool = AccountPool()

    async def login(self, slot: int = 0) -> dict:
        """Trigger Chrome-based login for a given slot.

        Uses the shared AccountPool — saves session to both disk AND memory.
        Also resets rate limit for the slot so the new session is usable.
        Runs the blocking playwright flow in a thread executor.
        Returns a dict with status and message.
        """
        import asyncio
        from server.services.rate_limiter import rate_limiter

        rate_limiter.reset(slot)
        loop = asyncio.get_running_loop()

        def _bg():
            return authenticate_via_playwright(self._pool, slot)

        result = await loop.run_in_executor(None, _bg)
        return {"status": "ok", "message": result}
