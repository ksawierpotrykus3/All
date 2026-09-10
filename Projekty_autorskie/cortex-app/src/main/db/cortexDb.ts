// ============================================================================
// CORTEX — Natywna baza SQLite (node:sqlite)
// Zastępuje JSON-owy magazyn kosmos_db.json tabelami folders / files w pliku
// data/cortex.db. Zero zewnętrznych zależności — korzystamy z wbudowanego
// modułu node:sqlite (Node >= 22, Electron >= 42).
// ============================================================================

import { DatabaseSync } from 'node:sqlite';
import * as fs from 'fs';
import * as path from 'path';
import type {
  KosmosProjectRecord,
  KosmosFolderRow,
  KosmosFileRow,
  KosmosGraphData,
} from '../../shared/types/kosmos';

// === Schemat SQL ============================================================
const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS folders (
  project_id     TEXT NOT NULL,
  project_name   TEXT NOT NULL,
  root_path      TEXT NOT NULL,
  path           TEXT NOT NULL,
  relative_path  TEXT NOT NULL,
  name           TEXT NOT NULL,
  parent_path    TEXT NOT NULL,
  file_count     INTEGER NOT NULL DEFAULT 0,
  depth          INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (project_id, path)
);

CREATE TABLE IF NOT EXISTS files (
  project_id     TEXT NOT NULL,
  project_name   TEXT NOT NULL,
  id             TEXT NOT NULL,
  name           TEXT NOT NULL,
  path           TEXT NOT NULL,
  relative_path  TEXT NOT NULL,
  folder_path    TEXT NOT NULL,
  extension      TEXT NOT NULL,
  type           TEXT NOT NULL,
  size_bytes     INTEGER NOT NULL DEFAULT 0,
  preview        TEXT,
  updated_at     TEXT,
  PRIMARY KEY (project_id, id)
);

CREATE TABLE IF NOT EXISTS kosmos_node_positions (
  project_id     TEXT NOT NULL,
  node_id        TEXT NOT NULL,
  x              REAL NOT NULL,
  y              REAL NOT NULL,
  updated_at     TEXT,
  PRIMARY KEY (project_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_files_folder ON files (project_id, folder_path);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders (project_id, parent_path);
`;

// === Bazowa klasa dostępu do SQLite ========================================
export class CortexDb {
  private db?: DatabaseSync;
  private dbPath: string;

  constructor(dbPath: string) {
    this.dbPath = dbPath;
  }

  /** Otwiera (lub tworzy) bazę i zapewnia aktualny schemat. */
  open(): void {
    const dir = path.dirname(this.dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    this.db = new DatabaseSync(this.dbPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
    this.db.exec('PRAGMA busy_timeout = 5000;');
    this.db.exec('PRAGMA foreign_keys = ON;');
    this.db.exec(SCHEMA_SQL);
  }

  close(): void {
    if (!this.db) return;
    try {
      this.db.close();
    } catch {
      /* baza mogła już zostać zamknięta */
    }
    this.db = undefined;
  }

  /** Gwarantuje zainicjalizowaną instancję bazy. */
  private get dbSync(): DatabaseSync {
    if (!this.db) {
      throw new Error('CortexDb nie jest otwarta — wywołaj open() przed użyciem.');
    }
    return this.db;
  }

  /** Ścieżka pliku bazy (do diagnostyki). */
  get path(): string {
    return this.dbPath;
  }

  // =========================================================================
  // Zapis hierarchii projektu (upsert)
  // =========================================================================
  upsertProject(project: KosmosProjectRecord): void {
    const stmtFolder = this.dbSync.prepare(`
      INSERT INTO folders (
        project_id, project_name, root_path, path, relative_path,
        name, parent_path, file_count, depth
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(project_id, path) DO UPDATE SET
        project_name = excluded.project_name,
        root_path = excluded.root_path,
        relative_path = excluded.relative_path,
        name = excluded.name,
        parent_path = excluded.parent_path,
        file_count = excluded.file_count,
        depth = excluded.depth
    `);

    const stmtFile = this.dbSync.prepare(`
      INSERT INTO files (
        project_id, project_name, id, name, path, relative_path,
        folder_path, extension, type, size_bytes, preview, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(project_id, id) DO UPDATE SET
        project_name = excluded.project_name,
        name = excluded.name,
        path = excluded.path,
        relative_path = excluded.relative_path,
        folder_path = excluded.folder_path,
        extension = excluded.extension,
        type = excluded.type,
        size_bytes = excluded.size_bytes,
        preview = excluded.preview,
        updated_at = excluded.updated_at
    `);

    const delFolder = this.dbSync.prepare(
      'DELETE FROM folders WHERE project_id = ? AND path = ?',
    );
    const delFile = this.dbSync.prepare(
      'DELETE FROM files WHERE project_id = ? AND id = ?',
    );

    this.dbSync.exec('BEGIN');
    try {
      // Usuń foldery, które już nie istnieją w tym projekcie.
      const currentFolderPaths = new Set(project.folders.map((f) => f.path));
      const existingFolders = this.dbSync
        .prepare('SELECT path FROM folders WHERE project_id = ?')
        .all(project.id) as unknown as { path: string }[];
      for (const row of existingFolders) {
        if (!currentFolderPaths.has(row.path)) {
          delFolder.run(project.id, row.path);
        }
      }

      // Usuń pliki, które już nie istnieją w tym projekcie.
      const currentFileIds = new Set(project.files.map((f) => f.id));
      const existingFiles = this.dbSync
        .prepare('SELECT id FROM files WHERE project_id = ?')
        .all(project.id) as unknown as { id: string }[];
      for (const row of existingFiles) {
        if (!currentFileIds.has(row.id)) {
          delFile.run(project.id, row.id);
        }
      }

      for (const f of project.folders) {
        stmtFolder.run(
          project.id,
          project.name,
          project.rootPath,
          f.path,
          f.relativePath,
          f.name,
          f.parentPath,
          f.fileCount,
          f.depth,
        );
      }

      for (const file of project.files) {
        stmtFile.run(
          project.id,
          project.name,
          file.id,
          file.name,
          file.path,
          file.relativePath,
          file.folderPath,
          file.extension,
          file.type,
          file.sizeBytes,
          file.preview ?? null,
          file.updatedAt ?? null,
        );
      }

      this.dbSync.exec('COMMIT');
    } catch (err) {
      this.dbSync.exec('ROLLBACK');
      throw err;
    }
  }

  /** Usuwa cały projekt (foldery + pliki). */
  deleteProject(projectId: string): void {
    this.dbSync.exec('BEGIN');
    try {
      this.dbSync.prepare('DELETE FROM files WHERE project_id = ?').run(projectId);
      this.dbSync.prepare('DELETE FROM folders WHERE project_id = ?').run(projectId);
      this.dbSync.exec('COMMIT');
    } catch (err) {
      this.dbSync.exec('ROLLBACK');
      throw err;
    }
  }

  /** Zwraca listę unikalnych projektów obecnych w bazie. */
  listProjects(): { id: string; name: string; rootPath: string }[] {
    const rows = this.dbSync
      .prepare(
        `SELECT project_id AS id, project_name AS name, root_path AS rootPath
         FROM folders
         GROUP BY project_id
         UNION
         SELECT project_id, project_name, folder_path AS rootPath
         FROM files
         WHERE project_id NOT IN (SELECT project_id FROM folders)
         GROUP BY project_id`,
      )
      .all() as unknown as { id: string; name: string; rootPath: string }[];
    return rows;
  }

  // =========================================================================
  // Odczyt danych dla grafu (foldery + pliki)
  // =========================================================================
  getFoldersByProject(projectId: string): KosmosFolderRow[] {
    return this.dbSync
      .prepare(
        'SELECT * FROM folders WHERE project_id = ? ORDER BY depth, relative_path',
      )
      .all(projectId) as unknown as KosmosFolderRow[];
  }

  getFilesByProject(projectId: string): KosmosFileRow[] {
    return this.dbSync
      .prepare(
        'SELECT * FROM files WHERE project_id = ? ORDER BY relative_path',
      )
      .all(projectId) as unknown as KosmosFileRow[];
  }

  getGraphData(projectId: string): KosmosGraphData {
    return {
      folders: this.getFoldersByProject(projectId),
      files: this.getFilesByProject(projectId),
    };
  }

  getFolderRow(projectId: string, folderPath: string): KosmosFolderRow | null {
    return (
      (this.dbSync
        .prepare('SELECT * FROM folders WHERE project_id = ? AND path = ?')
        .get(projectId, folderPath) as unknown as KosmosFolderRow) ?? null
    );
  }

  getFileRow(projectId: string, fileId: string): KosmosFileRow | null {
    return (
      (this.dbSync
        .prepare('SELECT * FROM files WHERE project_id = ? AND id = ?')
        .get(projectId, fileId) as unknown as KosmosFileRow) ?? null
    );
  }

  /** Czy baza zawiera choć jeden projekt (służy do decyzji o migracji). */
  hasAnyProject(): boolean {
    const row = this.dbSync
      .prepare('SELECT COUNT(*) AS n FROM folders')
      .get() as unknown as { n: number };
    return (row?.n ?? 0) > 0;
  }

  /**
   * Migruje rekordy projektów z legacy JSON do SQLite. Idempotentna:
   * nie nadpisuje istniejących projektów w bazie.
   */
  migrateFromJson(projects: KosmosProjectRecord[]): void {
    for (const project of projects) {
      this.upsertProject(project);
    }
  }

  /** Liczba projektów przechowywanych w bazie. */
  projectCount(): number {
    const row = this.dbSync
      .prepare('SELECT COUNT(DISTINCT project_id) AS n FROM folders')
      .get() as unknown as { n: number };
    return row?.n ?? 0;
  }

  /** Całkowita liczba plików we wszystkich projektach. */
  fileCount(): number {
    const row = this.dbSync
      .prepare('SELECT COUNT(*) AS n FROM files')
      .get() as unknown as { n: number };
    return row?.n ?? 0;
  }

  /** Zapisuje pozycje węzłów (x, y) dla danego projektu w tabeli kosmos_node_positions. */
  saveNodePositions(
    projectId: string,
    positions: Record<string, { x: number; y: number }>,
  ): void {
    const entries = Object.entries(positions);
    if (entries.length === 0) return;

    const stmt = this.dbSync.prepare(`
      INSERT INTO kosmos_node_positions (project_id, node_id, x, y, updated_at)
      VALUES (?, ?, ?, ?, datetime('now'))
      ON CONFLICT(project_id, node_id) DO UPDATE SET
        x = excluded.x,
        y = excluded.y,
        updated_at = excluded.updated_at
    `);

    this.dbSync.exec('BEGIN');
    try {
      for (const [nodeId, pos] of entries) {
        if (Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
          stmt.run(projectId, nodeId, pos.x, pos.y);
        }
      }
      this.dbSync.exec('COMMIT');
    } catch (err) {
      this.dbSync.exec('ROLLBACK');
      throw err;
    }
  }

  /** Pobiera zapisane pozycje węzłów dla danego projektu. */
  getNodePositions(projectId: string): Record<string, { x: number; y: number }> {
    const rows = this.dbSync
      .prepare('SELECT node_id, x, y FROM kosmos_node_positions WHERE project_id = ?')
      .all(projectId) as unknown as Array<{ node_id: string; x: number; y: number }>;

    const result: Record<string, { x: number; y: number }> = {};
    for (const r of rows) {
      result[r.node_id] = { x: r.x, y: r.y };
    }
    return result;
  }
}