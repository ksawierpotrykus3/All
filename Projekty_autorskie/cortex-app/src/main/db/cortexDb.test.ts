// @vitest-environment node
// ============================================================================
// Testy natywnej bazy SQLite (CortexDb) — migracja, upsert, odczyt grafu.
// ============================================================================

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { CortexDb } from './cortexDb';
import type { KosmosProjectRecord } from '../../shared/types/kosmos';

function makeTempDbPath(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cortex-db-'));
  return path.join(dir, 'cortex.db');
}

function makeProject(overrides: Partial<KosmosProjectRecord> = {}): KosmosProjectRecord {
  return {
    id: 'cortex_app',
    name: 'cortex-app',
    rootPath: 'c:/Users/Ksawier/Projekty/cortex-app',
    scannedAt: '2026-09-06T12:00:00.000Z',
    stats: { totalFiles: 2, totalFolders: 2, totalBytes: 3072 },
    folders: [
      {
        path: 'c:/Users/Ksawier/Projekty/cortex-app',
        relativePath: '',
        name: 'cortex-app',
        parentPath: 'c:/Users/Ksawier/Projekty',
        fileCount: 1,
        depth: 0,
      },
      {
        path: 'c:/Users/Ksawier/Projekty/cortex-app/src',
        relativePath: 'src',
        name: 'src',
        parentPath: 'c:/Users/Ksawier/Projekty/cortex-app',
        fileCount: 1,
        depth: 1,
      },
    ],
    files: [
      {
        id: 'package.json',
        name: 'package.json',
        path: 'c:/Users/Ksawier/Projekty/cortex-app/package.json',
        relativePath: 'package.json',
        folderPath: 'c:/Users/Ksawier/Projekty/cortex-app',
        folderRelative: '',
        extension: '.json',
        type: 'json',
        sizeBytes: 1024,
        preview: '{"name":"cortex-app"}',
        updatedAt: '2026-09-06T10:00:00.000Z',
      },
      {
        id: 'src/App.tsx',
        name: 'App.tsx',
        path: 'c:/Users/Ksawier/Projekty/cortex-app/src/App.tsx',
        relativePath: 'src/App.tsx',
        folderPath: 'c:/Users/Ksawier/Projekty/cortex-app/src',
        folderRelative: 'src',
        extension: '.tsx',
        type: 'kod',
        sizeBytes: 2048,
        preview: 'export function App() {}',
        updatedAt: '2026-09-06T11:00:00.000Z',
      },
    ],
    ...overrides,
  };
}

describe('CortexDb — natywna baza SQLite (node:sqlite)', () => {
  let db: CortexDb;
  let dbPath: string;

  beforeEach(() => {
    dbPath = makeTempDbPath();
    db = new CortexDb(dbPath);
    db.open();
  });

  afterEach(() => {
    db.close();
    try {
      fs.rmSync(path.dirname(dbPath), { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });

  it('otwiera bazę, tworzy tabele folders i files oraz jest pusta na starcie', () => {
    expect(db.path).toBe(dbPath);
    expect(db.hasAnyProject()).toBe(false);
    expect(db.projectCount()).toBe(0);
    expect(db.fileCount()).toBe(0);
  });

  it('upsertuje projekt i zwraca poprawne dane grafu', () => {
    db.upsertProject(makeProject());

    expect(db.hasAnyProject()).toBe(true);
    expect(db.projectCount()).toBe(1);
    expect(db.fileCount()).toBe(2);

    const projects = db.listProjects();
    expect(projects).toHaveLength(1);
    expect(projects[0].id).toBe('cortex_app');
    expect(projects[0].name).toBe('cortex-app');
    expect(projects[0].rootPath).toBe('c:/Users/Ksawier/Projekty/cortex-app');

    const graph = db.getGraphData('cortex_app');
    expect(graph.folders).toHaveLength(2);
    expect(graph.files).toHaveLength(2);

    const root = graph.folders.find((f) => f.depth === 0);
    expect(root).toBeTruthy();
    expect(root!.file_count).toBe(1);

    const appFile = graph.files.find((f) => f.name === 'App.tsx');
    expect(appFile).toBeTruthy();
    expect(appFile!.type).toBe('kod');
    expect(appFile!.folder_path).toBe('c:/Users/Ksawier/Projekty/cortex-app/src');
  });

  it('usuwa projekt wraz z jego folderami i plikami', () => {
    db.upsertProject(makeProject());
    db.deleteProject('cortex_app');

    expect(db.hasAnyProject()).toBe(false);
    expect(db.listProjects()).toHaveLength(0);
    expect(db.fileCount()).toBe(0);
  });

  it('nadpisuje istniejący projekt przy ponownym upsercie (zastępuje pliki)', () => {
    db.upsertProject(makeProject());

    const updated = makeProject({
      stats: { totalFiles: 1, totalFolders: 2, totalBytes: 1024 },
      files: [
        {
          id: 'package.json',
          name: 'package.json',
          path: 'c:/Users/Ksawier/Projekty/cortex-app/package.json',
          relativePath: 'package.json',
          folderPath: 'c:/Users/Ksawier/Projekty/cortex-app',
          folderRelative: '',
          extension: '.json',
          type: 'json',
          sizeBytes: 1024,
          preview: '{}',
          updatedAt: '2026-09-06T12:00:00.000Z',
        },
      ],
    });
    db.upsertProject(updated);

    expect(db.fileCount()).toBe(1);
    const files = db.getFilesByProject('cortex_app');
    expect(files).toHaveLength(1);
    expect(files[0].name).toBe('package.json');
  });

  it('obsługuje wiele projektów niezależnie', () => {
    db.upsertProject(makeProject());
    db.upsertProject(
      makeProject({
        id: 'lowca',
        name: 'łowca',
        rootPath: 'c:/Users/Ksawier/Projekty/lowca',
        folders: [
          {
            path: 'c:/Users/Ksawier/Projekty/lowca',
            relativePath: '',
            name: 'łowca',
            parentPath: 'c:/Users/Ksawier/Projekty',
            fileCount: 0,
            depth: 0,
          },
        ],
        files: [],
        stats: { totalFiles: 0, totalFolders: 1, totalBytes: 0 },
      }),
    );

    expect(db.projectCount()).toBe(2);
    expect(db.listProjects()).toHaveLength(2);
    expect(db.getGraphData('lowca').folders).toHaveLength(1);
    expect(db.getGraphData('lowca').files).toHaveLength(0);
    expect(db.getGraphData('cortex_app').files).toHaveLength(2);
  });

  it('migrateFromJson przenosi projekty z JSON do SQLite', () => {
    const legacy = [
      makeProject(),
      makeProject({
        id: 'lowca',
        name: 'łowca',
        rootPath: 'c:/Users/Ksawier/Projekty/lowca',
        folders: [
          {
            path: 'c:/Users/Ksawier/Projekty/lowca',
            relativePath: '',
            name: 'łowca',
            parentPath: 'c:/Users/Ksawier/Projekty',
            fileCount: 1,
            depth: 0,
          },
        ],
        files: [
          {
            id: 'notatka.txt',
            name: 'notatka.txt',
            path: 'c:/Users/Ksawier/Projekty/lowca/notatka.txt',
            relativePath: 'notatka.txt',
            folderPath: 'c:/Users/Ksawier/Projekty/lowca',
            folderRelative: '',
            extension: '.txt',
            type: 'txt',
            sizeBytes: 512,
            preview: 'treść',
            updatedAt: '2026-09-06T11:00:00.000Z',
          },
        ],
        stats: { totalFiles: 1, totalFolders: 1, totalBytes: 512 },
      }),
    ];

    db.migrateFromJson(legacy);

    expect(db.projectCount()).toBe(2);
    expect(db.fileCount()).toBe(3);
    expect(db.getGraphData('lowca').files[0].name).toBe('notatka.txt');
  });

  it('wycofuje transakcję, gdy zapis pliku narusza NOT NULL', () => {
    db.upsertProject(makeProject());

    // folderPath = undefined -> wymusza naruszenie NOT NULL w SQLite.
    const bad = makeProject();
    bad.files[0].folderPath = undefined as unknown as string;

    expect(() => db.upsertProject(bad)).toThrow();
    // Po rollbacku w bazie pozostaje oryginalny stan (2 pliki), bez częściowego zapisu.
    expect(db.fileCount()).toBe(2);
  });

  it('zapisuje i odczytuje pozycje węzłów (kosmos_node_positions) oraz zachowuje je przy rescanie', () => {
    db.upsertProject(makeProject());

    // Zapisz pozycje dla dwóch węzłów
    db.saveNodePositions('cortex_app', {
      'd:c:/Users/Ksawier/Projekty/cortex-app': { x: 100.5, y: 200.5 },
      'f:c:/Users/Ksawier/Projekty/cortex-app/package.json': { x: 120.0, y: 230.0 },
    });

    const positions = db.getNodePositions('cortex_app');
    expect(positions['d:c:/Users/Ksawier/Projekty/cortex-app']).toEqual({ x: 100.5, y: 200.5 });
    expect(positions['f:c:/Users/Ksawier/Projekty/cortex-app/package.json']).toEqual({ x: 120.0, y: 230.0 });

    // Ponowny upsert projektu (rescan dysku) NIE usuwa zapisanych pozycji
    db.upsertProject(makeProject());
    const positionsAfterRescan = db.getNodePositions('cortex_app');
    expect(positionsAfterRescan['d:c:/Users/Ksawier/Projekty/cortex-app']).toEqual({ x: 100.5, y: 200.5 });

    // Aktualizacja istniejącej pozycji (ON CONFLICT DO UPDATE)
    db.saveNodePositions('cortex_app', {
      'd:c:/Users/Ksawier/Projekty/cortex-app': { x: 300.0, y: 400.0 },
    });
    const updated = db.getNodePositions('cortex_app');
    expect(updated['d:c:/Users/Ksawier/Projekty/cortex-app']).toEqual({ x: 300.0, y: 400.0 });
  });
});