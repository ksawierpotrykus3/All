# Problem 1: F6/START nie uruchamia bota

## Status: ZDIAGNOZOWANE (potwierdzone w kodzie)

## Objaw
Klient: "po uruchomieniu i wydaniu polecenia START/F6 nie rozpoczyna jednak prawidłowo działania"

## Przyczyna
Wersja PROD ma pusty `backend_url` i `license_key` w config.json. Po naciśnięciu F6 bot najpierw sprawdza licencję, dostaje błąd i zatrzymuje się przed startem.

## Dowody (kod)

### 1. F6 → _on_start_stop() → sprawdza licencję ZANIM cokolwiek ruszy
Plik: `mvp/gui/main_window.py`, linie 700-704:
```python
if not self.bot_runner.is_running and not self._is_starting_bot:
    self.config.backend_url = str(dpg.get_value("backend_url")).strip()
    self.config.license_key = str(dpg.get_value("license_key")).strip()
    if not self._license_ok():
        return   # ← TUTAJ bot NIE startuje
```

### 2. _license_ok() łapie wyjątek i zwraca False
Plik: `mvp/gui/main_window.py`, linie 772-783:
```python
def _license_ok(self) -> bool:
    try:
        check_license(self.config.backend_url, self.config.license_key, get_hwid())
        ...
        return True
    except Exception as exc:
        ...
        return False
```

### 3. validate_license() rzuca błąd przy pustym configu
Plik: `mvp/license.py`, linie 81-82:
```python
if not backend_url or not license_key:
    raise LicenseError("Missing backend_url or license_key in config.json")
```

### 4. config.json PROD ma puste pola
Plik: `config.json`, linie 37-38:
```json
"backend_url": "",
"license_key": ""
```

## Rozwiązanie
Wysłać klientowi wersję DEV (`LastZBot-Dev-Setup.exe`), która ma BUILD_MODE='dev' i pomija walidację licencji.

Dowód: `mvp/license.py`, linia 112:
```python
if is_dev_mode():
    logger.info("DEV mode: skipping license validation (build mode)")
    return
```

## Status dla klienta
Wersja DEV wysłana w paczce `LastZBot_package.rar` (folder DEV). Klient ma ją przetestować.