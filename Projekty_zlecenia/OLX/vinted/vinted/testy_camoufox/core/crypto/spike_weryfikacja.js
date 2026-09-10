// spike_weryfikacja.js
// Weryfikacja faktów UDOWODNIONYCH z dokumentacji (sekcja 15.1)

const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
let passed = 0;
let failed = 0;

function check(label, ok, detail) {
  if (ok) {
    console.log(`  [PASS] ${label}` + (detail ? '  ' + detail : ''));
    passed++;
  } else {
    console.log(`  [FAIL] ${label}` + (detail ? '  ' + detail : ''));
    failed++;
  }
}

console.log('=== WERYFIKACJA FAKTÓW UDOWODNIONYCH Z SEKCJI 15.1 ===\n');

// ===== FAKT 7: SDK Incognia 85 KB =====
const origPath = 'C:\\temp\\vinted_scripts_v2\\k7v3q2.vinted.com_85d7e768568e.js.js';
let origSize = 0;
try {
  origSize = fs.statSync(origPath).size;
  check('F7: SDK oryginał istnieje', true, `${origSize} B (dokumentacja: 85 044)`);
  check('F7: rozmiar = 85044', origSize === 85044);
} catch (e) {
  check('F7: SDK oryginał istnieje', false, e.message);
}

// ===== FAKT 18: DEOBFUSCATED 91 929 B =====
const deobfPath = path.join(ROOT, 'k7v3q2_DEOBFUSCATED.js');
let deobfSize = 0;
let deobf = '';
try {
  deobf = fs.readFileSync(deobfPath, 'utf8');
  deobfSize = Buffer.byteLength(deobf, 'utf8');
  check('F18: DEOBFUSCATED istnieje', true, `${deobfSize} B (dokumentacja: 91 929)`);
  check('F18: rozmiar = 91929', deobfSize === 91929);
} catch (e) {
  check('F18: DEOBFUSCATED istnieje', false, e.message);
}

// ===== FAKT 22-23: 1777 stringów + rotacja 447 =====
const arrMatch = deobf.match(/var e=`([^`]+)`\.split\(`\.`\)/);
if (arrMatch) {
  const arr = arrMatch[1].split('.');
  check('F22: tablica stringów odczytana', true, `${arr.length} elementów (dokumentacja: 1777)`);
  check('F22: liczba stringów = 1777', arr.length === 1777);

  // Znajdź rotację (suma parseInt === 901385)
  const ROT_INDICES = [1680, 1428, 934, 1261, 269, 1813, 1895, 151, 481, 1653];
  let rotated = [...arr];
  let rotSteps = 0;
  let found = false;
  for (let i = 0; i < 5000; i++) {
    let sum = 0;
    for (const idx of ROT_INDICES) sum += parseInt(rotated[idx]);
    if (sum === 901385) { found = true; rotSteps = i; break; }
    rotated.push(rotated.shift());
  }
  check('F23: rotacja znaleziona', found, `kroki=${rotSteps} (dokumentacja: 447)`);
  check('F23: rotacja = 447 kroków', rotSteps === 447);
}

// ===== FAKT 9: HKDF_SALT =====
const beautifiedPath = path.join(ROOT, 'k7v3q2_BEAUTIFIED.js');
let beautified = '';
try {
  beautified = fs.readFileSync(beautifiedPath, 'utf8');
  check('F9: BEAUTIFIED istnieje', true, `${beautified.length} B (dokumentacja: 113 397)`);

  // Szukamy soli HKDF w pliku
  const saltInFile = beautified.includes('L6ZhSbP9TciQDgxC7pjukGhl4vYis56m');
  check('F9: HKDF_SALT w pliku', saltInFile, `"L6ZhSbP9TciQDgxC7pjukGhl4vYis56m"`);
} catch (e) {
  check('F9: BEAUTIFIED istnieje', false, e.message);
}

// ===== FAKT 19-21: reference implementation =====
const refFiles = [
  'incognia_krypto_reference.js',
  'incognia_transport_reference.js',
  'incognia_sdk_reference.js',
];
for (const f of refFiles) {
  const p = path.join(ROOT, f);
  const exists = fs.existsSync(p);
  if (exists) {
    const stat = fs.statSync(p);
    check(`F19-21: ${f}`, true, `${stat.size} B`);
  } else {
    check(`F19-21: ${f}`, false, 'nie istnieje');
  }
}

// ===== FAKT 22: strings_map.json =====
const mapPath = path.join(ROOT, 'incognia_strings_map.json');
if (fs.existsSync(mapPath)) {
  const map = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
  const keys = Object.keys(map);
  check('F22: strings_map.json', true, `${keys.length} stringów`);
  check('F22: liczba stringów = 1777', keys.length === 1777);
}

// ===== Smoke test F6a.4 =====
console.log('\n--- Smoke test reference implementation ---');
try {
  const krypto = require(path.join(ROOT, 'incognia_krypto_reference.js'));
  check('F19: HKDF_SALT poprawny', krypto.HKDF_SALT.length === 32);
  check('F19: HKDF_SALT tekst', new TextDecoder().decode(krypto.HKDF_SALT) === 'L6ZhSbP9TciQDgxC7pjukGhl4vYis56m');
  check('F19: DEFAULT_CONFIG.flushIntervalMs = 5000', krypto.DEFAULT_CONFIG.flushIntervalMs === 5000);
  check('F19: DEFAULT_CONFIG.bufferLimit = 50', krypto.DEFAULT_CONFIG.bufferLimit === 50);
  check('F19: DEFAULT_CONFIG.dispatchRetries = 3', krypto.DEFAULT_CONFIG.dispatchRetries === 3);
  check('F19: DEFAULT_CONFIG.retryBaseDelayMs = 500', krypto.DEFAULT_CONFIG.retryBaseDelayMs === 500);

  // Bytes to base64 roundtrip
  const data = new TextEncoder().encode('test-payload-1234');
  const b64 = krypto.bytesToBase64(data);
  const decoded = Buffer.from(b64, 'base64');
  check('F19: bytesToBase64 roundtrip', decoded.toString() === 'test-payload-1234');
} catch (e) {
  check('F19: smoke krypto', false, e.message);
}

try {
  const sdk = require(path.join(ROOT, 'incognia_sdk_reference.js'));
  check('F21: CONSUME_SUFFIX = /v1/consume', sdk.CONSUME_SUFFIX === '/v1/consume');
  check('F21: IncogniaSdk jest klasą', typeof sdk.IncogniaSdk === 'function');
  check('F21: initSdk jest funkcją', typeof sdk.initSdk === 'function');
} catch (e) {
  check('F21: smoke sdk', false, e.message);
}

console.log(`\n=== WYNIK: ${passed} PASS / ${failed} FAIL ===`);
process.exit(failed > 0 ? 1 : 0);
