import type { MouseEvent as ReactMouseEvent, MutableRefObject } from 'react';
import type { ProjektyNode } from '../../../types';
import {
  NODE_WIDTH,
  NODE_HEIGHT,
  NODE_HEADER_HEIGHT,
  NODE_BODY_HEIGHT,
} from '../constants';
import { CloseIcon } from '../icons/CanvasIcons';
import { bionicText } from '../utils/bionicReading';

interface NoteCardProps {
  node: ProjektyNode;
  isSource: boolean;
  isSelected: boolean;
  isEditing: boolean;
  draggingNodeId: string | null;
  theme: 'light' | 'dark';
  linkingMode: boolean;
  linkingModeRef: MutableRefObject<boolean>;
  cardElRefs: MutableRefObject<Record<string, HTMLDivElement | null>>;
  editingText: string;
  setEditingText: (t: string) => void;
  editingTextRef: MutableRefObject<string>;
  textareaRef: MutableRefObject<HTMLTextAreaElement | null>;
  autoResizeTextarea: (el: HTMLTextAreaElement) => void;
  startEditing: (id: string) => void;
  commitEditing: (targetId?: string, targetText?: string) => Promise<void>;
  cancelEditing: () => void;
  deleteNote: (id: string) => Promise<void>;
  handleNodeLinkingClick: (id: string) => Promise<void>;
  onCardMouseDown: (node: ProjektyNode, e: ReactMouseEvent) => void;
  onHeaderMouseDown: (node: ProjektyNode, e: ReactMouseEvent) => void;
  selectNode: (id: string | null) => void;
  createLinkedNoteNextTo: (sourceIds: string[]) => Promise<void>;
  isClusterView?: boolean;
}

export function NoteCard({
  node,
  isSource,
  isSelected,
  isEditing,
  draggingNodeId,
  theme,
  linkingMode,
  linkingModeRef,
  cardElRefs,
  editingText,
  setEditingText,
  editingTextRef,
  textareaRef,
  autoResizeTextarea,
  startEditing,
  commitEditing,
  cancelEditing,
  deleteNote,
  handleNodeLinkingClick,
  onCardMouseDown,
  onHeaderMouseDown,
  selectNode,
  createLinkedNoteNextTo,
  isClusterView = false,
}: NoteCardProps) {
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
      data-testid={`note-card-${node.id}`}
      data-node-id={node.id}
      data-selected={isSelected}
      data-editing={isEditing}
      data-linking-source={isSource}
      className={`absolute overflow-hidden rounded-2xl border group transition-colors pointer-events-auto outline-none ${
        draggingNodeId === node.id ? '!transition-none' : ''
      }`}
      style={{
        left: node.x,
        top: node.y,
        width: node.width || NODE_WIDTH,
        minHeight: node.height || NODE_HEIGHT,
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
      onDoubleClick={(e) => {
        e.stopPropagation();
        if (!linkingModeRef.current) {
          startEditing(node.id);
        }
      }}
      onMouseDown={(e) => onCardMouseDown(node, e)}
    >
      {/* Pływający przycisk usuwania i wskaźnik źródła */}
      <div className="absolute top-2.5 right-2.5 flex items-center gap-1.5 z-10">
        {linkingMode && isSource && (
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[#FFC799] bg-[rgba(255,199,153,0.1)] px-1.5 py-0.5 rounded border border-[rgba(255,199,153,0.25)]">
            Źródło
          </span>
        )}
        <button
          tabIndex={-1}
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            void deleteNote(node.id);
          }}
          className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 h-5 w-5 flex items-center justify-center rounded text-[#666] hover:text-white hover:bg-red-500/80 transition-all cursor-pointer"
          title="Usuń notatkę"
          aria-label="Usuń notatkę"
        >
          <CloseIcon />
        </button>
      </div>

      {/* Treść notatki */}
      {isEditing ? (
        <textarea
          autoFocus
          ref={(el) => {
            if (el) {
              textareaRef.current = el;
              autoResizeTextarea(el);
            } else {
              textareaRef.current = null;
            }
          }}
          value={editingText}
          onChange={(e) => {
            setEditingText(e.target.value);
            editingTextRef.current = e.target.value;
            autoResizeTextarea(e.target);
          }}
          onBlur={() => void commitEditing()}
          onKeyDown={(e) => {
            if (e.key === 'Tab') {
              e.preventDefault();
              e.stopPropagation();
              const currentNodeId = node.id;
              void commitEditing(currentNodeId, e.currentTarget.value).then(() => {
                selectNode(currentNodeId);
                void createLinkedNoteNextTo([currentNodeId]);
              });
            } else if (e.key === 'Escape') {
              e.preventDefault();
              e.stopPropagation();
              cancelEditing();
            } else if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              e.stopPropagation();
              void commitEditing();
            }
          }}
          className="block w-full resize-none bg-transparent text-sm leading-[1.55] px-4 py-3 outline-none"
          style={{
            minHeight: NODE_BODY_HEIGHT,
            color: theme === 'dark' ? '#f5f5f5' : '#1e293b',
          }}
          placeholder="Zanotuj…"
          data-ignore-drag="true"
        />
      ) : (
        <div
          onClick={(e) => {
            if (!linkingModeRef.current && isSelected) {
              e.stopPropagation();
              startEditing(node.id);
            }
          }}
          className="text-sm whitespace-pre-wrap break-words px-4 py-3 cursor-text leading-[1.55]"
          style={{
            minHeight: NODE_BODY_HEIGHT,
            color: theme === 'dark' ? '#eeeeee' : '#1e293b',
          }}
        >
          {node.content ? bionicText(node.content) : <span className={theme === 'dark' ? 'text-[#555555]' : 'text-slate-400'}>Zanotuj…</span>}
        </div>
      )}
    </div>
  );
}
