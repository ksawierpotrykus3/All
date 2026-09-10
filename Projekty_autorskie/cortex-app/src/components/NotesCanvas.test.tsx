import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, act, cleanup, waitFor } from '@testing-library/react';
import { NotesCanvas, findSpotNear, calculateZoomTransform } from './NotesCanvas';
import type { ProjektyNode, ProjektyEdge } from '../types';
import type { cortexBridge } from '../shared/types/ipc';

let mockNodes: ProjektyNode[];
let mockEdges: ProjektyEdge[];
let mockBridge: Partial<cortexBridge>;

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  localStorage.clear();
  mockNodes = [
    {
      id: 'node-1',
      project_id: 'default',
      title: '',
      content: 'Pierwsza notatka',
      x: 100,
      y: 100,
      width: 280,
      height: 140,
    },
    {
      id: 'node-2',
      project_id: 'default',
      title: '',
      content: 'Druga notatka',
      x: 500,
      y: 100,
      width: 280,
      height: 140,
    },
  ];
  mockEdges = [];

  mockBridge = {
    projGetProjects: vi.fn().mockResolvedValue([{ id: 'default', name: 'Notatki' }]),
    projSaveProject: vi.fn().mockResolvedValue({ success: true }),
    projDeleteProject: vi.fn().mockResolvedValue({ success: true }),
    projGetNodes: vi.fn().mockImplementation(() => Promise.resolve([...mockNodes])),
    projGetEdges: vi.fn().mockImplementation(() => Promise.resolve([...mockEdges])),
    projSaveNode: vi.fn().mockResolvedValue({ success: true }),
    projDeleteNode: vi.fn().mockResolvedValue({ success: true }),
    projSaveEdge: vi.fn().mockResolvedValue({ success: true }),
    projDeleteEdge: vi.fn().mockResolvedValue({ success: true }),
  };

  window.cortexBridge = mockBridge as any;
  window.confirm = vi.fn(() => true);
});

describe('NotesCanvas - Selection, Tab Linking, and Edge Management', () => {
  it('renders loaded notes properly', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');
    const card2 = await screen.findByTestId('note-card-node-2');
    expect(card1.textContent).toContain('Pierwsza notatka');
    expect(card2.textContent).toContain('Druga notatka');
  });

  it('selects a note on card click and highlights it', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');
    expect(card1.getAttribute('data-selected')).toBe('false');

    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);

    expect(card1.getAttribute('data-selected')).toBe('true');
  });

  it('starts linking mode with selected note as source when Tab is pressed', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');

    // Select node 1
    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);
    expect(card1.getAttribute('data-selected')).toBe('true');

    // Press Tab
    fireEvent.keyDown(window, { key: 'Tab' });

    expect(card1.getAttribute('data-linking-source')).toBe('true');
    expect(await screen.findByText(/Kliknij notatkę docelową, aby połączyć/i)).toBeDefined();
  });

  it('creates edge when second note is clicked in linking mode and exits linking mode', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');
    const card2 = await screen.findByTestId('note-card-node-2');

    // Select node 1 and press Tab
    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);

    fireEvent.keyDown(window, { key: 'Tab' });

    expect(card1.getAttribute('data-linking-source')).toBe('true');

    // Click node 2 to complete link
    fireEvent.click(card2);

    expect(mockBridge.projSaveEdge).toHaveBeenCalledWith(
      expect.objectContaining({
        edge: expect.objectContaining({
          source_node_id: 'node-1',
          target_node_id: 'node-2',
        }),
      }),
    );

    // Linking mode should now be closed
    expect(card1.getAttribute('data-linking-source')).toBe('false');
    expect(screen.queryByText(/Kliknij notatkę docelową/i)).toBeNull();
    // Target note should now be selected
    expect(card2.getAttribute('data-selected')).toBe('true');
  });

  it('commits text and creates new connected note when Tab is pressed in textarea', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');

    // Double click to edit
    fireEvent.doubleClick(card1);
    const textarea = await screen.findByPlaceholderText(/Zanotuj…/i);
    expect(textarea).toBeDefined();

    // Type text and press Tab
    fireEvent.change(textarea, { target: { value: 'Zaktualizowana notatka' } });

    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Tab' });
    });

    expect(mockBridge.projSaveNode).toHaveBeenCalledWith(
      expect.objectContaining({
        node: expect.objectContaining({
          id: 'node-1',
          content: 'Zaktualizowana notatka',
        }),
      }),
    );

    // Powinno zapisać nową połączoną notatkę
    expect(mockBridge.projSaveNode).toHaveBeenCalledWith(
      expect.objectContaining({
        node: expect.objectContaining({
          node_type: 'note',
        }),
      }),
    );

    // Powinno zapisać krawędź łączącą
    expect(mockBridge.projSaveEdge).toHaveBeenCalledWith(
      expect.objectContaining({
        edge: expect.objectContaining({
          source_node_id: 'node-1',
        }),
      }),
    );
  });

  it('cancels linking mode when Escape is pressed', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');

    // Select node 1 and press Tab
    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);

    fireEvent.keyDown(window, { key: 'Tab' });
    expect(card1.getAttribute('data-linking-source')).toBe('true');

    // Press Escape
    fireEvent.keyDown(window, { key: 'Escape' });

    expect(card1.getAttribute('data-linking-source')).toBe('false');
    expect(screen.queryByText(/Kliknij notatkę docelową/i)).toBeNull();
  });

  it('cancels linking mode when Tab is pressed again', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');

    // Select node 1 and press Tab
    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);

    fireEvent.keyDown(window, { key: 'Tab' });
    expect(card1.getAttribute('data-linking-source')).toBe('true');

    // Press Tab again
    fireEvent.keyDown(window, { key: 'Tab' });

    expect(card1.getAttribute('data-linking-source')).toBe('false');
    expect(screen.queryByText(/Kliknij notatkę docelową/i)).toBeNull();
  });

  it('clears selection when clicking canvas background', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');

    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);
    expect(card1.getAttribute('data-selected')).toBe('true');

    const canvasBg = screen.getByTestId('canvas-container');
    fireEvent.mouseDown(canvasBg, { target: canvasBg, clientX: 10, clientY: 10 });

    expect(card1.getAttribute('data-selected')).toBe('false');
  });

  it('deletes selected note when Delete key is pressed', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');

    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);
    expect(card1.getAttribute('data-selected')).toBe('true');

    fireEvent.keyDown(window, { key: 'Delete' });

    expect(mockBridge.projDeleteNode).toHaveBeenCalledWith({ id: 'node-1' });
    expect(screen.queryByTestId('note-card-node-1')).toBeNull();
  });

  it('does not duplicate edge if already linked', async () => {
    mockEdges = [
      {
        id: 'edge-1',
        project_id: 'default',
        source_node_id: 'node-1',
        target_node_id: 'node-2',
      },
    ];

    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');
    const card2 = await screen.findByTestId('note-card-node-2');

    // Select node 1 and press Tab
    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);
    fireEvent.keyDown(window, { key: 'Tab' });

    // Click node 2 (already connected)
    fireEvent.click(card2);

    expect(mockBridge.projSaveEdge).not.toHaveBeenCalled();
  });

  it('starts editing when Enter key is pressed on a selected note', async () => {
    render(<NotesCanvas />);
    const card1 = await screen.findByTestId('note-card-node-1');

    fireEvent.mouseDown(card1, { clientX: 110, clientY: 110 });
    fireEvent.mouseUp(window);
    expect(card1.getAttribute('data-selected')).toBe('true');

    fireEvent.keyDown(window, { key: 'Enter' });

    const textarea = await screen.findByPlaceholderText(/Zanotuj…/i);
    expect(textarea).toBeDefined();
  });

  it('creates a new note on canvas double-click and enters edit mode', async () => {
    render(<NotesCanvas />);
    const canvas = screen.getByTestId('canvas-container');

    fireEvent.doubleClick(canvas, { clientX: 300, clientY: 300 });

    expect(mockBridge.projSaveNode).toHaveBeenCalled();
    const textarea = await screen.findByPlaceholderText(/Zanotuj…/i);
    expect(textarea).toBeDefined();
  });

  it('initializes in permanent dark Vesper theme and sets dark class on documentElement', async () => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');

    render(<NotesCanvas />);
    await screen.findByTestId('help-toggle');

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem('cortex-theme')).toBe('dark');
  });

  it('opens and closes help modal when ? button is clicked and with Esc key', async () => {
    render(<NotesCanvas />);
    const helpBtn = await screen.findByTestId('help-toggle');

    expect(screen.queryByTestId('help-modal')).toBeNull();

    // Kliknij przycisk pomocy
    fireEvent.click(helpBtn);

    const helpModal = await screen.findByTestId('help-modal');
    expect(helpModal).toBeDefined();
    expect(helpModal.textContent).toContain('Skróty klawiszowe i sterowanie');
    expect(helpModal.textContent).toContain('Tab (w tekście)');
    expect(helpModal.textContent).toContain('Płynny Zoom');

    // Naciśnij Escape, aby zamknąć modal
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('help-modal')).toBeNull();
  });
});

describe('findSpotNear - Random directional placement and strict >= 80px clearance', () => {
  const createTestNode = (id: string, x: number, y: number, width = 240, height = 54): ProjektyNode => ({
    id,
    project_id: 'default',
    title: `Node ${id}`,
    content: '',
    node_type: 'note',
    parent_id: null,
    x,
    y,
    width,
    height,
    created_at: new Date().toISOString(),
  });

  const getEuclideanDist = (a: ProjektyNode, b: { x: number; y: number; width?: number; height?: number }): number => {
    const aw = a.width || 240;
    const ah = a.height || 54;
    const bw = b.width || 240;
    const bh = b.height || 54;
    const dx = Math.max(0, a.x - (b.x + bw), b.x - (a.x + aw));
    const dy = Math.max(0, a.y - (b.y + bh), b.y - (a.y + ah));
    return Math.hypot(dx, dy);
  };

  it('places note around source with distance between 120px and 150px from source edge', () => {
    const parent = createTestNode('n1', 500, 500);
    const nodes = [parent];

    const pos = findSpotNear(parent, nodes);
    const dist = getEuclideanDist(parent, { ...pos, width: 240, height: 54 });

    expect(dist).toBeGreaterThanOrEqual(119.5);
    expect(dist).toBeLessThanOrEqual(150.5);
  });

  it('produces diverse random angles around the source across multiple invocations', () => {
    const parent = createTestNode('n1', 1000, 1000);
    const positions = new Set<string>();

    for (let i = 0; i < 20; i++) {
      const pos = findSpotNear(parent, [parent]);
      positions.add(`${pos.x},${pos.y}`);
    }

    // Upewniamy się, że pozycje są zróżnicowane losowo wokół rodzica (nie w jednej linii)
    expect(positions.size).toBeGreaterThanOrEqual(15);
  });

  it('guarantees >= 120px clearance from all other notes when adding notes sequentially', () => {
    const root = createTestNode('root', 1000, 1000);
    const allNodes: ProjektyNode[] = [root];

    for (let i = 1; i <= 30; i++) {
      const parent = allNodes[Math.floor(Math.random() * allNodes.length)];
      const pos = findSpotNear(parent, allNodes);
      const newNode = createTestNode(`node_${i}`, pos.x, pos.y);

      // Sprawdzamy dystans do wszystkich istniejących notatek
      for (const existing of allNodes) {
        const dist = getEuclideanDist(existing, newNode);
        expect(dist).toBeGreaterThanOrEqual(119.5);
      }

      allNodes.push(newNode);
    }
  });

  it('respects multiline tall parent height (e.g. 180px) and guarantees clearance without overlapping bottom half', () => {
    const tallParent = createTestNode('tall_parent', 500, 500, 240, 180);
    const nodes = [tallParent];

    for (let i = 0; i < 30; i++) {
      const pos = findSpotNear(tallParent, nodes);
      const child = createTestNode(`child_${i}`, pos.x, pos.y, 240, 54);
      const dist = getEuclideanDist(tallParent, child);

      // Dystans geometryczny od krawędzi wysokiej notatki (180px) musi wynosić co najmniej 120px
      expect(dist).toBeGreaterThanOrEqual(119.5);

      // Jeśli notatka wylosowała pozycję w pionowym pasie pod rodzicem, jej top musi być poniżej parent.bottom + 120
      if (child.x < tallParent.x + 240 && child.x + 240 > tallParent.x && child.y > tallParent.y) {
        expect(child.y).toBeGreaterThanOrEqual(tallParent.y + 180 + 119.5);
      }
    }
  });

  it('respects real DOM measured height from cardElements map', () => {
    const parent = createTestNode('dom_parent', 500, 500, 240, 54); // w stanie React height to 54
    const mockCardEl = {
      offsetWidth: 240,
      offsetHeight: 220, // w DOM karta ma 220px z powodu długiego tekstu
    } as unknown as HTMLDivElement;

    const cardElements = {
      dom_parent: mockCardEl,
    };

    for (let i = 0; i < 30; i++) {
      const pos = findSpotNear(parent, [parent], undefined, undefined, cardElements);
      const child = createTestNode(`dom_child_${i}`, pos.x, pos.y, 240, 54);

      // Rzeczywisty obiekt z wymiarami DOM
      const actualParent = { ...parent, height: 220 };
      const dist = getEuclideanDist(actualParent, child);
      expect(dist).toBeGreaterThanOrEqual(119.5);
    }
  });

  it('guarantees zero collisions across 100 nodes in dense random tree with variable card heights', () => {
    const root = createTestNode('root', 0, 0, 240, 54);
    const allNodes: ProjektyNode[] = [root];
    const heights = [54, 120, 180, 80, 240];

    for (let i = 1; i <= 100; i++) {
      const parent = allNodes[Math.floor(Math.random() * allNodes.length)];
      const h = heights[i % heights.length];
      const pos = findSpotNear(parent, allNodes, undefined, { height: h });
      const newNode = createTestNode(`node_${i}`, pos.x, pos.y, 240, h);

      allNodes.push(newNode);
    }

    let collisionCount = 0;
    for (let i = 0; i < allNodes.length; i++) {
      for (let j = i + 1; j < allNodes.length; j++) {
        const a = allNodes[i];
        const b = allNodes[j];
        const dist = getEuclideanDist(a, b);
        if (dist < 119.5) {
          collisionCount++;
        }
      }
    }

    expect(collisionCount).toBe(0);
    expect(allNodes.length).toBe(101);
  });
});

describe('Zoom Transform & Proportional Centering (calculateZoomTransform)', () => {
  it('smoothly glides note under corner cursor towards center strictly proportional to scale increase', () => {
    const currentScale = 1.0;
    const currentOffset = { x: 0, y: 0 };
    const viewportWidth = 1000;
    const viewportHeight = 600;
    const centerX = viewportWidth / 2; // 500
    const centerY = viewportHeight / 2; // 300
    const focalX = 100;
    const focalY = 100;

    const result = calculateZoomTransform({
      currentScale,
      currentOffset,
      focalX,
      focalY,
      factor: 1.25, // Zoom in
      viewportWidth,
      viewportHeight,
      centeringFactor: 0.75,
    });

    expect(result.scale).toBe(1.25);
    const worldX = 100;
    const worldY = 100;
    const screenXAfter = worldX * result.scale + result.offset.x;
    const screenYAfter = worldY * result.scale + result.offset.y;

    // Przyrost względny: (1 - 1/1.25) = 0.20
    // Przesunięcie na ekranie: 100 + (500 - 100) * 0.20 * 0.75 = 100 + 60 = 160
    expect(screenXAfter).toBeCloseTo(160, 3);
    // 100 + (300 - 100) * 0.20 * 0.75 = 100 + 30 = 130
    expect(screenYAfter).toBeCloseTo(130, 3);
  });

  it('keeps world point 100% stationary when centeringFactor is 0', () => {
    const currentScale = 1.0;
    const currentOffset = { x: 100, y: 50 };
    const focalX = 400;
    const focalY = 300;

    const worldX = (focalX - currentOffset.x) / currentScale; // 300
    const worldY = (focalY - currentOffset.y) / currentScale; // 250

    const result = calculateZoomTransform({
      currentScale,
      currentOffset,
      focalX,
      focalY,
      factor: 1.25,
      centeringFactor: 0,
    });

    expect(result.scale).toBe(1.25);
    const screenXAfter = worldX * result.scale + result.offset.x;
    const screenYAfter = worldY * result.scale + result.offset.y;

    expect(screenXAfter).toBeCloseTo(focalX, 5);
    expect(screenYAfter).toBeCloseTo(focalY, 5);
  });

  it('keeps zoom out 100% grounded under cursor with zero sideways recoil', () => {
    const currentScale = 2.0;
    const currentOffset = { x: -400, y: -200 };
    const focalX = 850; // Kursor po prawej stronie
    const focalY = 400;

    const worldX = (focalX - currentOffset.x) / currentScale; // (850 - (-400))/2 = 625
    const worldY = (focalY - currentOffset.y) / currentScale; // (400 - (-200))/2 = 300

    const result = calculateZoomTransform({
      currentScale,
      currentOffset,
      focalX,
      focalY,
      factor: 0.8, // Zoom out
      viewportWidth: 1000,
      viewportHeight: 600,
      centeringFactor: 0.45,
    });

    expect(result.scale).toBeCloseTo(1.6, 5);
    const screenXAfter = worldX * result.scale + result.offset.x;
    const screenYAfter = worldY * result.scale + result.offset.y;

    // Punkt pod kursorem nie został odrzucony w bok — pozostał dokładnie pod kursorem
    expect(screenXAfter).toBeCloseTo(focalX, 5);
    expect(screenYAfter).toBeCloseTo(focalY, 5);
  });

  it('is completely symmetric and reversible when zooming in and out at the same point (centeringFactor: 0)', () => {
    const initialScale = 1.0;
    const initialOffset = { x: 50, y: -30 };
    const focalX = 350;
    const focalY = 220;

    // Zoom in
    const zoomedIn = calculateZoomTransform({
      currentScale: initialScale,
      currentOffset: initialOffset,
      focalX,
      focalY,
      factor: 1.5,
      centeringFactor: 0,
    });

    // Zoom out by the exact inverse factor
    const zoomedBack = calculateZoomTransform({
      currentScale: zoomedIn.scale,
      currentOffset: zoomedIn.offset,
      focalX,
      focalY,
      factor: 1 / 1.5,
      centeringFactor: 0,
    });

    expect(zoomedBack.scale).toBeCloseTo(initialScale, 5);
    expect(zoomedBack.offset.x).toBeCloseTo(initialOffset.x, 5);
    expect(zoomedBack.offset.y).toBeCloseTo(initialOffset.y, 5);
  });

  it('clamps zoom scale within [0.15, 3.0] and does not drift offset when clamped', () => {
    const atMax = calculateZoomTransform({
      currentScale: 3.0,
      currentOffset: { x: 100, y: 100 },
      focalX: 500,
      focalY: 500,
      factor: 1.5,
    });
    expect(atMax.scale).toBe(3.0);
    expect(atMax.offset).toEqual({ x: 100, y: 100 });

    const atMin = calculateZoomTransform({
      currentScale: 0.15,
      currentOffset: { x: 100, y: 100 },
      focalX: 500,
      focalY: 500,
      factor: 0.5,
    });
    expect(atMin.scale).toBe(0.15);
    expect(atMin.offset).toEqual({ x: 100, y: 100 });
  });

  it('zooms viewport center symmetrically when focal point is at screen center', () => {
    const viewWidth = 1000;
    const viewHeight = 600;
    const centerX = viewWidth / 2;
    const centerY = viewHeight / 2;

    const result = calculateZoomTransform({
      currentScale: 1.0,
      currentOffset: { x: 0, y: 0 },
      focalX: centerX,
      focalY: centerY,
      factor: 2.0,
      viewportWidth: viewWidth,
      viewportHeight: viewHeight,
    });

    const worldCenterX = (centerX - 0) / 1.0;
    const worldCenterY = (centerY - 0) / 1.0;
    const screenCenterXAfter = worldCenterX * result.scale + result.offset.x;
    const screenCenterYAfter = worldCenterY * result.scale + result.offset.y;

    expect(screenCenterXAfter).toBeCloseTo(centerX, 5);
    expect(screenCenterYAfter).toBeCloseTo(centerY, 5);
    expect(result.offset.x).toBe(-500);
    expect(result.offset.y).toBe(-300);
  });
});

describe('Canvas Panning (Middle-Click & Right-Click Drag)', () => {
  it('starts panning when middle mouse button (button 1) or right button (button 2) is pressed', async () => {
    render(<NotesCanvas />);
    const canvas = await screen.findByTestId('canvas-container');

    // Middle click down
    fireEvent.mouseDown(canvas, { button: 1, clientX: 200, clientY: 200 });
    // Mouse move
    fireEvent.mouseMove(window, { clientX: 250, clientY: 280 });
    fireEvent.mouseUp(window);

    // Canvas handled pan without crashing
    expect(canvas).toBeDefined();
  });
});

describe('Project Switcher & Multi-Board Management', () => {
  it('opens project switcher dropdown and lists projects', async () => {
    render(<NotesCanvas />);
    await waitFor(() => {
      expect(screen.getByTestId('project-switcher-button').textContent).toContain('Notatki');
    });

    const switcherBtn = screen.getByTestId('project-switcher-button');
    fireEvent.click(switcherBtn);

    await waitFor(() => {
      const dropdown = screen.getByTestId('project-dropdown-menu');
      expect(dropdown.textContent).toContain('Twoje tablice');
      expect(dropdown.textContent).toContain('Notatki');
    });
  });

  it('creates a new project and switches to it', async () => {
    render(<NotesCanvas />);
    await waitFor(() => {
      expect(screen.getByTestId('project-switcher-button').textContent).toContain('Notatki');
    });

    const switcherBtn = screen.getByTestId('project-switcher-button');
    fireEvent.click(switcherBtn);

    const createBtn = await screen.findByTestId('project-create-button');
    await act(async () => {
      fireEvent.click(createBtn);
    });

    expect(window.cortexBridge!.projSaveProject).toHaveBeenCalled();
  });

  it('renames a project and saves it', async () => {
    render(<NotesCanvas />);
    await waitFor(() => {
      expect(screen.getByTestId('project-switcher-button').textContent).toContain('Notatki');
    });

    const switcherBtn = screen.getByTestId('project-switcher-button');
    fireEvent.click(switcherBtn);

    const renameBtn = await screen.findByTestId('project-rename-default');
    await act(async () => {
      fireEvent.click(renameBtn);
    });

    const input = await screen.findByPlaceholderText('Nazwa tablicy...') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Nowa nazwa tablicy' } });
    await act(async () => {
      fireEvent.keyDown(input, { key: 'Enter' });
    });

    expect(window.cortexBridge!.projSaveProject).toHaveBeenCalledWith(
      expect.objectContaining({
        project: expect.objectContaining({
          id: 'default',
          name: 'Nowa nazwa tablicy',
        }),
      }),
    );
  });

  it('does not render delete button when only 1 project exists', async () => {
    render(<NotesCanvas />);
    await waitFor(() => {
      expect(screen.getByTestId('project-switcher-button').textContent).toContain('Notatki');
    });

    const switcherBtn = screen.getByTestId('project-switcher-button');
    fireEvent.click(switcherBtn);

    const deleteBtn = screen.queryByTestId('project-delete-default');
    expect(deleteBtn).toBeNull();
  });

  it('allows deleting a project when multiple projects exist', async () => {
    (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
      { id: 'proj-1', name: 'Projekt Alfa' },
      { id: 'proj-2', name: 'Projekt Beta' },
    ]);

    render(<NotesCanvas />);
    await waitFor(() => {
      expect(screen.getByTestId('project-switcher-button').textContent).toContain('Projekt Alfa');
    });

    const switcherBtn = screen.getByTestId('project-switcher-button');
    fireEvent.click(switcherBtn);

    const deleteBtn = await screen.findByTestId('project-delete-proj-2');
    await act(async () => {
      fireEvent.click(deleteBtn);
    });

    expect(window.cortexBridge!.projDeleteProject).toHaveBeenCalledWith({ id: 'proj-2' });
  });

  it('switches active project when clicking on another project item', async () => {
    (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
      { id: 'proj-1', name: 'Projekt Alfa' },
      { id: 'proj-2', name: 'Projekt Beta' },
    ]);

    render(<NotesCanvas />);
    await waitFor(() => {
      expect(screen.getByTestId('project-switcher-button').textContent).toContain('Projekt Alfa');
    });

    const switcherBtn = screen.getByTestId('project-switcher-button');
    fireEvent.click(switcherBtn);

    const proj2Item = await screen.findByTestId('project-item-proj-2');
    await act(async () => {
      fireEvent.click(proj2Item);
    });

    expect(localStorage.getItem('cortex_active_project_id')).toBe('proj-2');
    expect(window.cortexBridge!.projGetNodes).toHaveBeenCalledWith({ projectId: 'proj-2' });
  });

  describe('Project Portal Super-Node & Note Migration', () => {
    it('places a portal node using placement tool button and clicking on canvas', async () => {
      render(<NotesCanvas />);
      await waitFor(() => {
        expect(screen.getByTestId('footer-place-portal-button')).toBeDefined();
      });

      const placeBtn = screen.getByTestId('footer-place-portal-button');
      await act(async () => {
        fireEvent.click(placeBtn);
      });

      const canvasContainer = screen.getByTestId('canvas-container');
      await act(async () => {
        fireEvent.mouseDown(canvasContainer, { clientX: 300, clientY: 200, button: 0 });
      });

      expect(window.cortexBridge!.projSaveNode).toHaveBeenCalledWith(
        expect.objectContaining({
          node: expect.objectContaining({
            node_type: 'portal',
            width: 320,
            height: 240,
          }),
        }),
      );
    });

    it('renders portal card with connected notes, badge count, and without rocket emoji', async () => {
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'portal-1', project_id: 'default', title: 'Projekt: Generator AI', node_type: 'portal', x: 400, y: 300, width: 320, height: 240 },
        { id: 'note-1', project_id: 'default', content: 'Główny problem z danymi', node_type: 'note', x: 100, y: 100 },
        { id: 'note-2', project_id: 'default', content: 'Rozwiązanie AI', node_type: 'note', x: 200, y: 100 },
      ]);
      (window.cortexBridge!.projGetEdges as any).mockResolvedValue([
        { id: 'e1', project_id: 'default', source_node_id: 'note-1', target_node_id: 'portal-1' },
        { id: 'e2', project_id: 'default', source_node_id: 'note-2', target_node_id: 'portal-1' },
        { id: 'e3', project_id: 'default', source_node_id: 'note-1', target_node_id: 'note-2' },
      ]);

      render(<NotesCanvas />);
      const portalCard = await screen.findByTestId('portal-card-portal-1');
      expect(portalCard).toBeDefined();
      expect(portalCard.textContent).toContain('Projekt: Generator AI');
      expect(portalCard.textContent).not.toContain('🚀');
      expect(portalCard.textContent).toContain('2 połączonych notatek');
      expect(portalCard.textContent).toContain('Główny problem z danymi');
      expect(portalCard.textContent).toContain('Rozwiązanie AI');
    });

    it('creates new project, migrates connected notes and deletes them from source board', async () => {
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'portal-1', project_id: 'default', title: 'Projekt: Generator AI', node_type: 'portal', x: 400, y: 300, width: 320, height: 240 },
        { id: 'note-1', project_id: 'default', content: 'Zadanie 1', node_type: 'note', x: 100, y: 100 },
        { id: 'note-2', project_id: 'default', content: 'Zadanie 2', node_type: 'note', x: 200, y: 100 },
      ]);
      (window.cortexBridge!.projGetEdges as any).mockResolvedValue([
        { id: 'e1', project_id: 'default', source_node_id: 'note-1', target_node_id: 'portal-1' },
        { id: 'e2', project_id: 'default', source_node_id: 'note-2', target_node_id: 'portal-1' },
        { id: 'e3', project_id: 'default', source_node_id: 'note-1', target_node_id: 'note-2' },
      ]);

      render(<NotesCanvas />);
      const openBtn = await screen.findByTestId('open-project-btn-portal-1');
      await act(async () => {
        fireEvent.click(openBtn);
      });

      // Sprawdź zapis nowego projektu
      expect(window.cortexBridge!.projSaveProject).toHaveBeenCalledWith(
        expect.objectContaining({
          project: expect.objectContaining({
            name: 'Generator AI',
          }),
        }),
      );

      // Sprawdź zapis zmigrowanych węzłów i krawędzi
      expect(window.cortexBridge!.projSaveNode).toHaveBeenCalled();
      expect(window.cortexBridge!.projSaveEdge).toHaveBeenCalled();

      // Sprawdź usunięcie połączonych notatek i krawędzi z tablicy źródłowej
      expect(window.cortexBridge!.projDeleteNode).toHaveBeenCalledWith({ id: 'note-1' });
      expect(window.cortexBridge!.projDeleteNode).toHaveBeenCalledWith({ id: 'note-2' });
      expect(window.cortexBridge!.projDeleteEdge).toHaveBeenCalledWith({ id: 'e1' });
      expect(window.cortexBridge!.projDeleteEdge).toHaveBeenCalledWith({ id: 'e2' });
      expect(window.cortexBridge!.projDeleteEdge).toHaveBeenCalledWith({ id: 'e3' });
    });

    it('edits portal super-node title on double-click and saves updated title', async () => {
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'portal-1', project_id: 'default', title: 'Projekt: Generator AI', node_type: 'portal', x: 400, y: 300, width: 320, height: 240 },
      ]);

      render(<NotesCanvas />);
      const portalCard = await screen.findByTestId('portal-card-portal-1');
      const titleSpan = portalCard.querySelector('span[title="Kliknij dwukrotnie, aby zmienić nazwę projektu"]');
      expect(titleSpan).toBeDefined();

      await act(async () => {
        fireEvent.doubleClick(titleSpan!);
      });

      const input = portalCard.querySelector('input[placeholder="Nazwa projektu..."]') as HTMLInputElement;
      expect(input).toBeDefined();
      expect(input.value).toBe('Projekt: Generator AI');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'Nowy Super Projekt' } });
        fireEvent.keyDown(input, { key: 'Enter' });
      });

      expect(window.cortexBridge!.projSaveNode).toHaveBeenCalledWith(
        expect.objectContaining({
          node: expect.objectContaining({
            id: 'portal-1',
            title: 'Nowy Super Projekt',
          }),
        }),
      );
    });

    it('transitively extracts entire deep chain of notes connected through only 1 entry note into portal', async () => {
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'portal-1', project_id: 'default', title: 'Cortex - 2 tablice', node_type: 'portal', x: 800, y: 500, width: 320, height: 240 },
        { id: 'n1', project_id: 'default', content: 'Mam pomysł żeby miec może 2 tablice na start', node_type: 'note', x: 500, y: 500 },
        { id: 'n2', project_id: 'default', content: 'a 2 to może być tablica ktora tworzy Ai', node_type: 'note', x: 400, y: 400 },
        { id: 'n3', project_id: 'default', content: 'Podstawową funkcją i jedyną', node_type: 'note', x: 300, y: 300 },
        { id: 'n4', project_id: 'default', content: 'ubieranie w lepsze słowa', node_type: 'note', x: 200, y: 200 },
        { id: 'n-unrelated', project_id: 'default', content: 'Inny projekt niezwiązany', node_type: 'note', x: 1000, y: 1000 },
      ]);
      (window.cortexBridge!.projGetEdges as any).mockResolvedValue([
        // Tylko n1 jest połączone bezpośrednio z portalem!
        { id: 'e-portal', project_id: 'default', source_node_id: 'n1', target_node_id: 'portal-1' },
        // n1 -> n2 -> n3 -> n4
        { id: 'e1-2', project_id: 'default', source_node_id: 'n1', target_node_id: 'n2' },
        { id: 'e2-3', project_id: 'default', source_node_id: 'n2', target_node_id: 'n3' },
        { id: 'e3-4', project_id: 'default', source_node_id: 'n3', target_node_id: 'n4' },
      ]);

      render(<NotesCanvas />);
      const portalCard = await screen.findByTestId('portal-card-portal-1');
      expect(portalCard).toBeDefined();

      // Portal widzi wszystkie 4 notatki w łańcuchu pomimo podłączenia tylko n1 do portalu!
      expect(portalCard.textContent).toContain('4 połączonych notatek');
      expect(portalCard.textContent).toContain('Mam pomysł żeby miec może 2 tablice na start');
      expect(portalCard.textContent).toContain('a 2 to może być tablica ktora tworzy Ai');
      expect(portalCard.textContent).toContain('Podstawową funkcją i jedyną');
      expect(portalCard.textContent).toContain('ubieranie w lepsze słowa');
      expect(portalCard.textContent).not.toContain('Inny projekt niezwiązany');

      // Otwórz jako nową tablicę
      const openBtn = await screen.findByTestId('open-project-btn-portal-1');
      await act(async () => {
        fireEvent.click(openBtn);
      });

      // Wszystkie 4 notatki i ich wewnętrzne krawędzie zostały zmigrowane
      expect(window.cortexBridge!.projDeleteNode).toHaveBeenCalledWith({ id: 'n1' });
      expect(window.cortexBridge!.projDeleteNode).toHaveBeenCalledWith({ id: 'n2' });
      expect(window.cortexBridge!.projDeleteNode).toHaveBeenCalledWith({ id: 'n3' });
      expect(window.cortexBridge!.projDeleteNode).toHaveBeenCalledWith({ id: 'n4' });
      expect(window.cortexBridge!.projDeleteNode).not.toHaveBeenCalledWith({ id: 'n-unrelated' });
    });
  });

  describe('Infinite Zoom Continuum (Macro Project Galaxy)', () => {
    it('switches to macro view when zooming out below 15%', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-1', name: 'Generator AI' },
        { id: 'proj-2', name: 'Baza Wiedzy' },
      ]);
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'n1', project_id: 'proj-1', content: 'Super prompt', node_type: 'note', x: 0, y: 0 },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Otwórz menu i kliknij 'Widok makro'
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });

      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      // Powinny pojawić się wyspy projektów (Project Islands)
      const island1 = await screen.findByTestId('project-island-proj-1');
      const island2 = await screen.findByTestId('project-island-proj-2');
      expect(island1).toBeDefined();
      expect(island2).toBeDefined();
      expect(island1.textContent).toContain('Generator AI');
      expect(island2.textContent).toContain('Baza Wiedzy');
    });

    it('dives into project and returns to 100% scale when clicking dive button', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-1', name: 'Generator AI' },
        { id: 'proj-2', name: 'Baza Wiedzy' },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do makro
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });
      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      // Kliknij 'Otwórz projekt' na wyspie proj-2
      const diveBtn = await screen.findByTestId('dive-project-btn-proj-2');
      await act(async () => {
        fireEvent.click(diveBtn);
      });

      // Sprawdź czy aktywny projekt zmienił się na proj-2 i przełącznik zaktualizował nazwę
      expect(localStorage.getItem('cortex_active_project_id')).toBe('proj-2');
      expect(screen.getByTestId('project-switcher-button').textContent).toContain('Baza Wiedzy');
    });

    it('connects two projects with an edge in macro view', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-1', name: 'Generator AI' },
        { id: 'proj-2', name: 'Baza Wiedzy' },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do makro
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });
      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      const island1 = await screen.findByTestId('project-island-proj-1');
      const island2 = await screen.findByTestId('project-island-proj-2');

      // Zaznacz pierwszy projekt
      await act(async () => {
        fireEvent.click(island1);
      });
      expect(island1.getAttribute('data-selected')).toBe('true');

      // Naciśnij Tab aby rozpocząć łączenie
      fireEvent.keyDown(window, { key: 'Tab' });

      // Kliknij drugi projekt aby utworzyć połączenie
      await act(async () => {
        fireEvent.click(island2);
      });

      // Sprawdź czy relacja została zapisana w localStorage
      const savedEdges = JSON.parse(localStorage.getItem('cortex_macro_edges') || '[]');
      expect(savedEdges.length).toBe(1);
      expect(savedEdges[0].source_project_id).toBe('proj-1');
      expect(savedEdges[0].target_project_id).toBe('proj-2');
    });

    it('switches to notes at 41% scale when zooming in above 300% on a project', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-1', name: 'Generator AI' },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do makro
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });
      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      const canvasContainer = screen.getByTestId('canvas-container');

      // Zoom in powyżej 300% poprzez serię obrotów kółkiem myszy
      await act(async () => {
        fireEvent.wheel(canvasContainer, { deltaY: -400, clientX: 500, clientY: 500 });
        fireEvent.wheel(canvasContainer, { deltaY: -400, clientX: 500, clientY: 500 });
        fireEvent.wheel(canvasContainer, { deltaY: -400, clientX: 500, clientY: 500 });
        fireEvent.wheel(canvasContainer, { deltaY: -400, clientX: 500, clientY: 500 });
      });

      // Powinno przejść do notatek projektu i skala powinna wynosić 41%
      expect(screen.getByText('41%')).toBeDefined();
    });
  });

  describe('Dynamic Connected Islands & Edge Types', () => {
    it('renders 1 connected island for connected notes, and dynamically splits into 2 islands when bridge edge is deleted', async () => {
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'n1', project_id: 'default', title: 'A1', content: 'Tekst 1', x: 100, y: 100 },
        { id: 'n2', project_id: 'default', title: 'A2', content: 'Tekst 2', x: 300, y: 100 },
        { id: 'n3', project_id: 'default', title: 'B1', content: 'Tekst 3', x: 600, y: 100 },
        { id: 'n4', project_id: 'default', title: 'B2', content: 'Tekst 4', x: 800, y: 100 },
      ]);
      (window.cortexBridge!.projGetEdges as any).mockResolvedValue([
        { id: 'e1', project_id: 'default', source_node_id: 'n1', target_node_id: 'n2', has_arrow: true },
        { id: 'e_bridge', project_id: 'default', source_node_id: 'n2', target_node_id: 'n3', has_arrow: true },
        { id: 'e2', project_id: 'default', source_node_id: 'n3', target_node_id: 'n4', has_arrow: false },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('note-card-n1');

      // Dopóki jest most e_bridge — wszystkie 4 klocki tworzą 1 wspólną wyspę
      expect(screen.queryByTestId('connected-island-0')).not.toBeNull();
      expect(screen.queryByTestId('connected-island-1')).toBeNull();

      // Usunięcie mostu e_bridge
      const deleteBridgeBtn = screen.getByTestId('edge-delete-e_bridge');
      await act(async () => {
        fireEvent.click(deleteBridgeBtn);
      });

      // Po usunięciu mostu graf natychmiast dzieli się na 2 osobne strefy (wyspy)
      expect(screen.getByTestId('connected-island-0')).toBeDefined();
      expect(screen.getByTestId('connected-island-1')).toBeDefined();
    });

    it('toggles edge arrow between arrow and clean line with opposite action icon and persists via projSaveEdge', async () => {
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'n1', project_id: 'default', title: 'A1', content: 'Tekst 1', x: 100, y: 100 },
        { id: 'n2', project_id: 'default', title: 'A2', content: 'Tekst 2', x: 300, y: 100 },
      ]);
      (window.cortexBridge!.projGetEdges as any).mockResolvedValue([
        { id: 'e1', project_id: 'default', source_node_id: 'n1', target_node_id: 'n2', has_arrow: true },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('note-card-n1');

      const toggleBtn = screen.getByTestId('edge-toggle-arrow-e1');
      // Gdy linia ma strzałkę — przycisk pokazuje przeciwną akcję '—'
      expect(toggleBtn.textContent).toContain('—');

      await act(async () => {
        fireEvent.click(toggleBtn);
      });

      // Sprawdź czy zapisano krawędź z has_arrow = false
      expect(window.cortexBridge!.projSaveEdge).toHaveBeenCalledWith(
        expect.objectContaining({
          edge: expect.objectContaining({
            id: 'e1',
            has_arrow: false,
          }),
        }),
      );

      // Po zmianie na linię bez grota — przycisk pokazuje przeciwną akcję '➔'
      expect(screen.getByTestId('edge-toggle-arrow-e1').textContent).toContain('➔');
    });

    it('toggles macro edge arrow in macro view and persists to localStorage', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-1', name: 'Projekt A' },
        { id: 'proj-2', name: 'Projekt B' },
      ]);
      localStorage.setItem('cortex_macro_edges', JSON.stringify([
        { id: 'me-1', source_project_id: 'proj-1', target_project_id: 'proj-2', has_arrow: true }
      ]));

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do widoku makro
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });
      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      const macroToggleBtn = await screen.findByTestId('macro-edge-toggle-arrow-me-1');
      expect(macroToggleBtn.textContent).toContain('—');

      await act(async () => {
        fireEvent.click(macroToggleBtn);
      });

      const saved = JSON.parse(localStorage.getItem('cortex_macro_edges') || '[]');
      expect(saved[0].has_arrow).toBe(false);
      expect(screen.getByTestId('macro-edge-toggle-arrow-me-1').textContent).toContain('➔');
    });

    it('persists project dragged coordinates and does not reset position when another project is deleted', async () => {
      const p1 = { id: 'p1', name: 'Projekt 1', x: 100, y: 100 };
      const p2 = { id: 'p2', name: 'Projekt 2', x: 500, y: 100 };
      const p3 = { id: 'p3', name: 'Projekt 3', x: 900, y: 100 };

      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([p1, p2, p3]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do widoku makro
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });
      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      const cardP1 = await screen.findByTestId('project-island-p1');

      // Przeciągnij projekt p1 o 50px w dół i w prawo (w widoku makro ze scale=0.25 daje to dx = 50/0.25 = 200px -> newX = 100 + 200 = 300)
      fireEvent.mouseDown(cardP1, { clientX: 100, clientY: 100, button: 0 });
      fireEvent.mouseMove(window, { clientX: 150, clientY: 150 });
      fireEvent.mouseUp(window);

      // Sprawdź czy zapisano projekt ze zaktualizowanymi współrzędnymi
      expect(window.cortexBridge!.projSaveProject).toHaveBeenCalledWith(
        expect.objectContaining({
          project: expect.objectContaining({
            id: 'p1',
            x: 150,
            y: 150,
          }),
        }),
      );

      // Teraz usuń projekt p3
      const delBtnP3 = screen.getByTestId('macro-delete-p3');
      window.confirm = () => true;
      await act(async () => {
        fireEvent.click(delBtnP3);
      });

      // Projekt p1 wciąż ma współrzędne 150, 150 (nie został zresetowany do siatki)
      const updatedCardP1 = screen.getByTestId('project-island-p1');
      expect(updatedCardP1.style.left).toBe('150px');
      expect(updatedCardP1.style.top).toBe('150px');
    });

    it('exits macro view and switches to notes when a project is selected from dropdown menu', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-cortex-1', name: 'Cortex - 2 tablice' },
        { id: 'proj-cortex-2', name: 'AI w cortex' },
        { id: 'default', name: 'Ofertownik' },
      ]);
      (window.cortexBridge!.projGetNodes as any).mockImplementation(({ projectId }: { projectId: string }) => {
        if (projectId === 'proj-cortex-1') {
          return Promise.resolve([
            { id: 'n-cortex', project_id: 'proj-cortex-1', content: 'Notatka Cortexowa', node_type: 'note', x: 200, y: 300 },
          ]);
        }
        return Promise.resolve([
          { id: 'n-ofertownik', project_id: 'default', content: 'Oferta', node_type: 'note', x: 100, y: 100 },
        ]);
      });

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do widoku makro
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });
      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      // Upewnij się, że jesteśmy w widoku makro (są wyspy projektów)
      expect(await screen.findByTestId('project-island-proj-cortex-1')).toBeDefined();

      // Otwórz menu projektów i kliknij 'Cortex - 2 tablice'
      await act(async () => {
        fireEvent.click(screen.getByTestId('project-switcher-button'));
      });
      const cortexItem = await screen.findByTestId('project-item-proj-cortex-1');
      await act(async () => {
        fireEvent.click(cortexItem);
      });

      // Powinno WYJŚĆ z widoku makro i pokazać notatki projektu Cortex
      expect(screen.queryByTestId('project-island-proj-cortex-1')).toBeNull();
      const cortexNote = await screen.findByTestId('note-card-n-cortex');
      expect(cortexNote).toBeDefined();
      expect(cortexNote.textContent).toContain('Notatka Cortexowa');
      expect(localStorage.getItem('cortex_active_project_id')).toBe('proj-cortex-1');
    });

    it('exits macro view when clicking the already-active project in dropdown menu', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-cortex-1', name: 'Cortex - 2 tablice' },
        { id: 'default', name: 'Ofertownik' },
      ]);
      localStorage.setItem('cortex_active_project_id', 'proj-cortex-1');
      (window.cortexBridge!.projGetNodes as any).mockResolvedValue([
        { id: 'n-cortex', project_id: 'proj-cortex-1', content: 'Główny plan', node_type: 'note', x: 200, y: 300 },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do makro
      const switcherBtn = screen.getByTestId('project-switcher-button');
      await act(async () => {
        fireEvent.click(switcherBtn);
      });
      const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
      await act(async () => {
        fireEvent.click(macroBtn);
      });

      expect(await screen.findByTestId('project-island-proj-cortex-1')).toBeDefined();

      // Kliknij ponownie w ten sam projekt w menu
      await act(async () => {
        fireEvent.click(screen.getByTestId('project-switcher-button'));
      });
      const activeItem = await screen.findByTestId('project-item-proj-cortex-1');
      await act(async () => {
        fireEvent.click(activeItem);
      });

      // Powinno wejść do wnętrza projektu pomimo że projId === activeProjectId
      expect(screen.queryByTestId('project-island-proj-cortex-1')).toBeNull();
      expect(await screen.findByTestId('note-card-n-cortex')).toBeDefined();
    });

    it('opens the selected project via footer "Otwórz notatki" button', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-1', name: 'Projekt A' },
        { id: 'proj-2', name: 'Projekt B' },
      ]);
      (window.cortexBridge!.projGetNodes as any).mockImplementation(({ projectId }: { projectId: string }) => {
        if (projectId === 'proj-2') {
          return Promise.resolve([
            { id: 'n-proj2', project_id: 'proj-2', content: 'Notatka z B', node_type: 'note', x: 100, y: 100 },
          ]);
        }
        return Promise.resolve([]);
      });

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do makro
      await act(async () => {
        fireEvent.click(screen.getByTestId('project-switcher-button'));
      });
      await act(async () => {
        fireEvent.click(await screen.findByTestId('macro-view-toggle-btn'));
      });

      // Zaznacz projekt B
      const island2 = await screen.findByTestId('project-island-proj-2');
      await act(async () => {
        fireEvent.click(island2);
      });

      // Kliknij w dolny przycisk "Otwórz notatki"
      const openNotesBtn = screen.getByTestId('footer-open-notes-btn');
      await act(async () => {
        fireEvent.click(openNotesBtn);
      });

      // Otworzyło notatki z Projektu B
      expect(await screen.findByTestId('note-card-n-proj2')).toBeDefined();
      expect(localStorage.getItem('cortex_active_project_id')).toBe('proj-2');
    });

    it('opens the selected project when pressing Enter in macro view', async () => {
      (window.cortexBridge!.projGetProjects as any).mockResolvedValue([
        { id: 'proj-1', name: 'Projekt A' },
        { id: 'proj-2', name: 'Projekt B' },
      ]);
      (window.cortexBridge!.projGetNodes as any).mockImplementation(({ projectId }: { projectId: string }) => {
        if (projectId === 'proj-2') {
          return Promise.resolve([
            { id: 'n-proj2', project_id: 'proj-2', content: 'Notatka z Entera', node_type: 'note', x: 100, y: 100 },
          ]);
        }
        return Promise.resolve([]);
      });

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przejdź do makro
      await act(async () => {
        fireEvent.click(screen.getByTestId('project-switcher-button'));
      });
      await act(async () => {
        fireEvent.click(await screen.findByTestId('macro-view-toggle-btn'));
      });

      // Zaznacz projekt B
      const island2 = await screen.findByTestId('project-island-proj-2');
      await act(async () => {
        fireEvent.click(island2);
      });

      // Naciśnij Enter
      await act(async () => {
        fireEvent.keyDown(window, { key: 'Enter' });
      });

      // Otworzyło notatki z Projektu B
      expect(await screen.findByTestId('note-card-n-proj2')).toBeDefined();
      expect(localStorage.getItem('cortex_active_project_id')).toBe('proj-2');
    });
  });

  describe('3-Tier Semantic Zoom and Cluster Descriptions', () => {
    it('renders connected island and allows editing cluster description', async () => {
      mockEdges = [
        {
          id: 'edge-1-2',
          project_id: 'default',
          source_node_id: 'node-1',
          target_node_id: 'node-2',
          relation_type: 'depends_on',
        },
      ];

      render(<NotesCanvas />);
      await screen.findByTestId('note-card-node-1');

      // Sprawdź czy wyspa została narysowana
      const island = await screen.findByTestId('connected-island-0');
      expect(island).toBeDefined();

      // Ponieważ initial auto-center ustawia zoom na 40% (scale <= 0.50 - Poziom 2),
      // na klastrze pojawia się wyśrodkowany placeholder opisu
      const clusterPlaceholder = await screen.findByText('Kliknij, aby dodać opis klastra...');
      expect(clusterPlaceholder).toBeDefined();

      // Kliknięcie w opis otwiera edytor
      await act(async () => {
        fireEvent.click(clusterPlaceholder);
      });

      const textarea = screen.getByPlaceholderText('Wpisz esencję tego klastra...');
      expect(textarea).toBeDefined();

      // Wpisz opis i zapisz
      await act(async () => {
        fireEvent.change(textarea, { target: { value: 'Autoryzacja i tokeny JWT' } });
      });

      const saveBtn = screen.getByText('Zapisz');
      await act(async () => {
        fireEvent.click(saveBtn);
      });

      // Opis klastra wyświetla nową treść
      expect(await screen.findByText('Autoryzacja i tokeny JWT')).toBeDefined();

      // Weryfikacja wywołania zapisu do bridge'a
      expect(mockBridge.projSaveProject).toHaveBeenCalled();
    });

    it('renders cluster descriptions in macro view under project banner', async () => {
      mockBridge.projGetProjects = vi.fn().mockResolvedValue([
        {
          id: 'default',
          name: 'Projekt Alpha',
          cluster_descriptions: {
            'node-1': 'Moduł płatności Stripe',
          },
        },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przełącz do widoku makro
      await act(async () => {
        fireEvent.click(screen.getByTestId('project-switcher-button'));
      });
      await act(async () => {
        fireEvent.click(await screen.findByTestId('macro-view-toggle-btn'));
      });

      // Sprawdź czy opis klastra jest widoczny pod kartą projektu
      expect(await screen.findByText('Moduł płatności Stripe')).toBeDefined();
    });

    it('creates a cluster from Ctrl+G shortcut and links selected notes', async () => {
      render(<NotesCanvas />);
      const card1 = await screen.findByTestId('note-card-node-1');

      // Zaznacz notatkę 1
      await act(async () => {
        fireEvent.mouseDown(card1);
      });

      // Wciśnij skrót Ctrl+G
      await act(async () => {
        fireEvent.keyDown(window, { key: 'g', ctrlKey: true });
      });

      // Zapisano opis klastra
      expect(mockBridge.projSaveProject).toHaveBeenCalled();
    });

    it('allows dragging the entire cluster via island mousedown', async () => {
      mockEdges = [
        {
          id: 'edge-1-2',
          project_id: 'default',
          source_node_id: 'node-1',
          target_node_id: 'node-2',
          relation_type: 'depends_on',
        },
      ];

      render(<NotesCanvas />);
      const island = await screen.findByTestId('connected-island-0');

      // Chwyć ramkę klastra i zacznij przeciągać
      await act(async () => {
        fireEvent.mouseDown(island, { clientX: 100, clientY: 100, button: 0 });
      });

      // Przesuń myszką
      await act(async () => {
        fireEvent.mouseMove(window, { clientX: 180, clientY: 160 });
      });

      // Zwolnij przycisk myszy
      await act(async () => {
        fireEvent.mouseUp(window);
      });

      // Sprawdź czy węzły zostały zaktualizowane
      expect(mockBridge.projSaveNode).toHaveBeenCalled();
    });

    it('allows dragging satellite clusters around project in macro view', async () => {
      mockBridge.projGetProjects = vi.fn().mockResolvedValue([
        {
          id: 'default',
          name: 'Projekt Alpha',
          cluster_descriptions: {
            'node-1': 'Moduł płatności Stripe',
          },
        },
      ]);

      render(<NotesCanvas />);
      await screen.findByTestId('project-switcher-button');

      // Przełącz do widoku makro
      await act(async () => {
        fireEvent.click(screen.getByTestId('project-switcher-button'));
      });
      await act(async () => {
        fireEvent.click(await screen.findByTestId('macro-view-toggle-btn'));
      });

      // Znajdź satelitę klastra
      const satellite = await screen.findByTestId('macro-cluster-satellite-default-node-1');
      expect(satellite).toBeDefined();

      // Przeciągnij satelitę
      await act(async () => {
        fireEvent.mouseDown(satellite, { clientX: 200, clientY: 200, button: 0 });
      });

      await act(async () => {
        fireEvent.mouseMove(window, { clientX: 260, clientY: 300 });
      });

      await act(async () => {
        fireEvent.mouseUp(window);
      });

      // Sprawdź czy zaktualizowano projekt z nowymi pozycjami w bridge
      expect(mockBridge.projSaveProject).toHaveBeenCalled();
    });
  });

  describe('CAD Semantic Brackets & Context Menu Integration', () => {
    it('creates a bracket via context menu when nodes are selected and persists to project', async () => {
      mockNodes = [
        { id: 'b-node-1', project_id: 'default', title: 'Wezel 1', content: 'Tresc', x: 100, y: 100 },
        { id: 'b-node-2', project_id: 'default', title: 'Wezel 2', content: 'Tresc', x: 100, y: 300 },
      ];
      mockEdges = [];

      render(<NotesCanvas />);

      const n1 = await screen.findByTestId('note-card-b-node-1');
      const n2 = await screen.findByTestId('note-card-b-node-2');
      expect(n1).toBeDefined();
      expect(n2).toBeDefined();

      // Zaznacz wszystkie widoczne węzły za pomocą skrótu Ctrl+A
      await act(async () => {
        fireEvent.keyDown(window, { key: 'a', ctrlKey: true });
      });

      const canvasContainer = screen.getByTestId('canvas-container');

      // Otwórz menu kontekstowe prawym przyciskiem myszy
      await act(async () => {
        fireEvent.contextMenu(canvasContainer, { clientX: 250, clientY: 250 });
      });

      // Sprawdź obecność opcji w menu
      const createOption = await screen.findByText('STWORZ KLAMRE SEMANTYCZNA');
      expect(createOption).toBeDefined();

      // Kliknij "STWORZ KLAMRE SEMANTYCZNA"
      await act(async () => {
        fireEvent.click(createOption);
      });

      const confirmBtn = await screen.findByText('Stwórz i dosuń (20px)');
      await act(async () => {
        fireEvent.click(confirmBtn);
      });

      // Sprawdź, czy projekt został zapisany z nową klamrą
      expect(mockBridge.projSaveProject).toHaveBeenCalledWith(
        expect.objectContaining({
          project: expect.objectContaining({
            brackets: expect.arrayContaining([
              expect.objectContaining({
                name: '',
              }),
            ]),
          }),
        })
      );
    });

    it('removes bracket via garbage collection when note is deleted leaving < 2 nodes', async () => {
      (mockBridge.projGetProjects as any).mockResolvedValue([
        {
          id: 'default',
          name: 'Domyślny Projekt',
          brackets: [
            {
              id: 'bracket-to-prune',
              project_id: 'default',
              name: 'Grupa do usuniecia',
              node_ids: ['node-1', 'node-2'],
            },
          ],
        },
      ]);
      mockNodes = [
        { id: 'node-1', project_id: 'default', title: 'Del 1', content: 'Tresc', x: 100, y: 100 },
        { id: 'node-2', project_id: 'default', title: 'Del 2', content: 'Tresc', x: 100, y: 300 },
      ];
      mockEdges = [];

      render(<NotesCanvas />);

      const n1 = await screen.findByTestId('note-card-node-1');
      expect(n1).toBeDefined();

      // Zaznacz notatkę 1
      await act(async () => {
        fireEvent.mouseDown(n1, { clientX: 100, clientY: 100 });
        fireEvent.mouseUp(window);
      });

      // Usuń notatkę klawiszem Delete
      await act(async () => {
        fireEvent.keyDown(window, { key: 'Delete' });
      });

      // Garbage collection usuwa klamre (bo zostal tylko 1 wezel) i zapisuje projekt
      expect(mockBridge.projSaveProject).toHaveBeenCalledWith(
        expect.objectContaining({
          project: expect.objectContaining({
            brackets: [],
          }),
        })
      );
    });

    it('deletes bracket via bracket context menu action', async () => {
      (mockBridge.projGetProjects as any).mockResolvedValue([
        {
          id: 'default',
          name: 'Domyślny Projekt',
          brackets: [
            {
              id: 'bracket-ctx-del',
              project_id: 'default',
              name: 'Klamra do usuniecia',
              node_ids: ['node-1', 'node-2'],
            },
          ],
        },
      ]);
      mockNodes = [
        { id: 'node-1', project_id: 'default', title: '1', content: '', x: 100, y: 100 },
        { id: 'node-2', project_id: 'default', title: '2', content: '', x: 100, y: 300 },
      ];
      mockEdges = [];

      render(<NotesCanvas />);

      const bracketBadge = await screen.findByText('Klamra do usuniecia');
      expect(bracketBadge).toBeDefined();

      // Prawy klik na badge klamry otwiera dedykowane menu klamry
      await act(async () => {
        fireEvent.contextMenu(bracketBadge, { clientX: 200, clientY: 200 });
      });

      const delOption = await screen.findByText('USUN KLAMRE');
      expect(delOption).toBeDefined();

      await act(async () => {
        fireEvent.click(delOption);
      });

      expect(mockBridge.projSaveProject).toHaveBeenCalledWith(
        expect.objectContaining({
          project: expect.objectContaining({
            brackets: [],
          }),
        })
      );
    });

    it('supports Shift+click multi-cluster selection and creates cluster bracket via island context menu', async () => {
      // Dwa odrębne klastry
      mockNodes = [
        // Klaster A
        { id: 'node-a1', project_id: 'default', title: 'A1', content: '', x: 100, y: 100 },
        { id: 'node-a2', project_id: 'default', title: 'A2', content: '', x: 300, y: 100 },
        // Klaster B
        { id: 'node-b1', project_id: 'default', title: 'B1', content: '', x: 100, y: 400 },
        { id: 'node-b2', project_id: 'default', title: 'B2', content: '', x: 300, y: 400 },
      ];
      mockEdges = [
        { id: 'e-a', project_id: 'default', source_node_id: 'node-a1', target_node_id: 'node-a2', relation_type: 'depends_on' },
        { id: 'e-b', project_id: 'default', source_node_id: 'node-b1', target_node_id: 'node-b2', relation_type: 'depends_on' },
      ];

      render(<NotesCanvas />);

      const islandA = await screen.findByTestId('connected-island-0');
      const islandB = await screen.findByTestId('connected-island-1');

      // Zaznacz klaster A zwykłym kliknięciem
      await act(async () => {
        fireEvent.mouseDown(islandA, { button: 0, clientX: 150, clientY: 150, shiftKey: false });
      });

      // Zaznacz klaster B z wciśniętym Shift (Multi-selection klastrów)
      await act(async () => {
        fireEvent.mouseDown(islandB, { button: 0, clientX: 150, clientY: 450, shiftKey: true });
      });

      // Prawy klik na wyspie klastra B otwiera menu kontekstowe z łączną liczbą zaznaczonych węzłów obu klastrów
      await act(async () => {
        fireEvent.contextMenu(islandB, { clientX: 150, clientY: 450 });
      });

      const createAction = await screen.findByText('STWORZ KLAMRE SEMANTYCZNA');
      expect(createAction).toBeDefined();

      // Kliknij akcję stworzenia klamry dla klastrów
      await act(async () => {
        fireEvent.click(createAction);
      });

      // Pojawia się modal wpisania nazwy klamry
      const confirmBtn = await screen.findByText('Stwórz i dosuń (20px)');
      expect(confirmBtn).toBeDefined();

      await act(async () => {
        fireEvent.click(confirmBtn);
      });

      // Weryfikacja: bridge zapisuje nową klamrę spinającą węzły obu klastrów
      expect(mockBridge.projSaveProject).toHaveBeenCalledWith(
        expect.objectContaining({
          project: expect.objectContaining({
            brackets: expect.arrayContaining([
              expect.objectContaining({
                name: '',
                node_ids: expect.arrayContaining(['node-a1', 'node-a2', 'node-b1', 'node-b2']),
              }),
            ]),
          }),
        })
      );
    });

    it('saves cluster description to bridge with proper { project } payload and distributes to member nodes', async () => {
      mockNodes = [
        { id: 'c-n1', project_id: 'default', title: 'C1', content: '', x: 100, y: 100 },
        { id: 'c-n2', project_id: 'default', title: 'C2', content: '', x: 300, y: 100 },
      ];
      mockEdges = [
        { id: 'c-e1', project_id: 'default', source_node_id: 'c-n1', target_node_id: 'c-n2', relation_type: 'depends_on' },
      ];

      render(<NotesCanvas />);

      // W widoku domyślnym odszukaj kafelek klastra
      const clusterPill = await screen.findByText('Kliknij, aby dodać opis klastra...');
      expect(clusterPill).toBeDefined();

      await act(async () => {
        fireEvent.click(clusterPill);
      });

      const textarea = await screen.findByPlaceholderText('Wpisz esencję tego klastra...');
      fireEvent.change(textarea, { target: { value: 'Oznaczanie pomysłów - obserwacja' } });

      const saveBtn = await screen.findByText('Zapisz');
      await act(async () => {
        fireEvent.click(saveBtn);
      });

      // Weryfikacja: wywołano projSaveProject z { project: ... } i opisem dla obu węzłów
      expect(mockBridge.projSaveProject).toHaveBeenCalledWith({
        project: expect.objectContaining({
          cluster_descriptions: expect.objectContaining({
            'c-n1': 'Oznaczanie pomysłów - obserwacja',
            'c-n2': 'Oznaczanie pomysłów - obserwacja',
          }),
        }),
      });
    });

    it('teleports clusters to 20px gap and saves moved nodes upon creating a bracket', async () => {
      // Dwa odległe klastry w układzie poziomym
      mockNodes = [
        // Klaster 1: x: 100..400
        { id: 'tp-a1', project_id: 'default', title: 'A1', content: '', x: 100, y: 100, width: 140, height: 92 },
        { id: 'tp-a2', project_id: 'default', title: 'A2', content: '', x: 260, y: 100, width: 140, height: 92 },
        // Klaster 2: x: 1200..1500 (oddalony o 800px)
        { id: 'tp-b1', project_id: 'default', title: 'B1', content: '', x: 1200, y: 400, width: 140, height: 92 },
        { id: 'tp-b2', project_id: 'default', title: 'B2', content: '', x: 1360, y: 400, width: 140, height: 92 },
      ];
      mockEdges = [
        { id: 'tp-e1', project_id: 'default', source_node_id: 'tp-a1', target_node_id: 'tp-a2', relation_type: 'depends_on' },
        { id: 'tp-e2', project_id: 'default', source_node_id: 'tp-b1', target_node_id: 'tp-b2', relation_type: 'depends_on' },
      ];

      render(<NotesCanvas />);

      // Zaznaczamy oba klastry przez Shift+klik
      const islandA = await screen.findByTestId('connected-island-0');
      const islandB = await screen.findByTestId('connected-island-1');

      await act(async () => {
        fireEvent.mouseDown(islandA, { button: 0, clientX: 100, clientY: 100 });
        fireEvent.mouseDown(islandB, { button: 0, shiftKey: true, clientX: 1200, clientY: 400 });
      });

      // Otwieramy menu kontekstowe
      await act(async () => {
        fireEvent.contextMenu(islandB, { clientX: 1200, clientY: 400 });
      });

      const createAction = await screen.findByText('STWORZ KLAMRE SEMANTYCZNA');
      await act(async () => {
        fireEvent.click(createAction);
      });

      const confirmBtn = await screen.findByText('Stwórz i dosuń (20px)');
      await act(async () => {
        fireEvent.click(confirmBtn);
      });

      // Weryfikacja: węzły klastra B zostały teleportowane tuż za klaster A z odstępem 20px
      // Klaster A kończy się na x = 400, z paddingiem 28 -> islandMaxX = 428
      // Klaster B powinien zaczynać się na islandMinX = 448 (428 + 20) -> b1.x = 448 + 28 = 476
      expect(mockBridge.projSaveNode).toHaveBeenCalledWith(
        expect.objectContaining({
          node: expect.objectContaining({
            id: 'tp-b1',
            x: 476,
            y: 100, // zrównane do góry klastra A!
          }),
        })
      );
    });
  });
});
