import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { Projekt, ProjektyNode, ProjektyEdge } from '../types';
import type { ChatMessage, ContextBlock, ChatSession } from '../shared/types/chat';
import { computeConnectedComponents } from './canvas/utils/clusterGeometry';

interface AiChatSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

// Projekt wraz z wyliczonymi klastrami — dane trybu ręcznego (niezależne od kropki).
interface LoadedProject {
  project: Projekt;
  nodes: ProjektyNode[];
  edges: ProjektyEdge[];
  clusters: { key: string; title: string; nodeIds: string[] }[];
}

const MIN_SIDEBAR_WIDTH = 380;
const DEFAULT_SIDEBAR_WIDTH = 660;

// Proxy DeepSeek — port domyślny dla Cortex
const PROXY_URL = import.meta.env.VITE_PROXY_URL || 'http://localhost:4570';
const CHAT_ENDPOINT = `${PROXY_URL}/v1/chat/completions`;

// Timeout — odporność na „mielenie w nieskończoność”
const REQUEST_TIMEOUT_MS = 120_000;

// Maksymalna liczba wiadomości historii wysyłanych do modelu (ogranicza wybuch tokenów).
const MAX_HISTORY_MESSAGES = 20;

// Klucze storage dla stanu UI (live tracking, konfiguracja, szerokość).
// Sesje czatu są trzymane w StorageEngine (main process) — patrz chatSaveSession/chatGetSessions.
const LIVE_ENABLED_KEY = 'cortex_live_tracking_enabled';
const LIVE_SNAPSHOT_KEY = 'cortex_live_tracking_snapshot';

function createSession(name = 'Nowa rozmowa'): ChatSession {
  const now = Date.now();
  return {
    id: `s-${now}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    messages: [],
    context: [],
    createdAt: now,
    updatedAt: now,
  };
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (sameDay) return time;
  return `${d.toLocaleDateString([], { day: '2-digit', month: '2-digit' })} ${time}`;
}

function sessionPreview(s: ChatSession): string {
  if (!s.messages.length) return 'Nowa rozmowa';
  const last = s.messages[s.messages.length - 1];
  const who = last.sender === 'user' ? 'Ty: ' : 'AI: ';
  return who + last.text.slice(0, 60).replace(/\n/g, ' ');
}

// Lekki renderer Markdown (bez zewnętrznych zależności). Obsługuje:
// pogrubienie, kursywę, kod inline, bloki kodu (```), nagłówki (###), listy
// numerowane i punktowane, linki oraz zwykłe akapity. Treść NIE jest HTML —
// budujemy ReactNode, więc nie ma ryzyka XSS z contentu modelu.
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderInline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  // Najpierw kod inline `...`
  const parts = s.split(/(`[^`]+`)/g);
  parts.forEach((part, i) => {
    if (!part) return;
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
      out.push(
        <code key={i} className="px-1 py-0.5 rounded bg-[#0d0d0d] border border-[#2a2a2a] text-[#FFC799] text-[0.85em] font-mono">
          {part.slice(1, -1)}
        </code>,
      );
      return;
    }
    // W obrębie zwykłego fragmentu: pogrubienie **...** i kursywa *...*
    const sub = part.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    sub.forEach((p, j) => {
      if (!p) return;
      if (p.startsWith('**') && p.endsWith('**') && p.length > 3) {
        out.push(<strong key={`${i}-${j}`}>{p.slice(2, -2)}</strong>);
      } else if (p.startsWith('*') && p.endsWith('*') && p.length > 2) {
        out.push(<em key={`${i}-${j}`}>{p.slice(1, -1)}</em>);
      } else {
        // Link [tekst](url)
        const linkParts = p.split(/(\[[^\]]+\]\([^)]+\))/g);
        linkParts.forEach((lp, k) => {
          if (!lp) return;
          const m = lp.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
          if (m) {
            out.push(
              <a key={`${i}-${j}-${k}`} href={m[2]} target="_blank" rel="noreferrer" className="text-[#FFC799] underline underline-offset-2 hover:text-[#ffd6b3]">
                {m[1]}
              </a>,
            );
          } else {
            out.push(<span key={`${i}-${j}-${k}`}>{escapeHtml(lp)}</span>);
          }
        });
      }
    });
  });
  return out;
}

function renderMarkdown(text: string): ReactNode {
  if (!text) return null;
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Blok kodu ``` ... ```
    if (line.trim().startsWith('```')) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // pomiń zamykające ```
      blocks.push(
        <pre key={key++} className="my-2 p-3 rounded-lg bg-[#0d0d0d] border border-[#2a2a2a] overflow-x-auto text-[12px] leading-relaxed font-mono text-[#ddd] whitespace-pre">
          {codeLines.join('\n')}
        </pre>,
      );
      continue;
    }

    if (line.trim() === '') {
      i++;
      continue;
    }

    // Nagłówek ### / ## / #
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      const level = h[1].length;
      const content = h[2];
      if (level <= 3) {
        blocks.push(
          <div key={key++} className={`font-semibold text-white ${level === 1 ? 'text-base' : level === 2 ? 'text-sm' : 'text-[13px]'} mt-3 mb-1 first:mt-0`}>
            {renderInline(content)}
          </div>,
        );
      } else {
        blocks.push(<div key={key++} className="mt-2 mb-1 text-[13px] font-semibold text-[#ccc]">{renderInline(content)}</div>);
      }
      i++;
      continue;
    }

    // Lista punktowana - ... lub * ...
    if (/^\s*[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(<li key={i}>{renderInline(lines[i].replace(/^\s*[-*]\s+/, ''))}</li>);
        i++;
      }
      blocks.push(<ul key={key++} className="my-1.5 pl-5 list-disc space-y-0.5 marker:text-[#FFC799]">{items}</ul>);
      continue;
    }

    // Lista numerowana 1. ...
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(<li key={i}>{renderInline(lines[i].replace(/^\s*\d+[.)]\s+/, ''))}</li>);
        i++;
      }
      blocks.push(<ol key={key++} className="my-1.5 pl-5 list-decimal space-y-0.5 marker:text-[#FFC799]">{items}</ol>);
      continue;
    }

    // Tabela markdown (| a | b |)
    if (line.trim().startsWith('|') && i + 1 < lines.length && lines[i + 1].trim().match(/^\|[\s\-:|]+\|$/)) {
      const headerRow = line.trim().split('|').filter((c, idx, arr) => !(idx === 0 && arr.length > 1 && c === '')).map((c) => c.trim());
      const rows: string[][] = [];
      i += 2; // pomiń nagłówek i separator
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(lines[i].trim().split('|').filter((c, idx, arr) => !(idx === 0 && arr.length > 1 && c === '')).map((c) => c.trim()));
        i++;
      }
      blocks.push(
        <div key={key++} className="my-2 overflow-x-auto rounded-lg border border-[#2a2a2a]">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-[#1a1a1a]">
                {headerRow.map((c, ci) => (
                  <th key={ci} className="border border-[#2a2a2a] px-2 py-1.5 text-left text-[#FFC799] font-semibold">{renderInline(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="odd:bg-[#161616]">
                  {r.map((c, ci) => (
                    <td key={ci} className="border border-[#242424] px-2 py-1.5 text-[#ddd]">{renderInline(c)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // Zwykły akapit — łącz kolejne niepuste linie, które nie rozpoczynają bloku
    const paragraph: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].trim().startsWith('```') &&
      !/^(#{1,6})\s+/.test(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+[.)]\s+/.test(lines[i]) &&
      !(lines[i].trim().startsWith('|') && i + 1 < lines.length && lines[i + 1].trim().match(/^\|[\s\-:|]+\|$/))
    ) {
      paragraph.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={key++} className="my-1.5 leading-relaxed whitespace-pre-wrap">
        {renderInline(paragraph.join('\n'))}
      </p>,
    );
  }

  return <>{blocks}</>;
}

// Konfiguracja tego, co ma trafić do AI po naciśnięciu kropki.
// Sekcje można włączać/wyłączać, a ponadto wybrać konkretne projekty i klastry.
interface ContextConfig {
  view: boolean;          // tryb, projekt, ścieżka
  visible: boolean;       // lista obiektów (nazwy)
  content: boolean;       // pełna treść notatek
  edges: boolean;         // połączenia między notatkami
  macroEdges: boolean;    // połączenia między projektami
  brackets: boolean;      // klamry
  selected: boolean;      // zaznaczone
  projectIds: string[];   // puste = wszystkie projekty
  clusterIds: string[];   // puste = wszystkie klastry
}

const DEFAULT_CONTEXT_CONFIG: ContextConfig = {
  view: true,
  visible: true,
  content: true,
  edges: true,
  macroEdges: true,
  brackets: true,
  selected: true,
  projectIds: [],
  clusterIds: [],
};

const CONTEXT_CONFIG_KEY = 'cortex_ai_context_config';

function loadContextConfig(): ContextConfig {
  try {
    const raw = localStorage.getItem(CONTEXT_CONFIG_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...DEFAULT_CONTEXT_CONFIG, ...parsed };
    }
  } catch {
    // Ignoruj
  }
  return { ...DEFAULT_CONTEXT_CONFIG };
}

function persistContextConfig(config: ContextConfig): void {
  try {
    localStorage.setItem(CONTEXT_CONFIG_KEY, JSON.stringify(config));
  } catch {
    // Ignoruj
  }
}

interface LiveSnapshot {
  view?: {
    mode?: string;
    projectId?: string;
    projectName?: string | null;
    breadcrumb?: { id: string; title?: string }[];
  };
  titles?: Record<string, string>;
  visible?: Record<string, unknown>[];
  memory?: Record<string, unknown>[];
  edges?: Record<string, unknown>[];
  macroEdges?: Record<string, unknown>[];
  macroClusterLinks?: Record<string, unknown>[];
  brackets?: Record<string, unknown>[];
  selectedIds?: string[];
  allProjects?: { id: string; name: string; notes_count: number }[];
  allClusters?: Record<string, unknown>[];
}

// Odczytuje surowy snapshot widoku (przycisk „kropka” — Live Tracking).
function readLiveSnapshot(): LiveSnapshot | null {
  try {
    if (localStorage.getItem(LIVE_ENABLED_KEY) !== '1') return null;
    const raw = localStorage.getItem(LIVE_SNAPSHOT_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as LiveSnapshot;
  } catch {
    return null;
  }
}

function str(v: unknown): string {
  if (v === null || v === undefined) return '';
  return String(v);
}

// Neutralizuje sekwencje łamiące strukturę promptu (delimitery `===`), żeby treść
// notatki użytkownika nie mogła podszyć się pod nagłówki kontekstu systemowego.
function neutralizePromptInjection(v: unknown): string {
  return str(v).replace(/===/g, '[==]');
}

function formatNode(n: Record<string, unknown>): string {
  const parts: string[] = [];
  const type = str(n.node_type) || 'notatka';
  const title = str(n.title) || str(n.id);
  parts.push(`- [${type}] ${title}${n.status ? ` (status: ${str(n.status)})` : ''}`);
  if (n.label) parts.push(`  etykieta: ${neutralizePromptInjection(n.label)}`);
  if (n.description) parts.push(`  opis: ${neutralizePromptInjection(n.description)}`);
  if (n.content) parts.push(`  treść: ${neutralizePromptInjection(n.content)}`);
  return parts.join('\n');
}

function buildCleanViewContext(s: LiveSnapshot, config: ContextConfig): string {
  if (!s) return '';
  const lines: string[] = [];

  const titles = s.titles ?? {};
  const label = (id: unknown) => titles[String(id)] || str(id);

  const projectFilter = config.projectIds.length
    ? (id: unknown) => config.projectIds.includes(String(id))
    : () => true;
  const clusterFilter = config.clusterIds.length
    ? (id: unknown) => config.clusterIds.includes(String(id))
    : () => true;

  if (config.view && s.view) {
    const view = s.view;
    const modeLabel: Record<string, string> = {
      projects: 'projekty',
      clusters: 'klastry',
      board: 'tablica',
    };
    lines.push('=== WIDOK ===');
    if (view.mode) lines.push(`tryb: ${modeLabel[view.mode] || view.mode}`);
    if (view.projectName) lines.push(`projekt: ${view.projectName}`);
    if (view.breadcrumb?.length) {
      lines.push(`ścieżka: ${view.breadcrumb.map((b) => b.title || b.id).join(' > ')}`);
    }
    lines.push('');
  }

  if (config.visible && s.visible?.length) {
    const filtered = s.visible.filter((v) => {
      if (!v) return false;
      if (v.type === 'project') return projectFilter(v.id);
      if (v.type === 'cluster') return clusterFilter(v.id);
      return true;
    });
    if (filtered.length) {
      lines.push('=== OBIEKTY WIDOCZNE ===');
      for (const v of filtered) {
        if (v.type === 'project') {
          lines.push(`- [projekt] ${str(v.name) || label(v.id)} (notatek: ${v.notes_count ?? 0})`);
        } else if (v.type === 'cluster') {
          lines.push(`- [klaster] ${str(v.title) || label(v.id)} (${v.nodeCount ?? 0} notatek)`);
        } else {
          lines.push(`- [notatka] ${str(v.title) || label(v.id)}`);
        }
      }
      lines.push('');
    }
  }

  if (config.content && s.memory?.length) {
    const filtered = s.memory.filter((m) => {
      if (!m) return false;
      if (m.name && m.notes_count !== undefined) return projectFilter(m.id);
      if (Array.isArray(m.nodes)) return clusterFilter(m.id);
      return true;
    });
    if (filtered.length) {
      lines.push('=== TREŚĆ ===');
      for (const m of filtered) {
        const nodes = m.nodes;
        if (Array.isArray(nodes)) {
          const header = str(m.title) || str(m.name) || label(m.id);
          lines.push(`## ${header}`);
          for (const n of nodes) {
            if (n) lines.push(formatNode(n as Record<string, unknown>));
          }
          lines.push('');
        } else if (m.name && m.notes_count !== undefined) {
          lines.push(`## ${str(m.name)} (projekt, notatek: ${m.notes_count})`);
          lines.push('');
        } else {
          lines.push(formatNode(m as Record<string, unknown>));
          lines.push('');
        }
      }
    }
  }

  if (config.edges && s.edges?.length) {
    lines.push('=== POŁĄCZENIA ===');
    for (const e of s.edges) {
      if (!e) continue;
      const rel = e.relation_type ? ` [${str(e.relation_type)}]` : '';
      const lbl = e.label ? ` (${str(e.label)})` : '';
      const arrow = e.has_arrow === false ? ' <-> ' : ' -> ';
      lines.push(`- "${label(e.source)}"${arrow}"${label(e.target)}"${lbl}${rel}`);
    }
    lines.push('');
  }

  if (config.macroEdges && s.macroEdges?.length) {
    lines.push('=== POŁĄCZENIA PROJEKTÓW ===');
    for (const e of s.macroEdges) {
      if (!e) continue;
      const arrow = e.has_arrow === false ? ' <-> ' : ' -> ';
      lines.push(`- "${label(e.source)}"${arrow}"${label(e.target)}"`);
    }
    lines.push('');
  }

  // Połączenia między klastrami/klamrami z różnych projektów. Dostarczane ZAWSZE,
  // niezależnie od tego, czy obiekty są widoczne — AI ma pełny obraz powiązań.
  if (s.macroClusterLinks?.length) {
    lines.push('=== POŁĄCZENIA KLASTRÓW / KLAMER (MIĘDZY PROJEKTAMI) ===');
    for (const l of s.macroClusterLinks) {
      if (!l) continue;
      const src = str(l.source_label) || label(l.source_key);
      const tgt = str(l.target_label) || label(l.target_key);
      const srcKind = l.source_kind === 'bracket' ? '[klamra]' : l.source_kind === 'project' ? '[projekt]' : '[klaster]';
      const tgtKind = l.target_kind === 'bracket' ? '[klamra]' : l.target_kind === 'project' ? '[projekt]' : '[klaster]';
      const srcProj = label(l.source_project_id);
      const tgtProj = label(l.target_project_id);
      lines.push(`- ${srcKind} "${src}" (projekt: "${srcProj}") -> ${tgtKind} "${tgt}" (projekt: "${tgtProj}")`);
    }
    lines.push('');
  }

  if (config.brackets && s.brackets?.length) {
    lines.push('=== KLAMRY ===');
    for (const b of s.brackets) {
      if (!b) continue;
      const ids = Array.isArray(b.node_ids) ? b.node_ids : [];
      const names = ids.map(label).filter(Boolean).join(', ');
      lines.push(
        `- "${str(b.name) || str(b.id)}" (notatek: ${ids.length})${names ? ` → ${names}` : ''}${b.orientation ? ` [orientacja: ${str(b.orientation)}]` : ''}`,
      );
    }
    lines.push('');
  }

  if (config.selected && s.selectedIds?.length) {
    lines.push('=== ZAZNACZONE ===');
    lines.push(s.selectedIds.map(label).join(', '));
    lines.push('');
  }

  return lines.join('\n');
}

// Wylicza klastry dla wczytanego projektu (spójne składowe + opisy z klastrów).
function computeProjectClusters(
  proj: Projekt,
  nodes: ProjektyNode[],
  edges: ProjektyEdge[],
): { key: string; title: string; nodeIds: string[] }[] {
  const descs = proj.cluster_descriptions || {};
  const components = computeConnectedComponents(nodes, edges, descs);
  return components.map((cluster) => {
    const nodeWithDesc = cluster.find((n) => descs[n.id]?.trim());
    const key = nodeWithDesc?.id || cluster[0]?.id || '';
    const title = (nodeWithDesc && descs[nodeWithDesc.id]?.trim()) || cluster[0]?.title || key;
    return { key, title, nodeIds: cluster.map((n) => n.id) };
  });
}

// Buduje gotowy tekst kontekstu dla wybranych projektów i (opcjonalnie) klastrów.
// Zasada: wybrany projekt bez zaznaczonych klastrów -> wszystkie jego notatki;
// wybrany projekt z zaznaczonymi klastrami -> tylko te klastry.
function buildManualContext(
  loaded: LoadedProject[],
  selectedProjectIds: Set<string>,
  selectedClusters: Record<string, Set<string>>,
): { label: string; text: string } | null {
  const chosen = loaded.filter((l) => selectedProjectIds.has(l.project.id));
  if (!chosen.length) return null;

  const parts: string[] = ['=== KONTEKST WYBRANY RĘCZNIE ==='];
  let clusterCount = 0;

  for (const lp of chosen) {
    const projName = lp.project.name || lp.project.id;
    const chosenClusters = selectedClusters[lp.project.id];
    const restrict = chosenClusters && chosenClusters.size > 0;

    if (!restrict) {
      // Cały projekt
      parts.push(`\n## Projekt: ${projName} (${lp.nodes.length} notatek)`);
      for (const n of lp.nodes) {
        parts.push(`- [${str(n.node_type) || 'notatka'}] ${n.title || n.id}${n.content ? `\n  treść: ${str(n.content)}` : ''}`);
      }
    } else {
      for (const c of lp.clusters) {
        if (chosenClusters.has(c.key)) {
          clusterCount++;
          const nodes = lp.nodes.filter((n) => c.nodeIds.includes(n.id));
          parts.push(`\n## ${projName} → klaster: ${c.title || c.key} (${c.nodeIds.length} notatek)`);
          for (const n of nodes) {
            parts.push(`- [${str(n.node_type) || 'notatka'}] ${n.title || n.id}${n.content ? `\n  treść: ${str(n.content)}` : ''}`);
          }
        }
      }
    }
  }

  const labelParts: string[] = [];
  if (chosen.length) labelParts.push(`${chosen.length} projekt${chosen.length === 1 ? '' : 'y'}`);
  if (clusterCount) labelParts.push(`${clusterCount} klaster${clusterCount === 1 ? '' : 'ów'}`);
  const label = labelParts.join(' · ') || 'kontekst';

  return { label, text: parts.join('\n') };
}

export function AiChatSidebar({ isOpen, onClose }: AiChatSidebarProps) {
  const [width, setWidth] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('cortex_ai_sidebar_width');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= MIN_SIDEBAR_WIDTH) {
          return parsed;
        }
      }
    } catch {
      // Ignoruj
    }
    return DEFAULT_SIDEBAR_WIDTH;
  });

  const [isResizing, setIsResizing] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [liveActive, setLiveActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contextConfig, setContextConfig] = useState<ContextConfig>(() => loadContextConfig());
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [liveSnapshot, setLiveSnapshot] = useState<LiveSnapshot | null>(null);

  // Tryb ręczny: wybór projektów i klastrów niezależny od kropki.
  const [isManualOpen, setIsManualOpen] = useState(false);
  const [manualProjects, setManualProjects] = useState<LoadedProject[]>([]);
  const [manualLoading, setManualLoading] = useState(false);
  const [manualProjectIds, setManualProjectIds] = useState<Set<string>>(new Set());
  const [manualClusters, setManualClusters] = useState<Record<string, Set<string>>>({});

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [sessionsLoaded, setSessionsLoaded] = useState(false);

  // Ładowanie sesji z StorageEngine (main process) — asynchroniczne, przez IPC.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const b = window.cortexBridge;
      if (!b?.chatGetSessions) {
        try {
          const raw = localStorage.getItem('cortex_ai_sessions');
          let list: ChatSession[] = raw ? JSON.parse(raw) : [];
          let active = localStorage.getItem('cortex_ai_active_session_id') || '';
          if (!list.length) {
            const s = createSession('Nowa rozmowa');
            list = [s];
            active = s.id;
          } else if (!active || !list.some((x) => x.id === active)) {
            active = list[0].id;
          }
          setSessions(list);
          setActiveSessionId(active);
        } catch {
          const s = createSession('Nowa rozmowa');
          setSessions([s]);
          setActiveSessionId(s.id);
        }
        setSessionsLoaded(true);
        return;
      }
      try {
        const loaded = await b.chatGetSessions();
        if (cancelled) return;
        let list = Array.isArray(loaded)
          ? loaded.map((s) => ({ ...s, context: Array.isArray(s.context) ? s.context : [] }))
          : [];
        let active = await b.chatGetActiveSessionId();
        if (cancelled) return;
        if (!list.length) {
          const s = createSession('Nowa rozmowa');
          list = [s];
          active = s.id;
        } else if (!active || !list.some((x) => x.id === active)) {
          active = list[0].id;
        }
        setSessions(list);
        setActiveSessionId(active);
      } catch (e) {
        console.error('[AiChat] load sessions failed', e);
        const s = createSession('Nowa rozmowa');
        setSessions([s]);
        setActiveSessionId(s.id);
      } finally {
        if (!cancelled) setSessionsLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Zapis sesji do StorageEngine (oraz fallback do localStorage) — po każdej zmianie listy.
  useEffect(() => {
    if (!sessionsLoaded) return;
    try {
      localStorage.setItem('cortex_ai_sessions', JSON.stringify(sessions));
    } catch {
      // Ignoruj błędy localStorage
    }
    const b = window.cortexBridge;
    if (!b?.chatSaveSession) return;
    for (const s of sessions) {
      void b.chatSaveSession({ session: s });
    }
  }, [sessions, sessionsLoaded]);

  // Zapis aktywnej sesji.
  useEffect(() => {
    if (!activeSessionId) return;
    try {
      localStorage.setItem('cortex_ai_active_session_id', activeSessionId);
    } catch {
      // Ignoruj błędy localStorage
    }
    const b = window.cortexBridge;
    if (!b?.chatSaveActiveSessionId) return;
    void b.chatSaveActiveSessionId({ id: activeSessionId });
  }, [activeSessionId]);

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? sessions[0];
  const messages = activeSession?.messages ?? [];

  const updateSession = useCallback(
    (id: string, fn: (s: ChatSession) => ChatSession) => {
      setSessions((prev) => prev.map((s) => (s.id === id ? fn(s) : s)));
    },
    [],
  );

  const handleNewChat = useCallback(() => {
    const s = createSession('Nowa rozmowa');
    setSessions((prev) => [s, ...prev]);
    setActiveSessionId(s.id);
    setError(null);
  }, []);

  const handleDeleteSession = useCallback(
    (id: string) => {
      const b = window.cortexBridge;
      if (b?.chatDeleteSession) void b.chatDeleteSession({ id });
      const next = sessions.filter((s) => s.id !== id);
      if (!next.length) {
        const s = createSession('Nowa rozmowa');
        setSessions([s]);
        setActiveSessionId(s.id);
        setError(null);
        return;
      }
      setSessions(next);
      if (activeSessionId === id) {
        setActiveSessionId(next[0].id);
      }
      setError(null);
    },
    [sessions, activeSessionId],
  );

  // Zapis konfiguracji kontekstu
  useEffect(() => {
    persistContextConfig(contextConfig);
  }, [contextConfig]);

  const toggleConfigSection = useCallback((key: keyof ContextConfig) => {
    setContextConfig((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // --- Tryb ręczny: ładowanie projektów + klastrów -----------------------
  const loadManualProjects = useCallback(async () => {
    const b = window.cortexBridge;
    if (!b?.projGetProjects) return;
    setManualLoading(true);
    try {
      const projs = await b.projGetProjects();
      const loaded: LoadedProject[] = [];
      for (const p of projs) {
        const nodes = (await b.projGetNodes({ projectId: p.id })).map((n) => {
          if (n.title) return n;
          const firstLine = (n.content || '').split('\n').find((l) => l.trim() !== '')?.trim() ?? '';
          return { ...n, title: firstLine };
        });
        const edges = await b.projGetEdges({ projectId: p.id });
        const clusters = computeProjectClusters(p, nodes, edges);
        loaded.push({ project: p, nodes, edges, clusters });
      }
      setManualProjects(loaded);
    } catch (e) {
      console.error('[AiChat] manual context load failed', e);
      setError(String(e));
    } finally {
      setManualLoading(false);
    }
  }, []);

  const toggleManualProject = useCallback(
    (projId: string) => {
      // Zaznaczenie projektu = zaznaczenie wszystkich jego klastrów;
      // odznaczenie projektu = odznaczenie wszystkich jego klastrów.
      setManualProjectIds((prev) => {
        const next = new Set(prev);
        if (next.has(projId)) next.delete(projId);
        else next.add(projId);
        return next;
      });
      setManualClusters((cl) => {
        const c = { ...cl };
        const current = cl[projId];
        if (current && current.size > 0) {
          delete c[projId];
        } else {
          const lp = manualProjects.find((p) => p.project.id === projId);
          c[projId] = new Set(lp?.clusters.map((x) => x.key) ?? []);
        }
        return c;
      });
    },
    [manualProjects],
  );

  const toggleAllProjects = useCallback(() => {
    const allSelected = manualProjects.length > 0 && manualProjectIds.size === manualProjects.length;
    if (allSelected) {
      setManualProjectIds(new Set<string>());
      setManualClusters({});
    } else {
      setManualProjectIds(new Set(manualProjects.map((p) => p.project.id)));
      const c: Record<string, Set<string>> = {};
      for (const lp of manualProjects) {
        c[lp.project.id] = new Set(lp.clusters.map((x) => x.key));
      }
      setManualClusters(c);
    }
  }, [manualProjects, manualProjectIds]);

  const toggleManualCluster = useCallback((projId: string, clusterKey: string) => {
    setManualClusters((prev) => {
      const existing = prev[projId] ? new Set(prev[projId]) : new Set<string>();
      if (existing.has(clusterKey)) existing.delete(clusterKey);
      else existing.add(clusterKey);
      return { ...prev, [projId]: existing };
    });
    // Zaznaczenie klastra oznacza też wybór projektu
    setManualProjectIds((prev) => {
      const next = new Set(prev);
      next.add(projId);
      return next;
    });
  }, []);

  const addManualContext = useCallback(() => {
    const built = buildManualContext(manualProjects, manualProjectIds, manualClusters);
    if (!built) return;
    const block: ContextBlock = {
      id: `ctx-${Date.now()}`,
      label: built.label,
      text: built.text,
      createdAt: Date.now(),
    };
    updateSession(activeSessionId, (s) => ({
      ...s,
      context: [...s.context, block],
      updatedAt: Date.now(),
    }));
    setError(null);
  }, [manualProjects, manualProjectIds, manualClusters, activeSessionId, updateSession]);

  // Live tracking (kropka) — polling co 500 ms, bo storage nie odpala się w tym oknie
  useEffect(() => {
    if (!isOpen) return;
    const read = () => {
      try {
        setLiveActive(localStorage.getItem(LIVE_ENABLED_KEY) === '1');
      } catch {
        setLiveActive(false);
      }
      try {
        const raw = localStorage.getItem(LIVE_SNAPSHOT_KEY);
        if (raw) {
          setLiveSnapshot(JSON.parse(raw) as LiveSnapshot);
        } else {
          setLiveSnapshot(null);
        }
      } catch {
        setLiveSnapshot(null);
      }
    };
    read();
    const interval = window.setInterval(read, 500);
    window.addEventListener('storage', read);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('storage', read);
    };
  }, [isOpen]);

  // Escape zamyka
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Autofocus po otwarciu
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
      // Załaduj projekty do trybu ręcznego (jeśli jeszcze nie ma)
      if (!manualProjects.length) void loadManualProjects();
    }
  }, [isOpen]);

  // Scroll do najnowszej wiadomości
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [messages, isThinking, activeSessionId]);

  // Rozciąganie
  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX;
      const maxAllowedWidth = Math.max(MIN_SIDEBAR_WIDTH, window.innerWidth - 80);
      const clampedWidth = Math.min(Math.max(newWidth, MIN_SIDEBAR_WIDTH), maxAllowedWidth);
      setWidth(clampedWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  useEffect(() => {
    try {
      localStorage.setItem('cortex_ai_sidebar_width', width.toString());
    } catch {
      // Ignoruj
    }
  }, [width]);

  const handleSend = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isThinking || !activeSession) return;

    const sessionId = activeSession.id;
    const userMsg: ChatMessage = {
      id: `${Date.now()}-u`,
      sender: 'user',
      text: trimmed,
      timestamp: Date.now(),
    };

    const history = [...activeSession.messages, userMsg];
    updateSession(sessionId, (s) => ({
      ...s,
      messages: [...s.messages, userMsg],
      updatedAt: Date.now(),
    }));
    setInputValue('');
    setIsThinking(true);
    setError(null);

    const systemPrompt =
      'Jesteś asystentem AI w aplikacji Cortex — narzędziu do pracy na nieskończonej kanwie notatek. ' +
      'Pojęcia domeny: "notatka" to pojedynczy węzeł z treścią; "klaster" to grupa powiązanych notatek; ' +
      '"klamra" (bracket) to rama/obszar spinający notatki lub klastry; "krawędź"/"połączenie" to relacja ' +
      'między notatkami (może być skierowana); "projekt" to zbiór notatek i klastrów. ' +
      'Odpowiadaj pomocnie i zwięźle, w języku użytkownika. Możesz korzystać wyłącznie z informacji ' +
      'zawartych w tej rozmowie oraz z kontekstu kanwy opisanego w kolejnych wiadomościach systemowych. ' +
      'Nie zmyślaj danych, których nie ma w kontekście. Nie możesz samodzielnie edytować kanwy — ' +
      'jeśli użytkownik prosi o zmianę treści, zaproponuj konkretny tekst lub kroki, ale zaznacz, że ' +
      'zmianę musi zatwierdzić użytkownik. Formatuj odpowiedzi czytelnie (listy, tabele, kod).';

    const snapshot = readLiveSnapshot();
    const viewContext = snapshot ? buildCleanViewContext(snapshot, contextConfig) : '';

    // Trwałe bloki kontekstu dodane ręcznie (append-only) w tej sesji.
    const manualBlocks = activeSession.context ?? [];

    const apiMessages = [
      { role: 'system', content: systemPrompt },
      ...(viewContext
        ? [
            {
              role: 'system',
              content:
                'Kontekst widoku kanwy (użytkownik włączył przycisk „kropka” i przekazuje to, co aktualnie widzi):\n' +
                viewContext,
            },
          ]
        : []),
      // Kontekst wybrany ręcznie — trwały przez całą rozmowę.
      ...manualBlocks.map((b) => ({
        role: 'system' as const,
        content: `Kontekst dodany ręcznie przez użytkownika (${b.label}):\n${b.text}`,
      })),
      // Historia obcinana do ostatnich N wiadomości, żeby nie doprowadzić do wybuchu tokenów.
      ...history.slice(-MAX_HISTORY_MESSAGES).map((m) => ({
        role: m.sender,
        content: m.text,
      })),
    ];

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      // Czytamy strumień SSE (stream: true) — proxy DeepSeek zwraca chunk
      // OpenAI `choices[0].delta.content` zakończone linią `data: [DONE]`.
      setStreamingText('');
      const res = await fetch(CHAT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'deepseek-v4-pro',
          messages: apiMessages,
          stream: true,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        throw new Error(`Proxy zwróciło błąd ${res.status}${errText ? `: ${errText.slice(0, 300)}` : ''}`);
      }

      if (!res.body) {
        throw new Error('Proxy zwróciło pustą odpowiedź strumieniową.');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let replyText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE może dzielić zdarzenia na wiele chunków — parsuj tylko pełne linie.
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          if (data === '[DONE]') continue;
          try {
            const parsed = JSON.parse(data);
            const delta = parsed?.choices?.[0]?.delta?.content;
            if (typeof delta === 'string' && delta) {
              replyText += delta;
              setStreamingText(replyText);
            }
          } catch {
            // Ignoruj niekompletne/błędne linie SSE — zbieraj co się da.
          }
        }
      }

      clearTimeout(timeoutId);
      if (!replyText.trim()) replyText = '(brak odpowiedzi)';

      const assistantMsg: ChatMessage = {
        id: `${Date.now()}-a`,
        sender: 'assistant',
        text: replyText,
        timestamp: Date.now(),
      };
      updateSession(sessionId, (s) => ({
        ...s,
        messages: [...s.messages, assistantMsg],
        updatedAt: Date.now(),
      }));
    } catch (err) {
      clearTimeout(timeoutId);
      let reason = 'Nieznany błąd.';
      if (err instanceof Error && err.name === 'AbortError') {
        reason = `Przekroczono limit czasu oczekiwania (${Math.round(REQUEST_TIMEOUT_MS / 1000)} s). DeepSeek nie odpowiedział.`;
      } else if (err instanceof Error) {
        reason = err.message;
      }
      setError(reason);
      const assistantMsg: ChatMessage = {
        id: `${Date.now()}-a`,
        sender: 'assistant',
        text: `Nie udało się uzyskać odpowiedzi od AI.\n\nPowód: ${reason}\n\nSprawdź, czy proxy DeepSeek działa (powinno być uruchomione razem z Cortex).`,
        timestamp: Date.now(),
      };
      updateSession(sessionId, (s) => ({
        ...s,
        messages: [...s.messages, assistantMsg],
        updatedAt: Date.now(),
      }));
    } finally {
      setStreamingText('');
      setIsThinking(false);
    }
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <aside
      aria-label="Cortex AI Asystent"
      className={`fixed top-0 right-0 bottom-0 z-40 flex flex-col border-l shadow-[-20px_0_50px_rgba(0,0,0,0.85)] backdrop-blur-3xl ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      } ${isResizing ? '' : 'transition-transform duration-300 ease-out'}`}
      style={{
        width: `${width}px`,
        maxWidth: '96vw',
        backgroundColor: 'rgba(14, 14, 14, 0.98)',
        borderColor: '#242424',
      }}
    >
      {/* UCHWYT DO ROZCIĄGANIA */}
      <div
        onMouseDown={startResizing}
        aria-label="Zmień szerokość panelu"
        role="separator"
        aria-orientation="vertical"
        className="absolute top-0 bottom-0 -left-1.5 w-3 cursor-col-resize z-50 group flex items-center justify-center select-none"
        title="Przeciągnij, aby rozciągnąć panel"
      >
        <div
          className={`w-[2px] h-full transition-colors duration-150 ${
            isResizing ? 'bg-[#FFC799]' : 'bg-transparent group-hover:bg-[#FFC799]/50'
          }`}
        />
      </div>

      {/* NAGŁÓWEK */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#202020] bg-[#111111]/80 select-none">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-[rgba(255,199,153,0.1)] border border-[rgba(255,199,153,0.25)] flex items-center justify-center text-[#FFC799] text-sm font-bold shadow-sm">
            ✦
          </div>
          <div>
            <h2 className="text-sm font-bold text-white tracking-wide">Cortex AI Asystent</h2>
            <div className="flex items-center gap-2">
              <p className="text-[11px] text-[#777]">
                {activeSession ? activeSession.name : 'Czat'}
              </p>
              {liveActive && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#FFC799]/10 text-[#FFC799] border border-[#FFC799]/30 select-none">
                  ● widok
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsManualOpen((v) => !v)}
            aria-label="Wybierz kontekst"
            title="Wybierz projekty i klastry, które AI ma dostać"
            className={`flex items-center gap-1.5 px-2.5 h-8 rounded-xl transition-colors cursor-pointer text-xs font-medium ${
              isManualOpen
                ? 'text-[#FFC799] bg-[#202020]'
                : 'text-[#bbb] hover:text-[#FFC799] hover:bg-[#202020]'
            }`}
          >
            <span>⊞</span>
            <span>Kontekst</span>
          </button>
          <button
            onClick={() => setIsConfigOpen((v) => !v)}
            aria-label="Konfiguracja kontekstu"
            title="Konfiguracja kontekstu kropki"
            className={`w-8 h-8 rounded-xl flex items-center justify-center transition-colors cursor-pointer text-sm ${
              isConfigOpen
                ? 'text-[#FFC799] bg-[#202020]'
                : 'text-[#bbb] hover:text-[#FFC799] hover:bg-[#202020]'
            }`}
          >
            ⚙
          </button>
          <button
            onClick={handleNewChat}
            aria-label="Nowa rozmowa"
            title="Nowa rozmowa"
            className="w-8 h-8 rounded-xl flex items-center justify-center text-[#bbb] hover:text-[#FFC799] hover:bg-[#202020] transition-colors cursor-pointer text-sm"
          >
            +
          </button>
          <button
            onClick={onClose}
            aria-label="Zamknij asystenta AI"
            className="w-8 h-8 rounded-xl flex items-center justify-center text-[#777] hover:text-white hover:bg-[#202020] transition-colors cursor-pointer text-sm"
          >
            ✕
          </button>
        </div>
      </div>

      {/* PANEL KONFIGURACJI KONTEKSTU KROPKI */}
      {isConfigOpen && (
        <div className="px-5 py-4 border-b border-[#202020] bg-[#0d0d0d]/60 select-none space-y-2 max-h-80 overflow-y-auto cortex-chat-scroll">
          <span className="text-sm font-semibold text-[#ccc]">Kropka — co wysłać z widoku</span>

          {(
            [
              ['content', 'Treść notatek'],
              ['edges', 'Połączenia'],
              ['brackets', 'Klamry'],
              ['selected', 'Zaznaczone'],
            ] as [keyof ContextConfig, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => toggleConfigSection(key)}
              className={`flex w-full items-center justify-between px-3 py-2 rounded-lg text-sm border transition-colors cursor-pointer ${
                contextConfig[key]
                  ? 'border-[#FFC799]/40 bg-[rgba(255,199,153,0.1)] text-[#FFC799]'
                  : 'border-[#242424] bg-[#161616] text-[#999] hover:text-[#ccc]'
              }`}
            >
              <span>{label}</span>
              <span className="text-xs">{contextConfig[key] ? 'wł.' : 'wył.'}</span>
            </button>
          ))}
        </div>
      )}

      {/* PANEL RĘCZNEGO WYBORU KONTEKSTU (tryb niezależny od kropki) */}
      {isManualOpen && (
        <div className="px-5 py-4 border-b border-[#202020] bg-[#0d0d0d]/60 select-none space-y-3 max-h-[50vh] overflow-y-auto cortex-chat-scroll">
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[#666]">
              {manualLoading ? 'ładuję…' : `${manualProjects.length} projektów`}
            </span>
            <button
              onClick={toggleAllProjects}
              className="text-sm text-[#FFC799] hover:underline cursor-pointer"
            >
              {manualProjectIds.size === manualProjects.length && manualProjects.length > 0
                ? 'odznacz wszystko'
                : 'zaznacz wszystko'}
            </button>
          </div>

          {manualProjects.map((lp) => {
            const pid = lp.project.id;
            const projOn = manualProjectIds.has(pid);
            const chosenClusters = manualClusters[pid];
            const restricted = chosenClusters && chosenClusters.size > 0;
            return (
              <div key={pid} className="rounded-lg border border-[#242424] bg-[#161616] overflow-hidden">
                <button
                  onClick={() => toggleManualProject(pid)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-left text-sm transition-colors cursor-pointer ${
                    projOn && !restricted ? 'text-[#FFC799]' : 'text-[#ccc]'
                  }`}
                >
                  <span className="text-sm">{restricted ? '◐' : projOn ? '●' : '○'}</span>
                  <span className="flex-1 truncate">
                    {lp.project.name || pid} <span className="text-[#888]">({lp.nodes.length})</span>
                  </span>
                  <span className="text-xs text-[#777]">
                    {lp.clusters.length ? `${lp.clusters.length} klastrów` : ''}
                  </span>
                </button>

                {lp.clusters.length > 0 && (
                  <div className="px-3 pb-2 space-y-1">
                    {lp.clusters.map((c) => {
                      const on = chosenClusters?.has(c.key);
                      return (
                        <button
                          key={c.key}
                          onClick={() => toggleManualCluster(pid, c.key)}
                          className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-left text-sm transition-colors cursor-pointer ${
                            on
                              ? 'bg-[rgba(255,199,153,0.1)] text-[#FFC799]'
                              : 'text-[#aaa] hover:text-[#ddd]'
                          }`}
                        >
                          <span className="text-sm">{on ? '●' : '○'}</span>
                          <span className="flex-1 truncate">{c.title || c.key}</span>
                          <span className="text-xs text-[#777]">{c.nodeIds.length}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          <button
            onClick={addManualContext}
            disabled={manualProjectIds.size === 0}
            className={`w-full py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              manualProjectIds.size > 0
                ? 'bg-[#FFC799] text-black hover:bg-[#ffd6b3]'
                : 'bg-[#222222] text-[#444] cursor-not-allowed'
            }`}
          >
            Dodaj do rozmowy
          </button>
        </div>
      )}

      {/* LISTA SESJI */}
      <div className="max-h-32 overflow-y-auto px-4 py-2 border-b border-[#202020] bg-[#0d0d0d]/60 select-none">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`group flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors ${
              s.id === activeSessionId
                ? 'bg-[rgba(255,199,153,0.1)] text-[#FFC799]'
                : 'hover:bg-[#161616] text-[#999]'
            }`}
          >
            <button
              onClick={() => setActiveSessionId(s.id)}
              className="flex-1 text-left truncate cursor-pointer"
              title={s.name}
            >
              <div className="font-medium truncate">{s.name}</div>
              <div className="text-[10px] text-[#666] truncate">{sessionPreview(s)}</div>
            </button>
            <button
              onClick={() => handleDeleteSession(s.id)}
              aria-label={`Usuń sesję ${s.name}`}
              className="text-[#666] hover:text-red-400 text-[10px] leading-none cursor-pointer opacity-0 group-hover:opacity-100"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* WIADOMOŚCI */}
      <div className="flex-1 overflow-y-auto min-h-0 px-6 py-6 space-y-4 cortex-chat-scroll">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 select-none my-auto">
            <div className="w-12 h-12 rounded-2xl bg-[rgba(255,199,153,0.08)] border border-[rgba(255,199,153,0.2)] flex items-center justify-center text-[#FFC799] text-xl mb-3 shadow-[0_0_20px_rgba(255,199,153,0.1)]">
              ✦
            </div>
            <h3 className="text-base font-semibold text-white mb-1.5">W czym mogę pomóc?</h3>
            <p className="text-xs text-[#777] max-w-sm leading-relaxed">
              Zadaj pytanie, poproś o syntezę swoich notatek lub wpisz temat do analizy poniżej.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed shadow-md ${
                  msg.sender === 'user'
                    ? 'bg-[#222222] border border-[#333333] text-white rounded-tr-sm'
                    : 'bg-[#181818] border border-[#2a2a2a] text-[#ddd] rounded-tl-sm'
                }`}
              >
                <div className="break-words">
                  {msg.sender === 'assistant' ? renderMarkdown(msg.text) : <span className="whitespace-pre-wrap">{msg.text}</span>}
                </div>
                <div className="text-[11px] text-[#666] text-right mt-1.5 font-mono">
                  {formatTime(msg.timestamp)}
                </div>
              </div>
            </div>
          ))
        )}

        {isThinking && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed bg-[#181818] border border-[#2a2a2a] text-[#ddd] rounded-tl-sm">
              {streamingText ? (
                <div className="break-words">
                  {renderMarkdown(streamingText)}
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#FFC799] animate-pulse ml-1 align-middle" />
                </div>
              ) : (
                <div className="flex items-center gap-2 text-[#FFC799] text-xs">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#FFC799] animate-pulse" />
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#FFC799] animate-pulse" style={{ animationDelay: '0.15s' }} />
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#FFC799] animate-pulse" style={{ animationDelay: '0.3s' }} />
                  <span className="ml-1 text-[#777]">AI pisze...</span>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* STOPKA / INPUT */}
      <div className="p-4 border-t border-[#202020] bg-[#111111]/90">
        {error && (
          <div className="mb-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-[11px]">
            {error}
          </div>
        )}

        <div className="flex items-center bg-[#161616] border border-[#2a2a2a] rounded-2xl px-4 py-2 transition-colors duration-150 focus-within:border-[#3d3d3d]">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Napisz wiadomość do Cortex AI..."
            rows={1}
            className="w-full bg-transparent border-none text-sm text-white placeholder-[#666] flex-1 py-2 focus:outline-none focus:ring-0 resize-none max-h-40 overflow-y-auto cortex-chat-scroll"
            style={{ outline: 'none', border: 'none', boxShadow: 'none' }}
            disabled={isThinking}
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isThinking}
            aria-label="Wyślij"
            style={{ outline: 'none' }}
            className={`w-7 h-7 rounded-xl font-bold text-xs flex items-center justify-center transition-all ml-2 ${
              inputValue.trim() && !isThinking
                ? 'bg-[#FFC799] text-black hover:bg-[#ffd6b3] cursor-pointer shadow-sm'
                : 'bg-[#222222] text-[#444] cursor-not-allowed'
            }`}
          >
            ➔
          </button>
        </div>

        <div className="flex items-center justify-between mt-2 px-1 text-[10px] text-[#555] font-mono select-none">
          <span>{liveActive ? '● kontekst widoku: włączony' : 'Enter — wyślij, Shift+Enter — nowa linia'}</span>
          <span>Esc — zamknij</span>
        </div>
      </div>
    </aside>
  );
}