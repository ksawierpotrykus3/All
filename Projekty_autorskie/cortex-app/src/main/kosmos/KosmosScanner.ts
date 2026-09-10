// ============================================================================
// KOSMOS — Generyczny skaner plików + parser importów
// Buduje graf z PRAWDZIWĄ hierarchią folderów:
//   węzeł = folder LUB plik, krawędź 'contains' = folder zawiera plik/podfolder.
// Pliki są przyklejone do swojego folderu — nie mogą dryfować między folderami.
// Krawędź 'import' = realny import kodu (tylko między plikami).
// Lista folderów pochodzi z zewnątrz (żadnego hardcodowania cortex/łowca).
// ============================================================================

import * as fs from 'fs';
import * as path from 'path';
import type {
  KosmosGraph,
  KosmosNode,
  KosmosEdge,
  KosmosFileRecord,
  KosmosFolderRecord,
  KosmosProjectRecord,
} from '../../shared/types/kosmos';

const TEXT_EXTS = new Set([
  '.md', '.txt', '.ts', '.tsx', '.js', '.jsx', '.py', '.json',
  '.css', '.html', '.yml', '.yaml', '.xml', '.csv', '.bat', '.ps1',
]);

const CODE_EXTS = new Set(['.ts', '.tsx', '.js', '.jsx', '.py']);

const SKIP_DIRS = new Set(['node_modules', 'out', 'dist', 'release', '.git', '__pycache__', 'ffmpeg', 'data', '.venv', 'venv']);

const MAX_FILE_BYTES = 2 * 1024 * 1024;

// Dopasowuje: import 'x'; from 'x'; import(...); require('x')
const IMPORT_RE = /(?:from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))/g;

// Adres proxy DeepSeek — jedyne źródło prawdy do wykrywania, który projekt używa AI.
export const AI_PROXY_HOST = 'http://localhost:4570';

/**
 * Sprawdza, czy projekt faktycznie korzysta z proxy AI.
 * Skanuje pełną treść plików tekstowych (nie tylko podgląd), szukając adresu
 * localhost:4570. Zwraca true tylko wtedy, gdy realnie występuje w kodzie.
 */
export function projectUsesAi(rootFolder: string): boolean {
  if (!fs.existsSync(rootFolder)) return false;
  const absRoot = path.resolve(rootFolder);
  const { files } = collectTree(absRoot);
  for (const fp of files) {
    try {
      const text = fs.readFileSync(fp, 'utf-8');
      if (
        text.includes('localhost:4570') || text.includes('127.0.0.1:4570') ||
        text.includes('localhost:4571') || text.includes('127.0.0.1:4571')
      ) {
        return true;
      }
    } catch {
      /* ignoruj błędy odczytu */
    }
  }
  return false;
}

function toType(ext: string): KosmosNode['type'] {
  if (CODE_EXTS.has(ext)) return 'kod';
  if (ext === '.md') return 'markdown';
  if (ext === '.json') return 'json';
  if (ext === '.txt') return 'txt';
  return 'inny';
}

function extractImports(text: string): string[] {
  const out: string[] = [];
  let m: RegExpExecArray | null;
  IMPORT_RE.lastIndex = 0;
  while ((m = IMPORT_RE.exec(text)) !== null) {
    const v = m[1] || m[2] || m[3];
    if (v) out.push(v);
  }
  return out;
}

interface WalkResult {
  dirs: string[];
  files: string[];
}

/**
 * Rekurencyjnie zbiera podfoldery (do utworzenia węzłów folderów)
 * oraz pliki tekstowe (do utworzenia węzłów plików). Pomija SKIP_DIRS.
 */
function collectTree(root: string): WalkResult {
  const dirs: string[] = [];
  const files: string[] = [];

  const walk = (dir: string) => {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (e.isDirectory()) {
        if (SKIP_DIRS.has(e.name)) continue;
        const full = path.join(dir, e.name);
        dirs.push(full);
        walk(full);
      } else if (e.isFile()) {
        const ext = path.extname(e.name).toLowerCase();
        if (!TEXT_EXTS.has(ext)) continue;
        const fp = path.join(dir, e.name);
        try {
          if (fs.statSync(fp).size > MAX_FILE_BYTES) continue;
        } catch {
          continue;
        }
        files.push(fp);
      }
    }
  };

  walk(root);
  return { dirs, files };
}

/**
 * Skanuje podane foldery i buduje graf z węzłami folderów oraz plików.
 * @param folders lista bezwzględnych ścieżek folderów (źródeł)
 */
export function scanKosmos(folders: string[]): KosmosGraph {
  const nodes: KosmosNode[] = [];
  const edges: KosmosEdge[] = [];
  const sources: string[] = [];
  const pathToId = new Map<string, number>();        // ścieżka (normalizowana) -> id węzła (folder LUB plik)
  const importsByPath = new Map<string, string[]>();

  const norm = (p: string) => p.replace(/\\/g, '/').toLowerCase();

  for (const folder of folders) {
    if (!fs.existsSync(folder)) continue;
    const abs = path.resolve(folder);
    sources.push(abs);

    const { dirs, files } = collectTree(abs);

    // 1. Węzeł folderu źródłowego (root)
    const rootId = nodes.length;
    nodes.push({
      id: rootId,
      name: path.basename(abs),
      path: abs,
      kind: 'folder',
      type: 'inny',
      folder: path.basename(path.dirname(abs)) || abs,
      source: path.basename(abs),
      group: path.basename(abs),
    });
    pathToId.set(norm(abs), rootId);

    // 2. Węzły podfolderów
    for (const d of dirs) {
      const id = nodes.length;
      nodes.push({
        id,
        name: path.basename(d),
        path: d,
        kind: 'folder',
        type: 'inny',
        folder: path.basename(path.dirname(d)),
        source: path.basename(abs),
        group: path.basename(abs),
      });
      pathToId.set(norm(d), id);
    }

    // 3. Węzły plików
    for (const fp of files) {
      const ext = path.extname(fp).toLowerCase();
      const id = nodes.length;

      let preview = '';
      try {
        const text = fs.readFileSync(fp, 'utf-8');
        preview = text.slice(0, 350).replace(/\r/g, '').replace(/\n\s*\n+/g, '\n').trim();
        if (CODE_EXTS.has(ext)) {
          importsByPath.set(fp, extractImports(text));
        }
      } catch {
        /* ignoruj błędy odczytu */
      }

      const relToSource = path.relative(abs, fp).replace(/\\/g, '/');
      const topDir = relToSource.includes('/') ? relToSource.split('/')[0] : '';
      const group = topDir ? `${path.basename(abs)}/${topDir}` : path.basename(abs);

      nodes.push({
        id,
        name: path.basename(fp),
        path: fp,
        kind: 'file',
        type: toType(ext),
        folder: path.basename(path.dirname(fp)),
        source: path.basename(abs),
        preview,
        group,
      });
      pathToId.set(norm(fp), id);
    }

    // 4. Krawędzie zawierania (contains): folder -> podfolder i folder -> plik
    //    Pliki są przyklejone do swojego bezpośredniego folderu.
    for (const d of dirs) {
      const childId = pathToId.get(norm(d));
      const parentDir = path.dirname(d);
      const parentId = pathToId.get(norm(parentDir));
      if (childId !== undefined && parentId !== undefined) {
        edges.push({ source: parentId, target: childId, kind: 'contains' });
      }
    }
    for (const fp of files) {
      const childId = pathToId.get(norm(fp));
      const parentDir = path.dirname(fp);
      const parentId = pathToId.get(norm(parentDir));
      if (childId !== undefined && parentId !== undefined) {
        edges.push({ source: parentId, target: childId, kind: 'contains' });
      }
    }
  }

  // 5. Krawędzie: realne importy kodu (tylko między plikami)
  for (const [fp, imps] of importsByPath) {
    const srcId = pathToId.get(norm(fp));
    if (srcId === undefined) continue;
    const base = path.dirname(fp);
    for (const imp of imps) {
      if (!imp.startsWith('.')) continue; // tylko relatywne importy
      const targetBase = path.normalize(path.join(base, imp));
      let foundId: number | undefined;
      for (const ext of ['', '.ts', '.tsx', '.js', '.jsx', '.py', '.json', '.md']) {
        const cand = norm(targetBase + ext);
        if (pathToId.has(cand)) {
          foundId = pathToId.get(cand);
          break;
        }
      }
      if (foundId !== undefined && foundId !== srcId) {
        edges.push({ source: srcId, target: foundId, kind: 'import' });
      }
    }
  }

  return { nodes, edges, sources };
}

/**
 * Deterministycznie skanuje pojedynczy projekt i buduje rekord bazy danych
 * z pełną hierarchią folderów i listą wszystkich plików.
 */
export function scanKosmosProjectHierarchy(rootFolder: string): KosmosProjectRecord | null {
  if (!fs.existsSync(rootFolder)) return null;
  const absRoot = path.resolve(rootFolder);
  const rootStat = fs.statSync(absRoot);
  if (!rootStat.isDirectory()) return null;

  const { dirs, files: filePaths } = collectTree(absRoot);

  const folderMap = new Map<string, KosmosFolderRecord>();
  const fileRecords: KosmosFileRecord[] = [];

  // Root folder
  folderMap.set(absRoot, {
    path: absRoot,
    relativePath: '',
    name: path.basename(absRoot),
    parentPath: path.dirname(absRoot),
    fileCount: 0,
    depth: 0,
  });

  // Subfolders
  for (const d of dirs) {
    const rel = path.relative(absRoot, d).replace(/\\/g, '/');
    const depth = rel.split('/').length;
    folderMap.set(d, {
      path: d,
      relativePath: rel,
      name: path.basename(d),
      parentPath: path.dirname(d),
      fileCount: 0,
      depth,
    });
  }

  let totalBytes = 0;

  // Files
  for (const fp of filePaths) {
    let size = 0;
    let updatedAt = new Date().toISOString();
    try {
      const st = fs.statSync(fp);
      size = st.size;
      updatedAt = st.mtime.toISOString();
    } catch {
      /* ignoruj błędy stat */
    }

    totalBytes += size;
    const ext = path.extname(fp).toLowerCase();
    const parentDir = path.dirname(fp);
    const relFile = path.relative(absRoot, fp).replace(/\\/g, '/');
    const relFolder = path.relative(absRoot, parentDir).replace(/\\/g, '/');

    // Podgląd początku pliku
    let preview = '';
    try {
      const text = fs.readFileSync(fp, 'utf-8');
      preview = text.slice(0, 500).replace(/\r/g, '').replace(/\n\s*\n+/g, '\n').trim();
    } catch {
      /* ignoruj błędy odczytu */
    }

    // Zwiększ licznik w folderze
    const folderRec = folderMap.get(parentDir);
    if (folderRec) {
      folderRec.fileCount += 1;
    }

    fileRecords.push({
      id: relFile,
      name: path.basename(fp),
      path: fp,
      relativePath: relFile,
      folderPath: parentDir,
      folderRelative: relFolder,
      extension: ext,
      type: toType(ext),
      sizeBytes: size,
      preview,
      updatedAt,
    });
  }

  const sortedFolders = Array.from(folderMap.values()).sort((a, b) => {
    if (a.depth !== b.depth) return a.depth - b.depth;
    return a.relativePath.localeCompare(b.relativePath);
  });

  const sortedFiles = fileRecords.sort((a, b) => a.relativePath.localeCompare(b.relativePath));

  return {
    id: path.basename(absRoot).toLowerCase().replace(/[^a-z0-9_-]/g, '_'),
    name: path.basename(absRoot),
    rootPath: absRoot,
    scannedAt: new Date().toISOString(),
    folders: sortedFolders,
    files: sortedFiles,
    stats: {
      totalFiles: sortedFiles.length,
      totalFolders: sortedFolders.length,
      totalBytes,
    },
  };
}

/**
 * Skanuje listę folderów i zwraca rekordy bazy danych dla każdego projektu.
 */
export function scanAllProjectHierarchies(folders: string[]): KosmosProjectRecord[] {
  const result: KosmosProjectRecord[] = [];
  for (const f of folders) {
    const proj = scanKosmosProjectHierarchy(f);
    if (proj) result.push(proj);
  }
  return result;
}