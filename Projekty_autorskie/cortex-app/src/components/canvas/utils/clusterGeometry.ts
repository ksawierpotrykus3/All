import type { ProjektyNode, ProjektyEdge, ProjektyBracket } from '../../../types';
import { NODE_WIDTH, NODE_HEIGHT } from '../constants';

export interface ClusterLayout {
  cluster: ProjektyNode[];
  index: number;
  clusterKey: string;
  currentDesc: string;
  // Wewnetrzne granice samego klastra
  intrinsicMinX: number;
  intrinsicMaxX: number;
  intrinsicMinY: number;
  intrinsicMaxY: number;
  // Rozszerzone granice dopasowane do sciany klamry
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  height: number;
  // Srodek wewnetrzny notatek (dla wysrodkowania etykiety)
  contentCenterX: number;
  contentCenterY: number;
}

/**
 * Wyliczanie składowych spójnych (Connected Components BFS) w czasie < 1ms
 */
export function computeConnectedComponents(
  nodes: ProjektyNode[],
  edges: ProjektyEdge[],
  clusterDescriptions: Record<string, string> = {}
): ProjektyNode[][] {
  if (nodes.length === 0) return [];
  const adj: Record<string, string[]> = {};
  nodes.forEach((n) => {
    adj[n.id] = [];
  });
  edges.forEach((e) => {
    if (adj[e.source_node_id] && adj[e.target_node_id]) {
      adj[e.source_node_id].push(e.target_node_id);
      adj[e.target_node_id].push(e.source_node_id);
    }
  });

  const visited = new Set<string>();
  const result: ProjektyNode[][] = [];

  nodes.forEach((node) => {
    if (!visited.has(node.id)) {
      const cluster: ProjektyNode[] = [];
      const queue = [node.id];
      visited.add(node.id);

      while (queue.length > 0) {
        const currentId = queue.shift()!;
        const currentNode = nodes.find((n) => n.id === currentId);
        if (currentNode) cluster.push(currentNode);

        (adj[currentId] || []).forEach((neighborId) => {
          if (!visited.has(neighborId)) {
            visited.add(neighborId);
            queue.push(neighborId);
          }
        });
      }

      // Rysujemy obwiednię strefy gdy klocki są spięte (>= 2) LUB gdy dowolny węzeł ma zapisany opis klastra
      if (cluster.length >= 2 || (cluster.length === 1 && cluster.some((n) => clusterDescriptions[n.id]?.trim()))) {
        result.push(cluster);
      }
    }
  });

  return result;
}

/**
 * Oblicza geometrię stref klastrów z automatycznym rozszerzaniem mniejszych pudełek
 * do ściany klamry (CAD Wall Extension).
 */
export function computeClusterLayouts(
  nodes: ProjektyNode[],
  edges: ProjektyEdge[],
  clusterDescriptions: Record<string, string> = {},
  brackets: ProjektyBracket[] = [],
  padding = 28
): ClusterLayout[] {
  const clusters = computeConnectedComponents(nodes, edges, clusterDescriptions);
  if (clusters.length === 0) return [];

  // Krok 1: Wewnętrzne granice bazowe każdego klastra
  return clusters.map((cluster, index) => {
    const intrinsicMinX = Math.min(...cluster.map((n) => n.x)) - padding;
    const intrinsicMinY = Math.min(...cluster.map((n) => n.y)) - padding;
    const intrinsicMaxX = Math.max(...cluster.map((n) => n.x + (n.width || NODE_WIDTH))) + padding;
    const intrinsicMaxY = Math.max(...cluster.map((n) => n.y + (n.height || NODE_HEIGHT))) + padding;

    const sortedIds = cluster.map((n) => n.id).sort();
    // Szukamy opisu dla dowolnego węzła w klastrze (odporność na usuwanie pojedynczych węzłów)
    const nodeWithDesc = cluster.find((n) => clusterDescriptions[n.id]?.trim());
    const clusterKey = nodeWithDesc?.id || sortedIds[0];
    const currentDesc = nodeWithDesc ? (clusterDescriptions[nodeWithDesc.id] || '') : '';

    const contentCenterX = intrinsicMinX + (intrinsicMaxX - intrinsicMinX) / 2;
    const contentCenterY = intrinsicMinY + (intrinsicMaxY - intrinsicMinY) / 2;

    return {
      cluster,
      index,
      clusterKey,
      currentDesc,
      intrinsicMinX,
      intrinsicMaxX,
      intrinsicMinY,
      intrinsicMaxY,
      minX: intrinsicMinX,
      maxX: intrinsicMaxX,
      minY: intrinsicMinY,
      maxY: intrinsicMaxY,
      width: intrinsicMaxX - intrinsicMinX,
      height: intrinsicMaxY - intrinsicMinY,
      contentCenterX,
      contentCenterY,
    };
  });
}

export interface TeleportResult {
  updatedNodes: ProjektyNode[];
  movedNodesMap: Map<string, { x: number; y: number }>;
  orientation: 'horizontal' | 'vertical';
  clusterCount: number;
}

/**
 * Teleportuje i układa klastry spięte klamrą tak, aby przylegały do siebie
 * w odległości dokładnie 20px (CAD Cluster Auto-Packing).
 *
 * Poziomo: klastry ułożone obok siebie (lewy -> prawy) z odstępem 20px,
 *          wyrównane do wspólnej górnej krawędzi (minY).
 *          Klamra u góry ma długość równą sumie szerokości klastrów + 20px odstępów.
 *
 * Pionowo: klastry ułożone jeden pod drugim (górny -> dolny) z odstępem 20px,
 *          wyrównane do wspólnej lewej krawędzi (minX).
 *          Klamra po lewej stronie ma długość równą sumie wysokości klastrów + 20px odstępów.
 */
export function teleportAndPackBracketClusters(
  bracketNodeIds: string[],
  allNodes: ProjektyNode[],
  edges: ProjektyEdge[],
  clusterDescriptions: Record<string, string> = {},
  forcedOrientation?: 'horizontal' | 'vertical',
  gap = 20,
  padding = 28,
  side?: 'left' | 'right' | 'top' | 'bottom'
): TeleportResult {
  const matchingNodeIds = new Set(bracketNodeIds);
  const relevantNodes = allNodes.filter((n) => matchingNodeIds.has(n.id));

  if (relevantNodes.length < 2) {
    return {
      updatedNodes: allNodes,
      movedNodesMap: new Map(),
      orientation: forcedOrientation || 'vertical',
      clusterCount: 0,
    };
  }

  // Wyliczamy wszystkie klastry w grafie
  const allClusters = computeConnectedComponents(allNodes, edges, clusterDescriptions);

  // Klastry, które mają przynajmniej jeden węzeł w klamrze
  const memberClusters = allClusters.filter((c) =>
    c.some((n) => matchingNodeIds.has(n.id))
  );

  // Jeśli węzły są w osobnych grupach grafu
  const effectiveClusters = memberClusters.length >= 2
    ? memberClusters
    : computeConnectedComponents(relevantNodes, edges, clusterDescriptions);

  if (effectiveClusters.length < 2) {
    return {
      updatedNodes: allNodes,
      movedNodesMap: new Map(),
      orientation: forcedOrientation || 'vertical',
      clusterCount: effectiveClusters.length,
    };
  }

  // Obwiednie każdego klastra
  interface ClusterBox {
    cluster: ProjektyNode[];
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    width: number;
    height: number;
    centerX: number;
    centerY: number;
  }

  const boxes: ClusterBox[] = effectiveClusters.map((c) => {
    const minX = Math.min(...c.map((n) => n.x));
    const maxX = Math.max(...c.map((n) => n.x + (n.width || NODE_WIDTH)));
    const minY = Math.min(...c.map((n) => n.y));
    const maxY = Math.max(...c.map((n) => n.y + (n.height || NODE_HEIGHT)));
    return {
      cluster: c,
      minX,
      maxX,
      minY,
      maxY,
      width: maxX - minX,
      height: maxY - minY,
      centerX: (minX + maxX) / 2,
      centerY: (minY + maxY) / 2,
    };
  });

  // Ustalenie orientacji (jeśli nie wymuszona):
  // Porównujemy rozstęp środków klastrów w osi X i Y
  let orientation = forcedOrientation;
  if (!orientation) {
    const minCenterX = Math.min(...boxes.map((b) => b.centerX));
    const maxCenterX = Math.max(...boxes.map((b) => b.centerX));
    const minCenterY = Math.min(...boxes.map((b) => b.centerY));
    const maxCenterY = Math.max(...boxes.map((b) => b.centerY));
    const spanX = maxCenterX - minCenterX;
    const spanY = maxCenterY - minCenterY;
    orientation = spanX >= spanY ? 'horizontal' : 'vertical';
  }

  const movedNodesMap = new Map<string, { x: number; y: number }>();

  // Rzeczywisty odstęp między współrzędnymi węzłów, gwarantujący dokładnie 20px między wyspami
  // islandMin(i+1) - islandMax(i) = gap (20px)
  // (min(i+1) - padding) - (max(i) + padding) = gap
  // min(i+1) = max(i) + 2 * padding + gap
  const stepGap = 2 * padding + gap;

  if (orientation === 'horizontal') {
    // Sortujemy klastry od lewej do prawej
    boxes.sort((a, b) => a.centerX - b.centerX);

    // Wyrównanie osi poprzecznej: górna klamra -> do górnej krawędzi,
    // dolna klamra -> do dolnej krawędzi.
    const alignBottom = side === 'bottom';
    const anchorY = alignBottom
      ? Math.max(...boxes.map((b) => b.maxY))
      : Math.min(...boxes.map((b) => b.minY));
    let currentX = boxes[0].minX;

    boxes.forEach((box, i) => {
      const targetMinX = i === 0 ? box.minX : currentX;
      const targetMinY = alignBottom
        ? anchorY - box.height
        : anchorY;

      const dx = targetMinX - box.minX;
      const dy = targetMinY - box.minY;

      box.cluster.forEach((node) => {
        const newX = Math.round(node.x + dx);
        const newY = Math.round(node.y + dy);
        movedNodesMap.set(node.id, { x: newX, y: newY });
      });

      currentX = targetMinX + box.width + stepGap;
    });
  } else {
    // Sortujemy klastry od góry do dołu
    boxes.sort((a, b) => a.centerY - b.centerY);

    // Wyrównanie osi poprzecznej: lewa klamra -> do lewej krawędzi,
    // prawa klamra -> do prawej krawędzi.
    const alignRight = side === 'right';
    const anchorX = alignRight
      ? Math.max(...boxes.map((b) => b.maxX))
      : Math.min(...boxes.map((b) => b.minX));
    let currentY = boxes[0].minY;

    boxes.forEach((box, i) => {
      const targetMinX = alignRight
        ? anchorX - box.width
        : anchorX;
      const targetMinY = i === 0 ? box.minY : currentY;

      const dx = targetMinX - box.minX;
      const dy = targetMinY - box.minY;

      box.cluster.forEach((node) => {
        const newX = Math.round(node.x + dx);
        const newY = Math.round(node.y + dy);
        movedNodesMap.set(node.id, { x: newX, y: newY });
      });

      currentY = targetMinY + box.height + stepGap;
    });
  }

  // Zaktualizowana lista wszystkich węzłów
  const updatedNodes = allNodes.map((node) => {
    const moved = movedNodesMap.get(node.id);
    if (moved) {
      return { ...node, x: moved.x, y: moved.y };
    }
    return node;
  });

  return {
    updatedNodes,
    movedNodesMap,
    orientation,
    clusterCount: boxes.length,
  };
}
