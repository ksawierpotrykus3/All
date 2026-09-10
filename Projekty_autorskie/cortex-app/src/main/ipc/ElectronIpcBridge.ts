// ============================================================================
// ElectronIpcBridge — Canvas Projekty & AI Supervisor
// Rejestruje IPC handlery dla canvasu oraz modułu nadzoru łańcuchów AI.
// ============================================================================

import { ipcMain, IpcMainInvokeEvent, dialog, BrowserWindow } from 'electron';
import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { StorageEngine } from '../storage/StorageEngine';
import { CortexDb } from '../db/cortexDb';
import type {
  Projekt,
  ProjektyNode,
  ProjektyEdge,
  ProjektyNodeAnnotation,
} from '../../types';
import type { ChatSession } from '../../shared/types/chat';
import type { Lancuch, DecyzjaPayload } from '../../supervisor/types';
import type { KosmosProjectSummary } from '../../shared/types/kosmos';
import { scanKosmos, scanKosmosProjectHierarchy, projectUsesAi } from '../kosmos/KosmosScanner';
import { KosmosWatcher } from '../kosmos/KosmosWatcher';

// Ścieżka do katalogu useme_core (sibling cortex-app), gdzie leży chain_executor.py.
// Zakładamy, że proces startuje z katalogu głównego projektu (cortex-app).
const USEME_CORE_DIR = path.join(process.cwd(), '..', 'useme_core');

// Limit czasu dla procesów potomnych — zapobiega zawieszeniu IPC na zawsze.
const CHILD_TIMEOUT_MS = 10 * 60 * 1000; // 10 minut

// Walidacja komendy w polu `uruchom.komenda`. Zapobiega wstrzyknięciu poleceń
// shell (np. `cmd /c ...`, `a && b`, `a | b`, przekierowania, średniki).
function validateCommand(komenda: string): void {
  if (!komenda || typeof komenda !== 'string') {
    throw new Error('Brak komendy do uruchomienia');
  }
  const trimmed = komenda.trim();
  if (!trimmed) {
    throw new Error('Pusta komenda do uruchomienia');
  }
  if (/[;&|><`$()!\r\n]/.test(trimmed)) {
    throw new Error(`Niedozwolona komenda: ${JSON.stringify(trimmed)}`);
  }
}

// Walidacja argumentów — blokuje sekwencje interpretowane przez cmd.exe.
function validateArg(arg: string): void {
  if (typeof arg !== 'string') {
    throw new Error('Argument musi być łańcuchem znaków');
  }
  if (/[\r\n]/.test(arg)) {
    throw new Error('Niedozwolony znak nowej linii w argumencie');
  }
  // Blokada separatorów poleceń cmd.exe oraz operatorów przekierowania
  if (/(^|[\s])&|&&|\|\||\||>|<|%(?=[A-Za-z])/.test(arg)) {
    throw new Error(`Niedozwolony argument: ${JSON.stringify(arg)}`);
  }
}

// Sanityzacja identyfikatora używanego w ścieżkach plików — zapobiega path traversal.
function sanitizeFilePathSegment(id: string): string {
  const s = String(id);
  if (!s || s === '.' || s === '..' || s.includes('/') || s.includes('\\') || s.includes('\0')) {
    throw new Error(`Invalid id: ${JSON.stringify(id)}`);
  }
  return s;
}

export class ElectronIpcBridge {
  private seedingPromise: Promise<void> | null = null;
  private seededOnce = false;
  private watcher: KosmosWatcher;

  constructor(
    private ipc: typeof ipcMain,
    private storage: StorageEngine,
    private cortexDb: CortexDb,
  ) {
    this.watcher = new KosmosWatcher(cortexDb, (projectId) => {
      this.broadcastWatchEvent(projectId);
    });
  }

  /**
   * Rejestruje wszystkie IPC handlery.
   */
  registerHandlers(): void {
    this.registerProjektyHandlers();
    this.registerSupervisorHandlers();
    this.registerChatHandlers();
    this.registerKosmosHandlers();
    this.registerKosmosSqliteHandlers();
  }

  /**
   * Sprawdza, czy podana ścieżka pliku leży w obrębie któregoś z projektów
   * przechowywanych w bazie SQLite. Zapobiega odczytowi dowolnych plików
   * z dysku przez renderer (path traversal).
   */
  private isPathWithinKnownProjects(filePath: string): boolean {
    const target = path.resolve(filePath).toLowerCase();
    for (const project of this.cortexDb.listProjects()) {
      const root = path.resolve(project.rootPath).toLowerCase();
      if (target === root || target.startsWith(root + path.sep)) {
        return true;
      }
    }
    return false;
  }

  // =========================================================================
  // Canvas Projekty Handlers
  // =========================================================================
  private registerProjektyHandlers(): void {
    // Projects
    this.ipc.handle('projekty:project:save', async (_event: IpcMainInvokeEvent, payload: { project?: Projekt } & Projekt) => {
      try {
        const proj = payload?.project || payload;
        if (!proj || !proj.id) {
          throw new Error('Invalid project payload in projekty:project:save: missing id');
        }
        this.storage.saveProjekt(proj);
        return { success: true };
      } catch (err) {
        console.error('[projekty:project:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('projekty:project:get-all', async () => {
      try {
        return this.storage.getProjects();
      } catch (err) {
        console.error('[projekty:project:get-all]', err);
        return [];
      }
    });

    this.ipc.handle('projekty:project:get', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        return this.storage.getProjekt(payload.id);
      } catch (err) {
        console.error('[projekty:project:get]', err);
        return null;
      }
    });

    this.ipc.handle('projekty:project:delete', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        this.storage.deleteProjekt(payload.id);
        return { success: true };
      } catch (err) {
        console.error('[projekty:project:delete]', err);
        return { success: false };
      }
    });

    // Nodes
    this.ipc.handle('projekty:node:save', async (_event: IpcMainInvokeEvent, payload: { node: ProjektyNode }) => {
      try {
        this.storage.saveProjektyNode(payload.node);
        return { success: true };
      } catch (err) {
        console.error('[projekty:node:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('projekty:node:get', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        return this.storage.getProjektyNodes(payload.projectId);
      } catch (err) {
        console.error('[projekty:node:get]', err);
        return [];
      }
    });

    this.ipc.handle('projekty:node:delete', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        this.storage.deleteProjektyNode(payload.id);
        return { success: true };
      } catch (err) {
        console.error('[projekty:node:delete]', err);
        return { success: false };
      }
    });

    // Edges
    this.ipc.handle('projekty:edge:save', async (_event: IpcMainInvokeEvent, payload: { edge: ProjektyEdge }) => {
      try {
        this.storage.saveProjektyEdge(payload.edge);
        return { success: true };
      } catch (err) {
        console.error('[projekty:edge:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('projekty:edge:get', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        return this.storage.getProjektyEdges(payload.projectId);
      } catch (err) {
        console.error('[projekty:edge:get]', err);
        return [];
      }
    });

    this.ipc.handle('projekty:edge:delete', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        this.storage.deleteProjektyEdge(payload.id);
        return { success: true };
      } catch (err) {
        console.error('[projekty:edge:delete]', err);
        return { success: false };
      }
    });

    // Node Annotations
    this.ipc.handle('projekty:annotation:save', async (_event: IpcMainInvokeEvent, payload: { annotation: ProjektyNodeAnnotation }) => {
      try {
        this.storage.saveProjektyNodeAnnotation(payload.annotation);
        return { success: true };
      } catch (err) {
        console.error('[projekty:annotation:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('projekty:annotation:get', async (_event: IpcMainInvokeEvent, payload: { nodeId: string }) => {
      try {
        return this.storage.getProjektyNodeAnnotations(payload.nodeId);
      } catch (err) {
        console.error('[projekty:annotation:get]', err);
        return [];
      }
    });

    this.ipc.handle('projekty:annotation:delete', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        this.storage.deleteProjektyNodeAnnotation(payload.id);
        return { success: true };
      } catch (err) {
        console.error('[projekty:annotation:delete]', err);
        return { success: false };
      }
    });
  }

  // =========================================================================
  // AI Supervisor Handlers (Real Filesystem data/pipelines)
  // =========================================================================
  private registerSupervisorHandlers(): void {
    this.ipc.handle('supervisor:pipeline:get-all', async () => {
      try {
        return this.storage.getPipelines();
      } catch (err) {
        console.error('[supervisor:pipeline:get-all]', err);
        return [];
      }
    });

    this.ipc.handle('supervisor:pipeline:get', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        return this.storage.getPipeline(payload.id);
      } catch (err) {
        console.error('[supervisor:pipeline:get]', err);
        return null;
      }
    });

    this.ipc.handle('supervisor:pipeline:save', async (_event: IpcMainInvokeEvent, payload: { pipeline: Lancuch }) => {
      try {
        this.storage.savePipeline(payload.pipeline);
        return { success: true };
      } catch (err) {
        console.error('[supervisor:pipeline:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('supervisor:decision:save', async (_event: IpcMainInvokeEvent, payload: DecyzjaPayload) => {
      try {
        this.storage.saveDecision(payload);
        return { success: true };
      } catch (err) {
        console.error('[supervisor:decision:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('supervisor:chain:run', async (_event: IpcMainInvokeEvent, payload: { pipelineId: string; zlecenieDane?: Record<string, unknown> }) => {
      try {
        const output = await this.runAutomation(payload.pipelineId, payload.zlecenieDane);
        return { success: true, output };
      } catch (err) {
        console.error('[supervisor:chain:run]', err);
        return { success: false, error: String(err) };
      }
    });

    // Uniwersalne uruchomienie automatyzacji — czyta pole `uruchom` z definicji
    // i odpala dowolną komendę (python, .bat, node, .exe itd.). Bez tego pola
    // fallback do domyślnego silnika łańcucha AI (chain_executor.py).
    this.ipc.handle('supervisor:run', async (_event: IpcMainInvokeEvent, payload: { pipelineId: string; zlecenieDane?: Record<string, unknown> }) => {
      try {
        const output = await this.runAutomation(payload.pipelineId, payload.zlecenieDane);
        return { success: true, output };
      } catch (err) {
        console.error('[supervisor:run]', err);
        return { success: false, error: String(err) };
      }
    });
  }

  // =========================================================================
  // AI Chat Handlers
  // =========================================================================
  private registerChatHandlers(): void {
    this.ipc.handle('chat:session:save', async (_event: IpcMainInvokeEvent, payload: { session: ChatSession }) => {
      try {
        if (!payload?.session?.id) throw new Error('Invalid chat session payload: missing id');
        this.storage.saveChatSession(payload.session);
        return { success: true };
      } catch (err) {
        console.error('[chat:session:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('chat:session:get-all', async () => {
      try {
        return this.storage.getChatSessions();
      } catch (err) {
        console.error('[chat:session:get-all]', err);
        return [];
      }
    });

    this.ipc.handle('chat:session:delete', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        this.storage.deleteChatSession(payload.id);
        return { success: true };
      } catch (err) {
        console.error('[chat:session:delete]', err);
        return { success: false };
      }
    });

    this.ipc.handle('chat:active-session:save', async (_event: IpcMainInvokeEvent, payload: { id: string }) => {
      try {
        this.storage.saveChatActiveSessionId(payload.id);
        return { success: true };
      } catch (err) {
        console.error('[chat:active-session:save]', err);
        return { success: false };
      }
    });

    this.ipc.handle('chat:active-session:get', async () => {
      try {
        return this.storage.getChatActiveSessionId();
      } catch (err) {
        console.error('[chat:active-session:get]', err);
        return null;
      }
    });
  }

  // =========================================================================
  // Kosmos Handlers (graf wiedzy: pliki + importy)
  // =========================================================================
  private registerKosmosHandlers(): void {
    // Skan legacy (graf)
    this.ipc.handle('kosmos:scan', async (_event: IpcMainInvokeEvent, payload: { folders: string[] }) => {
      try {
        if (!payload?.folders || !Array.isArray(payload.folders)) {
          throw new Error('Invalid kosmos:scan payload: missing folders');
        }
        return scanKosmos(payload.folders);
      } catch (err) {
        console.error('[kosmos:scan]', err);
        return { nodes: [], edges: [], sources: [] };
      }
    });

    // Pobranie legacy bazy JSON. Nowe źródło prawdy to SQLite (kosmos:sqlite:*);
    // ten handler zachowujemy wyłącznie dla zgodności wstecznej i nie skanuje
    // żadnych ścieżek automatycznie.
    this.ipc.handle('kosmos:getProjects', async () => {
      try {
        return this.storage.getKosmosDatabase();
      } catch (err) {
        console.error('[kosmos:getProjects]', err);
        return [];
      }
    });

    // Dodanie/Zeskanowanie nowego projektu do bazy
    this.ipc.handle('kosmos:addProject', async (_event: IpcMainInvokeEvent, payload: { folderPath: string }) => {
      try {
        const { folderPath } = payload || {};
        if (!folderPath || !fs.existsSync(folderPath)) {
          throw new Error(`Folder nie istnieje: ${folderPath}`);
        }
        const scanned = scanKosmosProjectHierarchy(folderPath);
        if (!scanned) {
          throw new Error(`Nie udało się zeskanować folderu: ${folderPath}`);
        }
        const projects = this.storage.getKosmosDatabase();
        const existingIdx = projects.findIndex(p => path.resolve(p.rootPath) === path.resolve(folderPath));
        if (existingIdx >= 0) {
          projects[existingIdx] = scanned;
        } else {
          projects.push(scanned);
        }
        this.storage.saveKosmosDatabase(projects);
        return { success: true, projects, added: scanned };
      } catch (err) {
        console.error('[kosmos:addProject]', err);
        return { success: false, error: String(err) };
      }
    });

    // Usunięcie projektu z bazy
    this.ipc.handle('kosmos:deleteProject', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        const { projectId } = payload || {};
        let projects = this.storage.getKosmosDatabase();
        projects = projects.filter(p => p.id !== projectId);
        this.storage.saveKosmosDatabase(projects);
        return { success: true, projects };
      } catch (err) {
        console.error('[kosmos:deleteProject]', err);
        return { success: false, error: String(err) };
      }
    });

    // Systemowy dialog wyboru folderu z dysku
    this.ipc.handle('kosmos:pickFolder', async () => {
      try {
        const win = BrowserWindow.getFocusedWindow();
        const options = {
          properties: ['openDirectory' as const, 'dontAddToRecent' as const],
          title: 'Wybierz folder projektu do bazy Cortex',
        };
        const res = win
          ? await dialog.showOpenDialog(win, options)
          : await dialog.showOpenDialog(options);
        if (res.canceled || !res.filePaths?.[0]) return null;
        return res.filePaths[0];
      } catch (err) {
        console.error('[kosmos:pickFolder]', err);
        return null;
      }
    });

    // Odczyt pełnej zawartości pliku z dysku do podglądu.
    // Walidacja: ścieżka musi leżeć w obrębie któregoś z projektów w bazie,
    // aby renderer nie mógł odczytać dowolnego pliku z dysku (path traversal).
    this.ipc.handle('kosmos:readFile', async (_event: IpcMainInvokeEvent, payload: { filePath: string }) => {
      try {
        const { filePath } = payload || {};
        if (!filePath || !fs.existsSync(filePath)) {
          throw new Error(`Plik nie istnieje: ${filePath}`);
        }
        if (!this.isPathWithinKnownProjects(filePath)) {
          throw new Error(`Odmowa odczytu pliku spoza projektów: ${filePath}`);
        }
        const content = fs.readFileSync(filePath, 'utf-8');
        return { success: true, content };
      } catch (err) {
        console.error('[kosmos:readFile]', err);
        return { success: false, error: String(err) };
      }
    });

    // Przeniesienie pliku do innego folderu — REALNA operacja na dysku (fs.rename) + aktualizacja w bazie
    this.ipc.handle('kosmos:move', async (_event: IpcMainInvokeEvent, payload: { sourcePath: string; targetFolder: string }) => {
      try {
        const { sourcePath, targetFolder } = payload ?? {};
        if (!sourcePath || !targetFolder || typeof sourcePath !== 'string' || typeof targetFolder !== 'string') {
          throw new Error('Invalid kosmos:move payload: missing paths');
        }
        if (!path.isAbsolute(sourcePath) || !path.isAbsolute(targetFolder)) {
          throw new Error('kosmos:move wymaga bezwzględnych ścieżek');
        }
        if (!fs.existsSync(sourcePath)) {
          throw new Error(`Plik źródłowy nie istnieje: ${sourcePath}`);
        }
        if (!fs.statSync(sourcePath).isFile()) {
          throw new Error(`Źródło nie jest plikiem: ${sourcePath}`);
        }
        if (!fs.existsSync(targetFolder) || !fs.statSync(targetFolder).isDirectory()) {
          throw new Error(`Folder docelowy nie istnieje: ${targetFolder}`);
        }

        const srcDir = path.dirname(sourcePath);
        if (path.resolve(srcDir) === path.resolve(targetFolder)) {
          // Plik już jest w tym folderze — nic do zrobienia
          return { success: true, moved: false, newPath: sourcePath };
        }

        const fileName = path.basename(sourcePath);
        const newPath = path.join(targetFolder, fileName);

        // Odmowa nadpisania istniejącego pliku o tej samej nazwie
        if (fs.existsSync(newPath)) {
          throw new Error(`Plik docelowy już istnieje: ${newPath}`);
        }

        // 1. Zmień na dysku
        fs.renameSync(sourcePath, newPath);

        // 2. Zaktualizuj bazę danych
        this.storage.updateKosmosFileMove(sourcePath, targetFolder, newPath);

        return { success: true, moved: true, newPath };
      } catch (err) {
        console.error('[kosmos:move]', err);
        return { success: false, error: String(err) };
      }
    });
  }

  // =========================================================================
  // Kosmos — natywna baza SQLite (cortex.db)
  // =========================================================================
  private registerKosmosSqliteHandlers(): void {
    // Jednorazowa migracja: JSON (kosmos_db.json) -> SQLite, jeśli baza pusta.
    // `seededOnce` gwarantuje, że migracja nigdy nie przywróci projektu,
    // który użytkownik celowo usunął z SQLite (pusta baza po usunięciu
    // ostatniego projektu nie może z powrotem wyzwolić seed).
    const ensureSeeded = (): Promise<void> => {
      if (this.seededOnce) return Promise.resolve();
      if (this.seedingPromise) return this.seedingPromise;
      this.seedingPromise = (async () => {
        if (this.cortexDb.hasAnyProject()) return;
        const legacy = this.storage.getKosmosDatabase();
        this.cortexDb.migrateFromJson(legacy);
      })().finally(() => {
        this.seededOnce = true;
        this.seedingPromise = null;
      });
      return this.seedingPromise;
    };

    this.ipc.handle('kosmos:sqlite:list-projects', async (): Promise<KosmosProjectSummary[]> => {
      try {
        await ensureSeeded();
        return this.cortexDb.listProjects();
      } catch (err) {
        console.error('[kosmos:sqlite:list-projects]', err);
        return [];
      }
    });

    this.ipc.handle('kosmos:sqlite:project-uses-ai', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        if (!payload?.projectId) {
          throw new Error('Invalid project-uses-ai payload: missing projectId');
        }
        const project = this.cortexDb.listProjects().find((p) => p.id === payload.projectId);
        if (!project) return { usesAi: false };
        return { usesAi: projectUsesAi(project.rootPath) };
      } catch (err) {
        console.error('[kosmos:sqlite:project-uses-ai]', err);
        return { usesAi: false };
      }
    });

    this.ipc.handle('kosmos:sqlite:get-graph', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        await ensureSeeded();
        if (!payload?.projectId) {
          throw new Error('Invalid kosmos:sqlite:get-graph payload: missing projectId');
        }
        return this.cortexDb.getGraphData(payload.projectId);
      } catch (err) {
        console.error('[kosmos:sqlite:get-graph]', err);
        return { folders: [], files: [] };
      }
    });

    this.ipc.handle(
      'kosmos:sqlite:save-positions',
      async (
        _event: IpcMainInvokeEvent,
        payload: { projectId: string; positions: Record<string, { x: number; y: number }> },
      ) => {
        try {
          if (!payload?.projectId || !payload?.positions) {
            throw new Error('Invalid kosmos:sqlite:save-positions payload: missing projectId or positions');
          }
          this.cortexDb.saveNodePositions(payload.projectId, payload.positions);
          return { success: true };
        } catch (err) {
          console.error('[kosmos:sqlite:save-positions]', err);
          return { success: false, error: String(err) };
        }
      },
    );

    this.ipc.handle(
      'kosmos:sqlite:get-positions',
      async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
        try {
          if (!payload?.projectId) {
            throw new Error('Invalid kosmos:sqlite:get-positions payload: missing projectId');
          }
          return this.cortexDb.getNodePositions(payload.projectId);
        } catch (err) {
          console.error('[kosmos:sqlite:get-positions]', err);
          return {};
        }
      },
    );

    this.ipc.handle('kosmos:sqlite:import-project', async (_event: IpcMainInvokeEvent, payload: { folderPath: string }) => {
      try {
        const { folderPath } = payload || {};
        if (!folderPath || !fs.existsSync(folderPath)) {
          throw new Error(`Folder nie istnieje: ${folderPath}`);
        }
        const scanned = scanKosmosProjectHierarchy(folderPath);
        if (!scanned) {
          throw new Error(`Nie udało się zeskanować folderu: ${folderPath}`);
        }
        this.cortexDb.upsertProject(scanned);

        // Rozpocznij live-observację świeżo dodanego projektu.
        this.watcher.start(scanned.id, scanned.rootPath);

        return { success: true, projectId: scanned.id };
      } catch (err) {
        console.error('[kosmos:sqlite:import-project]', err);
        return { success: false, error: String(err) };
      }
    });

    // === Live-observacja (fs.watch) ==========================================

    this.ipc.handle('kosmos:sqlite:watch-start', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        const { projectId } = payload || {};
        if (!projectId) {
          throw new Error('Invalid kosmos:sqlite:watch-start payload: missing projectId');
        }
        const project = this.cortexDb.listProjects().find((p) => p.id === projectId);
        if (!project) {
          throw new Error(`Projekt nie istnieje w bazie: ${projectId}`);
        }
        const ok = this.watcher.start(project.id, project.rootPath);
        return { success: ok, error: ok ? undefined : 'Nie można obserwować folderu' };
      } catch (err) {
        console.error('[kosmos:sqlite:watch-start]', err);
        return { success: false, error: String(err) };
      }
    });

    this.ipc.handle('kosmos:sqlite:watch-stop', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        const { projectId } = payload || {};
        if (!projectId) return { success: false };
        this.watcher.stop(projectId);
        return { success: true };
      } catch (err) {
        console.error('[kosmos:sqlite:watch-stop]', err);
        return { success: false };
      }
    });

    this.ipc.handle('kosmos:sqlite:delete-project', async (_event: IpcMainInvokeEvent, payload: { projectId: string }) => {
      try {
        const { projectId } = payload || {};
        if (!projectId) {
          throw new Error('Invalid kosmos:sqlite:delete-project payload: missing projectId');
        }
        this.watcher.stop(projectId);
        this.cortexDb.deleteProject(projectId);
        return { success: true };
      } catch (err) {
        console.error('[kosmos:sqlite:delete-project]', err);
        return { success: false, error: String(err) };
      }
    });
  }

  /** Wysyła zdarzenie zmiany projektu do wszystkich okien renderera. */
  private broadcastWatchEvent(projectId: string): void {
    for (const win of BrowserWindow.getAllWindows()) {
      win.webContents.send('kosmos:watch-event', {
        projectId,
        at: new Date().toISOString(),
      });
    }
  }

  /**
   * Uniwersalne uruchomienie automatyzacji.
   * Czyta pole `uruchom` z definicji potoku (data/pipelines/<id>.json) i odpala
   * wskazaną komendę. Jeśli pola nie ma — fallback do chain_executor.py.
   */
  private async runAutomation(pipelineId: string, zlecenieDane?: Record<string, unknown>): Promise<string> {
    const pipeline = this.storage.getPipeline(pipelineId);
    const uruchom = pipeline?.uruchom;

    if (!uruchom) {
      return this.runPythonChain(pipelineId, zlecenieDane);
    }

    const args = uruchom.args ? [...uruchom.args] : [];
    validateCommand(uruchom.komenda);
    args.forEach(validateArg);
    let tmpDataPath: string | null = null;
    if (zlecenieDane) {
      const safeId = sanitizeFilePathSegment(pipelineId);
      const cwd = uruchom.cwd || USEME_CORE_DIR;
      tmpDataPath = path.join(cwd, `.zlecenie-${safeId}-${Date.now()}.json`);
      fs.writeFileSync(tmpDataPath, JSON.stringify(zlecenieDane, null, 2), 'utf-8');
      args.push(tmpDataPath);
    }

    return new Promise((resolve, reject) => {
      const child = spawn(uruchom.komenda, args, {
        cwd: uruchom.cwd || USEME_CORE_DIR,
        windowsHide: true,
        shell: false,
      });

      let stdout = '';
      let stderr = '';
      let settled = false;

      const timeoutId = setTimeout(() => {
        if (!settled) {
          child.kill();
        }
      }, CHILD_TIMEOUT_MS);

      const cleanup = () => {
        clearTimeout(timeoutId);
        if (tmpDataPath && fs.existsSync(tmpDataPath)) {
          try { fs.unlinkSync(tmpDataPath); } catch { /* ignoruj */ }
        }
      };

      child.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
      child.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });

      child.on('error', (err) => {
        if (settled) return;
        settled = true;
        cleanup();
        reject(err);
      });

      child.on('close', (code) => {
        if (settled) return;
        settled = true;
        cleanup();
        if (code === 0) {
          resolve(stdout.trim());
        } else {
          reject(new Error(stderr.trim() || `Proces zakończony kodem ${code}`));
        }
      });
    });
  }

  /**
   * Odpala łańcuch AI: python chain_executor.py <pipelineId> [dane.json].
   * Dane zlecenia (opcjonalne) zapisujemy do tymczasowego pliku JSON.
   */
  private runPythonChain(pipelineId: string, zlecenieDane?: Record<string, unknown>): Promise<string> {
    return new Promise((resolve, reject) => {
      const safeId = sanitizeFilePathSegment(pipelineId);

      // Walidacja istnienia pipeline przed uruchomieniem (odporność na błędne id).
      const existing = this.storage.getPipeline(safeId);
      if (!existing) {
        reject(new Error(`Nie znaleziono pipeline o id: ${safeId}`));
        return;
      }

      const executorPath = path.join(USEME_CORE_DIR, 'chain_executor.py');
      if (!fs.existsSync(executorPath)) {
        reject(new Error(`Nie znaleziono chain_executor.py w ${USEME_CORE_DIR}`));
        return;
      }

      const args = [executorPath, safeId];

      let tmpDataPath: string | null = null;
      if (zlecenieDane) {
        tmpDataPath = path.join(USEME_CORE_DIR, `.zlecenie-${safeId}-${Date.now()}.json`);
        fs.writeFileSync(tmpDataPath, JSON.stringify(zlecenieDane, null, 2), 'utf-8');
        args.push(tmpDataPath);
      }

      const child = spawn('python', args, {
        cwd: USEME_CORE_DIR,
        windowsHide: true,
      });

      let stdout = '';
      let stderr = '';
      let settled = false;

      const timeoutId = setTimeout(() => {
        if (!settled) {
          child.kill();
        }
      }, CHILD_TIMEOUT_MS);

      const cleanup = () => {
        clearTimeout(timeoutId);
        if (tmpDataPath && fs.existsSync(tmpDataPath)) {
          try { fs.unlinkSync(tmpDataPath); } catch { /* ignoruj */ }
        }
      };

      child.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
      child.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });

      child.on('error', (err) => {
        if (settled) return;
        settled = true;
        cleanup();
        reject(err);
      });

      child.on('close', (code) => {
        if (settled) return;
        settled = true;
        cleanup();
        if (code === 0) {
          resolve(stdout.trim());
        } else {
          reject(new Error(stderr.trim() || `Proces zakończony kodem ${code}`));
        }
      });
    });
  }

  destroy(): void {
    const channels = [
      'projekty:project:save', 'projekty:project:get-all', 'projekty:project:get', 'projekty:project:delete',
      'projekty:node:save', 'projekty:node:get', 'projekty:node:delete',
      'projekty:edge:save', 'projekty:edge:get', 'projekty:edge:delete',
      'projekty:annotation:save', 'projekty:annotation:get', 'projekty:annotation:delete',
      'supervisor:pipeline:get-all', 'supervisor:pipeline:get', 'supervisor:pipeline:save', 'supervisor:decision:save', 'supervisor:chain:run', 'supervisor:run',
      'chat:session:save', 'chat:session:get-all', 'chat:session:delete', 'chat:active-session:save', 'chat:active-session:get',
      'kosmos:scan', 'kosmos:move', 'kosmos:getProjects', 'kosmos:addProject', 'kosmos:deleteProject', 'kosmos:pickFolder', 'kosmos:readFile',
      'kosmos:sqlite:list-projects', 'kosmos:sqlite:get-graph', 'kosmos:sqlite:import-project',
      'kosmos:sqlite:save-positions', 'kosmos:sqlite:get-positions',
      'kosmos:sqlite:watch-start', 'kosmos:sqlite:watch-stop', 'kosmos:sqlite:delete-project',
    ];

    this.watcher.stopAll();

    for (const channel of channels) {
      this.ipc.removeHandler(channel);
    }
  }
}
