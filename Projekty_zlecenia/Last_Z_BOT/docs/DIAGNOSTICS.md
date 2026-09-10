# Przewodnik Diagnostyki

## Przegląd

LastZBot dostarcza trzy wyjścia diagnostyczne do rozwiązywania problemów z budowaniem i działaniem systemu w runtime.

## 1. Build Trace Log (dist/build-trace.json)

Generowany podczas wykonania **build.ps1**. Zawiera wszystkie kroki budowania ze znacznikami czasu.

### Zawartość
- Stan pobierania zależności vendor (pobrane, cache hits)
- Próby kompilacji Cython
- Postęp budowania Nuitka
- Generowanie instalatora
- Wyniki sprawdzenia zdrowotności

### Użycie
```bash
cat dist/build-trace.json | python -m json.tool | less
```

### Przykładowy wpis
```json
{
  "timestamp": "2026-01-15T12:00:00.000Z",
  "level": "INFO",
  "message": "Nuitka build completed",
  "duration_seconds": 150,
  "output_name": "LastZBot.exe"
}
```

## 2. Runtime Initialization Log (mvp/runtime_init.json)

Generowany gdy **LastZBot.exe** się uruchamia. Loguje sekwencję inicjalizacji.

### Zawartość
- Ładowanie pliku konfiguracyjnego
- Detekcja silnika OCR (WinOCR / RapidOCR)
- Inicjalizacja modelu RapidOCR (fallback)
- Status weryfikacji licencji
- Import modułów

### Użycie
```bash
tail -f mvp/runtime_init.json  # Obserwacja na żywo
cat mvp/runtime_init.json | python -m json.tool  # Pełny widok
```

## 3. Post-Install Health Check

Uruchom po ukończeniu instalatora, aby sprawdzić poprawność środowiska.

### Użycie
```powershell
.\mvp\build\health-check.ps1
```

### Sprawdzenia
- Silnik OCR dostępny (WinOCR lub RapidOCR)
- Modele RapidOCR obecne (fallback)
- Plik executable aplikacji gotowy

### Przykładowy wynik
```
=== Post-Install Health Check ===

Checking OCR engine...
  ✓ WinOCR available (Windows.Media.Ocr)
  ✓ RapidOCR fallback ready

Checking application startup...
  ✓ Application executable found

=== Health Check Complete ===
✓ All checks passed
```

## Rozwiązywanie problemów

### Build nie powiódł się - sprawdź dist/build-trace.json
```bash
grep "ERROR" dist/build-trace.json
```

### Aplikacja nie uruchamia się - sprawdź mvp/runtime_init.json
```bash
grep "WARN\|ERROR" mvp/runtime_init.json
```

### Health Check nie powiedzie się
Uruchom health-check.ps1, aby zidentyfikować brakujące zależności (silnik OCR, modele RapidOCR itp.)
```powershell
.\mvp\build\health-check.ps1
```
