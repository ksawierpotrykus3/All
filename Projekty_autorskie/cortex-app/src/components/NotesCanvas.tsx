import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { MouseEvent as ReactMouseEvent } from 'react';
import type { ProjektyNode, ProjektyEdge, Projekt, ProjectGroup, ProjektyBracket } from '../types';

// Typy i stałe
export type { ZoomTransformParams, ZoomTransformResult, MacroEdge } from './canvas/types';
import type { MacroEdge, MacroClusterLink, MacroClusterRef, MacroClusterAnchor, MacroClusterNodeKind } from './canvas/types';
import { MacroClusterLinksLayer } from './canvas/components/MacroClusterLinksLayer';
export {
  ZOOM_MACRO_THRESHOLD,
  PROJECT_CARD_WIDTH,
  PROJECT_CARD_HEIGHT,
  NODE_WIDTH,
  NODE_HEADER_HEIGHT,
  NODE_BODY_HEIGHT,
  NODE_HEIGHT,
  PORTAL_NODE_WIDTH,
  PORTAL_NODE_HEIGHT,
} from './canvas/constants';
import {
  ZOOM_MACRO_THRESHOLD,
  ZOOM_CLUSTER_THRESHOLD,
  PROJECT_CARD_WIDTH,
  PROJECT_CARD_HEIGHT,
  NODE_WIDTH,
  NODE_HEIGHT,
  NODE_BODY_HEIGHT,
  NOISE_DATA_URI,
  genId,
} from './canvas/constants';

// Utilsy matematyczne i geometryczne
export { calculateZoomTransform, getProjectMacroPosition } from './canvas/utils/zoomMath';
import { calculateZoomTransform, getProjectMacroPosition } from './canvas/utils/zoomMath';

export {
  centerOf,
  getNodePerimeterPoint,
  getProjectPerimeterPoint,
  getTransitiveConnectedNodes,
  findSpotNear,
} from './canvas/utils/nodePlacement';
import {
  getTransitiveConnectedNodes,
  findSpotNear,
} from './canvas/utils/nodePlacement';
import { teleportAndPackBracketClusters, computeConnectedComponents } from './canvas/utils/clusterGeometry';

// Komponenty cząstkowe
import { CanvasHeader } from './canvas/components/CanvasHeader';
import { CanvasFooter } from './canvas/components/CanvasFooter';
import { ConnectionLinesLayer } from './canvas/components/ConnectionLinesLayer';
import { ConnectedIslandsLayer } from './canvas/components/ConnectedIslandsLayer';
import { BracketsLayer } from './canvas/components/BracketsLayer';
import { CanvasContextMenu } from './canvas/components/CanvasContextMenu';
import { NoteCard } from './canvas/components/NoteCard';
import { PortalCard } from './canvas/components/PortalCard';
import { MacroProjectCard, getDefaultClusterOffset } from './canvas/components/MacroProjectCard';
import { HelpModal } from './canvas/components/HelpModal';
import { CanvasErrorBoundary } from './canvas/components/CanvasErrorBoundary';
import { useLiveTracking } from './canvas/useLiveTracking';

async function saveNode(node: ProjektyNode): Promise<void> {
  try {
    await window.cortexBridge?.projSaveNode?.({ node });
  } catch (err) {
    console.error('[NotesCanvas] saveNode', err);
  }
}

async function saveEdge(edge: ProjektyEdge): Promise<void> {
  try {
    await window.cortexBridge?.projSaveEdge?.({ edge });
  } catch (err) {
    console.error('[NotesCanvas] saveEdge', err);
  }
}

async function deleteEdgeApi(edgeId: string): Promise<void> {
  try {
    await window.cortexBridge?.projDeleteEdge?.({ id: edgeId });
  } catch (err) {
    console.error('[NotesCanvas] deleteEdge', err);
  }
}

export function NotesCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null);

  const [nodes, setNodes] = useState<ProjektyNode[]>([]);
  const [edges, setEdges] = useState<ProjektyEdge[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const panRef = useRef<{ startX: number; startY: number } | null>(null);

  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const dragRef = useRef<{
    id: string;
    startX: number;
    startY: number;
    nx: number;
    ny: number;
    moved: boolean;
    shiftKey?: boolean;
    group?: { id: string; x: number; y: number }[];
  } | null>(null);

  // Zaznaczenie i edycja
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState('');
  const cancelEditRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const autoResizeTextarea = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto';
    el.style.height = `${Math.max(NODE_BODY_HEIGHT, el.scrollHeight)}px`;
  };

  // Tryb łączenia (linking)
  const [linkingMode, setLinkingMode] = useState(false);
  const [linkSourceId, setLinkSourceId] = useState<string | null>(null);
  const [mouseCanvasPos, setMouseCanvasPos] = useState<{ x: number; y: number } | null>(null);

  const [showHelp, setShowHelp] = useState(false);

  

  // Projekty / Tablice
  const [projects, setProjects] = useState<Projekt[]>([]);
  const projectsRef = useRef<Projekt[]>(projects);
  projectsRef.current = projects;

  // Grupy / Foldery Projektów
  const [groups, setGroups] = useState<ProjectGroup[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const raw = localStorage.getItem('cortex_project_groups');
      if (raw) return JSON.parse(raw);
    } catch (e) {
      console.error('[NotesCanvas] Failed to load project groups', e);
    }
    return [];
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('cortex_project_groups', JSON.stringify(groups));
    }
  }, [groups]);

  const [activeProjectId, setActiveProjectId] = useState<string>(() => {
    if (typeof window === 'undefined') return 'default';
    return localStorage.getItem('cortex_active_project_id') || 'default';
  });
  const activeProjectIdRef = useRef<string>(activeProjectId);
  activeProjectIdRef.current = activeProjectId;

  const [isProjectMenuOpen, setIsProjectMenuOpen] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [editingProjectName, setEditingProjectName] = useState('');
  const projectMenuRef = useRef<HTMLDivElement>(null);

  // Widok: Notatki vs Wszystkie Projekty
  const [viewMode, setViewMode] = useState<'notes' | 'projects'>('notes');
  const viewModeRef = useRef<'notes' | 'projects'>('notes');
  viewModeRef.current = viewMode;

  // Tryb stawiania klocka projektu (Placement mode jak w grze)
  const [placementMode, setPlacementMode] = useState(false);
  const placementModeRef = useRef(false);
  placementModeRef.current = placementMode;

  const togglePortalPlacementMode = () => {
    const next = !placementModeRef.current;
    placementModeRef.current = next;
    setPlacementMode(next);
    if (next) {
      setLinking(false, null);
      selectNode(null);
    }
  };

  useEffect(() => {
    if (!isProjectMenuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (projectMenuRef.current && !projectMenuRef.current.contains(e.target as Node)) {
        setIsProjectMenuOpen(false);
        setEditingProjectId(null);
      }
    };
    window.addEventListener('mousedown', handleClickOutside);
    return () => window.removeEventListener('mousedown', handleClickOutside);
  }, [isProjectMenuOpen]);

  // Stały, profesjonalny ciemny motyw Vesper
  const theme: 'dark' = 'dark';

  useEffect(() => {
    document.documentElement.classList.add('dark');
    localStorage.setItem('cortex-theme', 'dark');
  }, []);

  // Menu kontekstowe (np. tworzenie klamry ze zaznaczenia, edycja klamry)
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    type: 'selection' | 'bracket';
    selectedCount?: number;
    targetId?: string;
    bracketName?: string;
  } | null>(null);

  // Modal tworzenia nowej klamry semantycznej
  const [createBracketModal, setCreateBracketModal] = useState<{
    nodeIds: string[];
    orientation: 'horizontal' | 'vertical';
    clusterCount: number;
  } | null>(null);
  const [newBracketInput, setNewBracketInput] = useState('');

  // Modal zmiany nazwy klamry z menu kontekstowego
  const [renameBracketModal, setRenameBracketModal] = useState<{
    id: string;
    name: string;
  } | null>(null);

  // Pod-tablica: ścieżka identyfikatorów węzłów (pusty = tablica główna)
  const [boardPath, setBoardPath] = useState<string[]>([]);
  const boardPathRef = useRef(boardPath);

  const currentBoardParentId = () => (boardPathRef.current.length > 0 ? boardPathRef.current[boardPathRef.current.length - 1] : null);

  const centerViewOn = (nodeId: string) => {
    const node = nodesRef.current.find((n) => n.id === nodeId);
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!node || !rect) return;
    const cx = node.x + (node.width || NODE_WIDTH) / 2;
    const cy = node.y + (node.height || NODE_HEIGHT) / 2;
    const s = scaleRef.current;
    setOffset({
      x: rect.width / 2 - cx * s,
      y: rect.height / 2 - cy * s,
    });
  };

  const ensureNodeVisible = (node: ProjektyNode) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const s = scaleRef.current;
    const curOff = offsetRef.current;
    const pad = 60;

    const screenX = curOff.x + node.x * s;
    const screenY = curOff.y + node.y * s;
    const nw = (node.width || NODE_WIDTH) * s;
    const nh = (node.height || NODE_HEIGHT) * s;

    let newOffX = curOff.x;
    let newOffY = curOff.y;

    if (screenX + nw > rect.width - pad) {
      newOffX = rect.width - pad - (node.x + (node.width || NODE_WIDTH)) * s;
    } else if (screenX < pad) {
      newOffX = pad - node.x * s;
    }

    if (screenY + nh > rect.height - pad) {
      newOffY = rect.height - pad - (node.y + (node.height || NODE_HEIGHT)) * s;
    } else if (screenY < pad) {
      newOffY = pad - node.y * s;
    }

    if (newOffX !== curOff.x || newOffY !== curOff.y) {
      setOffset({ x: newOffX, y: newOffY });
      offsetRef.current = { x: newOffX, y: newOffY };
    }
  };

  const parentId = boardPath.length > 0 ? boardPath[boardPath.length - 1] : null;
  const isMacroView = viewMode === 'projects' || scale < ZOOM_MACRO_THRESHOLD;
  const isClusterView = !isMacroView && scale <= ZOOM_CLUSTER_THRESHOLD;
  const visibleNodes = parentId === null
    ? nodes.filter((n) => n.parent_id == null)
    : nodes.filter((n) => n.id === parentId || n.parent_id === parentId);
  const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));
  const visibleEdges = edges.filter((e) => visibleNodeIds.has(e.source_node_id) && visibleNodeIds.has(e.target_node_id));
  const breadcrumbNodes = boardPath.map((id) => nodes.find((n) => n.id === id)).filter(Boolean) as ProjektyNode[];

  const openSubBoard = (nodeId: string) => {
    const path = boardPathRef.current;
    const idx = path.indexOf(nodeId);
    if (idx >= 0) {
      // Klik w istniejący segment chleba — cofnij do tego poziomu
      const next = path.slice(0, idx + 1);
      boardPathRef.current = next;
      setBoardPath(next);
    } else {
      const next = [...path, nodeId];
      boardPathRef.current = next;
      setBoardPath(next);
    }
    selectNode(null);
    centerViewOn(nodeId);
  };

  const goToBoardLevel = (index: number) => {
    if (index < 0) {
      boardPathRef.current = [];
      setBoardPath([]);
    } else {
      const next = boardPathRef.current.slice(0, index + 1);
      boardPathRef.current = next;
      setBoardPath(next);
    }
    selectNode(null);
  };

  // Marquee (zaznaczanie ramką)
  const [marquee, setMarquee] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const marqueeRef = useRef<{ x1: number; y1: number; x2: number; y2: number; active: boolean } | null>(null);

  // Schowek dla Ctrl+C / Ctrl+V
  const clipboardRef = useRef<ProjektyNode[] | null>(null);

  // Ref do pomiaru wysokości kart
  const cardElRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Referencje do najświeższych wartości dla globalnych listenerów
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const scaleRef = useRef(scale);
  const offsetRef = useRef(offset);
  const selectedNodeIdRef = useRef(selectedNodeId);
  const selectedIdsRef = useRef(selectedIds);
  const editingNodeIdRef = useRef(editingNodeId);
  const editingTextRef = useRef(editingText);
  const linkingModeRef = useRef(linkingMode);
  const linkSourceIdRef = useRef(linkSourceId);
  const macroEdgesRef = useRef<MacroEdge[]>([]);
  const macroClusterLinksRef = useRef<MacroClusterLink[]>([]);

  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);
  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);
  useEffect(() => {
    scaleRef.current = scale;
  }, [scale]);
  useEffect(() => {
    offsetRef.current = offset;
  }, [offset]);
  useEffect(() => {
    selectedNodeIdRef.current = selectedNodeId;
  }, [selectedNodeId]);
  useEffect(() => {
    selectedIdsRef.current = selectedIds;
  }, [selectedIds]);
  useEffect(() => {
    boardPathRef.current = boardPath;
  }, [boardPath]);
  useEffect(() => {
    editingNodeIdRef.current = editingNodeId;
  }, [editingNodeId]);
  useEffect(() => {
    editingTextRef.current = editingText;
  }, [editingText]);
  useEffect(() => {
    linkingModeRef.current = linkingMode;
  }, [linkingMode]);
  useEffect(() => {
    linkSourceIdRef.current = linkSourceId;
  }, [linkSourceId]);

  const { liveTrackingEnabled, setLiveTrackingEnabled } = useLiveTracking({
    activeProjectIdRef,
    offsetRef,
    scaleRef,
    selectedIdsRef,
    nodesRef,
    projectsRef,
    edgesRef,
    macroEdgesRef,
    macroClusterLinksRef,
    boardPathRef,
    viewModeRef,
    canvasElRef: canvasRef,
  });

  

  // Pomiar rzeczywistej wysokości kart (tylko dla poprawnych punktów zaczepienia strzałek)
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;

    const measure = () => {
      let changed = false;
      const next = [...nodesRef.current];
      for (const id of Object.keys(cardElRefs.current)) {
        const el = cardElRefs.current[id];
        if (!el) continue;
        const height = Math.round(el.offsetHeight);
        const idx = next.findIndex((n) => n.id === id);
        if (idx === -1) continue;
        if (next[idx].height !== height) {
          next[idx] = { ...next[idx], height };
          changed = true;
        }
      }
      if (changed) {
        nodesRef.current = next;
        setNodes(next);
      }
    };

    measure();

    const ro = new ResizeObserver(measure);
    for (const el of Object.values(cardElRefs.current)) {
      if (el) ro.observe(el);
    }
    return () => ro.disconnect();
  }, [nodes]);

  // Synchroniczne mutatory dla stanu + refów (zapobiega opóźnieniom w eventach)
  const selectNode = (nodeId: string | null) => {
    selectedNodeIdRef.current = nodeId;
    setSelectedNodeId(nodeId);
    selectedIdsRef.current = nodeId ? [nodeId] : [];
    setSelectedIds(nodeId ? [nodeId] : []);
  };

  // Toggle notatki w zaznaczeniu wielokrotnym (Shift+klik)
  const toggleSelectedId = (nodeId: string) => {
    const cur = selectedIdsRef.current;
    const next = cur.includes(nodeId) ? cur.filter((id) => id !== nodeId) : [...cur, nodeId];
    selectedIdsRef.current = next;
    setSelectedIds(next);
    selectedNodeIdRef.current = next.length === 1 ? next[0] : null;
    setSelectedNodeId(next.length === 1 ? next[0] : null);
  };

  const isSelected = (nodeId: string) => selectedIdsRef.current.includes(nodeId);

  const setLinking = (active: boolean, sourceId: string | null) => {
    linkingModeRef.current = active;
    linkSourceIdRef.current = sourceId;
    setLinkingMode(active);
    setLinkSourceId(sourceId);
  };

  // --- centrowanie widoku na notatkach projektu ---
  const centerOnProjectNotes = useCallback((nodesList: ProjektyNode[]) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const vw = rect ? rect.width : window.innerWidth;
    const vh = rect ? rect.height : window.innerHeight;

    if (!nodesList || nodesList.length === 0) {
      setScale(1.0);
      scaleRef.current = 1.0;
      setOffset({ x: vw / 2, y: vh / 2 });
      offsetRef.current = { x: vw / 2, y: vh / 2 };
      return;
    }

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of nodesList) {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      const right = n.x + (n.width || NODE_WIDTH);
      const bottom = n.y + (n.height || NODE_HEIGHT);
      if (right > maxX) maxX = right;
      if (bottom > maxY) maxY = bottom;
    }

    const bboxWidth = Math.max(1, maxX - minX);
    const bboxHeight = Math.max(1, maxY - minY);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const fitScale = Math.min(1.0, Math.max(0.4, Math.min((vw - 200) / bboxWidth, (vh - 200) / bboxHeight)));

    setScale(fitScale);
    scaleRef.current = fitScale;
    const newOffX = vw / 2 - centerX * fitScale;
    const newOffY = vh / 2 - centerY * fitScale;
    setOffset({ x: newOffX, y: newOffY });
    offsetRef.current = { x: newOffX, y: newOffY };
  }, []);

  // --- teleportacja / centrowanie widoku na wybranym klastrze ---
  const centerOnCluster = useCallback((clusterNodes: ProjektyNode[]) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const vw = rect ? rect.width : window.innerWidth;
    const vh = rect ? rect.height : window.innerHeight;

    if (!clusterNodes || clusterNodes.length === 0) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of clusterNodes) {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      const right = n.x + (n.width || NODE_WIDTH);
      const bottom = n.y + (n.height || NODE_HEIGHT);
      if (right > maxX) maxX = right;
      if (bottom > maxY) maxY = bottom;
    }

    const bboxWidth = Math.max(1, maxX - minX);
    const bboxHeight = Math.max(1, maxY - minY);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const fitScale = Math.min(1.0, Math.max(0.4, Math.min((vw - 260) / bboxWidth, (vh - 260) / bboxHeight)));

    setScale(fitScale);
    scaleRef.current = fitScale;
    const newOffX = vw / 2 - centerX * fitScale;
    const newOffY = vh / 2 - centerY * fitScale;
    setOffset({ x: newOffX, y: newOffY });
    offsetRef.current = { x: newOffX, y: newOffY };

    // Wyróżnienie zaznaczeniem węzłów wybranego klastra
    const clusterIds = clusterNodes.map((n) => n.id);
    setSelectedIds(clusterIds);
    selectedIdsRef.current = clusterIds;
  }, []);

  // --- wczytanie danych projektu ------------------------------------------
  const loadProjectData = useCallback(async (projId: string, autoCenter = true, targetClusterKey?: string) => {
    const b = window.cortexBridge;
    if (!b?.projGetNodes || !b?.projGetEdges) return;
    try {
      const nds = (await b.projGetNodes({ projectId: projId })).map((n) => {
        if (n.title) return n;
        const firstLine = (n.content || '').split('\n').find((l) => l.trim() !== '')?.trim() ?? '';
        return { ...n, title: firstLine };
      });
      const eds = await b.projGetEdges({ projectId: projId });

      setNodes(nds);
      nodesRef.current = nds;
      setEdges(eds);
      edgesRef.current = eds;
      setBoardPath([]);
      boardPathRef.current = [];
      selectNode(null);

      // Synchronizacja opisów klastrów dla wszystkich powiązanych węzłów w klastrach
      const curProj = projectsRef.current.find((p) => p.id === projId);
      let activeDescriptions = curProj?.cluster_descriptions || {};
      if (curProj && nds.length > 0) {
        const allClusters = computeConnectedComponents(nds, eds, activeDescriptions);
        let changed = false;
        const nextDesc = { ...activeDescriptions };
        allClusters.forEach((cl) => {
          const desc = cl.map((n) => activeDescriptions[n.id]).find((d) => d && d.trim());
          if (desc) {
            cl.forEach((n) => {
              if (nextDesc[n.id] !== desc) {
                nextDesc[n.id] = desc;
                changed = true;
              }
            });
          }
        });
        if (changed) {
          activeDescriptions = nextDesc;
          const updatedProj: Projekt = { ...curProj, cluster_descriptions: nextDesc, updated_at: new Date().toISOString() };
          setProjects((prev) => prev.map((p) => (p.id === projId ? updatedProj : p)));
          projectsRef.current = projectsRef.current.map((p) => (p.id === projId ? updatedProj : p));
          void window.cortexBridge?.projSaveProject?.({ project: updatedProj });
        }
      }

      // Teleportacja do wskazanego klastra (jeśli przekazano targetClusterKey)
      if (targetClusterKey && nds.length > 0) {
        const allClusters = computeConnectedComponents(nds, eds, activeDescriptions);
        const targetDesc = activeDescriptions[targetClusterKey]?.trim();
        const targetCluster = allClusters.find((c) =>
          c.some((n) => n.id === targetClusterKey || (targetDesc && activeDescriptions[n.id]?.trim() === targetDesc))
        );
        if (targetCluster && targetCluster.length > 0) {
          centerOnCluster(targetCluster);
          return;
        }
      }

      if (autoCenter) {
        centerOnProjectNotes(nds);
      }
    } catch (err) {
      console.error('[NotesCanvas] loadProjectData failed', err);
    }
  }, [centerOnProjectNotes, centerOnCluster]);

  const handleSwitchProject = async (projId: string, targetClusterKey?: string) => {
    setViewMode('notes');
    viewModeRef.current = 'notes';
    setActiveProjectId(projId);
    activeProjectIdRef.current = projId;
    localStorage.setItem('cortex_active_project_id', projId);
    setIsProjectMenuOpen(false);
    setEditingProjectId(null);
    setSelectedProjectId(null);
    setMacroClusterLinking(false, null);
    await loadProjectData(projId, true, targetClusterKey);
  };

  const handleCreateProject = async (targetGroupId?: string | null) => {
    const b = window.cortexBridge;
    const newId = genId();
    const newName = `Tablica ${projectsRef.current.length + 1}`;
    const initialPos = getProjectMacroPosition(
      { id: newId, name: newName },
      projectsRef.current.length,
      projectsRef.current.length + 1,
    );
    const newProj: Projekt = {
      id: newId,
      name: newName,
      x: initialPos.x,
      y: initialPos.y,
      folder_id: targetGroupId || null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    if (b?.projSaveProject) {
      await b.projSaveProject({ project: newProj });
    }

    const updated = [...projectsRef.current, newProj];
    projectsRef.current = updated;
    setProjects(updated);
    setActiveProjectId(newId);
    activeProjectIdRef.current = newId;
    localStorage.setItem('cortex_active_project_id', newId);
    setEditingProjectId(newId);
    setEditingProjectName(newName);
    await loadProjectData(newId);
  };

  const handleToggleGroupCollapse = (groupId: string) => {
    setGroups((prev) =>
      prev.map((g) => (g.id === groupId ? { ...g, collapsed: !g.collapsed } : g))
    );
  };

  const handleCreateGroup = (name: string) => {
    const newGroup: ProjectGroup = {
      id: 'g_' + genId(),
      name: name.trim(),
      collapsed: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setGroups((prev) => [...prev, newGroup]);
  };

  const handleDeleteGroup = (groupId: string, mode: 'move_to_root' | 'delete_all') => {
    if (mode === 'move_to_root') {
      setProjects((prev) => {
        const updated = prev.map((p) => (p.folder_id === groupId ? { ...p, folder_id: null } : p));
        updated.forEach((p) => {
          if (p.folder_id === null) {
            void window.cortexBridge?.projSaveProject?.({ project: p });
          }
        });
        return updated;
      });
    } else {
      const toDelete = projects.filter((p) => p.folder_id === groupId);
      toDelete.forEach((p) => {
        void window.cortexBridge?.projDeleteProject?.({ id: p.id });
      });
      setProjects((prev) => prev.filter((p) => p.folder_id !== groupId));
    }
    setGroups((prev) => prev.filter((g) => g.id !== groupId));
  };

  const handleMoveProject = (projectId: string, targetGroupId: string | null) => {
    setProjects((prev) => {
      const updated = prev.map((p) => (p.id === projectId ? { ...p, folder_id: targetGroupId } : p));
      const target = updated.find((p) => p.id === projectId);
      if (target) {
        void window.cortexBridge?.projSaveProject?.({ project: target });
      }
      return updated;
    });
  };

  const handleStartRename = (proj: Projekt, e: ReactMouseEvent) => {
    e.stopPropagation();
    setEditingProjectId(proj.id);
    setEditingProjectName(proj.name);
  };

  const handleSaveRename = async (projId: string) => {
    const trimmed = editingProjectName.trim();
    if (!trimmed) {
      setEditingProjectId(null);
      return;
    }
    const b = window.cortexBridge;
    const proj = projects.find((p) => p.id === projId);
    if (!proj) {
      setEditingProjectId(null);
      return;
    }

    const updatedProj: Projekt = {
      ...proj,
      name: trimmed,
      updated_at: new Date().toISOString(),
    };

    if (b?.projSaveProject) {
      await b.projSaveProject({ project: updatedProj });
    }

    setProjects((prev) => prev.map((p) => (p.id === projId ? updatedProj : p)));
    setEditingProjectId(null);
  };

  const handleDeleteProject = async (projId: string, e: ReactMouseEvent) => {
    e.stopPropagation();
    if (projects.length <= 1) {
      return;
    }
    const targetProj = projects.find((p) => p.id === projId);
    const projName = targetProj ? targetProj.name : 'ten projekt';
    if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
      const confirmed = window.confirm(`Czy na pewno chcesz usunąć projekt "${projName}"?`);
      if (!confirmed) return;
    }
    const b = window.cortexBridge;
    if (b?.projDeleteProject) {
      await b.projDeleteProject({ id: projId });
    }

    const remaining = projectsRef.current.filter((p) => p.id !== projId);
    projectsRef.current = remaining;
    setProjects(remaining);

    if (activeProjectId === projId) {
      const nextProj = remaining[0];
      if (nextProj) {
        setActiveProjectId(nextProj.id);
        activeProjectIdRef.current = nextProj.id;
        localStorage.setItem('cortex_active_project_id', nextProj.id);
        await loadProjectData(nextProj.id);
      }
    }
  };

  // --- stan i funkcje widoku makro (Infinite Zoom Continuum & Macro Connections) ---
  const [projectStats, setProjectStats] = useState<Record<string, { count: number; previews: string[] }>>({});
  const [draggingMacroProjId, setDraggingMacroProjId] = useState<string | null>(null);
  const macroDragRef = useRef<{ id: string; startX: number; startY: number; origX: number; origY: number; moved: boolean } | null>(null);

  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const selectedProjectIdRef = useRef<string | null>(null);
  selectedProjectIdRef.current = selectedProjectId;

  const [macroLinkingMode, setMacroLinkingMode] = useState(false);
  const macroLinkingModeRef = useRef(false);
  macroLinkingModeRef.current = macroLinkingMode;

  const [macroLinkSourceId, setMacroLinkSourceId] = useState<string | null>(null);
  const macroLinkSourceIdRef = useRef<string | null>(null);
  macroLinkSourceIdRef.current = macroLinkSourceId;

  const [macroEdges, setMacroEdges] = useState<MacroEdge[]>(() => {
    try {
      const saved = localStorage.getItem('cortex_macro_edges');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    macroEdgesRef.current = macroEdges;
  }, [macroEdges]);

  const setMacroLinking = (mode: boolean, sourceId: string | null) => {
    macroLinkingModeRef.current = mode;
    setMacroLinkingMode(mode);
    macroLinkSourceIdRef.current = sourceId;
    setMacroLinkSourceId(sourceId);
  };

  const connectProjects = (sourceId: string, targetId: string) => {
    if (sourceId === targetId) {
      setMacroLinking(false, null);
      return;
    }
    const exists = macroEdges.some(
      (e) =>
        (e.source_project_id === sourceId && e.target_project_id === targetId) ||
        (e.source_project_id === targetId && e.target_project_id === sourceId)
    );
    if (exists) {
      setMacroLinking(false, null);
      return;
    }
    const newEdge: MacroEdge = {
      id: `me_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      source_project_id: sourceId,
      target_project_id: targetId,
    };
    const updated = [...macroEdges, newEdge];
    setMacroEdges(updated);
    localStorage.setItem('cortex_macro_edges', JSON.stringify(updated));
    setMacroLinking(false, null);
  };

  const deleteMacroEdge = (edgeId: string) => {
    const updated = macroEdges.filter((e) => e.id !== edgeId);
    setMacroEdges(updated);
    localStorage.setItem('cortex_macro_edges', JSON.stringify(updated));
  };

  const toggleMacroEdgeArrow = (edgeId: string) => {
    const updated = macroEdges.map((e) => {
      if (e.id === edgeId) {
        const nextHasArrow = e.has_arrow === false;
        return { ...e, has_arrow: nextHasArrow };
      }
      return e;
    });
    setMacroEdges(updated);
    localStorage.setItem('cortex_macro_edges', JSON.stringify(updated));
  };

  // --- Łączenie klastrów i klamer między projektami (w widoku makro) ---
  // Dokładnie ten sam wzorzec co łączenie notatek w widoku mikro:
  // linkingMode (flaga) + linkSourceId (źródło) + handleNodeLinkingClick (klik).
  const [macroClusterLinks, setMacroClusterLinks] = useState<MacroClusterLink[]>(() => {
    try {
      const saved = localStorage.getItem('cortex_macro_cluster_links');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    macroClusterLinksRef.current = macroClusterLinks;
  }, [macroClusterLinks]);

  const [macroClusterLinkingMode, setMacroClusterLinkingMode] = useState(false);
  const macroClusterLinkingModeRef = useRef(false);
  macroClusterLinkingModeRef.current = macroClusterLinkingMode;

  const [macroSelectedClusterRef, setMacroSelectedClusterRef] = useState<MacroClusterRef | null>(null);
  const macroSelectedClusterRefRef = useRef<MacroClusterRef | null>(null);
  macroSelectedClusterRefRef.current = macroSelectedClusterRef;

  const [selectedMacroClusterLinkId, setSelectedMacroClusterLinkId] = useState<string | null>(null);
  const selectedMacroClusterLinkIdRef = useRef<string | null>(null);
  selectedMacroClusterLinkIdRef.current = selectedMacroClusterLinkId;

  const [macroClusterLinkSource, setMacroClusterLinkSource] = useState<MacroClusterRef | null>(null);
  const macroClusterLinkSourceRef = useRef<MacroClusterRef | null>(null);
  macroClusterLinkSourceRef.current = macroClusterLinkSource;

  const selectMacroCluster = (ref: MacroClusterRef | null) => {
    macroSelectedClusterRefRef.current = ref;
    setMacroSelectedClusterRef(ref);
    if (ref) {
      setSelectedProjectId(null);
      selectedProjectIdRef.current = null;
      setSelectedMacroClusterLinkId(null);
      selectedMacroClusterLinkIdRef.current = null;
    }
  };

  const setMacroClusterLinking = (active: boolean, source: MacroClusterRef | null) => {
    macroClusterLinkingModeRef.current = active;
    macroClusterLinkSourceRef.current = source;
    setMacroClusterLinkingMode(active);
    setMacroClusterLinkSource(source);
    if (source) {
      selectMacroCluster(source);
    }
  };

  const handleMacroClusterLinkingClick = (target: MacroClusterRef) => {
    if (!macroClusterLinkSourceRef.current) {
      selectMacroCluster(target);
      return;
    }

    const source = macroClusterLinkSourceRef.current;

    if (
      source.projectId === target.projectId &&
      source.kind === target.kind &&
      source.key === target.key
    ) {
      setMacroClusterLinking(false, null);
      return;
    }

    const exists = macroClusterLinksRef.current.some(
      (l) =>
        (l.source_project_id === source.projectId &&
          l.source_kind === source.kind &&
          l.source_key === source.key &&
          l.target_project_id === target.projectId &&
          l.target_kind === target.kind &&
          l.target_key === target.key) ||
        (l.source_project_id === target.projectId &&
          l.source_kind === target.kind &&
          l.source_key === target.key &&
          l.target_project_id === source.projectId &&
          l.target_kind === source.kind &&
          l.target_key === source.key),
    );

    if (exists) {
      setMacroClusterLinking(false, null);
      return;
    }

    const newLink: MacroClusterLink = {
      id: genId(),
      source_project_id: source.projectId,
      source_kind: source.kind,
      source_key: source.key,
      source_label: source.label,
      target_project_id: target.projectId,
      target_kind: target.kind,
      target_key: target.key,
      target_label: target.label,
    };

    const updated = [...macroClusterLinksRef.current, newLink];
    macroClusterLinksRef.current = updated;
    setMacroClusterLinks(updated);
    localStorage.setItem('cortex_macro_cluster_links', JSON.stringify(updated));
    setMacroClusterLinking(false, null);
    selectMacroCluster(target);
  };

  const deleteMacroClusterLink = (linkId: string) => {
    const updated = macroClusterLinksRef.current.filter((l) => l.id !== linkId);
    macroClusterLinksRef.current = updated;
    setMacroClusterLinks(updated);
    localStorage.setItem('cortex_macro_cluster_links', JSON.stringify(updated));
    if (selectedMacroClusterLinkIdRef.current === linkId) {
      setSelectedMacroClusterLinkId(null);
      selectedMacroClusterLinkIdRef.current = null;
    }
  };

  const loadAllProjectStats = useCallback(async (projs: Projekt[]) => {
    const b = window.cortexBridge;
    if (!b?.projGetNodes) return;
    const stats: Record<string, { count: number; previews: string[] }> = {};
    for (const p of projs) {
      try {
        const pNodes = await b.projGetNodes({ projectId: p.id });
        stats[p.id] = {
          count: pNodes.length,
          previews: pNodes
            .slice(0, 3)
            .map((n) => (n.title || n.content || '').split('\n')[0].trim())
            .filter(Boolean),
        };
      } catch (err) {
        console.error('[NotesCanvas] failed to get stats for project', p.id, err);
      }
    }
    setProjectStats(stats);
  }, []);

  const diveIntoProject = async (projectId: string, targetClusterKey?: string) => {
    await handleSwitchProject(projectId, targetClusterKey);
  };

  const zoomToMacroView = () => {
    setViewMode('projects');
    viewModeRef.current = 'projects';
    setScale(1.0);
    scaleRef.current = 1.0;
    const rect = canvasRef.current?.getBoundingClientRect();
    const vw = rect ? rect.width : window.innerWidth;
    const vh = rect ? rect.height : window.innerHeight;

    const currentProjs = projectsRef.current;
    if (!currentProjs || currentProjs.length === 0) {
      setOffset({ x: vw / 2, y: vh / 2 });
      offsetRef.current = { x: vw / 2, y: vh / 2 };
      return;
    }

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    currentProjs.forEach((p, i) => {
      const pos = getProjectMacroPosition(p, i, currentProjs.length);
      if (pos.x < minX) minX = pos.x;
      if (pos.y < minY) minY = pos.y;
      if (pos.x + PROJECT_CARD_WIDTH > maxX) maxX = pos.x + PROJECT_CARD_WIDTH;
      if (pos.y + PROJECT_CARD_HEIGHT > maxY) maxY = pos.y + PROJECT_CARD_HEIGHT;
    });

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const newOffX = vw / 2 - centerX;
    const newOffY = vh / 2 - centerY;
    setOffset({ x: newOffX, y: newOffY });
    offsetRef.current = { x: newOffX, y: newOffY };
  };

  const startDraggingMacroProject = (projId: string, posX: number, posY: number, e: ReactMouseEvent) => {
    if (e.button !== 0) return;
    if (macroLinkingModeRef.current || macroClusterLinkingModeRef.current) return;
    const target = e.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'BUTTON' || target.closest('button')) return;
    e.stopPropagation();
    e.preventDefault();

    macroDragRef.current = {
      id: projId,
      startX: e.clientX,
      startY: e.clientY,
      origX: posX,
      origY: posY,
      moved: false,
    };
  };

  const handleUpdateClusterOffset = (projId: string, clusterKey: string, offset: { x: number; y: number }) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id !== projId) return p;
        const updatedOffsets = { ...(p.cluster_offsets || {}), [clusterKey]: offset };
        const updatedProj = { ...p, cluster_offsets: updatedOffsets };
        const b = window.cortexBridge;
        if (b?.projSaveProject) {
          void b.projSaveProject({ project: updatedProj });
        }
        return updatedProj;
      })
    );
  };

  const addProjectInMacroView = async (pos: { x: number; y: number }) => {
    const newProjId = genId();
    const newProj: Projekt = {
      id: newProjId,
      name: `Projekt ${projects.length + 1}`,
      x: Math.round(pos.x - PROJECT_CARD_WIDTH / 2),
      y: Math.round(pos.y - PROJECT_CARD_HEIGHT / 2),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const b = window.cortexBridge;
    if (b?.projSaveProject) {
      await b.projSaveProject({ project: newProj });
    }

    setProjects((prev) => [...prev, newProj]);
    setEditingProjectId(newProjId);
    setEditingProjectName(newProj.name);
  };

  // --- wczytanie danych ----------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const b = window.cortexBridge;
      if (!b?.projGetProjects || !b?.projSaveProject) {
        setLoaded(true);
        return;
      }

      try {
        let projs = await b.projGetProjects();
        if (!projs || projs.length === 0) {
          const defaultProj: Projekt = {
            id: 'default',
            name: 'Tablica główna',
            x: 0,
            y: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
          await b.projSaveProject({ project: defaultProj });
          projs = [defaultProj];
        } else {
          projs = projs.map((p, i) => {
            if (typeof p.x !== 'number' || typeof p.y !== 'number') {
              const pos = getProjectMacroPosition(p, i, projs.length);
              const withPos: Projekt = { ...p, x: pos.x, y: pos.y };
              void b?.projSaveProject?.({ project: withPos });
              return withPos;
            }
            return p;
          });
        }

        let currentActiveId = activeProjectIdRef.current;
        if (!projs.some((p) => p.id === currentActiveId)) {
          currentActiveId = projs[0].id;
          activeProjectIdRef.current = currentActiveId;
          setActiveProjectId(currentActiveId);
          localStorage.setItem('cortex_active_project_id', currentActiveId);
        }

        const nds = (await b.projGetNodes({ projectId: currentActiveId })).map((n) => {
          if (n.title) return n;
          const firstLine = (n.content || '').split('\n').find((l) => l.trim() !== '')?.trim() ?? '';
          return { ...n, title: firstLine };
        });
        const eds = await b.projGetEdges({ projectId: currentActiveId });

        if (!cancelled) {
          setProjects(projs);
          projectsRef.current = projs;
          setNodes(nds);
          nodesRef.current = nds;
          setEdges(eds);
          edgesRef.current = eds;
          for (const n of nds) if (n.title) void saveNode(n);
          void loadAllProjectStats(projs);
          centerOnProjectNotes(nds);
        }
      } catch (err) {
        console.error('[NotesCanvas] load failed', err);
        if (!cancelled) setLoadError(String(err));
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loadAllProjectStats, centerOnProjectNotes]);

  // --- geometria canvasu ---------------------------------------------------
  const screenToCanvas = (clientX: number, clientY: number) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const cx = rect ? clientX - rect.left : clientX;
    const cy = rect ? clientY - rect.top : clientY;
    return {
      x: (cx - offsetRef.current.x) / scaleRef.current,
      y: (cy - offsetRef.current.y) / scaleRef.current,
    };
  };

  // --- edycja notatek ------------------------------------------------------
  const startEditing = (nodeId: string) => {
    const node = nodesRef.current.find((n) => n.id === nodeId);
    if (!node) return;
    cancelEditRef.current = false;
    selectNode(nodeId);
    editingNodeIdRef.current = nodeId;
    setEditingNodeId(nodeId);
    const initialText = node.node_type === 'portal' ? (node.title || '') : (node.content ?? '');
    editingTextRef.current = initialText;
    setEditingText(initialText);
  };

  const commitEditing = async (targetId?: string, targetText?: string) => {
    const id = targetId ?? editingNodeIdRef.current;
    if (!id) return;

    const text = targetText !== undefined ? targetText : editingTextRef.current;
    const wasCancelled = cancelEditRef.current;

    editingNodeIdRef.current = null;
    setEditingNodeId(null);
    editingTextRef.current = '';
    setEditingText('');

    if (wasCancelled) return;

    const node = nodesRef.current.find((n) => n.id === id);
    if (!node) return;

    if (node.node_type === 'portal') {
      const newTitle = text.trim() || 'Nowy projekt';
      if (node.title === newTitle) return;
      const updated: ProjektyNode = {
        ...node,
        title: newTitle,
        content: newTitle,
        updated_at: new Date().toISOString(),
      };
      setNodes((prev) => prev.map((n) => (n.id === id ? updated : n)));
      nodesRef.current = nodesRef.current.map((n) => (n.id === id ? updated : n));
      await saveNode(updated);
      return;
    }

    if (node.content === text) return;

    const firstLine = text.split('\n').find((l) => l.trim() !== '')?.trim() ?? '';
    const el = cardElRefs.current[id];
    const domHeight = el ? Math.round(el.offsetHeight) : undefined;
    const updated: ProjektyNode = {
      ...node,
      content: text,
      title: firstLine,
      height: domHeight && domHeight > NODE_HEIGHT ? domHeight : (node.height || NODE_HEIGHT),
      updated_at: new Date().toISOString(),
    };
    setNodes((prev) => prev.map((n) => (n.id === id ? updated : n)));
    nodesRef.current = nodesRef.current.map((n) => (n.id === id ? updated : n));
    await saveNode(updated);
  };

  const cancelEditing = () => {
    cancelEditRef.current = true;
    editingNodeIdRef.current = null;
    setEditingNodeId(null);
    editingTextRef.current = '';
    setEditingText('');
  };

  // Deterministyczny mechanizm Garbage Collection dla klamer:
  // Jeśli usunięto węzeł, klamra przycina listę węzłów; jeśli zostaje < 2 węzły, ulega samozniszczeniu.
  const pruneProjectBrackets = (proj: Projekt, remainingNodeIds: Set<string>): { updatedProj: Projekt; changed: boolean } => {
    if (!proj.brackets || proj.brackets.length === 0) return { updatedProj: proj, changed: false };
    let changed = false;
    const nextBrackets: ProjektyBracket[] = [];
    for (const b of proj.brackets) {
      const validIds = b.node_ids.filter((id) => remainingNodeIds.has(id));
      if (validIds.length >= 2) {
        if (validIds.length !== b.node_ids.length) {
          changed = true;
          nextBrackets.push({ ...b, node_ids: validIds });
        } else {
          nextBrackets.push(b);
        }
      } else {
        changed = true;
      }
    }
    if (changed) {
      return {
        updatedProj: {
          ...proj,
          brackets: nextBrackets,
          updated_at: new Date().toISOString(),
        },
        changed: true,
      };
    }
    return { updatedProj: proj, changed: false };
  };

  const deleteNote = async (nodeId: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== nodeId));
    nodesRef.current = nodesRef.current.filter((n) => n.id !== nodeId);
    setEdges((prev) => prev.filter((e) => e.source_node_id !== nodeId && e.target_node_id !== nodeId));
    edgesRef.current = edgesRef.current.filter((e) => e.source_node_id !== nodeId && e.target_node_id !== nodeId);
    if (selectedNodeIdRef.current === nodeId) selectNode(null);
    if (editingNodeIdRef.current === nodeId) {
      editingNodeIdRef.current = null;
      setEditingNodeId(null);
    }
    if (linkSourceIdRef.current === nodeId) setLinking(linkingModeRef.current, null);

    // Garbage collection klamer
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (curProj) {
      const remaining = new Set(nodesRef.current.map((n) => n.id));
      const { updatedProj, changed } = pruneProjectBrackets(curProj, remaining);
      if (changed) {
        setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
        projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));
        void window.cortexBridge?.projSaveProject?.({ project: updatedProj });
      }
    }

    try {
      await window.cortexBridge?.projDeleteNode?.({ id: nodeId });
    } catch (err) {
      console.error('[NotesCanvas] deleteNote', err);
    }
  };

  const deleteNotes = async (nodeIds: string[]) => {
    const ids = Array.from(new Set(nodeIds));
    if (ids.length === 0) return;

    setNodes((prev) => prev.filter((n) => !ids.includes(n.id)));
    nodesRef.current = nodesRef.current.filter((n) => !ids.includes(n.id));
    setEdges((prev) => prev.filter((e) => !ids.includes(e.source_node_id) && !ids.includes(e.target_node_id)));
    edgesRef.current = edgesRef.current.filter((e) => !ids.includes(e.source_node_id) && !ids.includes(e.target_node_id));

    if (selectedNodeIdRef.current && ids.includes(selectedNodeIdRef.current)) selectNode(null);
    if (editingNodeIdRef.current && ids.includes(editingNodeIdRef.current)) {
      editingNodeIdRef.current = null;
      setEditingNodeId(null);
    }
    if (linkSourceIdRef.current && ids.includes(linkSourceIdRef.current)) setLinking(linkingModeRef.current, null);

    // Garbage collection klamer
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (curProj) {
      const remaining = new Set(nodesRef.current.map((n) => n.id));
      const { updatedProj, changed } = pruneProjectBrackets(curProj, remaining);
      if (changed) {
        setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
        projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));
        void window.cortexBridge?.projSaveProject?.({ project: updatedProj });
      }
    }

    await Promise.allSettled(
      ids.map((id) => window.cortexBridge?.projDeleteNode?.({ id })),
    );
  };

  const deleteEdge = async (edgeId: string) => {
    setEdges((prev) => prev.filter((e) => e.id !== edgeId));
    edgesRef.current = edgesRef.current.filter((e) => e.id !== edgeId);
    await deleteEdgeApi(edgeId);
  };

  const handleToggleEdgeArrow = async (edgeId: string) => {
    const currentEdge = edgesRef.current.find((e) => e.id === edgeId);
    if (!currentEdge) return;

    const nextHasArrow = currentEdge.has_arrow === false;
    const updatedEdge: ProjektyEdge = { ...currentEdge, has_arrow: nextHasArrow };

    setEdges((prev) =>
      prev.map((e) => (e.id === edgeId ? updatedEdge : e)),
    );
    edgesRef.current = edgesRef.current.map((e) =>
      e.id === edgeId ? updatedEdge : e,
    );

    await saveEdge(updatedEdge);
  };

  // --- skróty klawiszowe ---------------------------------------------------
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const isTyping = !!el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT');

      const hasCtrl = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();

      // Ctrl+C — skopiuj zaznaczone notatki (płytko, bez pod-tablic)
      if (hasCtrl && key === 'c' && !isTyping) {
        const ids = selectedIdsRef.current;
        const selected = nodesRef.current
          .filter((n) => ids.includes(n.id))
          .map(({ id, project_id, title, content, label, description, node_type, status, x, y, width, height, collapsed, locked_position, ai_suggestion, ai_suggestion_reason }) => ({
            id, project_id, title, content, label, description, node_type, status, x, y, width, height, collapsed, locked_position, ai_suggestion, ai_suggestion_reason,
          }));
        if (selected.length > 0) {
          clipboardRef.current = selected;
        }
        return;
      }

      // Ctrl+A — zaznacz wszystkie widoczne notatki
      if (hasCtrl && key === 'a' && !isTyping) {
        e.preventDefault();
        const bp = boardPathRef.current;
        const pId = bp.length > 0 ? bp[bp.length - 1] : null;
        const allIds = nodesRef.current
          .filter((n) => (pId === null ? n.parent_id == null : n.id === pId || n.parent_id === pId))
          .map((n) => n.id);
        selectedIdsRef.current = allIds;
        setSelectedIds(allIds);
        selectedNodeIdRef.current = allIds.length === 1 ? allIds[0] : null;
        setSelectedNodeId(allIds.length === 1 ? allIds[0] : null);
        return;
      }

      // Ctrl+V — wklej notatki ze schowka
      if (hasCtrl && key === 'v' && !isTyping) {
        const clip = clipboardRef.current;
        if (!clip || clip.length === 0) return;
        const newNodes: ProjektyNode[] = [];
        for (const src of clip) {
          const node: ProjektyNode = {
            ...src,
            id: genId(),
            parent_id: currentBoardParentId(),
            x: src.x + 24,
            y: src.y + 24,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
          newNodes.push(node);
        }
        setNodes((prev) => [...prev, ...newNodes]);
        nodesRef.current = [...nodesRef.current, ...newNodes];
        selectedIdsRef.current = newNodes.map((n) => n.id);
        setSelectedIds(newNodes.map((n) => n.id));
        selectedNodeIdRef.current = newNodes.length === 1 ? newNodes[0].id : null;
        setSelectedNodeId(newNodes.length === 1 ? newNodes[0].id : null);
        for (const n of newNodes) void saveNode(n);
        return;
      }

      // Skrót otwierania pomocy: ?
      if (e.key === '?' && !isTyping) {
        e.preventDefault();
        setShowHelp((v) => !v);
        return;
      }

      // Shift+P — utwórz klocek projektu (Portal Node)
      if (e.shiftKey && (e.key === 'P' || e.key === 'p') && !isTyping && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        void createPortalNodeAtCenter();
        return;
      }

      // Ctrl+G / Cmd+G — utwórz klaster z zaznaczonych notatek
      if ((e.ctrlKey || e.metaKey) && (e.key === 'g' || e.key === 'G') && !isTyping) {
        e.preventDefault();
        void handleCreateCluster();
        return;
      }

      if (e.key === 'Tab' || e.code === 'Backquote') {
        e.preventDefault();

        // Obsługa łączenia w widoku makro (Tablica Projektów)
        if (viewModeRef.current === 'projects' || scaleRef.current < ZOOM_MACRO_THRESHOLD) {
          // Najpierw: zaznaczony klaster/klamra -> Tab łączy go (jak notatki w mikro).
          const selCluster = macroSelectedClusterRefRef.current;
          if (selCluster) {
            const isSameSource =
              macroClusterLinkSourceRef.current &&
              macroClusterLinkSourceRef.current.projectId === selCluster.projectId &&
              macroClusterLinkSourceRef.current.kind === selCluster.kind &&
              macroClusterLinkSourceRef.current.key === selCluster.key;
            if (macroClusterLinkingModeRef.current && isSameSource) {
              setMacroClusterLinking(false, null);
            } else {
              setMacroClusterLinking(true, selCluster);
            }
            return;
          }

          const selProj = selectedProjectIdRef.current;
          if (selProj) {
            if (macroLinkingModeRef.current && macroLinkSourceIdRef.current === selProj) {
              setMacroLinking(false, null);
            } else {
              setMacroLinking(true, selProj);
            }
          }
          return;
        }

        const currentEditing = editingNodeIdRef.current;
        const currentSelected = selectedNodeIdRef.current;
        const currentLinking = linkingModeRef.current;
        const currentLinkSource = linkSourceIdRef.current;

        if (currentEditing) {
          void commitEditing(currentEditing, editingTextRef.current);
          selectNode(currentEditing);
          setLinking(true, currentEditing);
          return;
        }

        if (currentSelected) {
          if (currentLinking && currentLinkSource === currentSelected) {
            setLinking(false, null);
          } else {
            setLinking(true, currentSelected);
          }
          return;
        }

        if (currentLinking) {
          setLinking(false, null);
        } else {
          setLinking(true, null);
        }
      } else if (e.key === 'Escape') {
        if (macroClusterLinkSourceRef.current) {
          e.preventDefault();
          setMacroClusterLinking(false, null);
        } else if (selectedMacroClusterLinkIdRef.current) {
          e.preventDefault();
          setSelectedMacroClusterLinkId(null);
          selectedMacroClusterLinkIdRef.current = null;
        } else if (macroSelectedClusterRefRef.current) {
          e.preventDefault();
          selectMacroCluster(null);
        } else if (macroLinkingModeRef.current) {
          e.preventDefault();
          setMacroLinking(false, null);
        } else if (selectedProjectIdRef.current) {
          e.preventDefault();
          setSelectedProjectId(null);
        } else if (placementModeRef.current) {
          e.preventDefault();
          placementModeRef.current = false;
          setPlacementMode(false);
        } else if (showHelp) {
          e.preventDefault();
          setShowHelp(false);
        } else if (linkingModeRef.current) {
          e.preventDefault();
          setLinking(false, null);
        } else if (editingNodeIdRef.current) {
          e.preventDefault();
          cancelEditing();
        } else if (selectedNodeIdRef.current || selectedIdsRef.current.length > 0) {
          e.preventDefault();
          selectNode(null);
        }
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && !isTyping) {
        if (selectedMacroClusterLinkIdRef.current) {
          e.preventDefault();
          deleteMacroClusterLink(selectedMacroClusterLinkIdRef.current);
        } else {
          const ids = selectedIdsRef.current;
          if (ids.length > 0 && !editingNodeIdRef.current) {
            e.preventDefault();
            void deleteNotes(ids);
          }
        }
      } else if (e.key === 'Enter' && !isTyping) {
        if (viewModeRef.current === 'projects' && selectedProjectIdRef.current) {
          e.preventDefault();
          void diveIntoProject(selectedProjectIdRef.current);
        } else if (selectedNodeIdRef.current && !editingNodeIdRef.current) {
          e.preventDefault();
          startEditing(selectedNodeIdRef.current);
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showHelp]);

  const findProjectUnderCursor = (worldX: number, worldY: number, projectsList: Projekt[]): Projekt | null => {
    if (projectsList.length === 0) return null;
    for (let i = 0; i < projectsList.length; i++) {
      const p = projectsList[i];
      const pos = getProjectMacroPosition(p, i, projectsList.length);
      if (
        worldX >= pos.x &&
        worldX <= pos.x + PROJECT_CARD_WIDTH &&
        worldY >= pos.y &&
        worldY <= pos.y + PROJECT_CARD_HEIGHT
      ) {
        return p;
      }
    }
    let best = projectsList[0];
    let minDist = Infinity;
    for (let i = 0; i < projectsList.length; i++) {
      const p = projectsList[i];
      const pos = getProjectMacroPosition(p, i, projectsList.length);
      const cx = pos.x + PROJECT_CARD_WIDTH / 2;
      const cy = pos.y + PROJECT_CARD_HEIGHT / 2;
      const dist = Math.hypot(worldX - cx, worldY - cy);
      if (dist < minDist) {
        minDist = dist;
        best = p;
      }
    }
    return best;
  };

  // --- zoom wokół punktu pod kursorem z proporcjonalnym dociąganiem do centrum ---
  const zoomAt = useCallback(
    (focalX: number, focalY: number, factor: number, viewportWidth?: number, viewportHeight?: number) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      const vw = viewportWidth ?? (rect ? rect.width : window.innerWidth);
      const vh = viewportHeight ?? (rect ? rect.height : window.innerHeight);

      const isProjectsMode = viewModeRef.current === 'projects';

      // 1. Zoom in w widoku projektów powyżej 300% (scale >= 3.0) -> Przejście do wnętrza wybranego projektu na 41% w szczegółach
      if (isProjectsMode && factor > 1) {
        const projectedScale = scaleRef.current * factor;
        if (projectedScale >= 3.0) {
          const worldX = (focalX - offsetRef.current.x) / scaleRef.current;
          const worldY = (focalY - offsetRef.current.y) / scaleRef.current;
          const targetProj = findProjectUnderCursor(worldX, worldY, projects);
          if (targetProj) {
            setViewMode('notes');
            viewModeRef.current = 'notes';
            setActiveProjectId(targetProj.id);
            activeProjectIdRef.current = targetProj.id;
            localStorage.setItem('cortex_active_project_id', targetProj.id);
            setIsProjectMenuOpen(false);
            setEditingProjectId(null);
            setSelectedProjectId(null);
            void loadProjectData(targetProj.id, false);
            setScale(0.41);
            scaleRef.current = 0.41;
            const newOffX = vw / 2 - (vw / 2) * 0.41;
            const newOffY = vh / 2 - (vh / 2) * 0.41;
            setOffset({ x: newOffX, y: newOffY });
            offsetRef.current = { x: newOffX, y: newOffY };
            return;
          }
        }
      }

      // 2. Zoom out w szczegółach notatek poniżej progu makro (scale < ZOOM_MACRO_THRESHOLD) -> Powrót do widoku wszystkich projektów
      if (!isProjectsMode && factor < 1) {
        const projectedScale = scaleRef.current * factor;
        if (projectedScale < ZOOM_MACRO_THRESHOLD) {
          setViewMode('projects');
          viewModeRef.current = 'projects';
          setScale(1.0);
          scaleRef.current = 1.0;
          const activeIdx = Math.max(0, projects.findIndex((p) => p.id === activeProjectIdRef.current));
          const activeProj = projects[activeIdx] || projects[0];
          if (activeProj) {
            const pos = getProjectMacroPosition(activeProj, activeIdx, projects.length);
            const cx = pos.x + PROJECT_CARD_WIDTH / 2;
            const cy = pos.y + PROJECT_CARD_HEIGHT / 2;
            const newOffX = vw / 2 - cx;
            const newOffY = vh / 2 - cy;
            setOffset({ x: newOffX, y: newOffY });
            offsetRef.current = { x: newOffX, y: newOffY };
          } else {
            setOffset({ x: vw / 2, y: vh / 2 });
            offsetRef.current = { x: vw / 2, y: vh / 2 };
          }
          return;
        }
      }

      const result = calculateZoomTransform({
        currentScale: scaleRef.current,
        currentOffset: offsetRef.current,
        focalX,
        focalY,
        factor,
        viewportWidth: vw,
        viewportHeight: vh,
        centeringFactor: 0.45,
      });

      if (
        result.scale !== scaleRef.current ||
        result.offset.x !== offsetRef.current.x ||
        result.offset.y !== offsetRef.current.y
      ) {
        scaleRef.current = result.scale;
        offsetRef.current = result.offset;
        setScale(result.scale);
        setOffset(result.offset);
      }
    },
    [projects],
  );

  // --- zoom (natywny listener) ---------------------------------------------
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;

    const onWheelNative = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const focalX = e.clientX - rect.left;
      const focalY = e.clientY - rect.top;

      // Płynny zoom: deltaY > 0 oddala widok, deltaY < 0 przybliża widok
      const factor = Math.min(Math.max(Math.exp(-e.deltaY * 0.0018), 0.7), 1.4);
      zoomAt(focalX, focalY, factor, rect.width, rect.height);
    };

    el.addEventListener('wheel', onWheelNative, { passive: false });
    return () => el.removeEventListener('wheel', onWheelNative);
  }, [zoomAt]);

  // --- interakcje canvasu --------------------------------------------------
  const onCanvasMouseDown = (e: ReactMouseEvent) => {
    if (contextMenu) {
      setContextMenu(null);
    }
    // Środkowy (1) lub prawy (2) przycisk myszy — natychmiastowe przesuwanie płótna / anulowanie trybu stawiania
    if (e.button === 1 || e.button === 2) {
      e.preventDefault();
      if (placementModeRef.current) {
        placementModeRef.current = false;
        setPlacementMode(false);
      }
      panRef.current = {
        startX: e.clientX - offsetRef.current.x,
        startY: e.clientY - offsetRef.current.y,
      };
      setIsPanning(true);
      return;
    }

    // Tryb stawiania klocka projektu (Placement mode jak w grze) — lewy klik stawia klocek
    if (placementModeRef.current && e.button === 0) {
      e.preventDefault();
      e.stopPropagation();
      const pos = screenToCanvas(e.clientX, e.clientY);
      void addPortalNodeAt(pos);
      placementModeRef.current = false;
      setPlacementMode(false);
      return;
    }

    const target = e.target as HTMLElement;
    if (target === canvasRef.current || target.dataset?.canvas === 'bg') {
      e.preventDefault();

      if (linkingModeRef.current) {
        setLinking(false, null);
      }
      if (macroClusterLinkingModeRef.current) {
        setMacroClusterLinking(false, null);
      }
      if (macroLinkingModeRef.current) {
        setMacroLinking(false, null);
      }
      if (selectedMacroClusterLinkIdRef.current) {
        setSelectedMacroClusterLinkId(null);
        selectedMacroClusterLinkIdRef.current = null;
      }
      if (macroSelectedClusterRefRef.current) {
        selectMacroCluster(null);
      }
      if (selectedProjectIdRef.current) {
        setSelectedProjectId(null);
      }
      if (editingNodeIdRef.current) {
        void commitEditing();
      }

      if (e.shiftKey) {
        // Shift + przeciąganie po tle = marquee (zaznaczanie ramką)
        const pos = screenToCanvas(e.clientX, e.clientY);
        marqueeRef.current = { x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y, active: true };
        setMarquee({ x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y });
        return;
      }

      selectNode(null);

      panRef.current = {
        startX: e.clientX - offsetRef.current.x,
        startY: e.clientY - offsetRef.current.y,
      };
      setIsPanning(true);
    }
  };

  // Globalne listenery myszy z płynną synchronizacją RAF (RequestAnimationFrame)
  useEffect(() => {
    let rafId: number | null = null;
    let latestEvent: MouseEvent | null = null;

    const processMove = () => {
      rafId = null;
      if (!latestEvent) return;
      const e = latestEvent;

      // Śledzenie pozycji dla linii łączącej TYLKO kiedy jest to aktywnie potrzebne
      if (
        linkingModeRef.current ||
        macroLinkingModeRef.current ||
        macroClusterLinkingModeRef.current ||
        placementModeRef.current
      ) {
        const pos = screenToCanvas(e.clientX, e.clientY);
        setMouseCanvasPos(pos);
      }

      const marqueeState = marqueeRef.current;
      if (marqueeState?.active) {
        const pos = screenToCanvas(e.clientX, e.clientY);
        marqueeRef.current = { ...marqueeState, x2: pos.x, y2: pos.y };
        setMarquee({ x1: marqueeState.x1, y1: marqueeState.y1, x2: pos.x, y2: pos.y });
        return;
      }

      const pan = panRef.current;
      if (pan) {
        const newOffX = e.clientX - pan.startX;
        const newOffY = e.clientY - pan.startY;
        offsetRef.current = { x: newOffX, y: newOffY };
        setOffset({ x: newOffX, y: newOffY });
        return;
      }

      if (macroDragRef.current) {
        const md = macroDragRef.current;
        const totalDist = Math.abs(e.clientX - md.startX) + Math.abs(e.clientY - md.startY);
        if (!md.moved && totalDist > 3) {
          md.moved = true;
          setDraggingMacroProjId(md.id);
        }
        if (md.moved) {
          const dx = (e.clientX - md.startX) / scaleRef.current;
          const dy = (e.clientY - md.startY) / scaleRef.current;
          const newX = Math.round(md.origX + dx);
          const newY = Math.round(md.origY + dy);
          const updated = projectsRef.current.map((p) => (p.id === md.id ? { ...p, x: newX, y: newY } : p));
          projectsRef.current = updated;
          setProjects(updated);
        }
        return;
      }

      const drag = dragRef.current;
      if (!drag) return;

      const totalMove = Math.abs(e.clientX - drag.startX) + Math.abs(e.clientY - drag.startY);
      if (!drag.moved && totalMove > 3) {
        drag.moved = true;
        setDraggingNodeId(drag.id);

        if (!selectedIdsRef.current.includes(drag.id)) {
          selectedIdsRef.current = [drag.id];
          setSelectedIds([drag.id]);
          selectedNodeIdRef.current = drag.id;
          setSelectedNodeId(drag.id);
        }

        const group = selectedIdsRef.current;
        drag.group = group
          .map((id) => {
            const n = nodesRef.current.find((node) => node.id === id);
            return n ? { id, x: n.x, y: n.y } : null;
          })
          .filter(Boolean) as { id: string; x: number; y: number }[];
      }

      if (drag.moved) {
        const dx = (e.clientX - drag.startX) / scaleRef.current;
        const dy = (e.clientY - drag.startY) / scaleRef.current;

        if (drag.group && drag.group.length > 0) {
          const moved = new Map(drag.group.map((g) => [g.id, g]));
          nodesRef.current = nodesRef.current.map((n) => {
            const g = moved.get(n.id);
            return g ? { ...n, x: Math.round(g.x + dx), y: Math.round(g.y + dy) } : n;
          });
          setNodes(nodesRef.current);
        } else {
          const nx = Math.round(drag.nx + dx);
          const ny = Math.round(drag.ny + dy);
          nodesRef.current = nodesRef.current.map((n) => (n.id === drag.id ? { ...n, x: nx, y: ny } : n));
          setNodes(nodesRef.current);
        }
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      latestEvent = e;
      if (
        linkingModeRef.current ||
        macroLinkingModeRef.current ||
        macroClusterLinkingModeRef.current ||
        placementModeRef.current
      ) {
        const pos = screenToCanvas(e.clientX, e.clientY);
        setMouseCanvasPos(pos);
      }
      if (rafId === null) {
        rafId = requestAnimationFrame(processMove);
      }
    };

    const handleMouseUp = (e: MouseEvent) => {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      if (!latestEvent || (e.clientX !== 0 || e.clientY !== 0)) {
        latestEvent = e;
      }
      processMove();

      const marqueeState = marqueeRef.current;
      if (marqueeState?.active) {
        marqueeRef.current = null;
        const rect = { x1: marqueeState.x1, y1: marqueeState.y1, x2: marqueeState.x2, y2: marqueeState.y2 };
        setMarquee(null);
        if (!rect) return;

        const minX = Math.min(rect.x1, rect.x2);
        const maxX = Math.max(rect.x1, rect.x2);
        const minY = Math.min(rect.y1, rect.y2);
        const maxY = Math.max(rect.y1, rect.y2);

        const bp = boardPathRef.current;
        const pId = bp.length > 0 ? bp[bp.length - 1] : null;
        const hitIds = nodesRef.current
          .filter((n) => (pId === null ? n.parent_id == null : n.id === pId || n.parent_id === pId))
          .filter((n) => {
            const w = n.width || NODE_WIDTH;
            const h = n.height || NODE_HEIGHT;
            // Test przecięcia prostokątów (partial overlap), nie tylko środek
            const nx1 = n.x;
            const ny1 = n.y;
            const nx2 = n.x + w;
            const ny2 = n.y + h;
            return nx1 < maxX && nx2 > minX && ny1 < maxY && ny2 > minY;
          })
          .map((n) => n.id);

        const cur = selectedIdsRef.current;
        const merged = Array.from(new Set([...cur, ...hitIds]));
        selectedIdsRef.current = merged;
        setSelectedIds(merged);
        selectedNodeIdRef.current = merged.length === 1 ? merged[0] : null;
        setSelectedNodeId(merged.length === 1 ? merged[0] : null);
        return;
      }

      const pan = panRef.current;
      if (pan) {
        panRef.current = null;
        setIsPanning(false);
        return;
      }

      if (macroDragRef.current) {
        const md = macroDragRef.current;
        if (md.moved) {
          const updated = projectsRef.current.find((p) => p.id === md.id);
          if (updated) {
            const b = window.cortexBridge;
            if (b?.projSaveProject) {
              void b.projSaveProject({ project: updated });
            }
          }
        }
        macroDragRef.current = null;
        setDraggingMacroProjId(null);
        return;
      }

      const drag = dragRef.current;
      if (!drag) return;

      const wasMoved = drag.moved;
      const clickedId = drag.id;
      dragRef.current = null;

      if (wasMoved) {
        setDraggingNodeId(null);
        for (const id of selectedIdsRef.current) {
          const node = nodesRef.current.find((n) => n.id === id);
          if (node) void saveNode(node);
        }
      } else {
        // Kliknięcie bez przesunięcia -> zaznaczenie notatki
        const isShift = Boolean(e.shiftKey || drag.shiftKey);
        if (linkingModeRef.current) {
          void handleNodeLinkingClick(clickedId);
        } else if (isShift) {
          toggleSelectedId(clickedId);
        } else {
          selectNode(clickedId);
        }
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const resetView = () => {
    if (Math.abs(scaleRef.current - 1) < 0.01) {
      scaleRef.current = 1;
      offsetRef.current = { x: 0, y: 0 };
      setScale(1);
      setOffset({ x: 0, y: 0 });
      return;
    }
    const rect = canvasRef.current?.getBoundingClientRect();
    const focalX = rect ? rect.width / 2 : window.innerWidth / 2;
    const focalY = rect ? rect.height / 2 : window.innerHeight / 2;
    const oldScale = scaleRef.current || 1;
    const oldOffset = offsetRef.current;

    const newOffsetX = focalX - ((focalX - oldOffset.x) / oldScale) * 1;
    const newOffsetY = focalY - ((focalY - oldOffset.y) / oldScale) * 1;

    const nextOffset = { x: newOffsetX, y: newOffsetY };
    scaleRef.current = 1;
    offsetRef.current = nextOffset;
    setScale(1);
    setOffset(nextOffset);
  };

  const zoomBy = (factor: number) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const focalX = rect ? rect.width / 2 : window.innerWidth / 2;
    const focalY = rect ? rect.height / 2 : window.innerHeight / 2;
    zoomAt(focalX, focalY, factor);
  };

  // --- stałe i metody dla klocka projektu (Portal Node) -------------------
  const addPortalNodeAt = async (pos: { x: number; y: number }) => {
    const node: ProjektyNode = {
      id: genId(),
      project_id: activeProjectIdRef.current,
      title: 'Projekt: Nowy Plan',
      content: '',
      node_type: 'portal',
      parent_id: currentBoardParentId(),
      x: pos.x - 320 / 2,
      y: pos.y - 240 / 2,
      width: 320,
      height: 240,
      created_at: new Date().toISOString(),
    };

    setNodes((prev) => [...prev, node]);
    nodesRef.current = [...nodesRef.current, node];
    selectNode(node.id);
    await saveNode(node);
  };

  const createPortalNodeAtCenter = async () => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const pos = screenToCanvas(rect.left + rect.width / 2, rect.top + rect.height / 2);
    await addPortalNodeAt(pos);
  };

  const handleOpenPortalAsProject = async (portalNode: ProjektyNode, connectedNodes: ProjektyNode[]) => {
    const rawTitle = portalNode.title || 'Nowy Plan';
    const projectName = rawTitle.replace(/^Projekt:\s*/i, '').trim() || 'Nowy Plan';

    let targetProjectId = typeof portalNode.metadata === 'object' && portalNode.metadata !== null
      ? portalNode.metadata.target_project_id
      : undefined;

    let targetProject = targetProjectId ? projects.find((p) => p.id === targetProjectId) : undefined;

    if (!targetProject) {
      const newProjectId = genId();
      const initialPos = getProjectMacroPosition(
        { id: newProjectId, name: projectName },
        projectsRef.current.length,
        projectsRef.current.length + 1,
      );
      const newProj: Projekt = {
        id: newProjectId,
        name: projectName,
        x: initialPos.x,
        y: initialPos.y,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const b = window.cortexBridge;
      if (b?.projSaveProject) {
        await b.projSaveProject({ project: newProj });
      }

      const updated = [...projectsRef.current, newProj];
      projectsRef.current = updated;
      setProjects(updated);

      const nodesToMigrate =
        connectedNodes && connectedNodes.length > 0
          ? connectedNodes
          : getTransitiveConnectedNodes(portalNode.id, nodesRef.current, edgesRef.current);

      if (nodesToMigrate.length > 0) {
        const idMap = new Map<string, string>();
        let minX = Infinity;
        let minY = Infinity;
        for (const n of nodesToMigrate) {
          if (n.x < minX) minX = n.x;
          if (n.y < minY) minY = n.y;
        }
        if (minX === Infinity) {
          minX = 0;
          minY = 0;
        }

        const migratedNodes: ProjektyNode[] = nodesToMigrate.map((n) => {
          const newId = genId();
          idMap.set(n.id, newId);
          return {
            ...n,
            id: newId,
            project_id: newProjectId,
            parent_id: null,
            x: n.x - minX + 150,
            y: n.y - minY + 150,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
        });

        const currentEdges = edgesRef.current;
        const internalEdges: ProjektyEdge[] = currentEdges
          .filter((e) => idMap.has(e.source_node_id) && idMap.has(e.target_node_id))
          .map((e) => ({
            ...e,
            id: genId(),
            project_id: newProjectId,
            source_node_id: idMap.get(e.source_node_id)!,
            target_node_id: idMap.get(e.target_node_id)!,
            created_at: new Date().toISOString(),
          }));

        // Zapisz w nowym projekcie
        for (const n of migratedNodes) {
          await saveNode(n);
        }
        for (const e of internalEdges) {
          await saveEdge(e);
        }

        // Usuń przeniesione notatki ze źródłowej tablicy
        const deletedNodeIds = new Set(nodesToMigrate.map((n) => n.id));
        const edgesToDelete = currentEdges.filter(
          (e) => deletedNodeIds.has(e.source_node_id) || deletedNodeIds.has(e.target_node_id)
        );

        for (const e of edgesToDelete) {
          if (b?.projDeleteEdge) {
            await b.projDeleteEdge({ id: e.id });
          }
        }

        for (const n of nodesToMigrate) {
          if (b?.projDeleteNode) {
            await b.projDeleteNode({ id: n.id });
          }
        }

        const remainingNodes = nodesRef.current.filter((n) => !deletedNodeIds.has(n.id));
        const remainingEdges = edgesRef.current.filter(
          (e) => !deletedNodeIds.has(e.source_node_id) && !deletedNodeIds.has(e.target_node_id)
        );
        nodesRef.current = remainingNodes;
        edgesRef.current = remainingEdges;
        setNodes(remainingNodes);
        setEdges(remainingEdges);
      }

      const updatedPortal: ProjektyNode = {
        ...portalNode,
        metadata: {
          ...(typeof portalNode.metadata === 'object' && portalNode.metadata !== null ? portalNode.metadata : {}),
          target_project_id: newProjectId,
        },
      };
      await saveNode(updatedPortal);
      targetProjectId = newProjectId;
    }

    if (targetProjectId) {
      await handleSwitchProject(targetProjectId);
    }
  };

  // --- notatki -------------------------------------------------------------
  const addNoteAt = async (pos: { x: number; y: number }) => {
    const node: ProjektyNode = {
      id: genId(),
      project_id: activeProjectIdRef.current,
      title: '',
      content: '',
      node_type: 'note',
      parent_id: currentBoardParentId(),
      x: pos.x - NODE_WIDTH / 2,
      y: pos.y - NODE_HEIGHT / 2,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      created_at: new Date().toISOString(),
    };

    cancelEditRef.current = false;
    setNodes((prev) => [...prev, node]);
    nodesRef.current = [...nodesRef.current, node];
    selectNode(node.id);
    editingNodeIdRef.current = node.id;
    setEditingNodeId(node.id);
    editingTextRef.current = '';
    setEditingText('');
    await saveNode(node);
  };

  // Tworzy nową notatkę obok zaznaczonych, od razu połączoną krawędzią (wywoływane z Tab w textarea)
  const createLinkedNoteNextTo = async (sourceIds: string[]) => {
    const sources = sourceIds.map((id) => nodesRef.current.find((n) => n.id === id)).filter(Boolean) as ProjektyNode[];
    if (sources.length === 0) return;

    // Granice widocznego obszaru w układzie canvasu
    const rect = canvasRef.current?.getBoundingClientRect();
    let bounds: { minX: number; minY: number; maxX: number; maxY: number } | undefined;
    if (rect) {
      const tl = screenToCanvas(rect.left, rect.top);
      const br = screenToCanvas(rect.left + rect.width, rect.top + rect.height);
      bounds = {
        minX: Math.min(tl.x, br.x),
        minY: Math.min(tl.y, br.y),
        maxX: Math.max(tl.x, br.x),
        maxY: Math.max(tl.y, br.y),
      };
    }

    // Pozycja: optymalne wolne miejsce wokół źródła z uwzględnieniem rzeczywistych wymiarów DOM kart
    const pos = findSpotNear(sources[0], visibleNodes, bounds, undefined, cardElRefs.current);

    const node: ProjektyNode = {
      id: genId(),
      project_id: activeProjectIdRef.current,
      title: sources[0].title || '',
      content: '',
      node_type: 'note',
      parent_id: currentBoardParentId(),
      x: pos.x,
      y: pos.y,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      created_at: new Date().toISOString(),
    };

    cancelEditRef.current = false;
    setNodes((prev) => [...prev, node]);
    nodesRef.current = [...nodesRef.current, node];
    selectNode(node.id);
    editingNodeIdRef.current = node.id;
    setEditingNodeId(node.id);
    editingTextRef.current = '';
    setEditingText('');
    ensureNodeVisible(node);
    await saveNode(node);

    // Połącz z ostatnim źródłem (lub wszystkimi, jeśli pojedyncze — dla prostoty jedno źródło)
    const source = sources[sources.length - 1];
    if (source) {
      const edge: ProjektyEdge = {
        id: genId(),
        project_id: activeProjectIdRef.current,
        source_node_id: source.id,
        target_node_id: node.id,
        relation_type: 'depends_on',
        created_at: new Date().toISOString(),
      };
      setEdges((prev) => [...prev, edge]);
      edgesRef.current = [...edgesRef.current, edge];
      void saveEdge(edge);
    }
  };

  const createNote = async (e: ReactMouseEvent) => {
    const target = e.target as HTMLElement;
    if (target !== canvasRef.current && target.dataset?.canvas !== 'bg') return;
    const pos = screenToCanvas(e.clientX, e.clientY);
    if (viewModeRef.current === 'projects' || scaleRef.current < ZOOM_MACRO_THRESHOLD) {
      await addProjectInMacroView(pos);
    } else {
      await addNoteAt(pos);
    }
  };

  const onCardMouseDown = (node: ProjektyNode, e: ReactMouseEvent) => {
    // Środkowy (1) lub prawy (2) przycisk myszy — przesuwanie płótna
    if (e.button === 1 || e.button === 2) {
      e.preventDefault();
      panRef.current = {
        startX: e.clientX - offsetRef.current.x,
        startY: e.clientY - offsetRef.current.y,
      };
      setIsPanning(true);
      return;
    }

    e.stopPropagation();
    if (linkingModeRef.current) {
      return;
    }
    // F2: Ctrl+klik otwiera pod-tablicę notatki
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      openSubBoard(node.id);
      return;
    }
    dragRef.current = {
      id: node.id,
      startX: e.clientX,
      startY: e.clientY,
      nx: node.x,
      ny: node.y,
      moved: false,
      shiftKey: e.shiftKey,
    };
  };

  const onHeaderMouseDown = (node: ProjektyNode, e: ReactMouseEvent) => {
    // Środkowy (1) lub prawy (2) przycisk myszy — przesuwanie płótna
    if (e.button === 1 || e.button === 2) {
      e.preventDefault();
      panRef.current = {
        startX: e.clientX - offsetRef.current.x,
        startY: e.clientY - offsetRef.current.y,
      };
      setIsPanning(true);
      return;
    }

    e.stopPropagation();
    if (linkingModeRef.current) {
      return;
    }
    dragRef.current = {
      id: node.id,
      startX: e.clientX,
      startY: e.clientY,
      nx: node.x,
      ny: node.y,
      moved: false,
    };
  };

  // --- łączenie notatek ----------------------------------------------------
  const handleNodeLinkingClick = async (nodeId: string) => {
    const sourceId = linkSourceIdRef.current;

    if (!sourceId) {
      setLinking(true, nodeId);
      return;
    }

    if (sourceId === nodeId) {
      // Kliknięcie na tę samą notatkę odznacza źródło
      setLinking(true, null);
      return;
    }

    const currentEdges = edgesRef.current;
    const exists = currentEdges.some(
      (e) =>
        (e.source_node_id === sourceId && e.target_node_id === nodeId) ||
        (e.source_node_id === nodeId && e.target_node_id === sourceId),
    );

    if (!exists) {
      const edge: ProjektyEdge = {
        id: genId(),
        project_id: activeProjectIdRef.current,
        source_node_id: sourceId,
        target_node_id: nodeId,
        relation_type: 'depends_on',
        created_at: new Date().toISOString(),
      };

      setEdges((prev) => [...prev, edge]);
      edgesRef.current = [...edgesRef.current, edge];
      void saveEdge(edge);
    }

    // Zakończ łączenie i zaznacz notatkę docelową
    setLinking(false, null);
    selectNode(nodeId);
  };

  const handleSaveClusterDescription = useCallback(async (clusterKey: string, description: string, nodeIds?: string[]) => {
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (!curProj) return;

    // Przypisujemy opis do wszystkich węzłów w klastrze (gwarancja przetrwania nazwy przy usuwaniu/edycji notatek)
    const targetIds = nodeIds && nodeIds.length > 0 ? Array.from(new Set([clusterKey, ...nodeIds])) : [clusterKey];
    const nextDescriptions = { ...(curProj.cluster_descriptions || {}) };

    if (description) {
      for (const id of targetIds) {
        nextDescriptions[id] = description;
      }
    } else {
      for (const id of targetIds) {
        delete nextDescriptions[id];
      }
    }

    const updatedProj: Projekt = {
      ...curProj,
      cluster_descriptions: nextDescriptions,
      updated_at: new Date().toISOString(),
    };

    setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
    projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));

    const b = window.cortexBridge;
    if (b?.projSaveProject) {
      try {
        await b.projSaveProject({ project: updatedProj });
      } catch (err) {
        console.error('[NotesCanvas] Failed to save cluster description', err);
      }
    }
  }, []);

  // Metody zarzadzania klamrami semantycznymi (CAD Brackets)
  const handleCreateBracket = useCallback(async (nodeIds: string[], customName?: string, forcedOrientation?: 'horizontal' | 'vertical') => {
    if (nodeIds.length < 2) return;
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (!curProj) return;

    // 1. Auto-teleportacja i dosuwanie klastrów z odstępem 20px (CAD Auto-Packing)
    const curNodes = nodesRef.current;
    const curEdges = edgesRef.current;
    const curDescriptions = curProj.cluster_descriptions || {};

    const packResult = teleportAndPackBracketClusters(
      nodeIds,
      curNodes,
      curEdges,
      curDescriptions,
      forcedOrientation,
      20,
      28
    );

    // Zapisanie przesuniętych węzłów
    if (packResult.movedNodesMap.size > 0) {
      setNodes(packResult.updatedNodes);
      nodesRef.current = packResult.updatedNodes;
      for (const nodeId of packResult.movedNodesMap.keys()) {
        const fullNode = packResult.updatedNodes.find((n) => n.id === nodeId);
        if (fullNode) {
          void saveNode(fullNode);
        }
      }
    }

    // Synchronizacja opisów klastrów dla wszystkich węzłów w powiązanych klastrach
    const allMemberClusters = computeConnectedComponents(curNodes, curEdges, curDescriptions);
    const nextDescriptions = { ...curDescriptions };
    const allBracketNodeIds = new Set<string>(nodeIds);

    allMemberClusters.forEach((cl) => {
      if (cl.some((n) => nodeIds.includes(n.id))) {
        const desc = cl.map((n) => curDescriptions[n.id]).find((d) => d && d.trim());
        if (desc) {
          cl.forEach((n) => {
            nextDescriptions[n.id] = desc;
            allBracketNodeIds.add(n.id);
          });
        }
      }
    });

    const newBracket: ProjektyBracket = {
      id: genId(),
      project_id: curProj.id,
      name: customName || '',
      node_ids: Array.from(allBracketNodeIds),
      orientation: packResult.orientation,
      created_at: new Date().toISOString(),
    };

    const nextBrackets = [...(curProj.brackets || []), newBracket];
    const updatedProj: Projekt = {
      ...curProj,
      cluster_descriptions: nextDescriptions,
      brackets: nextBrackets,
      updated_at: new Date().toISOString(),
    };

    setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
    projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));

    const b = window.cortexBridge;
    if (b?.projSaveProject) {
      try {
        await b.projSaveProject({ project: updatedProj });
      } catch (err) {
        console.error('[NotesCanvas] Failed to save bracket', err);
      }
    }
  }, []);

  const handlePackBracket = useCallback(async (bracketId: string, forcedOrientation?: 'horizontal' | 'vertical') => {
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (!curProj || !curProj.brackets) return;
    const bracket = curProj.brackets.find((b) => b.id === bracketId);
    if (!bracket) return;

    const curNodes = nodesRef.current;
    const curEdges = edgesRef.current;
    const curDescriptions = curProj.cluster_descriptions || {};

    const packResult = teleportAndPackBracketClusters(
      bracket.node_ids,
      curNodes,
      curEdges,
      curDescriptions,
      forcedOrientation || (bracket.orientation === 'auto' ? undefined : bracket.orientation),
      20,
      28
    );

    if (packResult.movedNodesMap.size > 0) {
      setNodes(packResult.updatedNodes);
      nodesRef.current = packResult.updatedNodes;
      for (const nodeId of packResult.movedNodesMap.keys()) {
        const fullNode = packResult.updatedNodes.find((n) => n.id === nodeId);
        if (fullNode) {
          void saveNode(fullNode);
        }
      }
    }

    if (forcedOrientation && forcedOrientation !== bracket.orientation) {
      const nextBrackets = curProj.brackets.map((b) =>
        b.id === bracketId ? { ...b, orientation: forcedOrientation } : b
      );
      const updatedProj: Projekt = {
        ...curProj,
        brackets: nextBrackets,
        updated_at: new Date().toISOString(),
      };
      setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
      projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));
      void window.cortexBridge?.projSaveProject?.({ project: updatedProj });
    }
  }, []);

  const handleDeleteBracket = useCallback(async (bracketId: string) => {
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (!curProj || !curProj.brackets) return;

    const nextBrackets = curProj.brackets.filter((b) => b.id !== bracketId);
    const updatedProj: Projekt = {
      ...curProj,
      brackets: nextBrackets,
      updated_at: new Date().toISOString(),
    };

    setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
    projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));

    const b = window.cortexBridge;
    if (b?.projSaveProject) {
      try {
        await b.projSaveProject({ project: updatedProj });
      } catch (err) {
        console.error('[NotesCanvas] Failed to delete bracket', err);
      }
    }
  }, []);

  const handleRenameBracket = useCallback(async (bracketId: string, newName: string) => {
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (!curProj || !curProj.brackets) return;

    const nextBrackets = curProj.brackets.map((b) => (b.id === bracketId ? { ...b, name: newName } : b));
    const updatedProj: Projekt = {
      ...curProj,
      brackets: nextBrackets,
      updated_at: new Date().toISOString(),
    };

    setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
    projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));

    const b = window.cortexBridge;
    if (b?.projSaveProject) {
      try {
        await b.projSaveProject({ project: updatedProj });
      } catch (err) {
        console.error('[NotesCanvas] Failed to rename bracket', err);
      }
    }
  }, []);

  const handleRotateBracket = useCallback(async (bracketId: string) => {
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    if (!curProj || !curProj.brackets) return;
    const bracket = curProj.brackets.find((b) => b.id === bracketId);
    if (!bracket) return;

    // Klamra przeskakuje na przeciwną stronę w tej samej osi:
    // lewa ↔ prawa, góra ↔ dół. Przy braku `side` ustalamy domyślną stronę
    // z orientacji (vertical -> left, horizontal -> top).
    const isVertical = bracket.orientation !== 'horizontal';
    const currentSide: 'left' | 'right' | 'top' | 'bottom' =
      bracket.side ?? (isVertical ? 'left' : 'top');

    let nextSide: 'left' | 'right' | 'top' | 'bottom';
    if (isVertical) {
      nextSide = currentSide === 'left' ? 'right' : 'left';
    } else {
      nextSide = currentSide === 'top' ? 'bottom' : 'top';
    }

    const nextBrackets = curProj.brackets.map((b) =>
      b.id === bracketId
        ? { ...b, side: nextSide, orientation: (isVertical ? 'vertical' : 'horizontal') as ProjektyBracket['orientation'] }
        : b
    );
    const updatedProj: Projekt = {
      ...curProj,
      brackets: nextBrackets,
      updated_at: new Date().toISOString(),
    };

    setProjects((prev) => prev.map((p) => (p.id === updatedProj.id ? updatedProj : p)));
    projectsRef.current = projectsRef.current.map((p) => (p.id === updatedProj.id ? updatedProj : p));

    // Dosuń klastry klamry do siebie (przyleganie 20px) i wyrównaj do strony klamry.
    const packResult = teleportAndPackBracketClusters(
      bracket.node_ids,
      nodesRef.current,
      edgesRef.current,
      curProj.cluster_descriptions || {},
      isVertical ? 'vertical' : 'horizontal',
      20,
      28,
      nextSide
    );
    if (packResult.movedNodesMap.size > 0) {
      setNodes(packResult.updatedNodes);
      nodesRef.current = packResult.updatedNodes;
      for (const nodeId of packResult.movedNodesMap.keys()) {
        const fullNode = packResult.updatedNodes.find((n) => n.id === nodeId);
        if (fullNode) void saveNode(fullNode);
      }
    }

    const b = window.cortexBridge;
    if (b?.projSaveProject) {
      try {
        await b.projSaveProject({ project: updatedProj });
      } catch (err) {
        console.error('[NotesCanvas] Failed to rotate bracket', err);
      }
    }
  }, []);

  const handleCreateBracketFromSelection = useCallback(() => {
    const sel = selectedIdsRef.current;
    if (sel.length < 2) return;

    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    const curNodes = nodesRef.current;
    const curEdges = edgesRef.current;
    const curDescriptions = curProj?.cluster_descriptions || {};

    const packCheck = teleportAndPackBracketClusters(
      sel,
      curNodes,
      curEdges,
      curDescriptions,
      undefined,
      20,
      28
    );

    setNewBracketInput('');
    setCreateBracketModal({
      nodeIds: sel,
      orientation: packCheck.orientation,
      clusterCount: packCheck.clusterCount,
    });
  }, []);

  const handleConfirmCreateBracket = useCallback(() => {
    if (!createBracketModal) return;
    const name = newBracketInput.trim();
    void handleCreateBracket(createBracketModal.nodeIds, name, createBracketModal.orientation);
    setCreateBracketModal(null);
  }, [createBracketModal, newBracketInput, handleCreateBracket]);

  const handleOpenBracketContextMenu = useCallback((bracketId: string, e: ReactMouseEvent) => {
    const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
    const bracket = curProj?.brackets?.find((b) => b.id === bracketId);
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      type: 'bracket',
      targetId: bracketId,
      bracketName: bracket?.name || 'Oznaczenia',
    });
  }, []);

  const handleCanvasContextMenu = useCallback((e: ReactMouseEvent) => {
    e.preventDefault();
    const sel = selectedIdsRef.current;
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      type: 'selection',
      selectedCount: sel.length,
    });
  }, []);

  // Przesuwanie i zaznaczanie klastrów na tablicy (obsługa Shift+klik dla wielu klastrów)
  const handleStartDragCluster = useCallback((clusterNodes: ProjektyNode[], e: ReactMouseEvent) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const nodeIds = clusterNodes.map((n) => n.id);
    const cur = selectedIdsRef.current;

    let nextSel: string[];
    if (e.shiftKey) {
      // Toggle klastra w selekcji grupowej
      const allInCur = nodeIds.every((id) => cur.includes(id));
      nextSel = allInCur
        ? cur.filter((id) => !nodeIds.includes(id))
        : Array.from(new Set([...cur, ...nodeIds]));
    } else {
      // Zwykły klik: jeśli klaster już jest częścią większego zaznaczenia, zachowaj całą grupę
      const isPart = nodeIds.every((id) => cur.includes(id)) && cur.length > nodeIds.length;
      nextSel = isPart ? cur : nodeIds;
    }

    setSelectedIds(nextSel);
    selectedIdsRef.current = nextSel;
    selectedNodeIdRef.current = nextSel.length === 1 ? nextSel[0] : null;
    setSelectedNodeId(nextSel.length === 1 ? nextSel[0] : null);

    const allSelectedNodes = nodesRef.current.filter((n) => nextSel.includes(n.id));
    dragRef.current = {
      id: clusterNodes[0].id,
      startX: e.clientX,
      startY: e.clientY,
      nx: clusterNodes[0].x,
      ny: clusterNodes[0].y,
      moved: false,
      group: allSelectedNodes.map((n) => ({ id: n.id, x: n.x, y: n.y })),
    };
  }, []);

  const handleOpenClusterContextMenu = useCallback((clusterNodes: ProjektyNode[], e: ReactMouseEvent) => {
    const nodeIds = clusterNodes.map((n) => n.id);
    const cur = selectedIdsRef.current;
    let nextSel = cur;
    if (!nodeIds.every((id) => cur.includes(id))) {
      nextSel = e.shiftKey ? Array.from(new Set([...cur, ...nodeIds])) : nodeIds;
      setSelectedIds(nextSel);
      selectedIdsRef.current = nextSel;
      selectedNodeIdRef.current = nextSel.length === 1 ? nextSel[0] : null;
      setSelectedNodeId(nextSel.length === 1 ? nextSel[0] : null);
    }

    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      type: 'selection',
      selectedCount: nextSel.length,
    });
  }, []);

  // Szybkie tworzenie klastra (z zaznaczonych notatek lub nowego)
  const handleCreateCluster = useCallback(async () => {
    const sel = selectedIdsRef.current;
    if (sel.length >= 2) {
      const currentEdges = edgesRef.current;
      for (let i = 0; i < sel.length - 1; i++) {
        const a = sel[i];
        const b = sel[i + 1];
        const exists = currentEdges.some(
          (e) => (e.source_node_id === a && e.target_node_id === b) || (e.source_node_id === b && e.target_node_id === a)
        );
        if (!exists) {
          const edge: ProjektyEdge = {
            id: genId(),
            project_id: activeProjectIdRef.current,
            source_node_id: a,
            target_node_id: b,
            relation_type: 'depends_on',
            created_at: new Date().toISOString(),
          };
          setEdges((prev) => [...prev, edge]);
          edgesRef.current = [...edgesRef.current, edge];
          void saveEdge(edge);
        }
      }
      const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
      if (curProj && !curProj.cluster_descriptions?.[sel[0]]) {
        void handleSaveClusterDescription(sel[0], 'Nowy klaster');
      }
    } else if (sel.length === 1) {
      void handleSaveClusterDescription(sel[0], 'Nowy klaster');
    } else {
      const rect = canvasRef.current?.getBoundingClientRect();
      const cx = rect ? rect.width / 2 : 400;
      const cy = rect ? rect.height / 2 : 300;
      const pos = screenToCanvas(cx, cy);

      const n1: ProjektyNode = {
        id: genId(),
        project_id: activeProjectIdRef.current,
        title: '',
        content: 'Pierwsza myśl klastra',
        node_type: 'note',
        x: pos.x - 140,
        y: pos.y,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        created_at: new Date().toISOString(),
      };
      const n2: ProjektyNode = {
        id: genId(),
        project_id: activeProjectIdRef.current,
        title: '',
        content: 'Druga myśl w klastrze',
        node_type: 'note',
        x: pos.x + 140,
        y: pos.y,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        created_at: new Date().toISOString(),
      };
      const edge: ProjektyEdge = {
        id: genId(),
        project_id: activeProjectIdRef.current,
        source_node_id: n1.id,
        target_node_id: n2.id,
        relation_type: 'depends_on',
        created_at: new Date().toISOString(),
      };

      setNodes((prev) => [...prev, n1, n2]);
      nodesRef.current = [...nodesRef.current, n1, n2];
      setEdges((prev) => [...prev, edge]);
      edgesRef.current = [...edgesRef.current, edge];
      await saveNode(n1);
      await saveNode(n2);
      await saveEdge(edge);
      void handleSaveClusterDescription(n1.id, 'Nowy klaster');
    }
  }, [handleSaveClusterDescription]);

  const activeProject = projects.find((p) => p.id === activeProjectId) || projects[0];

  // --- render --------------------------------------------------------------
  return (
    <div className="h-screen w-screen flex flex-col bg-slate-100 dark:bg-[#101010] text-slate-900 dark:text-[#eeeeee] overflow-hidden select-none transition-colors duration-200">
      {/* Pasek statusu łączenia — pływający banner pod nagłówkiem (mikro) */}
      {linkingMode && (
        <div
          className="absolute top-16 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-3.5 py-1.5 rounded-full shadow-lg backdrop-blur-xl animate-in fade-in slide-in-from-top-2 duration-150"
          style={{
            backgroundColor: theme === 'dark' ? 'rgba(22, 22, 22, 0.96)' : 'rgba(248, 250, 252, 0.96)',
            borderColor: theme === 'dark' ? '#2c2c2c' : 'rgba(203, 213, 225, 0.9)',
            borderWidth: '1px',
            borderStyle: 'solid',
          }}
        >
          <span className="w-2 h-2 rounded-full bg-[#FFC799] animate-ping" />
          <span className={`text-xs font-medium ${theme === 'dark' ? 'text-[#eeeeee]' : 'text-slate-700'}`}>
            {linkSourceId
              ? 'Kliknij notatkę docelową, aby połączyć'
              : 'Kliknij pierwszą notatkę (źródło połączenia)'}
          </span>
          <button
            tabIndex={-1}
            onClick={() => setLinking(false, null)}
            className="ml-1 text-[11px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-[#222222] hover:bg-slate-300 dark:hover:bg-[#2a2a2a] text-slate-800 dark:text-[#cccccc] transition-colors cursor-pointer border dark:border-[#2e2e2e]"
          >
            Anuluj (Esc)
          </button>
        </div>
      )}

      {/* Pasek statusu łączenia w widoku makro (klastry / klamry) */}
      {isMacroView && macroClusterLinkSource && (
        <div
          data-testid="macro-cluster-linking-banner"
          className="absolute top-16 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-3.5 py-1.5 rounded-full shadow-lg backdrop-blur-xl animate-in fade-in slide-in-from-top-2 duration-150"
          style={{
            backgroundColor: theme === 'dark' ? 'rgba(22, 22, 22, 0.96)' : 'rgba(248, 250, 252, 0.96)',
            borderColor: theme === 'dark' ? '#2c2c2c' : 'rgba(203, 213, 225, 0.9)',
            borderWidth: '1px',
            borderStyle: 'solid',
          }}
        >
          <span className="w-2 h-2 rounded-full bg-[#FFC799] animate-ping" />
          <span className={`text-xs font-medium ${theme === 'dark' ? 'text-[#eeeeee]' : 'text-slate-700'}`}>
            Łączenie:{' '}
            <strong className="text-[#FFC799]">{macroClusterLinkSource.label || 'Obiekt'}</strong> → Kliknij cel (inny klaster, klamrę lub projekt)
          </span>
          <button
            tabIndex={-1}
            onClick={() => setMacroClusterLinking(false, null)}
            className="ml-1 text-[11px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-[#222222] hover:bg-slate-300 dark:hover:bg-[#2a2a2a] text-slate-800 dark:text-[#cccccc] transition-colors cursor-pointer border dark:border-[#2e2e2e]"
          >
            Anuluj (Esc)
          </button>
        </div>
      )}

      {/* Pasek statusu łączenia projektów w widoku makro */}
      {isMacroView && macroLinkingMode && macroLinkSourceId && (
        <div
          data-testid="macro-project-linking-banner"
          className="absolute top-16 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-3.5 py-1.5 rounded-full shadow-lg backdrop-blur-xl animate-in fade-in slide-in-from-top-2 duration-150"
          style={{
            backgroundColor: theme === 'dark' ? 'rgba(22, 22, 22, 0.96)' : 'rgba(248, 250, 252, 0.96)',
            borderColor: theme === 'dark' ? '#2c2c2c' : 'rgba(203, 213, 225, 0.9)',
            borderWidth: '1px',
            borderStyle: 'solid',
          }}
        >
          <span className="w-2 h-2 rounded-full bg-[#FFC799] animate-ping" />
          <span className={`text-xs font-medium ${theme === 'dark' ? 'text-[#eeeeee]' : 'text-slate-700'}`}>
            Łączenie projektów → Kliknij projekt docelowy
          </span>
          <button
            tabIndex={-1}
            onClick={() => setMacroLinking(false, null)}
            className="ml-1 text-[11px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-[#222222] hover:bg-slate-300 dark:hover:bg-[#2a2a2a] text-slate-800 dark:text-[#cccccc] transition-colors cursor-pointer border dark:border-[#2e2e2e]"
          >
            Anuluj (Esc)
          </button>
        </div>
      )}

      {/* Pasek narzędzi — zwarty, wycentrowany panel pływający */}
      <CanvasHeader
        theme={theme}
        isMacroView={isMacroView}
        activeProject={activeProject}
        projects={projects}
        groups={groups}
        activeProjectId={activeProjectId}
        isProjectMenuOpen={isProjectMenuOpen}
        setIsProjectMenuOpen={setIsProjectMenuOpen}
        projectMenuRef={projectMenuRef}
        editingProjectId={editingProjectId}
        editingProjectName={editingProjectName}
        setEditingProjectId={setEditingProjectId}
        setEditingProjectName={setEditingProjectName}
        handleSwitchProject={handleSwitchProject}
        handleCreateProject={handleCreateProject}
        handleStartRename={handleStartRename}
        handleSaveRename={handleSaveRename}
        handleDeleteProject={handleDeleteProject}
        onToggleGroupCollapse={handleToggleGroupCollapse}
        onCreateGroup={handleCreateGroup}
        onDeleteGroup={handleDeleteGroup}
        onMoveProject={handleMoveProject}
        zoomToMacroView={zoomToMacroView}
        boardPath={boardPath}
        breadcrumbNodes={breadcrumbNodes}
        goToBoardLevel={goToBoardLevel}
        parentId={parentId}
        zoomBy={zoomBy}
        resetView={resetView}
        scale={scale}
        showHelp={showHelp}
        setShowHelp={setShowHelp}
        liveTrackingEnabled={liveTrackingEnabled}
        setLiveTrackingEnabled={setLiveTrackingEnabled}
      />

      {/* obszar roboczy */}
      <div
        ref={canvasRef}
        data-testid="canvas-container"
        className="flex-1 relative overflow-hidden transition-colors duration-200"
        style={{
          cursor: isPanning || draggingNodeId ? 'grabbing' : placementMode || linkingMode ? 'crosshair' : 'default',
          background: theme === 'dark' ? '#101010' : '#dbe1ea',
        }}
        onContextMenu={handleCanvasContextMenu}
        onMouseDown={onCanvasMouseDown}
        onDoubleClick={createNote}
      >
        {/* tło z siatką */}
        <div
          data-canvas="bg"
          className="absolute inset-0"
          style={{
            backgroundImage: `radial-gradient(${theme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(100, 116, 139, 0.45)'} ${1.75 * scale}px, transparent 0)`,
            backgroundSize: `${32 * scale}px ${32 * scale}px`,
            backgroundPosition: `${offset.x}px ${offset.y}px`,
          }}
        />

        {/* mikro-szum SVG (matowa tekstura papieru) */}
        <div
          data-canvas="grain"
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: `url("${NOISE_DATA_URI}")`,
            backgroundSize: '200px 200px',
            mixBlendMode: theme === 'dark' ? 'overlay' : 'multiply',
            opacity: theme === 'dark' ? 0.035 : 0.02,
          }}
        />

        {/* winieta skupienia — delikatnie domyka krawędzie */}
        <div
          data-canvas="vignette"
          className="absolute inset-0 pointer-events-none"
          style={{
            background: theme === 'dark'
              ? 'radial-gradient(ellipse at center, transparent 35%, rgba(0, 0, 0, 0.55) 100%)'
              : 'radial-gradient(ellipse at center, transparent 45%, rgba(15, 23, 42, 0.07) 100%)',
          }}
        />

        {/* świat (przesuwany i skalowany) */}
        <div
          className="absolute inset-0"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            transformOrigin: '0 0',
            pointerEvents: 'none',
          }}
        >
          {/* Warstwa automatycznych stref połączonych klocków (Islands) */}
          <ConnectedIslandsLayer
            theme={theme}
            isMacroView={isMacroView}
            visibleNodes={visibleNodes}
            visibleEdges={visibleEdges}
            scale={scale}
            clusterDescriptions={activeProject?.cluster_descriptions || {}}
            brackets={activeProject?.brackets || []}
            selectedNodeIds={selectedIds}
            onSaveClusterDescription={handleSaveClusterDescription}
            onStartDragCluster={handleStartDragCluster}
            onOpenClusterContextMenu={handleOpenClusterContextMenu}
          />

          {/* Warstwa klamer semantycznych CAD */}
          <BracketsLayer
            isMacroView={isMacroView}
            brackets={activeProject?.brackets || []}
            visibleNodes={visibleNodes}
            visibleEdges={visibleEdges}
            clusterDescriptions={activeProject?.cluster_descriptions || {}}
            scale={scale}
            onRenameBracket={handleRenameBracket}
            onDeleteBracket={handleDeleteBracket}
            onRotateBracket={handleRotateBracket}
            onOpenBracketContextMenu={handleOpenBracketContextMenu}
          />

          {/* Warstwa linii połączeń SVG */}
          <ConnectionLinesLayer
            theme={theme}
            isMacroView={isMacroView}
            isClusterView={isClusterView}
            visibleEdges={visibleEdges}
            visibleNodes={visibleNodes}
            deleteEdge={deleteEdge}
            toggleEdgeArrow={handleToggleEdgeArrow}
            linkingMode={linkingMode}
            linkSourceId={linkSourceId}
            mouseCanvasPos={mouseCanvasPos}
            macroEdges={macroEdges}
            projects={projects}
            deleteMacroEdge={deleteMacroEdge}
            toggleMacroEdgeArrow={toggleMacroEdgeArrow}
            macroLinkingMode={macroLinkingMode}
            macroLinkSourceId={macroLinkSourceId}
          />

          {/* Ramka zaznaczania (marquee) */}
          {marquee && (() => {
            const x = Math.min(marquee.x1, marquee.x2);
            const y = Math.min(marquee.y1, marquee.y2);
            const w = Math.abs(marquee.x2 - marquee.x1);
            const h = Math.abs(marquee.y2 - marquee.y1);
            return (
              <div
                className={`absolute pointer-events-none ${
                  theme === 'dark'
                    ? 'border border-[#FFC799] bg-[rgba(255,199,153,0.1)]'
                    : 'border border-blue-500 bg-blue-500/10'
                }`}
                style={{ left: x, top: y, width: w, height: h }}
              />
            );
          })()}

          {/* Ghost preview klocka projektu w trybie stawiania */}
          {placementMode && mouseCanvasPos && (
            <div
              className="absolute pointer-events-none rounded-2xl border-2 border-dashed flex items-center justify-center px-4 py-2 shadow-2xl"
              style={{
                left: mouseCanvasPos.x - PROJECT_CARD_WIDTH / 2,
                top: mouseCanvasPos.y - PROJECT_CARD_HEIGHT / 2,
                width: PROJECT_CARD_WIDTH,
                height: PROJECT_CARD_HEIGHT,
                borderColor: theme === 'dark' ? '#FFC799' : 'rgba(71, 85, 105, 0.8)',
                backgroundColor: theme === 'dark' ? 'rgba(22, 22, 22, 0.85)' : 'rgba(241, 245, 249, 0.75)',
                backdropFilter: 'blur(8px)',
                zIndex: 1000,
              }}
            >
              <p className={`text-xs font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-800'}`}>
                Kliknij, aby postawić projekt
              </p>
            </div>
          )}

          {/* Widok Makro: Wszystkie Projekty */}
          {isMacroView ? (
            <CanvasErrorBoundary fallbackTitle="Błąd w widoku makro projektów">
              <div className="absolute inset-0 pointer-events-none">
                <MacroClusterLinksLayer
                  theme={theme}
                  projects={projects}
                  links={macroClusterLinks}
                  onDeleteLink={deleteMacroClusterLink}
                  selectedLinkId={selectedMacroClusterLinkId}
                  onSelectLink={setSelectedMacroClusterLinkId}
                  macroClusterLinkSource={macroClusterLinkSource}
                  mouseCanvasPos={mouseCanvasPos}
                />
                {projects.map((proj, idx) => (
                  <MacroProjectCard
                    key={proj.id}
                    proj={proj}
                    idx={idx}
                    projects={projects}
                    projectStats={projectStats}
                    activeProjectId={activeProjectId}
                    selectedProjectId={selectedProjectId}
                    macroLinkingMode={macroLinkingMode}
                    macroLinkSourceId={macroLinkSourceId}
                    editingProjectId={editingProjectId}
                    editingProjectName={editingProjectName}
                    draggingMacroProjId={draggingMacroProjId}
                    theme={theme}
                    nodesCount={nodes.length}
                    setEditingProjectName={setEditingProjectName}
                    handleSaveRename={handleSaveRename}
                    setEditingProjectId={setEditingProjectId}
                    handleStartRename={handleStartRename}
                    handleDeleteProject={handleDeleteProject}
                    diveIntoProject={diveIntoProject}
                    startDraggingMacroProject={startDraggingMacroProject}
                    connectProjects={connectProjects}
                    setMacroLinking={setMacroLinking}
                    setSelectedProjectId={setSelectedProjectId}
                    scale={scale}
                    onUpdateClusterOffset={handleUpdateClusterOffset}
                    macroSelectedClusterRef={macroSelectedClusterRef}
                    macroClusterLinkSource={macroClusterLinkSource}
                    onSelectCluster={selectMacroCluster}
                    onClickClusterLink={handleMacroClusterLinkingClick}
                  />
                ))}
              </div>
            </CanvasErrorBoundary>
          ) : (
            <>
              {/* Karty notatek i portali */}
              {visibleNodes.map((node) => {
                const isSource = linkSourceId === node.id;
                const isSelectedNode = selectedIds.includes(node.id);
                const isEditing = editingNodeId === node.id;

                if (node.node_type === 'portal') {
                  return (
                    <PortalCard
                      key={node.id}
                      node={node}
                      visibleNodes={visibleNodes}
                      edges={edges}
                      isSource={isSource}
                      isSelected={isSelectedNode}
                      isEditing={isEditing}
                      draggingNodeId={draggingNodeId}
                      theme={theme}
                      linkingMode={linkingMode}
                      cardElRefs={cardElRefs}
                      editingText={editingText}
                      setEditingText={setEditingText}
                      editingTextRef={editingTextRef}
                      startEditing={startEditing}
                      commitEditing={commitEditing}
                      cancelEditing={cancelEditing}
                      deleteNote={deleteNote}
                      handleNodeLinkingClick={handleNodeLinkingClick}
                      onCardMouseDown={onCardMouseDown}
                      onHeaderMouseDown={onHeaderMouseDown}
                      handleOpenPortalAsProject={handleOpenPortalAsProject}
                      isClusterView={isClusterView}
                    />
                  );
                }

                return (
                  <NoteCard
                    key={node.id}
                    node={node}
                    isClusterView={isClusterView}
                    isSource={isSource}
                    isSelected={isSelectedNode}
                    isEditing={isEditing}
                    draggingNodeId={draggingNodeId}
                    theme={theme}
                    linkingMode={linkingMode}
                    linkingModeRef={linkingModeRef}
                    cardElRefs={cardElRefs}
                    editingText={editingText}
                    setEditingText={setEditingText}
                    editingTextRef={editingTextRef}
                    textareaRef={textareaRef}
                    autoResizeTextarea={autoResizeTextarea}
                    startEditing={startEditing}
                    commitEditing={commitEditing}
                    cancelEditing={cancelEditing}
                    deleteNote={deleteNote}
                    handleNodeLinkingClick={handleNodeLinkingClick}
                    onCardMouseDown={onCardMouseDown}
                    onHeaderMouseDown={onHeaderMouseDown}
                    selectNode={selectNode}
                    createLinkedNoteNextTo={createLinkedNoteNextTo}
                  />
                );
              })}

              {/* Pusty stan */}
              {loaded && nodes.length === 0 && (
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
                  <p className={`text-sm font-semibold ${theme === 'dark' ? 'text-[#bbbbbb]' : 'text-slate-600'}`}>Twoja przestrzeń notatek</p>
                  <p className={`mt-1 text-xs ${theme === 'dark' ? 'text-[#666666]' : 'text-slate-500'}`}>Kliknij dwukrotnie w dowolnym miejscu, aby utworzyć notatkę</p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Błąd wczytywania */}
        {loadError && (
          <div
            className="absolute inset-0 z-30 flex items-center justify-center"
            style={{
              backgroundColor: theme === 'dark' ? 'rgba(16, 16, 16, 0.95)' : 'rgba(241, 245, 249, 0.9)',
            }}
          >
            <div
              className="max-w-sm px-5 py-4 rounded-2xl border text-center shadow-lg"
              style={{
                backgroundColor: theme === 'dark' ? '#141414' : '#ffffff',
                borderColor: theme === 'dark' ? '#3a1e1e' : '#fecaca',
              }}
            >
              <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Nie udało się wczytać danych</p>
              <p className={`mt-1 text-xs ${theme === 'dark' ? 'text-[#ff8080]' : 'text-red-600'} break-words`}>{loadError}</p>
            </div>
          </div>
        )}
      </div>

      {/* Stopka ze skrótami — pływająca kapsułka */}
      <CanvasFooter
        isMacroView={isMacroView}
        activeProjectId={activeProjectId}
        selectedProjectId={selectedProjectId}
        diveIntoProject={diveIntoProject}
        togglePortalPlacementMode={togglePortalPlacementMode}
        placementMode={placementMode}
      />

      {/* Modal Pomocy — Skróty Klawiszowe */}
      <HelpModal
        showHelp={showHelp}
        onClose={() => setShowHelp(false)}
        theme={theme}
      />

      {/* Menu kontekstowe CAD */}
      {contextMenu && (
        <CanvasContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          type={contextMenu.type}
          selectedCount={contextMenu.selectedCount}
          bracketName={contextMenu.bracketName}
          onCreateBracket={handleCreateBracketFromSelection}
          onPackBracket={(orientation) => {
            if (contextMenu.targetId) {
              void handlePackBracket(contextMenu.targetId, orientation);
            }
          }}
          onDeleteBracket={() => {
            if (contextMenu.targetId) {
              void handleDeleteBracket(contextMenu.targetId);
            }
          }}
          onRenameBracket={() => {
            if (contextMenu.targetId) {
              const curProj = projectsRef.current.find((p) => p.id === activeProjectIdRef.current);
              const b = curProj?.brackets?.find((x) => x.id === contextMenu.targetId);
              setRenameBracketModal({
                id: contextMenu.targetId,
                name: b?.name || 'Klamra semantyczna',
              });
            }
          }}
          onClose={() => setContextMenu(null)}
          theme={theme}
        />
      )}

      {/* Modal tworzenia nowej klamry semantycznej — natywny design Cortex */}
      {createBracketModal && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/65 backdrop-blur-sm pointer-events-auto select-none font-sans"
          onClick={() => setCreateBracketModal(null)}
        >
          <div
            className="w-96 bg-[#141414] border border-[#2a2a2a] rounded-2xl shadow-[0_24px_60px_rgba(0,0,0,0.85)] p-5 flex flex-col gap-4 pointer-events-auto text-xs animate-in fade-in zoom-in-95 duration-100"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#222] pb-2.5">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#FFC799] shadow-[0_0_8px_#FFC799]" />
                <span className="font-semibold text-sm text-white tracking-tight">
                  NOWA KLAMRA SEMANTYCZNA
                </span>
              </div>
              <button
                type="button"
                onClick={() => setCreateBracketModal(null)}
                className="text-[#666] hover:text-white text-base font-bold transition-colors cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-[#888] font-medium">
                Nazwa klamry (np. Architektura, Ofertownik)
              </label>
              <input
                autoFocus
                type="text"
                value={newBracketInput}
                onChange={(e) => setNewBracketInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleConfirmCreateBracket();
                  }
                  if (e.key === 'Escape') {
                    setCreateBracketModal(null);
                  }
                }}
                className="w-full bg-[#0a0a0a] border border-[#2e2e2e] focus:border-[#FFC799] focus:ring-1 focus:ring-[#FFC799]/30 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none transition-all placeholder:text-[#555]"
                placeholder="Wpisz nazwę klamry..."
              />
            </div>

            {/* Wybór orientacji klamry */}
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] text-[#888] font-medium">Układ i kierunek klamry</span>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setCreateBracketModal((prev) => (prev ? { ...prev, orientation: 'horizontal' } : null))
                  }
                  className={`px-3 py-2 rounded-xl border text-xs font-medium transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                    createBracketModal.orientation === 'horizontal'
                      ? 'border-[#FFC799] bg-[#FFC799]/10 text-[#FFC799]'
                      : 'border-[#262626] bg-[#111] text-[#888] hover:border-[#333]'
                  }`}
                >
                  <span>↔ Pozioma (u góry)</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setCreateBracketModal((prev) => (prev ? { ...prev, orientation: 'vertical' } : null))
                  }
                  className={`px-3 py-2 rounded-xl border text-xs font-medium transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                    createBracketModal.orientation === 'vertical'
                      ? 'border-[#FFC799] bg-[#FFC799]/10 text-[#FFC799]'
                      : 'border-[#262626] bg-[#111] text-[#888] hover:border-[#333]'
                  }`}
                >
                  <span>↕ Pionowa (z boku)</span>
                </button>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#222]">
              <button
                type="button"
                onClick={() => setCreateBracketModal(null)}
                className="px-3.5 py-2 rounded-xl bg-[#1e1e1e] hover:bg-[#282828] text-[#aaa] hover:text-white text-xs font-medium transition-colors cursor-pointer border border-[#2a2a2a]"
              >
                Anuluj
              </button>
              <button
                type="button"
                onClick={handleConfirmCreateBracket}
                className="px-4 py-2 rounded-xl bg-[#FFC799] hover:bg-[#ffd6b3] text-black text-xs font-semibold transition-all shadow-md cursor-pointer"
              >
                Stwórz i dosuń (20px)
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Modal zmiany nazwy klamry z menu kontekstowego — natywny design Cortex */}
      {renameBracketModal && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/65 backdrop-blur-sm pointer-events-auto select-none font-sans"
          onClick={() => setRenameBracketModal(null)}
        >
          <div
            className="w-96 bg-[#141414] border border-[#2a2a2a] rounded-2xl shadow-[0_24px_60px_rgba(0,0,0,0.85)] p-5 flex flex-col gap-4 pointer-events-auto text-xs animate-in fade-in zoom-in-95 duration-100"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#222] pb-2.5">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#FFC799] shadow-[0_0_8px_#FFC799]" />
                <span className="font-semibold text-sm text-white tracking-tight">
                  ZMIANA NAZWY KLAMRY
                </span>
              </div>
              <button
                type="button"
                onClick={() => setRenameBracketModal(null)}
                className="text-[#666] hover:text-white text-base font-bold transition-colors cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-[#888] font-medium">Nazwa klamry semantycznej</label>
              <input
                autoFocus
                type="text"
                value={renameBracketModal.name}
                onChange={(e) =>
                  setRenameBracketModal((prev) => (prev ? { ...prev, name: e.target.value } : null))
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const trimmed = renameBracketModal.name.trim();
                    void handleRenameBracket(renameBracketModal.id, trimmed);
                    setRenameBracketModal(null);
                  }
                  if (e.key === 'Escape') {
                    setRenameBracketModal(null);
                  }
                }}
                className="w-full bg-[#0a0a0a] border border-[#2e2e2e] focus:border-[#FFC799] focus:ring-1 focus:ring-[#FFC799]/30 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none transition-all placeholder:text-[#555]"
                placeholder="Wpisz nazwę klamry..."
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#222]">
              <button
                type="button"
                onClick={() => setRenameBracketModal(null)}
                className="px-3.5 py-2 rounded-xl bg-[#1e1e1e] hover:bg-[#282828] text-[#aaa] hover:text-white text-xs font-medium transition-colors cursor-pointer border border-[#2a2a2a]"
              >
                Anuluj
              </button>
              <button
                type="button"
                onClick={() => {
                  const trimmed = renameBracketModal.name.trim();
                  void handleRenameBracket(renameBracketModal.id, trimmed);
                  setRenameBracketModal(null);
                }}
                className="px-4 py-2 rounded-xl bg-[#FFC799] hover:bg-[#ffd6b3] text-black text-xs font-semibold transition-all shadow-md cursor-pointer"
              >
                Zapisz
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
