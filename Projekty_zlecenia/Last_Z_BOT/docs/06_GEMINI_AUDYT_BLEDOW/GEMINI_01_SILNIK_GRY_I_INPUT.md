# GEMINI AUDYT CZĘŚĆ 1: SILNIK INPUTU I INTEGRACJA Z UNITY
**Plik audytowany:** `mvp/bot/input/sendinput_backend.py`, `mvp/bot/clicker.py`  
**Wymagania inżynierii wstecznej:** `AGENTS.md` (Sekcja ograniczeń silnika gry Unity 60 FPS)

---

## 1. BŁĄD KRYTYCZNY: Doklejanie flagi `MOUSEEVENTF_MOVE` do `spam_down` i `spam_up`

### Dowód w kodzie
Plik: `mvp/bot/input/sendinput_backend.py:187-199`

```python
    def spam_down(self, x: int, y: int) -> None:
        nx, ny = self._to_normalized_coords(x, y)
        flags = (
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTDOWN
        )
        self._send_fast(flags, dx=nx, dy=ny)

    def spam_up(self, x: int, y: int) -> None:
        nx, ny = self._to_normalized_coords(x, y)
        flags = (
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTUP
        )
        self._send_fast(flags, dx=nx, dy=ny)
```

### Mechanizm awarii w Unity
1. W systemie Windows wysłanie `MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN` powoduje umieszczenie w kolejce komunikatów zdarzenia ruchu kursora **równocześnie** ze zmianą stanu przycisku myszy.
2. W silniku Unity (klasa `BitBenderGames.MobileTouchCamera` oraz `EventSystem`):
   - Każde wciśnięcie połączone ze zmianą pozycji jest traktowane jako zdarzenie typu `TouchPhase.Moved` (początek gestu przeciągania mapy).
   - W Unity flaga `eligibleForClick` zostaje natychmiast ustawiona na `false`.
   - Zamiast rejestracji kliknięcia w skrzynkę / kafelek terenu, silnik gry zaczyna **przesuwać kamerę świata**.
3. **Złamanie zasady architektonicznej (AGENTS.md Reguła 2):**
   *Zasada bezwzględna:* `DOWN` i `UP` muszą odbywać się na dokładnie tych samych współrzędnych ($\Delta r = 0$). W trakcie wciśnięcia ruch myszy jest **surowo zabroniony**.

---

## 2. [SKORYGOWANE 2026-09-03] Szum pozycyjny `_noise_offset()` — dwa osobne progi

> **KOREKTA:** Poniższa pierwotna diagnoza myliła dwa niezależne filtry silnika. Szum 2.5–3.0 px generowany w `spam_move` (przerwa UP, state=0) **NIE** powoduje ucieczki kamery — to flaga `MOUSEEVENTF_MOVE` w `spam_down`/`spam_up` (sekcja 1) była źródłem drgań. Właściwy podział progów:
> - `MobileTouchCamera` ~1.5 px — ruch **w trakcie** trzymania → drag kamery.
> - `ClickDetector` ~5.0 px + 300 ms — dystans **między** kliknięciami → poniżej progu skleja spam w jeden gest.
>
> Poprawne rozwiązanie (wdrożone): usunąć `MOVE` z `spam_down/up`, a separację ≥5 px realizować ruchem `spam_move` wyłącznie przy zwolnionym przycisku. Szum w `_noise_offset()` **musi** dawać dystans ≥5 px, a nie <1.5 px jak pierwotnie zalecano.

### Historyczna (błędna) diagnoza

### Dowód w kodzie
Plik: `mvp/bot/clicker.py:440-444`

```python
    def _noise_offset(self) -> tuple[float, float]:
        self._noise_sign *= -1
        amp = random.uniform(2.5, 3.0)
        off = self._noise_sign * amp
        return off, off
```

Oraz w pętli spamu (`clicker.py:310-313`):
```python
    ox, oy = self._noise_offset()
    tx = int(x + ox)
    ty = int(y + oy)
    backend.spam_move(tx, ty)
```

### Mechanizm awarii
- Wektor przesunięcia wynosi $(+2.5, +2.5)$ lub $(-2.5, -2.5)$ px.
- Dystans euklidesowy: $\Delta d = \sqrt{2.5^2 + 2.5^2} = 3.535\text{ px}$.
- Silnik kamery Unity (`MobileTouchCamera`) posiada próg martwej strefy (drag threshold) na poziomie **$\approx 1.5\text{ px}$**.
- Przesunięcie o $3.5\text{ px}$ w trakcie cyklu klikania przekracza próg martwej strefy, co powoduje ucieczkę kamery z widoku skrzynki na losowe pole terenu.

---

## 3. BŁĄD POWAŻNY: Brak uwzględnienia bezwzględnego minimum `T_period >= 26.0 ms` w trybie DEV / custom CPS

### Dowód w kodzie
Plik: `mvp/bot/clicker.py:471-487` oraz `mvp/config.py:36`

```python
    def _target_cps(self, clicks_per_sec: int | None) -> float:
        cps = float(clicks_per_sec) if (clicks_per_sec and clicks_per_sec > 0) else 38.46
        if self._input_fps_mode == "60":
            cps = min(cps, self._max_cps_60fps)
        return cps
```

W `config.py` domyślny `input_fps_mode` to `"60"`, ale w `Clicker.__init__` domyślny `input_fps_mode` to `"60"`, a fallback to `"200"` (`clicker.py:105`).
Jeśli `input_fps_mode == "200"`, kod generuje kliknięcia z czasem `hold_s = 3ms` i okresem $< 25\text{ ms}$.
Na niezmodyfikowanym kliencie gry klasa `ClickIntervalMonitor` posiada próg **`_threshold = 25.0 ms`** i wywołuje `ReportFastClick()`, po czym serwer odrzuca 59 na 60 pakietów `get.treasure.info`.

---

## 4. BŁĄD POWAŻNY: Normalizacja współrzędnych w `SendInput` (65536 vs 65535)

### Dowód w kodzie
Plik: `mvp/bot/input/sendinput_backend.py:120-134`

```python
    def _to_normalized_coords(self, x: int, y: int) -> tuple[int, int]:
        ...
        nx = int(((int(x) - v_left) * 65536) / v_width)
        ny = int(((int(y) - v_top) * 65536) / v_height)
        return max(0, min(nx, 65535)), max(0, min(ny, 65535))
```

### Problem techniczny
W specyfikacji Win32 API dla `MOUSEEVENTF_ABSOLUTE`, koordynaty $0$ i $65535$ mapują się na skrajne piksele:
$\text{Normalized} = \frac{X \times 65535}{\text{Width} - 1}$.
Użycie mnożnika $65536$ i dzielnika $\text{Width}$ bez odjęcia $1$ powoduje akumulację błędu zaokrągleń (off-by-one / truncation error), co przy precyzyjnym klikaniu w małe przyciski (np. strzałka czatu, ikona skrzynki) powoduje trafianie w krawędź kafelka.
