// incognia_sdk_reference.js
// Główne klasy SDK Incognia: Mc (InteractionScheduler), Uc (SDK), Kc (entry point).
// Wyekstrahowane z k7v3q2_BEAUTIFIED.js.

// =====================================================================
// InteractionScheduler (Mc = Mc z SDK)
// Co `flushIntervalMs` lub po przekroczeniu `bufferLimit` wywołuje `onFlush(trigger)`.
// Reaguje na visibilitychange (start/stop timera + wymuszony flush przy ukryciu strony).
// =====================================================================

class InteractionScheduler {
  constructor({ intervalMs, bufferLimit, onFlush }) {
    this.running = false;
    this.timer = null;
    this.eventCount = 0;
    this.pendingEvents = false;
    this.options = { intervalMs, bufferLimit, onFlush };
    this.onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        this.startTimer();
        return;
      }
      this.stopTimer();
      this.fire(2); // trigger=2 = page hidden
    };
  }

  start() {
    if (!this.running) {
      this.running = true;
      this.startTimer();
      document.addEventListener("visibilitychange", this.onVisibilityChange, { capture: true });
    }
  }

  noteEvents(n) {
    if (!this.running || n <= 0) return;
    this.pendingEvents = true;
    this.eventCount += n;
    if (this.eventCount >= this.options.bufferLimit) this.fire(1); // trigger=1 = buffer full
  }

  stop() {
    if (this.running) {
      this.running = false;
      this.stopTimer();
      document.removeEventListener("visibilitychange", this.onVisibilityChange, { capture: true });
    }
  }

  startTimer() {
    if (this.timer != null || document.visibilityState !== "visible") return;
    this.timer = setInterval(() => {
      if (this.pendingEvents) this.fire(0); // trigger=0 = normal flush
    }, this.options.intervalMs);
  }

  stopTimer() {
    if (this.timer == null) return;
    clearInterval(this.timer);
    this.timer = null;
  }

  fire(trigger) {
    if (!this.running) return;
    this.pendingEvents = false;
    this.eventCount = 0;
    this.stopTimer();
    this.startTimer();
    this.options.onFlush(trigger);
  }
}

// =====================================================================
// Zegar opakowujący performance.now() (Nc = Nc z SDK)
// =====================================================================

const NativeClock = { now: () => performance.now() };

// =====================================================================
// Incognia SDK class (Uc = Uc z SDK)
// Pełny lifecycle: init() → snapshot → interaction loop → stop()
// =====================================================================

const STAGE_INIT = "init";
const STAGE_RUNTIME = "runtime";

class IncogniaSdk {
  constructor({
    snapshotCollectors,
    interactionCollectors,
    consumeUrl,
    sdkInstanceId,
    loaderTimings,
    onError,
    config,
  }) {
    this.consumeUrl = consumeUrl;
    this.onError = onError;
    this.stopped = false;
    this.consecutiveFailures = 0;
    this.started = false;
    this.interactionCollectors = interactionCollectors;
    this.snapshotCollectors = snapshotCollectors;
    this.sdkInstanceId = sdkInstanceId;
    this.loaderTimings = loaderTimings;
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  async init() {
    if (!this.started) {
      this.started = true;
      try {
        const encrypt = await buildEncryptor(this.sdkInstanceId);
        this.context = {
          clock: NativeClock,
          hash: sha256Hex,
          encrypt,
          config: this.config,
          sdkInstanceId: this.sdkInstanceId,
          loaderTimings: this.loaderTimings,
        };
        this.dispatcher = new Dispatcher({
          consumeUrl: this.consumeUrl,
          encrypt,
          dispatchRetries: this.config.dispatchRetries,
          retryBaseDelayMs: this.config.retryBaseDelayMs,
          onError: this.onError,
        });
        this.interactionScheduler = new InteractionScheduler({
          intervalMs: this.config.flushIntervalMs,
          bufferLimit: this.config.bufferLimit,
          onFlush: (t) => this.flushInteraction(t).catch((e) => {
            this.onError?.call(this, { error: 5, cause: e, stage: STAGE_RUNTIME });
          }),
        });
        this.interactionScheduler.start();
        this.startInteractionCollectors();
        await this.runSnapshotPhase();
      } catch (err) {
        this.started = false;
        throw err;
      }
    }
  }

  startInteractionCollectors() {
    const noteEvents = (n) => this.interactionScheduler?.noteEvents(n);
    for (const [name, collector] of this.interactionCollectors.entries()) {
      try {
        collector.start(this.context, noteEvents);
      } catch (e) {
        this.onError?.call(this, { error: 8, errorDetails: name, cause: e, stage: STAGE_INIT });
      }
    }
  }

  async runSnapshotPhase() {
    const t = this.context.clock.now();
    const signals = await this.collectSignals({
      collectors: this.snapshotCollectors,
      run: (c) => c.collect(this.context),
      errorCode: 7,
      stage: STAGE_INIT,
    });
    await this.dispatchWithPolicy({
      payload: {
        type: "pls",
        sdkInstanceId: this.sdkInstanceId,
        timestamp: Date.now(),
        totalTimingMs: this.context.clock.now() - t,
        signals,
      },
      stage: STAGE_INIT,
    });
  }

  async flushInteraction(trigger) {
    const t = this.context.clock.now();
    const signals = await this.collectSignals({
      collectors: this.interactionCollectors,
      run: (c) => c.flush(),
      errorCode: 8,
      stage: STAGE_RUNTIME,
    });
    await this.dispatchWithPolicy({
      payload: {
        type: "it",
        sdkInstanceId: this.sdkInstanceId,
        timestamp: Date.now(),
        trigger,
        totalTimingMs: this.context.clock.now() - t,
        signals,
      },
      stage: STAGE_RUNTIME,
    });
  }

  async dispatchWithPolicy({ payload, stage }) {
    if (this.stopped) return;
    const ok = await this.dispatcher.dispatch({ payload, stage });
    if (ok) {
      this.consecutiveFailures = 0;
      return;
    }
    this.consecutiveFailures += 1;
    if (this.consecutiveFailures >= this.config.maxDispatchFailures) this.stop();
  }

  stop() {
    if (this.stopped) return;
    this.stopped = true;
    this.interactionScheduler?.stop();
    for (const [name, collector] of this.interactionCollectors.entries()) {
      try { collector.stop(); } catch (e) {
        this.onError?.call(this, { error: 8, errorDetails: name, cause: e, stage: STAGE_RUNTIME });
      }
    }
    this.onError?.call(this, { error: 6, stage: STAGE_RUNTIME });
  }

  async collectSignals({ collectors, run, errorCode, stage }) {
    const arr = await Promise.all(collectors.map(async (c) => {
      try {
        return await run(c);
      } catch (e) {
        this.onError?.call(this, { error: errorCode, errorDetails: c?.name, cause: e, stage });
        // failureStatusCodes → mapa [code] = 2
        return Object.fromEntries((c?.failureStatusCodes ?? []).map((code) => [code, 2]));
      }
    }));
    return Object.assign({}, ...arr);
  }
}

// =====================================================================
// Endpoint konsumpcji (Gc = Gc z SDK)
// =====================================================================

const CONSUME_SUFFIX = "/v1/consume";

// =====================================================================
// Entry point (Kc = Kc z SDK)
// Wywoływany przez wrapper Vinted: window.__V.initSdk({...})
// =====================================================================

async function initSdk({ apiBaseUrl, sdkInstanceId, loaderTimings, onError }) {
  let sdk;
  try {
    sdk = new IncogniaSdk({
      snapshotCollectors: collectAllSnapshotCollectors(),
      interactionCollectors: collectAllInteractionCollectors(),
      consumeUrl: `${apiBaseUrl}${CONSUME_SUFFIX}`,
      sdkInstanceId,
      loaderTimings,
      onError,
    });
  } catch (e) {
    onError?.call({ onError }, { error: 4, cause: e, stage: "init" });
    return;
  }
  try {
    await sdk.init();
  } catch (e) {
    onError?.call({ onError }, { error: 3, cause: e, stage: STAGE_INIT });
  }
}

// Placeholdery — faktyczne collectory (WebGL, canvas, audio fingerprint itp.) są pominięte
// w tej reference implementation. Pełne implementacje są w k7v3q2_BEAUTIFIED.js.
function collectAllSnapshotCollectors() { return []; }
function collectAllInteractionCollectors() { return []; }

module.exports = {
  InteractionScheduler,
  NativeClock,
  IncogniaSdk,
  initSdk,
  CONSUME_SUFFIX,
};

const { DEFAULT_CONFIG, sha256Hex, buildEncryptor } = require("./incognia_krypto_reference.js");
const { Dispatcher } = require("./incognia_transport_reference.js");
