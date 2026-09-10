// incognia_collectors_snapshot.js
// Wszystkie 17 snapshot collectors z SDK Incognia (funkcja wc).
// Wyekstrahowane z k7v3q2_BEAUTIFIED.js, zdesobfuskowane i udokumentowane.
//
// Każdy collector to obiekt: { collect(context) => Promise<signals>, failureStatusCodes, outputs }
// Kontekst: { clock, hash, encrypt, config, sdkInstanceId, loaderTimings }

// =====================================================================
// Pomocnicze: bazowy fabrykujący collectorów (uproszczony T z SDK)
// =====================================================================

function makeCollector({ run, outputs = {}, timeoutMs = 1000, statusCode, timingCode, classifyError }) {
  return {
    failureStatusCodes: statusCode ? [statusCode] : [],
    async collect(context) {
      const start = context.clock.now();
      try {
        let result;
        if (timeoutMs) {
          result = await Promise.race([
            run(context),
            new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), timeoutMs))
          ]);
        } else {
          result = await run(context);
        }
        const signals = {};
        for (const [key, fn] of Object.entries(outputs)) {
          signals[key] = fn(result);
        }
        if (timingCode) signals[timingCode] = context.clock.now() - start;
        return signals;
      } catch (err) {
        const signals = {};
        for (const key of Object.keys(outputs)) signals[key] = null;
        if (timingCode) signals[timingCode] = context.clock.now() - start;
        if (statusCode) signals[statusCode] = classifyError ? classifyError(err) : 2;
        return signals;
      }
    }
  };
}

// =====================================================================
// 1. da — ClockDrift (false seed) — pomiar czasu zegara
// =====================================================================
function createDa() {
  const SEED_KEY = 'Hn'; // 'da' seed identifier
  return makeCollector({
    run: async (ctx) => {
      // W oryginale: seed = sdkInstanceId + 'Hn', byteIndex=0, min=0, max=0.05
      // Symulujemy: zwracamy losową wartość z zakresu
      return Math.random() * 0.05;
    },
    outputs: { [SEED_KEY]: v => v },
    timeoutMs: 200,
    statusCode: 'Ct',
    timingCode: 'St'
  });
}

// =====================================================================
// 2. fa — ClockDrift (true seed) — pomiar czasu zegara
// =====================================================================
function createFa() {
  const SEED_KEY = 'Un'; // 'fa' seed identifier
  return makeCollector({
    run: async (ctx) => Math.random() * 0.05,
    outputs: { [SEED_KEY]: v => v },
    timeoutMs: 200,
    statusCode: 'Ct',
    timingCode: 'St'
  });
}

// =====================================================================
// 3. pa — RandomTiming — losowy opóźnienie 8-14ms, wartość 0.82-0.94
// =====================================================================
function createPa() {
  const VALUE_KEY = 'Wn';
  const TIMING_KEY = 'Gn';
  return makeCollector({
    run: async (ctx) => {
      const value = 0.82 + Math.random() * (0.94 - 0.82);
      const delay = 8 + Math.random() * (14 - 8);
      await new Promise(r => setTimeout(r, delay));
      return { value, timing: delay };
    },
    outputs: {
      [VALUE_KEY]: v => v.value,
      [TIMING_KEY]: v => v.timing
    },
    timeoutMs: 50,
    statusCode: 'nt',
    timingCode: 'tt'
  });
}

// =====================================================================
// 4. ra — CanvasFingerprint — 240x60 canvas z gradientem, tekstem, łukiem
// =====================================================================
function createRa() {
  const CANVAS_W = 240, CANVAS_H = 60;
  return makeCollector({
    run: async (ctx) => {
      // W Node: canvas wymaga modułu 'canvas' npm
      // Tutaj zwracamy mock sygnałów — w produkcji użyć canvas npm
      const hash = 'sha256:' + '0'.repeat(64); // placeholder
      const alphaNonzeroRatio = 0.5 + Math.random() * 0.3; // typowe 0.5-0.8
      return { hash, alphaNonzeroRatio };
    },
    outputs: {
      a: v => v.hash,
      o: v => v.alphaNonzeroRatio
    },
    timeoutMs: 200,
    statusCode: 'c',
    timingCode: 's',
    classifyError: err => (err instanceof DOMException && err.name === 'SecurityError') ? 1 : 2
  });
}

// =====================================================================
// 5. sa — UserAgentDataHighEntropy — navigator.userAgentData.getHighEntropyValues
// =====================================================================
const HIGH_ENTROPY_BRANDS = [
  'eXEKD', 'tfBoo', 'kXAEq', 'NdzEq', 'HEfyr', 'EvuNr'
].map(k => ({ brand: k, version: '1' }));

function createSa() {
  return makeCollector({
    run: async (ctx) => {
      // W Node: navigator.userAgentData nie istnieje
      // Symulujemy Chrome-like high entropy
      return {
        brands: HIGH_ENTROPY_BRANDS.map(b => `${b.brand}:${b.version}`).sort().join(';'),
        mobile: false,
        platform: 'Windows',
        highEntropy: {
          uaFullVersion: '120.0.0.0',
          platformVersion: '15.0.0',
          model: '',
          architecture: 'x86',
          bitness: '64',
          wow64: false
        }
      };
    },
    outputs: {
      xe: v => v.brands,
      Se: v => v.mobile,
      Ce: v => v.platform,
      we: v => v.highEntropy?.uaFullVersion ?? null,
      Te: v => v.highEntropy?.platformVersion ?? null,
      Ee: v => v.highEntropy?.model ?? null,
      De: v => v.highEntropy?.architecture ?? null,
      Oe: v => v.highEntropy?.bitness ?? null,
      ke: v => v.highEntropy?.wow64 ?? null
    },
    timeoutMs: 1000,
    statusCode: 'je',
    timingCode: 'Ae'
  });
}

// =====================================================================
// 6. Gs — NavigatorProperties — podstawowe właściwości navigator
// =====================================================================
function createGs() {
  return makeCollector({
    run: () => ({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      platform: 'Win32',
      language: 'pl-PL',
      languages: 'pl-PL,pl,en-US,en',
      cookieEnabled: true,
      hardwareConcurrency: 8,
      maxTouchPoints: 0,
      deviceMemory: 8,
      connection: {
        effectiveType: '4g',
        rtt: 50,
        downlink: 10,
        saveData: false
      }
    }),
    outputs: {
      se: v => v.userAgent,
      ce: v => v.platform,
      le: v => v.language,
      ue: v => v.languages,
      de: v => v.cookieEnabled,
      fe: v => v.hardwareConcurrency,
      pe: v => v.maxTouchPoints,
      me: v => v.deviceMemory,
      he: v => v.connection?.effectiveType ?? null,
      ge: v => v.connection?.rtt ?? null,
      _e: v => v.connection?.downlink ?? null,
      ve: v => v.connection?.saveData ?? null
    },
    timeoutMs: 500,
    statusCode: 'be',
    timingCode: 'ye'
  });
}

// =====================================================================
// 7. ha — NavigatorFeatures — dostępność API przeglądarki
// =====================================================================
function createHa() {
  return makeCollector({
    run: () => ({
      serviceWorker: true,
      webAssembly: true,
      webgl1: true,
      webgl2: true,
      webrtc: true,
      sharedArrayBuffer: true,
      crossOriginIsolated: false,
      getUserMedia: true,
      webgpu: false,
      audioContext: true,
      offlineAudioContext: true,
      notification: true,
      geolocation: true
    }),
    outputs: {
      wt: v => v.serviceWorker,
      Tt: v => v.webAssembly,
      Et: v => v.webgl1,
      Dt: v => v.webgl2,
      Ot: v => v.webrtc,
      kt: v => v.sharedArrayBuffer,
      At: v => v.crossOriginIsolated,
      jt: v => v.getUserMedia,
      Mt: v => v.webgpu,
      Nt: v => v.audioContext,
      Pt: v => v.offlineAudioContext,
      Ft: v => v.notification,
      It: v => v.geolocation
    },
    timeoutMs: 1000,
    statusCode: 'Rt',
    timingCode: 'Lt'
  });
}

// =====================================================================
// 8. Ki — WebDriverDetection — wykrywanie webdriver/automation
// =====================================================================
const WEBDRIVER_GLOBALS = [
  { index: 0, global: '__webdriver_evaluate' },
  { index: 1, global: '...' }, // obfuskowane
  { index: 2, global: '__webdriver_script_function' },
  { index: 3, global: '__webdriver_script_func' },
  // ... 30+ entries
];

function createKi() {
  return makeCollector({
    run: () => ({
      webdriver: navigator.webdriver ?? null,
      globalIndices: [].join(','), // żadne nie znalezione
      nonNativeIndices: [].join(',')
    }),
    outputs: {
      yt: v => v.webdriver,
      bt: v => v.globalIndices,
      xt: v => v.nonNativeIndices
    },
    timeoutMs: 500,
    statusCode: 'Ct',
    timingCode: 'St'
  });
}

// =====================================================================
// 9. Bs — TimezoneClock — strefa czasowa + clockDelta
// =====================================================================
function createBs() {
  return makeCollector({
    run: () => {
      const fmt = new Intl.DateTimeFormat().resolvedOptions();
      const now = Date.now();
      const perfOrigin = performance.timeOrigin;
      const perfNow = performance.now();
      const clockDeltaMs = Math.abs(now - (perfOrigin + perfNow));
      return {
        timeZone: fmt.timeZone ?? null,
        timezoneOffset: new Date().getTimezoneOffset(),
        clockDeltaMs
      };
    },
    outputs: {
      Me: v => v.timeZone,
      Ne: v => v.timezoneOffset,
      Pe: v => v.clockDeltaMs
    },
    timeoutMs: 500,
    statusCode: 'Ie',
    timingCode: 'Fe'
  });
}

// =====================================================================
// 10. Ys — Permissions — navigator.permissions.query
// =====================================================================
const PERMISSION_NAMES = ['geolocation', 'notifications', 'camera', 'microphone', 'persistent-storage'];
const PERMISSION_MAP = { prompt: 0, granted: 1, denied: 2 };

function createYs() {
  return makeCollector({
    run: async () => {
      // W Node: navigator.permissions nie istnieje
      // Zwracamy domyślne wartości
      const results = {};
      for (const name of PERMISSION_NAMES) {
        results[name] = 0; // prompt
      }
      return results;
    },
    outputs: {
      zt: v => v.geolocation,
      Bt: v => v.notifications,
      Vt: v => v.camera,
      Ht: v => v.microphone,
      Ut: v => v['persistent-storage']
    },
    timeoutMs: 1000,
    statusCode: 'Gt',
    timingCode: 'Wt'
  });
}

// =====================================================================
// 11. nc — StorageEstimate — cookie/localStorage/indexedDB/quota
// =====================================================================
function createNc() {
  return makeCollector({
    run: async () => ({
      cookie: true,
      local: true,
      idb: true,
      quota: 50 * 1024 * 1024, // 50MB
      usage: 1024 * 1024,      // 1MB
      persisted: false
    }),
    outputs: {
      Kt: v => v.cookie,
      qt: v => v.local,
      Jt: v => v.idb,
      Yt: v => v.quota,
      Xt: v => v.usage,
      Zt: v => v.persisted
    },
    timeoutMs: 2000,
    statusCode: '$t',
    timingCode: 'Qt'
  });
}

// =====================================================================
// 12. zs — LoaderTimings — czasy ładowania SDK
// =====================================================================
function createZs() {
  return makeCollector({
    run: (ctx) => ctx.loaderTimings ?? {},
    outputs: {
      Bn: v => v?.configMs ?? null,
      Vn: v => v?.scriptMs ?? null
    },
    timeoutMs: 500,
    statusCode: null,
    timingCode: null
  });
}

// =====================================================================
// 13. Cc — WebGLFingerprint — renderer, vendor, extensions, render hash
// =====================================================================
function createCc() {
  return makeCollector({
    run: async (ctx) => {
      // Wymaga WebGL context (canvas npm w Node)
      // Mock:
      return {
        vendor: 'Google Inc.',
        renderer: 'ANGLE (NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)',
        version: 'OpenGL ES 2.0 (ANGLE 2.1.0)',
        shadingLanguageVersion: 'OpenGL ES GLSL ES 1.00',
        unmaskedVendor: 'NVIDIA Corporation',
        unmaskedRenderer: 'NVIDIA GeForce GTX 1060',
        extensionsHash: 'sha256:' + 'a'.repeat(64),
        paramsHash: 'sha256:' + 'b'.repeat(64),
        renderHash: 'sha256:' + 'c'.repeat(64)
      };
    },
    outputs: {
      en: v => v.vendor,
      tn: v => v.renderer,
      nn: v => v.version,
      rn: v => v.shadingLanguageVersion,
      an: v => v.unmaskedVendor,
      on: v => v.unmaskedRenderer,
      sn: v => v.extensionsHash,
      cn: v => v.paramsHash,
      ln: v => v.renderHash
    },
    timeoutMs: 300,
    statusCode: 'dn',
    timingCode: 'un'
  });
}

// =====================================================================
// 14. Hr — AudioFingerprint — OfflineAudioContext oscillator + compressor
// =====================================================================
function createHr() {
  return makeCollector({
    run: async (ctx) => {
      // Wymaga OfflineAudioContext (web-audio-api npm w Node)
      // Mock:
      return {
        sum: 12345.67,
        sampleRate: 44100,
        channels: 1
      };
    },
    outputs: {
      fn: v => v.sum,
      pn: v => v.sampleRate,
      mn: v => v.channels
    },
    timeoutMs: 1000,
    statusCode: 'gn',
    timingCode: 'hn'
  });
}

// =====================================================================
// 15. Rs — FontDetection — 130+ fontów, sprawdzanie offsetWidth/Height
// =====================================================================
const FONT_LIST = [
  { index: 0, family: 'Arial' }, { index: 1, family: 'Arial Black' },
  { index: 2, family: '...' }, // 130+ entries
  // Skrócona lista dla reference
  { index: 3, family: 'Calibri' }, { index: 4, family: 'Cambria' },
  { index: 5, family: 'Consolas' }, { index: 6, family: 'Courier New' },
  { index: 7, family: 'Georgia' }, { index: 8, family: 'Helvetica' },
  { index: 9, family: 'Times New Roman' }, { index: 10, family: 'Verdana' }
];
const BASE_FONTS = ['monospace', 'sans-serif', 'serif'];
const TEST_STRING = '...'; // długi string do pomiaru

function createRs() {
  return makeCollector({
    run: async () => {
      // W Node: wymaga canvas do pomiaru tekstu
      // Mock: zwracamy kilka indeksów
      return [0, 3, 5, 7, 9].join(',');
    },
    outputs: {
      _n: v => v,
      vn: v => v.split(',').length
    },
    timeoutMs: 1000,
    statusCode: 'bn',
    timingCode: 'yn'
  });
}

// =====================================================================
// 16. Ws — MediaCapabilities — audio/video canPlayType + MSE
// =====================================================================
const AUDIO_TYPES = ['audio/ogg', 'audio/flac', 'audio/mp3', 'audio/aac', 'audio/x-m4a'];
const VIDEO_TYPES = ['video/mp4; codecs="avc1.42E01E"', 'video/webm; codecs="vp8"', 'video/webm; codecs="vp9"'];

function createWs() {
  return makeCollector({
    run: () => {
      // Mock canPlayType results
      const audioCanPlay = AUDIO_TYPES.map(() => 2).join(','); // 2 = probably
      const videoCanPlay = VIDEO_TYPES.map(() => 2).join(',');
      return {
        audioCanPlay,
        videoCanPlay,
        audioMse: AUDIO_TYPES.map(() => 1).join(','), // 1 = maybe
        videoMse: VIDEO_TYPES.map(() => 1).join(',')
      };
    },
    outputs: {
      xn: v => v.audioCanPlay,
      Sn: v => v.videoCanPlay,
      Cn: v => v.audioMse,
      wn: v => v.videoMse
    },
    timeoutMs: 1000,
    statusCode: 'En',
    timingCode: 'Tn'
  });
}

// =====================================================================
// 17. ma — ScreenViewport — screen, viewport, pointer, hover
// =====================================================================
function createMa() {
  return makeCollector({
    run: () => ({
      screen: { width: 1920, height: 1080, availWidth: 1920, availHeight: 1040, colorDepth: 24, orientation: { type: 'landscape-primary' } },
      innerWidth: 1920,
      innerHeight: 1040,
      outerWidth: 1920,
      outerHeight: 1080,
      devicePixelRatio: 1,
      visualViewport: { width: 1920, height: 1040, scale: 1 },
      orientationType: 'landscape-primary',
      pointerFine: true,
      pointerCoarse: false,
      hoverHover: true,
      hoverNone: false
    }),
    outputs: {
      Le: v => v.screen.width,
      Re: v => v.screen.height,
      ze: v => v.screen.availWidth,
      Be: v => v.screen.availHeight,
      Ve: v => v.screen.colorDepth,
      He: v => v.innerWidth,
      Ue: v => v.innerHeight,
      We: v => v.outerWidth,
      Ge: v => v.outerHeight,
      Ke: v => v.devicePixelRatio,
      qe: v => v.visualViewport?.width ?? null,
      Je: v => v.visualViewport?.height ?? null,
      Ye: v => v.visualViewport?.scale ?? null,
      Xe: v => v.orientationType,
      Ze: v => v.pointerFine,
      Qe: v => v.pointerCoarse,
      $e: v => v.hoverHover,
      et: v => v.hoverNone
    },
    timeoutMs: 500,
    statusCode: 'nt',
    timingCode: 'tt'
  });
}

// =====================================================================
// Eksport: tablica 17 collectorów (kolejność jak w wc)
// =====================================================================

function createAllSnapshotCollectors() {
  return [
    createDa(),   // da
    createGs(),   // Gs
    createSa(),   // sa
    createFa(),   // fa
    createRa(),   // ra
    createBs(),   // Bs
    createKi(),   // Ki
    createHa(),   // ha
    createYs(),   // Ys
    createNc(),   // nc
    createZs(),   // zs
    createCc(),   // Cc
    createHr(),   // Hr
    createRs(),   // Rs
    createWs(),   // Ws
    createMa(),   // ma
    createPa()    // pa
  ];
}

module.exports = {
  createAllSnapshotCollectors,
  // Individual exports for testing
  createDa, createGs, createSa, createFa, createRa,
  createBs, createKi, createHa, createYs, createNc,
  createZs, createCc, createHr, createRs, createWs,
  createMa, createPa
};