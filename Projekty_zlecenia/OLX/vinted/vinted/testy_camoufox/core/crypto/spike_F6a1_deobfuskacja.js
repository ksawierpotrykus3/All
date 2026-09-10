// F6a.1 v3: Deobfuskacja z wykonaniem kodu w VM + hook na e()
const fs = require('fs');
const vm = require('vm');

const SRC = fs.readFileSync(
  'C:/temp/vinted_scripts_v2/k7v3q2.vinted.com_85d7e768568e.js.js',
  'utf-8'
);
console.log(`[LOAD] Źródło: ${SRC.length} znaków`);

// Wyekstrahuj tablicę stringów
const arrMatch = SRC.match(/var e=`([^`]+)`\.split\(`\.`\)/);
const arr = arrMatch[1].split('.');
console.log(`[ARR] ${arr.length} elementów`);

// Ustaw VM context z hooked e()
const STRINGS = {};
const ctx = {
  console,
  TextEncoder,
  TextDecoder: class { decode() { return ''; } },
  crypto: require('crypto').webcrypto,
  performance: { now: () => Date.now() },
  Date,
  Object,
  Math,
  Array,
  JSON,
  Uint8Array,
  Uint32Array,
  Int32Array,
  Float32Array,
  Promise,
  Symbol,
  Reflect,
  Map,
  Set,
  WeakMap,
  WeakSet,
  navigator: { userAgent: 'node', language: 'en' },
  document: {
    createElement: () => ({
      getContext: () => ({}),
      toDataURL: () => '',
      style: {},
    }),
    documentElement: {},
  },
  globalThis: {},
  window: {},
  setTimeout, clearTimeout, setInterval, clearInterval,
};
ctx.globalThis = ctx;
ctx.window = ctx;
ctx.self = ctx;

// Intercept funkcji e()
const REAL_E_IHTTCS = SRC.match(/ihTTCs=function\(([^)]+)\)\{for\(var t=`[^`]+`,n=``/);

// Patch SRC: zamień definicję var e=function(n,r){...} żeby hookowała wywołania
// Ale najprościej - wyciągnij definicję funkcji e() i zrób proxy

// Strategia: wykonaj kod w VM z globalną `e` jako funkcją która zwraca arr[idx-127] po rotacji

// Krok 1: znajdź i wykonaj rotację
// W SRC jest: (function(t,n){for(var r=e,i=t();;)try{...sum...===n)break;i.push(i.shift())}catch{...}})(t,901385)
// Wykonaj tę logikę ręcznie - obróć arr aż suma parseInt() === 901385

function makeDecoder(arr) {
  const CUSTOM_ALPHA = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=';
  return function e(n) {
    n -= 127;
    if (n < 0 || n >= arr.length) return undefined;
    const raw = arr[n];
    if (!raw || raw.length === 0) return '';
    // Base64 decode z custom alphabet
    const STANDARD_ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let std = '';
    for (const ch of raw) {
      const idx = CUSTOM_ALPHA.indexOf(ch);
      if (idx === -1) continue;
      if (idx === 64) std += '=';
      else std += STANDARD_ALPHA[idx];
    }
    const bytes = Buffer.from(std, 'base64');
    let pct = '';
    for (let i = 0; i < bytes.length; i++) {
      pct += '%' + ('00' + bytes[i].toString(16)).slice(-2);
    }
    try {
      return decodeURIComponent(pct);
    } catch (err) {
      return '[DECODE_ERR]';
    }
  };
}

const ROT_INDICES = [1680, 1428, 934, 1261, 269, 1813, 1895, 151, 481, 1653];
const TARGET_SUM = 901385;

// Próbuj różne rotacje aż suma się zgodzi
function tryRotation(arr) {
  const dec = makeDecoder(arr);
  let sum = 0;
  for (let k = 0; k < ROT_INDICES.length; k++) {
    const v = dec(ROT_INDICES[k]);
    const p = parseInt(v);
    if (isNaN(p)) return null;
    sum += p * [1, -1, -1, 1, 1, -1, -1, -1, -1, 1][k];
  }
  // Recheck - oryginalny wzór to: -p1/1 + -p2/2 + -p3/3 + p4/4 * (p5/5) + -p6/6 * (-p7/7) + -p8/8 * (-p9/9) + p10/10
  const [a, b, c, d, e5, f, g, h, i9, j] = ROT_INDICES.map(dec);
  const sum2 = -parseInt(a)/1 + -parseInt(b)/2 + -parseInt(c)/3 + parseInt(d)/4 * (parseInt(e5)/5) + -parseInt(f)/6 * (-parseInt(g)/7) + -parseInt(h)/8 * (-parseInt(i9)/9) + parseInt(j)/10;
  return Math.abs(sum2 - TARGET_SUM) < 0.001 ? sum2 : null;
}

console.log('[ROT] Próba obrotu tablicy...');
let found = false;
for (let r = 0; r < arr.length; r++) {
  const result = tryRotation(arr);
  if (result !== null) {
    console.log(`[ROT] ✓ Znaleziono rotację: ${r} (sum = ${result})`);
    found = true;
    break;
  }
  arr.push(arr.shift());
}

if (!found) {
  console.log('[ROT] ✗ Nie znaleziono rotacji, używam oryginalnej tablicy');
}

// Dekoduj wszystkie
const DECODED = arr.map((raw, idx) => makeDecoder(arr)(idx + 127));
const STRINGS_MAP = {};
for (let i = 0; i < DECODED.length; i++) {
  STRINGS_MAP[i + 127] = DECODED[i];
}

console.log(`[DECODE] ${DECODED.length} stringów`);

// Sprawdź kluczowe
const checks = [910, 1877, 814, 1285, 293, 1252, 1834, 1164, 1024, 1491, 983, 670, 1529, 278, 1381, 1308, 613, 1670, 774, 907, 1226, 1018, 358, 1748, 1759, 1756, 1140, 1167, 1163, 1162, 1843, 1784, 1815, 1658, 1680];
console.log('\n[KLUCZOWE STRINGI]');
for (const k of checks) {
  const v = STRINGS_MAP[k];
  console.log(`  e(${k}) = ${v !== undefined ? JSON.stringify(v).slice(0, 80) : 'undefined'}`);
}

// Substytucja tekstowa
const FORBIDDEN_NAMES = new Set(['Math','parseInt','parseFloat','setTimeout','setInterval','Object','Promise','Array','JSON','Date','Number','String','Buffer','Boolean','RegExp','Error','Symbol','Reflect','Proxy','document','window','globalThis','navigator','crypto','fetch','console','Function','TextEncoder','TextDecoder','Uint8Array','Uint32Array','Int32Array','Float32Array','Map','Set','WeakMap','WeakSet']);

const SUB_RE = /\b([a-zA-Z_$])\((\d+)\)/g;
let replaced = 0;
const deobfuscated = SRC.replace(SUB_RE, (match, fn, num) => {
  if (FORBIDDEN_NAMES.has(fn)) return match;
  const idx = parseInt(num);
  if (STRINGS_MAP[idx] !== undefined) {
    const s = STRINGS_MAP[idx];
    replaced++;
    return JSON.stringify(s);
  }
  return match;
});

console.log(`\n[SUBST] ${replaced} substytucji, ${deobfuscated.length} znaków`);

fs.writeFileSync('f:/PROJEKTY/vinted/vinted/testy_camoufox/k7v3q2_DEOBFUSCATED.js', deobfuscated, 'utf-8');
fs.writeFileSync('f:/PROJEKTY/vinted/vinted/testy_camoufox/incognia_strings_map.json', JSON.stringify(STRINGS_MAP, null, 2), 'utf-8');
console.log('[SAVE] OK');
