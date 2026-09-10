# Fix 1: DPI / skalowanie Windows

## Problem
`SetProcessDpiAwareness` wywoływane w `main.py`, ale w skompilowanym .exe (Nuitka) może nie zadziałać przed inicjalizacją GUI. W efekcie:
- `GetClientRect`/`ClientToScreen` zwracają wirtualizowane współrzędne (skalowane przez DPI)
- dxcam przechwytuje w fizycznych pikselach monitora
- Region przechwytywania nie pokrywa się z oknem gry → OCR czyta złe piksele

U wspólnika scaling 100% działa, u klienta 125%/150% nie.

## Miejsce w kodzie
- `mvp/main.py:37` — wywołanie `setup_dpi_awareness()`
- `mvp/bot/capture.py:23-24` — implementacja

## Rozwiązanie
1. Dodać manifest DPI-aware do builda Nuitka (żeby Windows ustawił DPI-awareness zanim Python załaduje moduły)
2. Wywołać `SetProcessDpiAwareness` na samym początku `main.py`, zanim jakikolwiek import GUI

## Kroki
- [ ] Sprawdzić jak Nuitka buduje .exe (build.ps1)
- [ ] Dodać manifest DPI-aware
- [ ] Przenieść setup_dpi_awareness przed importy GUI
- [ ] Test na maszynie ze skalowaniem 125%/150%