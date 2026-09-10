// ============================================================================
// CORTEX AI — Typy czatu (współdzielone renderer / main)
// ============================================================================

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: number;
}

// Trwały blok kontekstu dodany przez użytkownika w trybie ręcznym.
// Append-only: raz dodany zostaje w rozmowie, nie można go odznaczyć.
export interface ContextBlock {
  id: string;
  label: string; // krótki opis, np. "3 projekty · 2 klastry"
  text: string; // gotowy tekst kontekstu dla AI
  createdAt: number;
}

export interface ChatSession {
  id: string;
  name: string;
  messages: ChatMessage[];
  context: ContextBlock[];
  createdAt: number;
  updatedAt: number;
}