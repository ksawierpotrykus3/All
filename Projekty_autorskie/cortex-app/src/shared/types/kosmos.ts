// ============================================================================
// KOSMOS — typy grafu wiedzy (węzły = foldery LUB pliki, krawędzie = zawieranie/importy)
// Hierarchia folderów jest realna: węzeł folderu "zawiera" pliki i podfoldery.
// ============================================================================

export interface KosmosNode {
  /** indeks węzła w grafie (0-based, spójny z positions/colors/sizes) */
  id: number;
  /** nazwa pliku lub folderu (etykieta) */
  name: string;
  /** bezwzględna ścieżka (dla folderów — ścieżka katalogu bez separatora końcowego) */
  path: string;
  /** co reprezentuje węzeł */
  kind: 'folder' | 'file';
  /** typ pliku (tylko dla plików; dla folderów 'inny') */
  type: 'kod' | 'markdown' | 'json' | 'txt' | 'inny';
  /** nazwa folderu nadrzędnego (bezpośredni rodzic na dysku) */
  folder: string;
  /** nazwa źródła (folder root obserwowany, np. "cortex-app", "łowca") */
  source: string;
  /** krótki podgląd początku zawartości pliku */
  preview?: string;
  /** grupa/podfolder dla struktury (zachowane dla kompatybilności) */
  group?: string;
}

export interface KosmosEdge {
  /** indeks węzła źródłowego */
  source: number;
  /** indeks węzła docelowego */
  target: number;
  /** rodzaj relacji: import kodu lub zawieranie folder→podfolder/plik */
  kind: 'import' | 'contains';
}

export interface KosmosGraph {
  nodes: KosmosNode[];
  edges: KosmosEdge[];
  /** lista obserwowanych folderów (źródeł) */
  sources: string[];
}

export interface KosmosScanRequest {
  /** lista folderów do zeskanowania (generyczne źródła) */
  folders: string[];
}

export interface KosmosMoveRequest {
  /** bezwzględna ścieżka pliku do przeniesienia */
  sourcePath: string;
  /** bezwzględna ścieżka folderu docelowego */
  targetFolder: string;
}

// === STRUKTURA BAZY DANYCH (Deterministyczna hierarchia folderów i plików) ===

export interface KosmosFileRecord {
  id: string;
  name: string;
  path: string;
  relativePath: string;
  folderPath: string;
  folderRelative: string;
  extension: string;
  type: 'kod' | 'markdown' | 'json' | 'txt' | 'inny';
  sizeBytes: number;
  preview?: string;
  updatedAt?: string;
}

export interface KosmosFolderRecord {
  path: string;
  relativePath: string;
  name: string;
  parentPath: string;
  fileCount: number;
  depth: number;
}

export interface KosmosProjectRecord {
  id: string;
  name: string;
  rootPath: string;
  scannedAt: string;
  folders: KosmosFolderRecord[];
  files: KosmosFileRecord[];
  stats: {
    totalFiles: number;
    totalFolders: number;
    totalBytes: number;
  };
}

// === STRUKTURA BAZY SQLite (node:sqlite) ===

export interface KosmosFolderRow {
  project_id: string;
  project_name: string;
  root_path: string;
  path: string;
  relative_path: string;
  name: string;
  parent_path: string;
  file_count: number;
  depth: number;
}

export interface KosmosFileRow {
  project_id: string;
  project_name: string;
  id: string;
  name: string;
  path: string;
  relative_path: string;
  folder_path: string;
  extension: string;
  type: 'kod' | 'markdown' | 'json' | 'txt' | 'inny';
  size_bytes: number;
  preview: string | null;
  updated_at: string | null;
}

export interface KosmosGraphData {
  folders: KosmosFolderRow[];
  files: KosmosFileRow[];
}

export interface KosmosProjectSummary {
  id: string;
  name: string;
  rootPath: string;
}

// === LIVE-OBSERWACJA (fs.watch) ===

export interface KosmosWatchEvent {
  projectId: string;
  at: string;
}