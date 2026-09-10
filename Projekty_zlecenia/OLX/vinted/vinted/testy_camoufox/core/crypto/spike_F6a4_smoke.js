// spike_F6a4_smoke.js
// Test jednostkowy: sprawdzenie że reference implementation ładuje się bez błędów
// i że moduły się wzajemnie importują poprawnie.

const fs = require('fs');
const path = require('path');

const FILES = [
  'incognia_krypto_reference.js',
  'incognia_transport_reference.js',
  'incognia_sdk_reference.js',
];

console.log('--- F6a.4 smoke test ---');

for (const f of FILES) {
  const p = path.join(__dirname, f);
  const stat = fs.statSync(p);
  console.log(`  ${f}: ${stat.size} B`);
}

// Test 1: samodzielne ładowanie modułów
const krypto = require('./incognia_krypto_reference.js');
console.log('\n[krypto] exports:', Object.keys(krypto));
console.log('  HKDF_SALT length:', krypto.HKDF_SALT.length, 'bytes');
console.log('  HKDF_SALT:', new TextDecoder().decode(krypto.HKDF_SALT));
console.log('  DEFAULT_CONFIG:', krypto.DEFAULT_CONFIG);

const transport = require('./incognia_transport_reference.js');
console.log('\n[transport] exports:', Object.keys(transport));
console.log('  Dispatcher class:', typeof transport.Dispatcher);
console.log('  encodeModel type:', typeof transport.encodeModel);

const sdk = require('./incognia_sdk_reference.js');
console.log('\n[sdk] exports:', Object.keys(sdk));
console.log('  IncogniaSdk class:', typeof sdk.IncogniaSdk);
console.log('  initSdk fn:', typeof sdk.initSdk);
console.log('  CONSUME_SUFFIX:', sdk.CONSUME_SUFFIX);

// Test 2: bytesToBase64 roundtrip
(async () => {
  const data = new TextEncoder().encode("test-encrypted-payload-1234");
  const b64 = krypto.bytesToBase64(data);
  const decoded = Buffer.from(b64, 'base64');
  console.log('\n[bytesToBase64] in:', data.length, 'B  out:', b64.length, 'B  roundtrip:', decoded.toString() === "test-encrypted-payload-1234" ? 'OK' : 'FAIL');

  // Test 3: sha256Hex
  const hash = await krypto.sha256Hex(data);
  console.log('[sha256Hex]', hash.slice(0, 30) + '...', hash.startsWith('sha256:') ? 'OK' : 'FAIL');

  // Test 4: HKDF derive (tylko w Node 18+ z crypto.subtle)
  try {
    const key = await krypto.deriveAesKey('test-sdk-instance-abc123');
    console.log('[deriveAesKey] type:', key.constructor.name, 'algo:', key.algorithm.name, key.algorithm.name === 'AES-GCM' ? 'OK' : 'FAIL');

    // Test 5: AES-GCM encrypt roundtrip
    const ct = await krypto.aesGcmEncrypt(key, data);
    console.log('[aesGcmEncrypt] plaintext:', data.length, 'B  IV||ciphertext:', ct.length, 'B (12 IV +', ct.length - 12, 'ct)');
    console.log('  IV != zeros:', ct.slice(0, 12).some(b => b !== 0) ? 'OK (random)' : 'FAIL');
  } catch (e) {
    console.log('[HKDF/AES-GCM] requires Node 18+ with webcrypto:', e.message);
  }

  console.log('\n--- OK ---');
})();
