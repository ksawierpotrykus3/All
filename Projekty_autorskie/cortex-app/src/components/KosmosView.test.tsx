// ============================================================================
// KOSMOS — testy widoku grafu siłowego (force-graph) + czystej logiki grafu.
// Force-graph jest mockowany (jsdom nie ma canvas), natomiast buildVisibleGraph
// testujemy jako czystą funkcję.
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup, act } from '@testing-library/react';
import { KosmosView } from './KosmosView';
import { buildVisibleGraph, dirNodeId, fileNodeId, calcChildFolderDistance } from './kosmosGraph';
import type { KosmosGraphData, KosmosProjectSummary } from '../shared/types/kosmos';

// === Mock force-graph ========================================================
const mocks = vi.hoisted(() => {
  const clickHandler = { fn: null as ((node: { kind: string; path: string }) => void) | null };
  const hoverHandler = { fn: null as ((node: unknown) => void) | null };
  const dragEndHandler = { fn: null as ((node: any) => void) | null };
  const engineStopHandler = { fn: null as (() => void) | null };

  const mockFg: Record<string, any> = {};
  const chainable = () => mockFg;

  let storedData = { nodes: [] as any[], links: [] as any[] };
  mockFg.graphData = vi.fn((data?: any) => {
    if (data !== undefined) {
      storedData = data;
      return mockFg;
    }
    return storedData;
  });
  mockFg.backgroundColor = vi.fn(chainable);
  mockFg.width = vi.fn(chainable);
  mockFg.height = vi.fn(chainable);
  mockFg.nodeId = vi.fn(chainable);
  mockFg.nodeRelSize = vi.fn(chainable);
  mockFg.nodeVal = vi.fn(chainable);
  mockFg.nodeColor = vi.fn(chainable);
  mockFg.linkColor = vi.fn(chainable);
  mockFg.linkWidth = vi.fn(chainable);
  mockFg.linkDirectionalParticles = vi.fn(chainable);
  mockFg.warmupTicks = vi.fn(chainable);
  mockFg.cooldownTicks = vi.fn(chainable);
  mockFg.d3AlphaDecay = vi.fn(chainable);
  mockFg.d3VelocityDecay = vi.fn(chainable);
  mockFg.d3Force = vi.fn(() => ({
    strength: vi.fn().mockReturnThis(),
    distanceMin: vi.fn().mockReturnThis(),
    distanceMax: vi.fn().mockReturnThis(),
    distance: vi.fn().mockReturnThis(),
  }));
  mockFg.d3ReheatSimulation = vi.fn(chainable);
  mockFg.nodeLabel = vi.fn(chainable);
  mockFg.centerAt = vi.fn((x?: number, y?: number) => {
    if (x !== undefined || y !== undefined) return mockFg;
    return { x: 0, y: 0 };
  });
  mockFg.zoom = vi.fn((k?: number) => {
    if (k !== undefined) return mockFg;
    return 1.0;
  });
  mockFg.onZoom = vi.fn(chainable);
  mockFg.onZoomEnd = vi.fn(chainable);
  mockFg.onNodeClick = vi.fn((fn: (node: { kind: string; path: string }) => void) => {
    clickHandler.fn = fn;
    return mockFg;
  });
  mockFg.onNodeHover = vi.fn((fn: (node: unknown) => void) => {
    hoverHandler.fn = fn;
    return mockFg;
  });
  mockFg.onNodeDragEnd = vi.fn((fn: (node: any) => void) => {
    dragEndHandler.fn = fn;
    return mockFg;
  });
  mockFg.onEngineStop = vi.fn((fn: () => void) => {
    engineStopHandler.fn = fn;
    return mockFg;
  });
  mockFg._destructor = vi.fn();

  return { mockFg, clickHandler, hoverHandler, dragEndHandler, engineStopHandler };
});

vi.mock('force-graph', () => ({
  default: vi.fn(() => () => mocks.mockFg),
}));

// === Dane testowe ============================================================
const mockGraphData: KosmosGraphData = {
  folders: [
    {
      project_id: 'cortex_app',
      project_name: 'cortex-app',
      root_path: 'c:/root',
      path: 'c:/root',
      relative_path: '',
      name: 'cortex-app',
      parent_path: 'c:/',
      file_count: 1,
      depth: 0,
    },
    {
      project_id: 'cortex_app',
      project_name: 'cortex-app',
      root_path: 'c:/root',
      path: 'c:/root/src',
      relative_path: 'src',
      name: 'src',
      parent_path: 'c:/root',
      file_count: 1,
      depth: 1,
    },
  ],
  files: [
    {
      project_id: 'cortex_app',
      project_name: 'cortex-app',
      id: 'package.json',
      name: 'package.json',
      path: 'c:/root/package.json',
      relative_path: 'package.json',
      folder_path: 'c:/root',
      extension: '.json',
      type: 'json',
      size_bytes: 1024,
      preview: '{}',
      updated_at: null,
    },
    {
      project_id: 'cortex_app',
      project_name: 'cortex-app',
      id: 'src/App.tsx',
      name: 'App.tsx',
      path: 'c:/root/src/App.tsx',
      relative_path: 'src/App.tsx',
      folder_path: 'c:/root/src',
      extension: '.tsx',
      type: 'kod',
      size_bytes: 2048,
      preview: 'export function App() {}',
      updated_at: null,
    },
  ],
};

const mockProjects: KosmosProjectSummary[] = [
  { id: 'cortex_app', name: 'cortex-app', rootPath: 'c:/root' },
];

// === Testy czystej logiki grafu ==============================================
describe('kosmosGraph — buildVisibleGraph', () => {
  it('buduje pełny graf hierarchii z krawędziami contains', () => {
    const graph = buildVisibleGraph(mockGraphData, new Set());

    // 5 węzłów: root, src, wirtualny folder plików projektu, package.json, App.tsx
    expect(graph.nodes).toHaveLength(5);
    expect(graph.links).toHaveLength(4);

    const root = graph.nodes.find((n) => n.id === dirNodeId('c:/root'));
    const src = graph.nodes.find((n) => n.id === dirNodeId('c:/root/src'));
    const rootFiles = graph.nodes.find((n) => n.id === dirNodeId('c:/root::[pliki]'));
    const pkg = graph.nodes.find((n) => n.id === fileNodeId('c:/root/package.json'));
    const app = graph.nodes.find((n) => n.id === fileNodeId('c:/root/src/App.tsx'));

    expect(root).toBeTruthy();
    expect(root!.kind).toBe('folder');
    expect(root!.label).toBe('cortex-app');
    expect(root!.fileCount).toBe(1);

    expect(src).toBeTruthy();
    expect(src!.kind).toBe('folder');
    expect(src!.label).toBe('src');

    expect(rootFiles).toBeTruthy();
    expect(rootFiles!.kind).toBe('folder');
    expect(rootFiles!.label).toContain('Pliki projektu');
    expect(rootFiles!.fileCount).toBe(1);

    expect(pkg).toBeTruthy();
    expect(pkg!.kind).toBe('file');
    expect(pkg!.type).toBe('json');

    expect(app).toBeTruthy();
    expect(app!.kind).toBe('file');
    expect(app!.type).toBe('kod');
  });

  it('zwija folder — ukrywa jego potomków, zachowując sam węzeł', () => {
    const graph = buildVisibleGraph(mockGraphData, new Set(['c:/root/src']));

    // root + src (zwinięty) + rootFiles + package.json — App.tsx ukryty.
    expect(graph.nodes).toHaveLength(4);
    expect(graph.links).toHaveLength(3);

    const app = graph.nodes.find((n) => n.id === fileNodeId('c:/root/src/App.tsx'));
    expect(app).toBeUndefined();

    const src = graph.nodes.find((n) => n.id === dirNodeId('c:/root/src'));
    expect(src).toBeTruthy();

    // Zwinięcie wirtualnego folderu plików projektu ukrywa package.json
    const graphCollapsedFiles = buildVisibleGraph(
      mockGraphData,
      new Set(['c:/root::[pliki]']),
    );
    expect(
      graphCollapsedFiles.nodes.find((n) => n.id === fileNodeId('c:/root/package.json')),
    ).toBeUndefined();
    expect(
      graphCollapsedFiles.nodes.find((n) => n.id === dirNodeId('c:/root::[pliki]')),
    ).toBeTruthy();
  });

  it('przypisuje topBranch oraz deterministyczne współrzędne początkowe bez nakładania się', () => {
    const graph = buildVisibleGraph(mockGraphData, new Set());
    const root = graph.nodes.find((n) => n.id === dirNodeId('c:/root'));
    const src = graph.nodes.find((n) => n.id === dirNodeId('c:/root/src'));
    const app = graph.nodes.find((n) => n.id === fileNodeId('c:/root/src/App.tsx'));
    const pkg = graph.nodes.find((n) => n.id === fileNodeId('c:/root/package.json'));

    expect(root?.topBranch).toBe('__root__');
    expect(src?.topBranch).toBe('c:/root/src');
    expect(app?.topBranch).toBe('c:/root/src');
    expect(pkg?.topBranch).toBe('c:/root::[pliki]');

    // Współrzędne są zdefiniowanymi liczbami i nie ma węzłów w tym samym punkcie
    for (const node of graph.nodes) {
      expect(typeof node.x).toBe('number');
      expect(typeof node.y).toBe('number');
      expect(Number.isNaN(node.x)).toBe(false);
      expect(Number.isNaN(node.y)).toBe(false);
    }

    // Sprawdź, czy węzły nie mają identycznych pozycji
    const posSet = new Set(graph.nodes.map((n) => `${n.x?.toFixed(1)},${n.y?.toFixed(1)}`));
    expect(posSet.size).toBe(graph.nodes.length);
  });

  it('calcChildFolderDistance — dynamicznie wydłuża promienie przy dużej liczbie dzieci/plików', () => {
    // 1 dziecko: minimalny dystans bazowy 45px
    expect(calcChildFolderDistance(1, 0)).toBe(45);
    // 4 dzieci: większy promień
    expect(calcChildFolderDistance(4, 0)).toBe(54);
    // 16 dzieci (jak w dużych folderach): wydłuża się do ~120px
    expect(calcChildFolderDistance(16, 0)).toBe(120);
    // Bardzo duża liczba: ograniczona górnym progiem 160px
    expect(calcChildFolderDistance(40, 100)).toBe(160);
  });
});

// === Testy komponentu ========================================================
describe('KosmosView — graf siłowy zasilany bazą SQLite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mocks.clickHandler.fn = null;
    mocks.hoverHandler.fn = null;
    mocks.dragEndHandler.fn = null;
    mocks.engineStopHandler.fn = null;

    window.cortexBridge = {
      kosmosListProjects: vi.fn().mockResolvedValue(JSON.parse(JSON.stringify(mockProjects))),
      kosmosGetGraph: vi.fn().mockResolvedValue(JSON.parse(JSON.stringify(mockGraphData))),
      kosmosReadFile: vi.fn().mockResolvedValue({ success: true, content: '# Nagłówek' }),
      kosmosPickFolder: vi.fn().mockResolvedValue('c:/nowy-projekt'),
      kosmosImportProject: vi.fn().mockResolvedValue({ success: true, projectId: 'nowy' }),
      kosmosSavePositions: vi.fn().mockResolvedValue({ success: true }),
      kosmosGetPositions: vi.fn().mockResolvedValue({}),
    } as any;
  });

  afterEach(() => {
    cleanup();
  });

  it('ładuje listę projektów z SQLite i renderuje pasek narzędzi', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      expect(window.cortexBridge!.kosmosListProjects).toHaveBeenCalled();
      expect(screen.getByText('Kosmos')).toBeTruthy();
      expect(screen.getByText('Graf struktury')).toBeTruthy();
    });

    // Nazwa projektu w przełączniku
    expect(screen.getByText('cortex-app')).toBeTruthy();
  });

  it('pobiera graf dla wybranego projektu i przekazuje go do silnika', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      expect(window.cortexBridge!.kosmosGetGraph).toHaveBeenCalledWith({
        projectId: 'cortex_app',
      });
    });

    await waitFor(() => {
      expect(mocks.mockFg.graphData).toHaveBeenCalled();
    });

    const lastCall = mocks.mockFg.graphData.mock.calls.at(-1);
    expect(lastCall).toBeTruthy();
    expect(lastCall![0].nodes.length).toBeGreaterThan(0);
    expect(lastCall![0].links.length).toBeGreaterThan(0);
  });

  it('przełącza tryb etykiet po kliknięciu przycisku HUD', async () => {
    render(<KosmosView onBack={() => {}} />);

    const labelButton = await screen.findByText(/Etykiety:/i);
    expect(labelButton.textContent).toContain('wszystkie');

    fireEvent.click(labelButton);
    expect(labelButton.textContent).toContain('foldery');

    fireEvent.click(labelButton);
    expect(labelButton.textContent).toContain('ukryte');

    fireEvent.click(labelButton);
    expect(labelButton.textContent).toContain('wszystkie');
  });

  it('kliknięcie folderu wywołuje zwinięcie i ponowny render grafu', async () => {
    render(<KosmosView onBack={() => {}} />);

    // Poczekaj, aż graf zostanie w pełni załadowany.
    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0].nodes.length).toBeGreaterThan(0);
    });

    await waitFor(() => {
      expect(mocks.clickHandler.fn).not.toBeNull();
    });

    const callsBefore = mocks.mockFg.graphData.mock.calls.length;

    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src' });
    });

    await waitFor(() => {
      expect(mocks.mockFg.graphData.mock.calls.length).toBeGreaterThan(callsBefore);
    });

    // Po zwinięciu src, App.tsx znika z grafu
    const lastCall = mocks.mockFg.graphData.mock.calls.at(-1)!;
    const nodeIds = lastCall[0].nodes.map((n: { id: string }) => n.id);
    expect(nodeIds).not.toContain(fileNodeId('c:/root/src/App.tsx'));
    expect(nodeIds).toContain(dirNodeId('c:/root/src'));
  });

  it('dodanie folderu z dysku importuje projekt do SQLite', async () => {
    render(<KosmosView onBack={() => {}} />);

    const addButton = await screen.findByText('Dodaj folder');
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(window.cortexBridge!.kosmosPickFolder).toHaveBeenCalled();
      expect(window.cortexBridge!.kosmosImportProject).toHaveBeenCalledWith({
        folderPath: 'c:/nowy-projekt',
      });
    });
  });

  it('wyświetla komunikat błędu, gdy ładowanie listy projektów zawodzi', async () => {
    (window.cortexBridge!.kosmosListProjects as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('database disk failure'),
    );

    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Błąd ładowania projektów/i)).toBeTruthy();
    });
  });

  it('wyświetla komunikat błędu, gdy odczyt grafu zawodzi', async () => {
    // Załaduj listę projektów poprawnie, ale odrzuć zapytanie o graf.
    (window.cortexBridge!.kosmosGetGraph as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('graph read failure'),
    );

    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Błąd odczytu grafu/i)).toBeTruthy();
    });
  });

  it('nie wywołuje importu, gdy wybór folderu zostaje anulowany', async () => {
    (window.cortexBridge!.kosmosPickFolder as ReturnType<typeof vi.fn>).mockResolvedValue(null);

    render(<KosmosView onBack={() => {}} />);

    const addButton = await screen.findByText('Dodaj folder');
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(window.cortexBridge!.kosmosPickFolder).toHaveBeenCalled();
    });
    expect(window.cortexBridge!.kosmosImportProject).not.toHaveBeenCalled();
  });

  it('przełącza stan fizyki (aktywna / wstrzymana) po kliknięciu przycisku HUD', async () => {
    render(<KosmosView onBack={() => {}} />);

    const physicsBtn = await screen.findByText(/Fizyka:/i);
    expect(physicsBtn.textContent).toContain('aktywna');

    // Kliknij, by wstrzymać fizykę
    fireEvent.click(physicsBtn);
    expect(physicsBtn.textContent).toContain('wstrzymana');
    expect(mocks.mockFg.cooldownTicks).toHaveBeenCalledWith(0);

    // Kliknij, by wznowić fizykę
    fireEvent.click(physicsBtn);
    expect(physicsBtn.textContent).toContain('aktywna');
    expect(mocks.mockFg.d3ReheatSimulation).toHaveBeenCalled();
  });

  it('zachowuje pozycje istniejących węzłów przy zwiń/rozwiń bez resetowania współrzędnych', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
    });

    const initialNodes = mocks.mockFg.graphData().nodes;
    const rootNode = initialNodes.find((n: any) => n.id === dirNodeId('c:/root'));
    expect(rootNode).toBeTruthy();

    // Symulujemy, że węzeł przesunął się i osiadł na współrzędnych (123, 456)
    rootNode.x = 123;
    rootNode.y = 456;

    // Kliknij zwinięcie folderu src
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src' });
    });

    await waitFor(() => {
      const updatedNodes = mocks.mockFg.graphData().nodes;
      const updatedRoot = updatedNodes.find((n: any) => n.id === dirNodeId('c:/root'));
      expect(updatedRoot).toBeTruthy();
      // Pamięć przestrzenna zachowała pozycję (123, 456) zamiast resetować do (0, 0)!
      expect(updatedRoot.x).toBe(123);
      expect(updatedRoot.y).toBe(456);
    });
  });

  it('nie przestawia ani nie szarpie kamery przy operacji zwiń/rozwiń, zachowując widok użytkownika', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
    });

    mocks.mockFg.centerAt.mockClear();
    mocks.mockFg.zoom.mockClear();

    // Wywołaj zwinięcie
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src' });
    });

    await waitFor(() => {
      const updatedNodes = mocks.mockFg.graphData().nodes;
      expect(updatedNodes.length).toBeLessThan(5);
    });

    // Kamera nie była resetowana ani szarpana żadnym wywołaniem
    expect(mocks.mockFg.centerAt).not.toHaveBeenCalled();
    expect(mocks.mockFg.zoom).not.toHaveBeenCalled();
  });

  it('wyłącza siłę center (null) i rejestruje łagodne odpychanie oraz ogranicznik prędkości', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      expect(mocks.mockFg.d3Force).toHaveBeenCalledWith('center', null);
      expect(mocks.mockFg.d3Force).toHaveBeenCalledWith('wedgeConstraint', expect.any(Function));
      expect(mocks.mockFg.d3Force).toHaveBeenCalledWith('hardLineClearance', expect.any(Function));
      expect(mocks.mockFg.d3Force).toHaveBeenCalledWith('velocityClamp', expect.any(Function));
    });
  });

  it('odczytuje zapisane pozycje z SQLite (kosmosGetPositions) i ustawia węzły dokładnie na tych współrzędnych', async () => {
    const saved = {
      [dirNodeId('c:/root')]: { x: 777, y: 888 },
      [dirNodeId('c:/root/src')]: { x: -333, y: -444 },
    };
    (window.cortexBridge!.kosmosGetPositions as ReturnType<typeof vi.fn>).mockResolvedValue(saved);

    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      expect(window.cortexBridge!.kosmosGetPositions).toHaveBeenCalledWith({ projectId: 'cortex_app' });
    });

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      const nodes = last![0]?.nodes ?? [];
      const rootNode = nodes.find((n: any) => n.id === dirNodeId('c:/root'));
      const srcNode = nodes.find((n: any) => n.id === dirNodeId('c:/root/src'));
      expect(rootNode?.x).toBe(777);
      expect(rootNode?.y).toBe(888);
      expect(srcNode?.x).toBe(-333);
      expect(srcNode?.y).toBe(-444);
    });
  });

  it('zapisuje pozycje do SQLite (kosmosSavePositions) po zakończeniu symulacji (onEngineStop)', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
      expect(mocks.engineStopHandler.fn).not.toBeNull();
    });

    const nodes = mocks.mockFg.graphData().nodes;
    expect(nodes.length).toBeGreaterThan(0);
    nodes[0].x = 100;
    nodes[0].y = 200;

    act(() => {
      mocks.engineStopHandler.fn!();
    });

    await waitFor(() => {
      expect(window.cortexBridge!.kosmosSavePositions).toHaveBeenCalledWith(
        expect.objectContaining({
          projectId: 'cortex_app',
          positions: expect.objectContaining({
            [nodes[0].id]: { x: 100, y: 200 },
          }),
        }),
      );
    }, { timeout: 2000 });
  });

  it('przy wyłączonej fizyce rozszerzenie folderu daje fizykę WYŁĄCZNIE jego dzieciom, pozostawiając resztę galaktyki zamrożoną', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
    });

    // Najpierw zwiń folder src
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src', id: dirNodeId('c:/root/src') } as any);
    });

    await waitFor(() => {
      const nodes = mocks.mockFg.graphData().nodes;
      expect(nodes.find((n: any) => n.id === fileNodeId('c:/root/src/App.tsx'))).toBeUndefined();
    });

    // Wyłącz fizykę (pauza)
    const physicsBtn = await screen.findByText(/Fizyka:/i);
    fireEvent.click(physicsBtn);
    expect(physicsBtn.textContent).toContain('wstrzymana');

    // Teraz rozwiń folder src przy WYŁĄCZONEJ fizyce
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src', id: dirNodeId('c:/root/src') } as any);
    });

    await waitFor(() => {
      const nodes = mocks.mockFg.graphData().nodes;
      const appFile = nodes.find((n: any) => n.id === fileNodeId('c:/root/src/App.tsx'));
      const rootNode = nodes.find((n: any) => n.id === dirNodeId('c:/root'));
      const srcFolder = nodes.find((n: any) => n.id === dirNodeId('c:/root/src'));

      expect(appFile).toBeTruthy();
      // Dziecko rozwiniętego folderu (App.tsx) MA fizykę (brak fx, fy)!
      expect(appFile.fx).toBeUndefined();
      expect(appFile.fy).toBeUndefined();

      // Pozostałe węzły galaktyki (root, src itp.) są w 100% zablokowane (fx = x, fy = y)!
      expect(rootNode.fx).toBe(0);
      expect(rootNode.fy).toBe(0);
      expect(srcFolder.fx).toBe(srcFolder.x);
      expect(srcFolder.fy).toBe(srcFolder.y);
    });
  });

  it('po zakończeniu symulacji rozszerzonego folderu w trybie pauzy (onEngineStop) dzieci zostają zamrożone (fx, fy) i ich pozycje są zapisane', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
      expect(mocks.clickHandler.fn).not.toBeNull();
      expect(mocks.engineStopHandler.fn).not.toBeNull();
    });

    // Zwiń src
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src', id: dirNodeId('c:/root/src') } as any);
    });

    await waitFor(() => {
      const nodes = mocks.mockFg.graphData().nodes;
      expect(nodes.find((n: any) => n.id === fileNodeId('c:/root/src/App.tsx'))).toBeUndefined();
    });

    // Wyłącz fizykę
    const physicsBtn = await screen.findByText(/Fizyka:/i);
    fireEvent.click(physicsBtn);

    // Rozwiń src
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src', id: dirNodeId('c:/root/src') } as any);
    });

    await waitFor(() => {
      const app = mocks.mockFg.graphData().nodes.find((n: any) => n.id === fileNodeId('c:/root/src/App.tsx'));
      expect(app).toBeTruthy();
      expect(app.fx).toBeUndefined();
    });

    const appFile = mocks.mockFg.graphData().nodes.find((n: any) => n.id === fileNodeId('c:/root/src/App.tsx'));

    // Symulujemy koniec chłodzenia (silnik zatrzymuje się)
    appFile.x = 555;
    appFile.y = 666;

    act(() => {
      mocks.engineStopHandler.fn!();
    });

    // Po zatrzymaniu dziecko musi być zamrożone na stałe!
    expect(appFile.fx).toBe(555);
    expect(appFile.fy).toBe(666);

    // Pozycje zostały wysłane do SQLite
    await waitFor(() => {
      expect(window.cortexBridge!.kosmosSavePositions).toHaveBeenCalledWith(
        expect.objectContaining({
          projectId: 'cortex_app',
          positions: expect.objectContaining({
            [appFile.id]: { x: 555, y: 666 },
          }),
        }),
      );
    }, { timeout: 2000 });
  });

  it('przeciągnięcie węzła (onNodeDragEnd) przy zamrożonej fizyce blokuje go w miejscu upuszczenia i zapisuje pozycję', async () => {
    render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
      expect(mocks.dragEndHandler.fn).not.toBeNull();
    });

    // Wyłącz fizykę
    const physicsBtn = await screen.findByText(/Fizyka:/i);
    fireEvent.click(physicsBtn);

    const srcNode = mocks.mockFg.graphData().nodes.find((n: any) => n.id === dirNodeId('c:/root/src'));
    expect(srcNode).toBeTruthy();

    // Przeciągamy węzeł na nowe współrzędne (999, 888)
    srcNode.x = 999;
    srcNode.y = 888;
    delete srcNode.fx;
    delete srcNode.fy;

    act(() => {
      mocks.dragEndHandler.fn!(srcNode);
    });

    // onNodeDragEnd natychmiast zamraża węzeł na nowej pozycji
    expect(srcNode.fx).toBe(999);
    expect(srcNode.fy).toBe(888);

    // I zapisuje do SQLite
    await waitFor(() => {
      expect(window.cortexBridge!.kosmosSavePositions).toHaveBeenCalledWith(
        expect.objectContaining({
          projectId: 'cortex_app',
          positions: expect.objectContaining({
            [srcNode.id]: { x: 999, y: 888 },
          }),
        }),
      );
    }, { timeout: 2000 });
  });

  it('zapisuje i przywraca stan zwiniętych/rozwiniętych folderów w localStorage między sesjami', async () => {
    const { unmount } = render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
      expect(mocks.clickHandler.fn).not.toBeNull();
    });

    // Zwijamy folder src
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src', id: dirNodeId('c:/root/src') } as any);
    });

    // Sprawdzamy czy stan zwinięcia natychmiast trafił do localStorage
    const saved = localStorage.getItem('cortex_kosmos_cortex_app_collapsed');
    expect(saved).toBeTruthy();
    expect(JSON.parse(saved!)).toContain('c:/root/src');

    // Symulujemy zamknięcie i ponowne otwarcie widoku
    unmount();
    render(<KosmosView onBack={() => {}} />);

    // Na świeżo zamontowanym widoku folder src musi nadal pozostać zwinięty!
    await waitFor(() => {
      const nodes = mocks.mockFg.graphData().nodes;
      expect(nodes.length).toBeGreaterThan(0);
      // App.tsx nie ma w grafie, bo folder pamięta że jest zwinięty!
      expect(nodes.find((n: any) => n.id === fileNodeId('c:/root/src/App.tsx'))).toBeUndefined();
    });

    // Teraz rozwijamy folder src
    act(() => {
      mocks.clickHandler.fn!({ kind: 'folder', path: 'c:/root/src', id: dirNodeId('c:/root/src') } as any);
    });

    // Sprawdzamy czy w localStorage folder został odznaczony
    const updated = localStorage.getItem('cortex_kosmos_cortex_app_collapsed');
    expect(JSON.parse(updated!)).not.toContain('c:/root/src');

    // App.tsx pojawia się w grafie
    await waitFor(() => {
      const nodes = mocks.mockFg.graphData().nodes;
      expect(nodes.find((n: any) => n.id === fileNodeId('c:/root/src/App.tsx'))).toBeTruthy();
    });
  });

  it('zapisuje i przywraca pozycje węzłów w localStorage synchronicznie między sesjami', async () => {
    // 1. Zapisujemy pozycję ręcznie w localStorage
    localStorage.setItem(
      'cortex_kosmos_cortex_app_positions',
      JSON.stringify({
        [dirNodeId('c:/root')]: { x: 1234, y: 5678 },
      }),
    );

    // 2. Montujemy KosmosView — SQLite zwraca puste obiekty
    (window.cortexBridge!.kosmosGetPositions as ReturnType<typeof vi.fn>).mockResolvedValue({});

    render(<KosmosView onBack={() => {}} />);

    // 3. Pozycja natychmiast zostaje odczytana z localStorage bez czekania na bazę!
    await waitFor(() => {
      const nodes = mocks.mockFg.graphData().nodes;
      const rootNode = nodes.find((n: any) => n.id === dirNodeId('c:/root'));
      expect(rootNode).toBeTruthy();
      expect(rootNode.x).toBe(1234);
      expect(rootNode.y).toBe(5678);
    });
  });

  it('natychmiast zapisuje pozycje do localStorage przy odmontowaniu komponentu (onBack)', async () => {
    const { unmount } = render(<KosmosView onBack={() => {}} />);

    await waitFor(() => {
      const last = mocks.mockFg.graphData.mock.calls.at(-1);
      expect(last).toBeTruthy();
      expect(last![0]?.nodes?.length).toBeGreaterThan(0);
    });

    const rootNode = mocks.mockFg.graphData().nodes.find((n: any) => n.id === dirNodeId('c:/root'));
    expect(rootNode).toBeTruthy();
    rootNode.x = 4444;
    rootNode.y = 5555;

    // Odmontowujemy komponent (np. użytkownik klika 'Wróć do notatek')
    unmount();

    // Pozycje natychmiast znalazły się w localStorage bez opóźnienia
    const saved = localStorage.getItem('cortex_kosmos_cortex_app_positions');
    expect(saved).toBeTruthy();
    const parsed = JSON.parse(saved!);
    expect(parsed[dirNodeId('c:/root')]).toEqual({ x: 4444, y: 5555 });
  });
});