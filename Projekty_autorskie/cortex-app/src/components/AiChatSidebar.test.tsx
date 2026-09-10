import { render, screen, fireEvent, cleanup, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { AiChatSidebar } from './AiChatSidebar';
import { App } from '../App';

describe('AiChatSidebar Component', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders sidebar with expanded width (660px) and proper title', () => {
    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText('Cortex AI Asystent')).toBeDefined();
    expect(screen.getAllByText('Nowa rozmowa').length).toBeGreaterThan(0);

    const aside = screen.getByRole('complementary', { name: 'Cortex AI Asystent' });
    expect(aside.style.width).toBe('660px');
  });

  it('starts empty with clean greeting and no fake mock conversation', () => {
    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText('W czym mogę pomóc?')).toBeDefined();
    expect(screen.queryByText(/Jak zoptymalizować surowe strumienie/i)).toBeNull();
  });

  it('allows user to type and send a message', () => {
    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Napisz wiadomość do Cortex AI...');
    const sendBtn = screen.getByRole('button', { name: 'Wyślij' });

    fireEvent.change(input, { target: { value: 'Moje pierwsze prawdziwe pytanie' } });
    fireEvent.click(sendBtn);

    expect(screen.getAllByText('Moje pierwsze prawdziwe pytanie').length).toBeGreaterThan(0);
    expect(screen.queryByText('W czym mogę pomóc?')).toBeNull();
  });

  it('allows stretching / resizing the sidebar by dragging the handle', () => {
    // Ustaw stałą szerokość okna w teście
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1600 });

    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);

    const aside = screen.getByRole('complementary', { name: 'Cortex AI Asystent' });
    const resizer = screen.getByRole('separator', { name: 'Zmień szerokość panelu' });

    expect(aside.style.width).toBe('660px');

    // Rozpocznij przeciąganie
    fireEvent.mouseDown(resizer);

    // Przesuń kursor w lewo (do x = 800, czyli szerokość = 1600 - 800 = 800px)
    act(() => {
      fireEvent.mouseMove(window, { clientX: 800 });
    });

    expect(aside.style.width).toBe('800px');

    // Zakończ przeciąganie
    act(() => {
      fireEvent.mouseUp(window);
    });

    // Sprawdź czy zapisało w localStorage
    expect(localStorage.getItem('cortex_ai_sidebar_width')).toBe('800');
  });

  it('renders scrollable stream container with cortex-chat-scroll styling', () => {
    const { container } = render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);
    const scrollContainer = container.querySelector('.cortex-chat-scroll');
    expect(scrollContainer).toBeDefined();
    expect(scrollContainer?.className).toContain('overflow-y-auto');
  });

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn();
    render(<AiChatSidebar isOpen={true} onClose={handleClose} />);

    const closeBtn = screen.getByLabelText('Zamknij asystenta AI');
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape key is pressed', () => {
    const handleClose = vi.fn();
    render(<AiChatSidebar isOpen={true} onClose={handleClose} />);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('opens sidebar in App via the AI icon and closes via X', () => {
    render(<App />);

    const aside = screen.getByRole('complementary', { name: 'Cortex AI Asystent' });
    expect(aside.className).toContain('translate-x-full');

    const triggerBtn = screen.getByRole('button', { name: 'Otwórz asystenta AI' });
    fireEvent.click(triggerBtn);
    expect(aside.className).toContain('translate-x-0');

    fireEvent.click(screen.getByLabelText('Zamknij asystenta AI'));
    expect(aside.className).toContain('translate-x-full');
  });

  it('creates a new chat session when the + button is clicked', () => {
    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);

    const before = JSON.parse(localStorage.getItem('cortex_ai_sessions') || '[]');
    expect(before.length).toBe(1);

    fireEvent.click(screen.getByLabelText('Nowa rozmowa'));

    const after = JSON.parse(localStorage.getItem('cortex_ai_sessions') || '[]');
    expect(after.length).toBe(2);
    expect(after[0].messages).toEqual([]);
  });

  it('deletes a session via its delete button', () => {
    const s1 = {
      id: 's1',
      name: 'Pierwsza',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    const s2 = {
      id: 's2',
      name: 'Druga',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    localStorage.setItem('cortex_ai_sessions', JSON.stringify([s1, s2]));
    localStorage.setItem('cortex_ai_active_session_id', 's1');

    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Usuń sesję Pierwsza' }));

    const after = JSON.parse(localStorage.getItem('cortex_ai_sessions') || '[]');
    expect(after.map((s: any) => s.id)).toEqual(['s2']);
    expect(localStorage.getItem('cortex_ai_active_session_id')).toBe('s2');
  });

  it('shows the live view indicator when tracking is enabled', () => {
    localStorage.setItem('cortex_live_tracking_enabled', '1');
    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('● widok')).toBeDefined();
  });

  it('shows AI failure message in chat when fetch rejects', async () => {
    (fetch as any).mockRejectedValue(new Error('DeepSeek padł'));

    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('Napisz wiadomość do Cortex AI...'), {
      target: { value: 'Cześć' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Wyślij' }));

    await waitFor(() => {
      expect(screen.getAllByText(/Nie udało się uzyskać odpowiedzi od AI/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/DeepSeek padł/).length).toBeGreaterThan(0);
    });
  });

  it('shows timeout message when fetch aborts', async () => {
    (fetch as any).mockImplementation(
      (_url: string, opts: any) =>
        new Promise((_resolve, reject) => {
          opts.signal.addEventListener('abort', () => {
            const err = new Error('Aborted');
            err.name = 'AbortError';
            reject(err);
          });
        }),
    );

    vi.useFakeTimers();
    render(<AiChatSidebar isOpen={true} onClose={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('Napisz wiadomość do Cortex AI...'), {
      target: { value: 'Cześć' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Wyślij' }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(121_000);
    });

    expect(screen.getAllByText(/Przekroczono limit czasu oczekiwania/).length).toBeGreaterThan(0);
    vi.useRealTimers();
  });
});
