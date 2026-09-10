export interface ZoomTransformParams {
  currentScale: number;
  currentOffset: { x: number; y: number };
  focalX: number;
  focalY: number;
  factor: number;
  viewportWidth?: number;
  viewportHeight?: number;
  centeringFactor?: number;
  minScale?: number;
  maxScale?: number;
}

export interface ZoomTransformResult {
  scale: number;
  offset: { x: number; y: number };
}

export interface MacroEdge {
  id: string;
  source_project_id: string;
  target_project_id: string;
  has_arrow?: boolean;
}

// Połączenie między klastrami lub klamrami Z RÓŻNYCH projektów.
// Widoczne wyłącznie w widoku makro oraz w kontekście wysyłanym do AI.
export type MacroClusterNodeKind = 'cluster' | 'bracket' | 'project';

export interface MacroClusterLink {
  id: string;
  source_project_id: string;
  source_kind: MacroClusterNodeKind;
  source_key: string; // clusterKey (nodeId) lub bracket id
  source_label: string;
  target_project_id: string;
  target_kind: MacroClusterNodeKind;
  target_key: string;
  target_label: string;
  has_arrow?: boolean;
}

// Zaznaczenie/źródło łączenia klastra lub klamry w makro.
export interface MacroClusterRef {
  projectId: string;
  kind: MacroClusterNodeKind;
  key: string;
  label: string;
}

export interface MacroClusterAnchor {
  anchorId: string; // `${projectId}:${kind}:${key}`
  projectId: string;
  kind: MacroClusterNodeKind;
  key: string;
  label: string;
  x: number;
  y: number;
  box?: { x: number; y: number; width: number; height: number };
}
