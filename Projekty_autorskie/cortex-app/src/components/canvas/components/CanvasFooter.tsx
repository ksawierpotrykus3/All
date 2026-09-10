interface CanvasFooterProps {
  isMacroView: boolean;
  activeProjectId: string;
  selectedProjectId?: string | null;
  diveIntoProject: (id: string) => Promise<void> | void;
  togglePortalPlacementMode: () => void;
  placementMode: boolean;
}

export function CanvasFooter({
  isMacroView,
  activeProjectId,
  selectedProjectId,
  diveIntoProject,
  togglePortalPlacementMode,
  placementMode,
}: CanvasFooterProps) {
  return (
    <footer
      className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 flex items-center justify-center gap-4 px-4 py-1.5 rounded-full backdrop-blur-xl border text-xs shadow-sm bg-[rgba(20,20,20,0.95)] border-[#262626] text-[#888888]"
      style={{
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
      }}
    >
      {isMacroView ? (
        <>
          <span className="font-semibold text-white">
            Tablica projektów
          </span>
          <span>Dwuklik — nowy projekt</span>
          <span>Przeciągnij — ułóż projekty</span>
          <button
            data-testid="footer-open-notes-btn"
            onClick={() => void diveIntoProject(selectedProjectId || activeProjectId)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-full font-semibold shadow-sm transition-colors cursor-pointer bg-[#262626] hover:bg-[#333333] text-white border border-[#383838]"
          >
            <span>Otwórz notatki</span>
            <span className="font-bold text-xs text-[#FFC799]">→</span>
          </button>
        </>
      ) : (
        <>
          <span>Dwuklik — nowa notatka</span>
          <span>
            <kbd className="px-1.5 py-0.5 rounded border font-mono text-[10px] font-medium bg-[#181818] border-[#2c2c2c] text-[#cccccc]">
              Tab
            </kbd>{' '}
            — połącz
          </span>
          <button
            onClick={togglePortalPlacementMode}
            data-testid="footer-place-portal-button"
            className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full transition-all cursor-pointer ${
              placementMode
                ? 'bg-[#222222] text-[#FFC799] font-semibold border border-[rgba(255,199,153,0.3)]'
                : 'hover:text-white'
            }`}
            title="Wydziel gałąź notatek do osobnego projektu"
          >
            <span className="font-bold text-xs">+</span>
            <span>Wydziel projekt</span>
          </button>
          <span>
            <kbd className="px-1.5 py-0.5 rounded border font-mono text-[10px] font-medium bg-[#181818] border-[#2c2c2c] text-[#cccccc]">
              Enter
            </kbd>{' '}
            — zatwierdź
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 rounded border font-mono text-[10px] font-medium bg-[#181818] border-[#2c2c2c] text-[#cccccc]">
              Esc
            </kbd>{' '}
            — odznacz
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 rounded border font-mono text-[10px] font-medium bg-[#181818] border-[#2c2c2c] text-[#cccccc]">
              Del
            </kbd>{' '}
            — usuń
          </span>
        </>
      )}
    </footer>
  );
}
