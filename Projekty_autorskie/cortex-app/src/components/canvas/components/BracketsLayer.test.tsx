import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { BracketsLayer } from './BracketsLayer';
import { calculateBracketGeometries } from '../utils/bracketGeometry';
import type { ProjektyBracket, ProjektyNode } from '../../../types';

afterEach(() => {
  cleanup();
});

describe('CAD Semantic Brackets Engine and Layer', () => {
  const sampleNodes: ProjektyNode[] = [
    {
      id: 'node-1',
      project_id: 'proj-1',
      title: 'Waznosc wpisow',
      content: 'Tresc 1',
      x: 200,
      y: 100,
      width: 280,
      height: 160,
    },
    {
      id: 'node-2',
      project_id: 'proj-1',
      title: 'Problem braku wiki',
      content: 'Tresc 2',
      x: 200,
      y: 350,
      width: 280,
      height: 160,
    },
    {
      id: 'node-3',
      project_id: 'proj-1',
      title: 'Wezel boczny',
      content: 'Tresc 3',
      x: 600,
      y: 100,
      width: 280,
      height: 160,
    },
  ];

  describe('Mathematical Geometry & Multi-Track Detection', () => {
    it('determines vertical orientation when nodes are stacked vertically (dy >= dx)', () => {
      const brackets: ProjektyBracket[] = [
        {
          id: 'b-vert',
          project_id: 'proj-1',
          name: 'Oznaczenia Pionowe',
          node_ids: ['node-1', 'node-2'],
        },
      ];

      const geoms = calculateBracketGeometries(brackets, sampleNodes);
      expect(geoms).toHaveLength(1);
      expect(geoms[0].isVertical).toBe(true);
      expect(geoms[0].track).toBe(0);
      expect(geoms[0].nodeCount).toBe(2);
      expect(geoms[0].pathD).toContain('M ');
    });

    it('determines horizontal orientation when nodes are positioned side-by-side (dx > dy)', () => {
      const brackets: ProjektyBracket[] = [
        {
          id: 'b-horiz',
          project_id: 'proj-1',
          name: 'Oznaczenia Poziome',
          node_ids: ['node-1', 'node-3'],
        },
      ];

      const geoms = calculateBracketGeometries(brackets, sampleNodes);
      expect(geoms).toHaveLength(1);
      expect(geoms[0].isVertical).toBe(false);
      expect(geoms[0].track).toBe(0);
      expect(geoms[0].nodeCount).toBe(2);
    });

    it('automatically assigns outer track (track 1) when brackets overlap vertically', () => {
      const overlappingNodes: ProjektyNode[] = [
        { id: 'n1', project_id: 'p', title: '1', content: '', x: 200, y: 100, width: 200, height: 100 },
        { id: 'n2', project_id: 'p', title: '2', content: '', x: 200, y: 250, width: 200, height: 100 },
        { id: 'n3', project_id: 'p', title: '3', content: '', x: 200, y: 400, width: 200, height: 100 },
      ];

      const brackets: ProjektyBracket[] = [
        { id: 'b1', project_id: 'p', name: 'Grupa 1-2', node_ids: ['n1', 'n2'] },
        { id: 'b2', project_id: 'p', name: 'Krzyzowa 2-3', node_ids: ['n2', 'n3'] },
      ];

      const geoms = calculateBracketGeometries(brackets, overlappingNodes);
      expect(geoms).toHaveLength(2);
      expect(geoms[0].track).toBe(0);
      expect(geoms[1].track).toBe(1); // Odsunieta na zewnatrz
    });

    it('self-destructs / excludes bracket with fewer than 2 existing nodes', () => {
      const brackets: ProjektyBracket[] = [
        {
          id: 'b-ghost',
          project_id: 'proj-1',
          name: 'Duch',
          node_ids: ['node-1', 'nieistniejacy-wezel'],
        },
      ];

      const geoms = calculateBracketGeometries(brackets, sampleNodes);
      expect(geoms).toHaveLength(0); // Zero duchow
    });
  });

  describe('BracketsLayer Component Rendering & Interaction', () => {
    it('renders bracket label and triggers rename on click in cluster view', () => {
      const onRename = vi.fn();
      const brackets: ProjektyBracket[] = [
        {
          id: 'b-test',
          project_id: 'proj-1',
          name: 'Testowe Oznaczenia',
          node_ids: ['node-1', 'node-2'],
        },
      ];

      render(
        <BracketsLayer
          isMacroView={false}
          brackets={brackets}
          visibleNodes={sampleNodes}
          scale={0.5}
          onRenameBracket={onRename}
        />
      );

      const label = screen.getByText('Testowe Oznaczenia');
      expect(label).toBeDefined();

      // Klikniecie otwiera modal zmiany nazwy
      fireEvent.click(label);

      const input = screen.getByPlaceholderText('Wpisz opis tej klamry...') as HTMLTextAreaElement;
      expect(input).toBeDefined();
      expect(input.value).toBe('Testowe Oznaczenia');

      fireEvent.change(input, { target: { value: 'Nowe Oznaczenia CAD' } });
      fireEvent.click(screen.getByText('Zapisz'));

      expect(onRename).toHaveBeenCalledWith('b-test', 'Nowe Oznaczenia CAD');
    });

    it('triggers context menu callback on right-clicking bracket label in cluster view', () => {
      const onContextMenu = vi.fn();
      const brackets: ProjektyBracket[] = [
        {
          id: 'b-ctx',
          project_id: 'proj-1',
          name: 'Klamra Menu',
          node_ids: ['node-1', 'node-2'],
        },
      ];

      render(
        <BracketsLayer
          isMacroView={false}
          brackets={brackets}
          visibleNodes={sampleNodes}
          scale={0.5}
          onOpenBracketContextMenu={onContextMenu}
        />
      );

      const label = screen.getByText('Klamra Menu');
      fireEvent.contextMenu(label);

      expect(onContextMenu).toHaveBeenCalledWith('b-ctx', expect.any(Object));
    });

    it('does not render brackets in detailed note view (scale > 0.70)', () => {
      const brackets: ProjektyBracket[] = [
        {
          id: 'b-detail',
          project_id: 'proj-1',
          name: 'Ukryte w widoku notatek',
          node_ids: ['node-1', 'node-2'],
        },
      ];

      render(
        <BracketsLayer
          isMacroView={false}
          brackets={brackets}
          visibleNodes={sampleNodes}
          scale={1.0}
        />
      );

      expect(screen.queryByText('Ukryte w widoku notatek')).toBeNull();
    });

    it('does not render brackets in macro view', () => {
      const brackets: ProjektyBracket[] = [
        {
          id: 'b-macro',
          project_id: 'proj-1',
          name: 'Nie powinno sie renderowac',
          node_ids: ['node-1', 'node-2'],
        },
      ];

      render(
        <BracketsLayer
          isMacroView={true}
          brackets={brackets}
          visibleNodes={sampleNodes}
          scale={0.5}
        />
      );

      expect(screen.queryByText('Nie powinno sie renderowac')).toBeNull();
    });
  });
});
