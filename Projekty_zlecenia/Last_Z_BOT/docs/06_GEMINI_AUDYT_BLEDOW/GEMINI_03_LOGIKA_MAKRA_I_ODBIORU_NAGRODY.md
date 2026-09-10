# GEMINI AUDYT CZĘŚĆ 3: LOGIKA MAKRA, CYKL ZDARZEŃ I ODBIÓR NAGRODY
**Pliki audytowane:** `mvp/macro_def.py`, `mvp/bot/macro_engine.py`, `mvp/bot/runner.py`

---

## 1. BŁĄD KRYTYCZNY: Całkowity brak logiki odbioru nagrody po punkcie $T_0$

### Dowód w kodzie
Plik: `mvp/macro_def.py:174-190`

```python
    MacroStep(
        type=StepType.WATCH_TIMER,
        label="Step 5: watch timer (HH:MM:SS), idle->fast->spam",
        roi_pct=_ROI_TIMER,
        click_x=50,
        click_y=52,
        ...
        spam_duration_s=config.spam_duration_s,
        spam_clicks_per_sec=config.spam_clicks_per_sec,
    ),
```

Po kroku 5 tablica `steps` w `build_helicopter_macro` **się kończy** (brak kolejnych kroków).

### Mechanizm awarii
1. W trakcie zrzutu skrzynki (po odliczeniu timera do 0) helikopter odlatuje, a na mapie pojawia się skrzynka / zrzut.
2. Zgodnie z mechaniką gry opisaną przez klienta:
   - Po pojawieniu się skrzynki konieczne jest: kliknięcie w skrzynkę $\to$ otwarcie menu kontekstowego „Select” $\to$ odnalezienie opcji „Explore Treasure” $\to$ kliknięcie jej $\to$ odebranie nagrody $\to$ zamknięcie okna łupu $\to$ powrót do czuwania.
3. Co robi obecny kod bota w Step 5 (`macro_engine.py:1160-1170`):
   - Klika sztywno w punkt $(50\%, 52\%)$ przez 6 sekund.
   - Nie sprawdza, czy skrzynka w ogóle pojawiła się w $(50, 52)$ (jeśli helikopter był lekko przesunięty, kliknięcia trafiają w pusty kafelek).
   - Nie weryfikuje otwarcia menu wyboru ani dialogu nagrody.
   - Po 6 sekundach krok 5 kończy się statusem `success`, a silnik bota w `runner.py:534` wykonuje `self.macro_engine.reset()` i **od razu uruchamia Step 1 (nasłuch czatu)**.
4. Skutek dla gracza:
   - Skrzynka pozostaje nieodebrana na mapie.
   - Ekran pozostaje w trybie maksymalnego zoomu na mapie świata.
   - Jeśli gra wyświetliła okno nagrody (modal dialog), zasłania ono pasek czatu (`_ROI_CHAT_BAR`), przez co Step 1 nie może otworzyć czatu sojuszu i bot zawiesza się na `SCROLL_LISTEN_CHAT`.

---

## 2. BŁĄD POWAŻNY: Zerowanie statystyk sesji w każdej iteracji pętli

### Dowód w kodzie
Plik: `mvp/bot/macro_engine.py:253-263, 273`

```python
    def reset(self) -> None:
        self.memory.clear()
        self._step_results.clear()
        self._stop_requested.clear()
        self.stats_alerts = 0      # <--- ZEROWANIE
        self.stats_errors = 0      # <--- ZEROWANIE
        self.stats_start_time = None
        self.stats_end_time = None
        self.last_timer_value = None
        self.total_steps = 0

    def run(self, macro: Macro, window) -> MacroResult:
        self.reset()  # <--- Wywoływane na początku KAŻDEGO cyklu makra
        ...
```

Plik: `mvp/bot/runner.py:504, 534`
```python
    result = self.macro_engine.run(self.macro, window)
    ...
    self.macro_engine.reset()
```

### Mechanizm awarii
- Funkcja `reset()` jest wywoływana zarówno na początku `run()`, jak i na końcu każdej iteracji `_main_loop`.
- Zmienne `stats_alerts` oraz `stats_errors` są natychmiast zerowane po zakończeniu każdego helikoptera.
- W rezultacie kontrolki na Dashboardzie GUI (`stats_alerts_text`, `stats_errors_text`) zawsze pokazują 0 lub dane tylko z ułamka sekundy bieżącego helikoptera.

---

## 3. BŁĄD POWAŻNY: Fałszywe wyzwalanie spamu przy braku odczytu OCR (`value is None`)

### Dowód w kodzie
Plik: `mvp/bot/macro_engine.py:1073-1084`

```python
    if phase == "fast":
        if value is None:
            if last_known_value is not None and last_known_value <= spam_threshold:
                logger.info(
                    "watch_timer: timer disappeared at low value (%ds) — box just spawned! Phase -> spam",
                    last_known_value,
                )
                phase = "spam"
```

### Mechanizm awarii
- W fazie szybkiej (`fast`), jeśli `last_known_value <= 5s`, pojedynczy błąd odczytu OCR (rozmyta klatka z powodu animacji, chwilowy spadek jasności, opóźnienie DXCam) powoduje, że `value is None`.
- Kod natychmiast przyjmuje założenie, że „timer zniknął, więc skrzynka się pojawiła” i odpala 6-sekundowy spam klikania.
- Jeśli w rzeczywistości do końca licznika zostały jeszcze 3–4 sekundy, spam kończy się **zanim skrzynka fizycznie pojawi się w grze**. Wszystkie kliknięcia padają w próżnię.
