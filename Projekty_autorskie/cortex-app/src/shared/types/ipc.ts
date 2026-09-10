// ============================================================================
// CORTEX & SUPERVISOR — IPC Typed Bridge
// ============================================================================

import type { Projekt, ProjektyNode, ProjektyEdge, ProjektyNodeAnnotation } from '../../types';
import type { ChatSession } from './chat';
import type { Lancuch, DecyzjaPayload } from '../../supervisor/types';
import type { KosmosGraph, KosmosProjectRecord, KosmosGraphData, KosmosProjectSummary, KosmosWatchEvent } from './kosmos';

export interface cortexBridge {
  // Okno (frameless — własne przyciski)
  winMinimize: () => Promise<void>;
  winMaximize: () => Promise<boolean>;
  winClose: () => Promise<void>;
  winIsMaximized: () => Promise<boolean>;

  // Canvas Projekty
  projSaveProject: (payload: { project: Projekt }) => Promise<{ success: boolean }>;
  projGetProjects: () => Promise<Projekt[]>;
  projGetProject: (payload: { id: string }) => Promise<Projekt | null>;
  projDeleteProject: (payload: { id: string }) => Promise<{ success: boolean }>;

  projSaveNode: (payload: { node: ProjektyNode }) => Promise<{ success: boolean }>;
  projGetNodes: (payload: { projectId: string }) => Promise<ProjektyNode[]>;
  projDeleteNode: (payload: { id: string }) => Promise<{ success: boolean }>;

  projSaveEdge: (payload: { edge: ProjektyEdge }) => Promise<{ success: boolean }>;
  projGetEdges: (payload: { projectId: string }) => Promise<ProjektyEdge[]>;
  projDeleteEdge: (payload: { id: string }) => Promise<{ success: boolean }>;

  projSaveAnnotation: (payload: { annotation: ProjektyNodeAnnotation }) => Promise<{ success: boolean }>;
  projGetAnnotations: (payload: { nodeId: string }) => Promise<ProjektyNodeAnnotation[]>;
  projDeleteAnnotation: (payload: { id: string }) => Promise<{ success: boolean }>;

  // Supervisor AI (Real Filesystem data/pipelines)
  supervisorRunChain: (payload: { pipelineId: string; zlecenieDane?: Record<string, unknown> }) => Promise<{ success: boolean; output?: string; error?: string }>;
  supervisorRun: (payload: { pipelineId: string; zlecenieDane?: Record<string, unknown> }) => Promise<{ success: boolean; output?: string; error?: string }>;
  supervisorGetPipelines: () => Promise<Lancuch[]>;
  supervisorGetPipeline: (payload: { id: string }) => Promise<Lancuch | null>;
  supervisorSavePipeline: (payload: { pipeline: Lancuch }) => Promise<{ success: boolean }>;
  supervisorSaveDecision: (payload: DecyzjaPayload) => Promise<{ success: boolean }>;

  // AI Chat
  chatSaveSession: (payload: { session: ChatSession }) => Promise<{ success: boolean }>;
  chatGetSessions: () => Promise<ChatSession[]>;
  chatDeleteSession: (payload: { id: string }) => Promise<{ success: boolean }>;
  chatSaveActiveSessionId: (payload: { id: string }) => Promise<{ success: boolean }>;
  chatGetActiveSessionId: () => Promise<string | null>;

  // Kosmos (baza danych struktury folderów i plików)
  kosmosScan: (payload: { folders: string[] }) => Promise<KosmosGraph>;
  kosmosMove: (payload: { sourcePath: string; targetFolder: string }) => Promise<{ success: boolean; moved?: boolean; newPath?: string; error?: string }>;
  kosmosGetProjects: () => Promise<KosmosProjectRecord[]>;
  kosmosAddProject: (payload: { folderPath: string }) => Promise<{ success: boolean; projects?: KosmosProjectRecord[]; added?: KosmosProjectRecord; error?: string }>;
  kosmosDeleteProject: (payload: { projectId: string }) => Promise<{ success: boolean; projects?: KosmosProjectRecord[]; error?: string }>;
  kosmosPickFolder: () => Promise<string | null>;
  kosmosReadFile: (payload: { filePath: string }) => Promise<{ success: boolean; content?: string; error?: string }>;

  // Kosmos SQLite (natywna baza cortex.db — zapytania bezpośrednie)
  kosmosListProjects: () => Promise<KosmosProjectSummary[]>;
  kosmosGetGraph: (payload: { projectId: string }) => Promise<KosmosGraphData>;
  kosmosProjectUsesAi?: (payload: { projectId: string }) => Promise<{ usesAi: boolean }>;
  kosmosImportProject: (payload: { folderPath: string }) => Promise<{ success: boolean; projectId?: string; error?: string }>;
  kosmosSavePositions: (payload: { projectId: string; positions: Record<string, { x: number; y: number }> }) => Promise<{ success: boolean; error?: string }>;
  kosmosGetPositions: (payload: { projectId: string }) => Promise<Record<string, { x: number; y: number }>>;

  // Kosmos live-observacja (fs.watch w procesie głównym)
  kosmosWatchStart: (payload: { projectId: string }) => Promise<{ success: boolean; error?: string }>;
  kosmosWatchStop: (payload: { projectId: string }) => Promise<{ success: boolean }>;
  kosmosOnWatchEvent: (cb: (event: KosmosWatchEvent) => void) => () => void;
  kosmosDeleteSqliteProject: (payload: { projectId: string }) => Promise<{ success: boolean; error?: string }>;
}
