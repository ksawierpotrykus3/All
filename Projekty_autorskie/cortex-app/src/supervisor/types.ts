// ============================================================================
// CORTEX — AI Supervisor Data Types (Zero-Mock, Real Execution Model)
// Zgodne ze standardem schema.json
// ============================================================================

export type KrokStatus = 'zrobione' | 'czeka_na_ciebie' | 'w_kolejce' | 'blad' | 'w_toku';

export type TypDecyzji = 'approve' | 'modify' | 'reject';

export type WyzwalaczTyp = 'manual' | 'cron' | 'zdarzenie';

export type KrokTyp = 'ai' | 'kod' | 'warunek';

export interface PlikKroku {
  nazwa: string;
  typ?: string;
  tresc?: string;
  rozmiar?: string;
}

export interface OpcjaDecyzji {
  akcja: TypDecyzji;
  etykieta?: string;
  styl?: 'primary' | 'secondary' | 'danger';
}

export interface BlokDecyzji {
  pytanie: string;
  opcje?: OpcjaDecyzji[];
  wymaga_komentarza?: boolean;
}

export interface Krok {
  id: string | number;
  nazwa: string;
  typ: KrokTyp;
  status: KrokStatus;
  opis?: string;
  narzedzie?: string;
  wymaga_akceptacji?: boolean;
  faza?: string;
  szczegoly?: string[];
  
  // Dane wejściowe
  wejscie?: string;
  promptSystem?: string;
  promptUser?: string;
  
  // Dane wyjściowe / Wnioskowanie
  wyjscie?: string;
  wynik?: string;
  odpowiedz?: string;
  reasoning?: string;
  
  // Logi i diagnostyka
  logi?: string[];
  czas_trwania_s?: number;
  
  // Pliki powiązane
  pliki?: PlikKroku[];
  plikiWejsciowe?: string[];
  plikiWyjsciowe?: string[];
  
  // Dane tabelaryczne
  tabela?: Array<Record<string, unknown>>;
  
  // Bramka decyzyjna
  decyzja?: BlokDecyzji;
  
  // Warunek logiczny (dla potoków rozgałęzionych)
  warunek?: string;
}

export type StatusOgolny = 'w_toku' | 'zakonczono' | 'oczekuje' | 'blad';

// Jak uruchomić automatykę. Pole opcjonalne — jeśli go brak, Supervisor
// użyje domyślnego silnika łańcucha AI (chain_executor.py).
export interface PolecenieUruchomienia {
  komenda: string;              // np. "python", "node", "C:\\sciezka\\run.bat"
  args?: string[];              // argumenty, np. ["agent.py", "--auto-approve"]
  cwd?: string;                 // katalog roboczy (opcjonalny)
}

export interface Lancuch {
  id: string;
  nazwa: string;
  opis?: string;
  silnik?: string;
  wyzwalacz?: string;
  wyzwalacz_typ?: WyzwalaczTyp;
  ostatni_start?: string;
  status_ogolny?: StatusOgolny;
  kroki: Krok[];
  uruchom?: PolecenieUruchomienia;
  created_at?: string;
  updated_at?: string;
  parent_id?: string;
  parent_step?: string;
}

export interface DecyzjaPayload {
  pipelineId: string;
  stepId: string | number;
  decision: TypDecyzji;
  feedback?: string;
  timestamp?: string;
}

