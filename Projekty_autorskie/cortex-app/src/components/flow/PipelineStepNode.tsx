import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { Krok } from '../../supervisor/types';

export interface PipelineStepNodeData {
  krok: Krok;
  index: number;
  total: number;
  isSelected?: boolean;
  onSelect?: (index: number) => void;
}

const STATUS_CONFIG: Record<
  string,
  { border: string; dot: string; text: string; label: string; bg: string }
> = {
  zrobione: {
    border: 'border-emerald-500/40',
    dot: 'bg-emerald-400',
    text: 'text-emerald-300',
    label: 'Zrobione',
    bg: 'bg-emerald-500/10',
  },
  w_toku: {
    border: 'border-blue-400/50',
    dot: 'bg-blue-400',
    text: 'text-blue-300',
    label: 'Wykonywanie...',
    bg: 'bg-blue-500/10',
  },
  czeka_na_ciebie: {
    border: 'border-amber-400/50',
    dot: 'bg-amber-400',
    text: 'text-amber-300',
    label: 'Czeka na decyzję',
    bg: 'bg-amber-500/10',
  },
  blad: {
    border: 'border-red-400/50',
    dot: 'bg-red-400',
    text: 'text-red-300',
    label: 'Błąd',
    bg: 'bg-red-500/10',
  },
  w_kolejce: {
    border: 'border-zinc-700',
    dot: 'bg-zinc-600',
    text: 'text-zinc-500',
    label: 'W kolejce',
    bg: 'bg-zinc-800/40',
  },
};

const TYPE_LABELS: Record<string, string> = {
  ai: 'AI',
  kod: 'AUTOMATYCZNIE',
  warunek: 'DECYZJA',
};

export const PipelineStepNode: React.FC<{ data: PipelineStepNodeData }> = ({ data }) => {
  if (!data || !data.krok) {
    return null;
  }

  const { krok, index = 0, total = 1, isSelected = false, onSelect } = data;
  const statusCfg = STATUS_CONFIG[krok.status] ?? STATUS_CONFIG.w_kolejce;
  const typeLabel = TYPE_LABELS[krok.typ] ?? 'KROK';
  const isAi = krok.typ === 'ai';

  return (
    <div
      data-testid={`step-node-${krok.id}`}
      onClick={() => onSelect?.(index)}
      className={`relative w-[420px] rounded-xl border p-5 transition-all duration-150 cursor-pointer select-none bg-[#151515] ${
        isSelected
          ? 'border-zinc-300 ring-1 ring-zinc-300/30 bg-[#181818]'
          : `${statusCfg.border} hover:border-zinc-500`
      }`}
    >
      {/* Port wejściowy */}
      <Handle
        type="target"
        position={Position.Left}
        className={`!w-2.5 !h-2.5 !bg-zinc-600 !border !border-zinc-900 hover:!bg-zinc-300 !-left-[6px] ${
          index === 0 ? '!opacity-0 pointer-events-none' : '!opacity-100'
        }`}
      />

      {/* Nagłówek: numer + typ */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-mono font-bold text-zinc-400">
          {String(index + 1).padStart(2, '0')}
        </span>
        <span className="text-[11px] font-mono font-semibold tracking-wider px-2 py-0.5 rounded bg-zinc-800 text-zinc-200 border border-zinc-700/60">
          {typeLabel}
        </span>
        {krok.faza && (
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
            {krok.faza}
          </span>
        )}
      </div>

      {/* Nazwa kroku — duża i czytelna */}
      <h3 className="font-semibold text-lg text-zinc-50 leading-snug mb-2">
        {krok.nazwa}
      </h3>

      {/* Ludzkie wyjaśnienie: co robi ten krok */}
      {krok.opis && (
        <p className="text-sm text-zinc-300 leading-relaxed mb-4 font-sans">
          {krok.opis}
        </p>
      )}

      {/* Dla kroków AI: podgląd wyniku + wejście w szczegóły */}
      {isAi && (
        <div className="mt-1">
          {krok.wyjscie && (
            <div className="bg-black/50 rounded-lg p-3 border border-zinc-800 mb-3">
              <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-semibold mb-1.5">
                Wynik
              </div>
              <div className="text-sm text-zinc-200 line-clamp-3 leading-snug whitespace-pre-wrap">
                {krok.wyjscie}
              </div>
            </div>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect?.(index);
            }}
            className="w-full h-9 rounded-lg bg-white/[0.06] border border-zinc-700 text-zinc-100 text-sm font-medium hover:bg-white/[0.1] hover:border-zinc-500 transition-colors cursor-pointer"
          >
            Szczegóły AI: prompty, pliki i logi →
          </button>
        </div>
      )}

      {/* Belka dolna: status */}
      <div className="flex items-center justify-between pt-3 mt-1 border-t border-zinc-800/80">
        <span className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-md text-sm font-medium ${statusCfg.bg}`}>
          <span className={`w-2 h-2 rounded-full ${statusCfg.dot}`} />
          <span className={statusCfg.text}>{statusCfg.label}</span>
        </span>
        {isAi && (
          <span className="text-xs text-zinc-500 font-mono">
            {krok.narzedzie || 'AI'}
          </span>
        )}
      </div>

      {/* Port wyjściowy */}
      <Handle
        type="source"
        position={Position.Right}
        className={`!w-2.5 !h-2.5 !bg-zinc-600 !border !border-zinc-900 hover:!bg-zinc-300 !-right-[6px] ${
          index >= total - 1 ? '!opacity-0 pointer-events-none' : '!opacity-100'
        }`}
      />
    </div>
  );
};