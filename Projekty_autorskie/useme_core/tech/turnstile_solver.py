"""
Turnstile Solver Module for Camoufox Service

Feature 039: Camoufox Zombie Cleaner and Worker State Fix
Feature 041: Shadow DOM + Anti-detection hardening
  - Force-open closed shadow roots via add_init_script + live page evaluate
  - Bezier curve humanized mouse movements
  - Multi-strategy checkbox clicking with retry logic
  - Enhanced iframe detection (newer Turnstile URL patterns)
  - Visual checkbox/spinner state verification
"""

import asyncio
import json
import logging
import math
import os
import random
import re
import time
import unicodedata
from typing import Dict, Any, Optional
from urllib.parse import urlparse

# Import zombie cleanup utilities
from zombie_utils import reap_all_zombies, kill_process_tree

# Import Camoufox for real browser automation
try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    AsyncCamoufox = None

logger = logging.getLogger(__name__)

# Selectors
IFRAME_SELECTOR = 'iframe'

# ---------------------------------------------------------------------------
# Turnstile iframe URL patterns (ordered by specificity)
# ---------------------------------------------------------------------------
TURNSTILE_URL_PATTERNS = [
    'challenges.cloudflare.com',
    '/cdn-cgi/challenge-platform/',       # Newer Turnstile pattern (2024+)
    '/turnstile/',
    'challenge-platform',
]

# ---------------------------------------------------------------------------
# Multi-language CF interstitial title phrases (lowercase matching)
# ---------------------------------------------------------------------------
CF_INTERSTITIAL_TITLES = [
    # English
    'just a moment', 'attention required', 'checking your browser', 'please wait',
    'one more step', 'cloudflare', 'ddos protection', 'verify', 'challenge',
    'blocked', 'access denied', 'rate limited', 'under review', 'loading',
    # Vietnamese
    'chờ một chút', 'đợi một lát', 'xác minh', 'kiểm tra', 'đang tải',
    # Portuguese
    'um momento', 'aguarde', 'verificando', 'atenção', 'carregando',
    # Spanish
    'un momento', 'espere', 'comprobando', 'cargando',
    # German
    'einen moment', 'warten', 'überprüfung', 'laden',
    # French
    'un instant', 'attendez', 'vérification', 'chargement',
    # Dutch
    'een moment', 'wachten', 'controle', 'laden',
    # Japanese
    'しばらく', 'お待ち', '確認', '待って',
    # Chinese
    '请等待', '稍候', '验证', '检查', '加载',
    # Korean
    '잠시', '기다려', '확인', '검사', '로딩',
    # Russian
    'подождите', 'ожидание', 'проверка', 'загрузка',
    # Arabic
    'لحظة', 'انتظر', 'تحقق', 'جاري',
    # Indonesian / Malay
    'hanya sebentar', 'sebentar', 'memeriksa', 'perlindungan ddos',
    'mohon tunggu', 'sedang memuat', 'menunggu',
    # Italian
    'ci siamo quasi',
    # Other languages
    'moment', 'attendre', 'aspettare', 'esperar', 'warten',
    'одна секунда', 'сейчас', 'минуту', 'секунду',
    'čekejte', 'počakajte', 'vent', 'vänta', 'ο moment',
]

# Normalize to NFC for consistent matching regardless of browser Unicode form
CF_INTERSTITIAL_TITLES = [unicodedata.normalize('NFC', t) for t in CF_INTERSTITIAL_TITLES]


def _normalize_title(title: str) -> str:
    """Normalize page title to NFC for consistent matching.
    
    Browsers may return titles in NFD (decomposed) form for Vietnamese
    and other diacritic-heavy languages, while Python source code uses
    NFC (precomposed). Normalizing both sides ensures consistent matching.
    """
    return unicodedata.normalize('NFC', title.lower()) if title else ''

# ---------------------------------------------------------------------------
# Force-open closed shadow roots init script
# ---------------------------------------------------------------------------
SHADOW_DOM_FORCE_OPEN_SCRIPT = """
() => {
    const originalAttachShadow = Element.prototype.attachShadow;
    Element.prototype.attachShadow = function(init) {
        if (init && init.mode === 'closed') {
            return originalAttachShadow.call(this, {...init, mode: 'open'});
        }
        return originalAttachShadow.call(this, init);
    };
}
"""

# ---------------------------------------------------------------------------
# Live-page shadow DOM force-open evaluate (for already loaded pages)
# ---------------------------------------------------------------------------
SHADOW_DOM_FORCE_OPEN_LIVE = """
() => {
    function forceOpenShadowRoots(root, depth) {
        if (!root || depth > 30) return;
        try {
            for (let el of root.querySelectorAll('*')) {
                try {
                    if (el.shadowRoot && el.shadowRoot.mode === 'closed') {
                        // Override attachShadow to return open mode on next call
                        const orig = el.attachShadow;
                        el.attachShadow = function(init) {
                            return orig.call(this, {...init, mode: 'open'});
                        };
                    }
                } catch(e) {}
                try {
                    if (el.shadowRoot) {
                        forceOpenShadowRoots(el.shadowRoot, depth + 1);
                    }
                } catch(e) {}
            }
        } catch(e) {}
    }
    forceOpenShadowRoots(document, 0);
    return true;
}
"""


# ---------------------------------------------------------------------------
# Bezier curve helpers for humanized mouse movement
# ---------------------------------------------------------------------------

def _bezier_point(t: float, p0: tuple, p1: tuple, p2: tuple, p3: tuple) -> tuple:
    """Cubic bezier interpolation."""
    mt = 1 - t
    x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
    y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


async def human_mouse_move(page, target_x: float, target_y: float, steps: int = 25) -> None:
    """Move mouse from current position to target using bezier curve with variable speed.

    Simulates natural human mouse movement with:
    - Cubic bezier path (not a straight line)
    - Variable speed (acceleration at start, deceleration at end)
    - Small random jitter on each step
    - Realistic step timing
    - Uses estimated current position (not random) for natural transition
    """
    try:
        viewport = page.viewport_size
        if viewport:
            # Use a plausible "last known" position based on viewport center area
            # rather than fully random — more natural for consecutive movements
            center_x = viewport['width'] / 2
            center_y = viewport['height'] / 2
            start_x = center_x + random.uniform(-150, 150)
            start_y = center_y + random.uniform(-150, 150)
            # Clamp to viewport
            start_x = max(50, min(start_x, viewport['width'] - 50))
            start_y = max(50, min(start_y, viewport['height'] - 50))
        else:
            start_x = random.randint(200, 800)
            start_y = random.randint(200, 600)

        # Generate control points with curvature
        dx = target_x - start_x
        dy = target_y - start_y
        cp1_x = start_x + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
        cp1_y = start_y + dy * random.uniform(0.1, 0.3) + random.uniform(-80, 80)
        cp2_x = start_x + dx * random.uniform(0.6, 0.8) + random.uniform(-50, 50)
        cp2_y = start_y + dy * random.uniform(0.7, 0.9) + random.uniform(-40, 40)

        p0 = (start_x, start_y)
        p1 = (cp1_x, cp1_y)
        p2 = (cp2_x, cp2_y)
        p3 = (target_x, target_y)

        for i in range(steps + 1):
            t = i / steps
            # Ease-out timing: faster at start, slower at end
            eased_t = 1 - (1 - t) ** 3
            x, y = _bezier_point(eased_t, p0, p1, p2, p3)
            # Add micro-jitter
            jitter_scale = 0.5 * (1 - t) + 1.5  # less jitter at end
            x += random.gauss(0, jitter_scale)
            y += random.gauss(0, jitter_scale)
            await page.mouse.move(x, y)
            # Variable delay: faster in middle, slower at edges
            if t < 0.15 or t > 0.85:
                await asyncio.sleep(random.uniform(0.008, 0.025))
            else:
                await asyncio.sleep(random.uniform(0.003, 0.010))
    except Exception as e:
        logger.debug(f"[human_mouse_move] Bezier movement failed: {e}, using direct move")
        try:
            await page.mouse.move(target_x, target_y)
        except Exception:
            pass


async def human_click(page, x: float = None, y: float = None, target_locator=None) -> bool:
    """Perform a human-like click with approach, micro-delay, and natural release.

    Args:
        page: Playwright page object
        x, y: Optional coordinates (used if no locator provided)
        target_locator: Optional Playwright locator (preferred)

    Returns:
        bool: True if click succeeded
    """
    try:
        if target_locator:
            try:
                box = await target_locator.bounding_box()
                if box:
                    x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
                    y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
            except Exception:
                pass

        if x is None or y is None:
            return False

        # Move to position with human-like path
        await human_mouse_move(page, x, y)

        # Brief hover before click (natural behavior)
        await asyncio.sleep(random.uniform(0.05, 0.15))

        # Click with natural timing
        await page.mouse.click(x, y)

        # Brief post-click pause
        await asyncio.sleep(random.uniform(0.05, 0.12))
        return True
    except Exception as e:
        logger.debug(f"[human_click] Failed: {e}")
        if x is not None and y is not None:
            try:
                await page.mouse.click(x, y)
                return True
            except Exception:
                return False
        return False


async def human_scroll(page, direction: str = 'down', distance: int = None) -> None:
    """Perform a human-like scroll to simulate reading behavior."""
    try:
        if distance is None:
            distance = random.randint(100, 400)
        if direction == 'up':
            distance = -distance

        await page.mouse.wheel(0, distance)
        await asyncio.sleep(random.uniform(0.3, 0.8))
    except Exception as e:
        logger.debug(f"[human_scroll] Failed: {e}")


class TurnstileSolver:
    """
    Handles two CF modes:
    1. Managed Challenge — resolves, just wait
    2. Interactive Turnstile — click the checkbox

    Feature 041: Uses force-open shadow roots + humanized bezier clicks
    for anti-detection hardening.
    """

    # Checkbox selectors inside Turnstile iframe (ordered by specificity)
    CHECKBOX_SELECTORS = [
        '#challenge-stage input[type="checkbox"]',
        '.ctp-checkbox-container input[type="checkbox"]',
        '.cb-i input[type="checkbox"]',
        '.challenge-view input[type="checkbox"]',
        'input[type="checkbox"]',
        '.checkbox',
        '[role="checkbox"]',
    ]

    def __init__(self, page: Any, worker_id: str = 'unknown'):
        self.page = page
        self.worker_id = worker_id
        self._solve_attempts = 0
        self._target_frame = None

    def _log(self, level: str, msg: str) -> None:
        """Centralized logging with worker_id prefix."""
        log_func = getattr(logger, level, logger.info)
        log_func(f"[TURNSTILE][{self.worker_id}] {msg}")

    # -----------------------------------------------------------------------
    # Shadow DOM support
    # -----------------------------------------------------------------------

    async def inject_shadow_dom_force_open(self) -> None:
        """Inject init script to force all shadow roots to open mode before page loads."""
        try:
            await self.page.add_init_script(SHADOW_DOM_FORCE_OPEN_SCRIPT)
            self._log('debug', "Shadow DOM force-open script injected (init)")
        except Exception as e:
            self._log('debug', f"Shadow DOM injection skipped: {e}")

    async def force_shadow_dom_open_live(self) -> bool:
        """Try to force-open shadow roots on an already loaded page."""
        try:
            result = await asyncio.wait_for(
                self.page.evaluate(SHADOW_DOM_FORCE_OPEN_LIVE),
                timeout=2.0
            )
            if result:
                self._log('debug', "Shadow DOM force-open applied to live page")
                return True
        except asyncio.TimeoutError:
            self._log('debug', "Shadow DOM live force-open timed out (non-critical)")
        except Exception as e:
            self._log('debug', f"Shadow DOM live force-open failed: {e}")
        return False

    # -----------------------------------------------------------------------
    # Challenge detection
    # -----------------------------------------------------------------------

    async def detect_challenge(self) -> bool:
        """Detect if a Cloudflare challenge is present on the page."""
        try:
            return await asyncio.wait_for(self._detect_challenge_impl(), timeout=5.0)
        except asyncio.TimeoutError:
            self._log('warning', "detect_challenge TIMEOUT after 5s — assuming challenge present")
            return True
        except Exception as e:
            self._log('warning', f"detect_challenge error: {e}")
            return False

    async def _detect_challenge_impl(self) -> bool:
        """Core challenge detection logic."""
        try:
            title = await asyncio.wait_for(self.page.title(), timeout=3.0)
            title_normalized = _normalize_title(title)
            if any(phrase in title_normalized for phrase in CF_INTERSTITIAL_TITLES):
                return True
        except asyncio.TimeoutError:
            return True
        except Exception:
            pass

        # Check for CF-specific DOM elements
        try:
            cf_indicators = [
                '#challenge-running',
                '#challenge-stage',
                '#cf-challenge-running',
                '[id*="challenge"]',
                '.ctp-checkbox-container',
                '#turnstile-wrapper',
            ]
            for indicator in cf_indicators:
                try:
                    if await self.page.locator(indicator).count() > 0:
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        # Check page content for CF markers (old solver also did this)
        try:
            content = await asyncio.wait_for(self.page.content(), timeout=5.0)
            if any(m in content.lower() for m in ["__cf_chl_rt_tk", "cf-challenge", "cf_chl"]):
                return True
        except Exception:
            pass

        return False

    # -----------------------------------------------------------------------
    # Token-based detection (auto-solve for invisible/managed challenges)
    # -----------------------------------------------------------------------

    async def _wait_for_token(self, timeout: float) -> Optional[str]:
        """Wait for Turnstile to auto-issue a valid token.

        Uses page.wait_for_function() to detect when the hidden
        cf-turnstile-response input gets a value > 100 chars.
        This works for invisible/managed challenges where the
        browser fingerprint + proxy are trusted enough.

        Returns the token string, or None if no token appeared.
        """
        try:
            token = await asyncio.wait_for(
                self.page.evaluate("""() => {
                    const el = document.querySelector('[name="cf-turnstile-response"]');
                    if (!el || !el.value || el.value.length < 100) return null;
                    const el2 = document.querySelector('[name="cf-turnstile-response"]');
                    return el2 ? el2.value : null;
                }"""),
                timeout=0.5,
            )
            if token:
                self._log('info', f"Token already present (len={len(token)})")
                return token
        except Exception:
            pass

        try:
            token = await asyncio.wait_for(
                self.page.wait_for_function(
                    """() => {
                        const el = document.querySelector('[name="cf-turnstile-response"]');
                        return el && el.value && el.value.length > 100 ? el.value : null;
                    }""",
                    timeout=int(timeout * 1000),
                ),
                timeout=timeout + 1.0,
            )
            token_value = None
            try:
                token_value = await token.json_value()
            except Exception:
                pass
            if token_value:
                tlen = len(str(token_value))
                self._log('info', f"Auto-token appeared (len={tlen})")
                return str(token_value)
            return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self._log('debug', f"_wait_for_token error: {e}")
            return None

    # -----------------------------------------------------------------------
    # Main solve flow
    # -----------------------------------------------------------------------

    async def solve(self, timeout: float = 45.0) -> bool:
        """Zero-polling solve — behaves like a real human.

        A real user does NOT:
        - Poll for tokens via page.evaluate()
        - Check page content via page.content()
        - Query DOM for iframes/locators during JS Challenge
        - Move mouse or scroll during 'Just a moment...'

        Approach:
        1. Quick cookie check (page.context.cookies = CDP, not JS)
        2. Single lightweight title check to detect JS Challenge vs Turnstile
        3. JS Challenge → _solve_managed() directly (zero-polling cookie wait)
        4. Turnstile iframe → _solve_interactive()
        5. No challenge → short passive wait for cookie
        """
        self._solve_attempts = 0
        self._target_frame = None
        start = asyncio.get_event_loop().time()
        self._log('info', "Starting solve...")

        # Step 1: Quick cookie check — valid cf_clearance from previous session
        try:
            _cookies = await self.page.context.cookies()
            for c in _cookies:
                if c['name'] == 'cf_clearance':
                    _val = c.get('value', '') or ''
                    if len(_val) < self._MIN_CF_CLEARANCE_LENGTH:
                        self._log('debug', f"cf_clearance present but too short (len={len(_val)}) — will re-solve")
                        continue
                    _expires = c.get('expires', 0)
                    if _expires > 0 and time.time() < _expires:
                        # Cookie valid — verify page isn't still on challenge
                        try:
                            _t = await asyncio.wait_for(self.page.title(), timeout=2.0)
                            _tn = _normalize_title(_t)
                            if not any(p in _tn for p in CF_INTERSTITIAL_TITLES):
                                self._log('info', f"Fast path: valid cf_clearance, page loaded (title: {_t[:50]})")
                                return True
                        except Exception:
                            pass
                    self._log('debug', "Stale cf_clearance present — will re-solve")
        except Exception:
            pass

        # Step 2: Single lightweight title check to determine challenge type
        _is_js_challenge = False
        try:
            _title = await asyncio.wait_for(self.page.title(), timeout=3.0)
            _title_norm = _normalize_title(_title)
            if any(p in _title_norm for p in CF_INTERSTITIAL_TITLES):
                _is_js_challenge = True
                self._log('info', f"JS Challenge detected ('{_title[:60]}') — passive wait")
            else:
                self._log('info', f"No CF interstitial (title: {_title[:50]})")
                # Check if page has cf_clearance already
                if await self._has_clearance_cookie():
                    return True
                # Check if page has real content (no CF at all)
                # Threshold: cardmarket product pages are 20KB+; Cloudflare "Loading" pages
                # are ~300-500B. Require at least 2KB to consider it real content.
                try:
                    _body = await asyncio.wait_for(
                        self.page.evaluate("() => document.body?.innerText?.length || 0"),
                        timeout=2.0
                    )
                    if _body > 2000:
                        self._log('info', f"Page loaded with {_body}B content — no CF challenge")
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        # Step 3: Route to appropriate solver based on challenge type
        solve_success = False
        if _is_js_challenge:
            # JS Challenge (IUAM): no iframe, no Turnstile — just wait for cookie
            self._log('info', "JS Challenge detected — managed solve")
            solve_success = await asyncio.wait_for(
                self._solve_managed(timeout, start),
                timeout=max(10.0, timeout * 0.8),
            )
            if not solve_success:
                self._log('warning', "Managed solve failed — trying interactive as fallback")
                solve_success = await asyncio.wait_for(
                    self._solve_interactive(timeout, start),
                    timeout=max(10.0, timeout * 0.8),
                )
            self._log('info', f"[DIAG] Turnstile result={'ok' if solve_success else 'fail'} "
                              f"duration={asyncio.get_event_loop().time() - start:.1f}s")
            return solve_success

        # Step 4: Check for Turnstile iframe (interactive challenge)
        try:
            _has_visible_iframe = await self._find_visible_iframe()
            if _has_visible_iframe:
                self._log('info', "Turnstile iframe detected — interactive solve")
                solve_success = await asyncio.wait_for(
                    self._solve_interactive(timeout, start),
                    timeout=max(10.0, timeout * 0.8),
                )
                if not solve_success:
                    self._log('warning', "Interactive solve failed — trying managed as fallback")
                    solve_success = await asyncio.wait_for(
                        self._solve_managed(timeout, start),
                        timeout=max(10.0, timeout * 0.8),
                    )
                self._log('info', f"[DIAG] Turnstile result={'ok' if solve_success else 'fail'} "
                                  f"duration={asyncio.get_event_loop().time() - start:.1f}s")
                return solve_success
        except Exception:
            pass

        # Step 5: Fallback — passive cookie wait for edge cases
        if await self._has_clearance_cookie():
            self._log('info', "cf_clearance appeared — success")
            return True

        self._log('info', "No challenge detected and no cookie — short passive wait")
        _deadline = time.monotonic() + 10.0
        while time.monotonic() < _deadline:
            await asyncio.sleep(1.0)
            if await self._has_clearance_cookie():
                self._log('info', "cf_clearance appeared during fallback wait")
                return True

        self._log('info', "Solve failed — no challenge, no cookie")
        return False

    # -----------------------------------------------------------------------
    # Managed challenge (no iframe — just wait)
    # -----------------------------------------------------------------------

    async def _solve_managed(self, timeout: float, start: float) -> bool:
        """Passive JS Challenge wait — NO page interaction.

        Cloudflare's JS Challenge (IUAM) runs automated JavaScript in the page.
        A real user sees "Just a moment..." and waits passively — no mouse
        movement, no scrolling, no clicking.

        Previous approach polled the page every 0.5-1s using page.evaluate(),
        page.title(), page.content(), detect_challenge() — ALL detectable via
        Playwright's CDP/Juggler protocol traffic during the challenge period.

        This approach:
        1. Uses Playwright's event listeners (non-intrusive)
        2. Polls cookies via page.context.cookies() every 3s (not 0.5s)
           — page.context.cookies() is a CDP call, NOT page.evaluate()
        3. No page.evaluate(), page.title(), page.content() during wait
        4. No mouse/scroll interactions during challenge
        5. Detects redirect via framenavigated event
        """
        max_managed_wait = min(60.0, timeout * 0.7)

        # Track cookies at start to detect when cf_clearance appears
        try:
            _initial = await self.page.context.cookies()
            _initial_names = {c['name'] for c in _initial}
        except Exception:
            _initial_names = set()

        # Set up passive redirect detection — non-intrusive event listener
        _navigated_event = asyncio.Event()
        async def _on_nav(_frame):
            _navigated_event.set()
        self.page.on('framenavigated', _on_nav)

        managed_start = time.monotonic()
        try:
            while True:
                elapsed = time.monotonic() - start
                if elapsed > timeout:
                    self._log('error', f"Managed challenge timeout after {elapsed:.1f}s")
                    return False

                # Check elapsed, wait up to 3s
                remaining_in_loop = max_managed_wait - (time.monotonic() - managed_start)
                if remaining_in_loop <= 0:
                    break

                _wait = min(3.0, remaining_in_loop, max(0.5, timeout - elapsed))
                try:
                    await asyncio.wait_for(_navigated_event.wait(), timeout=_wait)
                except asyncio.TimeoutError:
                    pass

                # Check cookie via Playwright CDP (NOT page.evaluate — no JS injection)
                try:
                    _cookies = await self.page.context.cookies()
                    for c in _cookies:
                        if c['name'] == 'cf_clearance':
                            _val = c.get('value', '') or ''
                            if len(_val) < self._MIN_CF_CLEARANCE_LENGTH:
                                self._log('info',
                                    f"cf_clearance appeared but too short (len={len(_val)}, "
                                    f"need >={self._MIN_CF_CLEARANCE_LENGTH}) — waiting for real clearance"
                                )
                                continue
                            _domain = c.get('domain', '') or ''
                            if "challenges.cloudflare.com" in _domain:
                                self._log('info',
                                    f"cf_clearance appeared but domain={_domain} (iframe) — "
                                    f"waiting for real page clearance"
                                )
                                continue
                            # Found valid cf_clearance with real value and correct domain
                            # CRITICAL: Do NOT return True immediately — Cloudflare's Precursor
                            # Clearance sets cf_clearance cookie with valid length but the page
                            # is still blocked. Real Challenge Clearance causes an auto-redirect
                            # (framenavigated event) within 1-3s. Precursor clearance does NOT.
                            # Wait for the redirect to confirm this is real clearance.
                            _pre_redirect = time.monotonic()
                            try:
                                await asyncio.wait_for(_navigated_event.wait(), timeout=5.0)
                                # Reset event for subsequent iterations if needed
                                _navigated_event.clear()
                                _total = time.monotonic() - start
                                self._log('info',
                                    f"Solved (cookie appeared + redirect confirmed in "
                                    f"{time.monotonic() - _pre_redirect:.1f}s) in {_total:.1f}s"
                                )
                                return True
                            except asyncio.TimeoutError:
                                _elapsed = time.monotonic() - _pre_redirect
                                self._log('info',
                                    f"cf_clearance appeared (len={len(_val)}, domain={_domain}) "
                                    f"but no redirect in {_elapsed:.1f}s — precursor clearance, "
                                    f"continuing wait for real clearance"
                                )
                                continue
                except Exception:
                    await asyncio.sleep(0.5)

            # Managed wait exhausted — fall back to JS challenge solver
            managed_elapsed = time.monotonic() - managed_start
            self._log('info', f"Managed wait {managed_elapsed:.1f}s without cookie — JS challenge fallback")
            return await self._solve_js_challenge(timeout, start)

        finally:
            try:
                self.page.remove_listener('framenavigated', _on_nav)
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # JS challenge (no iframe, just wait for cookie — fallback from managed)
    # -----------------------------------------------------------------------

    async def _solve_js_challenge(self, timeout: float, start: float) -> bool:
        """JS-based CF challenge (no Turnstile iframe) — truly passive wait for auto-resolve.

        Does NOT:
        - Move mouse or scroll (detectable by CF during JS challenge)
        - Call detect_challenge() (page.evaluate = detectable CDP traffic)
        - Call _find_visible_iframe() (same)
        - Abort early (let the full timeout run)

        Only polls cf_clearance cookie via Playwright CDP every 3s.
        A real user sits still during "Just a moment..." — so do we.
        """
        self._log('info', f"Starting JS challenge wait (timeout={timeout:.0f}s)")
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout:
                self._log('error', f"JS challenge timeout after {elapsed:.1f}s")
                return False

            if await self._has_clearance_cookie():
                self._log('info', f"JS challenge solved (cookie appeared) in {elapsed:.1f}s")
                return True

            # No page interaction during JS challenge — just wait
            await asyncio.sleep(3.0)

    # -----------------------------------------------------------------------
    # Interactive solve (click checkbox)
    # -----------------------------------------------------------------------

    async def _solve_interactive(self, timeout: float, start: float) -> bool:
        """Interactive Turnstile — find and click the checkbox with humanized interaction."""
        # Fast-fail: if challenge is not detectable and no iframe, don't waste time
        if not await self.detect_challenge():
            if not await self._has_clearance_cookie():
                self._log('warning', "No challenge detected and no cf_clearance — failing fast")
                return False
            self._log('info', "No challenge detected but cf_clearance present — success")
            return True
        if not await self._find_visible_iframe():
            if await self._has_clearance_cookie():
                self._log('info', "No iframe but cf_clearance present — success")
                return True
            self._log('warning', "No Turnstile iframe found — failing fast")
            return False

        clicked = False
        missed_iframes = 0
        _t_solve_start = time.monotonic()

        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout:
                _solve_time = time.monotonic() - _t_solve_start
                self._log('error', f"Interactive solve timeout after {elapsed:.1f}s")
                return False

            self._solve_attempts += 1

            # Check if already solved
            if await self._has_clearance_cookie():
                # Verify: cookie exists AND challenge page is gone
                if not await self.detect_challenge():
                    _solve_time = time.monotonic() - _t_solve_start
                    self._log('info', f"Solved (Confirmed by cookie & title)! (solve_time={_solve_time:.2f}s)")
                    return True
                # Cookie exists but challenge page still visible — wait briefly for redirect
                self._log('debug', "cf_clearance present but challenge still detected — waiting for redirect")
                await asyncio.sleep(5.0)
                if await self._has_clearance_cookie():
                    # Cookie persisted — accept it, the redirect might not happen
                    _solve_time = time.monotonic() - _t_solve_start
                    self._log('info', f"Solved (cf_clearance confirmed after wait)! (solve_time={_solve_time:.2f}s)")
                    return True
                self._log('debug', "cf_clearance lost after wait — continuing solve")

            if not await self.detect_challenge():
                if await self._has_clearance_cookie():
                    return True
                # Challenge disappeared but no cookie yet — brief wait
                for _ in range(3):
                    await asyncio.sleep(0.5)
                    if await self._has_clearance_cookie():
                        return True

            # Limit attempts
            if self._solve_attempts > 15:
                self._log('warning', "Persistent failure after 15 attempts — giving up")
                return False

            # Find iframe if not yet found or periodic retry
            if not clicked or (self._solve_attempts % 3 == 0):
                if not await self._find_visible_iframe():
                    missed_iframes += 1
                    if missed_iframes > 5:
                        self._log('warning', "No iframe after 5 attempts — aborting")
                        return False
                    await asyncio.sleep(1.0)
                    # Re-check challenge before retry
                    if not await self.detect_challenge():
                        if await self._has_clearance_cookie():
                            return True
                        # Challenge might have auto-resolved — wait briefly
                        await asyncio.sleep(1.0)
                        if await self._has_clearance_cookie():
                            return True
                else:
                    missed_iframes = 0

                # Try clicking with humanized approach
                clicked = await self._try_click_turnstile()
                if clicked:
                    self._log('info', f"Click attempt #{self._solve_attempts}. Waiting for resolution...")

            # Wait for clearance after click
            # Use wait_for_function to detect the cf-turnstile-response token
            # instead of polling cookies() which is slow and unreliable.
            _post_click_timeout = 8.0 if clicked else 3.0
            try:
                _token_payload = await asyncio.wait_for(
                    self.page.wait_for_function(
                        """() => {
                            const el = document.querySelector('[name="cf-turnstile-response"]');
                            const hasToken = el && el.value && el.value.length > 100;
                            const hasCookie = document.cookie.includes('cf_clearance');
                            return hasToken || hasCookie ? { token: el ? el.value : null, cookie: hasCookie } : null;
                        }""",
                        timeout=int(_post_click_timeout * 1000),
                    ),
                    timeout=_post_click_timeout + 1.0,
                )
                _resolution = await _token_payload.json_value()
                if _resolution and (_resolution.get('cookie') or _resolution.get('token')):
                    if _resolution.get('cookie') or await self._has_clearance_cookie():
                        self._log('info', f"Solved after click ({'cookie' if _resolution.get('cookie') else 'token'} detected)!")
                        return True
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

            if not await self.detect_challenge():
                await asyncio.sleep(0.5)
                if await self._has_clearance_cookie():
                    return True

            # Re-apply shadow DOM force-open periodically
            if self._solve_attempts % 5 == 0:
                await self.force_shadow_dom_open_live()

    # -----------------------------------------------------------------------
    # Iframe detection
    # -----------------------------------------------------------------------

    async def _find_visible_iframe(self) -> bool:
        """Check if a visible Turnstile iframe exists (with force-open shadow DOM support).

        Uses three methods in cascade:
        1. Playwright frame list (fastest)
        2. JS deep traversal through shadow roots
        3. Playwright locator (pierces open shadow DOM)
        """
        try:
            # Method 1: Check all Playwright-managed frames (fastest, covers open shadow DOM)
            for frame in self.page.frames:
                try:
                    url = frame.url
                    if any(pattern in url for pattern in TURNSTILE_URL_PATTERNS):
                        # Verify: actual Turnstile widget DOM must exist
                        # Generic CF challenge platform iframes match the URL pattern
                        # but have no checkbox — clicking does nothing
                        try:
                            _has_turnstile = await self.page.locator('.ctp-checkbox-container').count() > 0
                            _has_challenge_stage = await self.page.locator('#challenge-stage').count() > 0
                            if not _has_turnstile and not _has_challenge_stage:
                                self._log('debug', "iframe URL matches but no Turnstile DOM — treating as managed challenge")
                                self._target_frame = None
                                return False
                        except Exception:
                            pass  # if check fails, proceed with found iframe
                        self._target_frame = frame
                        self._log('debug', f"iframe found via frame.url: {url[:80]}")
                        return True
                except Exception:
                    continue

            # Method 2: Deep JS traversal through all shadow roots (now force-opened)
            try:
                patterns_js = json.dumps(TURNSTILE_URL_PATTERNS)
                found = await asyncio.wait_for(
                    self.page.evaluate(f"""(patterns) => {{
                        function findIframeInShadow(root, depth) {{
                            if (!root || depth > 25) return false;
                            try {{
                                for (let iframe of root.querySelectorAll('iframe')) {{
                                    let src = (iframe.src || '').toLowerCase();
                                    let name = (iframe.name || '').toLowerCase();
                                    let id = (iframe.id || '').toLowerCase();
                                    for (let p of patterns) {{
                                        if (src.includes(p) || name.includes('turnstile') || id.includes('turnstile') || name.includes('challenge') || id.includes('challenge')) {{
                                            return true;
                                        }}
                                    }}
                                }}
                            }} catch(e) {{}}
                            try {{
                                for (let el of root.querySelectorAll('*')) {{
                                    if (el.shadowRoot) {{
                                        if (findIframeInShadow(el.shadowRoot, depth + 1)) return true;
                                    }}
                                }}
                            }} catch(e) {{}}
                            if (root instanceof ShadowRoot) {{
                                try {{
                                    for (let iframe of root.querySelectorAll('iframe')) {{
                                        let src = (iframe.src || '').toLowerCase();
                                        for (let p of patterns) {{
                                            if (src.includes(p)) return true;
                                        }}
                                    }}
                                }} catch(e) {{}}
                            }}
                            return false;
                        }}
                        return findIframeInShadow(document, 0);
                    }}""", {patterns_js}),
                    timeout=3.0
                )
            except asyncio.TimeoutError:
                self._log('debug', "JS iframe detection timed out")
                found = False
            except Exception as e:
                self._log('debug', f"JS iframe detection error: {e}")
                found = False

            if found:
                # Verify Turnstile DOM exists before accepting generic CF iframe
                try:
                    _has_turnstile = await self.page.locator('.ctp-checkbox-container').count() > 0
                    _has_challenge_stage = await self.page.locator('#challenge-stage').count() > 0
                    if not _has_turnstile and not _has_challenge_stage:
                        self._log('debug', "JS found iframe but no Turnstile DOM — treating as managed challenge")
                        found = False
                except Exception:
                    pass
            if found:
                # Re-lookup frame after JS detection
                for frame in self.page.frames:
                    try:
                        if any(pattern in frame.url for pattern in TURNSTILE_URL_PATTERNS):
                            self._target_frame = frame
                            self._log('debug', "iframe frame mapped after JS detection")
                            return True
                    except Exception:
                        continue
                self._log('debug', "iframe found via JS but couldn't map to frame object")
                return True  # found but couldn't map to frame object

            # Method 3: Playwright locator (auto-pierces open shadow DOM)
            locators = self.page.locator(IFRAME_SELECTOR)
            count = await locators.count()
            for i in range(count):
                try:
                    iframe_ptr = locators.nth(i)
                    src = await iframe_ptr.get_attribute('src') or ""
                    name = await iframe_ptr.get_attribute('name') or ""
                    id_attr = await iframe_ptr.get_attribute('id') or ""
                    if any(pattern in src for pattern in TURNSTILE_URL_PATTERNS) or \
                       'turnstile' in name.lower() or 'challenge' in name.lower() or \
                       'turnstile' in id_attr.lower() or 'challenge' in id_attr.lower():
                        box = await iframe_ptr.bounding_box()
                        if box and box['width'] > 20:
                            # Verify Turnstile DOM exists before accepting generic CF iframe
                            try:
                                _has_turnstile = await self.page.locator('.ctp-checkbox-container').count() > 0
                                _has_challenge_stage = await self.page.locator('#challenge-stage').count() > 0
                                if not _has_turnstile and not _has_challenge_stage:
                                    self._log('debug', "locator found iframe but no Turnstile DOM — treating as managed challenge")
                                    continue
                            except Exception:
                                pass
                            for frame in self.page.frames:
                                if any(pattern in frame.url for pattern in TURNSTILE_URL_PATTERNS):
                                    self._target_frame = frame
                                    break
                            if not self._target_frame:
                                self._log('debug', "iframe found via locator but no matching frame")
                            return True
                except Exception:
                    continue

        except Exception as e:
            self._log('debug', f"Error in iframe detection: {e}")
        return False

    # -----------------------------------------------------------------------
    # Checkbox clicking
    # -----------------------------------------------------------------------

    async def _try_click_turnstile(self) -> bool:
        """Click the Turnstile checkbox using humanized bezier movement.

        Uses 3 strategies in sequence:
        1. JS evaluate inside iframe (penetrates closed Shadow DOM within same-origin frame)
        2. Frame-element bounding box coordinate clicks (reliable for cross-origin iframes)
        3. dispatchEvent on frame element (triggers click at browser event level)

        Each strategy tries multiple positions with human-like timing.
        """
        if not self._target_frame:
            return False

        # -----------------------------------------------------------------------
        # Strategy 1: JS evaluate inside the iframe
        # This penetrates closed Shadow DOM within the iframe's own origin.
        # frame.evaluate() works because we're inside challenges.cloudflare.com.
        # -----------------------------------------------------------------------
        try:
            self._log('debug', "Strategy 1: JS evaluate inside iframe")
            clicked = await asyncio.wait_for(
                self._target_frame.evaluate("""() => {
                    function findCheckbox(root, depth) {
                        if (!root || depth > 30) return null;
                        // Direct CSS selectors
                        const selectors = [
                            'input[type="checkbox"]',
                            '[role="checkbox"]',
                            '.ctp-checkbox-container input',
                            '.challenge-view input',
                            '#challenge-stage input',
                        ];
                        for (let sel of selectors) {
                            try {
                                let el = root.querySelector(sel);
                                if (el) return el;
                            } catch(e) {}
                        }
                        // Search inside shadow roots recursively
                        let all = root.querySelectorAll('*');
                        for (let el of all) {
                            if (el.shadowRoot) {
                                let found = findCheckbox(el.shadowRoot, depth + 1);
                                if (found) return found;
                            }
                        }
                        // If root itself is a shadow root, search it too
                        if (root instanceof ShadowRoot) {
                            for (let sel of selectors) {
                                try {
                                    let el = root.querySelector(sel);
                                    if (el) return el;
                                } catch(e) {}
                            }
                        }
                        return null;
                    }
                    let cb = findCheckbox(document, 0);
                    if (!cb) return 'NOT_FOUND';
                    // Get bounding rect for logging
                    let r = cb.getBoundingClientRect();
                    // Click natively
                    cb.click();
                    return JSON.stringify({x: r.x|0, y: r.y|0, w: r.width|0, h: r.height|0});
                }"""),
                timeout=5.0
            )
            if clicked and clicked != 'NOT_FOUND':
                self._log('info', f"JS click: {clicked}")
                await asyncio.sleep(1.0)
                if await self._verify_click_success():
                    return True
        except asyncio.TimeoutError:
            self._log('debug', "Strategy 1 timed out")
        except Exception as e:
            self._log('debug', f"Strategy 1 failed: {e}")

        # -----------------------------------------------------------------------
        # Strategy 2: Coordinate click via frame bounding box
        # Bypasses DOM entirely — clicks at viewport coordinates where the
        # Turnstile checkbox is expected (top-left area of the iframe).
        # Works regardless of same/cross-origin because it's OS-level input.
        # -----------------------------------------------------------------------
        try:
            self._log('debug', "Strategy 2: Frame coordinate clicks")
            frame_element = await self._target_frame.frame_element()
            if frame_element:
                box = await frame_element.bounding_box()
                if box and box['width'] > 0 and box['height'] > 0:
                    # Generate click positions — checkbox is in top-left of iframe
                    rng = random.Random()
                    rng.seed(time.time())
                    positions = []
                    for ox in range(15, 50, 5):
                        for oy_factor in [x/10 for x in range(3, 7)]:
                            jx = rng.uniform(-2, 2)
                            jy = rng.uniform(-2, 2)
                            positions.append((
                                box['x'] + ox + jx,
                                box['y'] + box['height'] * oy_factor + jy
                            ))
                    rng.shuffle(positions)

                    for tx, ty in positions[:20]:
                        await human_click(self.page, x=tx, y=ty)
                        await asyncio.sleep(rng.uniform(0.4, 0.8))
                        if await self._verify_click_success():
                            self._log('info', f"Coordinate click SUCCESS at ({tx:.0f}, {ty:.0f})")
                            return True
        except Exception as e:
            self._log('debug', f"Strategy 2 failed: {e}")

        # -----------------------------------------------------------------------
        # Strategy 3: dispatchEvent at viewport coordinates
        # Creates and dispatches synthetic events at the viewport level.
        # This can bypass some click-detection heuristics on CF's side.
        # -----------------------------------------------------------------------
        try:
            self._log('debug', "Strategy 3: dispatchEvent area clicks")
            frame_element = await self._target_frame.frame_element()
            if frame_element:
                box = await frame_element.bounding_box()
                if box:
                    areas = [
                        (box['x'] + 25, box['y'] + box['height'] * 0.35),
                        (box['x'] + 30, box['y'] + box['height'] * 0.45),
                        (box['x'] + 20, box['y'] + box['height'] * 0.50),
                        (box['x'] + 35, box['y'] + box['height'] * 0.55),
                        (box['x'] + 15, box['y'] + box['height'] * 0.40),
                    ]
                    for cx, cy in areas:
                        await human_mouse_move(self.page, cx, cy)
                        await asyncio.sleep(random.uniform(0.05, 0.15))
                        # Dispatch click events at viewport level
                        await self.page.mouse.click(cx, cy)
                        await asyncio.sleep(0.8)
                        if await self._verify_click_success():
                            self._log('info', "DispatchEvent click SUCCESS")
                            return True
        except Exception as e:
            self._log('debug', f"Strategy 3 failed: {e}")

        return False

    # -----------------------------------------------------------------------
    # Click verification
    # -----------------------------------------------------------------------

    async def _verify_click_success(self) -> bool:
        """Verify Turnstile checkbox click was successful.

        Checks multiple indicators with progressive polling:
        1. cf-turnstile-response hidden input with valid token (polls up to 3s)
        2. Green checkmark / spinner visual state (via JS — checks page + iframe)
        3. cf_clearance cookie (polls up to 5s)

        All Playwright calls use asyncio.wait_for to prevent hanging if the
        browser connection is unresponsive.
        """
        try:
            # Indicator 1: cf-turnstile-response marker (poll for up to 3s)
            marker = self.page.locator('input[name="cf-turnstile-response"]').first
            for _ in range(15):
                try:
                    _count = await asyncio.wait_for(marker.count(), timeout=3.0)
                    if _count > 0:
                        val = await asyncio.wait_for(marker.get_attribute('value'), timeout=3.0)
                        if val and len(val) > 10:
                            self._log('info', f"Click SUCCESS: marker active (len={len(val)})")
                            return True
                except asyncio.TimeoutError:
                    self._log('debug', "_verify_click_success marker poll TIMEOUT — browser may be unresponsive")
                except Exception:
                    pass
                await asyncio.sleep(0.2)

            # Indicator 2: Check for spinner/green checkmark state via JS
            # Turnstile shows a spinner then green check on success
            try:
                visual_state = await asyncio.wait_for(
                    self.page.evaluate("""() => {
                        const markers = [
                            '.checkmark', '.green', '[class*="success"]',
                            '[class*="check"]', '[class*="spinner"]',
                            '[aria-label*="success"]', '[aria-label*="Verifying"]',
                            '.mark.mark-completed', '[data-state="solved"]',
                            '[data-state="verified"]'
                        ];
                        for (let sel of markers) {
                            try {
                                let el = document.querySelector(sel);
                                if (el) return sel;
                            } catch(e) {}
                        }
                        return null;
                    }"""),
                    timeout=1.0
                )
                if visual_state:
                    self._log('info', f"Click SUCCESS: visual indicator '{visual_state}' found")
                    return True
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

            # Also check visual state inside the target iframe (penetrates origin)
            if self._target_frame:
                try:
                    iframe_visual = await asyncio.wait_for(
                        self._target_frame.evaluate("""() => {
                            const sel = '.mark.mark-completed, [data-state="solved"], [data-state="verified"], .checkmark';
                            try {
                                let el = document.querySelector(sel);
                                return el ? 'found' : null;
                            } catch(e) { return null; }
                        }"""),
                        timeout=1.0
                    )
                    if iframe_visual:
                        self._log('info', "Click SUCCESS: visual indicator in iframe")
                        return True
                except Exception:
                    pass

            # Indicator 3: cf_clearance cookie (poll for up to 5s)
            for _ in range(25):
                if await self._has_clearance_cookie():
                    self._log('info', "Click SUCCESS: cf_clearance cookie found")
                    return True
                await asyncio.sleep(0.2)

        except Exception as e:
            self._log('debug', f"Verification error: {e}")
        return False

    # -----------------------------------------------------------------------
    # Cookie check
    # -----------------------------------------------------------------------

    # Minimum length for a valid cf_clearance value
    # Cloudflare issues real cf_clearance values as 100-200+ char hex strings.
    # Empty or short (< 20 chars) values are preliminary/placeholder cookies
    # set during the JS challenge before final clearance is issued.
    # Detecting these as "solved" causes false positives → page reload still blocked.
    _MIN_CF_CLEARANCE_LENGTH = 20

    async def _has_clearance_cookie(self) -> bool:
        """Check for valid cf_clearance cookie (non-empty value, correct domain).
        
        Uses asyncio.wait_for to prevent hanging forever if the Playwright
        connection to the browser is stuck — a blocked cookies() call would
        prevent the solve timeout from ever being checked, potentially
        locking the worker's lifecycle_lock for 20+ minutes.
        
        Returns True only if cf_clearance exists AND:
        - Has a non-empty value of at least _MIN_CF_CLEARANCE_LENGTH chars
        - Is NOT from the Turnstile iframe domain (challenges.cloudflare.com)
        
        Cloudflare's Turnstile widget runs in an iframe from challenges.cloudflare.com
        and sets its OWN cf_clearance cookie for the iframe domain during the JS
        challenge. This cookie has the correct length (575 chars) but is scoped
        to the iframe domain — it won't be sent on requests to the target page
        (cardmarket.com). Detecting this as "solved" causes the solver to return
        early, but the main page still gets blocked by CF.
        """
        try:
            cookies = await asyncio.wait_for(
                self.page.context.cookies(),
                timeout=5.0,
            )
            for c in cookies:
                if c['name'] == 'cf_clearance':
                    val = c.get('value', '') or ''
                    if len(val) < self._MIN_CF_CLEARANCE_LENGTH:
                        continue
                    # Reject cf_clearance from Turnstile iframe domain
                    # Real cf_clearance for our target page has domain=cardmarket.com
                    domain = c.get('domain', '') or ''
                    if "challenges.cloudflare.com" in domain:
                        self._log('debug',
                            f"cf_clearance found but domain={domain} (iframe) — rejecting"
                        )
                        continue
                    return True
            return False
        except asyncio.TimeoutError:
            self._log('warning', "_has_clearance_cookie TIMEOUT — browser may be unresponsive")
            return False
        except Exception:
            return False


# ===========================================================================
# Standalone solver function (used by Camoufox service)
# ===========================================================================

async def solve_turnstile_challenge(
    url: str,
    proxy_config: Dict[str, Any],
    tls_profile: str,
    worker_id: str,
    ff_version: Optional[int] = None
) -> Dict[str, Any]:
    """
    Solve Cloudflare Turnstile challenge using Camoufox browser.

    Feature 041: Injects force-open shadow DOM script before navigation
    for closed shadow root support. Also applies live force-open after page load.
    """
    version_info = f" (ff_version={ff_version})" if ff_version else ""
    logger.info(f"[TurnstileSolver] Starting solve for {worker_id}{version_info}")

    if not CAMOUFOX_AVAILABLE:
        logger.error("[TurnstileSolver] Camoufox library not available - cannot solve")
        return {
            'success': False,
            'error': 'camoufox_not_available',
            'cf_clearance': '',
            'user_agent': ''
        }

    browser = None
    _camoufox_instance = None
    context = None
    page = None
    browser_pid = None

    try:
        # Build proxy dict for Camoufox
        proxy_dict = None
        server = proxy_config.get('server', '')
        if server and server != 'direct':
            proxy_dict = {
                'server': server,
                'username': proxy_config.get('username', ''),
                'password': proxy_config.get('password', '')
            }

        # Firefox proxy auth prefs: signon.autologin.proxy=True tells Firefox
        # to send Proxy-Authorization credentials immediately (preemptive auth)
        # instead of waiting for a 407 response. Without this, Firefox on Linux
        # fails with NS_ERROR_UNKNOWN_HOST when the proxy requires auth but
        # doesn't issue a proper 407 challenge (common with residential proxies).
        firefox_user_prefs = {
            'signon.autologin.proxy': True,
            'network.proxy.type': 1,
        }

        launch_kwargs = {
            'headless': True,
            'proxy': proxy_dict,
            'geoip': True,
            'firefox_user_prefs': firefox_user_prefs,
        }
        if ff_version:
            launch_kwargs['ff_version'] = ff_version
            launch_kwargs['i_know_what_im_doing'] = True
        if tls_profile and 'firefox' in tls_profile.lower() and not ff_version:
            match = re.search(r'firefox(\d+)', tls_profile.lower())
            if match:
                launch_kwargs['ff_version'] = int(match.group(1))
                launch_kwargs['i_know_what_im_doing'] = True

        version_str = f" (ff_version={launch_kwargs.get('ff_version', 'default')})" if launch_kwargs.get('ff_version') else ""
        logger.info(f"[TurnstileSolver] Launching Camoufox for {worker_id} with proxy={server}{version_str}")

        _camoufox_instance = AsyncCamoufox(**launch_kwargs)
        browser = await _camoufox_instance.start()

        try:
            if hasattr(browser, '_connection') and hasattr(browser._connection, '_transport'):
                transport = browser._connection._transport
                if hasattr(transport, '_proc') and transport._proc:
                    browser_pid = transport._proc.pid
        except Exception:
            pass

        context = await browser.new_context(viewport=None)
        page = await context.new_page()

        # Feature 041: Inject shadow DOM force-open BEFORE navigation
        await page.add_init_script(SHADOW_DOM_FORCE_OPEN_SCRIPT)
        logger.debug(f"[TurnstileSolver] Shadow DOM force-open injected for {worker_id}")

        logger.info(f"[TurnstileSolver] Navigating to {url}")
        # Use networkidle to wait for XHR-loaded content (product listings, prices, etc.)
        # domcontentloaded is faster but may miss data loaded via XHR after DOM is ready.
        await page.goto(url, timeout=90000, wait_until='networkidle')

        # Apply live shadow DOM force-open after page load too
        solver = TurnstileSolver(page, worker_id=worker_id)
        await solver.force_shadow_dom_open_live()

        solved = await solver.solve(timeout=120.0)

        cookies = await context.cookies()
        cf_clearance = next((c['value'] for c in cookies if c['name'] == 'cf_clearance'), None)
        user_agent = await page.evaluate('() => navigator.userAgent')

        if solved:
            max_cookie_retries = 5
            for cookie_retry in range(max_cookie_retries):
                cookies = await context.cookies()
                cf_clearance = next((c['value'] for c in cookies if c['name'] == 'cf_clearance'), None)

                if cf_clearance and len(cf_clearance) > 10:
                    break

                if cookie_retry < max_cookie_retries - 1:
                    await asyncio.sleep(0.5)

            title = await page.title()
            page_content = await page.content()

            has_cf_indicators = (
                'Just a moment' in title or
                'checking your browser' in title or
                'Cloudflare' in title or
                'cf-challenge' in page_content or
                'cf_captcha' in page_content or
                'challenges.cloudflare.com' in page_content or
                'cf-turnstile' in page_content or
                ('nonce-' in page_content and 'challenge-platform' in page_content) or
                '/cdn-cgi/challenge-platform/' in page_content
            )

            is_cf_challenge_page = (
                page_content.strip().startswith('<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title>') or
                'Enable JavaScript and cookies to continue' in page_content
            )

            if (has_cf_indicators or is_cf_challenge_page) and not cf_clearance:
                logger.warning(f"[TurnstileSolver] Ghost block detected AFTER solve for {worker_id}")
                return {
                    'success': False,
                    'error': 'ghost_block_no_clearance',
                    'cf_clearance': '',
                    'user_agent': user_agent
                }

            all_cookies_dict = {c['name']: c['value'] for c in cookies}

            logger.info(f"[TurnstileSolver] Solve completed for {worker_id} (cf_clearance={bool(cf_clearance)})")
            return {
                'success': True,
                'cf_clearance': cf_clearance or '',
                'user_agent': user_agent,
                'cookies': all_cookies_dict,
                'html': page_content
            }
        else:
            title = await page.title()
            page_content = await page.content()

            has_cf_indicators = (
                'Just a moment' in title or
                'checking your browser' in title or
                'Cloudflare' in title or
                'cf-challenge' in page_content or
                'cf_captcha' in page_content
            )

            if has_cf_indicators and cf_clearance:
                logger.info(f"[TurnstileSolver] Ghost block: CF indicators present but have cf_clearance for {worker_id}")
                return {
                    'success': True,
                    'cf_clearance': cf_clearance,
                    'user_agent': user_agent,
                    'cookies': {c['name']: c['value'] for c in cookies},
                    'html': page_content
                }

            logger.warning(f"[TurnstileSolver] Solve failed for {worker_id}")
            return {
                'success': False,
                'error': 'solve_failed',
                'cf_clearance': cf_clearance or '',
                'user_agent': user_agent
            }

    except asyncio.TimeoutError:
        logger.warning(f"[TurnstileSolver] Timeout for {worker_id}")
        return {
            'success': False,
            'error': 'timeout',
            'cf_clearance': '',
            'user_agent': ''
        }
    except Exception as e:
        logger.error(f"[TurnstileSolver] Exception during solve for {worker_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'cf_clearance': '',
            'user_agent': ''
        }
    finally:
        # Cleanup browser
        try:
            if context:
                await context.close()
        except Exception:
            pass
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if _camoufox_instance:
                await _camoufox_instance.stop()
        except Exception:
            pass

        # Feature 039: Clean up zombie processes
        try:
            if browser_pid:
                kill_process_tree(browser_pid)
        except Exception:
            pass
        reap_all_zombies()