# LORE — zlecenie TG Coders (helikopter / OCR / Android)

## Co to za zlecenie (stan faktyczny)

Zleceniodawca: TG Coders (kontakt: Martyna Mleczko, martyna.m@tgcoders.pl).
Budzet: 10-12 tys. PLN, rozliczenie ETAPOWE, nie godzinowe.
Dni pracy: 21 (z ogloszenia).
Prawa autorskie: przeniesienie.

Realny zakres (doprecyzowany przez klienta w mailu, NIE to co w ogloszeniu):
- Przejecie i analiza istniejacego kodu aplikacji Android w Kotlinie.
- Sprawdzenie poprawnosci obecnych funkcji.
- Poprawa bledow wykrytych w testach.
- Dodanie DWOCH nowych parametrow do istniejacego mechanizmu obliczen.
- Przygotowanie stabilnej wersji do dalszych testow.
- Aplikacja analizuje w czasie rzeczywistym to, co wyswietla sie na ekranie telefonu:
  przechwytywanie ekranu (MediaProjection) + OCR, przetwarzanie odczytanych danych
  i prezentacja wynikow uzytkownikowi.
- Klient wprost mowi: dodatkowy atut to OCR, Accessibility Services, przechwytywanie ekranu.

Wazne rozjazdy wzgledem ogloszenia:
1. Ogloszenie mowilo o "usprawnianiu przejazdow" i "wyliczeniach". Realnie to analiza
   ekranu + OCR. Nasza oferta pytala o integracje z Uberem - to bylo chybione, bo
   klient zmienil/rozszerzyl zakres po wystawieniu ogloszenia.
2. Ogloszenie: budzet 10k. Klient w mailu: 10-12k, etapowo.
3. Ogloszenie: "dokonczenie aplikacji". Realnie: pelne przejecie projektu.

## Czego klient chce od nas TERAZ

Klient jest na etapie WERYFIKACJI technicznej, zanim cokolwiek dalej.
Konkretnie prosi o:
- link do GitHuba,
- przykladowe repo lub fragment kodu w Kotlinie,
- cokolwiek, co pozwoli jego zespolowi ocenic organizacje kodu i znajomosc Kotlin/Android,
- moze to byc projekt testowy, nie musi byc komercyjny,
- po weryfikacji: ustalenia, umowa, potem kod zrodlowy i pelny zakres techniczny,
- dalsza korespondencja MAILEM na martyna.m@tgcoders.pl.

## Co realnie mamy do pokazania

### A) Repo Android/Kotlin (mocne, ale nie o OCR)
https://github.com/MaXDev-CATHODE/ThingSpeak-monitor-widget-apk
Wlasciciel: wspolnik (MaXDev-CATHODE), nie my bezposrednio.
Stack: Kotlin, Jetpack Compose, Clean Architecture (MVI/MVVM), Hilt, Room, WorkManager,
Retrofit/OkHttp, Kotlin Serialization, Jetpack Glance (widgets), MPAndroidChart,
Material 3, CI/CD GitHub Actions, fastlane.
Co pokazuje: solidny warsztat Android/Kotlin, architektura, praca z danymi w tle,
reactive UI, cache, pipeline. Domenowo: monitoring danych (ThingSpeak IoT).
Czego NIE pokazuje: OCR, MediaProjection, Accessibility Services, screen capture.
Uwaga na smieci w repo: build_log.txt, build_log3.txt, build_output_check.txt,
build_stacktrace.txt, docs/ai_audit - to wyglada na AI-assisted dev. Do rozwazenia
sprzatanie przed pokazaniem.

### B) Bot desktopowy z OCR (mocne pod OCR, ale ryzykowne)
https://github.com/ksawierpotrykus3/All -> Projekty_zlecenia/Last_Z_BOT
To jest DOKLADNIE ten projekt ze zlecenia "Silnik bota + panel lokalny (10 500 PLN)"
+ "Backend licencyjny (4 500 PLN)", ktore mielismy gdzie indziej.
Co realnie jest w srodku (potwierdzone w config.json i AUDIT_REPORT.md):
- Proces docelowy: Survival.exe (bot do gry), scan_fps 30, spam 29 CPS,
  anti_detect_enabled: true, prevent_sleep, backend_url + license_key.
- OCR na serio: pipeline dwuwarstwowy Windows.Media.Ocr (WinRT, 13-17 ms)
  + RapidOCR (PP-OCR v4 / ONNX, ~32 ms), z regula importu onnxruntime przed winrt.
- Detekcja zdarzen: template matching / OCR na przechwytywanym obszarze,
  adaptacyjne interwaly OCR (1.0 s -> 0.2 s), countdown lock, hysteresis,
  obsluga skokow licznika (>2 s), T0 z sygnalu sieciowego \x58\x01.
- Inzynieria: 173 testy (property-based, Hypothesis), checkpointy z atomowym zapisem,
  thread-safety, error handling, recovery.
- Backend licencyjny: FastAPI + SQLite + JWT + Stripe (subskrypcje, webhooki),
  endpoint walidacji licencji (403 = blokada), przygotowany pod PostgreSQL.
RYZYKO: to bot do gry z antydetekcja. Szara strefa, lamanie ToS. Nie linkowac
tego do TG Coders. Mozna co najwyzej slownie wspomniec o doswiadczeniu z OCR
i screen capture z projektow desktopowych, bez domeny i bez linku.

### C) Inne repo uzytkownika (NIE pokazywac)
- ksawierpotrykus3/deep - proxy do DeepSeek z pula kont, solver PoW,
  CloudflareBypasser.py. Szara strefa, nie linkowac.
- ksawierpotrykus3/useme - automatyzacja Useme (ai_pipeline, browser_driver,
  chain_executor). Nie linkowac do tego zlecenia.

## Strategia

1. Do TG Coders wysylamy TYLKO repo ThingSpeak (Android/Kotlin).
2. OCR/screen capture wspominamy SLOWNIE jako doswiadczenie desktopowe (Python/Windows),
   bez linku, bez domeny, bez "gry" i bez "anty-detekcji".
3. Proponujemy krotkie zadanie techniczne na ich kodzie - przenosi ciezar
   z portfolio na praktyke, a oni i tak chca weryfikacji.
4. Repo "All" / Last_Z_BOT mozemy ewentualnie pokazac POZNIEJ, jesli zajdzie potrzeba,
   ale najpierw trzeba je posprzatac (usunac anty-detect, nazwy procesu gry,
   artefakty AI, logi, .coverage, transkrypcje sesji).
5. Budzet: 10-12k etapowo. Mozemy negocjowac podzial na etapy, bo zakres sie zmienil,
   ale delikatnie, bo klient sam podniosl budzet.

## Otwarte pytania / decyzje

- Czy sprzatamy repo ThingSpeak przed wyslaniem? (build_logi, ai_audit)
- Czy przygotowujemy wyodrebniony, czysty modul OCR z Last_Z_BOT do pokazania?
- Kto jest "imieniem" do podpisu w mailu (duet).
- Czy akceptujemy rozliczenie etapowe (tak/nie) i jak dzielimy etapy.

## Sciezki lokalne

- Ten folder: C:\Users\buchh\projects\tgcoders_helikopter
- Workspace projektow: C:\Users\buchh\projects
- Powiazane lokalnie: C:\Users\buchh\projects\useme (automatyzacja Useme),
  C:\Users\buchh\projects\deep (proxy DeepSeek)