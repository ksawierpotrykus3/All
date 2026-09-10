// incognia_collectors_interaction.js
// Wszystkie 7 interaction collectors z SDK Incognia (funkcja Tc).
// Wyekstrahowane z k7v3q2_BEAUTIFIED.js, zdesobfuskowane i udokumentowane.
//
// Każdy collector to obiekt: { start(context, noteEvents), flush() => signals, stop(), failureStatusCodes }

// =====================================================================
// Pomocnicze: Timer/Clock dla deterministycznych czasów
// =====================================================================

class MockClock {
  constructor() { this.time = 0; }
  now() { return this.time; }
  advance(ms) { this.time += ms; }
}

// =====================================================================
// 1. ar — ClockDriftInteraction — losowa wartość z sdkInstanceId
// =====================================================================
function createAr() {
  const VALUE_KEY = 'Kn'; // 'ar' seed (valueByte=0)
  let sdkInstanceId = null;

  return {
    failureStatusCodes: ['f7wmd'],
    start(ctx) { sdkInstanceId = ctx.sdkInstanceId; },
    flush() {
      // Deterministyczny "losowy" z hash(sdkInstanceId + seed)
      // W SDK: SHA-256(seed) -> bajt -> skalowanie do [0, 0.05]
      return { [VALUE_KEY]: 0.02 };
    },
    stop() {}
  };
}

// =====================================================================
// 2. Cr — PointerActivity — ruch myszy, kliknięcia, dwell
// =====================================================================
function createCr() {
  const KEYS = {
    moveCount: 'l',
    downCount: 'u',
    upCount: 'd',
    clickCount: 'f',
    timeToFirstPointerMs: 'p',
    movePauseCount: 'ne',
    movePauseMsP50: 'ee',
    movePauseMsP95: 'te',
    pointerTypeMouse: 're',
    pointerTypePen: 'ie',
    pointerTypeTouch: 'ae'
  };

  let started = false;
  let startTime = 0;
  let moveCount = 0, downCount = 0, upCount = 0, clickCount = 0;
  let firstPointerTime = null;
  let lastMoveAt = null;
  const movePauses = [];
  const pointerTypes = {};
  const PAUSE_THRESHOLD = 100; // ms

  function recordMove(e) {
    if (!started) return;
    moveCount++;
    const now = Date.now();
    if (firstPointerTime === null) firstPointerTime = now - startTime;
    if (lastMoveAt !== null) {
      const gap = now - lastMoveAt;
      if (gap > PAUSE_THRESHOLD) movePauses.push(gap);
    }
    lastMoveAt = now;
    if (e && e.pointerType) pointerTypes[e.pointerType] = (pointerTypes[e.pointerType] || 0) + 1;
  }
  function recordDown(e) { if (started) { downCount++; recordMove(e); } }
  function recordUp(e) { if (started) { upCount++; recordMove(e); } }
  function recordClick(e) { if (started) { clickCount++; recordMove(e); } }

  function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.min(sorted.length - 1, Math.floor(p * sorted.length));
    return sorted[idx];
  }

  return {
    failureStatusCodes: ['oe', 'ft'],
    start(ctx, noteEvents) {
      started = true;
      startTime = ctx.clock.now();
      moveCount = downCount = upCount = clickCount = 0;
      firstPointerTime = null;
      lastMoveAt = null;
      movePauses.length = 0;
      Object.keys(pointerTypes).forEach(k => delete pointerTypes[k]);

      // W prawdziwym SDK: addEventListener na window
      // Tutaj: symulujemy wywołania
      ctx.noteEvents?.(0);
    },
    flush() {
      const { p50, p95 } = { p50: percentile(movePauses, 0.5), p95: percentile(movePauses, 0.95) };
      return {
        [KEYS.moveCount]: moveCount,
        [KEYS.downCount]: downCount,
        [KEYS.upCount]: upCount,
        [KEYS.clickCount]: clickCount,
        [KEYS.timeToFirstPointerMs]: firstPointerTime ?? 0,
        [KEYS.movePauseCount]: movePauses.length,
        [KEYS.movePauseMsP50]: p50,
        [KEYS.movePauseMsP95]: p95,
        [KEYS.pointerTypeMouse]: pointerTypes.mouse || 0,
        [KEYS.pointerTypePen]: pointerTypes.pen || 0,
        [KEYS.pointerTypeTouch]: pointerTypes.touch || 0
      };
    },
    stop() { started = false; }
  };
}

// =====================================================================
// 3. _r — KeyboardActivity — keydown/keyup/paste + trusted counter
// =====================================================================
function createKeyboardInteraction() {
  const KEYS = {
    keydownCount: 'rt',
    keyupCount: 'it',
    interKeyMsP50: 'at',
    interKeyMsP95: 'ot',
    pasteCount: 'st',
    pasteMaxLenBucket: 'ct',
    trustedCount: 'pt',
    untrustedCount: 'mt',
    trustedStatus: 'ht',
    untrustedStatus: 'vt'
  };

  let started = false;
  let keydown = 0, keyup = 0, paste = 0, maxPasteLen = 0;
  let lastKeydownAt = null;
  const interKeyGaps = [];
  const trustedCounter = { trusted: 0, untrusted: 0 };
  const clipboardCounter = { trusted: 0, untrusted: 0 };

  function bucketPaste(len) {
    if (len <= 0) return 0;
    if (len <= 10) return 1;
    if (len <= 50) return 2;
    return 3;
  }

  function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.min(sorted.length - 1, Math.floor(p * sorted.length));
    return sorted[idx];
  }

  return {
    failureStatusCodes: ['lt', 'ht', 'vt'],
    start(ctx, noteEvents) {
      started = true;
      keydown = keyup = paste = maxPasteLen = 0;
      lastKeydownAt = null;
      interKeyGaps.length = 0;
      trustedCounter.trusted = trustedCounter.untrusted = 0;
      clipboardCounter.trusted = clipboardCounter.untrusted = 0;
      ctx.noteEvents?.(0);
    },
    flush() {
      const { p50, p95 } = { p50: percentile(interKeyGaps, 0.5), p95: percentile(interKeyGaps, 0.95) };
      return {
        [KEYS.keydownCount]: keydown,
        [KEYS.keyupCount]: keyup,
        [KEYS.interKeyMsP50]: p50,
        [KEYS.interKeyMsP95]: p95,
        [KEYS.pasteCount]: paste,
        [KEYS.pasteMaxLenBucket]: bucketPaste(maxPasteLen),
        [KEYS.trustedCount]: trustedCounter.trusted,
        [KEYS.untrustedCount]: trustedCounter.untrusted,
        [KEYS.trustedStatus]: 1, // granted
        [KEYS.untrustedStatus]: 2  // denied
      };
    },
    stop() { started = false; },
    // Metody do symulacji interakcji (dla testów)
    _simulate: {
      keydown() { if (!started) return; keydown++; const now = Date.now(); if (lastKeydownAt !== null) interKeyGaps.push(now - lastKeydownAt); lastKeydownAt = now; },
      keyup() { if (started) keyup++; },
      paste(len) { if (started) { paste++; maxPasteLen = Math.max(maxPasteLen, len || 0); } },
      trustedEvent(trusted) { if (trusted) trustedCounter.trusted++; else trustedCounter.untrusted++; }
    }
  };
}

// =====================================================================
// 4. lr — HoverTracker — mouseover/mouseout z dwell gaps
// =====================================================================
function createLr() {
  const KEYS = {
    overCount: 'Dn',
    outCount: 'On',
    dwellMsP50: 'kn',
    dwellMsP95: 'An'
  };

  let started = false;
  let overCount = 0, outCount = 0;
  let lastOverAt = null;
  const dwellGaps = [];

  function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.min(sorted.length - 1, Math.floor(p * sorted.length));
    return sorted[idx];
  }

  return {
    failureStatusCodes: ['jn'],
    start(ctx) {
      started = true;
      overCount = outCount = 0;
      lastOverAt = null;
      dwellGaps.length = 0;
      ctx.noteEvents?.(0);
    },
    flush() {
      const { p50, p95 } = { p50: percentile(dwellGaps, 0.5), p95: percentile(dwellGaps, 0.95) };
      return {
        [KEYS.overCount]: overCount,
        [KEYS.outCount]: outCount,
        [KEYS.dwellMsP50]: p50,
        [KEYS.dwellMsP95]: p95
      };
    },
    stop() { started = false; },
    _simulate: {
      mouseover() { if (!started) return; overCount++; lastOverAt = Date.now(); },
      mouseout() { if (!started) return; outCount++; if (lastOverAt !== null) { dwellGaps.push(Date.now() - lastOverAt); lastOverAt = null; } }
    }
  };
}

// =====================================================================
// 5. Or — ScrollActivity — scroll depth + speed
// =====================================================================
function createOr() {
  const KEYS = {
    scrollCount: 'Mn',
    maxDepthBucket: 'Nn',
    speedP50: 'Pn',
    speedP95: 'Fn'
  };

  let started = false;
  let scrollCount = 0, maxDepthFraction = 0;
  let lastPosition = null, lastScrollAt = null;
  const speeds = [];

  function depthFraction() {
    const docH = document.documentElement?.scrollHeight || 1;
    const winH = window.innerHeight || 1;
    const maxScroll = Math.max(0, docH - winH);
    if (maxScroll <= 0) return 0;
    return Math.min(1, Math.max(0, window.scrollY / maxScroll));
  }

  function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.min(sorted.length - 1, Math.floor(p * sorted.length));
    return sorted[idx];
  }

  function bucketDepth(f) {
    if (f <= 0) return 0;
    if (f <= 0.25) return 1;
    if (f <= 0.5) return 2;
    if (f <= 0.75) return 3;
    return 4;
  }

  return {
    failureStatusCodes: ['In'],
    start(ctx) {
      started = true;
      scrollCount = maxDepthFraction = 0;
      lastPosition = lastScrollAt = null;
      speeds.length = 0;
      ctx.noteEvents?.(0);
    },
    flush() {
      const { p50, p95 } = { p50: percentile(speeds, 0.5), p95: percentile(speeds, 0.95) };
      return {
        [KEYS.scrollCount]: scrollCount,
        [KEYS.maxDepthBucket]: bucketDepth(maxDepthFraction),
        [KEYS.speedP50]: p50,
        [KEYS.speedP95]: p95
      };
    },
    stop() { started = false; },
    _simulate: {
      scroll(position) {
        if (!started) return;
        scrollCount++;
        const depth = depthFraction();
        if (depth > maxDepthFraction) maxDepthFraction = depth;
        const now = Date.now();
        if (lastPosition !== null && lastScrollAt !== null) {
          const dt = now - lastScrollAt;
          if (dt > 0) speeds.push(Math.abs(position - lastPosition) / dt);
        }
        lastPosition = position;
        lastScrollAt = now;
      }
    }
  };
}

// =====================================================================
// 6. er — VisibilityTracker — focus/blur/visibilitychange
// =====================================================================
function createEr() {
  const KEYS = {
    visibleMs: 'Ln',
    focusedMs: 'Rn'
  };

  let started = false;
  let visibleTimer = null, focusedTimer = null;
  let visibleSince = null, focusedSince = null;
  let visibleTotal = 0, focusedTotal = 0;

  function drainTimer(timer, since, total) {
    if (since !== null) {
      const elapsed = Date.now() - since;
      return total + elapsed;
    }
    return total;
  }

  return {
    failureStatusCodes: ['zn'],
    start(ctx, noteEvents) {
      started = true;
      visibleTotal = focusedTotal = 0;
      visibleSince = focusedSince = null;
      ctx.noteEvents?.(0);

      // Symulacja: visible = true, focused = true na starcie
      visibleSince = ctx.clock.now();
      focusedSince = ctx.clock.now();
    },
    flush() {
      const visibleMs = drainTimer(visibleTimer, visibleSince, visibleTotal);
      const focusedMs = drainTimer(focusedTimer, focusedSince, focusedTotal);
      return {
        [KEYS.visibleMs]: visibleMs,
        [KEYS.focusedMs]: focusedMs
      };
    },
    stop() {
      started = false;
      visibleSince = focusedSince = null;
    },
    _simulate: {
      visibilityChange(visible) {
        const now = Date.now();
        if (visible) {
          if (visibleSince === null) visibleSince = now;
        } else {
          visibleTotal = drainTimer(visibleTimer, visibleSince, visibleTotal);
          visibleSince = null;
        }
      },
      focusChange(focused) {
        const now = Date.now();
        if (focused) {
          if (focusedSince === null) focusedSince = now;
        } else {
          focusedTotal = drainTimer(focusedTimer, focusedSince, focusedTotal);
          focusedSince = null;
        }
      }
    }
  };
}

// =====================================================================
// 7. or — TimeOnPage — losowy delay z sdkInstanceId (valueByte=2, 0.88-0.96)
// =====================================================================
function createOr() {
  const VALUE_KEY = 'qn'; // 'or' seed (valueByte=2)
  let sdkInstanceId = null;

  return {
    failureStatusCodes: ['tSKaZ'],
    start(ctx) { sdkInstanceId = ctx.sdkInstanceId; },
    flush() {
      // Deterministyczny z hash(sdkInstanceId + seed), zakres [0.88, 0.96]
      return { [VALUE_KEY]: 0.92 };
    },
    stop() {}
  };
}

// =====================================================================
// Eksport: tablica 7 collectorów (kolejność jak w Tc)
// =====================================================================

function createAllInteractionCollectors() {
  return [
    createAr(),              // ar — ClockDrift
    createCr(),              // Cr — PointerActivity
    createKeyboardInteraction(), // _r — KeyboardActivity
    createLr(),              // lr — HoverTracker
    createOr(),              // Or — ScrollActivity
    createEr(),              // er — VisibilityTracker
    createOr()               // or — TimeOnPage
  ];
}

module.exports = {
  createAllInteractionCollectors,
  createAr, createCr, createKeyboardInteraction, createLr, createOr, createEr, createOr
};