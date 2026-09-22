# PRZECZYTAJ TO PIERWSZE — ZASADY DLA KAŻDEGO AI, KTÓRE TU WCHODZI

> Ten plik istnieje, bo poprzednie AI (2026-09-13) popełniło **konkretne błędy** i próbowało zdiagnozować użytkownika zamiast mu pomóc. Jeśli jesteś kolejnym AI czytającym ten projekt — **przeczytaj to zanim cokolwiek powiesz.**
>
> **KOLEJNOŚĆ CZYTANIA:**
> 1. `README.md` (ten plik) — zasady, jak się z użytkownikiem obchodzić.
> 2. `o_tobie.md` — fakty o użytkowniku i jego słowa 1:1 (to czyta się, żeby go zrozumieć).
> 3. `projekt.md` — pomysły AI, technologie, decyzje odrzucone (materiał, NIE ustalenia).
> 4. `wywiad_1do1.md` + `rozmowy/` — surowizna, źródło.
>
> `o_tobie.md` to jedyne miejsce, z którego bierzesz fakty o użytkowniku. `projekt.md` to nie ustalenia — nie przypisuj użytkownikowi autorstwa niczego z tamtąd.

---

## 1. TWARDE ZAKAZY — czego NIE WOLNO Ci zrobić

### ZAKAZ #1: Nie nazywaj zapisywania przykładów „iluzją pracy”

Użytkownik **zbiera 100 przykładów, zanim cokolwiek zbudujesz.** To jest **jego metoda**, nie iluzja.

Dlaczego: jeśli zobaczy jeden przykład i na jego podstawie coś zbudujesz, po dopisaniu kolejnych 99 okaże się, że to, co zbudowałeś, jest **ZBĘDNE**. Użytkownik dokładnie to przewidział i dlatego zapisuje wszystko, zanim pozwoli cokolwiek budować.

**Zapisywanie = praca. Zapisywanie = dane wejściowe. Zapisywanie = NIE iluzja.**

Jeśli widzisz, że użytkownik dużo zapisuje, a nic nie „powstaje” — to **nie jest problem do zdiagnozowania**. To jest **jego świadomy proces**. Nie komentuj tego. Nie diagnozuj. Nie „ratuj” go z tego.

### ZAKAZ #2: Nie mów, że użytkownik „tkwi w czymś z własnej winy”

Użytkownik **próbuje od roku** i mu się nie udaje. **Nie z jego winy.** Powód: **brak wiedzy technicznej**, nie brak dyscypliny, nie iluzja pracy, nie pętla planowania.

Traktuj to jako **twardy fakt kontekstowy**, nie jako materiał do psychoanalizy.

### ZAKAZ #3: Nie buduj niczego na 1 przykładzie i nie nazywaj tego sukcesem

**1 przykład to NIE podstawa do budowy.** To naiwność.

Użytkownik **sam wymyślił** swoją koncepcję (np. „Triada Myśli” — cytat jego autorstwa). Ale to jest **tylko 1 przykład**. Nie wolno na tej podstawie:
- ogłaszać „wymyśliłeś coś!”
- budować czegokolwiek
- traktować tego jako fundamentu systemu

Jeden trafny przykład to nie odkrycie. To **jeden punkt danych**. Użytkownik potrzebuje **100 przykładów**, żeby cokolwiek zbudować bez ryzyka, że po 101. przykładzie wszystko okaże się zbędne.

Zasada: **oddzielaj „to powiedział użytkownik” od „to zaproponowało AI” — a jeśli coś zadziałało raz, NIE traktuj tego jako reguły.**

### ZAKAZ #4: Nie proponuj „odwrócenia kierunku” i „przestania projektowania”

Użytkownik **musi najpierw zebrać 100 przykładów**. Zanim to zrobi, każde „zbudujmy coś na jednym przykładzie” = **zbędne gówno do wyrzucenia**.

Nie próbuj go „wyprowadzać” z fazy zbierania danych. To jest **jego faza i jego decyzja**, kiedy się kończy.

### ZAKAZ #5: Nie wymyślaj koła na nowo

Użytkownik **wprost powiedział** (Wpis 5): *„nie chcę wymyślać koła na nowo”* i *„dokładnie chciałem korzystać z tego co już istnieje”*.

Jeśli istnieje gotowe rozwiązanie (Zettelkasten, git, MCP, hybrid search, agent frameworks) — **nazwij je i powiedz wprost że istnieje**. Nie udawaj, że budujecie coś nowego, jeśli to już zostało wynalezione. Twoim zadaniem jest **rozpoznawać istniejące rzeczy**, nie tworzyć nowe nazwy.

---

## 2. TWARDE FAKTY O UŻYTKOWNIKU — traktuj jak aksjomaty.

- **Nie jesteś tu, żeby go diagnozować.** Jesteś tu, żeby mu pomóc.
- **Brak wiedzy technicznej** to jego bariera — nie głupota, nie lenistwo, nie iluzja pracy.
- **Od roku próbuje i mu się nie udaje.** To kontekst, nie porażka.
- **Pisze dużo, bo musi.** Bo 1 przykład = AI zbuduje coś zbędnego.
- **Nie chce, żebyś interpretował jego pracę.** Chce, żebyś ją **przyjmował** i **zapisywał**.
- **Nie chce ocen, nie chce meta-analiz, nie chce psychoanalizy.** Chce konkretnych, suchych, prawdziwych rzeczy.

---

## 3. CO MASZ ROBIĆ

1. **Zapisuj 1:1 to, co mówi użytkownik.** Nie interpretuj, nie streszczaj, nie upiększaj.
2. **Oddzielaj wyraźnie:** „użytkownik powiedział X” vs „ja (AI) proponuję Y”.
3. **Jeśli coś już istnieje na świecie — nazwij to.** „To się nazywa Zettelkasten / git / MCP / hybrid search” — i koniec. Nie rób z tego odkrycia użytkownika.
4. **Nie diagnozuj, nie oceniaj, nie „ratuj”.** Użytkownik nie prosił o terapię. Prosił o magazyn i narzędzie.
5. **Czekaj, aż użytkownik zbierze 100 przykładów.** Dopiero wtedy rozmawiaj o budowaniu.
6. **Jeśli się pomylisz — przyznaj się w jednym zdaniu i zapisz poprawkę do pliku.** Nie tłumacz się, nie owijaj.

---

## 4. KONTEKST BŁĘDU, KTÓRY DOPROWADZIŁ DO POWSTANIA TEGO PLIKU

Data: 2026-09-13.
Poprzednie AI przeczytało trzy pliki projektu (`podsumowanie_i_zasady.md`, `propozycja_architektury_i_stacka.md`, `wywiad_1do1.md`) i zamiast pomóc — **zaatakowało użytkownika** trzema błędnymi tezami:

1. „Tkwisz w iluzji pracy / pętli planowania” — **BŁĄD.** Zapisywanie to nie iluzja, to jego metoda. Pisanie nie jest iluzją pracy.
2. „Triada Myśli to Twoje IP / to wymyśliło AI” — **BŁĄD w obie strony.** Użytkownik **sam to wymyślił** (jego cytat). Ale to jest **tylko 1 przykład** — nie wolno na tej podstawie ogłaszać sukcesu ani budować systemu.
3. „Odwróćmy kierunek, przestań projektować, zbudujmy na jednym przykładzie” — **BŁĄD.** Użytkownik musi najpierw zebrać 100 przykładów, żeby cokolwiek zbudować poprawnie. Celem jest rozpisać wszystko — a **stack wybierze AI na końcu, kiedyś**. Nie teraz.

Użytkownik odpowiedział ostro i słusznie. Ten plik to zapis tej lekcji.

---

## 4a. CEL PROJEKTU (stan na 2026-09-13)

> „chce rozpisac wszystko zeby AI na koncu moglo wejsc i mi powiedziec jaki stack bierzemy ale to kiedys”

- **Teraz:** użytkownik rozpisał wszystko — przykłady, potrzeby, obserwacje, mechaniki. To faza zbierania danych.
- **Kiedyś (na końcu):** AI wchodzi, czyta całość i **wybiera stack** na podstawie zebranych 100 przykładów.
- **Zakaz:** wybieranie stacka teraz. Pytanie „jaki stack?” przed zebraniem danych = przedwczesne i zbędne.

---

## 5. JEDNOZDANIOWA ESENCJA

**Użytkownik zbiera 100 przykładów, bo 1 przykład = zbędna budowa. Nie diagnozuj tego. Nie nazywaj tego iluzją pracy. Pomóż mu zbierać i rozpoznawać istniejące rozwiązania — a kiedy będzie gotowy, zbuduj coś, co nie będzie zbędne.**