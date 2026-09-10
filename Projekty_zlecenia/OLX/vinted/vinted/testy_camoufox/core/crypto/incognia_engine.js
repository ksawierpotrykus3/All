// incognia_engine.js
// Kompletny silnik Incognia — replikuje pełny lifecycle SDK:
// initSdk() → snapshot phase → interaction loop → stop()
// Używa reference implementation z:
// - incognia_krypto_reference.js (HKDF + AES-GCM)
// - incognia_transport_reference.js (POST + retry)
// - incognia_sdk_reference.js (SDK lifecycle)
// - incognia_collectors_snapshot.js (17 collectors)
// - incognia_collectors_interaction.js (7 collectors)
//
// Wymaga Node 18+ z crypto.subtle (WebCrypto API)

const {
  HKDF_SALT,
  DEFAULT_CONFIG,
  bytesToBase64,
  sha256Hex,
  deriveAesKey,
  aesGcmEncrypt,
  buildEncryptor
} = require('./incognia_krypto_reference.js');

const {
  Transport,
  Dispatcher,
  HttpStatusError,
  withRetry,
  encodeModel
} = require('./incognia_transport_reference.js');

const {
  InteractionScheduler,
  NativeClock,
  IncogniaSdk,
  initSdk,
  CONSUME_SUFFIX
} = require('./incognia_sdk_reference.js');

const { createAllSnapshotCollectors } = require('./incognia_collectors_snapshot.js');
const { createAllInteractionCollectors } = require('./incognia_collectors_interaction.js');

// =====================================================================
// Mock Global Objects dla Node.js (symulacja przeglądarki)
// =====================================================================

function setupNodeGlobals() {
  // performance.now()
  if (typeof global.performance === 'undefined') {
    const { PerformanceObserver, performance } = require('perf_hooks');
    global.performance = performance;
  }
  if (typeof performance.timeOrigin === 'undefined') {
    performance.timeOrigin = Date.now() - performance.now();
  }

  // crypto.getRandomValues (Node 18+ ma to w globalnym crypto)
  if (typeof global.crypto === 'undefined') {
    const { webcrypto } = require('crypto');
    global.crypto = webcrypto;
  }

  // navigator
  global.navigator = {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    platform: 'Win32',
    language: 'pl-PL',
    languages: ['pl-PL', 'pl', 'en-US', 'en'],
    cookieEnabled: true,
    hardwareConcurrency: 8,
    maxTouchPoints: 0,
    deviceMemory: 8,
    userAgentData: {
      brands: [{ brand: 'Google Chrome', version: '120' }, { brand: 'Chromium', version: '120' }, { brand: 'Not A;Brand', version: '99' }],
      mobile: false,
      platform: 'Windows',
      getHighEntropyValues: async (hints) => {
        const values = {
          uaFullVersion: '120.0.0.0',
          platformVersion: '15.0.0',
          model: '',
          architecture: 'x86',
          bitness: '64',
          wow64: false
        };
        return hints.reduce((acc, h) => { if (h in values) acc[h] = values[h]; return acc; }, {});
      }
    },
    mediaDevices: { getUserMedia: () => Promise.resolve() },
    permissions: {
      query: async ({ name }) => {
        const map = { geolocation: 'prompt', notifications: 'prompt', camera: 'prompt', microphone: 'prompt', 'persistent-storage': 'prompt' };
        return { state: map[name] || 'prompt' };
      }
    },
    storage: {
      estimate: async () => ({ quota: 50 * 1024 * 1024, usage: 1024 * 1024 }),
      persisted: async () => false
    },
    connection: { effectiveType: '4g', rtt: 50, downlink: 10, saveData: false },
    webdriver: false
  };

  // screen
  global.screen = {
    width: 1920, height: 1080,
    availWidth: 1920, availHeight: 1040,
    colorDepth: 24,
    orientation: { type: 'landscape-primary' }
  };

  // visualViewport
  global.visualViewport = { width: 1920, height: 1040, scale: 1 };

  // window / document (minimalne mocki dla collectorów)
  const listeners = new Map();
  global.window = global;
  global.document = {
    createElement: (tag) => {
      if (tag === 'canvas') {
        return {
          width: 0, height: 0,
          getContext: (type) => {
            if (type === '2d') return mockCanvas2dContext();
            if (type === 'webgl' || type === 'webgl2') return mockWebGLContext();
            return null;
          },
          toDataURL: () => 'data:image/png;base64,'
        };
      }
      if (tag === 'audio') return { canPlayType: () => 'probably' };
      if (tag === 'video') return { canPlayType: () => 'probably' };
      if (tag === 'span') {
        const el = { style: { cssText: '' }, offsetWidth: 100, offsetHeight: 20 };
        el.remove = () => {};
        return el;
      }
      return { style: {}, appendChild: () => {}, remove: () => {} };
    },
    body: { appendChild: () => {} },
    documentElement: { scrollHeight: 2000 },
    addEventListener: (event, handler, options) => {
      if (!listeners.has(event)) listeners.set(event, []);
      listeners.get(event).push({ handler, options });
    },
    removeEventListener: (event, handler) => {
      if (listeners.has(event)) {
        const arr = listeners.get(event);
        const idx = arr.findIndex(l => l.handler === handler);
        if (idx >= 0) arr.splice(idx, 1);
      }
    },
    visibilityState: 'visible',
    hasFocus: () => true
  };

  // matchMedia
  global.matchMedia = (query) => ({
    matches: query.includes('pointer:fine') || query.includes('hover:hover'),
    addListener: () => {}, removeListener: () => {}
  });

  // IndexedDB mock
  global.indexedDB = {
    open: (name, version) => {
      const req = { result: null, onupgradeneeded: null, onsuccess: null, onerror: null };
      setTimeout(() => {
        req.result = {
          createObjectStore: () => {},
          transaction: (store, mode) => ({
            objectStore: (name) => ({
              put: (key, val) => ({ onsuccess: null, onerror: null }),
              get: (key) => ({ onsuccess: null, onerror: null, result: key })
            })
          }),
          close: () => {}
        };
        req.onsuccess?.({ target: req });
      }, 0);
      return req;
    },
    deleteDatabase: (name) => ({ onsuccess: null, onerror: null })
  };

  // OfflineAudioContext mock (dla audio fingerprint)
  global.OfflineAudioContext = class {
    constructor(channels, length, sampleRate) {
      this.channels = channels; this.length = length; this.sampleRate = sampleRate;
      this.destination = {};
    }
    createOscillator() { return { type: 'sine', frequency: { value: 440 }, connect: () => {}, start: () => {} }; }
    createDynamicsCompressor() { return { threshold: { value: 0 }, knee: { value: 0 }, ratio: { value: 0 }, attack: { value: 0 }, release: { value: 0 }, connect: () => {} }; }
    startRendering() { return Promise.resolve({ getChannelData: () => new Float32Array(44100), sampleRate: 44100, numberOfChannels: 1 }); }
  };
  global.webkitOfflineAudioContext = global.OfflineAudioContext;

  // requestAnimationFrame
  global.requestAnimationFrame = (cb) => setTimeout(() => cb(performance.now()), 16);
  global.cancelAnimationFrame = (id) => clearTimeout(id);
}

// =====================================================================
// Mock Canvas 2D Context (dla canvas fingerprint)
// =====================================================================

function mockCanvas2dContext() {
  const imageData = { data: new Uint8ClampedArray(240 * 60 * 4), width: 240, height: 60 };
  for (let i = 0; i < imageData.data.length; i += 4) {
    imageData.data[i] = Math.random() * 255;
    imageData.data[i+1] = Math.random() * 255;
    imageData.data[i+2] = Math.random() * 255;
    imageData.data[i+3] = 255;
  }
  return {
    createLinearGradient: () => ({ addColorStop: () => {} }),
    fillStyle: '', fillRect: () => {}, font: '', fillText: () => {},
    strokeStyle: '', lineWidth: 1, beginPath: () => {}, arc: () => {}, stroke: () => {},
    getImageData: () => imageData,
    getParameter: (p) => {
      if (p === 0x0B71) return 'Google Inc.'; // VENDOR
      if (p === 0x0B72) return 'ANGLE (NVIDIA)'; // RENDERER
      if (p === 0x0B73) return 'OpenGL ES 2.0'; // VERSION
      if (p === 0x8B8C) return 'OpenGL ES GLSL ES 1.00'; // SHADING_LANGUAGE_VERSION
      return null;
    },
    getExtension: (name) => name === 'WEBGL_debug_renderer_info' ? { UNMASKED_VENDOR_WEBGL: 0x9245, UNMASKED_RENDERER_WEBGL: 0x9246 } : null,
    getSupportedExtensions: () => ['OES_texture_float', 'OES_texture_half_float', 'WEBGL_depth_texture'],
    createShader: () => ({ shaderSource: () => {}, compileShader: () => {}, getShaderParameter: () => true, getShaderInfoLog: () => '' }),
    createProgram: () => ({ attachShader: () => {}, linkProgram: () => {}, getProgramParameter: () => true, getProgramInfoLog: () => '' }),
    useProgram: () => {},
    bindBuffer: () => {}, createBuffer: () => ({}), bufferData: () => {},
    enableVertexAttribArray: () => {}, vertexAttribPointer: () => {},
    viewport: () => {}, clearColor: () => {}, clear: () => {}, drawArrays: () => {},
    readPixels: (x, y, w, h, format, type, pixels) => { /* fill mock data */ },
    ARRAY_BUFFER: 0x8892, STATIC_DRAW: 0x88E4, VERTEX_SHADER: 0x8B31, FRAGMENT_SHADER: 0x8B30,
    FLOAT: 0x1406, TRIANGLES: 0x0004, COLOR_BUFFER_BIT: 0x00004000,
    RGBA: 0x1908, UNSIGNED_BYTE: 0x1401
  };
}

// =====================================================================
// Mock WebGL Context (dla WebGL fingerprint)
// =====================================================================

function mockWebGLContext() {
  const ext = {
    getParameter: (p) => {
      if (p === 0x0B71) return 'Google Inc.';
      if (p === 0x0B72) return 'ANGLE (NVIDIA GeForce GTX 1060)';
      if (p === 0x0B73) return 'OpenGL ES 2.0';
      if (p === 0x8B8C) return 'OpenGL ES GLSL ES 1.00';
      return null;
    },
    getExtension: (name) => name === 'WEBGL_debug_renderer_info' ? { UNMASKED_VENDOR_WEBGL: 0x9245, UNMASKED_RENDERER_WEBGL: 0x9246 } : null,
    getSupportedExtensions: () => ['OES_texture_float', 'WEBGL_debug_renderer_info'],
    createShader: () => ({ compileShader: () => {}, getShaderParameter: () => true }),
    createProgram: () => ({ attachShader: () => {}, linkProgram: () => {}, getProgramParameter: () => true, useProgram: () => {} }),
    bindBuffer: () => {}, createBuffer: () => ({}), bufferData: () => {},
    enableVertexAttribArray: () => {}, vertexAttribPointer: () => {},
    viewport: () => {}, clearColor: () => {}, clear: () => {}, drawArrays: () => {},
    readPixels: () => {},
    ARRAY_BUFFER: 0x8892, STATIC_DRAW: 0x88E4, VERTEX_SHADER: 0x8B31, FRAGMENT_SHADER: 0x8B30,
    FLOAT: 0x1406, TRIANGLES: 0x0004, COLOR_BUFFER_BIT: 0x00004000,
    RGBA: 0x1908, UNSIGNED_BYTE: 0x1401
  };
  return ext;
}

// =====================================================================
// Inicjalizacja mocków
// =====================================================================

setupNodeGlobals();

// =====================================================================
// Główna klasa silnika (wrapper wokół IncogniaSdk)
// =====================================================================

class IncogniaEngine {
  constructor(options = {}) {
    this.options = {
      apiBaseUrl: options.apiBaseUrl || 'https://api.vinted.pl/j3r4zw',
      sdkInstanceId: options.sdkInstanceId || crypto.randomUUID(),
      loaderTimings: options.loaderTimings || { configMs: 100, scriptMs: 200 },
      onError: options.onError || ((err) => console.error('[IncogniaEngine] Error:', err)),
      config: { ...DEFAULT_CONFIG, ...options.config },
      // Tryb pracy:
      // 'full' = snapshot + interaction loop (domyślny)
      // 'snapshot-only' = tylko jeden snapshot, potem stop
      mode: options.mode || 'full'
    };

    this.sdk = null;
    this.started = false;
    this.stopped = false;
    this.lastSnapshot = null;
    this.interactionCount = 0;
  }

  async init() {
    if (this.started) throw new Error('Engine already started');

    // Podmieniamy fabryki collectorów na te z pełnymi implementacjami
    this.sdk = new IncogniaSdk({
      snapshotCollectors: createAllSnapshotCollectors(),
      interactionCollectors: createAllInteractionCollectors(),
      consumeUrl: `${this.options.apiBaseUrl}${CONSUME_SUFFIX}`,
      sdkInstanceId: this.options.sdkInstanceId,
      loaderTimings: this.options.loaderTimings,
      onError: this.options.onError,
      config: this.options.config
    });

    await this.sdk.init();
    this.started = true;
    console.log(`[IncogniaEngine] Started with sdkInstanceId=${this.options.sdkInstanceId}`);
  }

  // Ręczne wywołanie flushu interakcji (dla testów)
  async flushInteraction(trigger = 0) {
    if (!this.sdk) throw new Error('Not initialized');
    await this.sdk.flushInteraction(trigger);
    this.interactionCount++;
  }

  // Symulacja interakcji użytkownika (dla testów bez przeglądarki)
  simulateInteraction(type, data) {
    // Delegujemy do odpowiednich collectorów (jeśli mają _simulate)
    // W pełnej wersji tu podpinamy event listenery
  }

  // Zatrzymanie silnika
  stop() {
    if (this.sdk) {
      this.sdk.stop();
      this.sdk = null;
    }
    this.started = false;
    this.stopped = true;
    console.log('[IncogniaEngine] Stopped');
  }

  // Getter dla statusu
  getStatus() {
    return {
      started: this.started,
      stopped: this.stopped,
      sdkInstanceId: this.options.sdkInstanceId,
      interactionCount: this.interactionCount,
      config: this.options.config
    };
  }
}

// =====================================================================
// Helper: pojedynczy snapshot (dla F8 replay test)
// =====================================================================

async function generateSnapshot(options = {}) {
  const engine = new IncogniaEngine({
    apiBaseUrl: options.apiBaseUrl || 'https://api.vinted.pl/j3r4zw',
    sdkInstanceId: options.sdkInstanceId || crypto.randomUUID(),
    mode: 'snapshot-only',
    config: { ...DEFAULT_CONFIG, ...options.config }
  });

  await engine.init();

  // W trybie snapshot-only, SDK sam robi snapshot w init()
  // Musimy poczekać chwilę na zakończenie async collect
  await new Promise(r => setTimeout(r, 500));

  // Pobieramy ostatni wysłany payload (wymaga modyfikacji Dispatcher do expose)
  // Tutaj zwracamy status silnika
  const status = engine.getStatus();
  engine.stop();

  return { status, sdkInstanceId: engine.options.sdkInstanceId };
}

// =====================================================================
// Helper: pełny payload do /v1/consume (dla F8 replay)
// =====================================================================

async function buildConsumePayload(options = {}) {
  // Tworzymy kontekst jak w SDK
  const sdkInstanceId = options.sdkInstanceId || crypto.randomUUID();
  const loaderTimings = options.loaderTimings || { configMs: 100, scriptMs: 200 };

  const context = {
    clock: NativeClock,
    hash: sha256Hex,
    encrypt: await buildEncryptor(sdkInstanceId),
    config: { ...DEFAULT_CONFIG, ...options.config },
    sdkInstanceId,
    loaderTimings
  };

  // Uruchamiamy wszystkie snapshot collectory
  const collectors = createAllSnapshotCollectors();
  const signals = {};

  for (const collector of collectors) {
    try {
      const result = await collector.collect(context);
      Object.assign(signals, result);
    } catch (err) {
      context.onError?.({ error: 7, cause: err, stage: 'init' });
      // failureStatusCodes -> null
      for (const code of collector.failureStatusCodes) signals[code] = 2;
    }
  }

  // Budujemy model payloadu
  const payload = {
    type: 'pls',
    sdkInstanceId,
    timestamp: Date.now(),
    totalTimingMs: context.clock.now(),
    signals
  };

  // Szyfrujemy
  const dispatcher = new Dispatcher({
    consumeUrl: `${options.apiBaseUrl || 'https://api.vinted.pl/j3r4zw'}${CONSUME_SUFFIX}`,
    encrypt: context.encrypt,
    dispatchRetries: context.config.dispatchRetries,
    retryBaseDelayMs: context.config.retryBaseDelayMs,
    onError: context.onError
  });

  // Zwracamy gotowy body do POST
  const plaintext = new TextEncoder().encode(JSON.stringify(
    Object.fromEntries(Object.entries(payload.signals).map(([k, v]) => [k, typeof v === 'boolean' ? +!!v : v]))
  ));

  const cipherBytes = await context.encrypt(plaintext);
  const encryptedSignals = bytesToBase64(cipherBytes);

  return {
    v: 1,
    type: 'pls',
    siid: sdkInstanceId,
    ts: payload.timestamp,
    t: payload.totalTimingMs,
    s: encryptedSignals
  };
}

// =====================================================================
// Eksport
// =====================================================================

module.exports = {
  IncogniaEngine,
  generateSnapshot,
  buildConsumePayload,
  // Re-eksporty dla wygody
  HKDF_SALT,
  DEFAULT_CONFIG,
  CONSUME_SUFFIX
};

// =====================================================================
// CLI entry point (opcjonalny)
// =====================================================================

if (require.main === module) {
  (async () => {
    console.log('=== IncogniaEngine CLI ===');
    console.log('Usage: node incognia_engine.js [command]');
    console.log('Commands:');
    console.log('  snapshot    - wygeneruj pojedynczy snapshot');
    console.log('  payload     - zbuduj payload do /v1/consume');
    console.log('  engine      - uruchom pełny silnik (interakcyjny)');

    const cmd = process.argv[2];
    if (cmd === 'snapshot') {
      const { status, sdkInstanceId } = await generateSnapshot();
      console.log('Snapshot done:', status);
    } else if (cmd === 'payload') {
      const payload = await buildConsumePayload();
      console.log('Payload:', JSON.stringify(payload, null, 2));
    } else if (cmd === 'engine') {
      const engine = new IncogniaEngine();
      await engine.init();
      console.log('Engine running. Press Ctrl+C to stop.');
      process.on('SIGINT', () => { engine.stop(); process.exit(0); });
    } else {
      console.log('No command specified. Running payload demo...');
      const payload = await buildConsumePayload();
      console.log('Payload:', JSON.stringify(payload, null, 2));
    }
  })();
}