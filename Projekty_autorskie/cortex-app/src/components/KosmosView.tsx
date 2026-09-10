// ============================================================================
// KOSMOS — Hierarchiczny graf siłowy (force-graph) zasilany natywną bazą SQLite.
//
// Surowy, wydajny widok: foldery i pliki są węzłami, krawędzie "contains"
// odwzorowują realną hierarchię dysku. Fizykę, rysowanie, zoom i hover
// zapewnia open-source'owa biblioteka force-graph (MIT). W naszym kodzie
// leży jedynie "klej": zapytania SQL (przez IPC), mapowanie na format
// { nodes, links } oraz etykiety przez wbudowane API nodeLabel.
// ============================================================================

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraphModule from 'force-graph';
import MarkdownPreview from '@uiw/react-markdown-preview';
import type {
  KosmosGraphData,
  KosmosFileRow,
  KosmosProjectSummary,
} from '../shared/types/kosmos';
import {
  buildVisibleGraph,
  calcChildFolderDistance,
  dirNodeId,
} from './kosmosGraph';
import type { GraphNode, GraphLink } from './kosmosGraph';

const AI_PROXY_HOST = 'http://localhost:4570';
// @ts-expect-error - d3-force-3d does not have official typescript declarations
import { forceCollide } from 'd3-force-3d';

type LabelMode = 'all' | 'folders' | 'hidden';

// Specjalna wartość selektora: pokazuje wszystkie projekty z bazy na jednym obrazie.
const ALL_PROJECTS_ID = '__all__';

// Minimalny, jawny interfejs instancji force-graph, z którego korzystamy.
// (deklaracje typów force-graph opisują klasę, podczas gdy runtime zwraca
// callable fabrykę kapsule — dlatego trzymamy własny kontrakt).
interface ForceGraphApi {
  graphData(data?: { nodes: GraphNode[]; links: GraphLink[] }): any;
  backgroundColor(color: string): ForceGraphApi;
  width(width: number): ForceGraphApi;
  height(height: number): ForceGraphApi;
  nodeId(id: string): ForceGraphApi;
  nodeRelSize(size: number): ForceGraphApi;
  nodeVal(accessor: (node: GraphNode) => number): ForceGraphApi;
  nodeColor(accessor: (node: GraphNode) => string): ForceGraphApi;
  linkColor(accessor: () => string): ForceGraphApi;
  linkWidth(width: number): ForceGraphApi;
  linkDirectionalParticles(count: number): ForceGraphApi;
  warmupTicks(ticks: number): ForceGraphApi;
  cooldownTicks(ticks: number): ForceGraphApi;
  d3AlphaDecay(decay: number): ForceGraphApi;
  d3VelocityDecay(decay: number): ForceGraphApi;
  d3Force(forceName: string, forceFn?: any): any;
  d3ReheatSimulation?(): ForceGraphApi;
  nodeLabel(accessor: (node: GraphNode) => string): ForceGraphApi;
  onNodeClick(fn: (node: GraphNode) => void): ForceGraphApi;
  onNodeHover(fn: (node: GraphNode | null) => void): ForceGraphApi;
  onNodeDragEnd?(fn: (node: GraphNode) => void): ForceGraphApi;
  onEngineStop?(fn: () => void): ForceGraphApi;
  centerAt(x?: number, y?: number, durationMs?: number): any;
  zoom(scale?: number, durationMs?: number): any;
  onZoom?(fn: (transform: any) => void): ForceGraphApi;
  onZoomEnd?(fn: (transform: any) => void): ForceGraphApi;
  _destructor?: () => void;
}

// Deklaracje typów force-graph opisują klasę, ale runtime eksportuje callable
// fabrykę (kapsule). Rzutujemy na jawny kontrakt fabryki.
const forceGraphFactory = ForceGraphModule as unknown as (
  config?: object,
) => (element: HTMLElement) => ForceGraphApi;

// === Konfiguracja kolorów ===================================================
const FOLDER_COLOR = '#FFC799';

const FILE_COLORS: Record<KosmosFileRow['type'], string> = {
  kod: '#60a5fa',
  markdown: '#c4b5fd',
  json: '#fbbf24',
  txt: '#34d399',
  inny: '#a1a1aa',
};

const NODE_REL_SIZE = 4;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Wielkość węzła: foldery większe, gdy zawierają więcej plików.
function nodeVal(node: GraphNode): number {
  if (node.kind !== 'folder') return 1;
  return Math.max(1.4, Math.sqrt(node.fileCount) + 1);
}

interface KosmosViewProps {
  onBack: () => void;
}

// === Pamięć lokalna (localStorage) — synchroniczna, natychmiastowa i odporna na awarie ===
const getCollapsedStorageKey = (projectId: string) => `cortex_kosmos_${projectId}_collapsed`;
const getPositionsStorageKey = (projectId: string) => `cortex_kosmos_${projectId}_positions`;
const PHYSICS_STORAGE_KEY = 'cortex_kosmos_physics_enabled';

function loadSavedCollapsed(projectId: string): Set<string> {
  try {
    const raw = localStorage.getItem(getCollapsedStorageKey(projectId));
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        return new Set(arr);
      }
    }
  } catch (err) {
    console.error('[KosmosView] Błąd odczytu collapsed z localStorage:', err);
  }
  return new Set();
}

function saveCollapsed(projectId: string, collapsed: Set<string>): void {
  try {
    localStorage.setItem(getCollapsedStorageKey(projectId), JSON.stringify(Array.from(collapsed)));
  } catch (err) {
    console.error('[KosmosView] Błąd zapisu collapsed do localStorage:', err);
  }
}

function loadSavedPositions(projectId: string): Map<string, { x: number; y: number; vx?: number; vy?: number }> {
  const map = new Map<string, { x: number; y: number; vx?: number; vy?: number }>();
  try {
    const raw = localStorage.getItem(getPositionsStorageKey(projectId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        for (const [key, val] of Object.entries(parsed)) {
          const pos = val as any;
          if (typeof pos?.x === 'number' && typeof pos?.y === 'number' && !isNaN(pos.x) && !isNaN(pos.y)) {
            map.set(key, { x: pos.x, y: pos.y, vx: 0, vy: 0 });
          }
        }
      }
    }
  } catch (err) {
    console.error('[KosmosView] Błąd odczytu positions z localStorage:', err);
  }
  return map;
}

function savePositionsToStorage(projectId: string, positions: Record<string, { x: number; y: number }>): void {
  try {
    localStorage.setItem(getPositionsStorageKey(projectId), JSON.stringify(positions));
  } catch (err) {
    console.error('[KosmosView] Błąd zapisu positions do localStorage:', err);
  }
}

// ============================================================================
// Komponent
// ============================================================================
export function KosmosView({ onBack }: KosmosViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fgRef = useRef<ForceGraphApi | null>(null);

  const [projects, setProjects] = useState<KosmosProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<KosmosGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [labelMode, setLabelMode] = useState<LabelMode>('all');
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set());
  const [physicsEnabled, setPhysicsEnabled] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(PHYSICS_STORAGE_KEY);
      if (saved !== null) return saved === '1';
    } catch {}
    return true;
  });

  // Podgląd pliku (boczny drawer)
  const [previewFile, setPreviewFile] = useState<KosmosFileRow | null>(null);
  const [previewContent, setPreviewContent] = useState<string>('');
  const [previewLoading, setPreviewLoading] = useState(false);

  // Stan proxy AI (DeepSeek) — realny test połączenia, nie martwa etykieta.
  const [aiStatus, setAiStatus] = useState<'sprawdzanie' | 'online' | 'offline'>('sprawdzanie');

  const checkAiProxy = useCallback(async () => {
    setAiStatus('sprawdzanie');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    try {
      // Każda odpowiedź HTTP (nawet błąd 4xx/5xx) oznacza, że serwer proxy żyje.
      await fetch(`${AI_PROXY_HOST}/v1/models`, { method: 'GET', signal: controller.signal });
      setAiStatus('online');
    } catch {
      setAiStatus('offline');
    } finally {
      clearTimeout(timer);
    }
  }, []);

  useEffect(() => {
    checkAiProxy();
    const interval = setInterval(checkAiProxy, 30000);
    return () => clearInterval(interval);
  }, [checkAiProxy]);

  // Refs trzymające najnowszy stan dla callbacków rejestrowanych jednorazowo
  // (force-graph), aby uniknąć stale-closure.
  const labelModeRef = useRef<LabelMode>(labelMode);
  const physicsEnabledRef = useRef(physicsEnabled);
  const graphDataRef = useRef<KosmosGraphData | null>(null);
  const loadGraphSeqRef = useRef(0);
  const previewSeqRef = useRef(0);
  const selectedProjectIdRef = useRef<string | null>(null);
  // Pamięć przestrzenna węzłów — zapobiega resetowaniu współrzędnych przy zwiń/rozwiń
  const nodePositionsRef = useRef<Map<string, { x: number; y: number; vx?: number; vy?: number }>>(new Map());
  // Flaga pierwszego renderu projektu (dla wycentrowania kamery)
  const isFirstProjectRenderRef = useRef<boolean>(true);
  // ID folderu właśnie rozwiniętego (dla lokalnej fizyki przy wyłączonej fizyce globalnej)
  const recentlyExpandedFolderIdRef = useRef<string | null>(null);
  // Debounce zapisu pozycji do SQLite
  const savePositionsTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  // Liczba widocznych podfolderów dla każdego rodzica — do dynamicznego skalowania promienia
  const childFolderCountsRef = useRef<Map<string, number>>(new Map());
  // Mapowania relacji rodzic-dziecko dla deterministycznych więzów stożka i blokad linii
  const fileParentMapRef = useRef<Map<string, string>>(new Map());
  const folderParentMapRef = useRef<Map<string, string>>(new Map());
  // Indywidualne docelowe długości krawędzi (zgodne z układem geometrycznym)
  const linkDistancesRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    labelModeRef.current = labelMode;
  }, [labelMode]);

  useEffect(() => {
    physicsEnabledRef.current = physicsEnabled;
  }, [physicsEnabled]);

  useEffect(() => {
    graphDataRef.current = graphData;
  }, [graphData]);

  useEffect(() => {
    selectedProjectIdRef.current = selectedProjectId;
  }, [selectedProjectId]);

  // === Zapis współrzędnych węzłów do pamięci i SQLite ========================
  const saveCurrentPositions = useCallback((immediate = false) => {
    if (savePositionsTimeoutRef.current) {
      clearTimeout(savePositionsTimeoutRef.current);
      savePositionsTimeoutRef.current = null;
    }

    const doSave = () => {
      const projectId = selectedProjectIdRef.current;
      if (!projectId) return;

      const fg = fgRef.current;
      const currentGraph = fg?.graphData?.() as { nodes?: GraphNode[] } | undefined;
      const currentLivingNodes = (Array.isArray(currentGraph?.nodes) ? currentGraph.nodes : []) as GraphNode[];

      for (const cn of currentLivingNodes) {
        if (typeof cn.x === 'number' && typeof cn.y === 'number' && !isNaN(cn.x) && !isNaN(cn.y)) {
          nodePositionsRef.current.set(cn.id, {
            x: cn.x,
            y: cn.y,
            vx: cn.vx,
            vy: cn.vy,
          });
        }
      }

      const positions: Record<string, { x: number; y: number }> = {};
      nodePositionsRef.current.forEach((val, key) => {
        if (typeof val.x === 'number' && typeof val.y === 'number' && !isNaN(val.x) && !isNaN(val.y)) {
          positions[key] = { x: val.x, y: val.y };
        }
      });

      if (Object.keys(positions).length > 0) {
        // 1. Natychmiastowy, synchroniczny zapis do localStorage
        savePositionsToStorage(projectId, positions);

        // 2. Kopia zapasowa w bazie SQLite — tylko dla realnych projektów,
        //    nigdy dla widoku zbiorczego (__all__), by nie zaśmiecać tabeli.
        if (projectId !== ALL_PROJECTS_ID && window.cortexBridge?.kosmosSavePositions) {
          window.cortexBridge.kosmosSavePositions({ projectId, positions }).catch((err) => {
            console.error('[KosmosView] Błąd zapisu pozycji do bazy SQLite:', err);
          });
        }
      }
    };

    if (immediate) {
      doSave();
    } else {
      savePositionsTimeoutRef.current = setTimeout(() => {
        doSave();
      }, 300);
    }
  }, []);

  // Czyszczenie timera i natychmiastowy flush pozycji przed zamknięciem/odświeżeniem okna lub odmontowaniem
  useEffect(() => {
    const handleBeforeUnload = () => {
      saveCurrentPositions(true);
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      saveCurrentPositions(true);
    };
  }, [saveCurrentPositions]);

  const togglePhysics = useCallback(() => {
    setPhysicsEnabled((prev) => {
      const next = !prev;
      physicsEnabledRef.current = next;
      try {
        localStorage.setItem(PHYSICS_STORAGE_KEY, next ? '1' : '0');
      } catch {}

      const fg = fgRef.current;
      if (!fg) return next;

      const prevGraph = fg.graphData?.() as { nodes?: GraphNode[]; links?: GraphLink[] } | undefined;
      const nodes = (Array.isArray(prevGraph?.nodes) ? prevGraph.nodes : []) as GraphNode[];

      if (!next) {
        for (const n of nodes) {
          n.fx = n.x;
          n.fy = n.y;
        }
        fg.cooldownTicks?.(0);
        saveCurrentPositions(true);
      } else {
        for (const n of nodes) {
          if (n.depth === 0) {
            n.fx = 0;
            n.fy = 0;
          } else {
            delete n.fx;
            delete n.fy;
          }
        }
        // 300 klatek (~5 sekund) na spokojne ustabilizowanie układu w równowadze
        fg.cooldownTicks?.(300);
        fg.d3ReheatSimulation?.();
      }
      return next;
    });
  }, [saveCurrentPositions]);

  // === Ładowanie listy projektów z bazy SQLite ==============================
  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const list = (await window.cortexBridge?.kosmosListProjects()) ?? [];
      setProjects(list);
      if (list.length > 0) {
        setSelectedProjectId((prev) => prev ?? list[0].id);
      } else {
        setSelectedProjectId(null);
        setGraphData(null);
      }
      setStatusMessage('');
    } catch (err) {
      setStatusMessage(`Błąd ładowania projektów: ${String(err)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  // === Ładowanie grafu dla wybranego projektu ===============================
  const loadGraph = useCallback(async (projectId: string, preserveCollapsed = true, silent = false) => {
    const seq = ++loadGraphSeqRef.current;
    if (!silent) setGraphLoading(true);
    try {
      const [data, savedPositions] = await Promise.all([
        window.cortexBridge?.kosmosGetGraph({ projectId }),
        window.cortexBridge?.kosmosGetPositions?.({ projectId }),
      ]);
      // Ignoruj odpowiedź, jeśli w międzyczasie wybrano inny projekt.
      if (seq !== loadGraphSeqRef.current) return;

      if (savedPositions && typeof savedPositions === 'object') {
        for (const [nodeId, pos] of Object.entries(savedPositions)) {
          if (typeof pos?.x === 'number' && typeof pos?.y === 'number' && !isNaN(pos.x) && !isNaN(pos.y)) {
            if (!nodePositionsRef.current.has(nodeId)) {
              nodePositionsRef.current.set(nodeId, { x: pos.x, y: pos.y, vx: 0, vy: 0 });
            }
          }
        }
      }

      setGraphData(data ?? { folders: [], files: [] });
      if (!preserveCollapsed) {
        setCollapsedFolders(loadSavedCollapsed(projectId));
      }
      if (!silent) {
        setPreviewFile(null);
        setPreviewContent('');
        setPreviewLoading(false);
        setStatusMessage('');
      }
    } catch (err) {
      if (seq !== loadGraphSeqRef.current) return;
      setStatusMessage(`Błąd odczytu grafu: ${String(err)}`);
    } finally {
      if (seq === loadGraphSeqRef.current) {
        setGraphLoading(false);
      }
    }
  }, []);

  // === Ładowanie wszystkich projektów naraz (jeden wspólny obraz) ===========
  const loadAllGraphs = useCallback(async () => {
    setGraphLoading(true);
    try {
      const results = await Promise.all(
        projects.map((p) => window.cortexBridge?.kosmosGetGraph({ projectId: p.id })),
      );
      const folders = results.flatMap((d) => d?.folders ?? []);
      const files = results.flatMap((d) => d?.files ?? []);
      setGraphData({ folders, files });
      setPreviewFile(null);
      setPreviewContent('');
      setPreviewLoading(false);
      setStatusMessage('');
    } catch (err) {
      setStatusMessage(`Błąd odczytu grafów: ${String(err)}`);
    } finally {
      setGraphLoading(false);
    }
  }, [projects]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selectedProjectId === ALL_PROJECTS_ID) {
      // Ten sam mechanizm pamięci co widok pojedynczy: pozycje i zwinięcia
      // ładowane z localStorage pod własnym kluczem widoku zbiorczego.
      nodePositionsRef.current = loadSavedPositions(ALL_PROJECTS_ID);
      setCollapsedFolders(loadSavedCollapsed(ALL_PROJECTS_ID));
      isFirstProjectRenderRef.current = true;
      recentlyExpandedFolderIdRef.current = null;
      loadAllGraphs();
      return;
    }
    if (selectedProjectId) {
      if (selectedProjectIdRef.current && selectedProjectIdRef.current !== selectedProjectId) {
        saveCurrentPositions(true);
      }
      if (savePositionsTimeoutRef.current) {
        clearTimeout(savePositionsTimeoutRef.current);
        savePositionsTimeoutRef.current = null;
      }
      // Natychmiast synchronicznie wczytaj z localStorage — zero opóźnienia i zero wyczyszczenia!
      nodePositionsRef.current = loadSavedPositions(selectedProjectId);
      setCollapsedFolders(loadSavedCollapsed(selectedProjectId));
      isFirstProjectRenderRef.current = true;
      recentlyExpandedFolderIdRef.current = null;
      loadGraph(selectedProjectId, true);
    }
  }, [selectedProjectId, loadGraph, loadAllGraphs, saveCurrentPositions]);

  // === Live-observacja: auto-start przy wyborze projektu ====================
  useEffect(() => {
    if (selectedProjectId) {
      window.cortexBridge?.kosmosWatchStart?.({ projectId: selectedProjectId })?.catch(() => {
        // brak obserwacji nie blokuje widoku
      });
    }
  }, [selectedProjectId]);

  // === Live-observacja: subskrypcja zdarzeń fs.watch ========================
  useEffect(() => {
    const unsubscribe = window.cortexBridge?.kosmosOnWatchEvent?.((event) => {
      // Odśwież graf tylko, gdy zmiana dotyczy aktualnie wybranego projektu.
      // Zachowaj stan zwiniętych folderów i nie migaj overlayem (cichy refresh).
      if (event.projectId === selectedProjectIdRef.current) {
        loadGraph(event.projectId, true, true);
      }
    });
    return () => {
      unsubscribe?.();
    };
  }, [loadGraph]);

  // === Budowa widocznego grafu (expand/collapse) ============================
  const visibleGraph = useMemo(() => {
    if (!graphData) return { nodes: [] as GraphNode[], links: [] as GraphLink[] };
    return buildVisibleGraph(graphData, collapsedFolders);
  }, [graphData, collapsedFolders]);

  // === Render grafu do instancji force-graph ================================
  const renderGraph = useCallback(() => {
    const fg = fgRef.current;
    const container = containerRef.current;
    if (!fg || !container) return;

    // 1. Zapisz bieżące pozycje węzłów żyjących w silniku (pamięć przestrzenna)
    const prevGraph = fg.graphData?.() as { nodes?: GraphNode[]; links?: GraphLink[] } | undefined;
    const currentLivingNodes = (Array.isArray(prevGraph?.nodes) ? prevGraph.nodes : []) as GraphNode[];
    for (const cn of currentLivingNodes) {
      if (cn.x !== undefined && cn.y !== undefined) {
        nodePositionsRef.current.set(cn.id, {
          x: cn.x,
          y: cn.y,
          vx: cn.vx,
          vy: cn.vy,
        });
      }
    }

    const isFirstRender = isFirstProjectRenderRef.current;
    if (isFirstRender) {
      isFirstProjectRenderRef.current = false;
    }

    // Przelicz mapowania hierarchii (liczby podfolderów, relacje oraz docelowe odległości krawędzi)
    const childFolderCounts = new Map<string, number>();
    const fileParentMap = new Map<string, string>();
    const folderParentMap = new Map<string, string>();
    const linkDistances = new Map<string, number>();
    const nodeMapInitial = new Map(visibleGraph.nodes.map((n) => [n.id, n]));

    for (const l of visibleGraph.links) {
      const sId = typeof l.source === 'object' ? (l.source as GraphNode).id : l.source;
      const tId = typeof l.target === 'object' ? (l.target as GraphNode).id : l.target;
      const sNode = nodeMapInitial.get(sId);
      const tNode = nodeMapInitial.get(tId);
      if (sNode && tNode && sNode.x !== undefined && tNode.x !== undefined) {
        const d = Math.hypot(tNode.x - sNode.x, (tNode.y ?? 0) - (sNode.y ?? 0));
        linkDistances.set(`${sId}->${tId}`, d);
      }
      if (tId.startsWith('d:')) {
        childFolderCounts.set(sId, (childFolderCounts.get(sId) ?? 0) + 1);
        folderParentMap.set(tId, sId);
      } else if (tId.startsWith('f:')) {
        fileParentMap.set(tId, sId);
      }
    }
    childFolderCountsRef.current = childFolderCounts;
    fileParentMapRef.current = fileParentMap;
    folderParentMapRef.current = folderParentMap;
    linkDistancesRef.current = linkDistances;

    // 2. Zaaplikuj współrzędne: istniejące węzły NIE zmieniają pozycji,
    // a nowo rozwinięte dzieci wyłaniają się z rodzica w swoim sektorze.
    const nodes = visibleGraph.nodes.map((node) => {
      const saved = nodePositionsRef.current.get(node.id);
      if (saved) {
        node.x = saved.x;
        node.y = saved.y;
        node.vx = 0;
        node.vy = 0;
      } else if (!isFirstRender) {
        // Znajdź pozycję żyjącego rodzica dla płynnego wyłonienia się w jego sektorze
        const parentLink = visibleGraph.links.find((l) => {
          const tId = typeof l.target === 'object' ? (l.target as GraphNode).id : l.target;
          return tId === node.id;
        });
        const parentId = parentLink
          ? typeof parentLink.source === 'object'
            ? (parentLink.source as GraphNode).id
            : parentLink.source
          : null;
        const parentPos = parentId ? nodePositionsRef.current.get(parentId) : null;
        if (parentPos) {
          // Kąt w przestrzeni wyznaczony przez buildVisibleGraph (x, y) WZGLĘDEM RODZICA
          const parentGraphNode = visibleGraph.nodes.find((n) => n.id === parentId);
          const relX = (node.x ?? 0) - (parentGraphNode?.x ?? 0);
          const relY = (node.y ?? 0) - (parentGraphNode?.y ?? 0);
          const angle = Math.atan2(relY, relX);
          // Węzły startują blisko rodzica (zbite), skąd łagodnie wypływają bez teleportu
          const startDist = node.kind === 'folder' ? 10 : 5;
          node.x = parentPos.x + Math.cos(angle) * startDist;
          node.y = parentPos.y + Math.sin(angle) * startDist;
          node.vx = 0;
          node.vy = 0;
        }
      }

      if (node.depth === 0) {
        // Root zakotwiczony tam, gdzie rozłożył go buildVisibleGraph.
        // W trybie "wszystkie projekty" każdy root dostaje własny sektor na okręgu.
        node.fx = node.x ?? 0;
        node.fy = node.y ?? 0;
      } else if (physicsEnabledRef.current) {
        delete node.fx;
        delete node.fy;
      } else {
        // Fizyka wyłączona:
        const parentId =
          node.kind === 'file'
            ? fileParentMapRef.current.get(node.id)
            : folderParentMapRef.current.get(node.id);

        let isDescendant = false;
        let checkId: string | undefined = parentId;
        while (checkId) {
          if (recentlyExpandedFolderIdRef.current !== null && checkId === recentlyExpandedFolderIdRef.current) {
            isDescendant = true;
            break;
          }
          checkId = folderParentMapRef.current.get(checkId);
        }

        if (isDescendant) {
          // Lokalna fizyka wyłącznie dla potomków właśnie rozwiniętego folderu
          delete node.fx;
          delete node.fy;
        } else {
          // Wszystkie pozostałe węzły w galaktyce są 100% zablokowane
          node.fx = node.x;
          node.fy = node.y;
        }
      }

      return node;
    });

    if (isFirstRender) {
      fg.centerAt?.(0, 0, 0);
      fg.zoom?.(1.0001, 0);
      if (physicsEnabledRef.current) {
        fg.warmupTicks(30);
        fg.cooldownTicks(200);
      } else {
        fg.warmupTicks(0);
        fg.cooldownTicks(0);
      }
    } else {
      fg.warmupTicks(0);
      if (physicsEnabledRef.current) {
        fg.cooldownTicks(150);
      } else if (recentlyExpandedFolderIdRef.current) {
        // Lokalna fizyka dla nowo otwartego folderu: 100 klatek (~1.6s) na płynne wyłonienie się
        fg.cooldownTicks(100);
        fg.d3ReheatSimulation?.();
      } else {
        fg.cooldownTicks(0);
      }
    }

    fg.graphData({ nodes, links: visibleGraph.links });
  }, [visibleGraph]);

  // === Podgląd pliku =========================================================
  // Zdefiniowany przed blokiem inicjalizacji force-graph, a dostępny stamtąd
  // przez ref — unikamy stale-closure (callback `onNodeClick` jest rejestrowany
  // jednorazowo i nie widzi późniejszych wartości `graphData`).
  const handlePreviewFile = useCallback(async (filePath: string) => {
    const file = graphDataRef.current?.files.find((f) => f.path === filePath) ?? null;
    const seq = ++previewSeqRef.current;
    setPreviewFile(file);
    setPreviewLoading(true);
    try {
      const res = await window.cortexBridge?.kosmosReadFile({ filePath });
      if (seq !== previewSeqRef.current) return; // użytkownik kliknął inny plik
      if (res?.success && res.content !== undefined) {
        setPreviewContent(res.content);
      } else if (file?.preview) {
        setPreviewContent(file.preview);
      } else {
        setPreviewContent('Nie udało się odczytać pliku.');
      }
    } catch (err) {
      if (seq !== previewSeqRef.current) return;
      setPreviewContent(file?.preview ?? `Błąd odczytu: ${String(err)}`);
    } finally {
      if (seq === previewSeqRef.current) {
        setPreviewLoading(false);
      }
    }
  }, []);

  const handlePreviewFileRef = useRef(handlePreviewFile);
  useEffect(() => {
    handlePreviewFileRef.current = handlePreviewFile;
  }, [handlePreviewFile]);

  // Inicjalizacja instancji force-graph (raz).
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const fg = forceGraphFactory()(container);
    fgRef.current = fg;

    fg.backgroundColor('rgba(0, 0, 0, 0)')
      .width(container.clientWidth)
      .height(container.clientHeight)
      .nodeId('id')
      .nodeRelSize(NODE_REL_SIZE)
      .nodeVal((n: GraphNode) => nodeVal(n))
      .nodeColor((n: GraphNode) =>
        n.kind === 'folder'
          ? FOLDER_COLOR
          : FILE_COLORS[n.type ?? 'inny'],
      )
      .linkColor(() => 'rgba(255, 255, 255, 0.10)')
      .linkWidth(0.6)
      .linkDirectionalParticles(0)
      .warmupTicks(45)
      .cooldownTicks(300)
      .d3AlphaDecay(0.018)
      .d3VelocityDecay(0.65)
      .nodeLabel((n: GraphNode) => {
        if (labelModeRef.current === 'hidden') return '';
        if (labelModeRef.current === 'folders' && n.kind !== 'folder') return '';
        return n.label;
      })
      .onNodeClick((node: GraphNode) => {
        if (node.kind === 'folder') {
          saveCurrentPositions(true);
          setCollapsedFolders((prev) => {
            const next = new Set(prev);
            const folderId = node.id ?? dirNodeId(node.path);
            if (next.has(node.path)) {
              next.delete(node.path);
              recentlyExpandedFolderIdRef.current = folderId;
            } else {
              next.add(node.path);
              recentlyExpandedFolderIdRef.current = null;
            }
            if (selectedProjectIdRef.current) {
              saveCollapsed(selectedProjectIdRef.current, next);
            }
            return next;
          });
        } else {
          handlePreviewFileRef.current(node.path);
        }
      })
      .onNodeHover((node: GraphNode | null) => {
        container.style.cursor = node ? 'pointer' : 'default';
      })
      .onNodeDragEnd?.((node: GraphNode) => {
        node.fx = node.x;
        node.fy = node.y;
        if (node.x !== undefined && node.y !== undefined) {
          nodePositionsRef.current.set(node.id, {
            x: node.x,
            y: node.y,
            vx: 0,
            vy: 0,
          });
        }
        saveCurrentPositions(true);
      })
      .onEngineStop?.(() => {
        if (!physicsEnabledRef.current) {
          const currentGraph = fg.graphData?.() as { nodes?: GraphNode[] } | undefined;
          const currentNodes = (Array.isArray(currentGraph?.nodes) ? currentGraph.nodes : []) as GraphNode[];
          for (const n of currentNodes) {
            if (n.depth !== 0) {
              n.fx = n.x;
              n.fy = n.y;
            }
          }
          recentlyExpandedFolderIdRef.current = null;
        }
        saveCurrentPositions(false);
      });

    // 1. Wyłącz wbudowaną siłę 'center' (d3ForceCenter) — zapobiega przesuwaniu całego układu
    // przy pojawieniu się lub zniknięciu gałęzi (barycentrum nie ciągnie już reszty węzłów!).
    fg.d3Force?.('center', null);

    // 2. Przełam równość k === lastSetZoom (1.0), by force-graph NIGDY nie auto-skalował kamery
    fg.zoom?.(1.0001, 0);

    // === Stabilizacja fizyki: łagodne, organiczne siły bez wybuchów i szarpania ===
    const chargeForce = fg.d3Force?.('charge') as any;
    if (chargeForce) {
      chargeForce
        .strength((n: GraphNode) => (n.kind === 'folder' ? -35 : -10))
        .distanceMin(14)
        .distanceMax(200);
    }

    const linkForce = fg.d3Force?.('link') as any;
    if (linkForce) {
      linkForce
        .distance((link: any) => {
          const sId = typeof link.source === 'object' ? link.source.id : String(link.source);
          const tId = typeof link.target === 'object' ? link.target.id : String(link.target);
          const savedDist = linkDistancesRef.current.get(`${sId}->${tId}`);
          if (savedDist !== undefined && savedDist > 5) return savedDist;

          const target = link.target;
          const source = link.source;
          const isFolder =
            typeof target === 'object'
              ? target.kind === 'folder'
              : String(target).startsWith('d:');
          const isRootSource =
            typeof source === 'object' ? source.depth === 0 : false;

          // Główne gałęzie roota (np. reddit, youtube) mają długi dystans, by tworzyć osobne wyspy
          if (isRootSource && isFolder) return 130;
          // Podfoldery wewnątrz wyspy: skalowane dynamicznie proporcjonalnie do liczby dzieci i plików!
          if (isFolder) {
            const childCount = childFolderCountsRef.current.get(sId) ?? 0;
            const fileCount = typeof source === 'object' ? source.fileCount ?? 1 : 1;
            return calcChildFolderDistance(childCount, fileCount);
          }
          // Pliki roota vs pliki wewnątrz podfolderu
          return isRootSource ? 28 : 18;
        })
        .strength((link: any) => {
          const isFolder =
            typeof link.target === 'object'
              ? link.target.kind === 'folder'
              : String(link.target).startsWith('d:');
          return isFolder ? 0.35 : 0.65;
        });
    }

    // Twarde odpychanie kolizyjne (gwarantuje przerwę między kropkami ze zrzutu ekranu)
    fg.d3Force?.(
      'collide',
      forceCollide((n: GraphNode) => {
        if (n.kind === 'folder') {
          return 16 + Math.sqrt(n.fileCount || 1) * 1.3;
        }
        // Plik: promień ~5px + stały odstęp 3.5px = 8.5px
        return 8.5;
      }).iterations(2),
    );

    // 2. ODPYCHANIE LINIAMI (Segment-Segment Collision Resolution)
    // Deterministycznie zapobiega przecinaniu się jakichkolwiek kresek w drzewie grafu.
    // Traktuje każdą krawędź jak sprężysty pręt — gdy dwa odcinki zbliżą się do siebie,
    // odpychają się prostopadle do punktów największego zbliżenia.
    fg.d3Force?.('lineRepulsion', () => {
      const closestPoints = (
        p1x: number, p1y: number, p2x: number, p2y: number,
        p3x: number, p3y: number, p4x: number, p4y: number,
      ): [number, number] => {
        const d1x = p2x - p1x;
        const d1y = p2y - p1y;
        const d2x = p4x - p3x;
        const d2y = p4y - p3y;
        const rx = p1x - p3x;
        const ry = p1y - p3y;
        const a = d1x * d1x + d1y * d1y;
        const e = d2x * d2x + d2y * d2y;
        const f = d2x * rx + d2y * ry;

        if (a <= 1e-6 && e <= 1e-6) return [0, 0];
        if (a <= 1e-6) return [0, Math.max(0, Math.min(1, f / e))];
        const c = d1x * rx + d1y * ry;
        if (e <= 1e-6) return [Math.max(0, Math.min(1, -c / a)), 0];

        const b = d1x * d2x + d1y * d2y;
        const denom = a * e - b * b;

        let s = denom !== 0 ? Math.max(0, Math.min(1, (b * f - c * e) / denom)) : 0;
        let t = (b * s + f) / e;
        if (t < 0) {
          t = 0;
          s = Math.max(0, Math.min(1, -c / a));
        } else if (t > 1) {
          t = 1;
          s = Math.max(0, Math.min(1, (b - c) / a));
        }
        return [s, t];
      };

      const segmentsIntersect = (
        ax: number, ay: number, bx: number, by: number,
        cx: number, cy: number, dx: number, dy: number,
      ): boolean => {
        const ccw = (x1: number, y1: number, x2: number, y2: number, x3: number, y3: number) =>
          (y3 - y1) * (x2 - x1) > (y2 - y1) * (x3 - x1);
        return (
          ccw(ax, ay, cx, cy, dx, dy) !== ccw(bx, by, cx, cy, dx, dy) &&
          ccw(ax, ay, bx, by, cx, cy) !== ccw(ax, ay, bx, by, dx, dy)
        );
      };

      const force = (alpha: number) => {
        const linkF = fg.d3Force?.('link') as any;
        const links: any[] = linkF?.links?.() ?? [];
        if (!links.length) return;

        // Filtrujemy tylko krawędzie między folderami (szkielet konstelacji)
        const folderLinks = links.filter((l) => {
          const s = l.source;
          const t = l.target;
          return s && t && s.kind === 'folder' && t.kind === 'folder';
        });

        const fLen = folderLinks.length;
        const minLineDist = 24;
        const k = alpha * 0.4;

        for (let i = 0; i < fLen; i++) {
          const l1 = folderLinks[i];
          const s1 = l1.source;
          const t1 = l1.target;
          if (s1.x === undefined || t1.x === undefined) continue;

          for (let j = i + 1; j < fLen; j++) {
            const l2 = folderLinks[j];
            const s2 = l2.source;
            const t2 = l2.target;
            if (s2.x === undefined || t2.x === undefined) continue;
            if (s1 === s2 || s1 === t2 || t1 === s2 || t1 === t2) continue;

            const [s, t] = closestPoints(s1.x, s1.y, t1.x, t1.y, s2.x, s2.y, t2.x, t2.y);
            const c1x = s1.x + s * (t1.x - s1.x);
            const c1y = s1.y + s * (t1.y - s1.y);
            const c2x = s2.x + t * (t2.x - s2.x);
            const c2y = s2.y + t * (t2.y - s2.y);

            const dx = c2x - c1x;
            const dy = c2y - c1y;
            const dist = Math.hypot(dx, dy);

            const isIntersect = segmentsIntersect(s1.x, s1.y, t1.x, t1.y, s2.x, s2.y, t2.x, t2.y);

            if (isIntersect || dist < minLineDist) {
              const overlap = isIntersect ? minLineDist : minLineDist - dist;
              let nx = 0;
              let ny = 0;
              if (dist < 0.001) {
                const lineDx = t1.x - s1.x;
                const lineDy = t1.y - s1.y;
                const lLen = Math.hypot(lineDx, lineDy) || 1;
                nx = -lineDy / lLen;
                ny = lineDx / lLen;
              } else {
                nx = dx / dist;
                ny = dy / dist;
              }

              const pushX = nx * overlap * k;
              const pushY = ny * overlap * k;

              if (s1.depth > 0) {
                s1.vx = (s1.vx ?? 0) - pushX * (1 - s);
                s1.vy = (s1.vy ?? 0) - pushY * (1 - s);
              }
              t1.vx = (t1.vx ?? 0) - pushX * s;
              t1.vy = (t1.vy ?? 0) - pushY * s;

              if (s2.depth > 0) {
                s2.vx = (s2.vx ?? 0) + pushX * (1 - t);
                s2.vy = (s2.vy ?? 0) + pushY * (1 - t);
              }
              t2.vx = (t2.vx ?? 0) + pushX * t;
              t2.vy = (t2.vy ?? 0) + pushY * t;
            }
          }
        }
      };
      return force;
    });

    // 3. WACHLARZ KĄTOWY (rozpychanie kątowe gałęzi na wspólnym rodzicu)
    fg.d3Force?.('angularFan', () => {
      let nodes: GraphNode[] = [];
      const force = (alpha: number) => {
        const linkF = fg.d3Force?.('link') as any;
        const links: any[] = linkF?.links?.() ?? [];
        if (!links.length) return;

        const childrenByParent = new Map<string, GraphNode[]>();
        for (const l of links) {
          const s = l.source;
          const t = l.target;
          if (s && t && s.kind === 'folder' && t.kind === 'folder') {
            const list = childrenByParent.get(s.id) ?? [];
            list.push(t);
            childrenByParent.set(s.id, list);
          }
        }

        const k = alpha * 0.4;
        const minAngle = 0.45; // ~26 stopni minimalnego rozwarcia gałęzi

        childrenByParent.forEach((children, pId) => {
          if (children.length < 2) return;
          const parent = nodes.find((n) => n.id === pId);
          if (!parent) return;
          const px = parent.x ?? 0;
          const py = parent.y ?? 0;

          const angles = children.map((c) => ({
            node: c,
            angle: Math.atan2((c.y ?? 0) - py, (c.x ?? 0) - px),
          }));
          angles.sort((a, b) => a.angle - b.angle);

          for (let i = 0; i < angles.length; i++) {
            const nextIdx = (i + 1) % angles.length;
            let diff = angles[nextIdx].angle - angles[i].angle;
            if (diff < 0) diff += 2 * Math.PI;

            if (diff < minAngle && diff > 0.001) {
              const push = (minAngle - diff) * k;
              const n1 = angles[i].node;
              const n2 = angles[nextIdx].node;

              const a1 = angles[i].angle;
              const a2 = angles[nextIdx].angle;

              n1.vx = (n1.vx ?? 0) + Math.sin(a1) * push * 15;
              n1.vy = (n1.vy ?? 0) - Math.cos(a1) * push * 15;

              n2.vx = (n2.vx ?? 0) - Math.sin(a2) * push * 15;
              n2.vy = (n2.vy ?? 0) + Math.cos(a2) * push * 15;
            }
          }
        });
      };
      force.initialize = (_nodes: GraphNode[]) => {
        nodes = _nodes;
      };
      return force;
    });

    // 4. OGRANICZNIK STOŻKA PRZEDNIEGO (Wedge Constraint)
    // Pliki przypisane do danego folderu mogą poruszać się WYŁĄCZNIE w przednim stożku
    // radialnym (max +/- 37° od osi dziadek -> rodzic). Uniemożliwia to plikom obracanie się
    // na boki w stronę linii sąsiadów ani cofanie się w stronę rodzica.
    fg.d3Force?.('wedgeConstraint', () => {
      let nodes: GraphNode[] = [];
      const force = () => {
        if (!nodes.length) return;
        const nodeMap = new Map<string, GraphNode>();
        for (let i = 0; i < nodes.length; i++) {
          nodeMap.set(nodes[i].id, nodes[i]);
        }

        for (let i = 0; i < nodes.length; i++) {
          const node = nodes[i];
          if (node.x === undefined || node.y === undefined) continue;

          const parentId =
            node.kind === 'file'
              ? fileParentMapRef.current.get(node.id)
              : folderParentMapRef.current.get(node.id);
          if (!parentId) continue;
          const parent = nodeMap.get(parentId);
          if (!parent || parent.x === undefined || parent.y === undefined) continue;
          // Bezpośrednie gałęzie roota (depth 1) nie są ograniczane stożkiem rodzica
          if (parent.depth === 0) continue;

          const grandParentId = folderParentMapRef.current.get(parent.id);
          const grandParent = grandParentId ? nodeMap.get(grandParentId) : undefined;
          const gX = grandParent?.x ?? 0;
          const gY = grandParent?.y ?? 0;

          // Wektor od dziadka do rodzica = oś radialna w przód
          const outDx = parent.x - gX;
          const outDy = parent.y - gY;
          const outAngle = Math.atan2(outDy, outDx);

          // Wektor od rodzica do potomka
          const fDx = node.x - parent.x;
          const fDy = node.y - parent.y;
          const fDist = Math.hypot(fDx, fDy) || 0.001;
          const fAngle = Math.atan2(fDy, fDx);

          let delta = fAngle - outAngle;
          while (delta > Math.PI) delta -= 2 * Math.PI;
          while (delta < -Math.PI) delta += 2 * Math.PI;

          // Pliki: max 37° (~0.65 rad). Podfoldery: max 40° (~0.70 rad)
          const maxDelta = node.kind === 'file' ? 0.65 : 0.70;

          if (Math.abs(delta) > maxDelta) {
            const clampedDelta = Math.sign(delta) * maxDelta;
            const targetAngle = outAngle + clampedDelta;
            const targetDist = node.kind === 'file' ? Math.max(12, Math.min(45, fDist)) : fDist;
            node.x = parent.x + Math.cos(targetAngle) * targetDist;
            node.y = parent.y + Math.sin(targetAngle) * targetDist;
            node.vx = 0;
            node.vy = 0;
          }
        }
      };
      force.initialize = (_nodes: GraphNode[]) => {
        nodes = _nodes;
      };
      return force;
    });

    // 5. TWARDA BLOKADA PRZEKRACZANIA LINII I KOLIZJI (Deterministic Line Clearance)
    // Deterministycznie gwarantuje, że żaden plik nie przekroczy linii sąsiednich folderów.
    // Zachowuje niezmiennik półpłaszczyzny: plik musi ZAWSZE pozostać po tej samej stronie
    // linii, co jego folder-rodzic. Jeśli plik przekroczy linię, jest natychmiast rzutowany
    // z powrotem na dozwoloną stronę rodzica.
    fg.d3Force?.('hardLineClearance', () => {
      let nodes: GraphNode[] = [];
      const force = () => {
        const linkF = fg.d3Force?.('link') as any;
        const links: any[] = linkF?.links?.() ?? [];
        if (!links.length || !nodes.length) return;

        const nodeMap = new Map<string, GraphNode>();
        for (let i = 0; i < nodes.length; i++) {
          nodeMap.set(nodes[i].id, nodes[i]);
        }

        const nLen = nodes.length;
        const lLen = links.length;
        const minClearance = 16;

        for (let j = 0; j < lLen; j++) {
          const link = links[j];
          const s = link.source;
          const t = link.target;
          if (!s || !t || s.x === undefined || t.x === undefined) continue;

          const sId = typeof s === 'object' ? s.id : String(s);
          const tId = typeof t === 'object' ? t.id : String(t);

          // Interesują nas linie między folderami (szkielet drzewa)
          const isFolderLine =
            (typeof s === 'object' ? s.kind === 'folder' : sId.startsWith('d:')) &&
            (typeof t === 'object' ? t.kind === 'folder' : tId.startsWith('d:'));

          if (!isFolderLine) continue;

          const sx = s.x;
          const sy = s.y;
          const tx = t.x;
          const ty = t.y;

          const vx = tx - sx;
          const vy = ty - sy;
          const vLenSq = vx * vx + vy * vy;
          if (vLenSq < 16) continue;
          const vLen = Math.sqrt(vLenSq);

          for (let i = 0; i < nLen; i++) {
            const node = nodes[i];
            if (node.id === sId || node.id === tId) continue;
            if (node.x === undefined || node.y === undefined) continue;

            const proj = ((node.x - sx) * vx + (node.y - sy) * vy) / vLenSq;

            if (node.kind === 'file') {
              const parentId = fileParentMapRef.current.get(node.id);
              if (!parentId) continue;
              const parent = nodeMap.get(parentId);

              // 1. Linia obca (ani s, ani t nie jest rodzicem pliku)
              if (parentId !== sId && parentId !== tId && parent && parent.x !== undefined && parent.y !== undefined) {
                const parentCross = vx * (parent.y - sy) - vy * (parent.x - sx);
                const allowedSide = Math.sign(parentCross);
                if (allowedSide === 0) continue;

                const clampedProj = Math.max(0, Math.min(1, proj));
                const cx = sx + clampedProj * vx;
                const cy = sy + clampedProj * vy;

                const nodeCross = vx * (node.y - sy) - vy * (node.x - sx);
                const currentSide = Math.sign(nodeCross);

                const nx = (-vy / vLen) * allowedSide;
                const ny = (vx / vLen) * allowedSide;

                const distToLine = Math.hypot(node.x - cx, node.y - cy);

                // Jeżeli plik przeszedł na niedozwoloną stronę LUB podszedł zbyt blisko linii
                if (currentSide !== allowedSide || distToLine < minClearance) {
                  node.x = cx + nx * minClearance;
                  node.y = cy + ny * minClearance;
                  node.vx = 0;
                  node.vy = 0;
                }
              } else if (parentId === tId) {
                // 2. Linia rodzica (s = dziadek, t = rodzic). Plik musi być przed rodzicem (proj >= 1.0)
                if (proj < 0.95) {
                  // Plik cofnął się w stronę dziadka po linii s->t. Wypychamy go przed rodzica
                  node.x = tx + (vx / vLen) * 16;
                  node.y = ty + (vy / vLen) * 16;
                  node.vx = (node.vx ?? 0) + (vx / vLen) * 1.2;
                  node.vy = (node.vy ?? 0) + (vy / vLen) * 1.2;
                }
              }
            } else if (node.kind === 'folder') {
              // Kolizja folderu z obcą linią
              const clampedProj = Math.max(0, Math.min(1, proj));
              const cx = sx + clampedProj * vx;
              const cy = sy + clampedProj * vy;
              const dx = node.x - cx;
              const dy = node.y - cy;
              const distSq = dx * dx + dy * dy;
              const folderClearance = 24;

              if (distSq < folderClearance * folderClearance) {
                const dist = Math.sqrt(distSq) || 0.001;
                const overlap = folderClearance - dist;
                const pushX = dx / dist;
                const pushY = dy / dist;
                node.vx = (node.vx ?? 0) + pushX * Math.min(2.0, overlap * 0.15);
                node.vy = (node.vy ?? 0) + pushY * Math.min(2.0, overlap * 0.15);
              }
            }
          }
        }
      };
      force.initialize = (_nodes: GraphNode[]) => {
        nodes = _nodes;
      };
      return force;
    });

    // 5. OGRANICZNIK PRĘDKOŚCI (eliminuje teleportację i wybuchy)
    fg.d3Force?.('velocityClamp', () => {
      let nodes: GraphNode[] = [];
      const force = () => {
        const maxSpeed = 2.5; // px na klatkę (płynny, spokojny ruch bez skoków)
        for (let i = 0; i < nodes.length; i++) {
          const n = nodes[i];
          const vx = n.vx ?? 0;
          const vy = n.vy ?? 0;
          const speed = Math.hypot(vx, vy);
          if (speed > maxSpeed) {
            const ratio = maxSpeed / speed;
            n.vx = vx * ratio;
            n.vy = vy * ratio;
          }
        }
      };
      force.initialize = (_nodes: GraphNode[]) => {
        nodes = _nodes;
      };
      return force;
    });

    // Odświeżenie wymiarów przy zmianie rozmiaru kontenera/okna (debounce rAF).
    let rafId: number | null = null;
    const applySize = () => {
      rafId = null;
      if (container.clientWidth > 0 && container.clientHeight > 0) {
        fg.width(container.clientWidth).height(container.clientHeight);
      }
    };
    const onResize = () => {
      if (rafId === null) rafId = requestAnimationFrame(applySize);
    };
    window.addEventListener('resize', onResize);

    // Kontener zmienia wymiary też bez resize okna (np. otwarcie drawer).
    // ResizeObserver bywa niedostępny w niektórych środowiskach testowych.
    const resizeObserver =
      typeof ResizeObserver !== 'undefined' ? new ResizeObserver(onResize) : null;
    resizeObserver?.observe(container);

    return () => {
      window.removeEventListener('resize', onResize);
      resizeObserver?.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
      fg._destructor?.();
      fgRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-render grafu przy każdej zmianie widocznych węzłów / etykiet.
  useEffect(() => {
    renderGraph();
  }, [renderGraph]);

  // Zmiana trybu etykiet — ponownie aplikujemy akcesor, aby force-graph
  // przerysował widoczne etykiety (nodeLabel).
  useEffect(() => {
    fgRef.current?.nodeLabel((n: GraphNode) => {
      if (labelModeRef.current === 'hidden') return '';
      if (labelModeRef.current === 'folders' && n.kind !== 'folder') return '';
      return n.label;
    });
  }, [labelMode]);

  // === Usunięcie projektu z bazy SQLite ====================================
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDeleteProject = useCallback(async () => {
    if (!selectedProjectId) return;

    // Dwustopniowe potwierdzenie (bez window.confirm, które w frameless
    // Electron może być zablokowane): pierwszy klik uzbraja, drugi usuwa.
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }

    setConfirmDelete(false);

    // Zmiany w preload/procesie głównym nie są hot-reloadowane — jeśli mostek
    // nie ma tej metody, aplikacja wymaga restartu po przebudowie preload.
    if (!window.cortexBridge?.kosmosDeleteSqliteProject) {
      setStatusMessage('Mostek nieaktualny — zrestartuj aplikację (npm run dev).');
      return;
    }

    setStatusMessage('Usuwam projekt z bazy…');
    try {
      const res = await window.cortexBridge.kosmosDeleteSqliteProject({ projectId: selectedProjectId });
      if (res?.success) {
        localStorage.removeItem(getCollapsedStorageKey(selectedProjectId));
        localStorage.removeItem(getPositionsStorageKey(selectedProjectId));
        setSelectedProjectId(null);
        setGraphData(null);
        setCollapsedFolders(new Set());
        setPreviewFile(null);
        await loadProjects();
        setStatusMessage('Projekt usunięty z bazy SQLite.');
      } else {
        console.error('[KosmosView] delete-project failed:', res?.error);
        setStatusMessage(res?.error ? `Nie udało się usunąć: ${res.error}` : 'Nie udało się usunąć projektu.');
      }
    } catch (err) {
      console.error('[KosmosView] delete-project error:', err);
      setStatusMessage(`Błąd usuwania: ${String(err)}`);
    }
  }, [selectedProjectId, confirmDelete, loadProjects]);

  // Auto-reset potwierdzenia po 3 s, gdy użytkownik nie zdecyduje.
  useEffect(() => {
    if (!confirmDelete) return;
    const id = setTimeout(() => setConfirmDelete(false), 3000);
    return () => clearTimeout(id);
  }, [confirmDelete]);

  // === Dodanie folderu z dysku ===============================================
  const handleAddFolder = useCallback(async () => {
    try {
      const folderPath = await window.cortexBridge?.kosmosPickFolder();
      if (!folderPath) return;
      setStatusMessage(`Skanuję ${folderPath}…`);
      const res = await window.cortexBridge?.kosmosImportProject({ folderPath });
      if (res?.success) {
        await loadProjects();
        if (res.projectId) setSelectedProjectId(res.projectId);
        setStatusMessage('Projekt dodany do bazy SQLite.');
      } else {
        setStatusMessage(res?.error ?? 'Nie udało się dodać projektu.');
      }
    } catch (err) {
      setStatusMessage(`Błąd dodawania: ${String(err)}`);
    }
  }, [loadProjects]);

  const activeProject = projects.find((p) => p.id === selectedProjectId) ?? null;
  const fileCount = graphData?.files.length ?? 0;
  const folderCount = graphData?.folders.length ?? 0;

  // Aktywny tryb etykiet (cykl).
  const cycleLabelMode = () => {
    setLabelMode((prev) => (prev === 'all' ? 'folders' : prev === 'folders' ? 'hidden' : 'all'));
  };

  const isMarkdown = previewFile?.type === 'markdown';
  // Tylko typy tekstowe; 'inny' może być plikiem binarnym.
  const isTextual = previewFile
    ? ['kod', 'json', 'txt'].includes(previewFile.type)
    : false;

  return (
    <div className="fixed inset-0 flex flex-col bg-[#0a0e14] text-zinc-200">
      {/* ======================= Pasek narzędzi ======================= */}
      <header className="flex h-12 shrink-0 items-center gap-4 border-b border-white/[0.06] bg-[#0d1016] px-4">
        <button
          onClick={onBack}
          className="group flex items-center gap-2 text-xs text-zinc-400 transition-colors hover:text-zinc-200"
          aria-label="Powrót do tablicy"
        >
          <span className="text-sm leading-none transition-transform group-hover:-translate-x-0.5">←</span>
          <span>Tablica</span>
        </button>

        <div className="h-4 w-px bg-white/[0.08]" />

        <div className="flex items-baseline gap-2">
          <h1 className="text-sm font-semibold tracking-tight text-zinc-100">Kosmos</h1>
          <span className="text-[11px] text-zinc-500">Graf struktury</span>
        </div>

        <select
          value={selectedProjectId ?? ''}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          className="h-7 rounded-md border border-white/10 bg-[#151a22] px-2.5 text-xs text-zinc-300 outline-none transition-colors hover:border-white/20 focus:border-white/30"
          aria-label="Wybór projektu"
        >
          <option value={ALL_PROJECTS_ID}>Wszystkie projekty</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-1 text-[11px] tabular-nums text-zinc-500">
          <span>{folderCount} folderów</span>
          <span className="text-zinc-700">/</span>
          <span>{fileCount} plików</span>
          {activeProject && (
            <>
              <span className="text-zinc-700">/</span>
              <span className="max-w-[240px] truncate">{activeProject.rootPath}</span>
            </>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={checkAiProxy}
            className={`flex items-center gap-1.5 h-7 rounded-md border px-2.5 text-xs font-medium transition-colors ${
              aiStatus === 'online'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                : aiStatus === 'offline'
                ? 'border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20'
                : 'border-white/10 bg-white/[0.03] text-zinc-400 hover:bg-white/[0.06]'
            }`}
            title="Proxy DeepSeek (localhost:4570) — kliknij, aby sprawdzić ponownie"
          >
            <span
              className={`h-2 w-2 rounded-full ${
                aiStatus === 'online'
                  ? 'bg-emerald-400'
                  : aiStatus === 'offline'
                  ? 'bg-red-400'
                  : 'bg-zinc-400 animate-pulse'
              }`}
            />
            AI: {aiStatus === 'online' ? 'online' : aiStatus === 'offline' ? 'offline' : 'sprawdzanie'}
          </button>
          <button
            onClick={handleAddFolder}
            className="h-7 rounded-md border border-white/10 bg-white/[0.03] px-3 text-xs text-zinc-300 transition-colors hover:border-white/20 hover:bg-white/[0.06] hover:text-zinc-100"
          >
            Dodaj folder
          </button>
          <button
            onClick={handleDeleteProject}
            disabled={!selectedProjectId}
            className={`h-7 rounded-md border px-3 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              confirmDelete
                ? 'border-red-400/50 bg-red-400/15 text-red-200 hover:bg-red-400/25'
                : 'border-white/10 bg-white/[0.03] text-zinc-300 hover:border-red-400/30 hover:bg-red-400/10 hover:text-red-300'
            }`}
            title="Usuwa projekt z bazy Kosmos (pliki na dysku pozostają)"
          >
            {confirmDelete ? 'Potwierdź usunięcie' : 'Usuń'}
          </button>
          <button
            onClick={cycleLabelMode}
            className="h-7 rounded-md border border-white/10 bg-white/[0.03] px-3 text-xs text-zinc-300 transition-colors hover:border-white/20 hover:bg-white/[0.06] hover:text-zinc-100"
            title="Przełącza widoczność etykiet"
          >
            Etykiety: {labelMode === 'all' ? 'wszystkie' : labelMode === 'folders' ? 'foldery' : 'ukryte'}
          </button>
          <button
            onClick={togglePhysics}
            className={`h-7 rounded-md border px-3 text-xs font-medium transition-colors ${
              physicsEnabled
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                : 'border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20'
            }`}
            title="Włącza lub wstrzymuje fizykę grafu"
          >
            Fizyka: {physicsEnabled ? 'aktywna' : 'wstrzymana'}
          </button>
        </div>
      </header>

      {/* ======================= Obszar grafu ======================= */}
      <div
        className="relative flex-1 overflow-hidden"
        role="img"
        aria-label="Graf hierarchii projektu"
      >
        <div ref={containerRef} className="absolute inset-0" />

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="rounded-xl border border-white/10 bg-[#10131a] px-4 py-3 text-sm text-zinc-300">
              Ładowanie bazy SQLite…
            </div>
          </div>
        )}

        {!loading && graphLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20">
            <div className="rounded-lg border border-white/10 bg-[#10131a] px-3 py-2 text-xs text-zinc-400">
              Ładowanie grafu…
            </div>
          </div>
        )}

        {!loading && !graphData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-zinc-500">
            <p className="text-sm">Brak projektów w bazie.</p>
            <button
              onClick={handleAddFolder}
              className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-zinc-200 transition-colors hover:border-[#FFC799]/50 hover:text-[#FFC799]"
            >
              + Dodaj folder z dysku
            </button>
          </div>
        )}

        {!loading && graphData && graphData.folders.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-500">
            <p className="text-sm">Ten projekt nie zawiera plików ani folderów.</p>
          </div>
        )}

        {/* Legenda */}
        {graphData && graphData.folders.length > 0 && (
          <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-3 rounded-lg border border-white/5 bg-black/50 px-3 py-1.5 text-[11px] text-zinc-400 backdrop-blur-sm">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: FOLDER_COLOR }} /> Folder
            </span>
            {Object.entries(FILE_COLORS).map(([type, color]) => (
              <span key={type} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: color }} /> {type}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ======================= Status ======================= */}
      {statusMessage && (
        <div
          role="status"
          aria-live="polite"
          className="absolute bottom-3 right-3 rounded-lg border border-white/10 bg-black/70 px-3 py-1.5 text-xs text-zinc-300 backdrop-blur-sm"
        >
          {statusMessage}
        </div>
      )}

      {/* ======================= Drawer podglądu ======================= */}
      {previewFile && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Podgląd pliku ${previewFile.name}`}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setPreviewFile(null);
          }}
          className="absolute inset-y-0 right-0 z-50 flex w-[480px] max-w-[80vw] flex-col border-l border-white/10 bg-[#0d1015] shadow-2xl"
        >
          <div className="flex h-11 shrink-0 items-center gap-3 border-b border-white/5 px-3">
            <span className="truncate text-sm font-semibold text-zinc-100">
              {previewFile.name}
            </span>
            <span className="ml-auto text-[11px] text-zinc-500">
              {formatBytes(previewFile.size_bytes)} · {previewFile.type}
            </span>
            <button
              onClick={() => setPreviewFile(null)}
              aria-label="Zamknij podgląd"
              className="rounded-md px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-white/5 hover:text-white"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 overflow-auto">
            {previewLoading ? (
              <div className="p-4 text-sm text-zinc-500">Czytanie pliku…</div>
            ) : isMarkdown ? (
              <div className="p-4">
                <MarkdownPreview
                  source={previewContent}
                  wrapperElement={{ 'data-color-mode': 'dark' }}
                  style={{ background: 'transparent', fontSize: 13 }}
                />
              </div>
            ) : isTextual ? (
              <pre className="whitespace-pre-wrap break-words p-4 font-mono text-[12px] leading-relaxed text-zinc-300">
                {previewContent}
              </pre>
            ) : (
              <div className="p-4 text-sm text-zinc-500">Podgląd niedostępny dla tego typu pliku.</div>
            )}
          </div>

          <div className="flex h-9 shrink-0 items-center border-t border-white/5 px-3 text-[11px] text-zinc-500">
            {previewFile.path}
          </div>
        </div>
      )}
    </div>
  );
}