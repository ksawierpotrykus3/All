import { useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { Projekt, ProjektyNode, ProjektyEdge } from '../../types';
import type { MacroEdge, MacroClusterLink } from './types';
import {
  ZOOM_MACRO_THRESHOLD,
  ZOOM_CLUSTER_THRESHOLD,
  PROJECT_CARD_WIDTH,
  PROJECT_CARD_HEIGHT,
  NODE_WIDTH,
  NODE_HEIGHT,
} from './constants';
import { getProjectMacroPosition } from './utils/zoomMath';
import { computeClusterLayouts } from './utils/clusterGeometry';

const ENABLED_KEY = 'cortex_live_tracking_enabled';
const SNAPSHOT_KEY = 'cortex_live_tracking_snapshot';
const INTERVAL_MS = 1000;
const SCHEMA_VERSION = 1;

interface LiveTrackingSources {
  activeProjectIdRef: RefObject<string>;
  offsetRef: RefObject<{ x: number; y: number }>;
  scaleRef: RefObject<number>;
  selectedIdsRef: RefObject<string[]>;
  nodesRef: RefObject<ProjektyNode[]>;
  projectsRef: RefObject<Projekt[]>;
  edgesRef: RefObject<ProjektyEdge[]>;
  macroEdgesRef: RefObject<MacroEdge[]>;
  macroClusterLinksRef: RefObject<MacroClusterLink[]>;
  boardPathRef: RefObject<string[]>;
  viewModeRef: RefObject<'notes' | 'projects'>;
  canvasElRef: RefObject<HTMLDivElement | null>;
}

function nodeW(n: ProjektyNode): number {
  return n.width || NODE_WIDTH;
}

function nodeH(n: ProjektyNode): number {
  return n.height || NODE_HEIGHT;
}

function briefNode(n: ProjektyNode) {
  return {
    id: n.id,
    project_id: n.project_id,
    title: n.title,
    content: n.content,
    label: n.label,
    description: n.description,
    node_type: n.node_type,
    status: n.status,
    parent_id: n.parent_id,
    x: n.x,
    y: n.y,
    width: n.width,
    height: n.height,
  };
}

// Metadane notatki do warstwy `visible` (celowo bez treści).
function noteMeta(n: ProjektyNode) {
  return {
    id: n.id,
    project_id: n.project_id,
    title: n.title,
    label: n.label,
    description: n.description,
    parent_id: n.parent_id,
  };
}

function mapEdge(e: ProjektyEdge) {
  return {
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    label: e.label,
    relation_type: e.relation_type,
    has_arrow: e.has_arrow,
  };
}

function rectVisible(
  x: number,
  y: number,
  w: number,
  h: number,
  offset: { x: number; y: number },
  scale: number,
  vw: number,
  vh: number,
): boolean {
  const sx = offset.x + x * scale;
  const sy = offset.y + y * scale;
  return sx < vw && sy < vh && sx + w * scale > 0 && sy + h * scale > 0;
}

function buildSnapshot(s: LiveTrackingSources) {
  const activeProjectId = s.activeProjectIdRef.current;
  const offset = s.offsetRef.current;
  const scale = s.scaleRef.current;
  const rect = s.canvasElRef.current?.getBoundingClientRect();
  const vw = rect?.width || 0;
  const vh = rect?.height || 0;

  const nodes = s.nodesRef.current;
  const edges = s.edgesRef.current;
  const projects = s.projectsRef.current;
  const viewMode = s.viewModeRef.current;
  const boardPath = s.boardPathRef.current;
  const parentId = boardPath.length > 0 ? boardPath[boardPath.length - 1] : null;

  const active = projects.find((p) => p.id === activeProjectId) || null;
  const clusterDescriptions = active?.cluster_descriptions || {};
  const brackets = active?.brackets || [];

  const isMacro = viewMode === 'projects' || scale < ZOOM_MACRO_THRESHOLD;

  // Dokładnie ten sam zbiór węzłów, który renderuje NotesCanvas dla bieżącej planszy.
  const visibleNodes =
    parentId === null
      ? nodes.filter((n) => n.parent_id == null)
      : nodes.filter((n) => n.id === parentId || n.parent_id === parentId);
  const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));
  const visibleEdges = edges.filter(
    (e) => visibleNodeIds.has(e.source_node_id) && visibleNodeIds.has(e.target_node_id),
  );

  let mode: 'projects' | 'clusters' | 'board';
  if (isMacro) {
    mode = 'projects';
  } else if (parentId !== null) {
    mode = 'board';
  } else {
    mode = scale <= ZOOM_CLUSTER_THRESHOLD ? 'clusters' : 'board';
  }

  const breadcrumb = boardPath.map((id) => {
    const n = nodes.find((x) => x.id === id);
    return n ? { id: n.id, title: n.title } : { id, title: '' };
  });

  // Pełna mapa id -> nazwa/tytuł dla wszystkich węzłów i projektów. Kontekst AI
  // używa jej, by zawsze pokazywać czytelne nazwy zamiast surowych identyfikatorów.
  const titles: Record<string, string> = {};
  for (const n of nodes) titles[n.id] = n.title;
  for (const p of projects) titles[p.id] = p.name;

  // Pełna lista projektów — do selektora obiektów w panelu konfiguracji.
  const allProjects = projects.map((p) => ({
    id: p.id,
    name: p.name,
    notes_count: p.notes_count ?? 0,
  }));

  let visible: Record<string, unknown>[] = [];
  let memory: Record<string, unknown>[] = [];
  let nodeEdges: Record<string, unknown>[] = [];
  let macroEdges: Record<string, unknown>[] = [];
  let macroClusterLinks: Record<string, unknown>[] = [];
  let snapshotBrackets: Record<string, unknown>[] = [];
  let allClusters: Record<string, unknown>[] = [];

  if (mode === 'projects') {
    // Widoczne karty projektów — same metadane.
    visible = projects
      .map((p, i) => {
        const pos = getProjectMacroPosition(p, i, projects.length);
        return {
          type: 'project',
          id: p.id,
          name: p.name,
          notes_count: p.notes_count ?? 0,
          x: pos.x,
          y: pos.y,
        };
      })
      .filter((it) =>
        rectVisible(it.x, it.y, PROJECT_CARD_WIDTH, PROJECT_CARD_HEIGHT, offset, scale, vw, vh),
      )
      .map(({ x, y, ...rest }) => rest);

    // Pamięć: pełna zawartość projektów w kadrze. W pamięci trzymamy wyłącznie
    // notatki aktywnego projektu — dla pozostałych, jawnie, brak danych treści.
    memory = projects
      .map((p, i) => {
        const pos = getProjectMacroPosition(p, i, projects.length);
        return {
          p,
          inView: rectVisible(pos.x, pos.y, PROJECT_CARD_WIDTH, PROJECT_CARD_HEIGHT, offset, scale, vw, vh),
        };
      })
      .filter((it) => it.inView)
      .map(({ p }) => {
        const entry: Record<string, unknown> = {
          id: p.id,
          name: p.name,
          notes_count: p.notes_count ?? 0,
        };
        if (p.id === activeProjectId) {
          entry.nodes = nodes.map(briefNode);
        }
        return entry;
      });

    // Krawędzie w trybie makro: pełne połączenia aktywnego projektu (wszystkie,
    // nie tylko widoczne na ekranie), żeby AI miało strukturę grafu bez względu na zoom.
    nodeEdges = edges
      .filter((e) => e.project_id === activeProjectId)
      .map(mapEdge);
  } else if (mode === 'clusters') {
    const layouts = computeClusterLayouts(visibleNodes, visibleEdges, clusterDescriptions, brackets, 28);
    const clusteredIds = new Set<string>();

    const visibleClusterLayouts = layouts.filter((L) =>
      rectVisible(L.minX, L.minY, L.width, L.height, offset, scale, vw, vh),
    );

    // Pełna lista klastrów — do selektora obiektów (niezależnie od kadru).
    allClusters = layouts.map((L) => {
      const ids = L.cluster.map((n) => n.id);
      return {
        id: L.clusterKey,
        title: L.currentDesc || L.cluster[0]?.title || '',
        description: L.currentDesc || null,
        nodeIds: ids,
        nodeCount: ids.length,
      };
    });

    for (const L of visibleClusterLayouts) {
      L.cluster.forEach((n) => clusteredIds.add(n.id));
      const ids = L.cluster.map((n) => n.id);
      visible.push({
        type: 'cluster',
        id: L.clusterKey,
        title: L.currentDesc || L.cluster[0]?.title || '',
        description: L.currentDesc || null,
        nodeIds: ids,
        nodeCount: ids.length,
      });
    }

    // Pojedyncze notatki spoza klastrów (renderowane jako osobne karty) — metadane.
    const standaloneVisible = visibleNodes.filter((n) => {
      if (clusteredIds.has(n.id)) return false;
      return rectVisible(n.x, n.y, nodeW(n), nodeH(n), offset, scale, vw, vh);
    });
    visible.push(...standaloneVisible.map((n) => ({ type: 'note', ...noteMeta(n) })));

    // Pamięć: pełna treść widocznych klastrów oraz widocznych notatek spoza klastrów.
    memory = [
      ...visibleClusterLayouts.map((L) => ({
        id: L.clusterKey,
        title: L.currentDesc || L.cluster[0]?.title || '',
        nodes: L.cluster.map(briefNode),
      })),
      ...standaloneVisible.map((n) => ({ ...briefNode(n) })),
    ];

    nodeEdges = visibleEdges.map(mapEdge);
  } else {
    // board — notatki na bieżącej planszy (główna przy dużym zoomie lub wnętrze klastra).
    const visibleBoardNotes = visibleNodes.filter((n) =>
      rectVisible(n.x, n.y, nodeW(n), nodeH(n), offset, scale, vw, vh),
    );
    visible = visibleBoardNotes.map((n) => ({ type: 'note', ...noteMeta(n) }));
    memory = visibleBoardNotes.map((n) => briefNode(n));

    nodeEdges = visibleEdges.map(mapEdge);
  }

  // Makro-krawędzie i klamry wypełniamy NIEZALEŻNIE od trybu — dzięki temu kontekst
  // AI zawsze widzi połączenia projektów oraz klamry, gdy tylko są zdefiniowane.
  macroEdges = s.macroEdgesRef.current.map((e) => ({
    id: e.id,
    source: e.source_project_id,
    target: e.target_project_id,
    has_arrow: e.has_arrow,
  }));

  macroClusterLinks = s.macroClusterLinksRef.current.map((l) => ({
    id: l.id,
    source_project_id: l.source_project_id,
    source_kind: l.source_kind,
    source_key: l.source_key,
    source_label: l.source_label,
    target_project_id: l.target_project_id,
    target_kind: l.target_kind,
    target_key: l.target_key,
    target_label: l.target_label,
  }));

  snapshotBrackets = brackets.map((b) => ({
    id: b.id,
    name: b.name,
    node_ids: b.node_ids,
    track: b.track,
    orientation: b.orientation,
  }));

  return {
    schemaVersion: SCHEMA_VERSION,
    ts: Date.now(),
    viewport: { x: offset.x, y: offset.y, scale, width: vw, height: vh },
    view: {
      mode,
      projectId: activeProjectId,
      projectName: active?.name ?? null,
      breadcrumb,
    },
    titles,
    visible,
    memory,
    edges: nodeEdges,
    macroEdges,
    macroClusterLinks,
    brackets: snapshotBrackets,
    selectedIds: s.selectedIdsRef.current,
    allProjects,
    allClusters,
  };
}

/**
 * Live Tracking — cykliczny zapis snapshotu tego, co użytkownik widzi na canvasie.
 * Domyślnie WYŁĄCZONY. Gdy aktywny, co INTERVAL_MS zapisuje kompletny opis widoku
 * (viewport, widoczne obiekty, ich zawartość-pamięć, krawędzie, klamry, selekcję)
 * do localStorage, pod przyszły boczny chat. Kanał jest "niepodpięty" — tylko zapis.
 */
export function useLiveTracking(sources: LiveTrackingSources) {
  const [liveTrackingEnabled, setLiveTrackingEnabled] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem(ENABLED_KEY) === '1';
  });

  const sourcesRef = useRef(sources);
  sourcesRef.current = sources;
  const lastJsonRef = useRef<string | null>(null);

  useEffect(() => {
    if (!liveTrackingEnabled || typeof window === 'undefined') return;

    const interval = window.setInterval(() => {
      let snapshot: unknown;
      try {
        snapshot = buildSnapshot(sourcesRef.current);
      } catch (e) {
        console.error('[LiveTracking] snapshot build failed', e);
        return;
      }

      let json: string;
      try {
        json = JSON.stringify(snapshot);
      } catch (e) {
        console.error('[LiveTracking] snapshot serialize failed', e);
        return;
      }

      // Zapis warunkowy — tylko gdy widok faktycznie się zmienił.
      if (json === lastJsonRef.current) return;
      lastJsonRef.current = json;

      try {
        localStorage.setItem(SNAPSHOT_KEY, json);
      } catch (e) {
        console.error('[LiveTracking] snapshot write failed', e);
      }
    }, INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [liveTrackingEnabled]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(ENABLED_KEY, liveTrackingEnabled ? '1' : '0');
    }
  }, [liveTrackingEnabled]);

  return { liveTrackingEnabled, setLiveTrackingEnabled };
}