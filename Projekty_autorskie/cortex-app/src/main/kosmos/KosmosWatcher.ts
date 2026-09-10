// ============================================================================
// KOSMOS — Live-observacja folderów projektu (fs.watch)
// Nasłuchuje zmian w ścieżce projektu, debounce'uje eksplozje zdarzeń i po
// ustabilizowaniu wywołuje ponowny skan + upsert do SQLite. Zdarzenia są
// raportowane do renderera przez callback (mostek IPC).
//
// Uwaga: fs.watch na niektórych platformach zgłasza tylko nazwę/typ, nie
// pełną ścieżkę. Traktujemy to jako sygnał "coś się zmieniło" i wykonujemy
// pełne, deterministyczne skanowanie projektu (scanKosmosProjectHierarchy).
// ============================================================================

import * as fs from 'fs';
import type { CortexDb } from '../db/cortexDb';
import { scanKosmosProjectHierarchy } from './KosmosScanner';

const DEBOUNCE_MS = 600;
const THROTTLE_MS = 2000;

interface WatchEntry {
  rootPath: string;
  watcher: fs.FSWatcher;
  timer: NodeJS.Timeout | null;
  lastScanAt: number;
}

export type WatchChangeCallback = (projectId: string) => void;

export class KosmosWatcher {
  private watchers = new Map<string, WatchEntry>();

  constructor(
    private cortexDb: CortexDb,
    private onChange: WatchChangeCallback,
  ) {}

  /** Uruchamia obserwację ścieżki projektu. Idempotentny. */
  start(projectId: string, rootPath: string): boolean {
    const key = projectId;
    if (this.watchers.has(key)) return true;

    if (!fs.existsSync(rootPath) || !fs.statSync(rootPath).isDirectory()) {
      return false;
    }

    let watcher: fs.FSWatcher;
    try {
      watcher = fs.watch(rootPath, { recursive: true }, () => {
        this.scheduleScan(key, rootPath);
      });
    } catch {
      // recursive:true może nie być wspierane — spróbuj bez flagi
      try {
        watcher = fs.watch(rootPath, () => {
          this.scheduleScan(key, rootPath);
        });
      } catch (err) {
        console.error(`[KosmosWatcher] Nie można obserwować ${rootPath}:`, err);
        return false;
      }
    }

    watcher.on('error', (err) => {
      console.error(`[KosmosWatcher] Błąd watchera ${rootPath}:`, err);
    });

    this.watchers.set(key, { rootPath, watcher, timer: null, lastScanAt: 0 });
    console.log(`[KosmosWatcher] Obserwuję ${rootPath}`);
    return true;
  }

  /** Zatrzymuje obserwację projektu. */
  stop(projectId: string): void {
    const entry = this.watchers.get(projectId);
    if (!entry) return;
    if (entry.timer) clearTimeout(entry.timer);
    entry.watcher.close();
    this.watchers.delete(projectId);
    console.log(`[KosmosWatcher] Zatrzymano obserwację ${entry.rootPath}`);
  }

  /** Zatrzymuje wszystkie obserwacje. */
  stopAll(): void {
    for (const key of Array.from(this.watchers.keys())) {
      this.stop(key);
    }
  }

  private scheduleScan(projectId: string, rootPath: string): void {
    const entry = this.watchers.get(projectId);
    if (!entry) return;

    if (entry.timer) clearTimeout(entry.timer);

    // Debounce + throttle: skany nie częściej niż co THROTTLE_MS, nawet przy
    // nawale zdarzeń fs.watch (typowe dla dużych projektów).
    const elapsed = Date.now() - entry.lastScanAt;
    const delay = Math.max(DEBOUNCE_MS, THROTTLE_MS - elapsed);

    entry.timer = setTimeout(() => {
      entry.timer = null;
      this.rescan(projectId, rootPath);
    }, delay);
  }

  private rescan(projectId: string, rootPath: string): void {
    const entry = this.watchers.get(projectId);
    if (!entry) return;

    try {
      const scanned = scanKosmosProjectHierarchy(rootPath);
      if (!scanned) return;
      // Projekt mógł zmienić nazwę/id; trzymamy stabilny identyfikator.
      this.cortexDb.upsertProject({ ...scanned, id: projectId });
      entry.lastScanAt = Date.now();
      this.onChange(projectId);
    } catch (err) {
      console.error(`[KosmosWatcher] Błąd ponownego skanowania ${rootPath}:`, err);
    }
  }
}