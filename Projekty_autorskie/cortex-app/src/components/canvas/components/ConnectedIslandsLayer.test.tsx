import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ConnectedIslandsLayer } from './ConnectedIslandsLayer';
import { computeClusterLayouts, teleportAndPackBracketClusters } from '../utils/clusterGeometry';
import { calculateBracketGeometries } from '../utils/bracketGeometry';
import type { ProjektyNode, ProjektyEdge, ProjektyBracket } from '../../../types';

afterEach(() => {
  cleanup();
});

describe('CAD ConnectedIslandsLayer & Teleportation Packing (Klaster Klastrow)', () => {
  const sampleNodes: ProjektyNode[] = [
    // Klaster 1
    { id: 'c1-n1', project_id: 'p', title: 'A', content: '', x: 100, y: 100, width: 200, height: 100 },
    { id: 'c1-n2', project_id: 'p', title: 'B', content: '', x: 450, y: 100, width: 250, height: 100 },
    // Klaster 2 (odsunięty daleko w prawo i w dół)
    { id: 'c2-n1', project_id: 'p', title: 'C', content: '', x: 1200, y: 500, width: 200, height: 100 },
    { id: 'c2-n2', project_id: 'p', title: 'D', content: '', x: 1450, y: 500, width: 200, height: 100 },
    // Klaster 3
    { id: 'c3-n1', project_id: 'p', title: 'E', content: '', x: 2000, y: 1000, width: 200, height: 100 },
  ];

  const sampleEdges: ProjektyEdge[] = [
    { id: 'e1', project_id: 'p', source_node_id: 'c1-n1', target_node_id: 'c1-n2', relation_type: 'depends_on' },
    { id: 'e2', project_id: 'p', source_node_id: 'c2-n1', target_node_id: 'c2-n2', relation_type: 'depends_on' },
  ];

  const clusterDescs = {
    'c1-n1': 'Waznosc wpisow - Ai',
    'c2-n1': 'Problem braku wiki pomyslow',
    'c3-n1': 'Oznaczanie pomyslow - obserwacja',
  };

  describe('CAD Teleportation & Auto-Packing (Dosuwanie klastrów do 20px)', () => {
    it('teleports clusters horizontally with exactly 20px gap, flushes top, and bracket length equals sum of widths', () => {
      // Teleportujemy klastry 1 i 2 poziomo
      const pack = teleportAndPackBracketClusters(
        ['c1-n1', 'c1-n2', 'c2-n1', 'c2-n2'],
        sampleNodes,
        sampleEdges,
        clusterDescs,
        'horizontal',
        20,
        28
      );

      expect(pack.orientation).toBe('horizontal');
      expect(pack.clusterCount).toBe(2);

      // Obliczamy layouty wysp po teleportacji
      const layouts = computeClusterLayouts(pack.updatedNodes, sampleEdges, clusterDescs);
      const l1 = layouts.find((l) => l.cluster.some((n) => n.id === 'c1-n1'))!;
      const l2 = layouts.find((l) => l.cluster.some((n) => n.id === 'c2-n1'))!;

      // 1. Górne krawędzie klastrów są idealnie zrównane (flush at top)
      expect(l1.minY).toBe(l2.minY);

      // 2. Odległość między pudełkami (wyspami) wynosi DOKŁADNIE 20px!
      const gapBetweenIslands = l2.minX - l1.maxX;
      expect(gapBetweenIslands).toBe(20);

      // 3. Żadne pudełko nie rozciąga się sztucznie w dół (brak rozciągania na dole)
      expect(l1.height).toBe(l1.intrinsicMaxY - l1.intrinsicMinY);
      expect(l2.height).toBe(l2.intrinsicMaxY - l2.intrinsicMinY);

      // 4. Klamra u góry ma długość równą sumie szerokości obu klastrów + 20px odstępu
      const bracket: ProjektyBracket = {
        id: 'b-horiz',
        project_id: 'p',
        name: 'Klamra Pozioma',
        node_ids: ['c1-n1', 'c1-n2', 'c2-n1', 'c2-n2'],
        orientation: 'horizontal',
      };

      const geos = calculateBracketGeometries([bracket], pack.updatedNodes, layouts);
      expect(geos).toHaveLength(1);
      const geo = geos[0];

      // Szerokość klamry = maxX - minX
      const bracketSpan = geo.maxX - geo.minX;
      const expectedSpan = l1.width + 20 + l2.width;
      expect(bracketSpan).toBe(expectedSpan);
    });

    it('teleports clusters vertically with exactly 20px gap, flushes left, and bracket length equals sum of heights', () => {
      // Teleportujemy klastry 1 i 2 pionowo
      const pack = teleportAndPackBracketClusters(
        ['c1-n1', 'c1-n2', 'c2-n1', 'c2-n2'],
        sampleNodes,
        sampleEdges,
        clusterDescs,
        'vertical',
        20,
        28
      );

      expect(pack.orientation).toBe('vertical');
      expect(pack.clusterCount).toBe(2);

      const layouts = computeClusterLayouts(pack.updatedNodes, sampleEdges, clusterDescs);
      const l1 = layouts.find((l) => l.cluster.some((n) => n.id === 'c1-n1'))!;
      const l2 = layouts.find((l) => l.cluster.some((n) => n.id === 'c2-n1'))!;

      // 1. Lewe krawędzie klastrów są idealnie wyrównane (flush at left)
      expect(l1.minX).toBe(l2.minX);

      // 2. Odległość pionowa między pudełkami wynosi DOKŁADNIE 20px!
      const gapBetweenIslands = l2.minY - l1.maxY;
      expect(gapBetweenIslands).toBe(20);

      // 3. Żadne pudełko nie rozciąga się w bok
      expect(l1.width).toBe(l1.intrinsicMaxX - l1.intrinsicMinX);
      expect(l2.width).toBe(l2.intrinsicMaxX - l2.intrinsicMinX);

      // 4. Klamra pionowa ma długość równą sumie wysokości obu klastrów + 20px odstępu
      const bracket: ProjektyBracket = {
        id: 'b-vert',
        project_id: 'p',
        name: 'Klamra Pionowa',
        node_ids: ['c1-n1', 'c1-n2', 'c2-n1', 'c2-n2'],
        orientation: 'vertical',
      };

      const geos = calculateBracketGeometries([bracket], pack.updatedNodes, layouts);
      expect(geos).toHaveLength(1);
      const geo = geos[0];

      const bracketSpan = geo.maxY - geo.minY;
      const expectedSpan = l1.height + 20 + l2.height;
      expect(bracketSpan).toBe(expectedSpan);
    });
  });

  describe('Component Rendering & Visual Selection', () => {
    it('renders amber highlight when cluster nodes are selected', () => {
      const { container } = render(
        <ConnectedIslandsLayer
          theme="dark"
          isMacroView={false}
          visibleNodes={sampleNodes}
          visibleEdges={sampleEdges}
          scale={0.4}
          clusterDescriptions={clusterDescs}
          selectedNodeIds={['c1-n1', 'c1-n2']}
        />
      );

      const island0 = screen.getByTestId('connected-island-0');
      // Wybrany klaster otrzymuje obramowanie bursztynowe #FFC799
      expect(island0.style.borderColor).toBe('rgb(255, 199, 153)');
      expect(island0.className).toContain('ring-[#FFC799]/40');
    });

    it('triggers context menu callback on right clicking island or banner', () => {
      const onContextMenu = vi.fn();

      render(
        <ConnectedIslandsLayer
          theme="dark"
          isMacroView={false}
          visibleNodes={sampleNodes}
          visibleEdges={sampleEdges}
          scale={0.4}
          clusterDescriptions={clusterDescs}
          onOpenClusterContextMenu={onContextMenu}
        />
      );

      const island1 = screen.getByTestId('connected-island-1');
      fireEvent.contextMenu(island1);

      expect(onContextMenu).toHaveBeenCalledWith(
        expect.arrayContaining([expect.objectContaining({ id: 'c2-n1' })]),
        expect.any(Object)
      );
    });

    it('passes all cluster nodeIds when saving description to prevent name disappearance', () => {
      const onSave = vi.fn();

      render(
        <ConnectedIslandsLayer
          theme="dark"
          isMacroView={false}
          visibleNodes={sampleNodes}
          visibleEdges={sampleEdges}
          scale={1.0}
          clusterDescriptions={{}}
          onSaveClusterDescription={onSave}
        />
      );

      // Kliknij pierwszą etykietę klastra (klaster 0)
      const labelBadge = screen.getAllByText('Klaster (kliknij - edytuj opis)')[0];
      fireEvent.click(labelBadge);

      // Modal powinien być otwarty
      const textarea = screen.getByPlaceholderText('Wpisz esencję tego klastra...') as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: 'Oznaczanie pomysłów - obserwacja' } });

      const saveBtn = screen.getByText('Zapisz');
      fireEvent.click(saveBtn);

      // Weryfikacja: przekazano klucz, opis oraz tablicę WSZYSTKICH węzłów klastra
      expect(onSave).toHaveBeenCalledWith(
        expect.any(String),
        'Oznaczanie pomysłów - obserwacja',
        expect.arrayContaining(['c1-n1', 'c1-n2'])
      );
    });

    it('retains cluster description even if one of the member nodes is deleted', () => {
      // Klaster 1 miał 2 węzły: c1-n1 i c1-n2.
      // Opis został zapisany na obu węzłach.
      const descMap = {
        'c1-n1': 'Oznaczanie pomysłów - obserwacja',
        'c1-n2': 'Oznaczanie pomysłów - obserwacja',
      };

      // Usuwamy węzeł c1-n1 (zostaje c1-n2)
      const remainingNodes = sampleNodes.filter((n) => n.id !== 'c1-n1');
      const remainingEdges: ProjektyEdge[] = []; // brak krawędzi bo c1-n1 usunięty, ale c1-n2 ma opis

      const layouts = computeClusterLayouts(remainingNodes, remainingEdges, descMap);
      const c1Layout = layouts.find((l) => l.cluster.some((n) => n.id === 'c1-n2'));

      expect(c1Layout).toBeDefined();
      expect(c1Layout?.currentDesc).toBe('Oznaczanie pomysłów - obserwacja');
    });
  });
});
