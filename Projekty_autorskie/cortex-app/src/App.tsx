import { useState, useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import { NotesCanvas } from './components/NotesCanvas';
import { AiChatSidebar } from './components/AiChatSidebar';
import { KosmosView } from './components/KosmosView';
import { FlowView } from './components/flow/FlowView';

type Widok = 'notatki' | 'kosmos' | 'flow';

export function App() {
  const [widok, setWidok] = useState<Widok>('notatki');
  const [isAiChatOpen, setIsAiChatOpen] = useState(false);

  const pointerStartRef = useRef<{ x: number; y: number } | null>(null);

  // Kliknięcie w canvas zamyka czat, ale przeciąganie (pan) już nie.
  useEffect(() => {
    if (!isAiChatOpen) return;

    const onPointerDown = (e: PointerEvent) => {
      pointerStartRef.current = { x: e.clientX, y: e.clientY };
    };

    const onPointerUp = (e: PointerEvent) => {
      const start = pointerStartRef.current;
      pointerStartRef.current = null;
      if (!start) return;

      const dist = Math.hypot(e.clientX - start.x, e.clientY - start.y);
      if (dist > 5) return; // to było przeciąganie, nie klik

      // Ignoruj kliknięcia wewnątrz panelu czatu
      const target = e.target;
      if (target instanceof Element && target.closest('[aria-label="Cortex AI Asystent"]')) {
        return;
      }

      setIsAiChatOpen(false);
    };

    document.addEventListener('pointerdown', onPointerDown, true);
    document.addEventListener('pointerup', onPointerUp, true);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true);
      document.removeEventListener('pointerup', onPointerUp, true);
    };
  }, [isAiChatOpen]);

  if (widok === 'flow') {
    return <FlowView onBack={() => setWidok('notatki')} />;
  }

  if (widok === 'kosmos') {
    return <KosmosView onBack={() => setWidok('notatki')} />;
  }

  return (
    <div className="relative">
      {/* Pasek tytułowy (okno bez ramki) — przeciąganie + przyciski okna */}
      <div className="fixed top-0 left-0 right-0 z-[100] h-9 flex select-none pointer-events-none">
        {/* Lewa strefa przeciągania (mały narożnik, nie przeszkadza elementom canvasa) */}
        <div className="w-8 h-full pointer-events-auto" style={{ WebkitAppRegion: 'drag' } as CSSProperties} />
        {/* Środek pusty — przepuszcza kliknięcia do headera canvasa */}
        <div className="flex-1 h-full" />
        {/* Prawa strefa: przyciski okna */}
        <div className="flex items-center gap-1 pr-1 pointer-events-auto" style={{ WebkitAppRegion: 'no-drag' } as CSSProperties}>
          <button
            onClick={() => window.cortexBridge?.winMinimize()}
            aria-label="Minimalizuj"
            className="w-10 h-8 flex items-center justify-center text-[#aaa] hover:bg-[#222] hover:text-white rounded cursor-pointer text-xs transition-colors"
          >
            ─
          </button>
          <button
            onClick={() => window.cortexBridge?.winMaximize()}
            aria-label="Maksymalizuj"
            className="w-10 h-8 flex items-center justify-center text-[#aaa] hover:bg-[#222] hover:text-white rounded cursor-pointer text-xs transition-colors"
          >
            □
          </button>
          <button
            onClick={() => window.cortexBridge?.winClose()}
            aria-label="Zamknij"
            className="w-10 h-8 flex items-center justify-center text-[#aaa] hover:bg-red-600 hover:text-white rounded cursor-pointer text-xs transition-colors"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="fixed right-4 top-11 z-30 flex items-center gap-2">
        <button
          onClick={() => setWidok('kosmos')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium backdrop-blur-2xl transition-all duration-150 cursor-pointer shadow-sm hover:border-[#8ab4f8] hover:text-[#8ab4f8]"
          style={{
            backgroundColor: 'rgba(20, 20, 20, 0.95)',
            borderColor: '#262626',
            color: '#dddddd',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
          }}
        >
          <span>Kosmos</span>
          <span className="text-[#8ab4f8]">✦</span>
        </button>
        <button
          onClick={() => setWidok('flow')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium backdrop-blur-2xl transition-all duration-150 cursor-pointer shadow-sm hover:border-[#60a5fa] hover:text-[#60a5fa]"
          style={{
            backgroundColor: 'rgba(20, 20, 20, 0.95)',
            borderColor: '#262626',
            color: '#dddddd',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
          }}
        >
          <span>Przepływ</span>
          <span className="text-[#60a5fa]">⚡</span>
        </button>
      </div>

      {/* Niewidzialny hitbox na całej wysokości prawej krawędzi */}
      {!isAiChatOpen && (
        <button
          onClick={() => setIsAiChatOpen(true)}
          aria-label="Otwórz asystenta AI"
          title="Otwórz czat AI"
          className="fixed right-0 top-0 bottom-0 z-[60] w-4 flex items-center justify-end cursor-pointer bg-transparent border-none hover:bg-[rgba(255,199,153,0.08)] transition-colors duration-150"
        >
          <span className="w-1.5 h-14 rounded-l-md bg-[rgba(255,199,153,0.5)] flex items-center justify-center text-[#FFC799] text-sm shadow-[0_0_10px_rgba(255,199,153,0.4)] hover:bg-[rgba(255,199,153,0.85)]">
            ✦
          </span>
        </button>
      )}

      <NotesCanvas />

      <AiChatSidebar isOpen={isAiChatOpen} onClose={() => setIsAiChatOpen(false)} />
    </div>
  );
}
