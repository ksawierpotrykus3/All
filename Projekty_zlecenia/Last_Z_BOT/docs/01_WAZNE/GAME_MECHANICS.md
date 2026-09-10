# Mechanika Last Z — jedyne źródło prawdy
## Ostatnia aktualizacja: 2026-08-01
## Autor: Ksawier (na podstawie własnej znajomości gry)

---

## Event: Helikopter (Treasure Helicopter)

### Prawdziwy flow — krok po kroku:

1. **Alert**
   - W grze pojawia się alert o helikopterze
   - Najlepsze miejsce do szukania: **czat, zakładka Alliance**
   - W czacie pojawia się komunikat z konkretnymi koordynatami (X, Y)
   - **Koordynaty helikoptera są ZAWSZE LOSOWE** — bot musi je odczytać z czatu za pomocą OCR
   - **Jak odróżnić wpis helikoptera od zwykłego wpisu (np. "Receive Supplies"):**
     - Wpis helikoptera: `State`, `X:`, `Y:` w **JEDNEJ poziomej linii** (np. `State 742 X:524 Y:546`)
     - Zwykły wpis: `State` i `X:... Y:...` są **rozbite na DWA wiersze** (tekst się nie mieści w jednej linii)
     - `State`, `X:`, `Y:` to stałe elementy UI — nie tłumaczą się na inne języki
   - Bot odczytuje koordynaty z czatu i klika dokładnie w tę linię, aby przeskoczyć do helikoptera na mapie

2. **Kliknięcie koordynatów na czacie (TELEPORT)**
   - Po wykryciu alertu → bot klika **dokładnie w linię z koordynatami na czacie** (tę samą, którą znalazł krok 1)
   - Kliknięcie w linię na czacie → gra automatycznie przeskakuje widok mapy na helikopter
   - Pozycja kliknięcia pochodzi z bounding boxa OCR z kroku 1 (środek linii z `State X: Y:`), przekazana przez `step_results`
   - Między krokiem 1 a 2 nie ma opóźnienia — czat nie zdąży się przewinąć

3. **Czekanie na teleport (WAIT 3s)**
   - Po kliknięciu koordynatów gra potrzebuje ~3 sekund na przeteleportowanie kamery i jej stabilizację

4. **Kliknięcie w helikopter (ZAZNACZENIE)**
   - Bot klika w helikopter na środku ekranu (środek ROI helikoptera), żeby go zaznaczyć
   - ROI helikoptera: prostokąt w centrum ekranu (np. 35-65% szer., 20-80% wys.) — działa na każdej rozdzielczości
   - Po zaznaczeniu helikoptera pojawia się przycisk **Explore**

5. **Kliknięcie Explore (WYSŁANIE WOJSK)**
   - Bot klika przycisk **Explore** (środek ROI Explore)
   - Przycisk Explore służy **TYLKO I WYŁĄCZNIE do wysłania wojsk**
   - **BARDZO WAŻNE:** Wysłanie wojsk jest bezwzględnym **warunkiem koniecznym**. Bez użycia "Explore" na tym etapie i wysłania wojska na helikopter, nie będzie można lootować skrzynki na samym końcu.
   - Bot klika Explore **raz** (jedno kliknięcie, nie spam)

6. **Czekanie na dojazd wojsk + Timer (WATCH_TIMER)**
   - Wojska jadą do helikoptera — timer startowy to **2 godziny** (7200s)
     - 2h → 30min → 13min → 7min → 4min → 3min → 2min...
     - Poniżej 1 minuty zmiany są już niewielkie, timer się kończy
   - **Timer skacze nieliniowo** — nie odlicza sekunda po sekundzie, tylko przeskakuje o duże wartości przy każdym nowym wozie
   - **UWAGA:** Jeśli ktoś wycofa wojska z helikoptera przed końcem timera → timer ZNIKA, ale **helikopter ZOSTAJE** na mapie. Bot NIE spamuje od razu — czeka aż timer całkowicie znieknie (OCR zwraca None).
   - Bot śledzi TYLKO timer przez OCR — nie śledzi wozów
   - **Logika watch_timer (dwie fazy + konfigurowalny próg spamu):**
       - **Faza IDLE:** timer > 1 minuta → sprawdzanie co **30s** — **NIC NIE ROBI**, tylko czeka
       - **Faza AKTYWNA:** timer ≤ 1 minuta → sprawdzanie co **200ms** (5 razy na sekundę, "co chwilę aktualizuje")
       - **Próg SPAM:** timer ≤ `spam_threshold_s` (konfigurowalne w GUI, domyślnie 5s, potwierdzone histerezą $N \ge 2$) → natychmiast rozpoczyna fazę spamu (brak uśpienia do $T_0 - \text{lead\_time}$)
       - **Obsługa Wzrostu Timera (Timer Jump):** jeśli timer wzrośnie (np. wycofanie/zmiana wojsk i skok z 6s do 36s), bot resetuje licznik histerez i estymatę $T_0$, NIE traktując tego jako zniknięcia i kontynuuje czuwanie
       - **Obsługa Zniknięcia Timera (None):** jeśli timer znika (OCR zwraca None), spam odpala się natychmiast TYLKO wtedy, gdy ostatni odczyt był w strefie docelowej (`last_known_value <= spam_threshold_s`)

8. **Zapierdol klikania (Klatka po klatce i obsługa wejścia Unity)**
   - W momencie wyzwolenia spamu bot ustawia kursor na celu i czeka **25 ms (bufor pre-aiming)**, aby silnik Unity (PlayerLoop / EventSystem) przetworzył zmianę pozycji przed pierwszym wciśnięciem myszy.
   - W momencie gdy timer znika, na miejscu helikoptera pojawia się budynek / skrzynka.
   - Może pojawić się dymek ze złotą skrzynią (np. z licznikiem "0/10") nad budynkiem.
   - Od klikania w budynek **może wyskoczyć menu "Select"** (z opcjami takimi jak nazwa gracza i ikona helikoptera "Explore Treasure").
   - **BARDZO WAŻNE:** Całkowicie **IGNORUJEMY to menu**. Nie szukamy w nim przycisku "Explore" ani "Explore Treasure". Jak potwierdzono, po zniknięciu helki "nie ma żadnego explore ani nic... tylko się klika".
   - Bot wysyła serię kliknięć zgodnie z konfiguracją z GUI (`config.spam_clicks_per_sec`, domyślnie 30 CPS, trzymanie DOWN 18 ms bez jittera, separacja DOWN/UP bez ruchu w trakcie wciśnięcia).
   - Samo klikanie w środek zamyka temat i natychmiastowo odbiera nagrodę (pojawia się ekran "Congratulations" / "The treasure has been snatched up").

9. **Powrót do czuwania**
   - Po odebraniu nagrody → bot wraca do obserwacji czatu
   - Czeka na kolejny alert

---

## Czego bot potrzebuje do tego flow (PLAN — 6 kroków):

### Krok 1: Wykrycie alertu (`WAIT_FOR_CHAT`)
- **Handler:** `WAIT_FOR_CHAT`
- **Metoda:** OCR na czacie (zakładka Alliance), wykrywanie po strukturze linii
- **Co szukać:** `State`, `X:`, `Y:` w **JEDNEJ linii** (helikopter) vs **DWÓCH liniach** (zwykły wpis)
- **ROI:** ✅ Czat Alliance — Ksawier zaznacza w GUI (% okna gry)
- **Plan:** `docs/superpowers/plans/helicopter_macro/01_KROK1_DETEKCJA.md`

### Krok 2: Kliknięcie koordynatów na czacie (`CLICK`)
- **Handler:** `CLICK`
- **Metoda:** Klika w linię z koordynatami (pozycja z kroku 1, `step_1_click_x/y`)
- **ROI:** ❌ — automat z kroku 1
- **Plan:** `docs/superpowers/plans/helicopter_macro/02_KROK2_KLIKNIECIE.md`

### Krok 3 (wait): Czekanie na teleport (`WAIT 3s`)
- **Handler:** `WAIT`
- **Metoda:** 3 sekundy pauzy na przeteleportowanie i stabilizację kamery
- **ROI:** ❌

### Krok 3 (click): Kliknięcie w helikopter (`CLICK`)
- **Handler:** `CLICK`
- **Metoda:** Klika w środek ROI helikoptera (zaznaczenie)
- **ROI:** ✅ Helikopter — Ksawier zaznacza w GUI (% okna gry, środek ekranu)
- **Plan:** `docs/superpowers/plans/helicopter_macro/03_KROK3_KLIK_HELI.md`

### Krok 4: Kliknięcie Explore (`CLICK`)
- **Handler:** `CLICK`
- **Metoda:** Klika w środek ROI przycisku Explore (wysłanie wojsk)
- **ROI:** ✅ Explore — Ksawier zaznacza w GUI (% okna gry)
- **Plan:** `docs/superpowers/plans/helicopter_macro/04_KROK4_EXPLORE.md`

### Krok 5: Śledzenie timera (`WATCH_TIMER`)
- **Handler:** `WATCH_TIMER`
- **Metoda:** OCR na timerze co 1s. Gdy wartość ≤ **5 sekund** → przechodzi do kroku 6
- **ROI:** ✅ Timer — Ksawier zaznacza w GUI (górny pasek ekranu)
- **Plan:** `docs/superpowers/plans/helicopter_macro/05_KROK5_TIMER.md`

### Krok 6: Spam kliknięć (`CLICK` z powtórzeniami)
- **Handler:** `CLICK` (lub nowy `SPAM_CLICK`)
- **Metoda:** Full-auto spam 50 kliknięć w środek ROI helikoptera (ten sam co krok 3)
- **ROI:** ❌ — używa tego samego co krok 3
- **Plan:** `docs/superpowers/plans/helicopter_macro/06_KROK6_SPAM.md`

### Powrót:
- Po kroku 6 BotRunner wraca do kroku 1. Całe makro w pętli.

---

## Błędne założenia (obalone):

| Błędne | Prawdziwe |
|---|---|
| ❌ Skrzynka od razu zastępuje helikopter | ✅ Helikopter znika, na jego miejscu staje Baza/Budynek, nad nim może pojawić się złota skrzynka ("0/10") |
| ❌ Trzeba znaleźć "Explore Treasure" w menu "Select" i kliknąć | ✅ Nawet jeśli po kliknięciu w bazę otworzy się menu "Select" z opcją "Explore Treasure", CAŁKOWICIE JE IGNORUJEMY. Wystarczy spamować kliknięcia w centrum ekranu, dokładnie w punkt, gdzie był helikopter. |
| ❌ FIND_OR_SCROLL na menu Select | ✅ Żadnego szukania przycisków w menu. WATCH_TIMER ogarnia zwykły spam klikania w centrum gdy timer zniknie. |
| ❌ Explore to odbieranie nagrody | ✅ Explore to WYSYŁANIE WOJSK na początku. **Jest to warunek absolutnie konieczny, by w ogóle móc odebrać nagrodę.** Sama nagroda jest potem odbierana przez spam kliknięć, bez szukania przycisku Explore. |

---

## Uwagi do implementacji:

- Koordynaty helikoptera są **ZAWSZE LOSOWE** — bot odczytuje je z czatu przez OCR (pozycja bounding boxa)
- Czat (zakładka Alliance) jest najlepszym źródłem alertu
- Wykrywanie helikoptera po strukturze: `State`, `X:`, `Y:` w **jednej linii** vs **dwóch liniach** dla zwykłych wpisów
- Timer skacze nieliniowo (2h→30min→13min→7min→...) — nie odlicza sekunda po sekundzie
- Spam dopiero poniżej 60s lub gdy timer naturalnie zniknie — ignorujemy fałszywe zniknięcia (wycofanie wojsk)
- WATCH_TIMER wymaga poprawek: próg 60s, ignorowanie dużych skoków, rozróżnienie zniknięcia timera
- **Gra nie ma anticheata** — można bezpiecznie używać interception driver do automatyzacji wejścia (kliknięcia, OCR, template matching)