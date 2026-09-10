import { CloseIcon } from '../icons/CanvasIcons';

interface HelpModalProps {
  showHelp: boolean;
  onClose: () => void;
  theme: 'light' | 'dark';
}

export function HelpModal({ showHelp, onClose, theme }: HelpModalProps) {
  if (!showHelp) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        data-testid="help-modal"
        className="w-full max-w-lg rounded-2xl border shadow-2xl overflow-hidden"
        style={{
          backgroundColor: theme === 'dark' ? '#141414' : '#ffffff',
          borderColor: theme === 'dark' ? '#262626' : '#e2e8f0',
          color: theme === 'dark' ? '#eeeeee' : '#1e293b',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Nagłówek modalu */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{
            backgroundColor: theme === 'dark' ? '#111111' : 'rgba(248, 250, 252, 0.8)',
            borderColor: theme === 'dark' ? '#222222' : '#f1f5f9',
          }}
        >
          <div className="flex items-center gap-2">
            <h2 className={`text-sm font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Skróty klawiszowe i sterowanie</h2>
          </div>
          <button
            tabIndex={-1}
            onClick={onClose}
            className={`w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${
              theme === 'dark'
                ? 'text-[#777] hover:text-white hover:bg-[#202020]'
                : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
            }`}
            title="Zamknij (Esc)"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Tabela skrótów */}
        <div className="p-6 space-y-4 text-xs max-h-[70vh] overflow-y-auto">
          <div className="space-y-2">
            <h3 className={`text-[11px] font-semibold uppercase tracking-wider ${theme === 'dark' ? 'text-[#777]' : 'text-slate-400'}`}>Edycja i tworzenie</h3>
            <div className="grid grid-cols-2 gap-2">
              <div
                className="flex items-center justify-between p-2 rounded-lg border"
                style={{
                  backgroundColor: theme === 'dark' ? '#101010' : '#f8fafc',
                  borderColor: theme === 'dark' ? '#222222' : '#f1f5f9',
                }}
              >
                <span>Nowa notatka</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px]"
                  style={{
                    backgroundColor: theme === 'dark' ? '#1c1c1c' : '#ffffff',
                    borderColor: theme === 'dark' ? '#333333' : '#cbd5e1',
                    color: theme === 'dark' ? '#eeeeee' : '#334155',
                  }}
                >
                  Dwuklik
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border"
                style={{
                  backgroundColor: theme === 'dark' ? '#101010' : '#f8fafc',
                  borderColor: theme === 'dark' ? '#222222' : '#f1f5f9',
                }}
              >
                <span>Klocek projektu</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px]"
                  style={{
                    backgroundColor: theme === 'dark' ? '#1c1c1c' : '#ffffff',
                    borderColor: theme === 'dark' ? '#333333' : '#cbd5e1',
                    color: theme === 'dark' ? '#eeeeee' : '#334155',
                  }}
                >
                  Shift + P
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border"
                style={{
                  backgroundColor: theme === 'dark' ? '#101010' : '#f8fafc',
                  borderColor: theme === 'dark' ? '#222222' : '#f1f5f9',
                }}
              >
                <span>Szybkie połączenie</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px]"
                  style={{
                    backgroundColor: theme === 'dark' ? '#1c1c1c' : '#ffffff',
                    borderColor: theme === 'dark' ? '#333333' : '#cbd5e1',
                    color: theme === 'dark' ? '#eeeeee' : '#334155',
                  }}
                >
                  Tab (w tekście)
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border"
                style={{
                  backgroundColor: theme === 'dark' ? '#101010' : '#f8fafc',
                  borderColor: theme === 'dark' ? '#222222' : '#f1f5f9',
                }}
              >
                <span>Edytuj / Zatwierdź</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px]"
                  style={{
                    backgroundColor: theme === 'dark' ? '#1c1c1c' : '#ffffff',
                    borderColor: theme === 'dark' ? '#333333' : '#cbd5e1',
                    color: theme === 'dark' ? '#eeeeee' : '#334155',
                  }}
                >
                  Enter
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border"
                style={{
                  backgroundColor: theme === 'dark' ? '#101010' : '#f8fafc',
                  borderColor: theme === 'dark' ? '#222222' : '#f1f5f9',
                }}
              >
                <span>Anuluj / Odznacz</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px]"
                  style={{
                    backgroundColor: theme === 'dark' ? '#1c1c1c' : '#ffffff',
                    borderColor: theme === 'dark' ? '#333333' : '#cbd5e1',
                    color: theme === 'dark' ? '#eeeeee' : '#334155',
                  }}
                >
                  Esc
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border bg-[#101010] border-[#222222]"
              >
                <span>Usuń notatkę</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px] bg-[#1c1c1c] border-[#333333] text-[#eeeeee]"
                >
                  Del / Backspace
                </kbd>
              </div>
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[#777]">Nawigacja i sterowanie</h3>
            <div className="grid grid-cols-2 gap-2">
              <div
                className="flex items-center justify-between p-2 rounded-lg border bg-[#101010] border-[#222222]"
              >
                <span>Tryb łączenia linii</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px] bg-[#1c1c1c] border-[#333333] text-[#eeeeee]"
                >
                  Tab / `
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border bg-[#101010] border-[#222222]"
              >
                <span>Przesuwanie widoku</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px] bg-[#1c1c1c] border-[#333333] text-[#eeeeee]"
                >
                  Przeciągnij tło
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border bg-[#101010] border-[#222222]"
              >
                <span>Kopiuj / Wklej</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px] bg-[#1c1c1c] border-[#333333] text-[#eeeeee]"
                >
                  Ctrl+C / Ctrl+V
                </kbd>
              </div>
              <div
                className="flex items-center justify-between p-2 rounded-lg border bg-[#101010] border-[#222222]"
              >
                <span>Płynny Zoom</span>
                <kbd
                  className="px-1.5 py-0.5 rounded border text-[11px] bg-[#1c1c1c] border-[#333333] text-[#FFC799]"
                >
                  Kółko myszy
                </kbd>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
