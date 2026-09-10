# Extended Game Simulator Framework — Design Document

**Data:** 2 września 2026  
**Status:** Design Complete  
**Zakres:** Kompleksowy framework do testowania pełnej pętli gry (alert → klik → skan czatu) z inter​aktywnym UI, wariantami testów, pomiarami metryk i raportami analitycznymi.

---

## 1. Przegląd Architektury

Framework składa się z 3 głównych komponentów:

### 1.1 SimulationEngine
- **GameStateManager**: Zarządza stanem gry (chat, alert_animation, treasure, scanning)
- **VariantExecutor**: Aplikuje warianty testowe (czystość czatu, CPU load, timing alertu)
- **MetricsCollector**: Zbiera metryki w real-time (latency, accuracy, CPU, OCR confidence)
- **BotIntegrationLayer**: Komunikacja z MVP botem, kalibracja OCR, log kliknięć

### 1.2 InteractiveUI (Tkinter)
- **Left Panel**: Wizualizacja stanu gry (canvas z alertami, ROI boxami, animacją)
- **Right Panel**: Dashboard metryk (accuracy gauge, latency meter, CPU monitor, state indicator)
- **Bottom Panel**: Timeline zdarzeń (fazy iteracji z timestampami ms)
- **Overlay**: Kontrolki (Pause, Skip, Perturb), hotkeys (Space, P, R, C, S)

### 1.3 ReportingEngine (matplotlib + pandas)
- **Heatmaps**: Rozkład kliknięć, OCR confidence po wariantach, latency distribution
- **Timelines**: Wykres faz per iteracja, CPU/Memory trend, OCR confidence trend
- **Comparisons**: Wariant A vs B, różne CPS, before/after optimizacji
- **Trend Analysis**: Accuracy over time, degradation under load, anomaly detection

---

## 2. Single Iteration Loop — 6 Faz

Każda iteracja przechodzi przez standardowy cykl:

### Phase 1: Setup (~100ms)
- Aplikuj wariant: zmień obraz czatu, ustaw CPU load, zmodyfikuj timer
- Log: [SETUP] Variant applied: chat_state=cluttered, cpu_load=medium, alert_delay=0ms

### Phase 2: Alert (~1-5s)
- Pokaż alert animację (spada z góry)
- Bot wykonuje OCR, mierz detection time
- Log: [ALERT] Alert shown | OCR Confidence: 92% | Detection time: 145ms

### Phase 3: Click (~50-200ms)
- Bot wysyła klik do symulatora
- Weryfikuj trafienie (hit/miss)
- Mierz latency (OCR done → click received)
- Log: [CLICK] Latency: 78ms | Hit: YES

### Phase 4: Treasure (~500ms)
- Symuluj otwieranie skrzynki
- Mierz CPU spike (OCR + animacja)
- Log: [TREASURE] CPU spike: 45%

### Phase 5: Chat Scan (~1-2s)
- Powróć do widoku czatu
- Weryfikuj pozycję bota (czy wróć do chat state?)
- OCR confidence dla czatu
- **KRYTYCZNE**: Jeśli bot nie wróci do czatu — FAIL, zapisz anomalię
- Log: [CHAT_SCAN] Chat recovered in 890ms | OCR: 87% | State: ✓ chat

### Phase 6: Metrics (~50ms)
- Agreguj wszystkie dane z faz 1-5
- Zapisz do iteracji logu
- Aktualizuj dashboard w UI
- Log: [METRICS] Iteration #5 complete | Acc: 80% (4/5) | Avg Latency: 95ms ± 18ms

**Ważne:** Jeśli iteracja przejdzie, licznik accuracy się zwiększa. Jeśli fail (chat recovery error), licznik anomalii.

---

## 3. Test Variants — Macierz Scenariuszy

Użytkownik wybiera kombinację wariantów z macierzy poniżej. Framework testuje każdą kombinację jako oddzielną "konfigurację przebiegu".

| Wymiar | Opcje | Opis |
|--------|-------|------|
| **Chat Cleanliness** | clean, cluttered, spam | Stan czatu na ekranie |
| **Heli Visibility** | visible, hidden, partial | Czy heli jest widoczna podczas alertu |
| **System Load** | idle, medium, high | Sztuczny CPU load w tle |
| **Alert Timing** | immediate, delayed, overlapped | Opóźnienie/timing alertu |
| **Bot Config** | 30_cps, 38_cps, aggressive | Różne CPS oraz hold_ms z AGENTS.md |
| **Eye Tracking** | focused, distracted, loss_event | Symulacja stanu śledzenia oczu |

Każda kombinacja = jeden "run variant". Użytkownik może uruchomić N iteracji dla każdego wariantu.

---

## 4. Interactive UI — Layout i Kontrolki

### Layout (Tkinter root window, 1400x900):

\\\
┌──────────────────────────────────────────────────────────────────┐
│  Extended Game Simulator Framework — Session: variant_set_1       │
├─────────────────────────────────────────┬──────────────────────────┤
│                                         │                          │
│   [Game Canvas]                         │  [Metrics Dashboard]     │
│   600x700px                             │  400x700px               │
│   - Alert animation                     │  ┌──────────────────┐    │
│   - ROI boxes (green/red)               │  │ 🎯 Accuracy      │    │
│   - Chat/Treasure/Scanning states       │  │ 80% (4/5)        │    │
│   - State label at bottom               │  │                  │    │
│                                         │  │ ⏱️  Avg Latency  │    │
│                                         │  │ 95ms ± 18ms      │    │
│                                         │  │                  │    │
│                                         │  │ 💾 CPU (OCR)     │    │
│                                         │  │ [████░░░░] 45%   │    │
│                                         │  │                  │    │
│                                         │  │ 🟢 State: chat   │    │
│                                         │  │                  │    │
│                                         │  │ Variant: clean   │    │
│                                         │  │ CPS: 38          │    │
│                                         │  │ Load: medium     │    │
│                                         │  └──────────────────┘    │
│                                         │                          │
├─────────────────────────────────────────┴──────────────────────────┤
│ [Timeline Events] (scrollable, height: 150px)                      │
│ [00:00] Setup → [00:05] Alert → [00:12] OCR:92% → [00:15] Click   │
│ → [00:17] Hit! → [00:50] Chat Recovery ✓                           │
├─────────────────────────────────────────────────────────────────────┤
│ Controls: [Pause] [Skip] [Perturb▼] | Hotkeys: Space=Alert P=Pause │
│ R=Reset C=Change_Variant S=CPU_Spike Q=Quit                        │
└─────────────────────────────────────────────────────────────────────┘
\\\

### Hotkeys:
- **Space**: Wyzwól alert ręcznie (perturbacja)
- **P**: Pause/Resume iteracji
- **R**: Reset bieżącej iteracji
- **C**: Change variant on-the-fly (dialog)
- **S**: Trigger CPU spike (perturbacja)
- **Q**: Quit session (save data)

### Perturbations (Menu Perturb):
- Block clicks for N seconds
- Inject CPU spike (simulate high load)
- Change chat state mid-iteration
- Delay alert by N milliseconds
- Add OCR noise (lower confidence artificially)

---

## 5. Metryki — Co się mierzy

### Per-Iteration Metrics:
\\\python
{
    "iteration": 5,
    "variant": "cluttered_38cps_medium_load",
    "phase_1_setup_ms": 98,
    "phase_2_alert_detection_ms": 145,
    "phase_3_click_latency_ms": 78,
    "phase_3_hit": true,
    "phase_4_cpu_spike_percent": 45,
    "phase_5_chat_recovery_ms": 890,
    "phase_5_ocr_confidence": 0.87,
    "phase_5_state_verified": true,  # czy bot wróć do chat?
    "total_iteration_ms": 1356,
    "cpu_avg": 42,
    "ram_mb": 256
}
\\\

### Aggregated Session Metrics:
\\\python
{
    "session_id": "2026-09-02_14-35-12",
    "variant_config": {
        "chat_state": "cluttered",
        "heli_visible": true,
        "system_load": "medium",
        "bot_cps": 38,
        "eye_tracking": "focused"
    },
    "iterations_total": 100,
    "iterations_hit": 80,
    "accuracy_percent": 80.0,
    "accuracy_p95": 95.0,  # w top 5% sesji
    "latency_avg_ms": 95,
    "latency_std_ms": 18,
    "latency_p95_ms": 145,
    "latency_p99_ms": 189,
    "cpu_spike_max_percent": 62,
    "cpu_spike_avg_percent": 42,
    "reliability_percent": 98.0,  # % bez chat recovery errors
    "chat_recovery_failures": 2,
    "anomalies": [
        {"iteration": 23, "reason": "Chat not recovered", "severity": "critical"},
        {"iteration": 67, "reason": "Latency outlier", "severity": "warning"}
    ],
    "ocr_confidence_trend": -2.3  # % per 10 iterations (degradation?)
}
\\\

---

## 6. Reports & Analysis (Post-Session)

Po zakończeniu sesji framework generuje raport HTML z:

### 6.1 Heatmaps:
- **Click Position Heatmap**: XY rozkład wszystkich kliknięć (czy bot trafnia zawsze w to samo miejsce?)
- **OCR Confidence Heatmap**: Którzy warianty są trudne dla OCR?
- **Latency Distribution**: Histogram — rozkład czasów reakcji
- **CPU Spike Frequency**: Czy CPU spikuje konsekwentnie w tej samej fazie?

### 6.2 Timelines:
- **Per-Iteration Timeline**: Wizualizacja N iteracji (każda to bar z fazami kolorystycznie)
- **CPU/Memory Over Time**: Krzywa CPU i RAM przez cały session
- **Accuracy Curve**: Czy accuracy spada z czasem (degradation)?
- **OCR Confidence Trend**: Trend confidency OCR

### 6.3 Variant Comparisons:
- **Table**: Wariant A vs Wariant B (kolumny: accuracy, latency, CPU, reliability)
- **CPS Comparison**: 30 CPS vs 38 CPS vs aggressive (który jest lepszy?)
- **Load Comparison**: idle vs medium vs high (jak load wpływa na accuracy?)
- **Before/After Chart**: Jeśli dostępne — optymalizacja wygenerowana wizualnie

### 6.4 Trend Analysis:
- **Accuracy Degradation**: Czy accuracy spada po wielu iteracjach? (curve fit)
- **Chat Recovery Rate**: % успешных powrotów do chatu per wariant
- **Anomaly Detection**: Outliers — które iteracje były znacząco różne?
- **Prediction**: Trend extrapolation — czy system się stabilizuje czy degrade?

---

## 7. Integracja z MVP Botem

### Bot Integration Layer:
- Czyta OCR confidence z bota (z logów lub z API)
- Słucha na kliknięcia bota (hook do mouse event'ów)
- Wysyła stan symulatora do bota (canvas frame)
- Mierzy CPU/RAM bota (psutil)

### Communication:
- Bot stream frame → Simulator (kolejka threadsafe)
- Simulator sends game state updates → Bot (hook callbacks)
- Metryki aggregated w ReportingEngine po sesji

---

## 8. Fazy Implementacji

1. **Phase 1: Core Engine** — GameStateManager, VariantExecutor, MetricsCollector
2. **Phase 2: UI Foundation** — Tkinter layout, canvas, basic controls
3. **Phase 3: Bot Integration** — BotIntegrationLayer, metrics hooking
4. **Phase 4: Interactive Controls** — Pause, skip, perturb, hotkeys
5. **Phase 5: Reporting** — Heatmaps, timelines, comparisons, trend analysis
6. **Phase 6: Polish & Optimization** — Performance tuning, edge cases, documentation

---

## 9. Ograniczenia i Założenia

- **Python 3.11+** (z uv)
- **Tkinter** — UI (built-in z Python)
- **matplotlib** — wykresy
- **pandas** — agregacja danych
- **psutil** — monitoring CPU/RAM
- **threading** — interaktywne UI bez blocking
- **Warianty** — konfiguruje się w JSON lub CLI flags
- **Obrazy** — z data/macro_testing/ (muszą istnieć)

---

## 10. Success Criteria

✓ Framework umożliwia testowanie pełnej pętli gry (alert → klik → skan)  
✓ Interaktywny UI z live metrykam i perturbacjami  
✓ Warianty testów obejmują wszystkie krytyczne scenariusze  
✓ Raporty pokazują anomalii i trendy  
✓ Bot reliability mierzalna i optymalizowalna  

---

---

## 11. Timer Animation & Responsive Macro Testing

### Timer Countdown Overlay (Critical Feature)

**Purpose:** Test macro responsiveness to dynamic visual timing cues during treasure phase.

**Implementation:**
- Location: Rendered on top of helka_scrolled.png
- Countdown: T-60 → T-0 (60 second window)
- Visual: Large digits (Arial 48pt bold) with dynamic color
  - T-60 to T-30: Green (0x00FF00)
  - T-30 to T-10: Yellow (0xFFFF00)  
  - T-10 to T-0: Red (0xFF0000)
  - T=0 expired: Blink 2Hz (Red ↔ Black)

**Metrics Collected:**
- timer_prediction_ms: ms before/after bot clicked vs timer expiry
- timer_accuracy_percent: (ideal_window - delta) / ideal_window
- timer_is_early_click: boolean
- timer_is_late_click: boolean

**Test Scenarios:**
1. Early reaction: Bot predicts timer end
2. Late reaction: Bot clicks after T-0
3. Chaotic timer: Simulated lag with jumps (±5-20s)
4. Frozen timer: Countdown halts for N seconds
5. Distracted macro: Chat visible while timer runs

### All 6 Visualization States

Framework handles complete state machine with images from macro_testing/:

| State | Image | Description | Animation |
|-------|-------|-------------|-----------|
| CHAT | 1_scan_chat_without_arrow.png | Chat view, scanning mode | None (static) |
| CHAT_FOCUS | 1_scan_chat_with_arrow.png | Chat with UI marker | Arrow pulse (eye tracking variant) |
| ALERT_ANIMATION | 1_heli_alert_appearing_in_chat.png | Alert spawn | Fade-in 0-100% over 2s, drop animation |
| TREASURE | helka_scrolled.png | Treasure opened | **Timer countdown overlay (0-60s)** |
| REWARD_DETAILS | details.png | Loot breakdown | Fade-in, text reveal |
| CHAT_UNAVAILABLE | no_chat.png | Chat blocked/loading | Pulsing red border (loss_event variant) |

### State Transitions Measured

Every transition logged with:
- source_state, target_state
- transition_time_ms
- was_expected (initiated by framework vs unexpected)
- recovery_time_ms (if error state)

**Anomaly Detection:**
- Unexpected state transitions (bot stuck in wrong state)
- State recovery failures (can't return to chat)
- Timing violations (transition too slow)

---
