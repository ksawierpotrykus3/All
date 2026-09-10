// F6a.4: Wyciągnij z deobfuskowanego pliku kluczowe sekcje
const fs = require('fs');

const SRC = fs.readFileSync('f:/PROJEKTY/vinted/vinted/testy_camoufox/k7v3q2_DEOBFUSCATED.js', 'utf-8');
console.log(`[LOAD] ${SRC.length} znaków\n`);

// === 1. Znajdź Ec (config domyślny) ===
const ecMatch = SRC.match(/var Ec=([^;]+);/);
if (ecMatch) {
  console.log('[Ec - domyślny config]');
  console.log(ecMatch[1]);
  console.log();
}

// === 2. Znajdź Dc (salt HKDF) ===
const dcMatch = SRC.match(/Dc=new TextEncoder\(\)\["encode"\]\("([^"]+)"\)/);
if (dcMatch) {
  console.log(`[Dc - HKDF salt string]`);
  console.log(`  "${dcMatch[1]}" (${dcMatch[1].length} znaków)`);
  console.log();
}

// === 3. Znajdź Gc (sufiks URL consume) ===
const gcMatch = SRC.match(/var Gc=([^;]+);/);
if (gcMatch) {
  console.log('[Gc - URL sufiks]');
  console.log(`  ${gcMatch[1]}`);
  console.log();
}

// === 4. Znajdź klasę Oc (HKDF derive) ===
const ocMatch = SRC.match(/Oc=async[^=]+=>\{([^}]+(?:\{[^}]*\}[^}]*)*)\}/);
if (ocMatch) {
  console.log('[Oc - HKDF]');
  console.log(ocMatch[0].substring(0, 600));
  console.log();
}

// === 5. Znajdź klasę Ac (AES encrypt) ===
const acMatch = SRC.match(/Ac=async\([^)]+\)=>\{([^}]+(?:\{[^}]*\}[^}]*)*)\}/);
if (acMatch) {
  console.log('[Ac - AES encrypt]');
  console.log(acMatch[0].substring(0, 600));
  console.log();
}

// === 6. Znajdź główne kolektory ===
const wcMatch = SRC.match(/var wc=\(\)=>\[([^\]]+)\]/);
if (wcMatch) {
  console.log('[wc - snapshot collectors]');
  console.log(wcMatch[1]);
  console.log();
}

const tcMatch = SRC.match(/var Tc=\(\)=>\[([^\]]+)\]/);
if (tcMatch) {
  console.log('[Tc - interaction collectors]');
  console.log(tcMatch[1]);
  console.log();
}

// === 7. Znajdź Kc (główna funkcja init) ===
const kcMatch = SRC.match(/Kc=async e=>\{([^}]+(?:\{[^}]*\}[^}]*)*?)\};return t\["initSdk"\]/);
if (kcMatch) {
  console.log('[Kc - main initSdk function]');
  console.log(kcMatch[0].substring(0, 1000));
  console.log();
}

// === 8. Znajdź init wywołanie ===
console.log('[initSdk - setup]');
const setupMatch = SRC.match(/i=new Uc\(\{([^}]+)\}\)/);
if (setupMatch) console.log(setupMatch[1].substring(0, 500));

// === 9. Kolektory snapshot - szczegółowe funkcje ===
console.log('\n[Kolektory - przegląd zmiennych]');
const collectorFns = ['da', 'Gs', 'sa', 'fa', 'ra', 'Bs', 'Ki', 'ha', 'Ys', 'nc', 'zs', 'Cc', 'Hr', 'Rs', 'Ws', 'ma', 'pa'];
for (const fn of collectorFns) {
  const re = new RegExp(`var ${fn}=[^;]+;`);
  const m = SRC.match(re);
  if (m) {
    console.log(`  ${fn}: ${m[0].substring(0, 200)}`);
  }
}

// === 10. Interakcje - kolektory ===
console.log('\n[Interakcje]');
for (const fn of ['ar', 'Cr', '_r', 'lr', 'Or', 'er', 'or']) {
  const re = new RegExp(`var ${fn}=\\(\\)=>`, );
  const m = SRC.match(re);
  console.log(`  ${fn}: ${m ? 'OK' : 'nie znaleziono'}`);
}
