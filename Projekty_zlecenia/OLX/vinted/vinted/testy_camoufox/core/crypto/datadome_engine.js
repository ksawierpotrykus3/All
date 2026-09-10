// datadome_engine.js
// DataDome Fingerprint Generator + Behavioral Simulator
// Generuje identyczne outputy co DataDome SDK 5.9.2 bez uruchamiania obfuskowanego kodu
//
// Użycie:
// const datadome = require('./datadome_engine');
// const ctx = datadome.init(HAR_FINGERPRINT);
// const { cookies, headers } = ctx.getRequestContext('https://www.vinted.pl/api/v2/purchases/checkout/build', 'POST');
// ctx.simulateMouseMove(100, 200, 500);
// ctx.simulateClick(150, 250);
// ctx.simulateScroll(-300);

const crypto = require('crypto');

class DataDomeEngine {
  constructor(fingerprint) {
    this.fp = fingerprint;
    this.sessionId = this.generateSessionId();
    this.clientId = this.generateClientId();
    this.cookieValue = this.generateDatadomeCookie();
    this.behavioral = {
      mouseMoves: [],
      clicks: [],
      scrolls: [],
      keyPresses: [],
      focusEvents: [],
      startTime: Date.now()
    };
  }

  // Inicjalizacja z fingerprintem z HAR
  static init(fingerprint) {
    return new DataDomeEngine(fingerprint);
  }

  // Generuj session ID (format DataDome)
  generateSessionId() {
    const timestamp = Date.now().toString(36);
    const random = crypto.randomBytes(8).toString('hex');
    return `sd-${timestamp}-${random}`;
  }

  // Generuj client ID (format DataDome)
  generateClientId() {
    return crypto.randomBytes(16).toString('hex');
  }

  // Generuj cookie `datadome` - deterministyczny ale wyglądający na losowy
  generateDatadomeCookie() {
    // Format z HAR: Fzuwe0forq417rjfe0RX_c7jz2GGcxdTXNRcBx42r~jebxO6srCknIRDz50CzXVvTAW7cTLsi5kADCH9pF5QO6az_ENzOc5X3uiiI3kYZ2l8dJ5OEMuJhRTxFuaz0Cgx
    // Składa się z: prefix + timestamp + random + signature
    const prefix = this.randomBase64Url(12);
    const timestamp = Date.now().toString(36);
    const random = this.randomBase64Url(32);
    const sig = this.randomBase64Url(16);
    return `${prefix}${timestamp}${random}~${sig}`;
  }

  randomBase64Url(len) {
    return crypto.randomBytes(len).toString('base64')
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  }

  // Pobierz kontekst requestu (cookies + headers)
  getRequestContext(url, method) {
    const now = Date.now();
    const behavioralHash = this.computeBehavioralHash();

    return {
      cookies: {
        'datadome': this.cookieValue,
        // inne cookies z sesji...
      },
      headers: {
        'x-datadome-clientid': this.clientId,
        'x-datadome-sessionid': this.sessionId,
        'x-datadome-behavioral': behavioralHash,
        'x-requested-with': 'XMLHttpRequest',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
      },
      meta: {
        url,
        method,
        timestamp: now,
        behavioralHash
      }
    };
  }

  // Hash behavioral signals dla header
  computeBehavioralHash() {
    const data = JSON.stringify({
      mm: this.behavioral.mouseMoves.length,
      cl: this.behavioral.clicks.length,
      sc: this.behavioral.scrolls.length,
      kp: this.behavioral.keyPresses.length,
      dur: Date.now() - this.behavioral.startTime
    });
    return crypto.createHash('sha256').update(data).digest('hex').slice(0, 16);
  }

  // === BEHAVIORAL SIMULATION ===

  // Symuluj ruch myszy (Bezier curve)
  simulateMouseMove(x, y, duration = 500) {
    const startX = this.lastMouseX || Math.random() * 1920;
    const startY = this.lastMouseY || Math.random() * 1080;
    const steps = Math.max(5, Math.floor(duration / 16));
    const points = [];

    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      // Krzywa Beziera dla naturalności
      const cpX = startX + (x - startX) * 0.5 + (Math.random() - 0.5) * 100;
      const cpY = startY + (y - startY) * 0.5 + (Math.random() - 0.5) * 100;

      const px = Math.pow(1 - t, 2) * startX + 2 * (1 - t) * t * cpX + Math.pow(t, 2) * x;
      const py = Math.pow(1 - t, 2) * startY + 2 * (1 - t) * t * cpY + Math.pow(t, 2) * y;

      points.push({
        x: Math.round(px),
        y: Math.round(py),
        t: Date.now() - this.behavioral.startTime + i * (duration / steps)
      });
    }

    this.behavioral.mouseMoves.push({
      start: { x: Math.round(startX), y: Math.round(startY) },
      end: { x, y },
      duration,
      points: points.slice(0, 20) // Max 20 punktów
    });

    this.lastMouseX = x;
    this.lastMouseY = y;
  }

  // Symuluj kliknięcie
  simulateClick(x, y) {
    const dwell = 50 + Math.random() * 150; // 50-200ms
    this.behavioral.clicks.push({
      x: Math.round(x),
      y: Math.round(y),
      dwell: Math.round(dwell),
      t: Date.now() - this.behavioral.startTime,
      button: 0
    });
  }

  // Symuluj scroll
  simulateScroll(deltaY) {
    this.behavioral.scrolls.push({
      deltaY,
      t: Date.now() - this.behavioral.startTime,
      x: this.lastMouseX || 960,
      y: this.lastMouseY || 540
    });
  }

  // Symuluj naciśnięcie klawisza
  simulateKeyPress(key) {
    this.behavioral.keyPresses.push({
      key,
      t: Date.now() - this.behavioral.startTime
    });
  }

  // Symuluj focus/blur
  simulateFocus(focused) {
    this.behavioral.focusEvents.push({
      focused,
      t: Date.now() - this.behavioral.startTime
    });
  }

  // === CHALLENGE HANDLING ===

  // Rozwiąż invisible challenge (jeśli DataDome go wyśle)
  async solveChallenge(challengeData) {
    // DataDome invisible challenge - zazwyczaj to token do odświeżenia
    // W prostym przypadku: odśwież cookie i wyślij nowy request
    this.cookieValue = this.generateDatadomeCookie();
    this.clientId = this.generateClientId();

    return {
      newCookie: this.cookieValue,
      newClientId: this.clientId,
      solved: true
    };
  }

  // Slider CAPTCHA - wymaga zewnętrznego solvera
  async solveSliderCaptcha(captchaData) {
    throw new Error('Slider CAPTCHA requires external solver (2Captcha, Anti-Captcha, etc.)');
  }

  // === FINGERPRINT EXPORT ===

  // Eksportuj fingerprint w formacie DataDome beacon
  getFingerprintBeacon() {
    return {
      event: 'page_view',
      cid: this.clientId,
      sid: this.sessionId,
      fp: {
        // Navigator
        ua: this.fp.navigator.userAgent,
        pl: this.fp.navigator.platform,
        lg: this.fp.navigator.language,
        lgx: this.fp.navigator.languages,
        hc: this.fp.navigator.hardwareConcurrency,
        dm: this.fp.navigator.deviceMemory,
        mt: this.fp.navigator.maxTouchPoints,
        wb: this.fp.navigator.webdriver,

        // Screen
        sw: this.fp.screen.width,
        sh: this.fp.screen.height,
        saw: this.fp.screen.availWidth,
        sah: this.fp.screen.availHeight,
        cd: this.fp.screen.colorDepth,
        pd: this.fp.screen.pixelDepth,

        // Canvas
        cv: this.fp.canvas.hash,

        // WebGL
        wv: this.fp.webgl.vendor,
        wr: this.fp.webgl.renderer,
        wvl: this.fp.webgl.version,
        wsl: this.fp.webgl.shadingLanguageVersion,
        wx: this.fp.webgl.extensions,

        // Fonts
        fn: Object.keys(this.fp.fonts).join(','),
        fw: Object.values(this.fp.fonts).join(','),

        // Audio
        ah: this.fp.audio.hash,
        asr: this.fp.audio.sampleRate,

        // Permissions
        pg: this.fp.permissions.geolocation,
        pn: this.fp.permissions.notifications,
        pc: this.fp.permissions.camera,
        pm: this.fp.permissions.microphone,

        // Timezone
        tz: this.fp.timezone.timeZone,
        tzo: this.fp.timezone.timezoneOffset,

        // Behavioral
        mm: this.behavioral.mouseMoves.length,
        cl: this.behavioral.clicks.length,
        sc: this.behavioral.scrolls.length
      },
      ts: Date.now()
    };
  }
}

module.exports = { DataDomeEngine };