# Bugfix Requirements — Optymalizacja Watch Timer'a (Spam Click + OCR Bottleneck)

## Introduction

Makro `watch_timer` w MVP (`mvp/bot/macro_engine.py`, linia 945+) ma poważne problemy wydajnościowe i dokładnościowe:
- **Słaba rejestracja kliknięć**: Unity nie rejestruje wszystkich kliknięć, szczególnie przy wysokim obciążeniu CPU
- **Spóźnione spamowanie**: System reaguje za wolno przed spawnem (nawet z 5-sekundowym timerem do T0)
- **Wysokie zużycie CPU**: Faza FAST odpytuje OCR co 0.2s, co nakłada się (CPU spike szczególnie 0.5s przed T0)

Architektura: watch_timer ma 3 fazy (IDLE → FAST → SPAM). Problem leży w nadmiernej częstotliwości OCR (`fast_interval=0.2s`, `max_passes=2`) oraz braku proaktywnego planowania spamu przed T0, co powoduje kaskadowną obciążenie tuż przed spawnem dropa.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN faza jest FAST (timer ≤ `fast_threshold=300s`) THEN system odpytuje OCR co `fast_interval=0.2s` z `max_passes=2`, powodując nakładanie się zadań OCR na CPU

1.2 WHEN timer zbliża się do 0 (ostatnie 0.5–1s przed T0) THEN CPU spike osiąga szczyt, a kliknięcia wysyłane w tym oknie są słabo rejestrowane przez Unity (brak synchronizacji wysyłania względem CPU load)

1.3 WHEN spam_click jest wysyłany w fazie SPAM THEN moment początkowy spamu jest reaktywny (tzn. czeka na potwierdzenie OCR, że timer ≤ `spam_threshold=5s`), a nie proaktywny (nie przygotowuje się wcześniej)

1.4 WHEN faza FAST trwa długo (np. od 300s do 5s) THEN total CPU load od ciągłych OCR queryów powoduje, że ostatnie 5–10s przed T0 system jest przegrzany i nie może wysłać kliknięć w odpowiednim czasie

### Expected Behavior (Correct)

2.1 WHEN faza jest FAST THEN system musi zmniejszyć częstotliwość OCR, aby obciążenie CPU było stale niskie; proponowany interwał: `adaptive_interval` zaczynający się od ~0.5–1.0s i zmniejszający się jedynie w ostatnich 5–10s

2.2 WHEN timer zbliża się do 0 (ostatnie 0.5–1s) THEN system powinien zmniejszyć lub całkowicie wstrzymać OCR (jeśli T0 jest już precyzyjnie oszacowane), aby zwolnić CPU dla spamu kliknięć

2.3 WHEN timer spadnie poniżej `spam_threshold=5s` i mamy pewność co do T0 THEN system powinien rozpocząć spam proaktywnie (z minimalnym lead-time ~0.2–0.3s przed T0), a nie czekać na potwierdzenie OCR

2.4 WHEN spam_click rozpoczyna się THEN kliknięcia muszą być wysyłane ze stabilnym timingiem (~38 CPS), a CPU musi być wolne od OCR/grab operacji, aby kliknięcia były prawidłowo rejestrowane przez Unity

### Unchanged Behavior (Regression Prevention)

3.1 WHEN timer wraca do wartości wyższej (np. gracz wraca z helikoptera, timer reseta się) THEN system SHALL CONTINUE TO wykrywać to zdarzenie (jump ≥3s) i powrócić do fazy IDLE/FAST z nowym szacunkiem T0

3.2 WHEN timer nie zmienia się przez timeout period (`timeout_s=1800s`) THEN system SHALL CONTINUE TO zwrócić "inactivity_timeout" i skończyć makro bez błędu

3.3 WHEN OCR odczyta timer niedokładnie lub zwróci None THEN system SHALL CONTINUE TO obsługiwać ten scenariusz (fallback do `last_known_value`, czekanie na następny odczyt)

3.4 WHEN detekcja sieciowa T0 (sygnatura `\x58\x01` w `push.world.point.update`) jest dostępna THEN system SHALL CONTINUE TO używać jej jako pierwszy wyzwalacz, niezależnie od OCR

3.5 WHEN hysteresis jest konfigurowany (`hysteresis_confirmations > 1`) THEN system SHALL CONTINUE TO wymagać N potwierdzeń timer ≤ `spam_threshold` przed przejściem do SPAM
