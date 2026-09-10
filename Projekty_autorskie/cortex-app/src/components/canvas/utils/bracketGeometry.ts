import type { ProjektyBracket, ProjektyNode } from '../../../types';
import { NODE_WIDTH, NODE_HEIGHT } from '../constants';
import type { ClusterLayout } from './clusterGeometry';

export interface ComputedBracketGeometry {
  id: string;
  name: string;
  nodeIds: string[];
  isVertical: boolean;
  side: 'left' | 'right' | 'top' | 'bottom';
  track: number;
  pathD: string;
  labelX: number;
  labelY: number;
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  nodeCount: number;
  clusterCount?: number;
}

export function calculateBracketGeometries(
  brackets: ProjektyBracket[],
  nodes: ProjektyNode[],
  clusterLayouts?: ClusterLayout[]
): ComputedBracketGeometry[] {
  if (!brackets || brackets.length === 0 || !nodes || nodes.length === 0) {
    return [];
  }

  const nodesMap = new Map<string, ProjektyNode>();
  nodes.forEach((n) => nodesMap.set(n.id, n));

  // Krok 1: Filtracja i wyliczenie obwiedni wezlow lub wysp klastrow dla kazdej klamry
  const precomputed: Array<{
    bracket: ProjektyBracket;
    validNodes: ProjektyNode[];
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    isVertical: boolean;
    side: 'left' | 'right' | 'top' | 'bottom';
    clusterCount?: number;
  }> = [];

  brackets.forEach((b) => {
    const validNodes = (b.node_ids || [])
      .map((id) => nodesMap.get(id))
      .filter((n): n is ProjektyNode => Boolean(n));

    // Determinizm: klamra musi miec co najmniej 2 istniejace wezly
    if (validNodes.length < 2) {
      return;
    }

    // Sprawdzamy czy klamra obejmuje cale strefy klastrow z rozszerzonymi scianami
    const matchingClusters = (clusterLayouts || []).filter((cl) =>
      cl.cluster.some((n) => (b.node_ids || []).includes(n.id))
    );

    let minX: number;
    let maxX: number;
    let minY: number;
    let maxY: number;

    if (matchingClusters.length >= 2) {
      minX = Math.min(...matchingClusters.map((c) => c.minX));
      maxX = Math.max(...matchingClusters.map((c) => c.maxX));
      minY = Math.min(...matchingClusters.map((c) => c.minY));
      maxY = Math.max(...matchingClusters.map((c) => c.maxY));
    } else {
      minX = Math.min(...validNodes.map((n) => n.x));
      maxX = Math.max(...validNodes.map((n) => n.x + (n.width || NODE_WIDTH)));
      minY = Math.min(...validNodes.map((n) => n.y));
      maxY = Math.max(...validNodes.map((n) => n.y + (n.height || NODE_HEIGHT)));
    }

    // Deterministyczne wyznaczenie osi (pion vs poziom)
    let isVertical = true;
    if (b.orientation === 'vertical') {
      isVertical = true;
    } else if (b.orientation === 'horizontal') {
      isVertical = false;
    } else if (matchingClusters.length >= 2) {
      const first = matchingClusters[0];
      const last = matchingClusters[matchingClusters.length - 1];
      const dx = Math.abs(last.contentCenterX - first.contentCenterX);
      const dy = Math.abs(last.contentCenterY - first.contentCenterY);
      if (dx === 0 && dy === 0) {
        isVertical = (maxY - minY) >= (maxX - minX);
      } else {
        isVertical = dy >= dx;
      }
    } else {
      const spanX = maxX - minX;
      const spanY = maxY - minY;
      isVertical = spanY >= spanX;
    }

    precomputed.push({
      bracket: b,
      validNodes,
      minX,
      maxX,
      minY,
      maxY,
      isVertical,
      side: b.side ?? (isVertical ? 'left' : 'top'),
      clusterCount: matchingClusters.length >= 2 ? matchingClusters.length : undefined,
    });
  });

  // Krok 2: Przydzial torow (Multi-Track) dla unikania kolizji
  // Dzielimy klamry na pionowe i poziome
  const verticalItems = precomputed.filter((p) => p.isVertical);
  const horizontalItems = precomputed.filter((p) => !p.isVertical);

  const assignTracks = (
    items: typeof precomputed,
    getRange: (item: (typeof precomputed)[0]) => [number, number]
  ): Map<string, number> => {
    const trackMap = new Map<string, number>();

    // Sortujemy po pozycji poczatkowej
    const sorted = [...items].sort((a, b) => getRange(a)[0] - getRange(b)[0]);

    sorted.forEach((item) => {
      const [start, end] = getRange(item);
      let assignedTrack = item.bracket.track ?? 0;

      // Sprawdzamy, czy ten tor jest wolny wsrod wczesniej przydzielonych
      let trackOccupied = true;
      while (trackOccupied) {
        trackOccupied = sorted.some((other) => {
          if (other.bracket.id === item.bracket.id) return false;
          if (!trackMap.has(other.bracket.id)) return false;
          if (trackMap.get(other.bracket.id) !== assignedTrack) return false;

          const [oStart, oEnd] = getRange(other);
          // Sprawdzenie kolizji przedzialow (Interval Overlap)
          return Math.max(start, oStart) < Math.min(end, oEnd);
        });

        if (trackOccupied) {
          assignedTrack += 1;
        }
      }

      trackMap.set(item.bracket.id, assignedTrack);
    });

    return trackMap;
  };

  const vTrackMap = assignTracks(verticalItems, (item) => [item.minY, item.maxY]);
  const hTrackMap = assignTracks(horizontalItems, (item) => [item.minX, item.maxX]);

  // Krok 3: Generowanie sciezki SVG i pozycji etykiet
  const result: ComputedBracketGeometry[] = [];

  precomputed.forEach((item) => {
    const { bracket, validNodes, minX, maxX, minY, maxY, isVertical, side, clusterCount } = item;
    const track = isVertical
      ? vTrackMap.get(bracket.id) ?? 0
      : hTrackMap.get(bracket.id) ?? 0;

    let pathD = '';
    let labelX = 0;
    let labelY = 0;

    const hasClusters = clusterCount !== undefined && clusterCount >= 2;

    if (isVertical) {
      // Pionowa: klamra po lewej lub prawej stronie grupy.
      const baseOffset = hasClusters ? 76 : 36;
      const trackOffset = baseOffset + track * 56;
      const leftSide = side === 'left';
      const bracketX = leftSide ? minX - trackOffset : maxX + trackOffset;
      const tipX = leftSide ? bracketX - 16 : bracketX + 16;
      const midY = (minY + maxY) / 2;
      const startY = minY + 14;
      const endY = maxY - 14;
      const r = Math.min(10, Math.max(2, (maxY - minY) / 8));
      // Haczyki biegną w stronę grupy: lewa klamra -> w prawo (+), prawa -> w lewo (-)
      const bend = leftSide ? 16 : -16;

      pathD = `
        M ${bracketX + bend} ${startY}
        Q ${bracketX} ${startY} ${bracketX} ${startY + r}
        L ${bracketX} ${midY - r}
        Q ${bracketX} ${midY} ${tipX} ${midY}
        Q ${bracketX} ${midY} ${bracketX} ${midY + r}
        L ${bracketX} ${endY - r}
        Q ${bracketX} ${endY} ${bracketX + bend} ${endY}
      `.trim();

      labelX = leftSide ? tipX - 12 : tipX + 12;
      labelY = midY;
    } else {
      // Pozioma: klamra na górze lub na dole grupy.
      const baseOffset = hasClusters ? 64 : 36;
      const trackOffset = baseOffset + track * 56;
      const topSide = side === 'top';
      const bracketY = topSide ? minY - trackOffset : maxY + trackOffset;
      const tipY = topSide ? bracketY - 16 : bracketY + 16;
      const midX = (minX + maxX) / 2;
      const startX = minX + 14;
      const endX = maxX - 14;
      const r = Math.min(10, Math.max(2, (maxX - minX) / 8));
      // Haczyki biegną w stronę grupy: górna klamra -> w dół (+), dolna -> w górę (-)
      const bend = topSide ? 16 : -16;

      pathD = `
        M ${startX} ${bracketY + bend}
        Q ${startX} ${bracketY} ${startX + r} ${bracketY}
        L ${midX - r} ${bracketY}
        Q ${midX} ${bracketY} ${midX} ${tipY}
        Q ${midX} ${bracketY} ${midX + r} ${bracketY}
        L ${endX - r} ${bracketY}
        Q ${endX} ${bracketY} ${endX} ${bracketY + bend}
      `.trim();

      labelX = midX;
      labelY = topSide ? tipY - 10 : tipY + 10;
    }

    result.push({
      id: bracket.id,
      name: bracket.name || '',
      nodeIds: validNodes.map((n) => n.id),
      isVertical,
      side,
      track,
      pathD,
      labelX,
      labelY,
      minX,
      maxX,
      minY,
      maxY,
      nodeCount: validNodes.length,
      clusterCount,
    });
  });

  return result;
}
