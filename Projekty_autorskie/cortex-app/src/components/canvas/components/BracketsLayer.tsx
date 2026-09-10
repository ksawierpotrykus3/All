import { useMemo, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { MouseEvent as ReactMouseEvent } from 'react';
import type { ProjektyBracket, ProjektyNode, ProjektyEdge } from '../../../types';
import { ZOOM_CLUSTER_THRESHOLD } from '../constants';
import { calculateBracketGeometries, type ComputedBracketGeometry } from '../utils/bracketGeometry';
import { computeClusterLayouts } from '../utils/clusterGeometry';

interface BracketsLayerProps {
  isMacroView: boolean;
  brackets?: ProjektyBracket[];
  visibleNodes: ProjektyNode[];
  visibleEdges?: ProjektyEdge[];
  clusterDescriptions?: Record<string, string>;
  scale?: number;
  onRenameBracket?: (bracketId: string, newName: string) => void | Promise<void>;
  onDeleteBracket?: (bracketId: string) => void | Promise<void>;
  onRotateBracket?: (bracketId: string) => void | Promise<void>;
  onOpenBracketContextMenu?: (bracketId: string, e: ReactMouseEvent) => void;
}

export function BracketsLayer({
  isMacroView,
  brackets = [],
  visibleNodes,
  visibleEdges = [],
  clusterDescriptions = {},
  scale = 1,
  onRenameBracket,
  onDeleteBracket,
  onRotateBracket,
  onOpenBracketContextMenu,
}: BracketsLayerProps) {
  const [editingBracketId, setEditingBracketId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState('');
  const editInputRef = useRef<HTMLTextAreaElement>(null);

  // Klamry sa widoczne WYŁĄCZNIE na poziomie klastrów (scale <= ZOOM_CLUSTER_THRESHOLD)
  const isClusterView = !isMacroView && scale <= ZOOM_CLUSTER_THRESHOLD;

  // Deterministyczne wyliczenie geometrii klamer z uwzględnieniem rozszerzonych ścian klastrów
  const geometries = useMemo<ComputedBracketGeometry[]>(() => {
    if (!isClusterView || !brackets || brackets.length === 0 || visibleNodes.length === 0) {
      return [];
    }
    const clusterLayouts = computeClusterLayouts(visibleNodes, visibleEdges, clusterDescriptions, brackets);
    return calculateBracketGeometries(brackets, visibleNodes, clusterLayouts);
  }, [isClusterView, brackets, visibleNodes, visibleEdges, clusterDescriptions]);

  const handleStartRename = (bracketId: string, currentName: string) => {
    setEditingBracketId(bracketId);
    setEditingText(currentName);
    setTimeout(() => {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }, 50);
  };

  const handleSaveRename = () => {
    if (editingBracketId && onRenameBracket) {
      const trimmed = editingText.trim() || 'Klamra semantyczna';
      void onRenameBracket(editingBracketId, trimmed);
    }
    setEditingBracketId(null);
  };

  if (isMacroView || geometries.length === 0) return null;

  // Skala kompensacyjna gwarantujaca czytelnosc tekstu przy oddaleniu
  const counterScale = 1 / Math.max(0.2, scale);

  return (
    <div className="absolute inset-0 pointer-events-none z-10 overflow-visible font-sans">
      {/* Warstwa SVG rysująca czyste, dyskretne linie klamer CAD (bez poświaty) */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none overflow-visible">
        {geometries.map((geom) => (
          <path
            key={`bracket-path-${geom.id}`}
            d={geom.pathD}
            fill="none"
            stroke="#444444"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="transition-all duration-150"
          />
        ))}
      </svg>

      {/* Warstwa etykiet klamer — identyczny kafelek jak opis klastra */}
      {geometries.map((geom) => {
        const isEditingThis = editingBracketId === geom.id;

        const positionClass = geom.isVertical
          ? geom.side === 'right'
            ? '-translate-y-1/2'
            : '-translate-y-1/2 -translate-x-full'
          : geom.side === 'bottom'
            ? '-translate-x-1/2'
            : '-translate-x-1/2 -translate-y-full';

        const transformOrigin = geom.isVertical
          ? geom.side === 'right' ? 'left center' : 'right center'
          : geom.side === 'bottom' ? 'center top' : 'center bottom';

        return (
          <div
            key={`bracket-label-${geom.id}`}
            className={`absolute pointer-events-auto select-none ${positionClass}`}
            style={{
              left: geom.labelX,
              top: geom.labelY,
            }}
          >
            {!isEditingThis && (
              <div
                style={{
                  transform: `scale(${counterScale})`,
                  transformOrigin,
                }}
                className="bg-[#141414]/95 border border-[#FFC799]/50 hover:border-[#FFC799] rounded-2xl px-5 py-3.5 shadow-2xl cursor-pointer w-[320px] max-w-[90%] text-center transition-all duration-150 group"
                onClick={(e) => {
                  e.stopPropagation();
                  handleStartRename(geom.id, geom.name);
                }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (onOpenBracketContextMenu) {
                    onOpenBracketContextMenu(geom.id, e);
                  }
                }}
                title="Kliknij, aby edytować opis klamry • Prawy przycisk: menu"
              >
                <div className="flex items-center justify-center gap-2.5">
                  <p className="text-base md:text-lg font-bold text-[#FFC799] leading-snug tracking-normal whitespace-pre-wrap break-words [overflow-wrap:anywhere] pointer-events-none">
                    {geom.name || 'Kliknij, aby dodać opis klamry...'}
                  </p>

                  {/* Subtelny przycisk przerzucenia klamry na przeciwną stronę */}
                  {onRotateBracket && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void onRotateBracket(geom.id);
                      }}
                      onMouseDown={(e) => e.stopPropagation()}
                      className="shrink-0 w-7 h-7 inline-flex items-center justify-center rounded-full bg-[#1e1e1e] border border-[#333] text-[#999] hover:text-[#FFC799] hover:border-[#FFC799] text-base cursor-pointer transition-colors"
                      title="Przerzuć klamrę na przeciwną stronę"
                    >
                      ⟲
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Okno modalne edycji opisu klamry — identyczne z oknem opisu klastra */}
      {editingBracketId && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/50 backdrop-blur-sm pointer-events-auto select-none font-sans"
          onClick={() => setEditingBracketId(null)}
        >
          <div
            className="w-80 bg-[#141414] border border-[#2c2c2c] rounded-2xl shadow-2xl p-4 flex flex-col gap-2.5 pointer-events-auto text-xs animate-in fade-in zoom-in-95 duration-100"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center text-xs font-semibold text-white">
              <span>Opis klamry</span>
              <button
                type="button"
                onClick={() => setEditingBracketId(null)}
                className="text-[#666] hover:text-[#fff] px-1 text-sm font-bold cursor-pointer transition-colors"
              >
                ✕
              </button>
            </div>
            <textarea
              ref={editInputRef}
              autoFocus
              value={editingText}
              onChange={(e) => setEditingText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSaveRename();
                }
                if (e.key === 'Escape') {
                  setEditingBracketId(null);
                }
              }}
              className="w-full h-20 bg-[#0a0a0a] border border-[#242424] focus:border-[#FFC799] rounded-xl p-2.5 text-xs text-white outline-none resize-none leading-relaxed"
              placeholder="Wpisz opis tej klamry..."
            />
            <div className="flex justify-between items-center text-[10.5px] text-[#777]">
              <button
                type="button"
                onClick={() => {
                  if (onDeleteBracket && editingBracketId) {
                    void onDeleteBracket(editingBracketId);
                  }
                  setEditingBracketId(null);
                }}
                className="text-rose-400 hover:text-rose-300 transition-colors cursor-pointer text-xs font-medium"
              >
                Usuń klamrę
              </button>
              <div className="flex gap-2 items-center">
                <button
                  type="button"
                  onClick={() => setEditingBracketId(null)}
                  className="text-[#aaa] hover:text-white px-2.5 py-1 text-xs cursor-pointer"
                >
                  Anuluj
                </button>
                <button
                  type="button"
                  onClick={handleSaveRename}
                  className="bg-[#242424] hover:bg-[#333333] text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer border border-[#383838]"
                >
                  Zapisz
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
