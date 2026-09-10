/**
 * hybrid_consume_loop.js - Incognia /v1/consume loop w Node.js
 * 
 * Czyta tokeny z hybrid_tokens.json (zapisywane przez CamoufoxTokenRefresher)
 * Co 5 sekund wysyła zaszyfrowane sygnały do /v1/consume
 * Używa WebCrypto API (HKDF + AES-GCM) - identyczne jak demo_node_crypto.js
 * 
 * Uruchomienie: node hybrid_consume_loop.js
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// =====================================================================
// KONFIGURACJA
// =====================================================================

const TOKEN_STORE_PATH = path.join(__dirname, 'hybrid_tokens.json');
const HARVEST_SIGNALS_PATH = path.join(__dirname, 'harvest_signals.json');
const CONSUME_INTERVAL_MS = 5000; // 5 sekund (jak w SDK Incognia)
const DISPATCH_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 500;

// Stałe z SDK Incognia (z incognia_krypto_reference.js)
const HKDF_SALT = new TextEncoder().encode("L6ZhSbP9TciQDgxC7pjukGhl4vYis56m");
const MODEL_VERSION = 1;

// =====================================================================
// WEB CRYPTO - HKDF + AES-GCM (z incognia_krypto_reference.js)
// =====================================================================

const BASE64_CHUNK = 32_768;

function bytesToBase64(bytes) {
    if (bytes.length === 0) return "";
    let out = "";
    for (let i = 0; i < bytes.length; i += BASE64_CHUNK) {
        const slice = bytes.subarray(i, Math.min(i + BASE64_CHUNK, bytes.length));
        out += String.fromCharCode.apply(null, Array.from(slice));
    }
    return btoa(out);
}

async function sha256Hex(bytes) {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const arr = new Uint8Array(digest);
    let hex = "";
    for (const b of arr) hex += b.toString(16).padStart(2, "0");
    return "sha256:" + hex;
}

async function deriveAesKey(sdkInstanceId) {
    const ikm = new TextEncoder().encode(sdkInstanceId);
    const baseKey = await crypto.subtle.importKey(
        "raw", ikm, "HKDF", false, ["deriveKey"]
    );
    return crypto.subtle.deriveKey(
        { name: "HKDF", salt: HKDF_SALT, info: new Uint8Array(0), hash: "SHA-256" },
        baseKey,
        { name: "AES-GCM", length: 256 },
        true,
        ["encrypt", "decrypt"]
    );
}

async function aesGcmEncrypt(key, plaintext) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const cipherParams = { name: "AES-GCM", iv };
    const ct = await crypto.subtle.encrypt(cipherParams, key, plaintext);
    const ctBytes = new Uint8Array(ct);
    const out = new Uint8Array(iv.length + ctBytes.length);
    out.set(iv, 0);
    out.set(ctBytes, iv.length);
    return out;
}

async function buildEncryptor(sdkInstanceId) {
    const key = await deriveAesKey(sdkInstanceId);
    return (plaintext) => aesGcmEncrypt(key, plaintext);
}

// =====================================================================
// TRANSPORT (z incognia_transport_reference.js)
// =====================================================================

class HttpStatusError extends Error {
    constructor(status) {
        super("HTTP " + status);
        this.name = "HttpStatusError";
        this.status = status;
    }
}

async function transportSend(url, body) {
    return new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const options = {
            hostname: urlObj.hostname,
            path: urlObj.pathname + urlObj.search,
            method: "POST",
            headers: {
                "content-type": "application/json",
                "content-length": Buffer.byteLength(body),
            },
        };

        const req = https.request(options, (res) => {
            let data = "";
            res.on("data", chunk => data += chunk);
            res.on("end", () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve({ status: res.statusCode, data });
                } else {
                    reject(new HttpStatusError(res.statusCode));
                }
            });
        });

        req.on("error", reject);
        req.write(body);
        req.end();
    });
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
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

function encodeModel({ model, encryptedSignals }) {
    return {
        v: MODEL_VERSION,
        type: model.type,
        siid: model.sdkInstanceId,
        ts: model.timestamp,
        t: model.totalTimingMs,
        ...(model.type === "it" ? { tr: model.trigger } : {}),
        s: encryptedSignals,
    };
}

class Dispatcher {
    constructor({ consumeUrl, encrypt, dispatchRetries, retryBaseDelayMs, onError }) {
        this.encrypt = encrypt;
        this.onError = onError;
        this.dispatchRetries = dispatchRetries;
        this.retryBaseDelayMs = retryBaseDelayMs;
        this.consumeUrl = consumeUrl;
    }

    async dispatch({ payload, stage }) {
        // 1. JSON.stringify sygnałów (boolean -> 0/1)
        let plaintext;
        try {
            const conv = {};
            for (const [k, v] of Object.entries(payload.signals)) {
                conv[k] = typeof v === "boolean" ? +!!v : v;
            }
            plaintext = new TextEncoder().encode(JSON.stringify(conv));
        } catch (e) {
            this.onError?.({ error: 0, cause: e, stage });
            return false;
        }

        // 2. Szyfrowanie AES-GCM + base64
        let cipherB64;
        try {
            cipherB64 = bytesToBase64(await this.encrypt(plaintext));
        } catch (e) {
            this.onError?.({ error: 1, cause: e, stage });
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
                () => transportSend(this.consumeUrl, body),
                { attempts: this.dispatchRetries, baseDelayMs: this.retryBaseDelayMs }
            );
            return true;
        } catch (e) {
            const detail = e instanceof HttpStatusError
                ? { error: 2, errorDetails: e.status, stage }
                : { error: 2, cause: e, stage };
            this.onError?.(detail);
            return false;
        }
    }
}

// =====================================================================
// SYGNAŁY (harvest realnych wartości z przeglądarki + fallback symulowany)
// =====================================================================

// Wczytuje realne sygnały zebrane przez spike_harvest_signals.py (Playwright).
// Lekki silnik JS nie ma dostępu do canvas/WebGL/audio, więc te wartości
// muszą pochodzić z jednorazowego harvestu w prawdziwej przeglądarce.
function loadHarvestSignals() {
    try {
        if (!fs.existsSync(HARVEST_SIGNALS_PATH)) return null;
        const raw = JSON.parse(fs.readFileSync(HARVEST_SIGNALS_PATH, 'utf8'));
        return raw.signals ?? null;
    } catch (e) {
        console.warn('⚠️  Nie udało się wczytać harvest_signals.json:', e.message);
        return null;
    }
}

// Mapuje realne klucze z harvestu (spike_harvest_signals.py) na czytelne
// klucze używane w tym loopie. Klucze bez odpowiednika zostają z fake'ów.
const HARVEST_KEY_MAP = {
    hardwareConcurrency: 'hw_concurrency',
    maxTouchPoints: 'max_touch_points',
    deviceMemory: 'device_memory',
    canvas_data_url: 'canvas_fp',
    canvas_alpha_nonzero: 'canvas_alpha',
    webgl_vendor: 'webgl_vendor',
    webgl_renderer: 'webgl_renderer',
    webgl_version: 'webgl_version',
    webgl_shading: 'webgl_shading',
    webgl_unmasked_vendor: 'webgl_unmasked_vendor',
    webgl_unmasked_renderer: 'webgl_unmasked_renderer',
    webgl_extensions: 'webgl_extensions_hash',
    audio_sum: 'audio_sum',
    audio_sample_rate: 'audio_sample_rate',
    audio_channels: 'audio_channels',
    perm_geolocation: 'perm_geolocation',
    perm_notifications: 'perm_notifications',
    perm_camera: 'perm_camera',
    perm_microphone: 'perm_microphone',
    perm_persistent_storage: 'perm_persistent_storage',
    cookie_enabled: 'cookie_enabled',
    localstorage: 'localstorage',
    indexeddb: 'indexeddb',
    storage_quota: 'storage_quota',
    storage_usage: 'storage_usage',
    storage_persisted: 'storage_persisted',
    screen_width: 'screen_width',
    screen_height: 'screen_height',
    screen_avail_width: 'screen_avail_width',
    screen_avail_height: 'screen_avail_height',
    screen_color_depth: 'screen_color_depth',
    device_pixel_ratio: 'device_pixel_ratio',
    visual_viewport_width: 'visual_viewport_width',
    visual_viewport_height: 'visual_viewport_height',
    visual_viewport_scale: 'visual_viewport_scale',
    orientation_type: 'orientation_type',
    timezone: 'timezone',
    timezone_offset: 'timezone_offset',
    audio_can_play: 'audio_can_play',
    video_can_play: 'video_can_play',
    service_worker: 'service_worker',
    webassembly: 'webassembly',
    webgl1: 'webgl1',
    webgl2: 'webgl2',
    webrtc: 'webrtc',
    shared_array_buffer: 'shared_array_buffer',
    cross_origin_isolated: 'cross_origin_isolated',
    audio_context: 'audio_context',
    offline_audio_context: 'offline_audio_context',
};

// Buduje sygnały snapshotu: realne wartości z harvestu (jeśli są) + fallback.
function buildSnapshotSignals() {
    const base = generateFakeSnapshotSignals();
    const harvest = loadHarvestSignals();
    if (!harvest) {
        console.log('⚠️  Brak harvest_signals.json — używam symulowanych sygnałów.');
        return base;
    }
    let mapped = 0;
    for (const [src, dst] of Object.entries(HARVEST_KEY_MAP)) {
        if (harvest[src] !== undefined && harvest[src] !== null) {
            base[dst] = harvest[src];
            mapped++;
        }
    }

    // Spójność WebGL: gdy harvest mówi, że WebGL jest niedostępny
    // (block_webgl=True w Camoufox), nie wolno zostawiać fake'owych
    // wartości NVIDIA — serwer widziałby sprzeczność "brak WebGL + renderer NVIDIA".
    if (harvest.webgl1 === false && harvest.webgl2 === false) {
        base.webgl_vendor = null;
        base.webgl_renderer = null;
        base.webgl_version = null;
        base.webgl_shading = null;
        base.webgl_unmasked_vendor = null;
        base.webgl_unmasked_renderer = null;
        base.webgl_extensions_hash = null;
        base.webgl_params_hash = null;
        base.webgl_render_hash = null;
        console.log('ℹ️  WebGL wyłączony w harvest — klucze webgl_* ustawione na null.');
    }

    console.log(`✅ Podpięto ${mapped} realnych sygnałów z harvestu.`);
    return base;
}

function generateFakeSnapshotSignals() {
    // Symulacja snapshot phase (pls) - device fingerprint
    return {
        // Canvas fingerprint (symulowany)
        "canvas_fp": "sha256:fake_canvas_hash_" + Date.now(),
        "canvas_alpha": 0.5,
        
        // WebGL (symulowany)
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)",
        "webgl_version": "OpenGL ES 3.0",
        "webgl_shading": "OpenGL ES GLSL ES 3.00",
        "webgl_unmasked_vendor": "NVIDIA Corporation",
        "webgl_unmasked_renderer": "NVIDIA GeForce RTX 3080",
        "webgl_extensions_hash": "sha256:fake_extensions",
        "webgl_params_hash": "sha256:fake_params",
        "webgl_render_hash": "sha256:fake_render",
        
        // Audio (symulowany)
        "audio_sum": 12345,
        "audio_sample_rate": 44100,
        "audio_channels": 2,
        
        // Fonts (symulowane - 125 fontów w SDK)
        "fonts_detected": 42,
        
        // Permissions
        "perm_geolocation": 1,
        "perm_notifications": 1,
        "perm_camera": 0,
        "perm_microphone": 0,
        "perm_persistent_storage": 1,
        
        // Storage
        "cookie_enabled": 1,
        "localstorage": 1,
        "indexeddb": 1,
        "storage_quota": 1073741824,
        "storage_usage": 5242880,
        "storage_persisted": 1,
        
        // Navigator
        "hw_concurrency": 16,
        "device_memory": 8,
        "max_touch_points": 0,
        "connection_type": "4g",
        "connection_rtt": 50,
        "connection_downlink": 10.5,
        "connection_save_data": 0,
        "gpu_vendor": "NVIDIA",
        "gpu_renderer": "RTX 3080",
        
        // Screen
        "screen_width": 1920,
        "screen_height": 1080,
        "screen_avail_width": 1920,
        "screen_avail_height": 1040,
        "screen_color_depth": 24,
        "device_pixel_ratio": 1,
        "visual_viewport_width": 1920,
        "visual_viewport_height": 1040,
        "visual_viewport_scale": 1,
        "orientation_type": "landscape-primary",
        "pointer_fine": 1,
        "pointer_coarse": 0,
        "hover_hover": 1,
        "hover_none": 0,
        
        // Timezone
        "timezone": "Europe/Warsaw",
        "timezone_offset": -120,
        "clock_delta_ms": 5,
        
        // Media
        "audio_can_play": "2,2,2,2,2,2,2,2",
        "video_can_play": "2,2,2,2,2,2,2,2,2",
        "audio_mse": "2,2,2,2,2,2,2",
        "video_mse": "2,2,2,2,2,2,2,2,2",
        
        // Features
        "service_worker": 1,
        "webassembly": 1,
        "webgl1": 1,
        "webgl2": 1,
        "webrtc": 1,
        "shared_array_buffer": 1,
        "cross_origin_isolated": 1,
        "get_user_media": 1,
        "webgpu": 1,
        "audio_context": 1,
        "offline_audio_context": 1,
        "notification": 1,
        "geolocation": 1,
    };
}

function generateFakeInteractionSignals(trigger) {
    // Symulacja interaction phase (it) - behavioral
    const now = Date.now();
    return {
        // Clock
        "visible_ms": Math.floor(Math.random() * 5000) + 1000,
        "focused_ms": Math.floor(Math.random() * 5000) + 1000,
        
        // Mouse hover
        "over_count": Math.floor(Math.random() * 10) + 1,
        "out_count": Math.floor(Math.random() * 10) + 1,
        "dwell_ms_p50": Math.floor(Math.random() * 200) + 50,
        "dwell_ms_p95": Math.floor(Math.random() * 500) + 200,
        
        // Keyboard
        "keydown_count": Math.floor(Math.random() * 20) + 5,
        "keyup_count": Math.floor(Math.random() * 20) + 5,
        "inter_key_ms_p50": Math.floor(Math.random() * 100) + 50,
        "inter_key_ms_p95": Math.floor(Math.random() * 200) + 100,
        "paste_count": 0,
        "paste_max_len_bucket": 0,
        
        // Pointer
        "pointer_move_count": Math.floor(Math.random() * 100) + 20,
        "pointer_down_count": Math.floor(Math.random() * 10) + 2,
        "pointer_up_count": Math.floor(Math.random() * 10) + 2,
        "click_count": Math.floor(Math.random() * 5) + 1,
        "pointer_type_mouse": Math.floor(Math.random() * 100) + 20,
        "pointer_type_pen": 0,
        "pointer_type_touch": 0,
        "time_to_first_pointer_ms": Math.floor(Math.random() * 2000) + 500,
        "move_pause_count": Math.floor(Math.random() * 20) + 5,
        "move_pause_ms_p50": Math.floor(Math.random() * 100) + 50,
        "move_pause_ms_p95": Math.floor(Math.random() * 300) + 150,
        
        // Scroll
        "scroll_count": Math.floor(Math.random() * 20) + 5,
        "max_depth_bucket": Math.floor(Math.random() * 4) + 1,
        "speed_p50": Math.floor(Math.random() * 500) + 100,
        "speed_p95": Math.floor(Math.random() * 1000) + 500,
    };
}

// =====================================================================
// GŁÓWNA PĘTLA
// =====================================================================

async function readTokenStore() {
    return new Promise((resolve, reject) => {
        fs.readFile(TOKEN_STORE_PATH, 'utf8', (err, data) => {
            if (err) return reject(err);
            try {
                resolve(JSON.parse(data));
            } catch (e) {
                reject(e);
            }
        });
    });
}

async function main() {
    console.log("=".repeat(60));
    console.log("Incognia Consume Loop - Hybrid Mode");
    console.log("=".repeat(60));
    console.log(`Token store: ${TOKEN_STORE_PATH}`);
    console.log(`Consume interval: ${CONSUME_INTERVAL_MS}ms`);
    console.log("Waiting for first tokens from Refresher...\n");

    let encryptor = null;
    let dispatcher = null;
    let currentSdkInstanceId = null;
    let currentConsumeUrl = null;
    let dispatchCount = 0;
    let snapshotSent = false;

    // Główna pętla
    while (true) {
        try {
            // 1. Czytaj token store
            const store = await readTokenStore();
            
            if (!store.tokens) {
                console.log("⏳ No tokens yet, waiting...");
                await sleep(2000);
                continue;
            }

            const tokens = store.tokens;
            const age = Math.floor((Date.now() / 1000) - tokens.timestamp);
            
            // Sprawdź czy tokeny się zmieniły
            if (tokens.sdkInstanceId !== currentSdkInstanceId || 
                tokens.consumeUrl !== currentConsumeUrl) {
                
                console.log(`\n🔄 Tokens updated (age: ${age}s, refresh #${store.refresh_count})`);
                console.log(`  sdkInstanceId: ${tokens.sdkInstanceId}`);
                console.log(`  consumeUrl: ${tokens.consumeUrl}`);
                
                currentSdkInstanceId = tokens.sdkInstanceId;
                currentConsumeUrl = tokens.consumeUrl;
                
                // Zbuduj nowy encryptor i dispatcher
                encryptor = await buildEncryptor(currentSdkInstanceId);
                dispatcher = new Dispatcher({
                    consumeUrl: currentConsumeUrl,
                    encrypt: encryptor,
                    dispatchRetries: DISPATCH_RETRIES,
                    retryBaseDelayMs: RETRY_BASE_DELAY_MS,
                    onError: (err) => console.error("❌ Dispatch error:", err),
                });
                
                // Wyślij snapshot phase (pls) raz po zmianie tokenów
                snapshotSent = false;
            }

            if (!encryptor || !dispatcher) {
                console.log("⏳ Waiting for encryptor/dispatcher init...");
                await sleep(2000);
                continue;
            }

            // 2. Snapshot phase (tylko raz po zmianie tokenów)
            if (!snapshotSent) {
                console.log("\n📸 Sending snapshot (pls)...");
                const snapshotPayload = {
                    type: "pls",
                    sdkInstanceId: currentSdkInstanceId,
                    timestamp: Date.now(),
                    totalTimingMs: 0,
                    signals: buildSnapshotSignals(),
                };
                
                const ok = await dispatcher.dispatch({
                    payload: snapshotPayload,
                    stage: "init"
                });
                
                if (ok) {
                    console.log("✅ Snapshot sent successfully");
                    snapshotSent = true;
                } else {
                    console.log("❌ Snapshot failed");
                }
            }

            // 3. Interaction phase (co 5 sekund)
            const trigger = Math.floor(Math.random() * 3); // 0=normal, 1=buffer, 2=hidden
            const interactionPayload = {
                type: "it",
                sdkInstanceId: currentSdkInstanceId,
                timestamp: Date.now(),
                trigger,
                totalTimingMs: 0,
                signals: generateFakeInteractionSignals(trigger),
            };

            console.log(`\n📡 Dispatching interaction (trigger=${trigger}, #${++dispatchCount})...`);
            const ok = await dispatcher.dispatch({
                payload: interactionPayload,
                stage: "runtime"
            });

            if (ok) {
                console.log("✅ Interaction dispatched");
            } else {
                console.log("❌ Interaction failed");
            }

        } catch (e) {
            console.error("❌ Loop error:", e.message);
        }

        // Czekaj do następnego cyklu
        await sleep(CONSUME_INTERVAL_MS);
    }
}

// Uruchom
main().catch(e => {
    console.error("Fatal error:", e);
    process.exit(1);
});