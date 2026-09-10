/**
 * spike_F8_replay_test.js — Faza 8: test walidacji siid przez serwer Incognia.
 *
 * Cel: sprawdzić, czy endpoint POST /j3r4zw/v1/consume akceptuje
 * syntetyczny sdkInstanceId (bez wcześniejszej rejestracji przez /j3r4zw/v1/config),
 * czy serwer odrzuca żądanie (4xx).
 *
 * To jest czysto naukowy test anonimowego endpointu telemetrii anti-fraud:
 * bez logowania, bez zakupu, bez rezerwacji.
 *
 * Kryptografia (z incognia_krypto_reference.js / dokumentacja sekcja 14.5):
 *   - HKDF-SHA256(salt="L6ZhSbP9TciQDgxC7pjukGhl4vYis56m", ikm=sdkInstanceId) -> AES-256-GCM key
 *   - AES-GCM: 12B losowy IV, ciphertext, output = IV | ciphertext, base64
 *   - model: { v:1, type:"pls", siid, ts, t, s }
 *
 * Uruchomienie: node spike_F8_replay_test.js
 */
const https = require('https');
const path = require('path');
const fs = require('fs');

const CONFIG_URL = 'https://api.vinted.pl/j3r4zw/v1/config';
const CONSUME_URL = 'https://api.vinted.pl/j3r4zw/v1/consume';
const HKDF_SALT = new TextEncoder().encode('L6ZhSbP9TciQDgxC7pjukGhl4vYis56m');

// ===== WebCrypto: HKDF + AES-GCM (identyczne jak w SDK) =====

function bytesToBase64(bytes) {
    return Buffer.from(bytes).toString('base64');
}

async function buildEncryptor(sdkInstanceId) {
    const ikm = new TextEncoder().encode(sdkInstanceId);
    const baseKey = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey(
        { name: 'HKDF', salt: HKDF_SALT, info: new Uint8Array(0), hash: 'SHA-256' },
        baseKey,
        { name: 'AES-GCM', length: 256 },
        true,
        ['encrypt']
    );
    return async (plaintext) => {
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext);
        const out = new Uint8Array(iv.length + ct.byteLength);
        out.set(iv, 0);
        out.set(new Uint8Array(ct), iv.length);
        return out;
    };
}

// ===== HTTP helpers =====

function httpGet(url) {
    return new Promise((resolve) => {
        https.get(url, { headers: { 'accept': 'application/json' } }, (res) => {
            let data = '';
            res.on('data', (c) => (data += c));
            res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: data }));
        }).on('error', (e) => resolve({ status: 0, error: e.message }));
    });
}

function httpPost(url, body) {
    return new Promise((resolve) => {
        const u = new URL(url);
        const options = {
            hostname: u.hostname,
            path: u.pathname + u.search,
            method: 'POST',
            headers: {
                'content-type': 'application/json',
                'content-length': Buffer.byteLength(body),
                'origin': 'https://www.vinted.pl',
                'referer': 'https://www.vinted.pl/items/9807925466-genesis-krypton-700',
            },
        };
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (c) => (data += c));
            res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: data }));
        });
        req.on('error', (e) => resolve({ status: 0, error: e.message }));
        req.write(body);
        req.end();
    });
}

// ===== Główny test =====

async function main() {
    const results = {};

    // 1. GET /config — sprawdź czy endpoint jest dostępny anonimowo i czy zwraca siid
    const cfg = await httpGet(CONFIG_URL);
    results.config = { status: cfg.status, body: cfg.body.slice(0, 500) };
    console.log(`[1] GET /config -> ${cfg.status}`);

    let sdkInstanceId = null;
    try {
        const cfgJson = JSON.parse(cfg.body);
        // Klucz to snake_case: sdk_instance_id (zweryfikowane z body configa)
        sdkInstanceId = cfgJson.sdk_instance_id ?? cfgJson.sdkInstanceId ?? cfgJson.siid ?? null;
    } catch (e) {
        // body nie jest JSON — zostaje null
    }

    // 2. Test syntetyczny siid (bez /config) — kluczowy test Fazy 8
    const syntheticId = crypto.randomUUID();
    console.log(`[2] Syntetyczny siid: ${syntheticId}`);

    const encryptor = await buildEncryptor(syntheticId);
    // Minimalny payload sygnałów — pusty obiekt, sprawdzamy tylko akceptację siid
    const plaintext = new TextEncoder().encode('{}');
    const cipherBytes = await encryptor(plaintext);
    const model = {
        v: 1,
        type: 'pls',
        siid: syntheticId,
        ts: Date.now(),
        t: 0,
        s: bytesToBase64(cipherBytes),
    };
    const consume = await httpPost(CONSUME_URL, JSON.stringify(model));
    results.consume_synthetic = { status: consume.status, body: consume.body.slice(0, 500) };
    console.log(`[3] POST /consume (synthetic siid) -> ${consume.status}`);
    if (consume.status === 0) console.log(`    error: ${consume.error}`);

    // 3. Jeśli /config zwrócił realny siid, przetestuj też z nim (baseline)
    if (sdkInstanceId) {
        console.log(`[4] Realny siid z /config: ${sdkInstanceId}`);
        const encryptor2 = await buildEncryptor(sdkInstanceId);
        const cipher2 = await encryptor2(new TextEncoder().encode('{}'));
        const model2 = {
            v: 1,
            type: 'pls',
            siid: sdkInstanceId,
            ts: Date.now(),
            t: 0,
            s: bytesToBase64(cipher2),
        };
        const consume2 = await httpPost(CONSUME_URL, JSON.stringify(model2));
        results.consume_config_siid = { status: consume2.status, body: consume2.body.slice(0, 500) };
        console.log(`[5] POST /consume (config siid) -> ${consume2.status}`);
    } else {
        console.log('[4] /config nie zwrócił siid — pomijam test baseline.');
        results.consume_config_siid = { skipped: true };
    }

    // 4. Kontrola negatywna: celowo zepsuty base64 w polu "s"
    // Jeśli serwer zwróci 200 również dla zepsutego payloadu, to 200 jest
    // "fire-and-forget" (bez walidacji po stronie wejścia) i nie dowodzi akceptacji krypto.
    const brokenModel = {
        v: 1,
        type: 'pls',
        siid: crypto.randomUUID(),
        ts: Date.now(),
        t: 0,
        s: '!!not-valid-base64!!',
    };
    const broken = await httpPost(CONSUME_URL, JSON.stringify(brokenModel));
    results.consume_broken_base64 = { status: broken.status, body: broken.body.slice(0, 500) };
    console.log(`[6] POST /consume (broken base64) -> ${broken.status}`);

    // Zapisz wyniki
    const outPath = path.join(__dirname, 'wynik_F8_replay_test.json');
    fs.writeFileSync(outPath, JSON.stringify(results, null, 2), 'utf-8');
    console.log(`\nZapisano wyniki do: ${outPath}`);
}

main().catch((e) => {
    console.error('Fatal error:', e);
    process.exit(1);
});