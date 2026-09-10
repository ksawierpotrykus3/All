// ============================================================================
// CORTEX & SUPERVISOR — Preload Bridge
// ============================================================================

import { contextBridge, ipcRenderer } from 'electron';
import type { cortexBridge } from '../shared/types/ipc';

const cortexBridge: cortexBridge = {
  // Okno (frameless — własne przyciski)
  winMinimize: () => ipcRenderer.invoke('window:minimize'),
  winMaximize: () => ipcRenderer.invoke('window:maximize'),
  winClose: () => ipcRenderer.invoke('window:close'),
  winIsMaximized: () => ipcRenderer.invoke('window:is-maximized'),

  // Canvas Projekty
  projSaveProject: (payload) => ipcRenderer.invoke('projekty:project:save', payload),
  projGetProjects: () => ipcRenderer.invoke('projekty:project:get-all'),
  projGetProject: (payload) => ipcRenderer.invoke('projekty:project:get', payload),
  projDeleteProject: (payload) => ipcRenderer.invoke('projekty:project:delete', payload),

  projSaveNode: (payload) => ipcRenderer.invoke('projekty:node:save', payload),
  projGetNodes: (payload) => ipcRenderer.invoke('projekty:node:get', payload),
  projDeleteNode: (payload) => ipcRenderer.invoke('projekty:node:delete', payload),

  projSaveEdge: (payload) => ipcRenderer.invoke('projekty:edge:save', payload),
  projGetEdges: (payload) => ipcRenderer.invoke('projekty:edge:get', payload),
  projDeleteEdge: (payload) => ipcRenderer.invoke('projekty:edge:delete', payload),

  projSaveAnnotation: (payload) => ipcRenderer.invoke('projekty:annotation:save', payload),
  projGetAnnotations: (payload) => ipcRenderer.invoke('projekty:annotation:get', payload),
  projDeleteAnnotation: (payload) => ipcRenderer.invoke('projekty:annotation:delete', payload),

  // Supervisor AI
  supervisorRunChain: (payload) => ipcRenderer.invoke('supervisor:chain:run', payload),
  supervisorRun: (payload) => ipcRenderer.invoke('supervisor:run', payload),
  supervisorGetPipelines: () => ipcRenderer.invoke('supervisor:pipeline:get-all'),
  supervisorGetPipeline: (payload) => ipcRenderer.invoke('supervisor:pipeline:get', payload),
  supervisorSavePipeline: (payload) => ipcRenderer.invoke('supervisor:pipeline:save', payload),
  supervisorSaveDecision: (payload) => ipcRenderer.invoke('supervisor:decision:save', payload),

  // AI Chat
  chatSaveSession: (payload) => ipcRenderer.invoke('chat:session:save', payload),
  chatGetSessions: () => ipcRenderer.invoke('chat:session:get-all'),
  chatDeleteSession: (payload) => ipcRenderer.invoke('chat:session:delete', payload),
  chatSaveActiveSessionId: (payload) => ipcRenderer.invoke('chat:active-session:save', payload),
  chatGetActiveSessionId: () => ipcRenderer.invoke('chat:active-session:get'),

  // Kosmos (baza danych struktury folderów i plików)
  kosmosScan: (payload) => ipcRenderer.invoke('kosmos:scan', payload),
  kosmosMove: (payload) => ipcRenderer.invoke('kosmos:move', payload),
  kosmosGetProjects: () => ipcRenderer.invoke('kosmos:getProjects'),
  kosmosAddProject: (payload) => ipcRenderer.invoke('kosmos:addProject', payload),
  kosmosDeleteProject: (payload) => ipcRenderer.invoke('kosmos:deleteProject', payload),
  kosmosPickFolder: () => ipcRenderer.invoke('kosmos:pickFolder'),
  kosmosReadFile: (payload) => ipcRenderer.invoke('kosmos:readFile', payload),

  // Kosmos SQLite (natywna baza cortex.db)
  kosmosListProjects: () => ipcRenderer.invoke('kosmos:sqlite:list-projects'),
  kosmosGetGraph: (payload) => ipcRenderer.invoke('kosmos:sqlite:get-graph', payload),
  kosmosProjectUsesAi: (payload) => ipcRenderer.invoke('kosmos:sqlite:project-uses-ai', payload),
  kosmosImportProject: (payload) => ipcRenderer.invoke('kosmos:sqlite:import-project', payload),
  kosmosSavePositions: (payload) => ipcRenderer.invoke('kosmos:sqlite:save-positions', payload),
  kosmosGetPositions: (payload) => ipcRenderer.invoke('kosmos:sqlite:get-positions', payload),

  // Kosmos live-observacja (fs.watch)
  kosmosWatchStart: (payload) => ipcRenderer.invoke('kosmos:sqlite:watch-start', payload),
  kosmosWatchStop: (payload) => ipcRenderer.invoke('kosmos:sqlite:watch-stop', payload),
  kosmosDeleteSqliteProject: (payload) => ipcRenderer.invoke('kosmos:sqlite:delete-project', payload),
  kosmosOnWatchEvent: (cb) => {
    const handler = (_event: Electron.IpcRendererEvent, data: import('../shared/types/kosmos').KosmosWatchEvent) => cb(data);
    ipcRenderer.on('kosmos:watch-event', handler);
    return () => ipcRenderer.removeListener('kosmos:watch-event', handler);
  },
};

contextBridge.exposeInMainWorld('cortexBridge', cortexBridge);
