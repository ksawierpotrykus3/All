import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export interface CanvasContextMenuProps {
  x: number;
  y: number;
  type: 'selection' | 'bracket';
  selectedCount?: number;
  bracketName?: string;
  onCreateBracket?: () => void;
  onRenameBracket?: () => void;
  onDeleteBracket?: () => void;
  onPackBracket?: (orientation?: 'horizontal' | 'vertical') => void;
  onClose: () => void;
  theme?: 'light' | 'dark';
}

export function CanvasContextMenu({
  x,
  y,
  type,
  selectedCount = 0,
  bracketName = '',
  onCreateBracket,
  onRenameBracket,
  onDeleteBracket,
  onPackBracket,
  onClose,
  theme = 'dark',
}: CanvasContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('mousedown', handleClickOutside, true);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('mousedown', handleClickOutside, true);
    };
  }, [onClose]);

  if (typeof document === 'undefined') return null;

  const canCreateBracket = selectedCount >= 2;

  // Ograniczenie pozycji menu, aby nie wychodziło poza ekran
  const menuWidth = 240;
  const menuHeight = type === 'bracket' ? 220 : 130;
  const left = Math.min(x, window.innerWidth - menuWidth - 10);
  const top = Math.min(y, window.innerHeight - menuHeight - 10);

  return createPortal(
    <div
      ref={menuRef}
      role="menu"
      aria-label="Menu kontekstowe canvasu"
      className="fixed z-[99999] rounded-xl border border-[#2c2c2c] bg-[#141414] shadow-2xl p-1.5 flex flex-col gap-1 font-mono text-xs select-none animate-in fade-in zoom-in-95 duration-75"
      style={{
        left,
        top,
        width: menuWidth,
        color: theme === 'dark' ? '#e5e7eb' : '#111827',
      }}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      {type === 'selection' && (
        <>
          <div className="px-2.5 py-1 text-[10px] text-neutral-500 border-b border-[#222]">
            OPERACJE NA ZAZNACZENIU ({selectedCount})
          </div>
          <button
            type="button"
            role="menuitem"
            disabled={!canCreateBracket}
            onClick={() => {
              if (onCreateBracket && canCreateBracket) {
                onCreateBracket();
                onClose();
              }
            }}
            className={`w-full text-left px-2.5 py-2 rounded-lg transition-colors flex flex-col gap-0.5 ${
              canCreateBracket
                ? 'hover:bg-[#222] text-[#FFC799] cursor-pointer'
                : 'text-neutral-600 cursor-not-allowed'
            }`}
          >
            <span className="font-semibold text-xs tracking-tight">
              STWORZ KLAMRE SEMANTYCZNA
            </span>
            <span className="text-[10px] text-neutral-500 font-sans">
              {canCreateBracket
                ? 'Dosuń klastry (20px) i zepnij klamrą'
                : 'Wymaga zaznaczenia min. 2 wezlow'}
            </span>
          </button>
        </>
      )}

      {type === 'bracket' && (
        <>
          <div className="px-2.5 py-1 text-[10px] text-neutral-500 border-b border-[#222] truncate">
            KLAMRA: {bracketName || 'OZNACZENIA'}
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              if (onPackBracket) {
                onPackBracket();
                onClose();
              }
            }}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-[#222] text-[#FFC799] font-medium transition-colors cursor-pointer"
          >
            DOSUŃ KLASTRY (20PX)
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              if (onPackBracket) {
                onPackBracket('horizontal');
                onClose();
              }
            }}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-[#222] text-neutral-200 transition-colors cursor-pointer text-[11px]"
          >
            USTAW POZIOMO (I DOSUŃ)
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              if (onPackBracket) {
                onPackBracket('vertical');
                onClose();
              }
            }}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-[#222] text-neutral-200 transition-colors cursor-pointer text-[11px]"
          >
            USTAW PIONOWO (I DOSUŃ)
          </button>
          <div className="my-0.5 border-t border-[#222]" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              if (onRenameBracket) {
                onRenameBracket();
                onClose();
              }
            }}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-[#222] text-neutral-200 transition-colors cursor-pointer text-[11px]"
          >
            ZMIEN NAZWE KLAMRY
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              if (onDeleteBracket) {
                onDeleteBracket();
                onClose();
              }
            }}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-[#2f1a1a] text-rose-400 transition-colors cursor-pointer text-[11px]"
          >
            USUN KLAMRE
          </button>
        </>
      )}
    </div>,
    document.body
  );
}
