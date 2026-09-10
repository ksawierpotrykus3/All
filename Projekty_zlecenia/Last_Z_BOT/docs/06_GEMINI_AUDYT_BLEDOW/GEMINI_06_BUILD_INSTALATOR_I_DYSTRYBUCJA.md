> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# GEMINI AUDYT CZĘŚĆ 6: PAKIETOWANIE, INSTALATOR I INTEGRACJA SYSTEMU WINDOWS
**Pliki audytowane:** `mvp/build/installer.iss`, `mvp/build/build.ps1`, `mvp/bot/runner.py`, `mvp/bot/ocr.py`

---

## 1. BŁĄD KRYTYCZNY: Brak elewacji UAC i cicha blokada kliknięć przez Windows UIPI

### Dowód w kodzie
Plik: `mvp/build/installer.iss:23, 53-54, 82`

```pascal
PrivilegesRequired=admin
...
[Icons]
Name: "{autodesktop}\LastZBot"; Filename: "{app}\LastZBot.exe"; WorkingDir: "{app}"
...
[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; ... Flags: ... runasoriginaluser
```

Plik: `mvp/bot/runner.py:189-201`
```python
    from mvp.bot.window_finder import check_uipi_elevation_mismatch
    if check_uipi_elevation_mismatch(self.config.process_name):
        logger.warning("UIPI WARNING: The game process runs with Administrator privileges...")
```

### Mechanizm awarii
1. Większość gier PC oraz emulatorów Androida (BlueStacks, LDPlayer, Nox) domyślnie wymaga i uruchamia się z uprawnieniami **Administratora** (High Integrity Level).
2. Instalator Inno Setup tworzy skrót do `LastZBot.exe` bez wymuszenia elewacji administratora (brak manifestu `requireAdministrator`).
3. Mechanizm zabezpieczeń Windows — **UIPI (User Interface Privilege Isolation)** — bezwzględnie blokuje komunikaty myszy i klawiatury (`SendInput`, `PostMessage`, `WM_MOUSEWHEEL`) wysyłane z procesów o niższym poziomie uprawnień (Standard User) do procesów o wyższym poziomie (Administrator).
4. Skutek:
   - Bot nie zgłasza żadnego błędu w GUI, loguje „DOWN @(x,y)”, ale **w grze nic się nie klika**.

---

## 2. BŁĄD POWAŻNY: Zmienne środowiskowe HKLM a pierwsze uruchomienie z pulpitu

### Dowód w kodzie
Plik: `mvp/build/installer.iss:64-74`

```pascal
[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueName: "TESSERACT_CMD"; ValueData: "{autopf}\Tesseract-OCR\tesseract.exe"
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueName: "EASYOCR_MODULE_PATH"; ValueData: "{app}"
```

### Mechanizm awarii
1. Zapisanie zmiennych środowiskowych do klucza maszynowego `HKLM` staje się widoczne dla procesów użytkownika **dopiero po restarcie systemu lub ponownym zalogowaniu**.
2. Jeśli użytkownik po instalacji zamknie program i uruchomi go bezpośrednio ze skrótu na Pulpicie (`LastZBot.exe`), proces Explorera nie przekazuje nowych zmiennych `EASYOCR_MODULE_PATH` ani `TESSERACT_CMD`.
3. Skutek:
   - Moduł OCR (`ocr.py:23, 73`) nie może zlokalizować zainstalowanego silnika Tesseract ani wag modeli EasyOCR w `{app}\model`.
   - EasyOCR próbuje w tle pobierać modele z Internetu (`github.com/JaidedAI`), co przy braku połączenia lub wolnym łączu powoduje zamrożenie bota na 30–60 sekund lub błąd `URLError`.

---

## 3. BŁĄD POWAŻNY: Nuitka Onefile bez certyfikatu (Blokady SmartScreen i Antywirusa)

### Dowód w kodzie
Plik: `mvp/build/build.ps1:100-105`

Kompilacja Nuitka w trybie onefile (`--onefile --standalone --enable-plugin=torch`) generuje pojedynczy plik binarny PE o rozmiarze ok. **270 MB**.
- Plik nie jest podpisywany cyfrowo certyfikatem Code Signing.
- Windows Defender oraz antywirusy firm trzecich (Avast, Norton, Bitdefender) klasyfikują tak duże, niepodpisane pliki wykonywalne Nuitki jako zagrożenie heurystyczne (*Trojan:Win32/Wacatac* lub *Generic Heuristic*).
- Antywirusy po cichu blokują rozpakowywanie bibliotek PyTorch do folderu tymczasowego `%TEMP%`, co skutkuje „cichym ubiciem” procesu bota po kliknięciu Start.
