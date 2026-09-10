> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Problem 5+6: Zawieszanie się programu i nieprawidłowe czasy reakcji

## Status: ZDIAGNOZOWANE

## Objawy klienta
- "zawieszanie się programu"
- "nieprawidłowe czasy reakcji"

## Przyczyny zawieszania

### 1. Blokujące join na wątku GUI
Plik: `mvp/gui/main_window.py:730` + `mvp/bot/runner.py:376`
```python
# main_window.py — klik STOP
self.bot_runner.stop()
# runner.py — stop() czeka na wątek
self._thread.join(timeout=2.5)
```
GUI zamiera do 2.5s przy każdym STOP.

### 2. Start czeka do 35s na EasyOCR
Plik: `mvp/bot/runner.py:212`
```python
ocr_prewarm.join(timeout=35)
```

### 3. camera.grab() bez timeoutu — realne zamrożenie
Plik: `mvp/bot/capture.py:77`
```python
frame = camera.grab(region=region)
```
DXGI grab może blokować bezterminowo przy zminimalizowanym oknie / utracie dostępu.

### 4. Potencjalny deadlock
Plik: `mvp/bot/capture.py:172-181`
`release()` i `create()` pod lockiem — jeśli grab wiszący, deadlock.

## Przyczyny nieprawidłowych czasów

### 1. Znacznik czasu przed grabem
Plik: `mvp/bot/macro_engine.py:1174-1177`
```python
grab_mono = time.monotonic()
frame = self.capture.grab()
```
Jeśli grab trwa 200ms, oszacowanie T0 jest przesunięte w przeszłość → spam za wcześnie.

### 2. Zamrożone T0 przy identycznych odczytach
Plik: `mvp/bot/macro_engine.py:1042-1043`
```python
if value != last_known_value:
    estimated_t0_mono = new_t0
```
Gdy OCR zwraca tę samą wartość, T0 nie jest aktualizowany — zostaje z opóźnieniem z pierwszego odczytu.

### 3. Sleep Event.wait ~15.6ms + Bezier 15-75ms
Plik: `mvp/bot/macro_engine.py:1117-1124` + `clicker.py:419-426`
Pierwszy klik następuje 15-75ms po progu, przy t0_lead_time=0.3s to 5-25% okna.

### 4. Spam za wcześnie przy zniknięciu timera
Plik: `mvp/bot/macro_engine.py:1072-1078`
Przy timer=3s faza spam włączana natychmiast, bez t0_lead_time — spam może się skończyć przed pojawieniem skrzynki.

## Następny krok
Naprawić kolejno: grab timeout, T0 znacznik po grab, Event.wait → spin/sleep precyzyjny, weryfikacja zniknięcia timera.