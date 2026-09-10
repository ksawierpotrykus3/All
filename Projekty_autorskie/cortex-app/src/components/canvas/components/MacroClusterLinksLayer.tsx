import { useMemo } from 'react';
import type { Projekt } from '../../../types';
import type { MacroClusterLink, MacroClusterRef } from '../types';
import { computeMacroClusterAnchors } from '../utils/macroClusterAnchors';
import { getNodePerimeterPoint } from '../utils/nodePlacement';

interface MacroClusterLinksLayerProps {
  theme: 'light' | 'dark';
  projects: Projekt[];
  links: MacroClusterLink[];
  onDeleteLink?: (id: string) => void;
  selectedLinkId?: string | null;
  onSelectLink?: (id: string | null) => void;
  macroClusterLinkSource?: MacroClusterRef | null;
  mouseCanvasPos?: { x: number; y: number } | null;
}

// Globalna warstwa rysująca połączenia między klastrami/klamrami/projektami w widoku makro.
// Linia łączy się z zewnętrznym obwodem kart (obwiednią), posiada szeroki obszar interaktywny
// (hitbox) umożliwiający pewne najechanie i usunięcie, oraz wygina się inteligentnie w osi X lub Y.
export function MacroClusterLinksLayer({
  theme,
  projects,
  links,
  onDeleteLink,
  selectedLinkId,
  onSelectLink,
  macroClusterLinkSource,
  mouseCanvasPos,
}: MacroClusterLinksLayerProps) {
  // Mapa anchorId -> kotwica (światowe współrzędne oraz obwiednia box).
  const anchorMap = useMemo(() => {
    const map = new Map<string, ReturnType<typeof computeMacroClusterAnchors>[0]>();
    for (let i = 0; i < projects.length; i++) {
      const anchors = computeMacroClusterAnchors(projects[i], i, projects);
      for (const a of anchors) {
        map.set(a.anchorId, a);
      }
    }
    return map;
  }, [projects]);

  const hasLinks = Boolean(links && links.length > 0);
  const hasPreview = Boolean(macroClusterLinkSource && mouseCanvasPos);

  if (!hasLinks && !hasPreview) return null;

  const stroke = theme === 'dark' ? 'rgba(255, 199, 153, 0.65)' : 'rgba(37, 99, 235, 0.65)';

  return (
    <svg
      className="absolute pointer-events-none overflow-visible"
      style={{ top: 0, left: 0, width: 10000, height: 10000, zIndex: 5 }}
    >
      <defs>
        <marker
          id="macro-cortex-arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={theme === 'dark' ? 'rgba(255, 199, 153, 0.75)' : 'rgba(37, 99, 235, 0.75)'} />
        </marker>
        <marker
          id="macro-cortex-arrow-active"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={theme === 'dark' ? '#FFC799' : '#2563eb'} />
        </marker>
      </defs>

      {links.map((link) => {
        const srcId = `${link.source_project_id}:${link.source_kind}:${link.source_key}`;
        const tgtId = `${link.target_project_id}:${link.target_kind}:${link.target_key}`;
        const s = anchorMap.get(srcId);
        const t = anchorMap.get(tgtId);
        if (!s || !t) return null;

        // Dynamiczne wyliczenie punktów styku na obwodzie (krawędzi) kart, by linia nie przecinała tekstu
        const sPt = s.box ? getNodePerimeterPoint(s.box, { x: t.x, y: t.y }, 4) : { x: s.x, y: s.y };
        const tPt = t.box ? getNodePerimeterPoint(t.box, { x: s.x, y: s.y }, 6) : { x: t.x, y: t.y };

        const dx = tPt.x - sPt.x;
        const dy = tPt.y - sPt.y;

        let cp1: { x: number; y: number };
        let cp2: { x: number; y: number };

        if (Math.abs(dx) >= Math.abs(dy)) {
          const bend = Math.max(Math.min(Math.abs(dx) * 0.45, 140), 40);
          const dir = dx >= 0 ? 1 : -1;
          cp1 = { x: sPt.x + bend * dir, y: sPt.y };
          cp2 = { x: tPt.x - bend * dir, y: tPt.y };
        } else {
          const bend = Math.max(Math.min(Math.abs(dy) * 0.45, 140), 40);
          const dir = dy >= 0 ? 1 : -1;
          cp1 = { x: sPt.x, y: sPt.y + bend * dir };
          cp2 = { x: tPt.x, y: tPt.y - bend * dir };
        }

        const d = `M ${sPt.x} ${sPt.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${tPt.x} ${tPt.y}`;
        const midX = (sPt.x + 3 * cp1.x + 3 * cp2.x + tPt.x) / 8;
        const midY = (sPt.y + 3 * cp1.y + 3 * cp2.y + tPt.y) / 8;

        const isSelected = selectedLinkId === link.id;

        return (
          <g key={link.id} className="group/clusterlink pointer-events-auto">
            {/* Szeroki niewidzialny hitbox (32px) pozwalający na łatwy hover i kliknięcie */}
            <path
              d={d}
              fill="none"
              stroke="transparent"
              strokeWidth={32}
              strokeLinecap="round"
              className="pointer-events-auto cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onSelectLink?.(link.id);
              }}
            />
            {/* Widoczna krzywa Béziera */}
            <path
              d={d}
              fill="none"
              stroke={isSelected ? (theme === 'dark' ? '#FFC799' : '#2563eb') : stroke}
              strokeWidth={isSelected ? 2.5 : 1.75}
              strokeDasharray={isSelected ? undefined : '6 5'}
              strokeLinecap="round"
              markerEnd={isSelected ? 'url(#macro-cortex-arrow-active)' : 'url(#macro-cortex-arrow)'}
              className="pointer-events-none transition-all duration-150"
            />
            {/* Punkty styku */}
            <circle cx={sPt.x} cy={sPt.y} r={3.5} fill={isSelected ? '#FFC799' : stroke} className="pointer-events-none" />
            <circle cx={tPt.x} cy={tPt.y} r={3.5} fill={isSelected ? '#FFC799' : stroke} className="pointer-events-none" />

            {/* Kapsułka akcji z czerwonym przyciskiem [ ✕ ] do usuwania połączenia */}
            {onDeleteLink && (
              <g
                className={`transition-opacity duration-150 pointer-events-auto ${
                  isSelected ? 'opacity-100' : 'opacity-0 group-hover/clusterlink:opacity-100'
                }`}
                transform={`translate(${midX}, ${midY})`}
                onMouseDown={(e) => e.stopPropagation()}
              >
                <rect
                  x="-16"
                  y="-12"
                  width="32"
                  height="24"
                  rx="7"
                  fill={theme === 'dark' ? '#1c1414' : '#ffffff'}
                  stroke={theme === 'dark' ? '#ff5555' : '#dc2626'}
                  strokeWidth={1.25}
                  className="shadow-xl cursor-pointer hover:scale-110 active:scale-95 transition-transform"
                  data-testid={`macro-link-delete-${link.id}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteLink(link.id);
                  }}
                />
                <text
                  x="0"
                  y="4"
                  fontSize="12"
                  fontWeight="bold"
                  textAnchor="middle"
                  fill={theme === 'dark' ? '#ff6b6b' : '#dc2626'}
                  pointerEvents="none"
                >
                  ✕
                </text>
              </g>
            )}
          </g>
        );
      })}

      {/* Dynamiczna linia podglądu podczas łączenia klastrów/klamer (gumka za kursorem) */}
      {macroClusterLinkSource &&
        mouseCanvasPos &&
        (() => {
          const srcId = `${macroClusterLinkSource.projectId}:${macroClusterLinkSource.kind}:${macroClusterLinkSource.key}`;
          const s = anchorMap.get(srcId);
          if (!s) return null;
          const t = mouseCanvasPos;
          const sPt = s.box ? getNodePerimeterPoint(s.box, t, 4) : { x: s.x, y: s.y };

          const dx = t.x - sPt.x;
          const dy = t.y - sPt.y;
          let cp1: { x: number; y: number };
          let cp2: { x: number; y: number };

          if (Math.abs(dx) >= Math.abs(dy)) {
            const bend = Math.max(Math.min(Math.abs(dx) * 0.45, 140), 40);
            const dir = dx >= 0 ? 1 : -1;
            cp1 = { x: sPt.x + bend * dir, y: sPt.y };
            cp2 = { x: t.x - bend * dir, y: t.y };
          } else {
            const bend = Math.max(Math.min(Math.abs(dy) * 0.45, 140), 40);
            const dir = dy >= 0 ? 1 : -1;
            cp1 = { x: sPt.x, y: sPt.y + bend * dir };
            cp2 = { x: t.x, y: t.y - bend * dir };
          }

          const d = `M ${sPt.x} ${sPt.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${t.x} ${t.y}`;
          const activeColor = theme === 'dark' ? '#FFC799' : '#2563eb';

          return (
            <g className="macro-cluster-preview-line pointer-events-none">
              <path
                d={d}
                fill="none"
                stroke={activeColor}
                strokeWidth={2.25}
                strokeDasharray="6 4"
                strokeLinecap="round"
                className="animate-pulse"
              />
              <circle cx={sPt.x} cy={sPt.y} r={4.5} fill={activeColor} />
              <circle cx={t.x} cy={t.y} r={4.5} fill={activeColor} className="animate-ping opacity-75" />
            </g>
          );
        })()}
    </svg>
  );
}
