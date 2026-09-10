import React, { useState } from 'react';
import type { Krok, TypDecyzji } from '../../supervisor/types';

interface StepInspectorDrawerProps {
  krok: Krok | null;
  stepIndex: number;
  pipelineId: string;
  onClose: () => void;
  onDecisionSubmitted?: () => void;
}

type InspectorTab = 'prompty' | 'pliki' | 'wejscie' | 'wyjscie' | 'logi';

export const StepInspectorDrawer: React.FC<StepInspectorDrawerProps> = ({
  krok,
  stepIndex,
  pipelineId,
  onClose,
  onDecisionSubmitted,
}) => {
  const [activeTab, setActiveTab] = useState<InspectorTab>('prompty');
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState('');

  if (!krok) return null;

  const handleDecision = async (decision: TypDecyzji) => {
    if (!window.cortexBridge?.supervisorSaveDecision) return;
    setSubmitting(true);
    try {
      await window.cortexBridge.supervisorSaveDecision({
        pipelineId,
        stepId: krok.id,
        decision,
        feedback: feedback.trim() || undefined,
        timestamp: new Date().toISOString(),
      });
      onDecisionSubmitted?.();
    } catch (err) {
      console.error('Błąd zapisu decyzji:', err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed right-0 top-12 bottom-0 w-[540px] bg-[#111111]/98 border-l border-white/[0.1] backdrop-blur-2xl z-40 flex flex-col shadow-2xl animate-in slide-in-from-right duration-150">
      {/* Nagłówek panelu technicznego */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.08] bg-[#141414]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono font-bold text-zinc-400">
              KROK #{stepIndex + 1}
            </span>
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/[0.05] text-zinc-300 border border-white/[0.08]">
              {krok.typ === 'ai' ? 'AI GENERATOR' : krok.typ === 'kod' ? 'SKRYPT / KOD' : 'BRAMKA'}
            </span>
            {krok.faza && (
              <span className="text-[10px] font-mono text-zinc-400 bg-white/[0.03] px-1.5 py-0.5 rounded border border-white/[0.06]">
                {krok.faza}
              </span>
            )}
            {krok.status === 'w_toku' && (
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-blue-500/15 text-blue-300 border border-blue-400/30 animate-pulse">
                ● Na żywo
              </span>
            )}
          </div>
          <h2 className="text-sm font-semibold text-zinc-100 line-clamp-1">{krok.nazwa}</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer"
          title="Zamknij inspektor"
        >
          ✕
        </button>
      </div>

      {/* Rola etapu i narzędzie */}
      <div className="px-5 py-3 bg-white/[0.02] border-b border-white/[0.06] text-xs text-zinc-300 leading-relaxed font-sans">
        {krok.opis}
        <div className="mt-2 flex items-center gap-2 text-[11px] font-mono text-zinc-400">
          <span className="text-zinc-500 font-bold">Silnik / Narzędzie:</span>
          <span className="text-zinc-200 bg-white/[0.05] px-2 py-0.5 rounded border border-white/[0.06]">
            {krok.narzedzie || (krok.typ === 'ai' ? 'DeepSeek (4571)' : 'Playwright')}
          </span>
        </div>
      </div>

      {/* Bramka decyzyjna (jeśli wymagana) */}
      {krok.status === 'czeka_na_ciebie' && (
        <div className="m-4 p-3.5 rounded-xl border border-zinc-700 bg-zinc-900/90 backdrop-blur-md">
          <div className="flex items-center gap-2 mb-2 text-zinc-200 text-xs font-semibold font-mono">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            Wymagana decyzja inżynierska (Bramka kontrolna)
          </div>
          <p className="text-xs text-zinc-300 mb-3 leading-relaxed font-sans">
            {krok.decyzja?.pytanie || 'Zweryfikuj parametry wygenerowane w tym etapie i zdecyduj o kontynuacji wykonania.'}
          </p>
          <input
            type="text"
            placeholder="Wprowadź ewentualną korektę lub komentarz..."
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            className="w-full h-8 px-2.5 mb-3 rounded-lg bg-black border border-zinc-800 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500 font-mono"
          />
          <div className="flex items-center gap-2 font-mono">
            <button
              disabled={submitting}
              onClick={() => handleDecision('approve')}
              className="flex-1 h-8 rounded-lg bg-zinc-100 text-zinc-950 hover:bg-white text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              {submitting ? 'Zapisywanie...' : '✓ Zatwierdź'}
            </button>
            <button
              disabled={submitting}
              onClick={() => handleDecision('reject')}
              className="h-8 px-4 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:bg-zinc-800 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
            >
              Odrzuć
            </button>
          </div>
        </div>
      )}

      {/* Zakładki techniczne */}
      <div className="flex border-b border-zinc-800 px-5 gap-4 text-xs font-mono bg-[#141414]">
        <button
          onClick={() => setActiveTab('prompty')}
          className={`py-2.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'prompty'
              ? 'border-zinc-300 text-zinc-100 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-300'
          }`}
        >
          Prompty AI
        </button>
        <button
          onClick={() => setActiveTab('pliki')}
          className={`py-2.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'pliki'
              ? 'border-zinc-300 text-zinc-100 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-300'
          }`}
        >
          Pliki & Kontekst ({krok.plikiWejsciowe?.length ?? 0})
        </button>
        <button
          onClick={() => setActiveTab('wejscie')}
          className={`py-2.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'wejscie'
              ? 'border-zinc-300 text-zinc-100 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-300'
          }`}
        >
          Payload Wejściowy
        </button>
        <button
          onClick={() => setActiveTab('wyjscie')}
          className={`py-2.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'wyjscie'
              ? 'border-zinc-300 text-zinc-100 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-300'
          }`}
        >
          Szkic Oferty / Wynik
        </button>
        <button
          onClick={() => setActiveTab('logi')}
          className={`py-2.5 border-b-2 transition-colors cursor-pointer ${
            activeTab === 'logi'
              ? 'border-zinc-300 text-zinc-100 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-300'
          }`}
        >
          Logi ({krok.logi?.length ?? 0})
        </button>
      </div>

      {/* Zawartość zakładek */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {/* ZAKŁADKA 1: PROMPTY */}
        {activeTab === 'prompty' && (
          <div className="space-y-4">
            <div>
              <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider font-semibold mb-1.5 flex items-center justify-between">
                <span>Instrukcje Systemowe (System Prompt):</span>
                <span className="text-[10px] text-zinc-500 font-normal">Dyrektywy agenta i reguły</span>
              </div>
              <pre className="p-3.5 rounded-xl bg-black border border-zinc-800 text-xs font-mono text-zinc-300 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-72">
                {krok.promptSystem || 'Brak dedykowanego promptu systemowego dla tego kroku (etap oparty na czystym kodzie Python/Playwright).'}
              </pre>
            </div>

            <div>
              <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider font-semibold mb-1.5 flex items-center justify-between">
                <span>Szablon Zapytania (User Prompt):</span>
                <span className="text-[10px] text-zinc-500 font-normal">Wstrzyknięte dane zlecenia</span>
              </div>
              <pre className="p-3.5 rounded-xl bg-black border border-zinc-800 text-xs font-mono text-zinc-300 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-60">
                {krok.promptUser || 'Brak szablonu user prompt.'}
              </pre>
            </div>
          </div>
        )}

        {/* ZAKŁADKA 2: PLIKI & KONTEKST */}
        {activeTab === 'pliki' && (
          <div className="space-y-3">
            <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider font-semibold mb-1">
              Pliki z dysku wstrzykiwane do kontekstu tego etapu:
            </div>
            {krok.plikiWejsciowe && krok.plikiWejsciowe.length > 0 ? (
              <div className="space-y-2">
                {krok.plikiWejsciowe.map((file, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-black border border-zinc-800 space-y-1">
                    <div className="flex items-center justify-between font-mono text-xs">
                      <span className="text-zinc-200 font-semibold">{file}</span>
                      <span className="text-[10px] text-zinc-500 px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800">
                        {file.endsWith('.md') ? 'BAZA WIEDZY / PROMPT' : file.endsWith('.json') ? 'STAN / PAYLOAD' : 'KOD PYTHON'}
                      </span>
                    </div>
                    <div className="text-[11px] text-zinc-400 font-sans">
                      {file.includes('mechanika_wyceniania')
                        ? 'Podręcznik algorytmu wyceniania: stawka bazowa 90 zł/h, bufory ryzyka, tabela rynkowa małych zleceń, kalkulacja modułów.'
                        : file.includes('jak_pisac_oferty')
                        ? 'Standard redakcji oferty: struktura 4 punktów, brak lania wody, styl ekspercki, osadzenie kwoty w sekcji WYCENA.'
                        : file.includes('selekcja_zlecen')
                        ? 'Kryteria selekcji ogłoszeń: minimum 500 PLN, zakaz adminki/malware, obsługa edge case (Blueprint dla dużych SaaS).'
                        : file.includes('lore')
                        ? 'Kontekst profilu wykonawcy: Maks (Senior Dev), Ksawier (Biznes & Kontakt), stack e-commerce, AI i integracje.'
                        : file.includes('cookies')
                        ? 'Ciasteczka sesyjne profilu Useme do autoryzacji w przeglądarce Chromium.'
                        : 'Plik operacyjny obiegu danych.'}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-zinc-500 italic p-4 bg-black/40 rounded-xl border border-zinc-800/60">
                Ten krok nie wymaga dodatkowych plików kontekstowych z dysku.
              </div>
            )}
          </div>
        )}

        {/* ZAKŁADKA 3: WEJŚCIE / PAYLOAD */}
        {activeTab === 'wejscie' && (
          <div>
            <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider font-semibold mb-1.5 flex items-center justify-between">
              <span>Struktura danych wejściowych (Input Payload):</span>
              <span className="text-[10px] text-zinc-500">Format JSON</span>
            </div>
            <pre className="p-3.5 rounded-xl bg-black border border-zinc-800 text-xs font-mono text-zinc-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {krok.wejscie || 'Brak zarejestrowanego payloadu wejściowego.'}
            </pre>
          </div>
        )}

        {/* ZAKŁADKA 4: WYJŚCIE & SZKIC OFERTY */}
        {activeTab === 'wyjscie' && (
          <div className="space-y-4">
            <div>
              <div className="text-[11px] font-mono text-zinc-300 uppercase tracking-wider font-semibold mb-1.5 flex items-center justify-between">
                <span>Wygenerowane Wyjście / Szkic Propozycji:</span>
                <span className="text-[10px] text-zinc-500">Format wyjściowy</span>
              </div>
              <pre className="p-3.5 rounded-xl bg-black border border-zinc-800 text-xs font-mono text-zinc-200 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {krok.wyjscie || krok.wynik || krok.odpowiedz || 'Ten krok nie wygenerował jeszcze wyniku.'}
              </pre>
            </div>

            {krok.reasoning && (
              <div>
                <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider font-semibold mb-1.5">
                  Łańcuch myśli modelu (Reasoning i kalkulacja):
                </div>
                <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs text-zinc-300 leading-relaxed font-sans whitespace-pre-wrap">
                  {krok.reasoning}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ZAKŁADKA 5: LOGI */}
        {activeTab === 'logi' && (
          <div>
            <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider font-semibold mb-1.5">
              Strumień konsoli wykonania:
            </div>
            <div className="p-3 rounded-xl bg-black/80 border border-white/[0.06] text-xs font-mono text-zinc-400 space-y-1 max-h-96 overflow-y-auto">
              {krok.logi && krok.logi.length > 0 ? (
                krok.logi.map((line, idx) => (
                  <div key={idx} className="flex gap-2">
                    <span className="text-zinc-600 select-none">{String(idx + 1).padStart(2, '0')}</span>
                    <span className="text-zinc-300">{line}</span>
                  </div>
                ))
              ) : (
                <div className="text-zinc-600 italic">Brak zarejestrowanych wpisów konsoli dla tego kroku.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
