// incognia_engine_extended.js
// Rozszerzenie incognia_engine.js o WebSocket + JWE + Connectioncheck
// Wymaga: incognia_engine.js + incognia_krypto_reference.js

const crypto = require('crypto');
const WebSocket = require('ws');
const {
  HKDF_SALT,
  deriveAesKey,
  aesGcmEncrypt,
  bytesToBase64
} = require('./incognia_krypto_reference.js');

const INCOGNIA_CONSTANTS = {
  CONNECTIONCHECK_URL: 'https://conn-check.icg-in.com/connectioncheck',
  NETCONN_URL: 'https://conn-check.icg-in.info/netconn',
  WS_URL: 'wss://conn-check.icg-in.info/wsconn',
  CONSUME_SUFFIX: '/v1/consume',
  CONFIG: {
    flushIntervalMs: 5000,
    bufferLimit: 50,
    dispatchRetries: 3,
    maxDispatchFailures: 3,
    retryBaseDelayMs: 500,
  }
};

// RSA-OAEP unwrap dla JWE (używa WebCrypto API)
async function unwrapJweKey(jweToken, privateKeyPem) {
  // JWE format: header.encryptedKey.iv.ciphertext.tag
  // header: {"alg":"RSA-OAEP","enc":"A128CBC-HS256"}
  const parts = jweToken.split('.');
  if (parts.length !== 5) throw new Error('Invalid JWE format');

  const header = JSON.parse(Buffer.from(parts[0], 'base64').toString());
  const encryptedKey = Buffer.from(parts[1], 'base64');
  const iv = Buffer.from(parts[2], 'base64');
  const ciphertext = Buffer.from(parts[3], 'base64');
  const tag = Buffer.from(parts[4], 'base64');

  // Import private key
  const privateKey = await crypto.subtle.importKey(
    'pkcs8',
    pemToArrayBuffer(privateKeyPem),
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['unwrapKey']
  );

  // Unwrap CEK (Content Encryption Key)
  const cek = await crypto.subtle.unwrapKey(
    'raw',
    encryptedKey,
    privateKey,
    { name: 'RSA-OAEP' },
    { name: 'AES-CBC', length: 128 },
    false,
    ['decrypt']
  );

  // Decrypt payload with AES-CBC-HS256
  const decipher = crypto.createDecipheriv('aes-128-cbc', new Uint8Array(cek).slice(0, 16), iv);
  decipher.setAuthTag(tag);
  const decrypted = Buffer.concat([decipher.update(ciphertext), decipher.final()]);

  return JSON.parse(decrypted.toString());
}

// PEM to ArrayBuffer helper
function pemToArrayBuffer(pem) {
  const b64 = pem.replace(/-----BEGIN PRIVATE KEY-----/, '')
    .replace(/-----END PRIVATE KEY-----/, '')
    .replace(/\n/g, '');
  const bytes = Buffer.from(b64, 'base64');
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

// Generuj JWE token dla x-incognia-request-token (AES-GCM - jak w SDK)
// Wymaga derived key - przekazujemy engine instance
async function generateJweRequestToken(engine, payload) {
  // Używamy AES-GCM (nie AES-CBC jak w connectioncheck JWE)
  // To jest token który Incognia SDK generuje dla payment endpoint
  if (!engine.aesKey) {
    engine.aesKey = await deriveAesKey(engine.sdkInstanceId);
  }
  const plaintext = typeof payload === 'string' ? payload : JSON.stringify(payload);
  const plaintextBytes = new TextEncoder().encode(plaintext);
  const encrypted = await aesGcmEncrypt(engine.aesKey, plaintextBytes);
  return bytesToBase64(encrypted);
}

class IncogniaExtendedEngine {
  constructor(config = {}) {
    this.config = { ...INCOGNIA_CONSTANTS.CONFIG, ...config };
    this.sdkInstanceId = config.sdkInstanceId || crypto.randomUUID();
    this.apiBaseUrl = config.apiBaseUrl || 'https://api.vinted.pl/j3r4zw';
    this.aesKey = null;
    this.ws = null;
    this.wsConnected = false;
    this.consumeInterval = null;
    this.interactionBuffer = [];
  }

  // === INICJALIZACJA ===

  async init() {
    // 1. Derive AES key z sdkInstanceId
    this.aesKey = await deriveAesKey(this.sdkInstanceId);
    console.log('[Incognia] AES key derived');

    // 2. Connectioncheck flow (opcjonalny - jeśli serwer wymaga)
    await this.connectionCheckFlow();

    // 3. Uruchom consume loop
    this.startConsumeLoop();

    return this;
  }

  // Connectioncheck: POST /connectioncheck -> GET /netconn -> WS upgrade
  async connectionCheckFlow() {
    try {
      // Step 1: POST /connectioncheck
      const ccResp = await fetch(INCOGNIA_CONSTANTS.CONNECTIONCHECK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sdk_instance_id: this.sdkInstanceId })
      });
      const ccText = await ccResp.text();
      let ccData;
      try { ccData = JSON.parse(ccText); } catch { ccData = { raw: ccText }; }
      console.log('[Incognia] Connectioncheck:', ccData);

      // Step 2: GET /netconn (zwraca ICG-Connection-Token JWE)
      const netconnResp = await fetch(INCOGNIA_CONSTANTS.NETCONN_URL, {
        headers: { 'Accept': 'application/json' }
      });
      const netconnText = await netconnResp.text();
      let netconnData;
      try { netconnData = JSON.parse(netconnText); } catch { netconnData = { raw: netconnText }; }
      const jweToken = netconnResp.headers.get('ICG-Connection-Token') ||
                       netconnData.token ||
                       netconnData.connection_token;
      console.log('[Incognia] Netconn JWE token received');

      // Step 3: WebSocket upgrade z JWE tokenem
      if (jweToken) {
        await this.connectWebSocket(jweToken);
      }
    } catch (e) {
      console.warn('[Incognia] Connectioncheck flow failed (optional):', e.message);
    }
  }

  // WebSocket connection
  async connectWebSocket(jweToken) {
    return new Promise((resolve, reject) => {
      const wsUrl = `${INCOGNIA_CONSTANTS.WS_URL}?token=${encodeURIComponent(jweToken)}`;
      this.ws = new WebSocket(wsUrl);

      this.ws.on('open', () => {
        console.log('[Incognia] WebSocket connected');
        this.wsConnected = true;
        resolve();
      });

      this.ws.on('message', (data) => {
        this.handleWsMessage(data);
      });

      this.ws.on('error', (err) => {
        console.error('[Incognia] WebSocket error:', err.message);
      });

      this.ws.on('close', () => {
        console.log('[Incognia] WebSocket closed');
        this.wsConnected = false;
      });

      // Timeout
      setTimeout(() => {
        if (!this.wsConnected) reject(new Error('WebSocket connection timeout'));
      }, 10000);
    });
  }

  // Obsługa wiadomości WebSocket (binary frames - protobuf?)
  handleWsMessage(data) {
    // DataDome/Incognia WS frames są zazwyczaj protobuf
    // Tutaj logujemy do analizy
    console.log('[Incognia] WS message:', data.length, 'bytes');
    // TODO: parse protobuf jeśli znany schema
  }

  // === CONSUME LOOP ===

  startConsumeLoop() {
    // Initial snapshot (type=pls)
    this.sendConsume('pls');

    // Periodic interaction flush (type=it)
    this.consumeInterval = setInterval(() => {
      this.sendConsume('it');
    }, this.config.flushIntervalMs);
  }

  // Wyślij consume request
  async sendConsume(type) {
    const payload = await this.buildConsumePayload(type);
    const url = `${this.apiBaseUrl}${INCOGNIA_CONSTANTS.CONSUME_SUFFIX}`;

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-incognia-request-token': payload.token
        },
        body: JSON.stringify(payload.body)
      });
      console.log(`[Incognia] Consume ${type}: ${resp.status}`);
      const text = await resp.text();
      try {
        return JSON.parse(text);
      } catch {
        return { raw: text, status: resp.status };
      }
    } catch (e) {
      console.error('[Incognia] Consume failed:', e.message);
    }
  }

  // Buduj payload dla /v1/consume
  async buildConsumePayload(type) {
    const signals = this.collectSignals(type);
    const plaintext = JSON.stringify(signals);
    const plaintextBytes = new TextEncoder().encode(plaintext);
    const encrypted = await aesGcmEncrypt(this.aesKey, plaintextBytes);
    const encryptedB64 = bytesToBase64(encrypted);

    const body = {
      v: 1,
      type,
      siid: this.sdkInstanceId,
      ts: Date.now(),
      t: type === 'pls' ? 1000 : 1, // snapshot time ~1s, interaction ~1ms
      s: encryptedB64 // base64(IV || ciphertext)
    };

    // x-incognia-request-token to osobny JWE (AES-GCM)
    const token = await generateJweRequestToken(this, { siid: this.sdkInstanceId, ts: Date.now() });

    return { body, token };
  }

  // Zbierz sygnały (używa collectorów z incognia_engine.js)
  collectSignals(type) {
    // Tu wywołujemy collectorów z incognia_collectors_snapshot.js
    // Dla uproszczenia zwracamy placeholder
    return {
      type,
      sdkInstanceId: this.sdkInstanceId,
      timestamp: Date.now(),
      signals: this.interactionBuffer.splice(0)
    };
  }

  // Dodaj interakcję do bufora
  addInteraction(interaction) {
    this.interactionBuffer.push({
      ...interaction,
      ts: Date.now()
    });

    // Flush jeśli buffer pełny
    if (this.interactionBuffer.length >= this.config.bufferLimit) {
      this.sendConsume('it');
    }
  }

  // === PUBLIC API ===

  // Generuj x-incognia-request-token dla payment endpoint
  async generateRequestToken() {
    return generateJweRequestToken(this, {
      siid: this.sdkInstanceId,
      ts: Date.now()
    });
  }

  // Pobierz stan do synchronizacji z curl_cffi
  getState() {
    return {
      sdkInstanceId: this.sdkInstanceId,
      aesKeyDerived: !!this.aesKey,
      wsConnected: this.wsConnected,
      bufferSize: this.interactionBuffer.length
    };
  }

  // Zatrzymaj
  stop() {
    if (this.consumeInterval) clearInterval(this.consumeInterval);
    if (this.ws) this.ws.close();
  }
}

module.exports = { IncogniaExtendedEngine, generateJweRequestToken, unwrapJweKey };