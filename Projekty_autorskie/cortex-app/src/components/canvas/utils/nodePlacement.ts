import type { ProjektyNode, ProjektyEdge, Projekt } from '../../../types';
import { NODE_WIDTH, NODE_HEIGHT, PROJECT_CARD_WIDTH, PROJECT_CARD_HEIGHT } from '../constants';
import { getProjectMacroPosition } from './zoomMath';

export const centerOf = (node: ProjektyNode) => ({
  x: node.x + (node.width || NODE_WIDTH) / 2,
  y: node.y + (node.height || NODE_HEIGHT) / 2,
});

/**
 * Oblicza punkt na obwodzie (krawędzi zewnętrznej) notatki lub karty,
 * dzięki czemu groty strzałek (marker-end) nie chowają się w środku karty, lecz stykają się z jej brzegiem.
 */
export const getNodePerimeterPoint = (
  box: { x: number; y: number; width?: number; height?: number },
  targetPoint: { x: number; y: number },
  padding: number = 4,
): { x: number; y: number } => {
  const w = (box.width || NODE_WIDTH) + padding * 2;
  const h = (box.height || NODE_HEIGHT) + padding * 2;
  const cx = box.x + (box.width || NODE_WIDTH) / 2;
  const cy = box.y + (box.height || NODE_HEIGHT) / 2;
  const hw = w / 2;
  const hh = h / 2;

  const dx = targetPoint.x - cx;
  const dy = targetPoint.y - cy;

  if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) {
    return { x: cx, y: cy };
  }

  const sx = Math.abs(dx) > 1e-6 ? hw / Math.abs(dx) : Infinity;
  const sy = Math.abs(dy) > 1e-6 ? hh / Math.abs(dy) : Infinity;
  const s = Math.min(sx, sy);

  return {
    x: cx + dx * s,
    y: cy + dy * s,
  };
};

export const getProjectPerimeterPoint = (
  proj: Projekt,
  idx: number,
  total: number,
  targetPoint: { x: number; y: number },
  padding: number = 6,
): { x: number; y: number } => {
  const pos = getProjectMacroPosition(proj, idx, total);
  return getNodePerimeterPoint(
    { x: pos.x, y: pos.y, width: PROJECT_CARD_WIDTH, height: PROJECT_CARD_HEIGHT },
    targetPoint,
    padding,
  );
};

/**
 * Rekurencyjnie pobiera wszystkie notatki należące do łańcucha / poddrzewa myśli
 * podłączonego do węzła portalu (pełny podgraf osiągalny z portalu).
 */
export const getTransitiveConnectedNodes = (
  portalNodeId: string,
  allNodes: ProjektyNode[],
  allEdges: ProjektyEdge[],
): ProjektyNode[] => {
  const directNeighborIds = allEdges
    .filter((e) => e.source_node_id === portalNodeId || e.target_node_id === portalNodeId)
    .map((e) => (e.source_node_id === portalNodeId ? e.target_node_id : e.source_node_id))
    .filter((id) => id !== portalNodeId);

  const visited = new Set<string>();
  const queue: string[] = [];

  for (const id of directNeighborIds) {
    const node = allNodes.find((n) => n.id === id);
    if (node && node.node_type !== 'portal') {
      visited.add(id);
      queue.push(id);
    }
  }

  while (queue.length > 0) {
    const currentId = queue.shift()!;
    for (const edge of allEdges) {
      if (edge.source_node_id === currentId || edge.target_node_id === currentId) {
        const neighborId = edge.source_node_id === currentId ? edge.target_node_id : edge.source_node_id;
        if (neighborId !== portalNodeId && !visited.has(neighborId)) {
          const neighborNode = allNodes.find((n) => n.id === neighborId);
          if (neighborNode && neighborNode.node_type !== 'portal') {
            visited.add(neighborId);
            queue.push(neighborId);
          }
        }
      }
    }
  }

  return allNodes.filter((n) => visited.has(n.id));
};

// Znajduje wolne, losowe miejsce wokół notatki źródłowej:
// 1. Losowy kąt i losowy odstęp 60–80 px od krawędzi źródła (dokładny obwód Minkowskiego uwzględniający pełną dynamiczną wysokość karty)
// 2. Gwarantowany brak kolizji i minimalny odstęp 80 px (odległość Euklidesowa między prostokątami) od wszystkich innych notatek
export const findSpotNear = (
  source: ProjektyNode,
  allNodes: ProjektyNode[],
  bounds?: { minX: number; minY: number; maxX: number; maxY: number },
  targetSize?: { width?: number; height?: number },
  cardElements?: Record<string, HTMLDivElement | null>,
): { x: number; y: number } => {
  const w = targetSize?.width || NODE_WIDTH;
  const h = targetSize?.height || NODE_HEIGHT;

  const getMeasuredWidth = (n: ProjektyNode): number => {
    const el = cardElements ? cardElements[n.id] : undefined;
    return Math.max(NODE_WIDTH, n.width || 0, el?.offsetWidth || 0);
  };

  const getMeasuredHeight = (n: ProjektyNode): number => {
    const el = cardElements ? cardElements[n.id] : undefined;
    return Math.max(NODE_HEIGHT, n.height || 0, el?.offsetHeight || 0);
  };

  const sw = getMeasuredWidth(source);
  const sh = getMeasuredHeight(source);
  const scx = source.x + sw / 2;
  const scy = source.y + sh / 2;

  // Filtrujemy tylko notatki z tego samego poziomu tablicy (ten sam parent_id)
  const others = allNodes.filter(
    (n) => n.id !== source.id && (n.parent_id ?? null) === (source.parent_id ?? null),
  );

  const GAP_MIN = 120;
  const GAP_MAX = 150;
  const CLEAR = 120; // Wymagany minimalny odstęp od krawędzi innych notatek

  // Ścisła matematyczna weryfikacja odległości Euklidesowej między dwoma prostokątami AABB
  const isClear = (x: number, y: number, minDistance = CLEAR): boolean => {
    for (const o of others) {
      const ow = getMeasuredWidth(o);
      const oh = getMeasuredHeight(o);

      // Odległość 1D wzdłuż osi X i Y (0 jeśli rzuty nachodzą na siebie)
      const dx = Math.max(0, o.x - (x + w), x - (o.x + ow));
      const dy = Math.max(0, o.y - (y + h), y - (o.y + oh));

      // Dystans geometryczny między krawędziami / narożnikami
      const dist = Math.hypot(dx, dy);
      if (dist < minDistance - 0.5) {
        return false; // Zbyt blisko istniejącej notatki (< minDistance px)
      }
    }
    return true;
  };

  // Oblicza pozycję na obwodzie rozszerzonego prostokąta Minkowskiego o zadany gap.
  // Gwarantuje, że dystans geometryczny między krawędziami S i N wynosi dokładnie gap dla dowolnego kąta.
  const posAtAngle = (angle: number, gap: number): { x: number; y: number } => {
    const Ux = (sw + w) / 2;
    const Uy = (sh + h) / 2;

    const cosA = Math.cos(angle);
    const sinA = Math.sin(angle);

    let offsetCx: number;
    let offsetCy: number;

    const cornerAngle = Math.atan2(Uy, Ux);
    const normalizedA = Math.atan2(sinA, cosA); // [-PI, PI]

    // Prawe skrzydło
    if (Math.abs(normalizedA) <= cornerAngle) {
      offsetCx = Ux + gap;
      offsetCy = Ux * Math.tan(normalizedA);
    }
    // Lewe skrzydło
    else if (Math.abs(normalizedA) >= Math.PI - cornerAngle) {
      offsetCx = -(Ux + gap);
      const angleFromLeft = normalizedA >= 0 ? Math.PI - normalizedA : -Math.PI - normalizedA;
      offsetCy = -Ux * Math.tan(angleFromLeft);
    }
    // Dół
    else if (normalizedA > 0) {
      offsetCy = Uy + gap;
      offsetCx = Uy / Math.tan(normalizedA);
    }
    // Góra
    else {
      offsetCy = -(Uy + gap);
      offsetCx = -Uy / Math.tan(normalizedA);
    }

    const cx = scx + offsetCx;
    const cy = scy + offsetCy;

    return {
      x: Math.round(cx - w / 2),
      y: Math.round(cy - h / 2),
    };
  };

  // Krok 1: Próby w pełni losowych kątów i odległości 60-80 px wokół źródła
  for (let attempt = 0; attempt < 120; attempt++) {
    const angle = Math.random() * Math.PI * 2;
    const gap = GAP_MIN + Math.random() * (GAP_MAX - GAP_MIN);
    const candidate = posAtAngle(angle, gap);

    if (isClear(candidate.x, candidate.y, CLEAR)) {
      return candidate;
    }
  }

  // Krok 2: Jeśli obszar bezpośrednio wokół źródła jest gęsto zajęty,
  // przeszukaj promieniście w zwiększających się pierścieniach (z losowym przesunięciem fazy)
  const basePhase = Math.random() * Math.PI * 2;
  for (let ring = 1; ring <= 40; ring++) {
    const extraDist = ring * 30;
    const steps = 16 + ring * 4;
    for (let i = 0; i < steps; i++) {
      const angle = basePhase + (i / steps) * Math.PI * 2 + (Math.random() - 0.5) * 0.1;
      const gap = GAP_MIN + extraDist;
      const candidate = posAtAngle(angle, gap);

      if (isClear(candidate.x, candidate.y, CLEAR)) {
        return candidate;
      }
    }
  }

  // Krok 3: Ostateczny fallback (gdyby 40 pierścieni było zapełnionych setkami notatek)
  let maxOccupiedX = source.x + sw;
  for (const o of others) {
    const ow = getMeasuredWidth(o);
    if (o.x + ow > maxOccupiedX) {
      maxOccupiedX = o.x + ow;
    }
  }
  return { x: maxOccupiedX + CLEAR, y: source.y };
};
