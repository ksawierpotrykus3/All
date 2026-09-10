# Research — uruchamianie i dystrybucja aplikacji Nuitka na Windows

## Kontekst (co wiemy, bez wnioskowania)
- Aplikacja budowana Nuitka, obecnie `--standalone --onefile`, wynik ~270 MB.
- Instalator Inno Setup; pliki nie są podpisane cyfrowo.
- Użytkownik końcowy pobiera instalator z internetu (ryzyko SmartScreen/AV).
- W buildzie brakuje części DLL VC++ runtime (`msvcp140_2.dll`, `concrt140.dll`).

## Pytanie badawcze (otwarte)
Jakie są realne konsekwencje modelu onefile vs standalone dla aplikacji Nuitka na Windows (czas startu, skanowanie AV, aktualizacje, podpisywanie), i jakie kroki faktycznie zmniejszają ryzyko blokad AV/SmartScreen u użytkownika końcowego?

## Czego szukać (bez zakładania odpowiedzi)
- Porównanie onefile vs standalone: czas zimnego startu, zachowanie AV (czy heurystyki flagują rozpakowywanie do %TEMP%), łatwość aktualizacji delta.
- Czy i jak podpis cyfrowy wpływa na reputację SmartScreen — ile trwa budowa reputacji, jakie są realne koszty (w tym tańsze alternatywy niż EV).
- Czy zgłoszenie do Microsoft Security Intelligence faktycznie pomaga, i jaka jest procedura.
- Co jest realnie wymagane z VC++ redist dla PyTorch/OpenCV.

## Uwaga metodologiczna
Nie zakładaj, że "standalone jest lepszy". Zbierz wady i zalety obu podejść. Jeśli onefile jest akceptowalny przy podpisie i zgłoszeniu, podaj to jako opcję.