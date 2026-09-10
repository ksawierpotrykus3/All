# 01 — Zlecenie: SCP (IdoSell) — sprzedaż do CZ/SK + blokada detalu

**Klient:** Paweł (SCP)\
**Kontakt zastępczy:** Joanna Kuć — <joanna.kuc@scp1.pl>\
**Mój e-mail do kontaktu:** <sentinel.audit.system@gmail.com>\
**Status:** wykonane (technicznie przygotowane + instrukcja do manualnego wprowadzenia stawek)

***

## Wiadomość 1 — Paweł (zleceniodawca)

Mam zestawienie kosztów transportu. Przesyłam je w załączeniu.

Zadanie polega na włączeniu możliwości zakupów dla klientów z Czech i Słowacji z automatyczną kalkulacją kosztów wysyłki do tych krajów. Technicznie powinno działać dla wszystkich wersji językowych zarówno dla klientów niezalogowanych jak i zalogowanych (czyli wcześniej zarejestrowanych).

Daj proszę znać jak to widzicie cenowo i terminowo.

P.S. Muszę sprawdzić czy oferowanie klientom detalicznym z Czech i Słowacji nie wymaga spełnienia przez nas dodatkowych warunków od strony prawnej, dlatego w pierwszej kolejności być może powyższa możliwość powinna być dostępna wyłącznie dla firm czeskich i słowackich.

***

## Wiadomość 2 — Ksawier (ja)

Biorąc pod uwagę dodanie reguł wagowo-kodowych (sporo manualnego wprowadzania) i napisanie dedykowanego skryptu do koszyka pod kątem walidacji, wstępnie wyceniam to na ok. 1 500 – 2 000 zł netto. Czas realizacji: od 3 do 5 dni roboczych.

Zanim jednak ruszymy i doprecyzuję na 100% kwotę, potrzebuję od Ciebie 3 informacji.

1. W załączniku widzę tylko cennik dla Czech. Podeślesz też plik ze stawkami dla Słowacji?
2. Daj proszę znać, jak ostatecznie decydujesz. Jeśli mamy zablokować detal, to technicznie zrobię to tak: przy wyborze kraju CZ lub SK system całkowicie ukryje zakupy „na paragon" i wymusi podanie nazwy firmy oraz numeru NIP.
3. W pliku podałeś kwoty netto. Zwróć uwagę, że jeśli zablokujemy detal i będziesz sprzedawał tylko do czeskich/słowackich firm, to taka transakcja kwalifikuje się przeważnie jako WDT (Wewnątrzwspólnotowa Dostawa Towarów). Wymaga to najczęściej naliczania w koszyku stawki VAT 0% (odwrotne obciążenie). Dopytaj proszę swoją księgowość, czy właśnie tak mam skonfigurować koszty wysyłki na froncie, żeby sklep poprawnie to przeliczał.

***

## Wiadomość 3 — Paweł

Cześć,

Ok, akceptujemy 1000 zł. Proszę o realizację.

W czasie mojej nieobecności proponuję kontakt mailowy z Joanną, gdyż dostęp do konta UseMe mam tylko ja, a jest dwuetapowa weryfikacja, której prawdopodobnie przed urlopem mi nie wyłączą.

Joanna Kuć - <joanna.kuc@scp1.pl>

Ja podam jej Waszego e-maila - <sentinel.audit.system@gmail.com> - aby wiedziała z jakiego adresu ma się spodziewać od Was wiadomości. :)

***

## Wiadomość 4 — Ksawier (ja) — 2026-06-24

Cześć,

Wszystko jasne, udanego urlopu.

Zmiana założeń upraszcza sprawę po naszej stronie. Za samo przygotowanie zaplecza technicznego i kodowanie weźmiemy 1000 zł netto i na fakturę jak poprzednio.

Co do rozwiązania technicznego to w standardzie silnik tak ładnie nam tego nie rozdzieli, więc napiszemy pod to customowy skrypt JS. Wepniemy go w bramkę koszyka i jak klient wybierze kraj z UE (poza PL), skrypt ukryje opcję paragonu i zablokuje przejście dalej bez podania NIP-u. Resztę świata odcinamy całkiem brakiem przypisanych stref dostaw, więc checkout ich nawet nie przepuści.

Ustawimy też strefy dla reszty UE, żeby mieli tylko odbiór własny i koszty do potwierdzenia. Dla CZ i SK postawimy profile dostaw i po prostu podrzucimy Joannie instrukcje, gdzie w panelu macie wklepać kwoty z waszego excela. Zepniemy też od razu konfigurację podatkową, żeby po weryfikacji VAT EU IdoSell sam zrzucał podatek na 0% i pokazywał firmom w koszyku od razu kwoty netto.

***

## Wiadomość 5 — Paweł — 2026-06-24

Cześć,

Zakup przez użytkownika niezalogowanego (gościa) ma być możliwy wyłącznie dla firm, jeżeli jest to klient zagraniczny z UE. Zakupy dla klientów spoza UE powinny być zablokowane.

W związku z tym każdy taki klient musi być zobowiązany podać NIP / VAT ID.

Klienci z Czech i Słowacji, dzięki cennikowi transportu, będą mogli kupić towar wraz z wysyłką. Pozostali klienci zagraniczni z UE powinni również móc złożyć zamówienie, ale wyłącznie w opcji „odbiór własny" lub „do potwierdzenia koszt transportu".

Macierz z kosztami transportu wg wagi i kodów pocztowych możemy wypełnić sami, podobnie jak zrobiliśmy to kiedyś dla kosztów transportu w Polsce.

Od Was oczekujemy technicznego rozwiązania i wskazania, w którym miejscu mamy manualnie wprowadzać dane.

Ceny towaru i koszty transportu dla firmowych klientów zagranicznych (bo tylko tacy mogą być) w każdym wariancie powinny być podawane w koszyku w cenach netto.

P.S. Od jutra jestem na urlopie. W tym czasie w moim zastępstwie będzie reagować tutaj koleżanka Joanna lub zareaguję ja po powrocie (po 07.07.).

***

## Ustalenia końcowe / zakres (podsumowanie)

- **Cena:** 1 000 zł netto (faktura jak poprzednio).
- **Blokada detalu dla UE spoza PL:** customowy skrypt JS wpięty w bramkę koszyka.
- **Zakres skryptu:**
  - kraj UE (poza PL) → ukrycie opcji „paragon", wymuszenie podania NIP / VAT ID,
  - reszta świata → całkowicie zablokowana (brak stref dostaw),
  - CZ i SK → profile dostaw + automatyczna kalkulacja kosztów wg cennika (waga/kody),
  - pozostałe kraje UE → tylko „odbiór własny" lub „koszt transportu do potwierdzenia".
- **Podatki:** po weryfikacji VAT EU → VAT 0% (WDT, odwrotne obciążenie), ceny netto w koszyku.
- **Manualne dane:** macierz kosztów transportu wg wagi i kodów pocztowych — wypełnia klient (Joanna) wg instrukcji.

***

