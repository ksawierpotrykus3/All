# Wsparcie systemów Windows

## Status: Wymagany Windows 10 lub nowszy

### Decyzja

Porzucamy wsparcie dla Windows 7. Powód: silnik OCR **Windows.Media.Ocr** (WinOCR) jest dostępny dopiero od Windows 10 i jest podstawą szybkiej ścieżki OCR (13–17 ms). Na Windows 7 byłby dostępny wyłącznie wolniejszy RapidOCR, co nie gwarantuje wymaganej wydajności.

### Wymagania minimalne

| System | Wspierany |
|--------|-----------|
| Windows 7 SP1 | ✗ Nie |
| Windows 10 | ✓ Tak |
| Windows 11 | ✓ Tak |

### Konsekwencje dla kodu

- Inno Setup `MinVersion=10.0`
- Warstwa `mvp/lib/windows_api_compat.py` może pozostać dla wykrywania wersji, ale nie jest już wymagana dla Win7.
- WinOCR (Windows.Media.Ocr) jest jedynym silnikiem szybkiej ścieżki OCR.
- RapidOCR pozostaje wyłącznie jako fallback awaryjny, nie jako ścieżka podstawowa.

### Do zrobienia (weryfikacja)

- [ ] Ustawić `MinVersion=10.0` w `installer.iss` i `installer-dev.iss`
- [ ] Usunąć / oznaczyć martwy kod Win7 w `windows_api_compat.py` (opcjonalnie)
- [ ] Dodać wyraźny komunikat o wymaganiu Windows 10+ w dokumentacji użytkownika