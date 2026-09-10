export interface Projekt {
  id: string;
  name: string;
  folder_id?: string | null;
  project_type?: 'technical';
  x?: number;
  y?: number;
  notes_count?: number;
  cluster_descriptions?: Record<string, string>;
  cluster_offsets?: Record<string, { x: number; y: number }>;
  brackets?: ProjektyBracket[];
  created_at?: string;
  updated_at?: string;
}

export interface ProjektyBracket {
  id: string;
  project_id: string;
  name: string;
  node_ids: string[];
  track?: number;
  orientation?: 'auto' | 'vertical' | 'horizontal';
  side?: 'left' | 'right' | 'top' | 'bottom';
  created_at?: string;
}

export interface ProjectGroup {
  id: string;
  name: string;
  collapsed?: boolean;
  color?: string;
  created_at?: string;
  updated_at?: string;
}

export type NodeType = 'root' | 'domain' | 'component' | 'task' | 'integration' | 'note' | 'portal';
export type NodeStatus = 'new' | 'in_progress' | 'ready' | 'deprecated';
export type RelationType = 'requires' | 'depends_on' | 'data_flow' | 'sync' | 'supports';

export interface NodeMetadata {
  is_leaf?: boolean;
  stack?: string[];
  author?: 'user' | 'ai';
  associated_task_id?: string;
  timestamp?: string;
  target_project_id?: string;
}

export interface ProjektyNode {
  id: string;
  project_id: string;
  title: string;
  content: string;
  label?: string;
  description?: string;
  node_type?: NodeType;
  status?: NodeStatus;
  metadata?: NodeMetadata | string;
  parent_id?: string | null;
  x: number;
  y: number;
  width?: number;
  height?: number;
  collapsed?: number;
  locked_position?: boolean;
  ai_suggestion?: boolean;
  ai_suggestion_reason?: string;
  source_message_id?: string | null;
  source_conversation_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ProjektyEdge {
  id: string;
  project_id: string;
  source_node_id: string;
  target_node_id: string;
  label?: string;
  has_arrow?: boolean;
  relation_type?: RelationType;
  source_handle?: string;
  target_handle?: string;
  locked?: boolean;
  created_at?: string;
}

export interface ProjektyNodeAnnotation {
  id: string;
  node_id: string;
  project_id: string;
  content: string;
  created_at?: string;
}
