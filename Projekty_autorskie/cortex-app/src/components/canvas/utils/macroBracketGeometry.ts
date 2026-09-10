import { ProjektyBracket } from '../../../types';

export interface MacroClusterBox {
  key: string;
  desc: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface MacroBracketGeometry {
  bracketId: string;
  name: string;
  mode: 'bracket' | 'tether';
  distance: number;
  isVertical: boolean;
  side: 'left' | 'right' | 'top' | 'bottom';
  pathD: string;
  labelX: number;
  labelY: number;
  stemTargetX: number;
  stemTargetY: number;
  tetherPathD?: string;
  tetherLabelX?: number;
  tetherLabelY?: number;
  clusterKeys: string[];
}

export function computeMacroBracketGeometries(
  brackets: ProjektyBracket[] | undefined,
  clusterDescriptions: Record<string, string> | undefined,
  clusterBoxes: MacroClusterBox[],
  projectCenter: { x: number; y: number }
): MacroBracketGeometry[] {
  if (!brackets || brackets.length === 0 || clusterBoxes.length < 2) {
    return [];
  }

  const results: MacroBracketGeometry[] = [];

  for (const bracket of brackets) {
    if (!bracket.node_ids || bracket.node_ids.length === 0) continue;

    // Znajdź powiązane klastry satelitarne
    const memberBoxes = clusterBoxes.filter((cBox) => {
      if (bracket.node_ids.includes(cBox.key)) return true;
      // Sprawdź czy jakikolwiek węzeł o tym samym opisie jest w klamrze
      if (clusterDescriptions) {
        const matchingIds = Object.entries(clusterDescriptions)
          .filter(([, desc]) => desc?.trim() === cBox.desc.trim())
          .map(([id]) => id);
        return bracket.node_ids.some((nid) => matchingIds.includes(nid));
      }
      return false;
    });

    if (memberBoxes.length < 2) continue;

    // Oblicz dystans między najbliższymi krawędziami klastrów
    let minGap = Infinity;
    if (memberBoxes.length === 2) {
      const b1 = memberBoxes[0];
      const b2 = memberBoxes[1];
      const gapX = Math.max(0, Math.max(b1.x, b2.x) - Math.min(b1.x + b1.width, b2.x + b2.width));
      const gapY = Math.max(0, Math.max(b1.y, b2.y) - Math.min(b1.y + b1.height, b2.y + b2.height));
      minGap = Math.hypot(gapX, gapY);
    } else {
      for (let i = 0; i < memberBoxes.length; i++) {
        for (let j = i + 1; j < memberBoxes.length; j++) {
          const b1 = memberBoxes[i];
          const b2 = memberBoxes[j];
          const gapX = Math.max(0, Math.max(b1.x, b2.x) - Math.min(b1.x + b1.width, b2.x + b2.width));
          const gapY = Math.max(0, Math.max(b1.y, b2.y) - Math.min(b1.y + b1.height, b2.y + b2.height));
          const d = Math.hypot(gapX, gapY);
          if (d < minGap) minGap = d;
        }
      }
    }

    // Próg odległości: poniżej 200px tworzy się pełna klamra CAD, powyżej inne subtelne oznaczenie (tether)
    const PROXIMITY_THRESHOLD = 200;
    const isClose = minGap <= PROXIMITY_THRESHOLD;

    let bMinX = Infinity;
    let bMaxX = -Infinity;
    let bMinY = Infinity;
    let bMaxY = -Infinity;

    for (const b of memberBoxes) {
      if (!Number.isFinite(b.x) || !Number.isFinite(b.y)) continue;
      const bw = Number.isFinite(b.width) ? b.width : 220;
      const bh = Number.isFinite(b.height) ? b.height : 60;
      bMinX = Math.min(bMinX, b.x);
      bMaxX = Math.max(bMaxX, b.x + bw);
      bMinY = Math.min(bMinY, b.y);
      bMaxY = Math.max(bMaxY, b.y + bh);
    }

    if (!Number.isFinite(bMinX) || !Number.isFinite(bMaxX) || !Number.isFinite(bMinY) || !Number.isFinite(bMaxY)) {
      continue;
    }

    let minCenterX = Infinity;
    let maxCenterX = -Infinity;
    let minCenterY = Infinity;
    let maxCenterY = -Infinity;

    for (const b of memberBoxes) {
      if (!Number.isFinite(b.x) || !Number.isFinite(b.y)) continue;
      const bw = Number.isFinite(b.width) ? b.width : 220;
      const bh = Number.isFinite(b.height) ? b.height : 60;
      const cx = b.x + bw / 2;
      const cy = b.y + bh / 2;
      minCenterX = Math.min(minCenterX, cx);
      maxCenterX = Math.max(maxCenterX, cx);
      minCenterY = Math.min(minCenterY, cy);
      maxCenterY = Math.max(maxCenterY, cy);
    }

    if (!Number.isFinite(minCenterX) || !Number.isFinite(maxCenterX) || !Number.isFinite(minCenterY) || !Number.isFinite(maxCenterY)) {
      continue;
    }

    const centerDeltaX = maxCenterX - minCenterX;
    const centerDeltaY = maxCenterY - minCenterY;

    // Jeśli rozrzut środków w pionie jest większy lub równy rozrzutowi w poziomie -> orientacja pionowa
    const isVertical = centerDeltaY >= centerDeltaX;

    const gCenterX = (bMinX + bMaxX) / 2;
    const gCenterY = (bMinY + bMaxY) / 2;
    const dx = gCenterX - projectCenter.x;
    const dy = gCenterY - projectCenter.y;

    let side: 'left' | 'right' | 'top' | 'bottom';
    if (isVertical) {
      side = dx < 0 ? 'left' : 'right';
    } else {
      side = dy < 0 ? 'top' : 'bottom';
    }

    const r = 8;
    let pathD = '';
    let labelX = 0;
    let labelY = 0;
    let stemTargetX = 0;
    let stemTargetY = 0;

    if (side === 'left') {
      const bracketX = Math.round(bMinX - 12);
      const tipX = bracketX - 10;
      const startY = Math.round(bMinY + 6);
      const endY = Math.max(startY + 16, Math.round(bMaxY - 6));
      const midY = Math.round((startY + endY) / 2);

      pathD = `
        M ${bracketX + 6} ${startY}
        Q ${bracketX} ${startY} ${bracketX} ${startY + r}
        L ${bracketX} ${midY - r}
        Q ${bracketX} ${midY} ${tipX} ${midY}
        Q ${bracketX} ${midY} ${bracketX} ${midY + r}
        L ${bracketX} ${endY - r}
        Q ${bracketX} ${endY} ${bracketX + 6} ${endY}
      `.trim();

      labelX = tipX - 8;
      labelY = midY;
      stemTargetX = bMaxX;
      stemTargetY = midY;
    } else if (side === 'right') {
      const bracketX = Math.round(bMaxX + 12);
      const tipX = bracketX + 10;
      const startY = Math.round(bMinY + 6);
      const endY = Math.max(startY + 16, Math.round(bMaxY - 6));
      const midY = Math.round((startY + endY) / 2);

      pathD = `
        M ${bracketX - 6} ${startY}
        Q ${bracketX} ${startY} ${bracketX} ${startY + r}
        L ${bracketX} ${midY - r}
        Q ${bracketX} ${midY} ${tipX} ${midY}
        Q ${bracketX} ${midY} ${bracketX} ${midY + r}
        L ${bracketX} ${endY - r}
        Q ${bracketX} ${endY} ${bracketX - 6} ${endY}
      `.trim();

      labelX = tipX + 8;
      labelY = midY;
      stemTargetX = bMinX;
      stemTargetY = midY;
    } else if (side === 'top') {
      const bracketY = Math.round(bMinY - 12);
      const tipY = bracketY - 10;
      const startX = Math.round(bMinX + 6);
      const endX = Math.max(startX + 16, Math.round(bMaxX - 6));
      const midX = Math.round((startX + endX) / 2);

      pathD = `
        M ${startX} ${bracketY + 6}
        Q ${startX} ${bracketY} ${startX + r} ${bracketY}
        L ${midX - r} ${bracketY}
        Q ${midX} ${bracketY} ${midX} ${tipY}
        Q ${midX} ${bracketY} ${midX + r} ${bracketY}
        L ${endX - r} ${bracketY}
        Q ${endX} ${bracketY} ${endX} ${bracketY + 6}
      `.trim();

      labelX = midX;
      labelY = tipY - 8;
      stemTargetX = midX;
      stemTargetY = bMaxY;
    } else {
      // bottom
      const bracketY = Math.round(bMaxY + 12);
      const tipY = bracketY + 10;
      const startX = Math.round(bMinX + 6);
      const endX = Math.max(startX + 16, Math.round(bMaxX - 6));
      const midX = Math.round((startX + endX) / 2);

      pathD = `
        M ${startX} ${bracketY - 6}
        Q ${startX} ${bracketY} ${startX + r} ${bracketY}
        L ${midX - r} ${bracketY}
        Q ${midX} ${bracketY} ${midX} ${tipY}
        Q ${midX} ${bracketY} ${midX + r} ${bracketY}
        L ${endX - r} ${bracketY}
        Q ${endX} ${bracketY} ${endX} ${bracketY - 6}
      `.trim();

      labelX = midX;
      labelY = tipY + 8;
      stemTargetX = midX;
      stemTargetY = bMinY;
    }

    // Jeśli klastry są za daleko, generujemy tether (ścieżkę więzi)
    let tetherPathD: string | undefined;
    let tetherLabelX: number | undefined;
    let tetherLabelY: number | undefined;

    if (!isClose && memberBoxes.length >= 2) {
      const validBoxes = memberBoxes.filter((b) => Number.isFinite(b.x) && Number.isFinite(b.y));
      if (validBoxes.length >= 2) {
        const centers = validBoxes.map((b) => ({
          x: Math.round(b.x + (b.width || 220) / 2),
          y: Math.round(b.y + (b.height || 60) / 2),
        }));
        tetherPathD = centers.reduce(
          (acc, c, idx) => (idx === 0 ? `M ${c.x} ${c.y}` : `${acc} L ${c.x} ${c.y}`),
          '',
        );
        const sumX = centers.reduce((sum, c) => sum + c.x, 0);
        const sumY = centers.reduce((sum, c) => sum + c.y, 0);
        tetherLabelX = Math.round(sumX / centers.length);
        tetherLabelY = Math.round(sumY / centers.length);
      }
    }

    results.push({
      bracketId: bracket.id,
      name: bracket.name || 'Klamra',
      mode: isClose ? 'bracket' : 'tether',
      distance: minGap,
      isVertical,
      side,
      pathD,
      labelX,
      labelY,
      stemTargetX,
      stemTargetY,
      tetherPathD,
      tetherLabelX,
      tetherLabelY,
      clusterKeys: memberBoxes.map((b) => b.key),
    });
  }

  return results;
}
