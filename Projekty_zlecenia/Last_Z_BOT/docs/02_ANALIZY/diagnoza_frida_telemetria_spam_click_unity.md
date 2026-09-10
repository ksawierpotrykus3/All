# Analiza Telemetryczna Spam Click w Silniku Unity (Frida & Il2Cpp)

> **Data badania:** 4 września 2026 r.  
> **Cel:** Pełna weryfikacja rejestracji kliknięć w pamięci gry `Survival.exe` (Unity 60 FPS, `GameAssembly.dll`), wykrywanie dławika `ClickIntervalMonitor` i weryfikacja koordynatów uderzenia.

---

## 1. Odkrycie Architektoniczne: Pętla Wejścia Unity w `Survival.exe`

Podczas profilowania wywołań Win32 API wewnątrz procesu `Survival.exe` (PID 10956) zmierzono częstotliwości zapytań:

```json
{
  "GetCursorPos": 60,
  "GetAsyncKeyState": 1082,
  "PeekMessageA": 60,
  "PeekMessageW": 0,
  "DispatchMessageW": 0
}
```

### Wnioski:
1. **Gra całkowicie pomija kolejki Unicode `DispatchMessageW` oraz `PeekMessageW` (0 wywołań).**
2. **Silnik Unity bada fizyczny stan myszy ponad 1000 razy na sekundę (`1082 Hz`) przez `user32.dll!GetAsyncKeyState(VK_LBUTTON = 0x01)`.**
3. Pozycję kursora silnik odpytuje w cyklu klatek (`60 Hz`) przez `user32.dll!GetCursorPos`.

---

## 2. Deasemblacja `ClickIntervalMonitor` w `GameAssembly.dll`

Zdeasemblowano metody `ClickIntervalMonitor.Update` i `ReportFastClick`:

```assembly
0x7ff8451b22c3: call 0x7ff849ddefe0        ; UnityEngine.Input.GetMouseButtonDown(0)
0x7ff8451b22c8: mov byte ptr [rbx + 0x21], al ; Stan kliknięcia
0x7ff8451b22cb: test al, al
0x7ff8451b22cd: je 0x7ff8451b2332          ; Brak kliku -> wyjście z Update()
0x7ff8451b22cf: xor ecx, ecx
0x7ff8451b22d1: call 0x7ff849d88850        ; Time.unscaledTime
0x7ff8451b22f0: subss xmm2, [rbx + 0x1c]   ; Oblicza Delta T (currentTime - lastClickTime)
0x7ff8451b22f5: comiss xmm1, xmm2          ; Porównuje Delta T z progiem 25.0 ms
0x7ff8451b2301: mov byte ptr [rbx + 0x20], 1 ; BLOKADA: isFastClick = true!
0x7ff8451b230e: call 0x7ff8450e0940        ; ReportFastClick() -> blokada pakietu get.treasure.info!
```

### Kluczowe adresy Il2Cpp:
- **`0x7ff849ddefe0`:** `UnityEngine.Input.GetMouseButtonDown(0)` — źródło prawdy o rejestracji kliknięcia w klatce Unity.
- **`0x7ff8451b22b0`:** `ClickIntervalMonitor.Update` — weryfikacja odstępu czasu.
- **`0x7ff8451b2270`:** `ClickIntervalMonitor.ReportFastClick` — zgłoszenie naruszenia i blokada nagrody.

---

## 3. Pomiary Telemetryczne Spamu Bota (Zrzut z Pamięci Gry)

Podczas testu spam click bota zarejestrowano wewnątrz `0x7ff849ddefe0` serię kliknięć:

| Metryka | Wartość zmierzona | Interpretacja |
| :--- | :--- | :--- |
| **Dostarczone kliknięcia** | **180 kliknięć** (179 interwałów) | ✅ Silnik gry zarejestrował 100% kliknięć wysłanych przez bota. |
| **Wywołania `ReportFastClick`** | **0 blokad** | ✅ Gra nie zablokowała pakietów (tempo było w 100% bezpieczne). |
| **Średni okres kliknięć** | **$\approx 32.5\text{ ms}$ ($\approx 30.8\text{ CPS}$)** | ✅ Zgodne z limitem 30 CPS ($26\text{--}38\text{ ms}$). |
| **Współrzędne uderzeń ($X, Y$)** | **$(960, 528\text{--}533)$** | ⚠️ **Uwaga: uderzenia przy $Y=52\%$ trafiały w model czołgu gracza — patrz sekcja 4.** |

---

## 4. Analiza Koordynatów: Uwaga Dotycząca Przeszkód w Polu Celu

Analiza powiększenia klatki zrzutu (`data/images/analysis/helka_chest.png`):

1. **Wysokość $Y = 51\text{--}52\%$ ($Y \approx 530\text{ px}$):**
   - W tym punkcie stoi **czołg / wojska gracza sojuszu** (`[MAVE] mut20001`) oraz świecący okrąg interakcji.
   - Spam pod koordynat `click_y = 52` może zostać przechwycony przez profil gracza lub menu armii zamiast skrzynki.

2. **Standardowy cel spamu pozostaje środek ekranu (`50%, 50%`):**
   - Domyślnym i preferowanym celem makra jest geometryczny środek zrzutu: **`click_x = 50.0%, click_y = 50.0%`** — zgodnie z Regułą 15 w `AGENTS.md`.
   - `mvp/macro_def.py` utrzymuje parametry `click_x = 50, click_y = 50`.

3. **Opcjonalna alternatywa $Y = 57\%$ ($Y \approx 580\text{--}600\text{ px}$):**
   - Dolna krawędź budynku skrzynki (oznaczona zielonym znacznikiem na klatkach zrzutu).
   - Może być rozważona **wyłącznie** wtedy, gdy w środku ekranu zostanie potwierdzona trwała przeszkoda (np. model czołgu sojuszu). Nie jest to zmiana domyślna — kod i reguła 15 pozostają przy `50%, 50%`.

---

## 5. Domyślne Interwały OCR i Wydajność Procesora

Zaktualizowano domyślne parametry w `config.json` oraz `mvp/config.py`:
- `idle_check_interval_s = 3.0s` (zamiast 0.5s — eliminacja niepotrzebnego obciążenia CPU podczas wielominutowego oczekiwania).
- `fast_check_interval_s = 0.2s` (5 Hz w fazie szybkiej).
- `fast_threshold_s = 60s` (faza szybka aktywuje się dopiero na 1 minutę przed zrzutem zamiast na 5 minut).