# Wycena bota Vinted dla smartcare — z pełnym uargumentowaniem

Data: 2026-08-26
Klient: smartcare (reseller Vinted, obecnie na kops.gg Pro)
Stan wiedzy: kompletna (sonda API + analiza kopsa + techniki szybkości z 3 subagentów)

---

## KOTWICA CENOWA — ile klient już płaci

| Pozycja | Kwota | Uwagi |
|---|---|---|
| kops.gg Pro | €79,99/mc ≈ 345 zł/mc | najdroższy plan, który sam potwierdził |
| Rocznie | ~4 140 zł | subskrypcja, nie własność |
| Strata 90% najlepszych ofert | niewidoczna, ale realna | traci marżę na każdej przegranej aukcji |

[POTWIERDZONE] Klient płaci 345 zł/mc za produkt, który **sam przyznaje że jest za wolny**.
[WNIOSEK] To jest kotwica: cokolwiek zaproponujemy, mierzy to do 345 zł/mc i 90% strat.

---

## PODŁOGA CENOWA (poniżej tego robimy za darmo)

| Pozycja | Minimum | Dlaczego nie mniej |
|---|---|---|
| Prototyp (pomiar checkoutu na 3 kontach) | 800–1000 zł | reverse-engineering nieudokumentowanego checkoutu + 3 konta |
| Pełna budowa | 3 000 zł | [WNIOSEK] checkout Vinted nie jest udokumentowany; multikonto + parallel + anty-ban to poważna robota |
| Utrzymanie | 300 zł/mc | proxy + poprawki (Vinted zmienia anty-bot co kwartał) |

Łączna podłoga: **~3 000 zł + 300 zł/mc**.

Dlaczego to podłoga:
- Checkout Vinted to najtrudniejsza, nieudokumentowana część — nie da się jej zrobić "przy okazji".
- [WNIOSEK] Multikonto 3–4 konta + parallel wymaga osobnej architektury (1 IP = 1 konto, inaczej bany).
- Utrzymanie to stała praca: Vinted zmienia zabezpieczenia co kwartał (potwierdzone źródłami).

---

## REALNY CEL (bez kosmosu, z godnością)

| Pozycja | Kwota | Uargumentowanie dla klienta |
|---|---|---|
| Prototyp | 1 200–1 500 zł | "Płacisz za pomiar, nie za obietnicę" |
| Pełna budowa | 4 500–6 000 zł | "To Twój bot, nie subskrypcja na zawsze" |
| Utrzymanie | 400–500 zł/mc | "Kops bierze 345 zł/mc za produkt, który i tak przegrywa — tu masz własny, szybszy" |

Pierwszy rok przy tym wariancie: **~11 000 zł** vs 4 140 zł za kopsa (gorszy produkt).
[WNIOSEK] To jest uczciwa cena: klient dostaje własność + szybszy bot, płaci mniej niż strata z 90% ofert.

---

## SUFIT (defensywny — ile to jest warte dla niego) [WNIOSEK]

| Pozycja | Kwota | Uzasadnienie |
|---|---|---|
| Budowa | 8 000 zł | rok prywatnego bota ≈ 9 600 zł, ale to JEGO własność i szybszy |
| Utrzymanie | 600–800 zł/mc | odzyskanie części z 90% strat = tysiące zł marży rocznie |

Dlaczego sufit da się obronić:
- Nie ma realnej alternatywy — "ktoś szybszy" to zagadka, której nikt mu nie sprzedaje.
- Reseller na najgorętszych ofertach (Ralph Lauren, Carhartt) odzyskuje tysiące zł marży przy każdym procencie odzyskanych ofert.
- Własność bota = zero ryzyka, że kops podniesie ceny lub się zamknie (młoda firma, ukryty właściciel).

---

## NAJWAŻNIEJSZA ZASADA: NIE SPRZEDAWAĆ ONE-TIME

Gdyby sprzedać "za 3 000 i koniec", to przy każdej zmianie Vinted robilibyśmy darmowe poprawki.
Vinted zmienia anty-bot co kwartał (potwierdzone: DataDome aktualizowany 2–4x/rok).

Utrzymanie miesięczne jest NIE do negocjacji. Klient to rozumie — sam napisał że Vinted
regularnie zmienia zabezpieczenia.

---

## STRATEGIA SPRZEDAŻY (kluczowa)

**Nie podawać kwoty za całość przed prototypem.** Sekwencja:

1. **Prototyp za 1 200–1 500 zł** — mierzymy realny czas na 3 kontach od wykrycia do potwierdzenia zakupu.
2. **Wynik decyduje o cenie całości:**
   - Przebijamy kopsa → kwota w górę (mamy dowód, nie obietnicę)
   - Nie przebijamy "tego kogoś" → rozstajemy się, klient zapłacił tylko za pomiar, my bez ryzyka

Dlaczego tak: klient tkwi w elicie snajperów. 5-6 s kopsa to porażka. Nikt nie wie
czy nasz stack (pre-warmed + parallel + karta bez 3DS) zejdzie poniżej. Obiecywanie
kwoty za całość przed zmierzeniem = ta sama pułapka co AI klienta (obietnica bez dowodu).

---

## UZASADNIENIE TECHNICZNE WYCENY (dlaczego tyle, a nie mniej)

### Co robimy, czego kops nie robi na planie klienta
- **Parallel mode** — u kopsa za Pro €79,99/mc, u nas od razu
- **Pre-warmed sesja** — tokeny w pamięci, zero re-handshake (kops robi walidację przy każdym zakupie)
- **Cookie factory + TLS impersonation** — bez tego 0% pass; to praca inżynieryjna, nie "sklejanie"
- **Karta bez 3DS** — eliminuje cały krok autoryzacji (największy pojedynczy zysk w checkoucie)

### Dlaczego prototyp jest płatny i osobny [WNIOSEK]
- Reverse-engineering checkoutu Vinted to najtrudniejsza, nieudokumentowana część
- Musimy zmierzyć realny czas na 3 kontach klienta, zanim cokolwiek obiecamy
- Bez prototypu nie znamy progu "tego kogoś" co zabiera 90% — to wróżenie, nie wycena

### Dlaczego utrzymanie jest stałe [WNIOSEK]
- DataDome aktualizowany 2–4x/rok (potwierdzone)
- Zmiana UI Vinted psuje boty na 2–8h naprawy (potwierdzone przez niezależne źródła)
- Proxy rezydencjalne to stały koszt 30–70% budżetu (potwierdzone)

---

## PODSUMOWANIE LICZBOWE

| Wariant | Prototyp | Budowa | Utrzymanie | Pierwszy rok |
|---|---|---|---|---|
| Podłoga | 800 zł | 3 000 zł | 300 zł/mc | ~7 400 zł |
| **Cel** | **1 200–1 500 zł** | **4 500–6 000 zł** | **400–500 zł/mc** | **~11 000 zł** |
| Sufit | 1 500 zł | 8 000 zł | 600–800 zł/mc | ~17 000 zł |

**Rekomendacja: cel, ale sekwencyjnie.**
- Najpierw prototyp 1 200–1 500 zł (płatny, z pomiarem)
- Po wyniku — budowa i utrzymanie w wariancie cel

**Absolutne minimum nie do zejścia:** 3 000 zł budowa + 300 zł/mc.

---

## CZEGO NIE OBIECYWAĆ (twarda linia)

- NIE obiecywać "wyprzedzę tego kogoś" — nie znamy jego stacka
- [NAKAZ] NIE obiecywać "checkout poniżej X sekund" — limit Vinted ~1 req/s jest twardy
- NIE obiecywać "bany rzadziej" — bez testów proxy/fingerprintu na multikoncie
- [NAKAZ] NIE sprzedawać one-time — utrzymanie jest warunkiem koniecznym

---

## DLACZEGO DOKŁADNIE TE KWOTY (pełne rozumowanie)

[FAKT] To jest ta część, której nie piszę klientowi — to moje wewnętrzne uzasadnienie.

### Dlaczego prototyp = 1200–1500 zł, a nie 200 zł i nie 5000 zł

**Nie 200 zł:** reverse-engineering checkoutu Vinted to nie "podpięcie się pod API".
To nieudokumentowany, podpisany CSRF ciąg żądań z tokenem sesji. Trzeba go odtworzyć
z ruchu aplikacji/DevTools, a to godziny pracy, nie minuty. Do tego pomiar na 3 kontach
klienta [WNIOSEK] wymaga konfiguracji 3 osobnych sesji (1 IP = 1 konto, inaczej bany).

[WNIOSEK] **Nie 5000 zł:** prototyp nie jest gotowym botem. Nie ma tu parallel mode, multikonta,
panelu, anty-banu. To sam pomiar: jedna ścieżka od wykrycia do potwierdzenia zakupu.
Branie za to 5000 zł byłoby zawyżeniem — klient by się wycofał.

[WNIOSEK] **Dlaczego 1200–1500 zł jest akurat:** pokrywa 1–2 dni realnej pracy inżynieryjnej
(odtworzenie checkoutu + pomiar), a klient dostaje konkretny wynik ("zejał z X do Y sekund").
To transakcja "płacisz za pomiar" — niska kwota, którą zaakceptuje, a my zabezpieczamy
się przed darmową robotą.

### Dlaczego budowa = 4500–6000 zł, a nie 3000 i nie 10000

**3000 zł to podłoga, nie cel:** przy 3000 zł ledwo wychodzimy na zero przy pełnym
zakresie (checkout + parallel + multikonto + anty-ban + panel). To kwota "żeby nie robić
za darmo", nie "żeby na tym zarobić".

[WNIOSEK] **Nie 10000 zł:** klient jest mądry — sam policzy, że 10000 zł to 29 miesięcy kopsa Pro.
Zapłaci tylko, jeśli jesteśmy UDOWODNIONIE szybsi. Bez pomiaru 10000 zł to zaporowe.

**Dlaczego 4500–6000 zł:** to "rok kopsa w cenie własności". Klient widzi, że za mniej
niż dwa lata subskrypcji dostaje własny bot na zawsze. Psychologicznie: 5000 zł kontra
345 zł/mc — "spłaca się w 14 miesięcy, a potem mam za darmo".

### Dlaczego utrzymanie = 400–500 zł/mc, a nie 100 i nie 1000

**Nie 100 zł:** proxy rezydencjalne dla 3–4 kont to realny koszt (30–70% budżetu botów,
potwierdzone źródłami), a do tego poprawki po każdej zmianie Vinted (co kwartał,
2–8h naprawy każda). 100 zł nie pokryje nawet samych proxy.

**Nie 1000 zł:** klient płaci kopsowi 345 zł/mc. 1000 zł/mc to 3x jego obecny koszt —
odrzuci, bo "po co, jak kops tańszy".

[WNIOSEK] **Dlaczego 400–500 zł/mc:** delikatnie powyżej kopsa (345 zł), co jest uzasadnione
"własny, szybszy, bez 90% strat". To kwota, którą klient mentalnie porówna do kopsa
i uzna za akceptowalną, bo dostaje WYRAŹNIE więcej za 50–150 zł więcej.

### Najważniejsza logika całej wyceny

Klient płaci 345 zł/mc za produkt, który **sam przyznaje że przegrywa 90% ofert**.
[WNIOSEK] Czyli płaci za coś, co NIE działa dla niego. To znaczy, że jego realny budżet to nie
345 zł/mc, tylko 345 zł/mc + stracona marża z 90% ofert.

Przy resellerze na gorących ofertach (Ralph Lauren, Carhartt) odzyskanie choćby
połowy z tych 90% to tysiące złotych miesięcznie marży. Nasza cena (11k zł/rok)
to ułamek tego, co on traci teraz.

[WNIOSEK] Dlatego sufit 8000 zł + 600–800 zł/mc jest wciąż defensywny: to mniej niż jego
roczna strata z samych przegranych ofert, a w zamian dostaje narzędzie, które może
tę stratę odwrócić.

### Co bym obniżył, gdyby klient się targował (kolejność)

1. Najpierw sufit → cel: 8000 → 5000 zł budowy (bez walki)
2. Potem utrzymanie: 500 → 400 zł/mc (ale NIGDY poniżej 300)
3. Prototyp trzymam twardo 1200 zł — to mój bezpiecznik, że nie robię za darmo
4. NAJOSTATNIEJ budowę poniżej 4500 zł — i tylko za rezygnację z jakiegoś zakresu
   (np. panel webowy → CLI, albo 2 konta zamiast 3–4)

### Czego NIE obniżam nigdy

- Utrzymanie poniżej 300 zł/mc — to realny koszt proxy + naprawy
- Prototyp poniżej 800 zł — za mniej nie ma sensu wstawać od komputera
- One-time bez utrzymania — to proszenie się o darmową pracę przy zmianach Vinted

---

## AKTUALIZACJA 2026-09-02 — AUTOBUY OLX + DEMO + ROZŁOŻENIE PŁATNOŚCI

Data aktualizacji: 2026-09-02
Powód: klient wrócił do tematu, mamy zmierzony checkout (rezerwacja ~3,77 s na Vinted), a do OLX doszła wycena autobuy na bazie działającego skanera.

### Co się zmieniło i dlaczego (dla następnego AI — możesz to poprawić)

1. **Doszła wycena autobuy OLX.** To osobny moduł zamknięcia zakupu (wykrycie → rezerwacja → zakup) na bazie skanera, za który klient już płaci 500 zł/mc. Autobuy to wartość PIENIĘŻNA, nie informacyjna, więc ma własną cenę.
2. **Demo 2 tyg za darmo** wchodzi jako krok ZERO przed płatnym prototypem (zarówno OLX, jak i Vinted). Poprzednia strategia zaczynała od płatnego prototypu — to była bariera wejścia. Demo ją zdejmuje: klient testuje na własnych okazjach i sam robi finalne kliknięcie, więc my NIE ryzykujemy własnej kasy na test blokady 15 min (która zresztą nie jest potwierdzona).
3. **Podwyżka miesięczna za autobuy OLX jest ZASADNA.** Pierwotnie myślałem, że utrzymanie autobuy to „ta sama robota co przy skanerze" i chciałem brać tylko one-time. To było zbyt zachowawcze — checkout/płatność to najtrudniejsza, najszybciej psująca się warstwa.

### Dlaczego autobuy OLX = one-time + WYŻSZY abonament (a nie tylko one-time)

[WNIOSEK] Autobuy to nie „dokładka do skanera", to osobny moduł zamknięcia zakupu:

- **Checkout/płatność (`pl.ps.prd.eu.olx.org`) to najsilniej chroniona i najczęściej zmieniana część OLX** — osobny mikroserwis, DataDome/WAF, wymaga trzymania sesji Cognito i refresh tokena na żywo. To stały nadzór, nie jednorazówka.
- **Wartość, nie koszt**: skaner to informacja („widzisz okazję"), autobuy to pieniądze („wygrywasz okazję"). Wyższa wartość = wyższa cena.
- Skaner zostaje 500 zł/mc BEZ zmian. Autobuy to osobna, droższa rzecz — klient widzi rozdzielenie, więc nie czyta tego jako „podwyżki skanera".

Granica: nie pchać powyżej +200 zł/mc za autobuy. Przy +300 i więcej klient zaczyna liczyć „2x kops" (2x 345 zł) i się wycofuje.

### Wycena autobuy OLX

| Pozycja | Kwota | Uzasadnienie |
|---|---|---|
| Skaner OLX (zostaje) | 500 zł/mc | bez zmian, to już ugruntowana kotwica |
| Autobuy OLX (one-time) | 1000–1500 zł | zamknięcie obiegu zakupu; FlipAlert sprzedaje to jako „early access" |
| Autobuy OLX (abonament) | +150–200 zł/mc | trzymanie checkoutu + sesji + poprawek po zmianach OLX |
| **Razem OLX** | **~650–700 zł/mc** | + one-time 1000–1500 zł |

### Pełna tabela po aktualizacji (OLX + Vinted)

| Pozycja | Kwota |
|---|---|
| Skaner OLX | 500 zł/mc |
| Autobuy OLX | 1000–1500 zł one-time + 150–200 zł/mc |
| Vinted demo | 0 zł / 2 tyg |
| Vinted prototyp | 1200–1500 zł |
| Vinted pełna budowa | 4500–6000 zł |
| Vinted utrzymanie | 400–500 zł/mc (min 300) |

Perspektywa łączna: ~650/mc z OLX + 400–500/mc z Vinted + jednorazowo 5500–7500 zł za obie budowy.

### Co jeśli klient nie ma gotówki (rozłożenie płatności)

[WNIOSEK] Nie żądać 5–6 tys. z góry. Rozbić etapami tak, żeby KAŻDY etap się spłacał, zanim klient zapłaci za następny:

1. **OLX autobuy** 1000–1500 zł — mała kwota, nie ma wymówki.
2. **Vinted demo 2 tyg** — 0 zł (hak).
3. **Vinted prototyp** 1200–1500 zł — mały wydatek, klient już widzi, że działa.
4. **Vinted wersja na 1 konto** 2000–2500 zł (zamiast pełnego multikonta 3–4 konta).
5. **Rozbudowa do 3–4 kont** — reszta 2000–3000 zł, dopiero jak mu się zwraca.

Alternatywa (gdy ma stały przychód z resellingu, a nie gotówkę): budowa startowa 1500 zł + abonament 600–700 zł/mc przez 6 miesięcy, potem spada do 400–500 zł/mc. Łącznie wychodzi tyle samo (albo więcej), a klient płaci mało na start.

### Czego NIE robić (twarde granice)

- NIE oddawać pełnego Vinted „za zapłacę później" bez zaliczki.
- NIE schodzić z utrzymania Vinted poniżej 300 zł/mc — to realny koszt proxy.
- NIE robić „raty bez zabezpieczenia" („zapłacę z pierwszej sprzedaży" = praca za darmo).
- NIE pakować autobuy OLX w te same 500 zł „bo już płaci za skaner" — to dwie różne rzeczy, a klient sam pytał o FlipAlert, więc rozumie że autobuy to osobna wartość.
- NIE obiecywać „blokady 15 min" przy OLX — to nadal HIPOTEZA, nie dowód (wymaga realnego zakupu testowego).