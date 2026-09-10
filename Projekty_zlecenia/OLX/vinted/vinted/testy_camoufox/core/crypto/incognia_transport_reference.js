// incognia_transport_reference.js
// Warstwa transportu i retry SDK Incognia.
// Wyekstrahowane z k7v3q2_BEAUTIFIED.js (klasy Bc, Vc, Hc + helper Rc).

// =====================================================================
// HttpStatusError (zc = zc z SDK)
// =====================================================================

class HttpStatusError extends Error {
  constructor(status) {
    super("HTTP " + status);
    this.name = "HttpStatusError";
    this.status = status;
  }
}

// =====================================================================
// Transport (Bc = Bc z SDK)
// POST z credentials:include, keepalive, content-type:application/json
// Rzuca HttpStatusError jeśli response.ok === false
// =====================================================================

class Transport {
  constructor({ url }) {
    this.url = url;
  }

  async send(body) {
    const opts = {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
      credentials: "include",
      keepalive: true,
    };
    const res = await fetch(this.url, opts);
    if (!res.ok) throw new HttpStatusError(res.status);
  }
}

// =====================================================================
// Retry-with-backoff (Vc = Vc z SDK)
// attempts: ile razy spróbować (domyślnie 3)
// baseDelayMs: bazowy czas opóźnienia (mnożony losowo × 2^n)
// =====================================================================

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function withRetry(fn, { attempts, baseDelayMs }) {
  let lastErr;
  for (let n = 0; n < attempts; n++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      if (n < attempts - 1) {
        const delay = Math.random() * baseDelayMs * Math.pow(2, n);
        await sleep(delay);
      }
    }
  }
  throw lastErr;
}

// =====================================================================
// Model output (Rc = Rc z SDK)
// Format wysyłany do /j3r4zw/v1/consume
// =====================================================================

const MODEL_VERSION = 1;

function encodeModel({ model, encryptedSignals }) {
  return {
    v: MODEL_VERSION,
    type: model.type,                    // "pls" (snapshot) lub "it" (interaction trigger)
    siid: model.sdkInstanceId,
    ts: model.timestamp,
    t: model.totalTimingMs,
    ...(model.type === "it" ? { tr: model.trigger } : {}),
    s: encryptedSignals,                 // base64 z IV || ciphertext
  };
}

// =====================================================================
// Dispatcher (Hc = Hc z SDK)
// Konwertuje signals → JSON → szyfruje → POST → /v1/consume
// =====================================================================

class Dispatcher {
  constructor({ consumeUrl, encrypt, dispatchRetries, retryBaseDelayMs, onError }) {
    this.encrypt = encrypt;
    this.onError = onError;
    this.dispatchRetries = dispatchRetries;
    this.retryBaseDelayMs = retryBaseDelayMs;
    this.transport = new Transport({ url: consumeUrl });
  }

  async dispatch({ payload, stage }) {
    // 1. JSON.stringify(sygnałów) — konwersja boolean→0/1
    let plaintext;
    try {
      const conv = {};
      for (const [k, v] of Object.entries(payload.signals)) {
        conv[k] = typeof v === "boolean" ? +!!v : v;
      }
      plaintext = new TextEncoder().encode(JSON.stringify(conv));
    } catch (e) {
      this.onError?.call(this, { error: 0, cause: e, stage });
      return false;
    }

    // 2. Szyfrowanie AES-GCM + base64
    let cipherB64;
    try {
      cipherB64 = await bytesToBase64(await this.encrypt(plaintext));
    } catch (e) {
      this.onError?.call(this, { error: 1, cause: e, stage });
      return false;
    }

    // 3. Budowa modelu + JSON
    const body = JSON.stringify(encodeModel({
      model: payload,
      encryptedSignals: cipherB64,
    }));

    // 4. POST z retry
    try {
      await withRetry(
        () => this.transport.send(body),
        { attempts: this.dispatchRetries, baseDelayMs: this.retryBaseDelayMs }
      );
      return true;
    } catch (e) {
      const detail = e instanceof HttpStatusError
        ? { error: 2, errorDetails: e.status, stage }
        : { error: 2, cause: e, stage };
      this.onError?.call(this, detail);
      return false;
    }
  }
}

// Re-eksport (wymagane przez incognia_krypto_reference.js)
const { bytesToBase64 } = require("./incognia_krypto_reference.js");

module.exports = {
  HttpStatusError,
  Transport,
  withRetry,
  Dispatcher,
  encodeModel,
};
