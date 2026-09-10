import type { Projekt } from '../../../types';
import type { MacroClusterAnchor } from '../types';
import { getProjectMacroPosition } from './zoomMath';
import { PROJECT_CARD_WIDTH, PROJECT_CARD_HEIGHT } from '../constants';
import {
  CLUSTER_CARD_WIDTH,
  estimateClusterCardHeight,
  getDefaultClusterOffset,
} from '../components/MacroProjectCard';
import { computeMacroBracketGeometries } from './macroBracketGeometry';
import type { MacroClusterBox } from './macroBracketGeometry';

// Ta sama deduplikacja klastrów co w MacroProjectCard (jeden satelita per unikalny opis).
export function getUniqueClusters(proj: Projekt): { key: string; desc: string }[] {
  const map = new Map<string, { key: string; desc: string }>();
  for (const [key, desc] of Object.entries(proj.cluster_descriptions || {})) {
    const trimmed = desc?.trim();
    if (trimmed && !map.has(trimmed)) {
      map.set(trimmed, { key, desc: trimmed });
    }
  }
  return Array.from(map.values());
}

// Wylicza światowe pozycje (w układzie canvasu makro) klastrów i klamer danego projektu.
// Używane przez globalną warstwę linii do łączenia klastrów/klamer z różnych projektów
// oraz przy budowaniu kontekstu AI.
export function computeMacroClusterAnchors(
  proj: Projekt,
  idx: number,
  projects: Projekt[],
): MacroClusterAnchor[] {
  const anchors: MacroClusterAnchor[] = [];
  const pos = getProjectMacroPosition(proj, idx, projects.length);

  // Kotwica samego projektu (krawędzie karty projektu).
  anchors.push({
    anchorId: `${proj.id}:project:${proj.id}`,
    projectId: proj.id,
    kind: 'project',
    key: proj.id,
    label: proj.name,
    x: pos.x + PROJECT_CARD_WIDTH / 2,
    y: pos.y + PROJECT_CARD_HEIGHT / 2,
    box: { x: pos.x, y: pos.y, width: PROJECT_CARD_WIDTH, height: PROJECT_CARD_HEIGHT },
  });

  const clusterList = getUniqueClusters(proj);
  const offsets = proj.cluster_offsets || {};

  const clusterBoxes: MacroClusterBox[] = clusterList.map(({ key, desc }, cIdx) => {
    const def = getDefaultClusterOffset(cIdx, clusterList.length);
    const cPos = offsets[key] || def;
    return {
      key,
      desc,
      x: cPos.x,
      y: cPos.y,
      width: CLUSTER_CARD_WIDTH,
      height: estimateClusterCardHeight(desc),
    };
  });

  for (const box of clusterBoxes) {
    const worldX = pos.x + box.x;
    const worldY = pos.y + box.y;
    anchors.push({
      anchorId: `${proj.id}:cluster:${box.key}`,
      projectId: proj.id,
      kind: 'cluster',
      key: box.key,
      label: box.desc,
      x: worldX + box.width / 2,
      y: worldY + box.height / 2,
      box: { x: worldX, y: worldY, width: box.width, height: box.height },
    });
  }

  const bracketGeoms = computeMacroBracketGeometries(
    proj.brackets,
    proj.cluster_descriptions,
    clusterBoxes,
    { x: PROJECT_CARD_WIDTH / 2, y: PROJECT_CARD_HEIGHT / 2 },
  );

  for (const g of bracketGeoms) {
    // Zarówno pełna klamra (bracket), jak i daleka klamra (tether) — obie mogą być łączone.
    const isTether = g.mode === 'tether';
    const ax = isTether && g.tetherLabelX !== undefined ? g.tetherLabelX : g.labelX;
    const ay = isTether && g.tetherLabelY !== undefined ? g.tetherLabelY : g.labelY;
    const labelW = 160;
    const labelH = 36;
    anchors.push({
      anchorId: `${proj.id}:bracket:${g.bracketId}`,
      projectId: proj.id,
      kind: 'bracket',
      key: g.bracketId,
      label: g.name || 'Klamra',
      x: pos.x + ax,
      y: pos.y + ay,
      box: { x: pos.x + ax - labelW / 2, y: pos.y + ay - labelH / 2, width: labelW, height: labelH },
    });
  }

  return anchors;
}

