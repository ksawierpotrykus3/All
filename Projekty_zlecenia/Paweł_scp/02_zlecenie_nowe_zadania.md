# 02 — Nowe zlecenie: 3 zadania (widok listy, ceny UX, proforma w e-mailu)

**Klient:** Paweł (SCP)  
**Status:** do wyceny / potwierdzenia zakresu

---

## Wiadomość — Paweł

Cześć Maksymilian,

W nawiązaniu do spotkania:

Proszę zweryfikuj poniższe kwestie, które zostały mi zgłoszone ostatnio przez klienta z Rumunii:
- zmienia walutę z EUR na PLN, albo jest problem z wybraniem waluty EUR,
- po zalogowaniu nadal pokazuje „Login" na górze strony.

Daj znać jak tylko coś ustalisz i czy mam zgłaszać te kwestie do suportu IdoSell.

Przesyłam listę nowych zadań:

1. Karta produktu – ilość na magazynie -> po zmianie czcionki ilość nie jest już pogrubiona -> chciałbym, aby była pogrubiona lub w inny sposób wyeksponowana dla klienta.

2. W tej chwili widok produktów jest w formie kafelków -> chciałbym dodać drugi widok, jako opcja, że produkty są wyświetlane w formie listy jeden produkt pod drugim -> zdjęcie + nazwa + krótki opis + stan magazynowy + cena (idealnie przed i po rabacie, jeżeli jest zdefiniowany rabat).

3. Prezentacja ceny przed i po rabacie + jaki rabat % - dopracowanie w taki sposób, aby było to jasne dla klienta (UX) -> w tej chwili mamy trzy podstawowe ceny dla każdego produktu: cena dla gościa (bez rejestracji), cena hurtowa (po rejestracji), cena hurtowa po rabacie (po rejestracji dla klienta, który ma zdefiniowaną politykę rabatową) – do tego dochodzą jeszcze ceny promocyjne na wybrane produkty.

4. Wysyłanie proformy / order confirmation wraz z e-mailem o nowym zamówieniu – w tej chwili proforma jest dostępna wyłącznie w szczegółach zamówienia na panelu.

Daj znać jak widzisz realizację powyższych nowych zadań.

W kwestii pkt. 2 i podpunktu dotyczącego widoku listy, oprócz widoku kafelków, to podsyłam przykład takiego rozwiązania u konkurencji z Czech:

<https://e-shop.exvalos.cz/en/products/rubber-sheets/rubber-rolls-without-ply/sbr>

Dodawanie do koszyka od razu poziomu listy lub kafelków (bez potrzeby wchodzenia każdorazowo do karty produktu) wydaje mi się bardzo dobrym rozwiązaniem dla stałych klientów, którzy wiedzą co potrzebują i w ten sposób mogą szybko zbudować koszyk.

Pozdrawiam,
Paweł

---

## Podział (wg ustaleń seniora: „tylko 2, 3, 4”)

W zakres nowego płatnego zlecenia wchodzą **wyłącznie punkty 2, 3 i 4** z wiadomości Pawła. Punkt 1 (karta produktu) został wyłączony ze zlecenia.

### Zakres zlecenia (3 zadania):

1. **[Zadanie 2 z maila] Widok listy produktów (wiersze B2B) + dodawanie do koszyka**  
   - Drugi widok obok kafelków z przełącznikiem `[Siatka (Kafelki)]` vs `[Lista (Wiersze B2B)]`.
   - Struktura wiersza: zdjęcie + nazwa + atrybuty w linii + stan magazynowy + ceny z rabatem + pole ilości + przycisk „Do koszyka” (wzór: `e-shop.exvalos.cz`).
   - Wymaga obsługi koszyka w tle (AJAX Add-to-Basket) oraz precyzyjnego przelicznika jednostek ($m^2$ vs rolki/sztuki).

2. **[Zadanie 3 z maila] Prezentacja cen przed/po rabacie + % rabatu (UX)**  
   - Dopracowanie logiki wyświetlania 3 poziomów cen: cena gościa (detal), cena hurtowa (po rejestracji firmy), cena hurtowa z rabatem indywidualnym + ewentualne ceny promocyjne.
   - Odpowiednie plakietki (np. `-17% rabat B2B`, `-20% wyprzedaż`) widoczne tylko dla uprawnionych sesji.

3. **[Zadanie 4 z maila] Wysyłanie proformy / order confirmation w e-mailu z zamówieniem**  
   - Konfiguracja szablonu e-mail w IdoSell, aby klient otrzymywał dokument proforma (PDF / link do generowania) bezpośrednio przy potwierdzeniu zamówienia (zamiast szukać go wyłącznie w panelu klienta).

### Kwestie wyłączone ze zlecenia / osobne:

- **[Punkt 1 z maila] Karta produktu (pogrubienie ilości na magazynie):** Wyłączone ze zlecenia (drobiazg CSS do zrobienia w wolnej chwili lub odrzucone).
- **Zgłoszenie klienta z Rumunii (EUR/PLN i „Login”):**
  - **Diagnoza seniora:** Senior potwierdził, że w jego skryptach brakowało flagi `omit cookies`, przez co klient zagraniczny otrzymywał polskie ciasteczka (polską sesję i walutę PLN).
  - **Diagnoza z audytu na żywo (scp1.pl):** W selektorze nagłówka (`#menu_settings_country`) Rumunia w ogóle nie istnieje jako opcja (dostępne są tylko PL, CZ, SK, HR). Gdy klient wchodzi z zagranicy, IdoSell nie znajduje Rumunii w profilu sklepu i przy przeładowaniu strony resetuje koszyk/sesję do domyślnej Polski (PLN). Wymaga to aktywacji Rumunii w panelu IdoSell oraz poprawki w skrypcie COP.
  - **Wymóg deterministyczny:** Konieczne wykonanie testu end-to-end z zagranicznego IP (Rumunia / VPN) w trybie incognito, aby udowodnić, że po poprawce waluta EUR nie jest nadpisywana i sesja logowania działa prawidłowo.

---

## Wycena (zakres zadań 2, 3, 4)

| # | Zadanie (wg maila Pawła) | Zakres | Szacunek |
|---|--------------------------|--------|----------|
| 2 | Widok listy B2B + koszyk | Własny szablon listy (composer), przełącznik widoków, AJAX add-to-basket + REALNA logika limitu ilości (ile m² można dodać) | 500 – 800 zł |
| 3 | Prezentacja 3 cen + rabat % | Plakietki rabatowe + stylowanie gotowych cen z backendu (backend liczy — potwierdzone) | 200 – 300 zł |
| 4 | Proforma w e-mailu zamówienia | Automatyzacja wysyłki proformy przy potwierdzeniu zamówienia (link vs PDF załącznik) — research: dokument natywnie generowany on-demand + API | 300 – 500 zł |

**Razem orientacyjnie:** ~1 000 – 1 600 zł netto

> **Rekomendacja dla wyceny końcowej:** 1 100 – 1 500 zł netto za całość (2+3+4), z opcją wyceny zadania 4 osobno (ryzyko ↑ — PDF załącznik vs link).

---

## Dlaczego ta wycena (dowody i ustalenia) — stan po audycie kodu i odpowiedziach seniora

### A. Benchmark z poprzedniego zlecenia (01): 1000 zł netto

Za 1000 zł zrealizowano moduł koszyka (pliki `idosell_koszyk_summary.js`, `idosell_oscop_b2b.js`). **Audyt kodu wykazał, że realny zakres był prostszy, niż głosiła specyfikacja:**

| Deklarowane w 01 | Realnie w kodzie | Dowód |
|---|---|---|
| Blokada osób prywatnych / wymuszenie B2B | ✅ Zrobione w całości | `forceClientTypeFirm()` w `idosell_oscop_b2b.js` (linie 156–175) |
| Walidacja formatu i długości NIP | ⚠️ Tylko minimalna długość (min. 4 znaki) | `validateNip()` w `idosell_oscop_b2b.js` (linie 197–238); w `idosell_koszyk_summary.js` `getTaxNumberData()` w ogóle bez walidacji |
| Logika cen transportu wg kodu pocztowego CZ/SK | ❌ Brak — tylko kosmetyczne formatowanie kodu | `normalizeZipcode()` (format `123 45` / `12-345`); w całym `idosell_koszyk_summary.js` (2466 linii) `zipcode` występuje wyłącznie jako serializacja pola do GraphQL, zero obliczeń stawek |

### B. Odpowiedzi seniora (osoba znająca IdoSell od środka)

Senior potwierdził cztery rzeczy, które zmieniają wycenę:

1. **„własny szablon w composer"** → Zadanie 2 to custom szablon (jak `SummaryCOP`), nie natywny widok. Realna robota, ale to nasza kompetencja.
2. **„jest realna logika dodawania do koszyka i obliczania ile można dodać m²"** → Zadanie 2 to NIE tylko szablon — zawiera autorską logikę limitu ilości (m² vs rolki/sztuki) po stronie frontendu. To podnosi złożoność Z2.
3. **„raczej backend to liczy" (Zadanie 3)** → Zadanie 3 NIE wymaga logiki przeliczania cen — backend IdoSell liczy ceny i rabaty automatycznie. Frontend tylko prezentuje gotowe dane.
4. **„backend to liczy z automatu, nie trzeba na to skryptu"** → Odpada cała logika przeliczania kosztów transportu/cen — robi to IdoSell za darmo. Potwierdzone kodem: ceny (`cost.value`) przychodzą gotowe z API IdoSell (GraphQL `BASKET_COST`), frontend ich nie liczy.

**Proforma (Z4):** senior nie wie („nwm tego XD") — wymagany research dokumentacji (wykonany, patrz sekcja E).

### C. Co to oznacza dla wyceny

- **Zadanie 2**: szablon + AJAX add-to-basket + prezentacja + **realna logika limitu ilości (m²)**. Wyżej niż wcześniej zakładano. → 500–800 zł.
- **Zadanie 3**: wyłącznie plakietki i stylowanie gotowych cen (backend liczy). → 200–300 zł.
- **Zadanie 4**: niewiadoma częściowo rozwiązana researchem (patrz sekcja E). → 300–500 zł zależnie od wyboru PDF vs link.

### D. Dlaczego stara wycena (2 600 – 4 200 zł) była zawyżona

Stara tabela zakładała, że frontend musi **liczyć** ceny i koszty transportu (logika sesyjna, przelicznik jednostek, cenniki frachtu). Audyt kodu + słowa seniora dowodzą, że **backend IdoSell liczy ceny automatycznie**. Frontend jedynie prezentuje gotowe wartości. To eliminuje większość ryzyka, które wcześniej windowało widełki. Zadanie 2 wraca jednak wyżej przez realną logikę limitu ilości (m²).

> Wniosek: rekomendacja **1 100 – 1 500 zł netto** za całość (2+3+4).

### E. Research: proforma w IdoSell (Zadanie 4)

Ustalenia z dokumentacji/blogu IdoSell:

1. **Proforma jest natywnie generowana on-demand** — od 2016 roku dokument proforma (i potwierdzenie sprzedaży) jest „od razu gotowy do drukowania" po złożeniu zamówienia, bez ręcznego wystawiania przez obsługę. Numer proformy = numer zamówienia.
2. **Dostępna przez API** — blog IdoSell wprost mówi, że dokumenty proforma są dostępne „na karcie zamówienia, zwrotu i poprzez API". To kluczowe: istnieje programowy dostęp do wygenerowania proformy.
3. **E-maile transakcyjne** — IdoSell ma sekcję `MODERACJA / Zarządzanie treścią e-maili / E-maile transakcyjne / Potwierdzenia wpłynięcia zamówień`, gdzie konfiguruje się szablony potwierdzeń zamówień (detal/hurt/aukcja). To naturalne miejsce do podpięcia linku lub załącznika proformy.

**Wniosek dla wyceny Z4:** Dokument proforma istnieje natywnie i jest dostępny programowo (API). Realna robota to **automatyzacja wysyłki** — podpięcie linku do proformy w szablonie e-maila transakcyjnego, albo (trudniej) automatyczne pobieranie PDF przez API i dodawanie jako załącznik. Załącznik PDF = więcej roboty (hook + generowanie + załączanie); link w treści = taniej. Wycena 300–500 zł zależna od wyboru PDF vs link.

---

## Do ustalenia przed wyceną końcową

- [ ] Czy przełącznik kafelki/lista ma zapamiętywać wybór użytkownika (cookie)?
- [ ] Które dokładnie ceny i w jakiej kolejności pokazywać w widoku listy (gość / hurtowa / po rabacie)?
- [ ] Proforma: PDF w załączniku do maila „nowe zamówienie", czy osobny e-mail z proformą?
- [ ] Czy zadanie 1 (pogrubienie stanu magazynowego) wrzucamy do tego samego zlecenia, czy liczymy jako drobną poprawkę?

---

## Status propozycji seniora (analiza zrzutu ekranu „chyba nie jest najgorzej”)

Senior przygotował wstępną makietę / prototyp widoku listy B2B (plik zrzutu z czatu):
- **Przełącznik widoków:** `[ Siatka (Kafelki) ]` vs `[ Lista (Wiersze B2B) ]` (domyślnie aktywny pomarańczowy).
- **Struktura wiersza:**
  - Miniaturka zdjęcia produktu,
  - Nazwa towaru + parametry techniczne w linii (Baza kauczukowa, Grubość, Szerokość, Długość),
  - Badge magazynowy ze statusem (`✓ Na stanie: 140 m² / Wysyłka w 24h z magazynu`, `✓ Końcówka: 20 m²`, `✓ Na zamówienie (3-5 dni)`),
  - Prezentacja rabatu i cen (`-17% rabat B2B`, przekreślona cena wyjściowa np. `785,00 zł`, cena ostateczna np. `652,80 zł / 12 metry kwadratowe`),
  - Licznik ilości: `[-] [ 2 ] [+]`,
  - Akcja: przycisk `[ Do koszyka ]`.

### ⚠️ Krytyczne uwagi inżynierskie (co na pewno się wyłoży, jeśli nie zabezpieczymy tego deterministycznie):

1. **Konflikt jednostek: `m²` vs `rolka / sztuka` vs pole ilości:**
   - Na makiecie produkt ma cenę `652,80 zł / 12 metry kwadratowe`, a stan podany jest w `m²` (np. 140 m²).
   - W polu ilości ustawione jest `2`. Co oznacza "2"? Czy klient kupuje 2 rolki (czyli 2 × 12 m² = 24 m²), czy kupuje 2 m²?
   - W IdoSell produkty rolkowe/cięte wymagają ścisłej synchronizacji jednostek bazowych i przeliczników. Jeżeli silnik IdoSell przyjmuje zamówienie w sztukach, a stan magazynowy jest w m², skrypt dodający do koszyka z listy wyśle błędną ilość lub IdoSell odrzuci request.
2. **Produkty z wariantami (rozmiary / kolory):**
   - Na makiecie brak selektora wariantów. Jeśli produkt w IdoSell posiada warianty, natywny przycisk "Do koszyka" nie zadziała i wyrzuci błąd braku wyboru wariantu albo wymusi przejście do karty produktu, niwecząc cel widoku szybkiego zamawiania.
3. **Produkty „Na zamówienie” (stan 0):**
   - Pozycja 4 na makiecie ma status „Na zamówienie (3-5 dni)”, a przycisk „Do koszyka” jest aktywny. Trzeba zweryfikować w panelu IdoSell, czy sklep ma globalnie zezwolone zakupy towarów z zerowym stanem, czy wymaga specjalnego flow.
4. **Obsługa dodawania do koszyka (AJAX Add-to-Basket) na listingu:**
   - To nie jest zwykła zmiana CSS. Wymaga podpięcia asynchronicznego zapytania POST do endpointu koszyka IdoSell, zaktualizowania licznika w nagłówku strony oraz wyświetlenia potwierdzenia (toast/dymek) bez przeładowywania strony.
5. **Prezentacja 3 cen wg uprawnień (gość vs hurtownik vs rabat indywidualny):**
   - Na makiecie widać badge `-17% rabat B2B`. Widok ten MUSI być dynamiczny w zależności od sesji klienta. Gość niezalogowany NIE MOŻE widzieć rabatów hurtowych B2B ani cen dedykowanych.

---

## Lista czynników zmieniających wycenę (status po wiadomości seniora)

### Zadanie 1 — widok listy produktów + dodawanie do koszyka z listingu
- [x] Czy widok ma mieć przycisk „Do koszyka”: **TAK** — klient wprost wskazał to jako kluczową wartość dla stałych klientów, wzorując się na `e-shop.exvalos.cz`.
- [ ] Czy produkty na liście posiadają warianty do wyboru w wierszu, czy każdy wiersz to osobny towar bazowy?
- [ ] Jak IdoSell ma przeliczać ilość: sztuki/rolki czy metry kwadratowe?
- [ ] Czy przełącznik kafelki/lista ma zapamiętywać wybór (cookie/localStorage)?
- [ ] Responsywność (RWD): jak zachowuje się tabela na telefonach (przełamanie wiersza w mini-kartę).

### Zadanie 2 — prezentacja cen + % rabatu
- [x] Wiemy, że są 3 poziomy: cena gościa, cena hurtowa, cena hurtowa po rabacie + promocje.
- [ ] Potwierdzenie: co widzi gość, co widzi hurtownik standardowy, co widzi hurtownik z przypisanym rabatem.

### Zadanie 3 — proforma w e-mailu
- [ ] Weryfikacja techniczna w panelu IdoSell: czy silnik powiadomień IdoSell pozwala na załączenie pliku PDF proformy w zdarzeniu „nowe zamówienie”, czy konieczny jest link generowany automatycznie.

### Zgłoszenia klienta z Rumunii (wymagają natychmiastowej weryfikacji deterministycznej)
- [ ] **Waluta EUR -> PLN:** Sprawdzić i dodać Rumunię (`1143020169`) do dozwolonych stref w selektorze `#menu_settings_country` w IdoSell oraz zweryfikować flagę `omit cookies` w skrypcie COP.
- [ ] **Napis „Login” po zalogowaniu:** Sprawdzić cache (Varnish/Cloudflare) oraz selektory sesji w szablonie nagłówka.