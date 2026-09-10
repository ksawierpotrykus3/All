import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  useNodesState,
  useEdgesState,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type { Lancuch, Krok } from '../../supervisor/types';
import { PipelineStepNode } from './PipelineStepNode';
import { StepInspectorDrawer } from './StepInspectorDrawer';

interface FlowViewProps {
  onBack: () => void;
}

const nodeTypes = {
  pipelineStep: PipelineStepNode,
};

const FlowAutoFitter: React.FC<{ triggerKey: string }> = ({ triggerKey }) => {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const timer = setTimeout(() => {
      fitView({ padding: 0.15, duration: 250 });
    }, 60);
    return () => clearTimeout(timer);
  }, [triggerKey, fitView]);
  return null;
};

export const FlowView: React.FC<FlowViewProps> = ({ onBack }) => {
  const [pipelines, setPipelines] = useState<Lancuch[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const [layoutMode, setLayoutMode] = useState<'grid' | 'linear'>('grid');

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);

  // Pobieranie listy pipeline'ów z IPC
  const fetchPipelines = useCallback(async () => {
    if (!window.cortexBridge?.supervisorGetPipelines) return;
    try {
      const list = await window.cortexBridge.supervisorGetPipelines();
      if (Array.isArray(list)) {
        const valid = list.filter((p): p is Lancuch => Boolean(p && p.id));
        setPipelines(valid);
        if (valid.length > 0) {
          setSelectedPipelineId((prev) => {
            if (prev && valid.some((p) => p.id === prev)) return prev;
            return valid[0].id;
          });
        }
      }
    } catch (err) {
      console.error('Błąd pobierania rurociągów:', err);
    }
  }, []);

  // Polling stanu pipeline'u w czasie rzeczywistym
  useEffect(() => {
    fetchPipelines();
    const timer = setInterval(fetchPipelines, 1500);
    return () => clearInterval(timer);
  }, [fetchPipelines]);

  const activePipeline = useMemo(() => {
    return pipelines.find((p) => p.id === selectedPipelineId) ?? pipelines[0] ?? null;
  }, [pipelines, selectedPipelineId]);

  // Generowanie węzłów i krawędzi dla React Flow na podstawie kroków
  useEffect(() => {
    if (!activePipeline || !activePipeline.kroki || activePipeline.kroki.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const kroki = activePipeline.kroki;
    const total = kroki.length;
    const perRow = total <= 4 ? total : Math.ceil(total / 2);

    const flowNodes = kroki.map((krok, idx) => {
      let x = 0;
      let y = 0;
      if (layoutMode === 'linear') {
        x = idx * 520 + 60;
        y = 120;
      } else {
        const row = Math.floor(idx / perRow);
        const col = idx % perRow;
        x = col * 520 + 60;
        y = row * 560 + 80;
      }

      return {
        id: `step-${idx}`,
        type: 'pipelineStep',
        position: { x, y },
        data: {
          krok,
          index: idx,
          total: kroki.length,
          isSelected: selectedStepIndex === idx,
          onSelect: (stepIdx: number) => setSelectedStepIndex(stepIdx),
        },
      };
    });

    const flowEdges = kroki.slice(0, -1).map((krok, idx) => {
      const nextKrok = kroki[idx + 1];
      const isAnimated = krok.status === 'w_toku' || nextKrok?.status === 'w_toku';
      const isDone = krok.status === 'zrobione';
      const isFailed = krok.status === 'blad';

      let edgeColor = '#3f3f46'; // zinc-700
      if (isFailed) edgeColor = '#ef4444';
      else if (isAnimated) edgeColor = '#a1a1aa';
      else if (isDone) edgeColor = '#71717a';

      return {
        id: `edge-${idx}->${idx + 1}`,
        source: `step-${idx}`,
        target: `step-${idx + 1}`,
        type: 'smoothstep',
        animated: isAnimated,
        style: { stroke: edgeColor, strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeColor,
          width: 14,
          height: 14,
        },
      };
    });

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [activePipeline, selectedStepIndex, layoutMode, setNodes, setEdges]);

  // Uruchomienie rurociągu (Trigger)
  const handleTriggerRun = async () => {
    if (!activePipeline || !window.cortexBridge?.supervisorRunChain) return;
    setIsRunning(true);
    setRunMessage('Uruchamianie procesu...');
    try {
      const res = await window.cortexBridge.supervisorRunChain({ pipelineId: activePipeline.id });
      if (res.success) {
        setRunMessage('Proces zakończony pomyślnie.');
      } else {
        setRunMessage(`Błąd: ${res.error || 'Nieznany błąd'}`);
      }
      await fetchPipelines();
    } catch (err) {
      setRunMessage(`Błąd wykonania: ${String(err)}`);
    } finally {
      setIsRunning(false);
      setTimeout(() => setRunMessage(null), 5000);
    }
  };

  const selectedStep: Krok | null =
    activePipeline && selectedStepIndex !== null && activePipeline.kroki[selectedStepIndex]
      ? activePipeline.kroki[selectedStepIndex]
      : null;

  return (
    <div className="fixed inset-0 flex flex-col bg-[#0a0a0a] text-zinc-200 select-none">
      {/* Pasek nawigacyjny */}
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-white/[0.08] bg-[#121212] px-4 z-30">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            <span>←</span>
            <span>Tablica notatek</span>
          </button>
          <div className="h-4 w-px bg-white/[0.08]" />
          <div className="flex items-baseline gap-2">
            <h1 className="text-sm font-semibold tracking-tight text-zinc-100">Przepływ</h1>
            <span className="text-[11px] font-mono text-zinc-500">Inżynieryjny Rurociąg (DAG)</span>
          </div>

          {/* Wybór rurociągu */}
          {pipelines.length > 0 && (
            <select
              value={activePipeline?.id ?? ''}
              onChange={(e) => {
                setSelectedPipelineId(e.target.value);
                setSelectedStepIndex(null);
              }}
              className="h-7 rounded-lg border border-white/10 bg-[#1a1a1a] px-2.5 text-xs text-zinc-200 outline-none hover:border-white/20 transition-colors cursor-pointer"
            >
              {pipelines.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nazwa || p.id}
                </option>
              ))}
            </select>
          )}

          {/* Przełącznik widoku: 2 Rzędy (Czytelny) vs 1 Rząd (Liniowy) */}
          <div className="flex items-center bg-[#181818] p-0.5 rounded-lg border border-white/10 text-xs">
            <button
              onClick={() => setLayoutMode('grid')}
              className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
                layoutMode === 'grid'
                  ? 'bg-white/10 text-zinc-100 shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Układ 2-rzędowy — mieści się na ekranie bez potrzeby oddalania kamery"
            >
              ⊞ 2 Rzędy (Czytelny)
            </button>
            <button
              onClick={() => setLayoutMode('linear')}
              className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
                layoutMode === 'linear'
                  ? 'bg-white/10 text-zinc-100 shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Układ 1-rzędowy — klasyczna pozioma linia"
            >
              ↔ 1 Rząd
            </button>
          </div>
        </div>

        {/* Prawa strona headera: akcje i status */}
        <div className="flex items-center gap-3">
          {runMessage && (
            <span className="text-xs font-mono text-zinc-400 animate-pulse">{runMessage}</span>
          )}

          {activePipeline?.status_ogolny && (
            <span className="text-xs font-mono px-2 py-0.5 rounded-full border border-white/10 bg-white/[0.03] text-zinc-400">
              Stan: {activePipeline.status_ogolny}
            </span>
          )}

          <button
            disabled={isRunning}
            onClick={handleTriggerRun}
            className="flex items-center gap-1.5 h-7 px-3 rounded-lg bg-zinc-100 text-zinc-950 text-xs font-semibold hover:bg-white transition-colors cursor-pointer disabled:opacity-50"
          >
            <span>{isRunning ? 'Wykonywanie...' : '▶ Uruchom przebieg'}</span>
          </button>
        </div>
      </header>

      {/* Obszar roboczy React Flow */}
      <div className="relative flex-1 w-full h-full bg-[#0a0a0a]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => {
            const idx = node.data?.index;
            if (typeof idx === 'number') {
              setSelectedStepIndex(idx);
            }
          }}
          fitView
          colorMode="dark"
        >
          <FlowAutoFitter triggerKey={`${activePipeline?.id}-${layoutMode}-${nodes.length}`} />
          <Background color="#222" gap={24} size={1} />
          <Controls className="!bg-[#141414] !border-[#262626] !text-white rounded-lg shadow-xl" />
          <MiniMap
            nodeColor={(n: any) => {
              const status = n.data?.krok?.status;
              if (status === 'zrobione') return '#10b981';
              if (status === 'w_toku') return '#60a5fa';
              if (status === 'czeka_na_ciebie') return '#f59e0b';
              if (status === 'blad') return '#ef4444';
              return '#52525b';
            }}
            className="!bg-[#141414]/90 !border-[#262626] rounded-lg"
          />
        </ReactFlow>

        {/* Informacja w przypadku braku załadowanych węzłów */}
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-zinc-500 font-mono text-xs gap-2 pointer-events-none">
            <span className="text-2xl opacity-40">⏳</span>
            <span>Ładowanie definicji rurociągu...</span>
          </div>
        )}

        {/* Boczny panel inspekcji — dla kroków AI oraz bramek decyzyjnych */}
        {(selectedStep?.typ === 'ai' || selectedStep?.status === 'czeka_na_ciebie') && activePipeline && (
          <StepInspectorDrawer
            krok={selectedStep}
            stepIndex={selectedStepIndex ?? 0}
            pipelineId={activePipeline.id}
            onClose={() => setSelectedStepIndex(null)}
            onDecisionSubmitted={() => fetchPipelines()}
          />
        )}
      </div>
    </div>
  );
};
