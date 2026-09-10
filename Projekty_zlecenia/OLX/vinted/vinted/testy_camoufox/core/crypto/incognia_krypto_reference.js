// incognia_krypto_reference.js
// Warstwa kryptograficzna SDK Incognia (85d7e768568e.js — wyekstrahowane z SDK Incognia używanego przez Vinted).
// Plik powstał z deobfuskacji + ręcznej refaktoryzacji z k7v3q2_BEAUTIFIED.js.
// Cały moduł korzysta z natywnego WebCrypto API (crypto.subtle) — działa w Node 18+ i w przeglądarce.

// =====================================================================
// Stałe kryptograficzne
// =====================================================================

// Sól HKDF (32 znaki = 32 bajty). Stała zaszyta w SDK — identyczna dla wszystkich klientów.
const HKDF_SALT = new TextEncoder().encode("L6ZhSbP9TciQDgxC7pjukGhl4vYis56m");

// Domyślna konfiguracja runtime (Ec = $ z SDK)
const DEFAULT_CONFIG = {
  flushIntervalMs: 5_000,   // co ile ms InteractionScheduler robi flush
  bufferLimit: 50,          // max zdarzeń w buforze przed wymuszonym flushem
  dispatchRetries: 3,       // ile razy ponowić dispatch przy błędzie HTTP
  maxDispatchFailures: 3,   // ile kolejnych porażek zanim SDK się zatrzyma
  retryBaseDelayMs: 500,    // bazowy czas opóźnienia retry (mnożony przez 2^n + jitter)
};

// =====================================================================
// Base64 chunked (Fc = Fc z SDK) — bezpieczna dla Uint8Array dużych rozmiarów
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

// =====================================================================
// SHA-256 → hex z prefiksem "sha256:" (jc = jc z SDK)
// =====================================================================

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const arr = new Uint8Array(digest);
  let hex = "";
  for (const b of arr) hex += b.toString(16).padStart(2, "0");
  return "sha256:" + hex;
}

// =====================================================================
// HKDF derive (Oc = Oc z SDK)
// Wejście:  sdkInstanceId (string)
// Wyjście: CryptoKey (AES-GCM, 256-bit) z uprawnieniami encrypt+decrypt
// =====================================================================

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

// =====================================================================
// AES-GCM encrypt (Ac = Ac z SDK)
// IV: 12 losowych bajtów (crypto.getRandomValues)
// Output: Uint8Array(IV || ciphertext)
// =====================================================================

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

// =====================================================================
// Encryptor factory (kc = kc z SDK)
// Zwraca funkcję (Uint8Array) => Promise<Uint8Array>
// =====================================================================

async function buildEncryptor(sdkInstanceId) {
  const key = await deriveAesKey(sdkInstanceId);
  return (plaintext) => aesGcmEncrypt(key, plaintext);
}

module.exports = {
  HKDF_SALT,
  DEFAULT_CONFIG,
  bytesToBase64,
  sha256Hex,
  deriveAesKey,
  aesGcmEncrypt,
  buildEncryptor,
};
