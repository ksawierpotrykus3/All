import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { NotesCanvas } from '../NotesCanvas';
import type { Projekt, ProjektyNode } from '../../types';
import type { cortexBridge } from '../../shared/types/ipc';

let mockProjects: Projekt[];
let mockNodes: ProjektyNode[];
let mockBridge: Partial<cortexBridge>;

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  localStorage.clear();
  mockProjects = [
    {
      id: 'proj-1',
      name: 'Projekt Alpha',
      cluster_descriptions: {
        'node-1': 'Baza Danych',
        'node-3': 'API Serwera',
      },
      brackets: [
        {
          id: 'bracket-1',
          project_id: 'proj-1',
          name: 'Backend Core',
          node_ids: ['node-1', 'node-3'],
        },
      ],
      cluster_offsets: {
        'node-1': { x: 370, y: 0 },
        'node-3': { x: 370, y: 90 },
      },
      notes_count: 2,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'proj-2',
      name: 'Projekt Beta',
      cluster_descriptions: {
        'node-2': 'Frontend UI',
      },
      notes_count: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  mockNodes = [
    {
      id: 'node-1',
      project_id: 'proj-1',
      title: '',
      content: 'Wpis BD',
      x: 100,
      y: 100,
      width: 280,
      height: 140,
    },
    {
      id: 'node-3',
      project_id: 'proj-1',
      title: '',
      content: 'Wpis API',
      x: 100,
      y: 300,
      width: 280,
      height: 140,
    },
    {
      id: 'node-2',
      project_id: 'proj-2',
      title: '',
      content: 'Wpis UI',
      x: 500,
      y: 100,
      width: 280,
      height: 140,
    },
  ];

  mockBridge = {
    projGetProjects: vi.fn().mockResolvedValue(mockProjects),
    projSaveProject: vi.fn().mockResolvedValue({ success: true }),
    projDeleteProject: vi.fn().mockResolvedValue({ success: true }),
    projGetNodes: vi.fn().mockImplementation(({ projectId }) =>
      Promise.resolve(mockNodes.filter((n) => n.project_id === projectId)),
    ),
    projGetEdges: vi.fn().mockResolvedValue([]),
    projSaveNode: vi.fn().mockResolvedValue({ success: true }),
    projDeleteNode: vi.fn().mockResolvedValue({ success: true }),
    projSaveEdge: vi.fn().mockResolvedValue({ success: true }),
    projDeleteEdge: vi.fn().mockResolvedValue({ success: true }),
  };

  window.cortexBridge = mockBridge as any;
  window.confirm = vi.fn(() => true);
});

async function switchToMacroView() {
  const switcherBtn = await screen.findByTestId('project-switcher-button');
  fireEvent.click(switcherBtn);
  const macroBtn = await screen.findByTestId('macro-view-toggle-btn');
  fireEvent.click(macroBtn);
}

describe('Macro Canvas - Cluster, Bracket and Project Linking', () => {
  it('renders projects and satellite clusters in macro view', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    const cluster1 = await screen.findByTestId('macro-cluster-satellite-proj-1-node-1');
    const cluster2 = await screen.findByTestId('macro-cluster-satellite-proj-2-node-2');

    expect(cluster1).toBeDefined();
    expect(cluster1.textContent).toContain('Baza Danych');
    expect(cluster2).toBeDefined();
    expect(cluster2.textContent).toContain('Frontend UI');
  });

  it('selects a cluster satellite on click without selecting the project card', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    const cluster1 = await screen.findByTestId('macro-cluster-satellite-proj-1-node-1');
    const projectCard1 = await screen.findByTestId('project-island-proj-1');

    fireEvent.mouseDown(cluster1, { clientX: 200, clientY: 200 });
    fireEvent.click(cluster1);

    // Satelita ma klasę podświetlenia zaznaczenia ring-[#FFC799]
    expect(cluster1.className).toContain('ring-[#FFC799]');
    // Karta projektu NIE może być zaznaczona
    expect(projectCard1.getAttribute('data-selected')).toBe('false');
  });

  it('starts macro cluster linking on Tab key, shows banner and preview line', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    const cluster1 = await screen.findByTestId('macro-cluster-satellite-proj-1-node-1');
    fireEvent.mouseDown(cluster1, { clientX: 200, clientY: 200 });
    fireEvent.click(cluster1);

    // Wciśnięcie Tab
    fireEvent.keyDown(window, { key: 'Tab' });

    // Banner informacyjny musi być widoczny
    const banner = await screen.findByTestId('macro-cluster-linking-banner');
    expect(banner.textContent).toContain('Baza Danych');
    expect(banner.textContent).toContain('Kliknij cel');

    // Satelita źródłowy ma mocniejsze podświetlenie źródła
    expect(cluster1.className).toContain('ring-2 ring-[#FFC799]');

    // Ruch myszką generuje linię podglądu
    fireEvent.mouseMove(window, { clientX: 400, clientY: 300 });
    const previewLine = document.querySelector('.macro-cluster-preview-line');
    expect(previewLine).not.toBeNull();
  });

  it('cancels linking on Escape key or banner button', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    const cluster1 = await screen.findByTestId('macro-cluster-satellite-proj-1-node-1');
    fireEvent.mouseDown(cluster1, { clientX: 200, clientY: 200 });
    fireEvent.click(cluster1);
    fireEvent.keyDown(window, { key: 'Tab' });

    expect(await screen.findByTestId('macro-cluster-linking-banner')).toBeDefined();

    // Escape anuluje
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('macro-cluster-linking-banner')).toBeNull();
  });

  it('connects cluster to cluster on target click and saves to localStorage', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    const cluster1 = await screen.findByTestId('macro-cluster-satellite-proj-1-node-1');
    const cluster2 = await screen.findByTestId('macro-cluster-satellite-proj-2-node-2');

    // Zaznacz klaster 1 i włącz łączenie
    fireEvent.mouseDown(cluster1, { clientX: 200, clientY: 200 });
    fireEvent.click(cluster1);
    fireEvent.keyDown(window, { key: 'Tab' });

    expect(await screen.findByTestId('macro-cluster-linking-banner')).toBeDefined();

    // Kliknij w klaster 2 jako cel
    fireEvent.mouseDown(cluster2, { clientX: 500, clientY: 200 });
    fireEvent.click(cluster2);

    // Tryb łączenia powinien się zamknąć
    expect(screen.queryByTestId('macro-cluster-linking-banner')).toBeNull();

    // Powiązanie zapisane w localStorage
    const saved = localStorage.getItem('cortex_macro_cluster_links');
    expect(saved).not.toBeNull();
    const links = JSON.parse(saved || '[]');
    expect(links.length).toBe(1);
    expect(links[0]).toMatchObject({
      source_project_id: 'proj-1',
      source_kind: 'cluster',
      source_key: 'node-1',
      target_project_id: 'proj-2',
      target_kind: 'cluster',
      target_key: 'node-2',
    });
  });

  it('connects cluster to project card on project card click', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    const cluster1 = await screen.findByTestId('macro-cluster-satellite-proj-1-node-1');
    const projectCard2 = await screen.findByTestId('project-island-proj-2');

    fireEvent.mouseDown(cluster1, { clientX: 200, clientY: 200 });
    fireEvent.click(cluster1);
    fireEvent.keyDown(window, { key: 'Tab' });

    expect(await screen.findByTestId('macro-cluster-linking-banner')).toBeDefined();

    // Klik w kartę Projektu 2
    fireEvent.click(projectCard2);

    expect(screen.queryByTestId('macro-cluster-linking-banner')).toBeNull();

    const saved = localStorage.getItem('cortex_macro_cluster_links');
    const links = JSON.parse(saved || '[]');
    expect(links.length).toBe(1);
    expect(links[0]).toMatchObject({
      source_project_id: 'proj-1',
      source_kind: 'cluster',
      source_key: 'node-1',
      target_project_id: 'proj-2',
      target_kind: 'project',
      target_key: 'proj-2',
    });
  });

  it('connects bracket to cluster on bracket click in linking mode', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    // Szukamy etykiety klamry z proj-1
    const bracketLabel = await screen.findByText('Backend Core');
    const bracketContainer = bracketLabel.closest('div[title*="Klamra"]');
    expect(bracketContainer).not.toBeNull();

    // Klik w klamrę
    fireEvent.click(bracketContainer!);
    fireEvent.keyDown(window, { key: 'Tab' });

    const banner = await screen.findByTestId('macro-cluster-linking-banner');
    expect(banner.textContent).toContain('Backend Core');

    // Klik w klaster projektu 2
    const cluster2 = await screen.findByTestId('macro-cluster-satellite-proj-2-node-2');
    fireEvent.click(cluster2);

    expect(screen.queryByTestId('macro-cluster-linking-banner')).toBeNull();

    const saved = localStorage.getItem('cortex_macro_cluster_links');
    const links = JSON.parse(saved || '[]');
    expect(links.length).toBe(1);
    expect(links[0]).toMatchObject({
      source_project_id: 'proj-1',
      source_kind: 'bracket',
      source_key: 'bracket-1',
      target_project_id: 'proj-2',
      target_kind: 'cluster',
      target_key: 'node-2',
    });
  });

  it('allows deleting a macro cluster link by clicking the [ ✕ ] button', async () => {
    // Ustawiamy istniejące połączenie w localStorage
    const initialLink = {
      id: 'test-link-1',
      source_project_id: 'proj-1',
      source_kind: 'cluster',
      source_key: 'node-1',
      source_label: 'Klaster 1',
      target_project_id: 'proj-2',
      target_kind: 'cluster',
      target_key: 'node-2',
      target_label: 'Klaster 2',
    };
    localStorage.setItem('cortex_macro_cluster_links', JSON.stringify([initialLink]));

    render(<NotesCanvas />);
    await switchToMacroView();

    // Szukamy przycisku usuwania dla tego połączenia
    const deleteBtn = await screen.findByTestId('macro-link-delete-test-link-1');
    expect(deleteBtn).not.toBeNull();

    // Klik w [ ✕ ]
    fireEvent.click(deleteBtn);

    const saved = localStorage.getItem('cortex_macro_cluster_links');
    const links = JSON.parse(saved || '[]');
    expect(links.length).toBe(0);
  });

  it('allows selecting and deleting a macro cluster link using the Delete key', async () => {
    const initialLink = {
      id: 'test-link-keyboard',
      source_project_id: 'proj-1',
      source_kind: 'bracket',
      source_key: 'bracket-1',
      source_label: 'Backend Core',
      target_project_id: 'proj-2',
      target_kind: 'cluster',
      target_key: 'node-2',
      target_label: 'Klaster 2',
    };
    localStorage.setItem('cortex_macro_cluster_links', JSON.stringify([initialLink]));

    render(<NotesCanvas />);
    await switchToMacroView();

    // Szukamy przycisku usuwania lub klikalnej ścieżki
    const deleteBtn = await screen.findByTestId('macro-link-delete-test-link-keyboard');
    const pathContainer = deleteBtn.closest('g.group\\/clusterlink');
    expect(pathContainer).not.toBeNull();

    // Kliknięcie w grupę połączenia (zaznaczenie linii)
    const hitPath = pathContainer!.querySelector('path[stroke="transparent"]');
    expect(hitPath).not.toBeNull();
    fireEvent.click(hitPath!);

    // Wciśnięcie klawisza Delete
    fireEvent.keyDown(window, { key: 'Delete' });

    const saved = localStorage.getItem('cortex_macro_cluster_links');
    const links = JSON.parse(saved || '[]');
    expect(links.length).toBe(0);
  });

  it('does not crash (black screen) when dragging a cluster in a bracket away from another', async () => {
    render(<NotesCanvas />);
    await switchToMacroView();

    const cluster1 = await screen.findByTestId('macro-cluster-satellite-proj-1-node-1');
    fireEvent.mouseDown(cluster1, { clientX: 300, clientY: 300 });
    fireEvent.mouseMove(window, { clientX: 600, clientY: 800 });
    fireEvent.mouseUp(window);
  });

  it('does not crash with real user projects when dragging a bracketed cluster', async () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const fs = await import('fs');
    const obsProj = JSON.parse(fs.readFileSync('data/projekty/projects/n_1788103096717_mi7uvs.json', 'utf8'));
    mockBridge.projGetProjects = vi.fn().mockResolvedValue([obsProj]);
    render(<NotesCanvas />);
    await switchToMacroView();

    // Try dragging all clusters in obsProj
    for (const [key] of Object.entries(obsProj.cluster_descriptions)) {
      const cluster = screen.queryByTestId(`macro-cluster-satellite-n_1788103096717_mi7uvs-${key}`);
      if (cluster) {
        fireEvent.mouseDown(cluster, { clientX: 300, clientY: 300 });
        for (let offset = 10; offset <= 250; offset += 50) {
          fireEvent.mouseMove(window, { clientX: 300 + offset, clientY: 300 - offset });
        }
        fireEvent.mouseUp(window);
      }
    }
  });
});
