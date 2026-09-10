import type { ProjektyEdge, ProjektyNode, Projekt } from '../../../types';
import type { MacroEdge } from '../types';
import {
  centerOf,
  getNodePerimeterPoint,
  getProjectPerimeterPoint,
} from '../utils/nodePlacement';
import { getProjectMacroPosition } from '../utils/zoomMath';
import { PROJECT_CARD_WIDTH, PROJECT_CARD_HEIGHT } from '../constants';

interface ConnectionLinesLayerProps {
  theme: 'light' | 'dark';
  isMacroView: boolean;
  visibleEdges: ProjektyEdge[];
  visibleNodes: ProjektyNode[];
  deleteEdge: (id: string) => Promise<void> | void;
  toggleEdgeArrow?: (id: string) => Promise<void> | void;
  linkingMode: boolean;
  linkSourceId: string | null;
  mouseCanvasPos: { x: number; y: number } | null;
  macroEdges: MacroEdge[];
  projects: Projekt[];
  deleteMacroEdge: (id: string) => void;
  toggleMacroEdgeArrow?: (id: string) => void;
  macroLinkingMode: boolean;
  macroLinkSourceId: string | null;
  isClusterView?: boolean;
}

export function ConnectionLinesLayer({
  theme,
  isMacroView,
  visibleEdges,
  visibleNodes,
  deleteEdge,
  toggleEdgeArrow,
  linkingMode,
  linkSourceId,
  mouseCanvasPos,
  macroEdges,
  projects,
  deleteMacroEdge,
  toggleMacroEdgeArrow,
  macroLinkingMode,
  macroLinkSourceId,
  isClusterView = false,
}: ConnectionLinesLayerProps) {
  const centerOfProject = (proj: Projekt, idx: number, total: number) => {
    const pos = getProjectMacroPosition(proj, idx, total);
    return {
      x: pos.x + PROJECT_CARD_WIDTH / 2,
      y: pos.y + PROJECT_CARD_HEIGHT / 2,
    };
  };

  return (
    <svg
      className="absolute"
      style={{
        top: 0,
        left: 0,
        width: 10000,
        height: 10000,
        pointerEvents: 'none',
        overflow: 'visible',
        opacity: isClusterView ? 0.08 : 1,
        transition: 'opacity 150ms ease-out',
      }}
    >
      <defs>
        <marker
          id="cortex-arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={theme === 'dark' ? '#555555' : '#64748b'} />
        </marker>
        <marker
          id="cortex-arrow-hover"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={theme === 'dark' ? '#FFC799' : '#2563eb'} />
        </marker>
        <marker
          id="cortex-arrow-preview"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={theme === 'dark' ? '#FFC799' : '#2563eb'} />
        </marker>
      </defs>

      {/* Krawędzie łączące notatki — linie łączą się dokładnie z obwodem kart, z opcjonalnym grotem strzałki */}
      {!isMacroView &&
        visibleEdges.map((edge) => {
          const src = visibleNodes.find((n) => n.id === edge.source_node_id);
          const tgt = visibleNodes.find((n) => n.id === edge.target_node_id);
          if (!src || !tgt) return null;
          const sc = centerOf(src);
          const tc = centerOf(tgt);
          const s = getNodePerimeterPoint(src, tc, 2);
          const t = getNodePerimeterPoint(tgt, sc, 6);
          const dx = t.x - s.x;
          const bend = Math.max(Math.min(Math.abs(dx) * 0.5, 120), 40);
          const dir = dx >= 0 ? 1 : -1;
          const cp1 = { x: s.x + bend * dir, y: s.y };
          const cp2 = { x: t.x - bend * dir, y: t.y };
          const d = `M ${s.x} ${s.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${t.x} ${t.y}`;
          const midX = (s.x + 3 * cp1.x + 3 * cp2.x + t.x) / 8;
          const midY = (s.y + 3 * cp1.y + 3 * cp2.y + t.y) / 8;

          const hasArrow = edge.has_arrow !== false;

          return (
            <g
              key={edge.id}
              className="edge-group group/edge pointer-events-auto"
            >
              {/* Szerszy niewidzialny obszar klikalny */}
              <path d={d} className="cortex-edge-hit" />
              {/* Widoczna linia połączenia (krzywa Béziera) */}
              <path
                d={d}
                className={`cortex-edge ${hasArrow ? 'cortex-edge-with-arrow' : ''}`}
              />
              {/* Punkty zaczepienia */}
              <circle cx={s.x} cy={s.y} r={3} fill={theme === 'dark' ? '#333333' : '#94a3b8'} />
              <circle cx={t.x} cy={t.y} r={3} fill={theme === 'dark' ? '#333333' : '#94a3b8'} />

              {/* Kapsułka akcji: [ — / ➔ ] oraz czerwony [ ✕ ] */}
              <g
                className="opacity-0 group-hover/edge:opacity-100 transition-opacity"
                transform={`translate(${midX}, ${midY})`}
                onMouseDown={(e) => e.stopPropagation()}
              >
                {/* Tło kapsułki */}
                <rect
                  x="-34"
                  y="-12"
                  width="68"
                  height="24"
                  rx="8"
                  fill={theme === 'dark' ? '#141414' : '#ffffff'}
                  stroke={theme === 'dark' ? '#2e2e2e' : '#cbd5e1'}
                  strokeWidth={1}
                  className="shadow-md"
                />

                {/* Przełącznik stylu (Wyświetla przeciwną akcję: jeśli jest strzałka to pokazuje '—', jeśli jest linia to pokazuje '➔') */}
                <g
                  data-testid={`edge-toggle-arrow-${edge.id}`}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    void toggleEdgeArrow?.(edge.id);
                  }}
                  className="cursor-pointer hover:opacity-80"
                >
                  <title>{hasArrow ? 'Zmień na czystą linię bez grota' : 'Zmień na strzałkę kierunkową'}</title>
                  <rect
                    x="-32"
                    y="-10"
                    width="30"
                    height="20"
                    rx="6"
                    fill={theme === 'dark' ? '#202020' : '#f1f5f9'}
                  />
                  <text
                    x="-17"
                    y="4"
                    fontSize="11"
                    fontFamily="monospace"
                    fill={theme === 'dark' ? (hasArrow ? '#888888' : '#FFC799') : (hasArrow ? '#64748b' : '#2563eb')}
                    textAnchor="middle"
                    fontWeight="bold"
                  >
                    {hasArrow ? '—' : '➔'}
                  </text>
                </g>

                {/* Czerwony przycisk usunięcia połączenia */}
                <g
                  data-testid={`edge-delete-${edge.id}`}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    void deleteEdge(edge.id);
                  }}
                  className="cursor-pointer hover:opacity-80"
                >
                  <title>Usuń połączenie</title>
                  <rect
                    x="2"
                    y="-10"
                    width="30"
                    height="20"
                    rx="6"
                    fill={theme === 'dark' ? '#3a1c1c' : '#fee2e2'}
                  />
                  <text
                    x="17"
                    y="4"
                    fontSize="11"
                    fontFamily="sans-serif"
                    fill={theme === 'dark' ? '#ff7070' : '#dc2626'}
                    textAnchor="middle"
                    fontWeight="bold"
                  >
                    ✕
                  </text>
                </g>
              </g>
            </g>
          );
        })}

      {/* Dynamiczna linia podglądu podczas łączenia notatek */}
      {!isMacroView &&
        linkingMode &&
        linkSourceId &&
        mouseCanvasPos &&
        (() => {
          const src = visibleNodes.find((n) => n.id === linkSourceId);
          if (!src) return null;
          const s = getNodePerimeterPoint(src, mouseCanvasPos, 2);
          const t = mouseCanvasPos;
          const dx = t.x - s.x;
          const bend = Math.max(Math.min(Math.abs(dx) * 0.5, 120), 40);
          const dir = dx >= 0 ? 1 : -1;
          const cp1 = { x: s.x + bend * dir, y: s.y };
          const cp2 = { x: t.x - bend * dir, y: t.y };
          const d = `M ${s.x} ${s.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${t.x} ${t.y}`;
          return (
            <path
              d={d}
              fill="none"
              stroke={theme === 'dark' ? '#FFC799' : '#2563eb'}
              strokeWidth={2}
              strokeDasharray="6 4"
              strokeLinecap="round"
              markerEnd="url(#cortex-arrow-preview)"
              className="animate-pulse"
            />
          );
        })()}

      {/* Krawędzie łączące projekty w widoku makro */}
      {isMacroView &&
        macroEdges.map((edge) => {
          const srcIdx = projects.findIndex((p) => p.id === edge.source_project_id);
          const tgtIdx = projects.findIndex((p) => p.id === edge.target_project_id);
          if (srcIdx < 0 || tgtIdx < 0) return null;
          const src = projects[srcIdx];
          const tgt = projects[tgtIdx];
          const sc = centerOfProject(src, srcIdx, projects.length);
          const tc = centerOfProject(tgt, tgtIdx, projects.length);
          const s = getProjectPerimeterPoint(src, srcIdx, projects.length, tc, 2);
          const t = getProjectPerimeterPoint(tgt, tgtIdx, projects.length, sc, 8);
          const dx = t.x - s.x;
          const bend = Math.max(Math.min(Math.abs(dx) * 0.5, 200), 80);
          const dir = dx >= 0 ? 1 : -1;
          const cp1 = { x: s.x + bend * dir, y: s.y };
          const cp2 = { x: t.x - bend * dir, y: t.y };
          const d = `M ${s.x} ${s.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${t.x} ${t.y}`;
          const midX = (s.x + 3 * cp1.x + 3 * cp2.x + t.x) / 8;
          const midY = (s.y + 3 * cp1.y + 3 * cp2.y + t.y) / 8;

          const hasMacroArrow = edge.has_arrow !== false;

          return (
            <g
              key={edge.id}
              className="edge-group group/edge pointer-events-auto"
            >
              <path d={d} className="cortex-edge-hit" strokeWidth={32} />
              <path
                d={d}
                fill="none"
                stroke={theme === 'dark' ? '#383838' : '#94a3b8'}
                strokeWidth={2.5}
                markerEnd={hasMacroArrow ? 'url(#cortex-arrow)' : undefined}
                className="transition-colors hover:stroke-[#FFC799]"
              />
              <circle cx={s.x} cy={s.y} r={4} fill={theme === 'dark' ? '#383838' : '#94a3b8'} />
              <circle cx={t.x} cy={t.y} r={4} fill={theme === 'dark' ? '#383838' : '#94a3b8'} />

              {/* Kapsułka akcji dla krawędzi makro */}
              <g
                className="opacity-0 group-hover/edge:opacity-100 transition-opacity"
                transform={`translate(${midX}, ${midY})`}
                onMouseDown={(e) => e.stopPropagation()}
              >
                {/* Tło kapsułki */}
                <rect
                  x="-34"
                  y="-12"
                  width="68"
                  height="24"
                  rx="8"
                  fill={theme === 'dark' ? '#141414' : '#ffffff'}
                  stroke={theme === 'dark' ? '#2e2e2e' : '#cbd5e1'}
                  strokeWidth={1}
                  className="shadow-md"
                />

                {/* Przełącznik stylu dla krawędzi makro */}
                <g
                  data-testid={`macro-edge-toggle-arrow-${edge.id}`}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleMacroEdgeArrow?.(edge.id);
                  }}
                  className="cursor-pointer hover:opacity-80"
                >
                  <title>{hasMacroArrow ? 'Zmień na czystą linię bez grota' : 'Zmień na strzałkę kierunkową'}</title>
                  <rect
                    x="-32"
                    y="-10"
                    width="30"
                    height="20"
                    rx="6"
                    fill={theme === 'dark' ? '#202020' : '#f1f5f9'}
                  />
                  <text
                    x="-17"
                    y="4"
                    fontSize="11"
                    fontFamily="monospace"
                    fill={theme === 'dark' ? (hasMacroArrow ? '#888888' : '#FFC799') : (hasMacroArrow ? '#64748b' : '#2563eb')}
                    textAnchor="middle"
                    fontWeight="bold"
                  >
                    {hasMacroArrow ? '—' : '➔'}
                  </text>
                </g>

                {/* Czerwony przycisk usunięcia połączenia makro */}
                <g
                  data-testid={`macro-edge-delete-${edge.id}`}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteMacroEdge(edge.id);
                  }}
                  className="cursor-pointer hover:opacity-80"
                >
                  <title>Usuń połączenie</title>
                  <rect
                    x="2"
                    y="-10"
                    width="30"
                    height="20"
                    rx="6"
                    fill={theme === 'dark' ? '#3a1c1c' : '#fee2e2'}
                  />
                  <text
                    x="17"
                    y="4"
                    fontSize="11"
                    fontFamily="sans-serif"
                    fill={theme === 'dark' ? '#ff7070' : '#dc2626'}
                    textAnchor="middle"
                    fontWeight="bold"
                  >
                    ✕
                  </text>
                </g>
              </g>
            </g>
          );
        })}

      {/* Dynamiczna linia podglądu podczas łączenia projektów */}
      {isMacroView &&
        macroLinkingMode &&
        macroLinkSourceId &&
        mouseCanvasPos &&
        (() => {
          const srcIdx = projects.findIndex((p) => p.id === macroLinkSourceId);
          if (srcIdx < 0) return null;
          const src = projects[srcIdx];
          const s = getProjectPerimeterPoint(src, srcIdx, projects.length, mouseCanvasPos, 2);
          const t = mouseCanvasPos;
          const dx = t.x - s.x;
          const bend = Math.max(Math.min(Math.abs(dx) * 0.5, 200), 80);
          const dir = dx >= 0 ? 1 : -1;
          const cp1 = { x: s.x + bend * dir, y: s.y };
          const cp2 = { x: t.x - bend * dir, y: t.y };
          const d = `M ${s.x} ${s.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${t.x} ${t.y}`;
          return (
            <path
              d={d}
              fill="none"
              stroke={theme === 'dark' ? '#FFC799' : '#2563eb'}
              strokeWidth={2.5}
              strokeDasharray="8 6"
              strokeLinecap="round"
              markerEnd="url(#cortex-arrow-preview)"
              className="animate-pulse"
            />
          );
        })()}
    </svg>
  );
}
