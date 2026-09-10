import type { MouseEvent as ReactMouseEvent, MutableRefObject } from 'react';
import type { ProjektyNode, ProjektyEdge } from '../../../types';
import { getTransitiveConnectedNodes } from '../utils/nodePlacement';
import { PORTAL_NODE_WIDTH, PORTAL_NODE_HEIGHT } from '../constants';
import { CloseIcon } from '../icons/CanvasIcons';

interface PortalCardProps {
  node: ProjektyNode;
  visibleNodes: ProjektyNode[];
  edges: ProjektyEdge[];
  isSource: boolean;
  isSelected: boolean;
  isEditing: boolean;
  draggingNodeId: string | null;
  theme: 'light' | 'dark';
  linkingMode: boolean;
  cardElRefs: MutableRefObject<Record<string, HTMLDivElement | null>>;
  editingText: string;
  setEditingText: (t: string) => void;
  editingTextRef: MutableRefObject<string>;
  startEditing: (id: string) => void;
  commitEditing: (targetId?: string, targetText?: string) => Promise<void>;
  cancelEditing: () => void;
  deleteNote: (id: string) => Promise<void>;
  handleNodeLinkingClick: (id: string) => Promise<void>;
  onCardMouseDown: (node: ProjektyNode, e: ReactMouseEvent) => void;
  onHeaderMouseDown: (node: ProjektyNode, e: ReactMouseEvent) => void;
  handleOpenPortalAsProject: (portalNode: ProjektyNode, connectedNodes: ProjektyNode[]) => Promise<void>;
  isClusterView?: boolean;
}

export function PortalCard({
  node,
  visibleNodes,
  edges,
  isSource,
  isSelected,
  isEditing,
  draggingNodeId,
  theme,
  linkingMode,
  cardElRefs,
  editingText,
  setEditingText,
  editingTextRef,
  startEditing,
  commitEditing,
  cancelEditing,
  deleteNote,
  handleNodeLinkingClick,
  onCardMouseDown,
  onHeaderMouseDown,
  handleOpenPortalAsProject,
  isClusterView = false,
}: PortalCardProps) {
  const connectedNodes = getTransitiveConnectedNodes(node.id, visibleNodes, edges);

  return (
    <div
      key={node.id}
      ref={(el) => {
        if (el) {
          cardElRefs.current[node.id] = el;
        } else {
          delete cardElRefs.current[node.id];
        }
      }}
      tabIndex={0}
      data-testid={`portal-card-${node.id}`}
      data-node-id={node.id}
      data-selected={isSelected}
      data-editing={isEditing}
      data-linking-source={isSource}
      className={`absolute overflow-hidden rounded-2xl border group transition-colors pointer-events-auto outline-none flex flex-col p-4 select-none ${
        draggingNodeId === node.id ? '!transition-none' : ''
      }`}
      style={{
        left: node.x,
        top: node.y,
        width: node.width || PORTAL_NODE_WIDTH,
        minHeight: node.height || PORTAL_NODE_HEIGHT,
        zIndex: draggingNodeId === node.id ? 100 : isSelected ? 50 : 2,
        backgroundColor: '#141414',
        opacity: isClusterView ? 0.05 : 1,
        pointerEvents: isClusterView ? 'none' : 'auto',
        transition: 'opacity 150ms ease-out, border-color 150ms ease-out',
        borderColor: isSelected || isEditing
          ? 'rgba(255, 199, 153, 0.65)'
          : isSource
          ? '#FFC799'
          : '#242424',
        boxShadow: isSelected || isEditing
          ? '0 0 0 1px rgba(255, 199, 153, 0.25), 0 16px 36px -4px rgba(0, 0, 0, 0.8)'
          : '0 12px 28px -6px rgba(0, 0, 0, 0.6), inset 0 1px 1px 0 rgba(255, 255, 255, 0.03)',
      }}
      onClick={
        linkingMode
          ? (e) => {
              e.stopPropagation();
              void handleNodeLinkingClick(node.id);
            }
          : undefined
      }
      onMouseDown={(e) => onCardMouseDown(node, e)}
    >
      {/* Nagłówek Portalu */}
      <div
        className="flex items-center justify-between border-b cursor-grab active:cursor-grabbing pb-2 mb-2 transition-colors"
        style={{
          borderBottomColor: theme === 'dark' ? '#262626' : 'rgba(226, 232, 240, 0.8)',
        }}
        onDoubleClick={(e) => {
          e.stopPropagation();
          startEditing(node.id);
        }}
        onMouseDown={(e) => onHeaderMouseDown(node, e)}
      >
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          {isEditing ? (
            <input
              type="text"
              autoFocus
              value={editingText}
              onChange={(e) => {
                setEditingText(e.target.value);
                editingTextRef.current = e.target.value;
              }}
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              onBlur={() => void commitEditing(node.id, editingText)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void commitEditing(node.id, editingText);
                if (e.key === 'Escape') cancelEditing();
              }}
              className="text-xs font-semibold bg-transparent border-b border-[#FFC799] outline-none flex-1 text-white"
              placeholder="Nazwa projektu..."
            />
          ) : (
            <span
              onDoubleClick={(e) => {
                e.stopPropagation();
                startEditing(node.id);
              }}
              className="text-xs font-semibold truncate text-[#eeeeee] cursor-text hover:underline"
              title="Kliknij dwukrotnie, aby zmienić nazwę projektu"
            >
              {node.title || 'Nowy projekt'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            tabIndex={-1}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              void deleteNote(node.id);
            }}
            className={`opacity-0 group-hover:opacity-100 focus-visible:opacity-100 h-5 w-5 flex items-center justify-center rounded transition-colors hover:text-white hover:bg-red-500/80 ${
              theme === 'dark' ? 'text-[#777]' : 'text-slate-300'
            }`}
            title="Usuń klocek projektu"
            aria-label="Usuń klocek projektu"
          >
            <CloseIcon />
          </button>
        </div>
      </div>

      {/* Wnętrze Portalu: Podgląd połączonych notatek */}
      <div
        className="flex-1 w-full rounded-xl border p-2.5 flex flex-col justify-between items-center relative min-h-[110px]"
        style={{
          backgroundColor: theme === 'dark' ? '#111111' : 'rgba(241, 245, 249, 0.65)',
          borderColor: theme === 'dark' ? '#202020' : 'rgba(226, 232, 240, 0.8)',
        }}
      >
        {connectedNodes.length > 0 ? (
          <div className="w-full flex flex-col gap-1 overflow-hidden">
            <span className="text-[10px] font-medium uppercase tracking-wider text-[#666] mb-0.5">
              Połączone notatki ({connectedNodes.length}):
            </span>
            {connectedNodes.slice(0, 4).map((cn) => (
              <div
                key={cn.id}
                className="w-full px-2 py-0.5 rounded-md border text-[11px] truncate flex items-center gap-1.5"
                style={{
                  backgroundColor: theme === 'dark' ? '#161616' : 'rgba(255, 255, 255, 0.85)',
                  borderColor: theme === 'dark' ? '#242424' : 'rgba(226, 232, 240, 0.9)',
                  color: theme === 'dark' ? '#cccccc' : '#334155',
                }}
              >
                <span className="text-[#666]">↳</span>
                <span className="truncate">{cn.title || cn.content.slice(0, 24) || 'Notatka'}</span>
              </div>
            ))}
            {connectedNodes.length > 4 && (
              <span className="text-[10px] text-[#666] text-center">
                + {connectedNodes.length - 4} więcej...
              </span>
            )}
            <div className="mt-1 text-[10px] font-medium text-[#777]">
              {connectedNodes.length === 1 ? '1 połączona notatka' : `${connectedNodes.length} połączonych notatek`}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-2">
            <span className="text-xs text-[#777] font-medium">
              Podłącz notatki klawiszem Tab
            </span>
            <span className="text-[10px] text-[#555] mt-0.5">
              aby przenieść je do nowej tablicy
            </span>
          </div>
        )}
      </div>

      {/* Przycisk akcji: Otwórz jako nową tablicę */}
      <button
        data-testid={`open-project-btn-${node.id}`}
        onClick={(e) => {
          e.stopPropagation();
          void handleOpenPortalAsProject(node, connectedNodes);
        }}
        className={`mt-2.5 w-full py-1.5 px-3 rounded-lg font-medium text-xs flex items-center justify-center gap-1.5 border shadow-sm transition-all cursor-pointer ${
          theme === 'dark'
            ? 'bg-[#1c1c1c] hover:bg-[#242424] text-[#eeeeee] border-[#2a2a2a]'
            : 'bg-white hover:bg-slate-50 text-slate-800 border-slate-200 hover:border-slate-300'
        }`}
        title="Tworzy osobną tablicę i przenosi do niej połączone notatki"
      >
        <span>Otwórz jako nową tablicę</span>
        <span className="text-xs font-bold text-[#FFC799]">↗</span>
      </button>
    </div>
  );
}
