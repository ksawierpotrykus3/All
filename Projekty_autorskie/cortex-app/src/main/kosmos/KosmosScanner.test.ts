import { describe, it, expect } from 'vitest';
import { scanKosmos } from './KosmosScanner';

describe('scanKosmos deterministic verification', () => {
  it('correctly scans cortex-app and łowca with previews, groups, and edges', () => {
    const folders = [
      'c:/Users/Ksawier/Pictures/Screenshots/Projekty_autorskie/cortex-app',
      'c:/Users/Ksawier/Pictures/Screenshots/Projekty_autorskie/łowca',
    ];
    const graph = scanKosmos(folders);

    expect(graph.nodes.length).toBeGreaterThan(0);
    expect(graph.edges.length).toBeGreaterThan(0);

    const cortexNodes = graph.nodes.filter((n) => n.source === 'cortex-app');
    const lowcaNodes = graph.nodes.filter((n) => n.source === 'łowca');

    const folderNodes = graph.nodes.filter((n) => n.kind === 'folder');
    const fileNodes = graph.nodes.filter((n) => n.kind === 'file');
    const containsEdges = graph.edges.filter((e) => e.kind === 'contains');
    const importEdges = graph.edges.filter((e) => e.kind === 'import');

    console.log('[TEST] Total nodes:', graph.nodes.length);
    console.log('[TEST] Folders:', folderNodes.length, 'Files:', fileNodes.length);
    console.log('[TEST] Cortex nodes:', cortexNodes.length);
    console.log('[TEST] Łowca nodes:', lowcaNodes.length);
    console.log('[TEST] Total edges:', graph.edges.length, '(contains:', containsEdges.length, ', import:', importEdges.length, ')');

    // Hierarchia folderów: węzły folderów istnieją, a pliki są do nich dołączone przez 'contains'
    expect(folderNodes.length).toBeGreaterThan(0);
    expect(fileNodes.length).toBeGreaterThan(0);
    expect(containsEdges.length).toBeGreaterThan(0);

    const groups: Record<string, number> = {};
    for (const n of graph.nodes) {
      const g = n.group || 'unknown';
      groups[g] = (groups[g] || 0) + 1;
    }
    console.log('[TEST] Groups distribution:', groups);

    const nodesWithPreview = graph.nodes.filter((n) => typeof n.preview === 'string' && n.preview.length > 0);
    console.log('[TEST] Nodes with non-empty preview:', nodesWithPreview.length);
    expect(nodesWithPreview.length).toBeGreaterThan(0);

    if (lowcaNodes.length > 0) {
      console.log('[TEST] Sample Łowca node:', {
        name: lowcaNodes[0].name,
        group: lowcaNodes[0].group,
        folder: lowcaNodes[0].folder,
        previewLength: lowcaNodes[0].preview?.length,
        previewSnippet: lowcaNodes[0].preview?.slice(0, 100),
      });
    }

    if (cortexNodes.length > 0) {
      console.log('[TEST] Sample Cortex node:', {
        name: cortexNodes[0].name,
        group: cortexNodes[0].group,
        folder: cortexNodes[0].folder,
        previewLength: cortexNodes[0].preview?.length,
      });
    }

    expect(cortexNodes.length).toBeGreaterThan(0);
    expect(lowcaNodes.length).toBeGreaterThan(0);
  });
});
