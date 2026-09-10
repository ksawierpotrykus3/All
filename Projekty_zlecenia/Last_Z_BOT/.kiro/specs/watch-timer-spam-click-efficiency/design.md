# Watch Timer Optimization Bugfix Design

## Overview

Makro `watch_timer` ma trzy poważne problemy wydajnościowe:

1. **OCR Bottleneck**: Faza FAST odpytuje OCR co 0.2s, co przez 295 sekund nakłada się (każdy query: 0.5–1s), tworząc CPU spike szczególnie tuż przed T0.
2. **CPU nie zwolni się przed spamem**: Ciągłe OCR queries powodują, że w ostatnich 0.5–1s przed spamem CPU jest przegrzany, kliknięcia nie są rejestrowane przez Unity.
3. **Reaktywne spamowanie**: System czeka na potwierdzenie OCR (timer≤5s) zamiast proaktywnie przygotować spam z szacunkiem T0.

Strategia naprawy:
- **Adaptive OCR interval**: Zacząć z 0.5–1.0s w fazie FAST, zmniejszać do 0.2s dopiero w ostatnich 5–10s.
- **CPU pause window**: 0.5–1s przed T0 — wstrzymać OCR, udostępnić CPU dla spamu.
- **Proactive spam prep**: Gdy timer<spam_threshold i mamy 2–3 potwierdzenia, zarezerwować T0 i przygotować spam bez czekania na OCR.
- **Monotonic T0 estimate**: Po dwóch potwierdzeniach timer≤5s, zastosować `estimated_t0_mono` zamiast biegać OCR.

## Glossary

- **Bug_Condition (C)**: Mały interwał OCR (0.2s) przez długi okres (FAST: 295s) powoduje CPU spike, a brak CPU pause window tuż przed T0 uniemożliwia rejestrację kliknięć.
- **Property (P)**: System powinien adaptacyjnie zmniejszać obciążenie OCR, wstrzymać OCR w CPU pause window, i proaktywnie przygotować spam na podstawie szacunku T0.
- **Preservation**: Logika faz (IDLE→FAST→SPAM), fallback OCR, rejestracja jumpu timera, obsługa inactivity timeout, priorytet detekcji sieciowej T0 — wszystko musi działać bez zmian.
- **fast_interval**: Obecnie stały 0.2s; musi być adaptacyjny (0.5–1.0s na początku FAST, 0.2s w ostatnich 5–10s).
- **CPU pause window**: Ostatnie 0.5–1s przed szacunkowym T0 — czas, w którym OCR powinno być wstrzymane.
- **estimated_t0_mono**: Monotonicznie rosnący szacunek T0 na bazie zmian timera; zastępuje wielokrotne OCR queries.
- **hysteresis**: Liczba potwierdzeń timer≤5s wymagana do przejścia do SPAM; musi być respektowana.

## Bug Details

### Bug Condition

Bug pojawia się gdy faza jest FAST i timer dąży do 0. Systemu brakuje:
1. Adaptacyjnego zmniejszania obciążenia OCR,
2. Aktywnego wstrzymania OCR tuż przed T0 (CPU pause window),
3. Proaktywnego szacunku T0 opartego na monotoniczności timera.

Efekt: CPU spike tuż przed T0, kliknięcia nie rejestrowane.

**Formalna Specyfikacja:**
```
FUNCTION isBugCondition(state)
  INPUT: state of type WatchTimerState
  OUTPUT: boolean
  
  RETURN (state.phase == FAST)
         AND (current_time_remaining >= fast_interval)
         AND (ocr_queries_accumulated >= threshold_for_cpu_spike)
         AND NOT (cpu_pause_window_active)
         AND NOT (proactive_spam_prepared)
END FUNCTION
```

### Examples

**Przykład 1: OCR Bottleneck**
- Stan: Faza FAST, timer 280s, fast_interval=0.2s.
- Obserwacja: Od 300s do 280s wykonano (300-280)/0.2 = 100 OCR queryów, każdy 0.5–1s = 50–100s CPU time.
- Spodziewane: Powinno być 5–10 queryów z interwałem 1.0s.

**Przykład 2: CPU Spike przed T0**
- Stan: Faza FAST, timer 3s, fast_interval=0.2s, ostatnie 1s przed T0.
- Obserwacja: OCR query uruchomiony zaraz przed spamem, CPU spike, kliknięcia zignorowane.
- Spodziewane: OCR powinno być wstrzymane, CPU wolne dla spamu.

**Przykład 3: Reaktywne vs Proaktywne Spamowanie**
- Stan: OCR potwierdza timer≤5s po 0.3s od rzeczywistego spadku.
- Obserwacja: Spam uruchomi się z opóźnieniem ~0.3s, T0 przegapione.
- Spodziewane: System powinien mieć szacunek T0 z leadtime, spam przygotowany.



## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Logika przejścia między fazami (IDLE → FAST → SPAM) musi pozostać taka sama; zmiana dotyczy tylko częstotliwości OCR w FAST.
- Detekcja sieciowa T0 (sygnatura `\x58\x01` w `push.world.point.update`) zachowuje najwyższy priorytet — nigdy nie może być zablokowana.
- Fallback OCR (gdy sieć nie dostarcza T0) musi nadal działać z nowymi interwałami adaptacyjnymi.
- Obsługa jumpu timera (Δ ≥3s) — system musi wrócić do fazy IDLE/FAST z nowym szacunkiem.
- Obsługa inactivity timeout (1800s) — system musi zwrócić "inactivity_timeout" bez błędu.
- Obsługa None / niedokładności OCR — fallback do `last_known_value` i czekanie na następny odczyt.
- Hysteresis potwierdzenia (wymagana liczba N potwierdzeń timer≤5s) — musi być egzekwowana przed przejściem do SPAM.

**Scope:**
Wszystkie operacje, które nie są zbliżaniem się timera do 0 w fazie FAST, powinny być całkowicie niezmienione:
- Inicjalizacja makra, odczyt konfiguracji.
- Przejście do IDLE (reset timera lub inactivity).
- Wysyłanie spamu w fazie SPAM (algorytm kliknięć niezmieniony).
- Obsługa przerwania (stop signal).

### Preserved Behaviors with Detailed Conditions

1. **Timer Jump Detection** (Requirements 3.1): Gdy timer zmienia się o ≥3s w górę, system rejestruje jump i resetuje szacunek T0.
2. **Inactivity Timeout** (Requirements 3.2): Po 1800s braku zmian, makro zwraca wynik bez błędu.
3. **OCR Error Handling** (Requirements 3.3): None / błędy OCR obsługiwane fallbackiem.
4. **Network T0 Priority** (Requirements 3.4): `\x58\x01` z sieci wyzwala spam niezależnie od OCR.
5. **Hysteresis Enforcement** (Requirements 3.5): Wymaga N potwierdzeń timer≤5s przed SPAM.



## Hypothesized Root Cause

Na bazie analizy bugfix.md, główne przyczyny to:

1. **Stały OCR Interval w Fazie FAST**: `fast_interval=0.2s` aplikowany przez całą fazę (300s–5s) bez adaptacji.
   - Faza trwa ~295s, co daje (295/0.2)=1475 queryów OCR.
   - Każdy query 0.5–1s = 737–1475s CPU time (czyli 2–5 godz. obliczeniowych wciśniętych w 295s).
   - Nakładanie się queryów: query N+1 uruchamia się, gdy query N nadal się wykonuje.

2. **Brak CPU Pause Window**: Tuż przed T0 (ostatnie 0.5–1s) OCR nadal biegnie z pełną mocą.
   - Unity nie rejestruje kliknięć, gdy CPU jest w spike'u.
   - Spam kliknięć wysyłany w szczycie obciążenia ma ~50% wskaźnik nieudanych rejestracji.

3. **Reaktywne Spamowanie**: System czeka na potwierdzenie OCR (timer≤5s) przed przejściem do SPAM.
   - OCR może potwierdzić timer≤5s z opóźnieniem 0.3–0.5s po rzeczywistej zmianie.
   - Lead-time do T0 wynosi ~5s, ale opóźnienie OCR + przygotowanie spamu = już 0.8s zmarnowane.
   - T0 może być przegapiony, jeśli spam nie ma prekalkulowanego momentu startu.

4. **Brak Monotonic T0 Estimate**: Po Δtimer≤1s (2–3 potwierdzeniach), system mógłby ekstrapolować T0.
   - Zamiast tego OCR biegnie dalej i gromadzi szum.
   - Szacunek T0 powinien być "locked" po 2–3 potwierdzeniach, aby umożliwić proaktywne przygotowanie.

5. **Brak Synchronizacji Wysyłania z CPU Load**: Spam kliknięć wysyłany "natychmiast" bez czekania na zmniejszenie obciążenia CPU.
   - Powinno być: czekaj na CPU < próg, potem wyślij spam.



## Correctness Properties

Property 1: Adaptive OCR Interval — Obniżenie CPU Load w Fazie FAST

_For any_ timer value w fazie FAST gdzie system obserwuje long-running countdown (timer >10s), fixed `_handle_watch_timer` 
SHALL dynamicznie zmniejszać obciążenie OCR poprzez zmianę `ocr_dynamic_interval`:
- Początek FAST: `interval = 1.0s` (zamiast 0.2s).
- Ostatnie 5–10s przed T0: `interval = 0.2s`.
- Wynik: total CPU load ze względu na OCR zmniejszy się z 737–1475s do <100s.

**Validates: Requirements 2.1, 2.4**

Property 2: CPU Pause Window — Zwolnienie CPU Przed Spamem

_For any_ timer value gdzie szacunkowy T0 jest znany i bliski (<1s do startu spamu), fixed system 
SHALL całkowicie wstrzymać OCR queries przez ostatnich 0.5–1s (CPU pause window), aby CPU był dostępny dla spam click routine.
- Rezultat: Kliknięcia wysłane w tym oknie będą zarejestrowane przez Unity z >90% wskaźnikiem powodzenia.
- Obserwacja: Bez pauzy, wskaźnik to <50%.

**Validates: Requirements 2.2, 2.4**

Property 3: Proactive Spam Preparation — Przygotowanie Spamu Przed Potwierdzeniem OCR

_For any_ timer value gdzie N potwierdzeń (N≥2) pokazało timer≤5s z konsekwentnym spadkiem Δ, fixed system 
SHALL:
- Ekstrapolować `estimated_t0_mono` na bazie ostatnich Δ z hysterezą.
- Przygotować spam async (bez czekania na następny OCR query).
- Wyzwolić spam z leadtime ~0.2–0.3s przed estimated_t0_mono.
- Rezultat: Spam rozpoczyna się w ciągu ±0.3s od rzeczywistego T0, zamiast ±0.8s (opcja reaktywna).

**Validates: Requirements 2.3**

Property 4: Preservation — Niezmienna Logika Faz i Fallbacków

_For any_ input gdzie timer nie spada monotoniczne (jump ≥3s, None OCR, sieciowy T0, hystereza nie spełniona), 
fixed system SHALL zachować dokładnie to samo zachowanie co original:
- Jump reseta fazę do IDLE.
- None/błędy OCR fallbackują do `last_known_value`.
- Sieć `\x58\x01` wyzwala spam niezależnie od OCR.
- Hystereza wymaga N potwierdzeń.
- Inactivity timeout zwraca wynik po 1800s.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**



## Fix Implementation

### Overview Zmian

Implementacja będzie skupiona na:
1. Nowa konfiguracja w `MacroStep`: `ocr_dynamic_interval_config` (początkowy interval, próg przyspieszenia, min interval).
2. Nowa logika w `_handle_watch_timer`: adaptacyjny interval, CPU pause window, proactive spam trigger.
3. Optymalizacja `_read_timer_value`: flag `skip_ocr` w CPU pause window.
4. Dodanie `estimated_t0_mono` do stanu (tracking monotonicznego szacunku T0).

### File: `mvp/bot/macro_engine.py`

**Lokacja**: Funkcje `_handle_watch_timer`, `_read_timer_value` i logika OCR interval w fazie FAST.

**Zmiana 1: Dodanie Konfiguracji Adaptive OCR Interval do MacroStep**

```python
# W klasie MacroStep, w polach konfiguracji:
ocr_dynamic_interval_config: Optional[Dict[str, float]] = None
# Domyślnie (jeśli None):
# {
#   "initial_interval": 1.0,      # Interwał na początek FAST
#   "accel_threshold": 10.0,      # Liczba sekund pozostałych -> zacząć przyspieszać
#   "min_interval": 0.2,          # Minimalny interwał
#   "cpu_pause_window": 1.0,      # Ostatnie N sekund wstrzymać OCR
# }
```

**Zmiana 2: Adaptacyjny Interval w _handle_watch_timer Faza FAST**

Logika:
- Na starcie FAST: `current_interval = initial_interval (1.0s)`.
- Co każde potwierdzenie timer≤5s: czytaj `time_remaining`, przerachuń `current_interval`:
  - Jeśli `time_remaining >= accel_threshold (10s)`: interval = initial_interval.
  - Jeśli `time_remaining < accel_threshold`: interval zmniejsz liniowo do `min_interval`.
  - Formuła: `interval = min_interval + (initial_interval - min_interval) * (time_remaining / accel_threshold)`.

**Zmiana 3: CPU Pause Window — Wstrzymanie OCR Tuż Przed Spamem**

Logika:
- Gdy `estimated_t0_mono` jest znany i `time_to_t0 < cpu_pause_window`:
  - Ustaw `skip_ocr = True` w `_read_timer_value`.
  - `_read_timer_value` nie będzie wykonywać nowego OCR query, zamiast tego użyje `last_known_value`.
  - System nadal sprawdza warunki wyzwolenia spamu, ale bez obciążenia OCR.

**Zmiana 4: Proactive Spam Preparation — Monotonic T0 Estimate**

Logika:
- Trackuj ostatnich N zmian timera: `[t1, t2, t3, ...]`.
- Po 2–3 potwierdzeniach timer≤5s: oblicz średnie Δ między odczytami.
- Ekstrapoluj: `estimated_t0_mono = current_time + (last_timer_value / avg_delta)`.
- Po obliczeniu: ustaw `spam_prepared = True`, przygotuj spam async bez czekania na następny OCR query.



### Detailed Implementation Strategy

**Zmiana 5: Struktura Stanu w _handle_watch_timer**

Nowe pola do trackowania:
```python
ocr_interval_state = {
    "current_interval": initial_interval,
    "last_query_time": None,
    "timer_history": [],  # Lista ostatnich odczytów timera z czasami
}

spam_prep_state = {
    "confirmed_count": 0,  # Liczba potwierdzeń timer <= spam_threshold
    "estimated_t0_mono": None,
    "spam_prepared": False,
    "preparation_time": None,
}

cpu_pause_state = {
    "active": False,
    "start_time": None,
}
```

**Zmiana 6: Pętla FAST — Integracja Adaptive Interval**

Pseudokod:
```
WHILE phase == FAST AND time_remaining >= fast_threshold DO
  // Sprawdź, czy już czas na kolejny OCR query
  time_since_last_query = now() - ocr_interval_state.last_query_time
  
  IF time_since_last_query >= ocr_interval_state.current_interval THEN
    // Oblicz nowy interval na bazie pozostałego czasu
    new_interval = calculate_adaptive_interval(
      time_remaining,
      initial_interval,
      accel_threshold,
      min_interval
    )
    ocr_interval_state.current_interval = new_interval
    
    // Czytaj timer (z możliwością skip_ocr w CPU pause window)
    timer_value = _read_timer_value(skip_ocr = (cpu_pause_state.active))
    
    // Trackuj historię
    ocr_interval_state.timer_history.append({
      "value": timer_value,
      "time": now()
    })
    
    // Aktualizuj spam_prep_state
    IF timer_value <= spam_threshold THEN
      spam_prep_state.confirmed_count += 1
      IF spam_prep_state.confirmed_count >= hysteresis THEN
        // Ekstrapoluj T0
        delta_avg = calculate_avg_delta(timer_history)
        spam_prep_state.estimated_t0_mono = now() + (timer_value / delta_avg)
    ELSE
      spam_prep_state.confirmed_count = 0
    
    // Włącz CPU pause window, gdy jesteśmy blisko
    IF spam_prep_state.estimated_t0_mono AND 
       (spam_prep_state.estimated_t0_mono - now() < cpu_pause_window) THEN
      cpu_pause_state.active = True
    
    ocr_interval_state.last_query_time = now()
  
  // Czekaj minimalny czas (unikaj busy loop)
  sleep(0.01)  // lub na bazie next_query_time
  
  // Sprawdź warunki wyzwolenia spamu
  IF should_trigger_spam(timer_value, estimated_t0_mono, ...) THEN
    BREAK  // Przejdź do fazy SPAM
END WHILE
```

**Zmiana 7: Warunek should_trigger_spam**

Priorytet:
1. Detekcja sieciowa `\x58\x01` → wyzwól spam natychmiast.
2. OCR potwierdza timer≤5s + hystereza N potwierdzenia → wyzwól spam.
3. `estimated_t0_mono` znany i obecny czas ≈ T0 (±0.2s) → wyzwól spam.

```python
def should_trigger_spam(network_t0_triggered, ocr_timer_value, estimated_t0_mono, ...):
    if network_t0_triggered:
        return True
    if ocr_timer_value <= spam_threshold and confirmed_count >= hysteresis:
        return True
    if estimated_t0_mono is not None:
        time_to_t0 = estimated_t0_mono - now()
        if abs(time_to_t0) <= 0.2:
            return True
    return False
```



## Testing Strategy

### Validation Approach

Strategia testowania przebiega w dwóch fazach:
1. **Exploratory Bug Condition Checking**: Symulacja nieoptymalizowanego OCR na unfixed kodzie → obserwacja CPU spike i spóźnionego spamu.
2. **Fix Verification**: Potwierdzenie, że fixed kod zmniejsza obciążenie OCR i wyzwala spam proaktywnie.
3. **Preservation Checking**: Weryfikacja, że wszystkie pozostałe logiki (jump, inactivity, hystereza) działają identycznie.

### Exploratory Bug Condition Checking

**Cel**: Zaobserwować CPU spike i spóźnione spamowanie na unfixed kodzie, aby potwierdzić root cause.

**Test Plan**: 
Symuluj pełny countdown od 300s do 0s z:
- Stały OCR interval 0.2s (unfixed behavior).
- Mockuj `read_timer_value()` do zwrócenia rzeczywistego spadku timera.
- Mierz CPU load oraz czas od osiągnięcia timer≤5s do wyzwolenia spamu.

**Test Cases**:

1. **OCR Bottleneck Test**: Uruchom unfixed `_handle_watch_timer` z timer 300s→5s, fast_interval=0.2s.
   - Oczekiwane na unfixed: ~1475 OCR queryów w 295s, CPU spike widoczny w ostatnich 5s.
   - Mierzone: Liczba queryów, CPU usage %, opóźnienie spamu.

2. **CPU Pause Window Test**: Obserwuj CPU load w ostatnich 1s przed T0 na unfixed.
   - Oczekiwane na unfixed: CPU usage >80% z powodu OCR.
   - Oczekiwane na fixed: CPU usage <30% dzięki CPU pause.

3. **Spam Trigger Latency Test**: Zmierz czas od timer≤5s do wyzwolenia spamu na unfixed i fixed.
   - Oczekiwane na unfixed: 0.3–0.8s (czekaj na potwierdzenie OCR).
   - Oczekiwane na fixed: 0.1–0.2s (proactive estimate).

4. **Edge Case — timer Jump**: Symuluj jump timera +5s w trakcie FAST.
   - Oczekiwane na both: Reset fazy do IDLE, licznik confirmed_count zerowany.

### Fix Checking

**Cel**: Zweryfikować, że fixed kod spełnia wszystkie 4 Correctness Properties.

**Pseudocode:**
```
FOR ALL scenario IN [300s countdown, jump, network_t0, ocr_error, hysteresis_variations] DO
  result_fixed := run_fixed_handle_watch_timer(scenario)
  ASSERT result_fixed satisfies Property 1, 2, 3, 4
END FOR
```

**Test Cases**:

1. **Adaptive Interval Scaling**: 
   - Input: Timer 300s → 5s z mockowaną OCR.
   - Assert: `ocr_interval` zmienia się z 1.0s do 0.2s w ostatnich 10s.
   - Assert: Total OCR queries < 100 (zamiast 1475).

2. **CPU Pause Activation**:
   - Input: Estimated T0 znany, time_to_t0 < 1.0s.
   - Assert: `skip_ocr = True` w `_read_timer_value`.
   - Assert: CPU load < 30% w ostatnich 1s.

3. **Proactive Spam Trigger**:
   - Input: 3 potwierdzenia timer≤5s, estimated_t0_mono obliczone.
   - Assert: `spam_prepared = True` bez czekania na kolejny OCR query.
   - Assert: Spam wyzwolony ±0.2s od T0 (zamiast ±0.8s).

4. **Network T0 Priority**:
   - Input: Sieciowy `\x58\x01` przychodzi, OCR nadal w fazie FAST.
   - Assert: Spam wyzwolony natychmiast (prioritet nad OCR).

### Preservation Checking

**Cel**: Zweryfikować, że zmiana adaptive interval i CPU pause nie psuje istniejące logiki.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  result_original := run_original_handle_watch_timer(input)
  result_fixed := run_fixed_handle_watch_timer(input)
  ASSERT result_original == result_fixed
END FOR
```

**Testing Approach**: Property-based testing z Hypothesis:
- Generuj losowe sekwencje timer values (monotoniczne spadki, jumpy, none values).
- Dla każdej sekwencji: porównaj originalne i fixed zachowanie.
- Oczekiwane: Identyczne wyniki dla wszystkich non-buggy inputów.

**Test Cases**:

1. **Timer Jump Preservation**:
   - Input: Sekwencja [100, 99, 98, 103] (jump +5s).
   - Assert fixed: Reset do IDLE, T0 reseta.
   - Verify: Identyczne jak original.

2. **Inactivity Timeout Preservation**:
   - Input: Brak zmian przez 1800s.
   - Assert fixed: Zwróć "inactivity_timeout".
   - Verify: Identyczne jak original.

3. **OCR Error Handling Preservation**:
   - Input: `_read_timer_value()` zwraca None.
   - Assert fixed: Fallback do `last_known_value`.
   - Verify: Identyczne jak original.

4. **Hysteresis Enforcement Preservation**:
   - Input: 1 potwierdzenie timer≤5s (hysteresis=2 wymagane).
   - Assert fixed: Nie wyzwala spamu.
   - Verify: Identyczne jak original.

5. **IDLE/Early Phases Preservation**:
   - Input: Timer > fast_threshold (np. 400s).
   - Assert fixed: Faza == IDLE, bez adaptacji interval.
   - Verify: Identyczne jak original.

### Unit Tests

- Test `calculate_adaptive_interval()`: Sprawdź skalowanie z różnymi `time_remaining`, `accel_threshold`.
- Test `calculate_avg_delta()`: Sprawdź ekstrapolację T0 z losową historią zmian.
- Test `should_trigger_spam()`: Sprawdź priorytet (network > hystereza > estimate).
- Test `cpu_pause_window` state machine: Włączanie/wyłączanie pauzy.

### Property-Based Tests (Hypothesis)

- **Property A**: Dla każdej monotonnie malejącej sekwencji timer values w FAST, adaptacyjny interval nigdy nie wywoła OCR niż co 0.2s.
- **Property B**: Dla każdej sekwencji z 2+ potwierdzeniami timer≤5s, estimated_t0_mono zostanie obliczony.
- **Property C**: Dla każdej sekwencji bez jumpa/error, spam zostanie wyzwolony wewnątrz ±0.3s od rzeczywistego T0.

### Integration Tests

- Full countdown 300s → 0s z mockowanymi sieciowymi T0, obserwacja spam timing.
- Countdown z jump w połowie, weryfikacja reset'u.
- Countdown z OCR errors, fallback do last_known_value.
- Multiple countdowns w sekwencji (IDLE → FAST → SPAM → IDLE), verify state reset.

