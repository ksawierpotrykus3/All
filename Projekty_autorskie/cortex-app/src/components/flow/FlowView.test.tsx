import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { FlowView } from './FlowView';
import type { Lancuch } from '../../supervisor/types';

// Mock ResizeObserver dla środowiska jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe('FlowView — Rurociąg zadań React Flow', () => {
  afterEach(() => {
    cleanup();
  });
  const mockPipeline: Lancuch = {
    id: 'useme-oferty',
    nazwa: 'Automatyczna Ofertowarka Useme',
    status_ogolny: 'w_toku',
    kroki: [
      {
        id: 1,
        nazwa: 'Weryfikacja sesji i połączenia',
        typ: 'kod',
        status: 'zrobione',
        wyjscie: 'Połączenie OK',
        czas_trwania_s: 1.2,
      },
      {
        id: 2,
        nazwa: 'Selekcja zleceń przez AI',
        typ: 'ai',
        status: 'w_toku',
        narzedzie: 'DeepSeek',
        reasoning: 'Analiza 5 zleceń pod kątem marży...',
        czas_trwania_s: 3.4,
      },
      {
        id: 3,
        nazwa: 'Bramka akceptacji oferty',
        typ: 'warunek',
        status: 'czeka_na_ciebie',
        decyzja: {
          pytanie: 'Czy zatwierdzasz ofertę 4500 PLN?',
        },
      },
    ],
  };

  beforeEach(() => {
    window.cortexBridge = {
      ...(window.cortexBridge || {}),
      supervisorGetPipelines: vi.fn().mockResolvedValue([mockPipeline]),
      supervisorRunChain: vi.fn().mockResolvedValue({ success: true }),
      supervisorSaveDecision: vi.fn().mockResolvedValue({ success: true }),
    } as any;
  });

  it('renderuje nagłówek, status i klocki rurociągu', async () => {
    const onBack = vi.fn();
    render(<FlowView onBack={onBack} />);

    // Weryfikacja nagłówka
    expect(screen.getByText('Przepływ')).toBeTruthy();
    expect(screen.getByText('Inżynieryjny Rurociąg (DAG)')).toBeTruthy();

    // Weryfikacja załadowania pipeline'u
    await waitFor(() => {
      expect(screen.getByText('Weryfikacja sesji i połączenia')).toBeTruthy();
      expect(screen.getByText('Selekcja zleceń przez AI')).toBeTruthy();
      expect(screen.getByText('Bramka akceptacji oferty')).toBeTruthy();
    });

    // Sprawdzenie obecności statusów
    expect(screen.getByText('Zrobione')).toBeTruthy();
    expect(screen.getByText('Wykonywanie...')).toBeTruthy();
    expect(screen.getByText('Czeka na decyzję')).toBeTruthy();
  });

  it('otwiera szufladę telemetryczną po kliknięciu w krok z bramką decyzyjną', async () => {
    render(<FlowView onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Bramka akceptacji oferty')).toBeTruthy();
    });
    fireEvent.click(screen.getByText('Bramka akceptacji oferty'));

    // Weryfikacja otwarcia szuflady inspekcji
    await waitFor(() => {
      expect(screen.getByText(/Wymagana decyzja inżynierska/i)).toBeTruthy();
      expect(screen.getByText('Czy zatwierdzasz ofertę 4500 PLN?')).toBeTruthy();
      expect(screen.getByText('✓ Zatwierdź')).toBeTruthy();
    });

    // Kliknięcie "Zatwierdź"
    fireEvent.click(screen.getByText('✓ Zatwierdź'));

    await waitFor(() => {
      expect(window.cortexBridge?.supervisorSaveDecision).toHaveBeenCalledWith(
        expect.objectContaining({
          pipelineId: 'useme-oferty',
          stepId: 3,
          decision: 'approve',
        }),
      );
    });
  });

  it('renderuje 7-krokowy rurociąg useme-bot z magazynem, opisami i fazami', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const botData = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, '../../../data/pipelines/useme-bot.json'), 'utf-8')
    );

    window.cortexBridge = {
      ...(window.cortexBridge || {}),
      supervisorGetPipelines: vi.fn().mockResolvedValue([botData]),
    } as any;

    const { container } = render(<FlowView onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Weryfikacja sesji i połączenia')).toBeTruthy();
    });

    const flowNodes = container.querySelectorAll('.react-flow__node');
    expect(flowNodes.length).toBe(7);
  });
});
