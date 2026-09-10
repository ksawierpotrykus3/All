# Research — input injection i integralność procesów (Windows)

## Kontekst (co wiemy, bez wnioskowania)
- Aplikacja Windows (Nuitka) wysyła zdarzenia myszy przez SendInput do okna gry (sendinput_backend.py:148-155). Zdarzenia klawiatury nie są używane (jest zdefiniowana struktura KEYBDINPUT, ale brak metod key_down/key_up).
- Przy wykryciu różnicy poziomów integralności (UIPI) zapisywane jest tylko ostrzeżenie w logu; aplikacja kontynuuje (runner.py:192-198).
- Skróty instalatora nie wymagają uprawnień administratora (installer.iss:52-54); sam instalator wymaga admina (PrivilegesRequired=admin).
- W repo jest skrypt instalujący sterownik Interception (scripts/install_interception.ps1), ale backend bota rejestruje wyłącznie SendInputBackend (input/backend.py:11-13).

## Pytanie badawcze (otwarte)
Jak działa blokada UIPI między procesami o różnym poziomie integralności na Windows, kiedy faktycznie uniemożliwia SendInput do okna gry, i jakie są wszystkie realne opcje rozwiązania (wymuszenie admina, sterownik, inne API)?

## Czego szukać (bez zakładania odpowiedzi)
- Dokładne warunki, w których SendInput jest odrzucany (czy zawsze, czy tylko niektóre gry/okna).
- Porównanie wymuszenia admina (manifest requireAdministrator) vs sterownik (Interception) vs inne podejścia — wady, zalety, ryzyka.
- Czy PostMessage/SendMessage mają inne zachowanie niż SendInput przy UIPI.
- Jak wykryć poziom integralności procesu docelowego z Pythona.

## Uwaga metodologiczna
Nie zakładaj, że wymuszenie admina jest jedynym lub najlepszym rozwiązaniem. Zbierz trade-offy dla minimum 2 podejść i podaj, które jest najprostsze w utrzymaniu przy sprzedaży wielu klientom.