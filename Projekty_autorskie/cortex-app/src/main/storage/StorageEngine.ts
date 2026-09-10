// ============================================================================
// CORTEX & SUPERVISOR — StorageEngine (JSON-only)
// Zapis do plików JSON w katalogu data/projekty/ oraz data/pipelines/
// Atomowy zapis: tmp → rename + backup .bak
// ============================================================================

import * as fs from 'fs';
import * as path from 'path';
import { Projekt, ProjektyNode, ProjektyEdge, ProjektyNodeAnnotation } from '../../types';
import type { ChatSession } from '../../shared/types/chat';
import type { KosmosProjectRecord } from '../../shared/types/kosmos';
import type { Lancuch, Krok, KrokStatus, KrokTyp, StatusOgolny, WyzwalaczTyp, DecyzjaPayload } from '../../supervisor/types';

function atomicWriteFileSync(filePath: string, data: string, encoding: BufferEncoding = 'utf8'): void {
  if (fs.existsSync(filePath)) {
    try {
      fs.copyFileSync(filePath, filePath + '.bak');
    } catch {
      // backup failure is non-fatal
    }
  }
  const tmpPath = filePath + '.tmp';
  fs.writeFileSync(tmpPath, data, encoding);
  try {
    fs.renameSync(tmpPath, filePath);
  } catch (err) {
    // Jeśli rename nie powiedzie się (np. plik docelowy zablokowany), zostaw tmp
    console.error(`[StorageEngine] Błąd atomowego zapisu ${filePath}:`, err);
    throw err;
  }
}

function ensureDir(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function readJsonFile<T>(filePath: string): T | null {
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8')) as T;
  } catch (err) {
    console.error(`[StorageEngine] Błąd odczytu JSON z ${filePath}:`, err);
    return null;
  }
}

function readJsonDir<T>(dir: string): T[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter(f => f.endsWith('.json'))
    .map(f => readJsonFile<T>(path.join(dir, f)))
    .filter((x): x is T => x !== null);
}

function deleteFileIfExists(filePath: string): void {
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }
}

// Sanityzacja identyfikatorów używanych w ścieżkach plików.
// Zapobiega path traversal (np. `../` lub separatorom w id).
function sanitizeId(id: string): string {
  const s = String(id);
  if (!s || s === '.' || s === '..' || s.includes('/') || s.includes('\\') || s.includes('\0')) {
    throw new Error(`Invalid id: ${JSON.stringify(id)}`);
  }
  return s;
}

function normalizeStatus(statusRaw?: string): KrokStatus {
  if (!statusRaw) return 'w_kolejce';
  const s = String(statusRaw).toLowerCase();
  if (s === 'wykonano' || s === 'done' || s === 'zrobione' || s === 'completed' || s === 'success') return 'zrobione';
  if (s === 'w_toku' || s === 'in_progress' || s === 'running') return 'w_toku';
  if (s === 'czeka_na_czlowieka' || s === 'czeka_na_ciebie' || s === 'wait' || s === 'waiting' || s === 'pause') return 'czeka_na_ciebie';
  if (s === 'blad' || s === 'error' || s === 'failed') return 'blad';
  return 'w_kolejce';
}

function normalizeType(typeRaw?: string, name?: string): KrokTyp {
  if (typeRaw) {
    const t = String(typeRaw).toLowerCase();
    if (t === 'kod' || t === 'code' || t === 'playwright' || t === 'script' || t === 'exec') return 'kod';
    if (t === 'warunek' || t === 'branch' || t === 'gate' || t === 'if') return 'warunek';
    if (t === 'ai' || t === 'model' || t === 'llm' || t === 'deepseek') return 'ai';
  }
  const n = String(name || '').toLowerCase();
  if (n.includes('playwright') || n.includes('kod') || n.includes('skrypt') || n.includes('fetch') || n.includes('odczyt') || n.includes('zapis')) return 'kod';
  if (n.includes('warunek') || n.includes('if') || n.includes('bramka')) return 'warunek';
  return 'ai';
}

function normalizeStatusOgolny(statusRaw?: string): StatusOgolny {
  if (!statusRaw) return 'w_toku';
  const s = String(statusRaw).toLowerCase();
  if (s === 'zakonczono' || s === 'done' || s === 'completed' || s === 'finished' || s === 'ok' || s === 'success') return 'zakonczono';
  if (s === 'w_toku' || s === 'in_progress' || s === 'running') return 'w_toku';
  if (s === 'oczekuje' || s === 'waiting' || s === 'queued' || s === 'pending') return 'oczekuje';
  if (s === 'blad' || s === 'error' || s === 'failed') return 'blad';
  return 'w_toku';
}

function normalizeWyzwalaczTyp(wyzwalacz?: string): WyzwalaczTyp {
  const w = String(wyzwalacz || '').toLowerCase();
  if (w.includes('harmonogram') || w.includes('cron') || w.includes('cyklicz') || w.includes('zaplanowan')) return 'cron';
  if (w.includes('zdarzenie') || w.includes('event') || w.includes('webhook') || w.includes('plik')) return 'zdarzenie';
  return 'manual';
}

// === StorageEngine =========================================================
export class StorageEngine {
  private _basePath: string;

  get basePath(): string { return this._basePath; }

  constructor(basePath: string) {
    this._basePath = basePath;
  }

  async init(): Promise<void> {
    const dataDir = path.join(this.basePath, 'projekty');
    ensureDir(dataDir);
    ensureDir(path.join(dataDir, 'projects'));
    ensureDir(path.join(dataDir, 'nodes'));
    ensureDir(path.join(dataDir, 'edges'));
    ensureDir(path.join(dataDir, 'annotations'));

    const pipelinesDir = path.join(this.basePath, 'pipelines');
    ensureDir(pipelinesDir);

    const chatDir = path.join(this.basePath, 'chats');
    ensureDir(chatDir);

    console.log('[StorageEngine] JSON storage ready:', this.basePath);
  }

  // =========================================================================
  // Canvas Projekty CRUD
  // =========================================================================

  saveProjekt(proj: Projekt): void {
    const dir = path.join(this.basePath, 'projekty', 'projects');
    ensureDir(dir);
    atomicWriteFileSync(path.join(dir, `${sanitizeId(proj.id)}.json`), JSON.stringify(proj, null, 2));
  }

  getProjects(): Projekt[] {
    const dir = path.join(this.basePath, 'projekty', 'projects');
    return readJsonDir<Projekt>(dir)
      .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));
  }

  getProjekt(id: string): Projekt | null {
    const p = path.join(this.basePath, 'projekty', 'projects', `${sanitizeId(id)}.json`);
    return readJsonFile<Projekt>(p);
  }

  deleteProjekt(id: string): void {
    const safeId = sanitizeId(id);
    const p = path.join(this.basePath, 'projekty', 'projects', `${safeId}.json`);
    deleteFileIfExists(p);
    const nodesDir = path.join(this.basePath, 'projekty', 'nodes');
    const edgesDir = path.join(this.basePath, 'projekty', 'edges');
    const annotationsDir = path.join(this.basePath, 'projekty', 'annotations');

    if (fs.existsSync(nodesDir)) {
      fs.readdirSync(nodesDir)
        .filter(f => f.endsWith('.json'))
        .forEach(f => {
          const node = readJsonFile<ProjektyNode>(path.join(nodesDir, f));
          if (node?.project_id === id) deleteFileIfExists(path.join(nodesDir, f));
        });
    }
    if (fs.existsSync(edgesDir)) {
      fs.readdirSync(edgesDir)
        .filter(f => f.endsWith('.json'))
        .forEach(f => {
          const edge = readJsonFile<ProjektyEdge>(path.join(edgesDir, f));
          if (edge?.project_id === id) deleteFileIfExists(path.join(edgesDir, f));
        });
    }
    if (fs.existsSync(annotationsDir)) {
      fs.readdirSync(annotationsDir)
        .filter(f => f.endsWith('.json'))
        .forEach(f => {
          const ann = readJsonFile<ProjektyNodeAnnotation>(path.join(annotationsDir, f));
          if (ann?.project_id === id) deleteFileIfExists(path.join(annotationsDir, f));
        });
    }
  }

  // --- Nodes ---
  saveProjektyNode(node: ProjektyNode): void {
    const dir = path.join(this.basePath, 'projekty', 'nodes');
    ensureDir(dir);
    atomicWriteFileSync(path.join(dir, `${sanitizeId(node.id)}.json`), JSON.stringify(node, null, 2));
  }

  getProjektyNodes(projectId: string): ProjektyNode[] {
    const dir = path.join(this.basePath, 'projekty', 'nodes');
    return readJsonDir<ProjektyNode>(dir)
      .filter(n => n.project_id === projectId)
      .sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
  }

  deleteProjektyNode(id: string): void {
    const safeId = sanitizeId(id);
    const p = path.join(this.basePath, 'projekty', 'nodes', `${safeId}.json`);
    deleteFileIfExists(p);
    const edgesDir = path.join(this.basePath, 'projekty', 'edges');
    const annotationsDir = path.join(this.basePath, 'projekty', 'annotations');
    if (fs.existsSync(edgesDir)) {
      fs.readdirSync(edgesDir)
        .filter(f => f.endsWith('.json'))
        .forEach(f => {
          const edge = readJsonFile<ProjektyEdge>(path.join(edgesDir, f));
          if (edge && (edge.source_node_id === id || edge.target_node_id === id)) {
            deleteFileIfExists(path.join(edgesDir, f));
          }
        });
    }
    if (fs.existsSync(annotationsDir)) {
      fs.readdirSync(annotationsDir)
        .filter(f => f.endsWith('.json'))
        .forEach(f => {
          const ann = readJsonFile<ProjektyNodeAnnotation>(path.join(annotationsDir, f));
          if (ann?.node_id === id) deleteFileIfExists(path.join(annotationsDir, f));
        });
    }
  }

  // --- Edges ---
  saveProjektyEdge(edge: ProjektyEdge): void {
    const dir = path.join(this.basePath, 'projekty', 'edges');
    ensureDir(dir);
    atomicWriteFileSync(path.join(dir, `${sanitizeId(edge.id)}.json`), JSON.stringify(edge, null, 2));
  }

  getProjektyEdges(projectId: string): ProjektyEdge[] {
    const dir = path.join(this.basePath, 'projekty', 'edges');
    return readJsonDir<ProjektyEdge>(dir)
      .filter(e => e.project_id === projectId);
  }

  deleteProjektyEdge(id: string): void {
    const p = path.join(this.basePath, 'projekty', 'edges', `${sanitizeId(id)}.json`);
    deleteFileIfExists(p);
  }

  // --- Node Annotations ---
  saveProjektyNodeAnnotation(ann: ProjektyNodeAnnotation): void {
    const dir = path.join(this.basePath, 'projekty', 'annotations');
    ensureDir(dir);
    atomicWriteFileSync(path.join(dir, `${sanitizeId(ann.id)}.json`), JSON.stringify(ann, null, 2));
  }

  getProjektyNodeAnnotations(nodeId: string): ProjektyNodeAnnotation[] {
    const dir = path.join(this.basePath, 'projekty', 'annotations');
    return readJsonDir<ProjektyNodeAnnotation>(dir)
      .filter(a => a.node_id === nodeId)
      .sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
  }

  deleteProjektyNodeAnnotation(id: string): void {
    const p = path.join(this.basePath, 'projekty', 'annotations', `${sanitizeId(id)}.json`);
    deleteFileIfExists(p);
  }

  // =========================================================================
  // AI SUPERVISOR — Real Filesystem Data Reader
  // =========================================================================

  private normalizePipelineData(raw: any, fileBasename: string): Lancuch | null {
    if (!raw || typeof raw !== 'object') return null;

    const id = raw.id || fileBasename.replace(/\.json$/i, '');
    const nazwa = raw.nazwa || raw.name || raw.title || id;
    const opis = raw.opis || raw.description || '';
    const silnik = raw.silnik || raw.engine || raw.narzedzie || '';
    const wyzwalacz = raw.wyzwalacz || raw.trigger || '';
    const ostatni_start = raw.ostatni_start || raw.lastRun || '';

    let rawKroki: any[] = [];
    if (Array.isArray(raw.kroki)) {
      rawKroki = raw.kroki;
    } else if (Array.isArray(raw.steps)) {
      rawKroki = raw.steps;
    } else if (Array.isArray(raw)) {
      rawKroki = raw;
    }

    const kroki: Krok[] = rawKroki.map((k, index) => {
      const stepId = k.id !== undefined ? k.id : k.krok_numer !== undefined ? k.krok_numer : index + 1;
      const stepName = k.nazwa || k.krok_nazwa || k.name || `Krok ${index + 1}`;
      const stepStatus = normalizeStatus(k.status);
      const stepType = normalizeType(k.typ || k.type || k.typ_kroku, stepName);
      const stepDesc = k.opis || k.opis_kroku || k.description || '';
      const narzedzie = k.narzedzie || k.tool || k.silnik || '';

      const promptSystem = k.promptSystem || k.prompty?.system || k.systemPrompt || '';
      const promptUser = k.promptUser || k.prompty?.user || k.userPrompt || '';
      const wejscie = k.wejscie || k.input || (promptUser ? (promptSystem ? `System:\n${promptSystem}\n\nUser:\n${promptUser}` : promptUser) : promptSystem);

      const wyjscie = k.wyjscie || k.output || k.odpowiedz || k.odpowiedz_modelu || k.wynik || k.result || '';
      const reasoning = k.reasoning || k.mysli_modelu || k.mysli || '';
      const logi = Array.isArray(k.logi) ? k.logi : Array.isArray(k.logs) ? k.logs : [];

      let pliki = k.pliki || k.files || [];
      if (!Array.isArray(pliki)) pliki = [];

      let tabela = Array.isArray(k.tabela) ? k.tabela : (Array.isArray(k.table) ? k.table : undefined);

      let decyzja = k.decyzja || undefined;
      if (decyzja?.opcje) {
        decyzja = {
          ...decyzja,
          opcje: decyzja.opcje.map((op: any) => ({
            ...op,
            akcja: op.akcja === 'ok' ? 'approve' : op.akcja === 'popraw' ? 'modify' : op.akcja === 'cofnij' ? 'reject' : op.akcja,
          })),
        };
      } else if (!decyzja && k.wymaga_akceptacji) {
        decyzja = {
          pytanie: k.pytanie || 'Czy akceptujesz wynik tego etapu?',
          opcje: [
            { akcja: 'approve', etykieta: '✓ Zatwierdź', styl: 'primary' },
            { akcja: 'modify', etykieta: '✎ Popraw', styl: 'secondary' },
            { akcja: 'reject', etykieta: '✕ Odrzuć', styl: 'danger' }
          ]
        };
      }

      return {
        id: stepId,
        nazwa: stepName,
        typ: stepType,
        status: stepStatus,
        opis: stepDesc,
        narzedzie,
        wymaga_akceptacji: Boolean(k.wymaga_akceptacji || k.decyzja),
        wejscie,
        promptSystem,
        promptUser,
        wyjscie,
        wynik: k.wynik || wyjscie,
        odpowiedz: k.odpowiedz || wyjscie,
        reasoning,
        logi,
        czas_trwania_s: k.czas_trwania_s ?? k.time_s ?? 0,
        pliki,
        plikiWejsciowe: k.plikiWejsciowe || [],
        plikiWyjsciowe: k.plikiWyjsciowe || [],
        tabela,
        decyzja,
        warunek: k.warunek,
        faza: k.faza || k.stage || '',
        szczegoly: Array.isArray(k.szczegoly) ? k.szczegoly : (Array.isArray(k.details) ? k.details : []),
      };
    });

    return {
      id,
      nazwa,
      opis,
      silnik,
      wyzwalacz,
      wyzwalacz_typ: normalizeWyzwalaczTyp(wyzwalacz),
      ostatni_start,
      status_ogolny: normalizeStatusOgolny(raw.status_ogolny),
      kroki,
      uruchom: raw.uruchom,
      created_at: raw.created_at || new Date().toISOString(),
      updated_at: raw.updated_at || new Date().toISOString(),
      parent_id: raw.parent_id || raw.parentId || '',
      parent_step: raw.parent_step || raw.parentStep || '',
    };
  }

  private mergePipelineWithStan(base: Lancuch, stan: Lancuch): Lancuch {
    const stanStepsMap = new Map<string, Krok>();
    for (const k of stan.kroki) {
      stanStepsMap.set(String(k.id), k);
      stanStepsMap.set(k.nazwa.toLowerCase().trim(), k);
    }

    const mergedSteps: Krok[] = base.kroki.map((baseStep) => {
      const live = stanStepsMap.get(String(baseStep.id)) || stanStepsMap.get(baseStep.nazwa.toLowerCase().trim());
      if (live) {
        return {
          ...baseStep,
          status: live.status,
          czas_trwania_s: live.czas_trwania_s || baseStep.czas_trwania_s,
          wejscie: live.wejscie || baseStep.wejscie,
          wyjscie: live.wyjscie || baseStep.wyjscie,
          reasoning: live.reasoning || baseStep.reasoning,
          logi: live.logi && live.logi.length ? live.logi : baseStep.logi,
          decyzja: live.decyzja || baseStep.decyzja,
          faza: live.faza || baseStep.faza,
          szczegoly: live.szczegoly && live.szczegoly.length ? live.szczegoly : baseStep.szczegoly,
        };
      }
      return baseStep;
    });

    // Dodaj ewentualne dynamiczne kroki wygenerowane w czasie biegu, których nie było w szablonie
    const baseNames = new Set(base.kroki.map((k) => k.nazwa.toLowerCase().trim()));
    const baseIds = new Set(base.kroki.map((k) => String(k.id)));
    for (const k of stan.kroki) {
      if (!baseIds.has(String(k.id)) && !baseNames.has(k.nazwa.toLowerCase().trim())) {
        mergedSteps.push(k);
      }
    }

    return {
      ...base,
      status_ogolny: stan.status_ogolny || base.status_ogolny,
      updated_at: stan.updated_at || base.updated_at,
      parent_id: stan.parent_id || base.parent_id,
      parent_step: stan.parent_step || base.parent_step,
      kroki: mergedSteps,
    };
  }

  getPipelines(): Lancuch[] {
    const pipelinesDir = path.join(this.basePath, 'pipelines');
    ensureDir(pipelinesDir);

    const entries = fs.readdirSync(pipelinesDir, { withFileTypes: true });
    const basePipelines = new Map<string, Lancuch>();
    const stanPipelines = new Map<string, Lancuch>();

    for (const entry of entries) {
      if (entry.isFile() && entry.name.endsWith('.json') && !entry.name.includes('decyzja')) {
        const filePath = path.join(pipelinesDir, entry.name);
        const content = readJsonFile<any>(filePath);
        if (content) {
          const normalized = this.normalizePipelineData(content, entry.name);
          if (normalized) {
            basePipelines.set(normalized.id, normalized);
          }
        }
      } else if (entry.isDirectory()) {
        const stanPath = path.join(pipelinesDir, entry.name, 'stan.json');
        if (fs.existsSync(stanPath)) {
          const content = readJsonFile<any>(stanPath);
          if (content) {
            const normalized = this.normalizePipelineData(content, entry.name);
            if (normalized) {
              stanPipelines.set(normalized.id, normalized);
            }
          }
        }
      }
    }

    const allIds = new Set([...basePipelines.keys(), ...stanPipelines.keys()]);
    const byId = new Map<string, Lancuch>();

    for (const id of allIds) {
      const base = basePipelines.get(id);
      const stan = stanPipelines.get(id);
      if (base && stan) {
        byId.set(id, this.mergePipelineWithStan(base, stan));
      } else if (base) {
        byId.set(id, base);
      } else if (stan) {
        byId.set(id, stan);
      }
    }

    // Składanie łańcuchów podrzędnych (np. "Generator oferty") w ich rodzica
    // (np. "Automatyczna Ofertowarka"), aby pokazać jeden spójny przepływ.
    for (const [, child] of byId) {
      if (!child.parent_id || child.parent_id === child.id) continue;
      const parent = byId.get(child.parent_id);
      if (!parent) continue;

      const target = (child.parent_step || '').trim().toLowerCase();
      const insertIdx = target
        ? parent.kroki.findIndex((k) => {
            const name = k.nazwa.trim().toLowerCase();
            const idStr = String(k.id);
            return name.startsWith(target) || target.startsWith(name) || idStr === (child.parent_step || '');
          })
        : -1;

      const parentKroki = [...parent.kroki];
      if (insertIdx >= 0) {
        // Zastąp nadrzędny krok-„opakowanie” realnymi krokami AI z łańcucha.
        parentKroki.splice(insertIdx, 1, ...child.kroki);
      } else {
        parentKroki.push(...child.kroki);
      }
      parent.kroki = parentKroki;
    }

    // Zwróć tylko korzenie (bez parent_id albo z nieistniejącym rodzicem).
    return Array.from(byId.values()).filter(
      (p) => !p.parent_id || !byId.has(p.parent_id),
    );
  }

  getPipeline(id: string): Lancuch | null {
    const safeId = sanitizeId(id);
    const pipelinesDir = path.join(this.basePath, 'pipelines');
    const directPath = path.join(pipelinesDir, `${safeId}.json`);
    const subPath = path.join(pipelinesDir, safeId, 'stan.json');

    const directContent = fs.existsSync(directPath) ? readJsonFile<any>(directPath) : null;
    const subContent = fs.existsSync(subPath) ? readJsonFile<any>(subPath) : null;

    const base = directContent ? this.normalizePipelineData(directContent, `${safeId}.json`) : null;
    const stan = subContent ? this.normalizePipelineData(subContent, safeId) : null;

    if (base && stan) {
      return this.mergePipelineWithStan(base, stan);
    }
    return base || stan || null;
  }

  savePipeline(pipeline: Lancuch): void {
    const safeId = sanitizeId(pipeline.id);
    const pipelinesDir = path.join(this.basePath, 'pipelines');
    ensureDir(pipelinesDir);
    atomicWriteFileSync(path.join(pipelinesDir, `${safeId}.json`), JSON.stringify(pipeline, null, 2));

    const subDir = path.join(pipelinesDir, safeId);
    if (fs.existsSync(subDir)) {
      atomicWriteFileSync(path.join(subDir, 'stan.json'), JSON.stringify(pipeline, null, 2));
    }
  }

  saveDecision(payload: DecyzjaPayload): void {
    const pipelinesDir = path.join(this.basePath, 'pipelines');
    ensureDir(pipelinesDir);

    const decisionRecord = {
      ...payload,
      timestamp: new Date().toISOString(),
    };

    // Kanoniczny plik decyzji: data/pipelines/{id}/decyzja.json
    const subDir = path.join(pipelinesDir, sanitizeId(String(payload.pipelineId)));
    ensureDir(subDir);
    atomicWriteFileSync(path.join(subDir, 'decyzja.json'), JSON.stringify(decisionRecord, null, 2));

    const pipeline = this.getPipeline(String(payload.pipelineId));
    if (!pipeline) return;

    const stepIdx = pipeline.kroki.findIndex(k => String(k.id) === String(payload.stepId));
    if (stepIdx < 0) return;

    if (payload.decision === 'approve') {
      pipeline.kroki[stepIdx].status = 'zrobione';
      if (stepIdx + 1 < pipeline.kroki.length && pipeline.kroki[stepIdx + 1].status === 'w_kolejce') {
        pipeline.kroki[stepIdx + 1].status = 'czeka_na_ciebie';
      }
    } else if (payload.decision === 'reject') {
      // Odrzucenie kończy krok błędem — przestaje „czekać".
      pipeline.kroki[stepIdx].status = 'blad';
      if (pipeline.kroki[stepIdx].decyzja) {
        pipeline.kroki[stepIdx].decyzja = {
          ...pipeline.kroki[stepIdx].decyzja!,
          pytanie: `${pipeline.kroki[stepIdx].decyzja!.pytanie} (odrzucono: ${payload.feedback || 'bez powodu'})`,
        };
      }
    }
    // modify: krok pozostaje „czeka_na_ciebie" — model ma poprawić i ponownie otworzyć bramkę.

    this.savePipeline(pipeline);
  }

  // =========================================================================
  // AI Chat — persystencja sesji czatu
  // =========================================================================

  private getChatDir(): string {
    return path.join(this.basePath, 'chats');
  }

  private getActiveChatPath(): string {
    return path.join(this.basePath, 'chat_active_session.json');
  }

  saveChatSession(session: ChatSession): void {
    const dir = this.getChatDir();
    ensureDir(dir);
    atomicWriteFileSync(path.join(dir, `${sanitizeId(session.id)}.json`), JSON.stringify(session, null, 2));
  }

  getChatSessions(): ChatSession[] {
    const dir = this.getChatDir();
    return readJsonDir<ChatSession>(dir)
      .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  }

  deleteChatSession(id: string): void {
    const p = path.join(this.getChatDir(), `${sanitizeId(id)}.json`);
    deleteFileIfExists(p);
  }

  saveChatActiveSessionId(id: string): void {
    atomicWriteFileSync(this.getActiveChatPath(), JSON.stringify({ id }));
  }

  getChatActiveSessionId(): string | null {
    const p = this.getActiveChatPath();
    const data = readJsonFile<{ id?: string }>(p);
    return data?.id ?? null;
  }

  // =========================================================================
  // Kosmos Database (Deterministyczna hierarchia folderów i plików)
  // =========================================================================
  private getKosmosDbPath(): string {
    return path.join(this.basePath, 'projekty', 'kosmos_db.json');
  }

  saveKosmosDatabase(projects: KosmosProjectRecord[]): void {
    const p = this.getKosmosDbPath();
    ensureDir(path.dirname(p));
    atomicWriteFileSync(p, JSON.stringify(projects, null, 2));
  }

  getKosmosDatabase(): KosmosProjectRecord[] {
    const p = this.getKosmosDbPath();
    const data = readJsonFile<KosmosProjectRecord[]>(p);
    return data ?? [];
  }

  updateKosmosFileMove(sourcePath: string, targetFolder: string, newPath: string): void {
    const projects = this.getKosmosDatabase();
    let modified = false;

    for (const proj of projects) {
      const file = proj.files.find(f => path.resolve(f.path) === path.resolve(sourcePath));
      if (file) {
        const oldFolder = file.folderPath;
        const newRelFolder = path.relative(proj.rootPath, targetFolder).replace(/\\/g, '/');
        const newRelFile = path.relative(proj.rootPath, newPath).replace(/\\/g, '/');

        file.path = newPath;
        file.folderPath = targetFolder;
        file.folderRelative = newRelFolder;
        file.relativePath = newRelFile;

        // Aktualizuj liczniki w folderach
        const oldFolderRec = proj.folders.find(f => path.resolve(f.path) === path.resolve(oldFolder));
        if (oldFolderRec && oldFolderRec.fileCount > 0) oldFolderRec.fileCount -= 1;

        const newFolderRec = proj.folders.find(f => path.resolve(f.path) === path.resolve(targetFolder));
        if (newFolderRec) newFolderRec.fileCount += 1;

        modified = true;
        break;
      }
    }

    if (modified) {
      this.saveKosmosDatabase(projects);
    }
  }

  destroy(): void {
    console.debug('[StorageEngine] Destroyed');
  }
}
