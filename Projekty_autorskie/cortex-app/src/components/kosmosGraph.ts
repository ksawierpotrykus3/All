// ============================================================================
// KOSMOS — czysta logika budowania grafu siłowego z danych SQLite.
// Bez zależności od DOM/canvas — łatwa do testowania jednostkowego.
// ============================================================================

import type { KosmosGraphData, KosmosFolderRow } from '../shared/types/kosmos';

export interface GraphNode {
  id: string;
  kind: 'folder' | 'file';
  label: string;
  path: string;
  type?: KosmosGraphData['files'][number]['type'];
  depth: number;
  fileCount: number;
  topBranch?: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  kind: 'contains';
}

export interface VisibleGraph {
  nodes: GraphNode[];
  links: GraphLink[];
}

export const dirNodeId = (p: string) => `d:${p}`;
export const fileNodeId = (p: string) => `f:${p}`;

export function folderLabel(folder: KosmosFolderRow): string {
  return folder.relative_path === '' ? folder.name : folder.relative_path;
}

/**
 * Wylicza optymalną długość krawędzi (promień) do podfolderów.
 * Skaluje się proporcjonalnie do liczby potomków, zapewniając odpowiedni
 * obwód wachlarza, by węzły i ich pliki nie tłoczyły się ani nie przecinały linii sąsiadów.
 */
export function calcChildFolderDistance(childCount: number, fileCount: number = 0): number {
  return Math.max(45, Math.min(160, 32 + childCount * 5.5 + Math.sqrt(fileCount) * 2.0));
}


/**
 * Buduje widoczny graf hierarchii, respektując zwinięte foldery.
 * Wylicza początkowy, uporządkowany układ biegunowy (polar layout) wg gałęzi,
 * co zapobiega eksplozji w t=0 oraz krzyżowaniu się obcych drzew.
 */
export function buildVisibleGraph(
  graphData: KosmosGraphData,
  collapsedFolders: Set<string>,
): VisibleGraph {
  const folderMap = new Map(graphData.folders.map((f) => [f.path, f]));

  const childFoldersByParent = new Map<string, KosmosFolderRow[]>();
  for (const folder of graphData.folders) {
    const list = childFoldersByParent.get(folder.parent_path) ?? [];
    list.push(folder);
    childFoldersByParent.set(folder.parent_path, list);
  }

  const filesByFolder = new Map<string, KosmosGraphData['files']>();
  for (const file of graphData.files) {
    const list = filesByFolder.get(file.folder_path) ?? [];
    list.push(file);
    filesByFolder.set(file.folder_path, list);
  }

  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];

  const roots = graphData.folders.filter((f) => f.depth === 0);
  const effectiveRoots = roots.length > 0
    ? roots
    : graphData.folders[0]
      ? [graphData.folders[0]]
      : [];
  if (effectiveRoots.length === 0) return { nodes, links };

  // Odstęp między "galaktykami" projektów w trybie wszystkich projektów naraz.
  const GALAXY_SPACING = Math.max(600, effectiveRoots.length * 260);

  const visitFolder = (
    folderPath: string,
    topBranch: string,
    posX: number,
    posY: number,
    dirAngle: number,
  ) => {
    const folder = folderMap.get(folderPath);
    if (!folder) return;

    const folderId = dirNodeId(folder.path);
    nodes.push({
      id: folderId,
      kind: 'folder',
      label: folderLabel(folder),
      path: folder.path,
      depth: folder.depth,
      fileCount: folder.file_count,
      topBranch,
      x: posX,
      y: posY,
    });

    if (collapsedFolders.has(folder.path)) return;

    const children = childFoldersByParent.get(folder.path) ?? [];
    const childCount = children.length;

    // Wartości specyficzne dla poziomu root — liczone osobno dla każdego projektu.
    const rootFiles = folder.depth === 0 ? (filesByFolder.get(folder.path) ?? []) : [];
    const hasRootFiles = folder.depth === 0 && rootFiles.length > 0;
    const topBranches = folder.depth === 0 ? (childFoldersByParent.get(folder.path) ?? []) : [];
    const topBranchCount = folder.depth === 0
      ? Math.max(1, topBranches.length + (hasRootFiles ? 1 : 0))
      : 1;

    children.forEach((child, idx) => {
      let childAngle = dirAngle;
      let childDist = 45;
      let childTopBranch = topBranch;

      if (folder.depth === 0) {
        childAngle = (2 * Math.PI * idx) / topBranchCount - Math.PI / 2;
        childDist = 130;
        childTopBranch = child.path;
      } else if (childCount > 1) {
        // Kontrolowany stożek przedni (max ~70° / +/- 35°), by gałęzie potomne NIGDY nie zawracały
        // w stronę roota ani nie przecinały linii sąsiednich gałęzi głównych!
        const fanSpread = Math.min(1.22, 0.12 * childCount);
        childAngle = dirAngle + (idx - (childCount - 1) / 2) * (fanSpread / Math.max(1, childCount - 1));
        const baseDist = calcChildFolderDistance(childCount, folder.file_count);
        // Piętrowe rozwijanie (petale): nieparzyste dzieci wysunięte dalej, by nie tłoczyć się po obwodzie
        const tier = idx % 2;
        childDist = childCount > 4 ? baseDist + tier * 32 : baseDist;
      }

      const cx = posX + Math.cos(childAngle) * childDist;
      const cy = posY + Math.sin(childAngle) * childDist;

      visitFolder(child.path, childTopBranch, cx, cy, childAngle);
      links.push({
        source: folderId,
        target: dirNodeId(child.path),
        kind: 'contains',
      });
    });

    // Luźne pliki w katalogu głównym (roocie): zwijane w dedykowany węzeł-gałąź,
    // by nie obklejały środka projektu i nie kolidowały z krawędziami głównych folderów.
    if (folder.depth === 0 && hasRootFiles) {
      const vPath = `${folder.path}::[pliki]`;
      const vId = dirNodeId(vPath);
      const vAngle = (2 * Math.PI * topBranches.length) / topBranchCount - Math.PI / 2;
      const vDist = 110;
      const vx = posX + Math.cos(vAngle) * vDist;
      const vy = posY + Math.sin(vAngle) * vDist;

      nodes.push({
        id: vId,
        kind: 'folder',
        label: `📄 Pliki projektu (${rootFiles.length})`,
        path: vPath,
        depth: 1,
        fileCount: rootFiles.length,
        topBranch: vPath,
        x: vx,
        y: vy,
      });

      links.push({
        source: folderId,
        target: vId,
        kind: 'contains',
      });

      if (!collapsedFolders.has(vPath)) {
        rootFiles.forEach((file, fIdx) => {
          const fid = fileNodeId(file.path);
          const fanSpan = Math.min(Math.PI * 0.9, 0.28 * rootFiles.length);
          const fAngle =
            vAngle +
            (fIdx - (rootFiles.length - 1) / 2) *
              (rootFiles.length > 1 ? fanSpan / (rootFiles.length - 1) : 0);
          const fx = vx + Math.cos(fAngle) * 18;
          const fy = vy + Math.sin(fAngle) * 18;

          nodes.push({
            id: fid,
            kind: 'file',
            label: file.name,
            path: file.path,
            type: file.type,
            depth: 2,
            fileCount: 0,
            topBranch: vPath,
            x: fx,
            y: fy,
          });
          links.push({ source: vId, target: fid, kind: 'contains' });
        });
      }
    } else if (folder.depth > 0) {
      // Pliki w regularnych podfolderach
      const files = filesByFolder.get(folder.path) ?? [];
      const fileCount = files.length;

      files.forEach((file, fIdx) => {
        const fid = fileNodeId(file.path);
        let fAngle: number;
        let fDist = 18;

        if (childCount > 0) {
          // Folder ma podfoldery: pliki tworzą zwięzły pęczek w stożku przednim (+/- 20° od osi),
          // rozwijając się warstwowo wzdłuż promienia na zewnątrz — NIGDY w linie sąsiadów!
          const side = fIdx % 2 === 0 ? 1 : -1;
          const layer = Math.floor(fIdx / 2);
          fAngle = dirAngle + side * 0.35;
          fDist = 18 + layer * 10;
        } else {
          // Folder liść: pliki tworzą wąską koronę z przodu w zewnętrznym sektorze (max +/- 25°)
          const fanSpan = Math.min(Math.PI * 0.45, 0.16 * fileCount);
          fAngle =
            dirAngle +
            (fIdx - (fileCount - 1) / 2) *
              (fileCount > 1 ? fanSpan / (fileCount - 1) : 0);
          fDist = 18;
        }

        const fx = posX + Math.cos(fAngle) * fDist;
        const fy = posY + Math.sin(fAngle) * fDist;

        nodes.push({
          id: fid,
          kind: 'file',
          label: file.name,
          path: file.path,
          type: file.type,
          depth: folder.depth + 1,
          fileCount: 0,
          topBranch,
          x: fx,
          y: fy,
        });
        links.push({ source: folderId, target: fid, kind: 'contains' });
      });
    }
  };

  effectiveRoots.forEach((root, ri) => {
    let rootX = 0;
    let rootY = 0;
    if (effectiveRoots.length > 1) {
      const angle = (2 * Math.PI * ri) / effectiveRoots.length - Math.PI / 2;
      rootX = Math.cos(angle) * GALAXY_SPACING;
      rootY = Math.sin(angle) * GALAXY_SPACING;
    }
    visitFolder(root.path, '__root__', rootX, rootY, 0);
  });

  return { nodes, links };
}