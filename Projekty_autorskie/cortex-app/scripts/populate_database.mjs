import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { scanKosmosProjectHierarchy } from '../src/main/kosmos/KosmosScanner.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, '..');
const parentDir = path.resolve(appRoot, '..');

const targets = [
  path.join(appRoot, 'baza_wiedzy_kosmos'),
  appRoot,
  path.join(parentDir, 'useme_core'),
  path.join(parentDir, 'łowca'),
];

console.log('[KOSMOS POPULATE] Skanowanie wybranych folderów...');

const projects = [];

for (const target of targets) {
  if (fs.existsSync(target)) {
    console.log(` -> Skanowanie: ${target}`);
    const record = scanKosmosProjectHierarchy(target);
    if (record) {
      console.log(`    ✓ Zindeksowano: ${record.name} (${record.stats.totalFolders} folderów, ${record.stats.totalFiles} plików, ${record.stats.totalBytes} bajtów)`);
      projects.push(record);
    }
  } else {
    console.log(` -> Pominięto (nie istnieje): ${target}`);
  }
}

const dbDir = path.join(appRoot, 'data', 'projekty');
const dbPath = path.join(dbDir, 'kosmos_db.json');

fs.mkdirSync(dbDir, { recursive: true });
fs.writeFileSync(dbPath, JSON.stringify(projects, null, 2), 'utf-8');

console.log(`\n[KOSMOS POPULATE] Pomyślnie zapisano ${projects.length} projektów do bazy danych:`);
console.log(`Plik bazy: ${dbPath}`);
console.log(`Rozmiar bazy: ${fs.statSync(dbPath).size} bajtów`);
