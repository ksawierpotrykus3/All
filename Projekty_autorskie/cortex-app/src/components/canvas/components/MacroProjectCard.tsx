import { useState, useEffect, useRef } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import type { Projekt } from '../../../types';
import { getProjectMacroPosition } from '../utils/zoomMath';
import { PROJECT_CARD_WIDTH, PROJECT_CARD_HEIGHT } from '../constants';
import { CloseIcon } from '../icons/CanvasIcons';
import { computeMacroBracketGeometries } from '../utils/macroBracketGeometry';
import type { MacroClusterBox } from '../utils/macroBracketGeometry';
import type { MacroClusterRef } from '../types';

interface MacroProjectCardProps {
  proj: Projekt;
  idx: number;
  projects: Projekt[];
  projectStats: Record<string, { count: number; previews: string[] }>;
  activeProjectId: string;
  selectedProjectId: string | null;
  macroLinkingMode: boolean;
  macroLinkSourceId: string | null;
  editingProjectId: string | null;
  editingProjectName: string;
  draggingMacroProjId: string | null;
  theme: 'light' | 'dark';
  nodesCount: number;
  scale?: number;
  setEditingProjectName: (name: string) => void;
  handleSaveRename: (id: string) => void | Promise<void>;
  setEditingProjectId: (id: string | null) => void;
  handleStartRename: (proj: Projekt, e: ReactMouseEvent) => void;
  handleDeleteProject: (id: string, e: ReactMouseEvent) => void | Promise<void>;
  diveIntoProject: (id: string, targetClusterKey?: string) => void | Promise<void>;
  startDraggingMacroProject: (id: string, x: number, y: number, e: ReactMouseEvent) => void;
  connectProjects: (sourceId: string, targetId: string) => void;
  setMacroLinking: (mode: boolean, sourceId: string | null) => void;
  setSelectedProjectId: (id: string | null) => void;
  onUpdateClusterOffset?: (projId: string, clusterKey: string, offset: { x: number; y: number }) => void;
  macroSelectedClusterRef: MacroClusterRef | null;
  macroClusterLinkSource: MacroClusterRef | null;
  onSelectCluster: (ref: MacroClusterRef | null) => void;
  onClickClusterLink: (ref: MacroClusterRef) => void;
}

const CLUSTER_CARD_WIDTH = 220;

export function estimateClusterCardHeight(desc: string): number {
  const padding = 20; // p-2.5 = 10px top + 10px bottom
  const header = 20; // Klaster X + mb-1
  const border = 2;
  const charsPerLine = 28;
  const lines = Math.max(1, Math.ceil((desc ? desc.trim().length : 0) / charsPerLine));
  const lineHeight = 18;
  return padding + header + border + lines * lineHeight;
}

function getDefaultClusterOffset(index: number, total: number): { x: number; y: number } {
  if (total === 1) {
    return { x: PROJECT_CARD_WIDTH + 30, y: 15 };
  }
  if (total === 2) {
    if (index === 0) return { x: PROJECT_CARD_WIDTH + 30, y: 15 };
    return { x: -CLUSTER_CARD_WIDTH - 30, y: 15 };
  }
  if (total === 3) {
    if (index === 0) return { x: PROJECT_CARD_WIDTH + 30, y: -10 };
    if (index === 1) return { x: -CLUSTER_CARD_WIDTH - 30, y: -10 };
    return { x: 50, y: PROJECT_CARD_HEIGHT + 25 };
  }
  const defaults = [
    { x: PROJECT_CARD_WIDTH + 30, y: -15 },
    { x: PROJECT_CARD_WIDTH + 30, y: 80 },
    { x: -CLUSTER_CARD_WIDTH - 30, y: -15 },
    { x: -CLUSTER_CARD_WIDTH - 30, y: 80 },
    { x: 50, y: PROJECT_CARD_HEIGHT + 25 },
  ];
  return defaults[index % defaults.length];
}

export { getDefaultClusterOffset, CLUSTER_CARD_WIDTH };

export function MacroProjectCard({
  proj,
  idx,
  projects,
  projectStats,
  activeProjectId,
  selectedProjectId,
  macroLinkingMode,
  macroLinkSourceId,
  editingProjectId,
  editingProjectName,
  draggingMacroProjId,
  theme,
  nodesCount,
  setEditingProjectName,
  handleSaveRename,
  setEditingProjectId,
  handleStartRename,
  handleDeleteProject,
  diveIntoProject,
  startDraggingMacroProject,
  connectProjects,
  setMacroLinking,
  setSelectedProjectId,
  scale,
  onUpdateClusterOffset,
  macroSelectedClusterRef,
  macroClusterLinkSource,
  onSelectCluster,
  onClickClusterLink,
}: MacroProjectCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [cardHeight, setCardHeight] = useState(PROJECT_CARD_HEIGHT);

  const pos = getProjectMacroPosition(proj, idx, projects.length);
  const stats = projectStats[proj.id] || {
    count: proj.id === activeProjectId ? nodesCount : proj.notes_count || 0,
    previews: [],
  };
  const isCurrentActive = proj.id === activeProjectId;
  const isSelected = selectedProjectId === proj.id;
  const isLinkingSource = macroLinkingMode && macroLinkSourceId === proj.id;
  const isEditingThis = editingProjectId === proj.id;
  // Deduplikacja klastrów według unikalnego opisu (jeden satelita per unikalny klaster)
  const uniqueClustersMap = new Map<string, { key: string; desc: string }>();
  for (const [key, desc] of Object.entries(proj.cluster_descriptions || {})) {
    const trimmed = desc?.trim();
    if (trimmed && !uniqueClustersMap.has(trimmed)) {
      uniqueClustersMap.set(trimmed, { key, desc: trimmed });
    }
  }
  const clusterList = Array.from(uniqueClustersMap.values()).map((item) => [item.key, item.desc]);

  useEffect(() => {
    if (cardRef.current) {
      setCardHeight(cardRef.current.offsetHeight);
    }
  }, [proj.name, stats.count, clusterList.length]);

  const [offsets, setOffsets] = useState<Record<string, { x: number; y: number }>>(() => {
    return proj.cluster_offsets || {};
  });

  useEffect(() => {
    if (proj.cluster_offsets) {
      setOffsets(proj.cluster_offsets);
    }
  }, [proj.cluster_offsets]);

  const [measuredHeights, setMeasuredHeights] = useState<Record<string, number>>({});
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const registerCardRef = (key: string, el: HTMLDivElement | null) => {
    cardRefs.current[key] = el;
    if (el) {
      const h = el.offsetHeight;
      if (h > 0 && measuredHeights[key] !== h) {
        // Zapobieganie błędom Maximum update depth exceeded - odroczenie do rAF poza fazę commitu DOM
        requestAnimationFrame(() => {
          setMeasuredHeights((prev) => (prev[key] === h ? prev : { ...prev, [key]: h }));
        });
      }
    }
  };

  const [draggingKey, setDraggingKey] = useState<string | null>(null);

  const handleClusterMouseDown = (key: string, desc: string, defaultOffset: { x: number; y: number }, e: ReactMouseEvent) => {
    if (e.button !== 0) return;
    e.stopPropagation();

    // Jeśli trwa łączenie klastrów/klamry, nie przeciągaj — kliknięcie obsłuży onClick
    if (macroClusterLinkSource) {
      return;
    }

    onSelectCluster({ projectId: proj.id, kind: 'cluster', key, label: desc });

    const startClientX = e.clientX;
    const startClientY = e.clientY;
    const current = offsets[key] || defaultOffset;
    const startX = typeof current?.x === 'number' && Number.isFinite(current.x) ? current.x : (defaultOffset?.x ?? 0);
    const startY = typeof current?.y === 'number' && Number.isFinite(current.y) ? current.y : (defaultOffset?.y ?? 0);
    let moved = false;

    const currentScale = scale && Number.isFinite(scale) && scale > 0.01 ? scale : 0.15;

    let latestPos = { x: startX, y: startY };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const dx = (moveEvent.clientX - startClientX) / currentScale;
      const dy = (moveEvent.clientY - startClientY) / currentScale;
      if (!Number.isFinite(dx) || !Number.isFinite(dy)) return;

      if (!moved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
        moved = true;
        setDraggingKey(key);
      }
      if (moved) {
        let nextX = Math.round(startX + dx);
        let nextY = Math.round(startY + dy);

        // Magnetyczne wyrównywanie kart spiętych klamrą w osi pionowej (dla idealnie prostej klamry)
        const currentDesc = clusterList.find(([k]) => k === key)?.[1];
        const matchingBracket = proj.brackets?.find((b) =>
          (b.node_ids || []).some((nid) => nid === key || (currentDesc && proj.cluster_descriptions?.[nid]?.trim() === currentDesc.trim()))
        );

        if (matchingBracket) {
          const otherBox = clusterBoxes.find((b) =>
            b.key !== key && (matchingBracket.node_ids || []).some((nid) => nid === b.key || (b.desc && proj.cluster_descriptions?.[nid]?.trim() === b.desc.trim()))
          );
          if (otherBox && Number.isFinite(otherBox.x) && Math.abs(nextX - otherBox.x) <= 18) {
            nextX = otherBox.x;
          }
        }

        latestPos = { x: nextX, y: nextY };
        setOffsets((prev) => ({
          ...prev,
          [key]: latestPos,
        }));
      }
    };

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      setDraggingKey(null);

      if (moved && onUpdateClusterOffset) {
        onUpdateClusterOffset(proj.id, key, latestPos);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const actualCardH = cardHeight > 0 ? cardHeight : PROJECT_CARD_HEIGHT;

  const clusterBoxes: MacroClusterBox[] = clusterList.map(([key, desc], cIdx) => {
    const def = getDefaultClusterOffset(cIdx, clusterList.length);
    const cPos = offsets[key] || def;
    const realH = measuredHeights[key] || estimateClusterCardHeight(desc);
    return {
      key,
      desc,
      x: cPos.x,
      y: cPos.y,
      width: CLUSTER_CARD_WIDTH,
      height: realH,
    };
  });

  const macroBrackets = computeMacroBracketGeometries(
    proj.brackets,
    proj.cluster_descriptions,
    clusterBoxes,
    { x: PROJECT_CARD_WIDTH / 2, y: actualCardH / 2 }
  );

  const activeBracketedKeys = new Set(
    macroBrackets.filter((mb) => mb.mode === 'bracket').flatMap((mb) => mb.clusterKeys)
  );

  return (
    <div
      ref={cardRef}
      key={proj.id}
      data-testid={`project-island-${proj.id}`}
      data-project-id={proj.id}
      data-selected={isSelected}
      className={`absolute rounded-2xl border pointer-events-auto p-4 select-none ${
        draggingMacroProjId === proj.id
          ? 'cursor-grabbing !transition-none scale-[1.01]'
          : isLinkingSource
          ? 'scale-[1.02] transition-colors duration-150'
          : 'transition-colors duration-150'
      }`}
      style={{
        left: pos.x,
        top: pos.y,
        width: PROJECT_CARD_WIDTH,
        minHeight: PROJECT_CARD_HEIGHT,
        height: 'auto',
        backgroundColor: '#141414',
        borderColor: isLinkingSource || isSelected || isCurrentActive
          ? 'rgba(255, 199, 153, 0.65)'
          : '#242424',
        boxShadow: isLinkingSource || isSelected || isCurrentActive
          ? '0 0 0 1px rgba(255, 199, 153, 0.25), 0 16px 36px -4px rgba(0, 0, 0, 0.8)'
          : '0 12px 28px -6px rgba(0, 0, 0, 0.6), inset 0 1px 1px 0 rgba(255, 255, 255, 0.03)',
        zIndex: draggingMacroProjId === proj.id ? 100 : isLinkingSource ? 30 : isSelected ? 25 : isCurrentActive ? 20 : 10,
        cursor: 'grab',
      }}
      onClick={(e) => {
        e.stopPropagation();
        // Aktywne łączenie klastra/klamry -> połącz z tym projektem (kind: 'project').
        if (macroClusterLinkSource) {
          onClickClusterLink({ projectId: proj.id, kind: 'project', key: proj.id, label: proj.name });
          return;
        }
        if (macroLinkingMode && macroLinkSourceId) {
          if (macroLinkSourceId !== proj.id) {
            connectProjects(macroLinkSourceId, proj.id);
          } else {
            setMacroLinking(false, null);
          }
        } else {
          onSelectCluster(null);
          setSelectedProjectId(proj.id);
        }
      }}
      onMouseDown={(e) => startDraggingMacroProject(proj.id, pos.x, pos.y, e)}
      onDoubleClick={(e) => {
        e.stopPropagation();
        void diveIntoProject(proj.id);
      }}
    >
      {/* Wnętrze karty wyniesione do warstwy z-10 nad liniami SVG */}
      <div className="relative z-10 flex flex-col justify-between h-full w-full pointer-events-auto gap-1">
        {/* Rząd 1: Wskaźnik, Pełna Nazwa Projektu i Przycisk Usuń */}
        <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className={`w-2 h-2 rounded-full shrink-0 ${theme === 'dark' ? 'bg-[#FFC799]' : 'bg-slate-700'}`} />
          {isEditingThis ? (
            <input
              type="text"
              autoFocus
              value={editingProjectName}
              onChange={(e) => setEditingProjectName(e.target.value)}
              onBlur={() => void handleSaveRename(proj.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void handleSaveRename(proj.id);
                if (e.key === 'Escape') setEditingProjectId(null);
              }}
              className="w-full text-sm font-semibold bg-transparent border-b border-[#FFC799] outline-none text-white"
              placeholder="Nazwa projektu..."
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
            />
          ) : (
            <span
              onDoubleClick={(e) => {
                e.stopPropagation();
                handleStartRename(proj, e);
              }}
              className="text-sm font-semibold truncate text-white cursor-text hover:underline"
              title="Kliknij dwukrotnie, aby zmienić nazwę"
            >
              {proj.name}
            </span>
          )}
        </div>

        {projects.length > 1 && (
          <button
            tabIndex={-1}
            data-testid={`macro-delete-${proj.id}`}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => handleDeleteProject(proj.id, e)}
            className="w-6 h-6 flex items-center justify-center rounded-lg text-[#777] hover:text-[#ff8080] hover:bg-red-500/10 transition-colors cursor-pointer"
            title="Usuń projekt"
            aria-label="Usuń projekt"
          >
            <CloseIcon />
          </button>
        )}
      </div>

      {/* Rząd 2: Pasek stanu i licznik notatek */}
      <div className="flex items-center justify-between text-xs py-1 border-t border-b border-[#222222] my-0.5">
        <span className="text-[#777] font-medium text-[11px]">
          Tablica
        </span>
        <span
          className={`font-medium px-2 py-0.5 rounded-full text-[11px] border ${
            isCurrentActive
              ? theme === 'dark'
                ? 'bg-[rgba(255,199,153,0.1)] border-[rgba(255,199,153,0.25)] text-[#FFC799]'
                : 'bg-blue-500/10 border-blue-500/30 text-blue-600'
              : theme === 'dark'
              ? 'bg-[#121212] border-[#222222] text-[#888]'
              : 'bg-slate-100 border-slate-200 text-slate-600'
          }`}
        >
          {stats.count === 1 ? '1 notatka' : `${stats.count} notatek`}
        </span>
      </div>

        {/* Rząd 3: Dolny pasek akcji */}
        <div className="pt-0.5">
          <button
            data-testid={`dive-project-btn-${proj.id}`}
            onClick={(e) => {
              e.stopPropagation();
              void diveIntoProject(proj.id);
            }}
            className={`w-full py-1.5 px-3 rounded-lg font-medium text-xs flex items-center justify-center gap-1.5 shadow-sm transition-colors cursor-pointer ${
              theme === 'dark'
                ? 'bg-[#202020] hover:bg-[#282828] text-white border border-[#2a2a2a]'
                : 'bg-slate-900 hover:bg-slate-800 text-white'
            }`}
            title="Otwórz notatki tego projektu"
          >
            <span>Otwórz projekt</span>
            <span className="text-xs font-bold text-[#FFC799]">→</span>
          </button>
        </div>
      </div>

      {/* Dynamiczne organiczne linie łączące kartę projektu z klastrami naokoło i klamrami */}
      {clusterList.length > 0 && (() => {
        const SVG_PAD = 1500;

        const renderStemLine = (
          targetX: number,
          targetY: number,
          lineKey: string,
          isDragging: boolean
        ) => {
          if (!Number.isFinite(targetX) || !Number.isFinite(targetY)) return null;
          const cardCenterX = PROJECT_CARD_WIDTH / 2;
          const cardCenterY = Math.round(actualCardH / 2);
          const dx = targetX - cardCenterX;
          const dy = targetY - cardCenterY;

          let startX = cardCenterX;
          let startY = cardCenterY;

          if (Math.abs(dx) >= Math.abs(dy)) {
            if (dx > 0) {
              startX = PROJECT_CARD_WIDTH;
              startY = cardCenterY;
            } else {
              startX = 0;
              startY = cardCenterY;
            }
          } else {
            if (dy > 0) {
              startX = cardCenterX;
              startY = actualCardH;
            } else {
              startX = cardCenterX;
              startY = 0;
            }
          }

          const sX = startX + SVG_PAD;
          const sY = startY + SVG_PAD;
          const destX = targetX + SVG_PAD;
          const destY = targetY + SVG_PAD;

          const distX = Math.abs(destX - sX);
          const distY = Math.abs(destY - sY);

          let cp1X = sX;
          let cp1Y = sY;
          let cp2X = destX;
          let cp2Y = destY;

          if (Math.abs(dx) >= Math.abs(dy)) {
            const bend = Math.min(distX * 0.45, 90);
            const dir = dx > 0 ? 1 : -1;
            cp1X = sX + bend * dir;
            cp2X = destX - bend * dir;
          } else {
            const bend = Math.min(distY * 0.45, 90);
            const dir = dy > 0 ? 1 : -1;
            cp1Y = sY + bend * dir;
            cp2Y = destY - bend * dir;
          }

          const pathD = `M ${sX} ${sY} C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${destX} ${destY}`;

          return (
            <g key={`line-group-${lineKey}`}>
              <path
                d={pathD}
                fill="none"
                stroke={theme === 'dark' ? 'rgba(255, 199, 153, 0.12)' : 'rgba(59, 130, 246, 0.12)'}
                strokeWidth={4}
                strokeLinecap="round"
              />
              <path
                d={pathD}
                fill="none"
                stroke={
                  isDragging
                    ? theme === 'dark' ? '#FFC799' : '#2563eb'
                    : theme === 'dark' ? 'rgba(255, 199, 153, 0.55)' : 'rgba(59, 130, 246, 0.55)'
                }
                strokeWidth={isDragging ? 2.2 : 1.75}
                strokeDasharray={isDragging ? undefined : '5 4'}
                strokeLinecap="round"
              />
              <circle cx={sX} cy={sY} r={2.5} fill={theme === 'dark' ? '#FFC799' : '#3b82f6'} />
              <circle cx={destX} cy={destY} r={isDragging ? 3.5 : 2.5} fill={theme === 'dark' ? '#FFC799' : '#3b82f6'} />
            </g>
          );
        };

        return (
          <>
            <svg
              className="absolute pointer-events-none z-0"
              style={{
                top: -SVG_PAD,
                left: -SVG_PAD,
                width: PROJECT_CARD_WIDTH + SVG_PAD * 2,
                height: actualCardH + SVG_PAD * 2,
                overflow: 'visible',
              }}
            >
              {/* 1. Linie do klastrów wolnych lub oddalonych */}
              {clusterList.map(([key], cIdx) => {
                if (activeBracketedKeys.has(key)) return null;
                const def = getDefaultClusterOffset(cIdx, clusterList.length);
                const cPos = offsets[key] || def;
                const isDraggingThis = draggingKey === key;
                const targetX = cPos.x + (cPos.x < 0 ? CLUSTER_CARD_WIDTH : 0);
                const targetY = cPos.y + 24;
                return renderStemLine(targetX, targetY, key, isDraggingThis);
              })}

              {/* 2. Linie do aktywnych klamer CAD (jedno wspólne ramie z projektu) */}
              {macroBrackets
                .filter((mb) => mb.mode === 'bracket')
                .map((mb) => {
                  const isAnyDragging = mb.clusterKeys.some((k) => draggingKey === k);
                  return renderStemLine(
                    mb.stemTargetX,
                    mb.stemTargetY,
                    `bracket-${mb.bracketId}`,
                    isAnyDragging
                  );
                })}
            </svg>

            {/* Warstwa klamer wektorowych CAD i linii powiązań tether na orbicie */}
            {macroBrackets.length > 0 && (
              <svg className="absolute inset-0 pointer-events-none overflow-visible w-full h-full z-10">
                {macroBrackets.map((mb) => {
                  if (mb.mode === 'bracket') {
                    return (
                      <path
                        key={`macro-bracket-svg-${mb.bracketId}`}
                        d={mb.pathD}
                        fill="none"
                        stroke={theme === 'dark' ? '#555555' : '#888888'}
                        strokeWidth={1.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="transition-all duration-75"
                      />
                    );
                  }
                  if (mb.tetherPathD) {
                    return (
                      <path
                        key={`macro-tether-svg-${mb.bracketId}`}
                        d={mb.tetherPathD}
                        fill="none"
                        stroke={
                          theme === 'dark'
                            ? 'rgba(255, 199, 153, 0.35)'
                            : 'rgba(37, 99, 235, 0.35)'
                        }
                        strokeWidth={1.5}
                        strokeDasharray="4 4"
                        strokeLinecap="round"
                        className="transition-all duration-75"
                      />
                    );
                  }
                  return null;
                })}
              </svg>
            )}

            {/* Kafelki z nazwami klamer CAD i etykiety tetheringu */}
            {macroBrackets.map((mb) => {
              if (mb.mode === 'bracket') {
                const isBracketSelected =
                  macroSelectedClusterRef?.projectId === proj.id &&
                  macroSelectedClusterRef.kind === 'bracket' &&
                  macroSelectedClusterRef.key === mb.bracketId;
                const isBracketLinkingSource =
                  macroClusterLinkSource?.projectId === proj.id &&
                  macroClusterLinkSource.kind === 'bracket' &&
                  macroClusterLinkSource.key === mb.bracketId;

                let positionClass = '';
                if (mb.side === 'left') positionClass = '-translate-x-full -translate-y-1/2';
                else if (mb.side === 'right') positionClass = '-translate-y-1/2';
                else if (mb.side === 'top') positionClass = '-translate-x-1/2 -translate-y-full';
                else positionClass = '-translate-x-1/2';

                return (
                  <div
                    key={`macro-bracket-label-${mb.bracketId}`}
                    className={`absolute z-30 pointer-events-auto select-none ${positionClass}`}
                    style={{ left: mb.labelX, top: mb.labelY }}
                    onClick={(e) => {
                      e.stopPropagation();
                      const ref: MacroClusterRef = {
                        projectId: proj.id,
                        kind: 'bracket',
                        key: mb.bracketId,
                        label: mb.name || 'Klamra',
                      };
                      if (macroClusterLinkSource) {
                        onClickClusterLink(ref);
                      } else {
                        onSelectCluster(ref);
                      }
                    }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      void diveIntoProject(proj.id, mb.clusterKeys[0]);
                    }}
                    title={`Klamra: ${mb.name} • Kliknij: zaznacz • Podwójny klik: przejdź • Tab: połącz`}
                  >
                    <div
                      className={`rounded-xl px-3 py-1.5 shadow-xl text-xs font-semibold text-white transition-all cursor-pointer flex items-start gap-1.5 backdrop-blur-sm group max-w-[220px] ${
                        isBracketLinkingSource
                          ? 'bg-[#141414] border-2 border-[#FFC799] ring-2 ring-[#FFC799] scale-105 shadow-2xl'
                          : isBracketSelected
                          ? 'bg-[#141414] border border-[#FFC799] ring-2 ring-[#FFC799]/60'
                          : 'bg-[#141414]/95 border border-[#383838] hover:border-[#FFC799]'
                      }`}
                    >
                      <span className="text-[10px] text-[#FFC799] font-bold shrink-0 mt-0.5">⎴</span>
                      <span className="whitespace-normal break-words leading-tight text-left">{mb.name}</span>
                    </div>
                  </div>
                );
              }

              if (mb.mode === 'tether' && mb.tetherLabelX !== undefined && mb.tetherLabelY !== undefined) {
                const isTetherSelected =
                  macroSelectedClusterRef?.projectId === proj.id &&
                  macroSelectedClusterRef.kind === 'bracket' &&
                  macroSelectedClusterRef.key === mb.bracketId;
                const isTetherLinkingSource =
                  macroClusterLinkSource?.projectId === proj.id &&
                  macroClusterLinkSource.kind === 'bracket' &&
                  macroClusterLinkSource.key === mb.bracketId;

                return (
                  <div
                    key={`macro-tether-label-${mb.bracketId}`}
                    className="absolute z-30 pointer-events-auto select-none -translate-x-1/2 -translate-y-1/2"
                    style={{ left: mb.tetherLabelX, top: mb.tetherLabelY }}
                    onClick={(e) => {
                      e.stopPropagation();
                      const ref: MacroClusterRef = {
                        projectId: proj.id,
                        kind: 'bracket',
                        key: mb.bracketId,
                        label: mb.name || 'Klamra',
                      };
                      if (macroClusterLinkSource) {
                        onClickClusterLink(ref);
                      } else {
                        onSelectCluster(ref);
                      }
                    }}
                    title={`Klamra (daleka): ${mb.name || 'Klamra'} • Kliknij: zaznacz • Tab: połącz`}
                  >
                    <div
                      className={`rounded-xl px-2.5 py-1 text-[9px] text-[#FFC799] font-medium shadow-md backdrop-blur-sm flex items-start gap-1 max-w-[200px] cursor-pointer ${
                        isTetherLinkingSource
                          ? 'bg-[#141414] border-2 border-[#FFC799] ring-2 ring-[#FFC799] scale-105 shadow-2xl'
                          : isTetherSelected
                          ? 'bg-[#141414] border border-[#FFC799] ring-2 ring-[#FFC799]/60'
                          : 'bg-[#141414]/90 border border-[#FFC799]/40 hover:border-[#FFC799]'
                      }`}
                    >
                      <span className="text-[9px] shrink-0 mt-0.5">⎴</span>
                      <span className="whitespace-normal break-words leading-tight text-left">{mb.name}</span>
                    </div>
                  </div>
                );
              }

              return null;
            })}
          </>
        );
      })()}

      {/* Klastry rozmieszczone naokoło projektu (ruchome drag & drop, styl Cortexa) */}
      {clusterList.map(([key, desc], cIdx) => {
        const def = getDefaultClusterOffset(cIdx, clusterList.length);
        const cPos = offsets[key] || def;
        const matchingNodeIds = Object.entries(proj.cluster_descriptions || {})
          .filter(([, d]) => d?.trim() === desc)
          .map(([k]) => k);
        const bracketForCluster = proj.brackets?.find((b) =>
          (b.node_ids || []).some((nid) => matchingNodeIds.includes(nid) || nid === key)
        );
        const isDraggingThis = draggingKey === key;
        const isClusterSelected =
          macroSelectedClusterRef?.projectId === proj.id &&
          macroSelectedClusterRef.kind === 'cluster' &&
          macroSelectedClusterRef.key === key;
        const isClusterLinkingSource =
          macroClusterLinkSource?.projectId === proj.id &&
          macroClusterLinkSource.kind === 'cluster' &&
          macroClusterLinkSource.key === key;

        return (
          <div
            key={key}
            ref={(el) => registerCardRef(key, el)}
            data-testid={`macro-cluster-satellite-${proj.id}-${key}`}
            onMouseDown={(e) => handleClusterMouseDown(key, desc, def, e)}
            onClick={(e) => {
              e.stopPropagation();
              if (macroClusterLinkSource) {
                onClickClusterLink({ projectId: proj.id, kind: 'cluster', key, label: desc });
              } else {
                onSelectCluster({ projectId: proj.id, kind: 'cluster', key, label: desc });
              }
            }}
            onDoubleClick={(e) => {
              e.stopPropagation();
              void diveIntoProject(proj.id, key);
            }}
            className={`absolute p-2.5 rounded-xl border shadow-lg cursor-grab active:cursor-grabbing pointer-events-auto z-20 select-none group ${
              isDraggingThis
                ? '!cursor-grabbing scale-105 z-50 ring-1 ring-[#FFC799] shadow-2xl transition-none'
                : isClusterLinkingSource
                  ? 'z-50 ring-2 ring-[#FFC799] scale-105 shadow-2xl'
                  : isClusterSelected
                    ? 'z-40 ring-2 ring-[#FFC799]/60'
                    : 'transition-all duration-75 hover:scale-[1.02]'
            } ${
              theme === 'dark'
                ? 'bg-[#141414] border-[#282828] hover:bg-[#1a1a1a] hover:border-[#FFC799]/60 shadow-black/80'
                : 'bg-white border-slate-200 hover:border-blue-500/60 shadow-slate-300'
            }`}
            style={{
              width: `${CLUSTER_CARD_WIDTH}px`,
              left: `${cPos.x}px`,
              top: `${cPos.y}px`,
            }}
            title="Kliknij: zaznacz • Podwójny klik: wejdź do projektu • Tab: połącz"
          >
            <div className="flex items-center justify-between gap-1 mb-1 pointer-events-none">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 group-hover:scale-125 transition-transform ${
                  theme === 'dark' ? 'bg-[#FFC799]' : 'bg-blue-600'
                }`} />
                <span className={`text-[10px] font-bold tracking-wider uppercase ${
                  theme === 'dark' ? 'text-[#FFC799]' : 'text-blue-600'
                }`}>
                  Klaster {cIdx + 1}
                </span>
              </div>
              {bracketForCluster && (() => {
                const mbForThis = macroBrackets.find((mb) => (mb.clusterKeys || []).includes(key));
                if (mbForThis && mbForThis.mode === 'bracket') return null;
                return (
                  <span
                    className="text-[9px] text-[#FFC799]/90 bg-[#FFC799]/10 border border-[#FFC799]/30 px-1.5 py-0.5 rounded truncate max-w-[105px] font-semibold"
                    title={`Spięte klamrą: ${bracketForCluster.name || 'Klamra'}`}
                  >
                    {bracketForCluster.name || 'Klamra'}
                  </span>
                );
              })()}
            </div>
            <p className={`text-xs font-medium leading-snug break-words pointer-events-none ${
              theme === 'dark' ? 'text-white/90' : 'text-slate-800'
            }`} style={{ overflowWrap: 'anywhere' }}>
              {desc}
            </p>
          </div>
        );
      })}
    </div>
  );
}
