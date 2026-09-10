import { useMemo, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { MouseEvent as ReactMouseEvent } from 'react';
import type { ProjektyNode, ProjektyEdge, ProjektyBracket } from '../../../types';
import { ZOOM_CLUSTER_THRESHOLD } from '../constants';
import { computeClusterLayouts } from '../utils/clusterGeometry';

interface ConnectedIslandsLayerProps {
  theme: 'light' | 'dark';
  isMacroView: boolean;
  visibleNodes: ProjektyNode[];
  visibleEdges: ProjektyEdge[];
  scale?: number;
  clusterDescriptions?: Record<string, string>;
  brackets?: ProjektyBracket[];
  selectedNodeIds?: string[];
  onSaveClusterDescription?: (clusterKey: string, description: string, nodeIds?: string[]) => void | Promise<void>;
  onStartDragCluster?: (clusterNodes: ProjektyNode[], e: ReactMouseEvent) => void;
  onOpenClusterContextMenu?: (clusterNodes: ProjektyNode[], e: ReactMouseEvent) => void;
}

export function ConnectedIslandsLayer({
  theme,
  isMacroView,
  visibleNodes,
  visibleEdges,
  scale = 1,
  clusterDescriptions = {},
  brackets = [],
  selectedNodeIds = [],
  onSaveClusterDescription,
  onStartDragCluster,
  onOpenClusterContextMenu,
}: ConnectedIslandsLayerProps) {
  const [editingClusterKey, setEditingClusterKey] = useState<string | null>(null);
  const [editingClusterNodes, setEditingClusterNodes] = useState<ProjektyNode[]>([]);
  const [editingText, setEditingText] = useState('');
  const dragStartPos = useRef<{ x: number; y: number } | null>(null);

  // Skala kompensacyjna (1 / scale) — tekst czytelny przy oddaleniu
  const counterScale = 1 / Math.max(0.18, scale);

  // Wyliczenie geometrii klastrów z automatycznym rozszerzaniem pudełek do ściany klamry (CAD Wall Extension)
  const clusterLayouts = useMemo(() => {
    if (isMacroView || visibleNodes.length === 0) return [];
    const layouts = computeClusterLayouts(visibleNodes, visibleEdges, clusterDescriptions, brackets);
    const isClusterZoom = scale <= ZOOM_CLUSTER_THRESHOLD;

    const mapped = layouts.map((layout) => {
      const isSelected = layout.cluster.some((n) => selectedNodeIds.includes(n.id));
      const isEditingThis = editingClusterKey === layout.clusterKey;
      return {
        ...layout,
        labelX: layout.contentCenterX,
        labelY: layout.contentCenterY,
        isEditingThis,
        isClusterZoom,
        isSelected,
        badgeScale: counterScale,
      };
    });

    // Etykieta jest przypięta dokładnie do środka klastra (contentCenter).
    // Anty-kolizja nie przesuwa etykiet — przy zoomie powodowała skoki pozycji,
    // bo różne pary na przemian wchodziły/wychodziły z kolizji.
    return mapped;
  }, [isMacroView, visibleNodes, visibleEdges, clusterDescriptions, brackets, selectedNodeIds, scale, editingClusterKey, counterScale]);

  const handleStartEdit = (cluster: ProjektyNode[], clusterKey: string, currentDesc: string) => {
    setEditingClusterKey(clusterKey);
    setEditingClusterNodes(cluster);
    setEditingText(currentDesc);
  };

  const handleSave = () => {
    const trimmed = editingText.trim();
    if (onSaveClusterDescription && editingClusterKey) {
      const nodeIds = editingClusterNodes.map((n) => n.id);
      void onSaveClusterDescription(editingClusterKey, trimmed, nodeIds);
    }
    setEditingClusterKey(null);
    setEditingClusterNodes([]);
  };

  if (isMacroView || clusterLayouts.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-0 overflow-visible">
      {clusterLayouts.map((layout) => {
        const {
          cluster,
          index,
          minX,
          minY,
          width,
          height,
          labelX,
          labelY,
          clusterKey,
          currentDesc,
          isEditingThis,
          isClusterZoom,
          isSelected,
        } = layout;

        return (
          <div key={`cluster-${clusterKey || index}`} className="contents">
            {/* Ramka klastra / wyspy - z podświetleniem zaznaczenia oraz menu kontekstowym */}
            <div
              data-testid={`connected-island-${index}`}
              className={`absolute rounded-3xl border transition-all duration-150 ease-out pointer-events-auto cursor-grab active:cursor-grabbing group/island ${
                isSelected ? 'ring-2 ring-[#FFC799]/40' : ''
              }`}
              style={{
                left: minX,
                top: minY,
                width,
                height,
                backgroundColor: isSelected
                  ? theme === 'dark'
                    ? 'rgba(255, 199, 153, 0.08)'
                    : 'rgba(37, 99, 235, 0.08)'
                  : theme === 'dark'
                    ? 'rgba(18, 18, 18, 0.42)'
                    : 'rgba(241, 245, 249, 0.45)',
                borderColor: isSelected
                  ? '#FFC799'
                  : theme === 'dark'
                    ? isClusterZoom
                      ? 'rgba(70, 70, 70, 0.9)'
                      : 'rgba(38, 38, 38, 0.65)'
                    : 'rgba(226, 232, 240, 0.75)',
                boxShadow: isSelected
                  ? '0 0 25px rgba(255, 199, 153, 0.25), inset 0 0 40px rgba(255, 199, 153, 0.08)'
                  : theme === 'dark'
                    ? 'inset 0 0 40px rgba(0, 0, 0, 0.35)'
                    : 'inset 0 0 30px rgba(0, 0, 0, 0.02)',
              }}
              onMouseDown={(e) => {
                if (e.button === 0 && onStartDragCluster) {
                  onStartDragCluster(cluster, e);
                }
              }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (onOpenClusterContextMenu) {
                  onOpenClusterContextMenu(cluster, e);
                }
              }}
              title="Przeciągnij, aby przesunąć cały klaster • Shift+Klik: zaznacz klaster • Prawy klik: menu klamer"
            />

            {/* Etykieta klastra na krawędzi (Poziom 1: > 70%) */}
            {!isClusterZoom && !isEditingThis && (
              <div
                className="absolute z-10 pointer-events-auto flex items-center gap-2 px-3 py-1 rounded-lg bg-[#161616] border border-[#2e2e2e] text-[#aaa] hover:text-[#fff] hover:border-[#555] text-xs cursor-grab active:cursor-grabbing transition-all shadow-md select-none"
                style={{ left: minX + 20, top: minY - 14 }}
                onMouseDown={(e) => {
                  if (e.button === 0 && onStartDragCluster) {
                    onStartDragCluster(cluster, e);
                  }
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  handleStartEdit(cluster, clusterKey, currentDesc);
                }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (onOpenClusterContextMenu) {
                    onOpenClusterContextMenu(cluster, e);
                  } else {
                    handleStartEdit(cluster, clusterKey, currentDesc);
                  }
                }}
                title="Kliknij, aby edytować opis klastra. Przeciągnij, aby przesunąć."
              >
                <span className="w-2 h-2 rounded-full bg-[#FFC799] shrink-0" />
                <span className="font-semibold max-w-xs truncate">
                  {currentDesc || 'Klaster (kliknij - edytuj opis)'}
                </span>
              </div>
            )}

            {/* Poziom 2: Duży, czytelny opis klastra z anty-kolizją i chwytaniem drag & drop */}
            {isClusterZoom && !isEditingThis && (
              <div
                className="absolute z-20 pointer-events-auto -translate-x-1/2 -translate-y-1/2 select-none"
                style={{
                  left: labelX,
                  top: labelY,
                }}
              >
                <div
                  onMouseDown={(e) => {
                    if (e.button === 0 && onStartDragCluster) {
                      dragStartPos.current = { x: e.clientX, y: e.clientY };
                      onStartDragCluster(cluster, e);
                    }
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (onOpenClusterContextMenu) {
                      onOpenClusterContextMenu(cluster, e);
                    }
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (dragStartPos.current) {
                      const dist = Math.hypot(e.clientX - dragStartPos.current.x, e.clientY - dragStartPos.current.y);
                      if (dist > 4) return;
                    }
                    handleStartEdit(cluster, clusterKey, currentDesc);
                  }}
                  className={`bg-[#141414]/95 border rounded-2xl px-4 py-3 shadow-2xl cursor-grab active:cursor-grabbing transition-all duration-150 w-[250px] max-w-[min(250px,90%)] text-center group ${
                    isSelected
                      ? 'border-[#FFC799] ring-2 ring-[#FFC799]/30'
                      : 'border-[#333333] hover:border-[#FFC799]'
                  }`}
                  style={{
                    transform: `scale(${counterScale})`,
                    transformOrigin: 'center center',
                  }}
                  title="Przeciągnij, aby przesunąć • Shift+Klik: zaznacz • Kliknij: edytuj opis • Prawy klik: menu"
                >
                  <p className="text-sm md:text-base font-semibold text-[#ffffff] leading-snug tracking-normal whitespace-pre-wrap break-words [overflow-wrap:anywhere] pointer-events-none">
                    {currentDesc || 'Kliknij, aby dodać opis klastra...'}
                  </p>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Kompaktowe okienko szybkiej edycji opisu klastra — montowane w document.body (createPortal), całkowicie odporne na transform canvasu */}
      {editingClusterKey && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm pointer-events-auto select-none"
          onClick={() => {
            setEditingClusterKey(null);
            setEditingClusterNodes([]);
          }}
        >
          <div
            className="w-80 bg-[#141414] border border-[#2c2c2c] rounded-2xl shadow-2xl p-4 flex flex-col gap-2.5 pointer-events-auto text-xs animate-in fade-in zoom-in-95 duration-100"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center text-xs font-semibold text-white">
              <span>Opis klastra</span>
              <button
                onClick={() => {
                  setEditingClusterKey(null);
                  setEditingClusterNodes([]);
                }}
                className="text-[#666] hover:text-[#fff] px-1 text-sm font-bold cursor-pointer transition-colors"
              >
                ✕
              </button>
            </div>
            <textarea
              autoFocus
              value={editingText}
              onChange={(e) => setEditingText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSave();
                }
                if (e.key === 'Escape') {
                  setEditingClusterKey(null);
                  setEditingClusterNodes([]);
                }
              }}
              className="w-full h-20 bg-[#0a0a0a] border border-[#242424] focus:border-[#FFC799] rounded-xl p-2.5 text-xs text-white outline-none resize-none leading-relaxed"
              placeholder="Wpisz esencję tego klastra..."
            />
            <div className="flex justify-between items-center text-[10.5px] text-[#777]">
              <span>Enter — zapisz • Esc — anuluj</span>
              <button
                onClick={() => handleSave()}
                className="bg-[#242424] hover:bg-[#333333] text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer border border-[#383838]"
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
