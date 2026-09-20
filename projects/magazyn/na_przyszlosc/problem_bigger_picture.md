# PROBLEM: UTRZYMANIE „BIGGER PICTURE” PRZEZ AI (Badanie i Rozwój)

> **Status:** Zagadnienie do autonomicznego rozwijania przez zespół modeli / przygotowanie pod architekturę.  
> **Hierarchia:** Ten dokument to **jeden z konkretnych przykładów zastosowania zespołów AI w tle** (podlega pod nadrzędną koncepcję: [`zespoly_ai_i_zadania_w_tle.md`](file:///c:/Users/buchh/projects/magazyn/na_przyszlosc/zespoly_ai_i_zadania_w_tle.md)).  
> **Cel pliku:** Zadanie badawcze dla **zespołu modeli** (nie jednego modelu): analizować rozmowy, budować hipotezy dotyczące utrzymania kontekstu i generować pytania robocze dla użytkownika (które potem Jarvis może przepisać/zadać w czacie).

---

## Kontekst użytkownika (Cytaty 1:1)

**O roli zespołu modeli i relacji do zadań w tle:**
> „1. jak cos to nie model ale zespol modeli  
> 2. to jest przyklad zastosowania tylko 1 z wieku  
> tam samo  1. podlega jako przyklad do 2.”

**Koncepcja roli tego pliku jako zadania dla AI:**
> „to jest np plik ktory bym wrzucil tam i jakos kazal AI bym to rozwijac np nadzorowal rozmowy z Ai i sprawdzal czy jest cos coeiakwego. budowal hipotezy i wrzucal putania do specjalnego pliku a potem moze bym kazal jarvisowi przepisac mi te pytania.”

**O obowiązku trzymania całości:**
> „no nie ma obowiazku ale jakbym stworzyl miejsce odpowiedzialne za takie cos to wteyd BY mial obowiazek. rozumiesz mowie to na zapas.”

**O naturze modeli LLM i zakazie przedwczesnej kapitulacji:**
> „szczerze? co jesli modele AI po prostu takie sa? co jesli im powiem idealnie zdefiniuje co maja robic a itak nie beda mialy bigger picutre?”  
> „jaki ejst sens mowienia ze sie nie da odrazu? co mi da to ze nie sprobuje?”

---

## 1. Definicja problemu

* **Wąskie widzenie modeli:** Gdy AI wchodzi w szczegółową dyskusję, ma tendencję do zapominania o nadrzędnym celu (attention dilution / context rot).
* **Skutek uboczny:** Użytkownik zostaje zmuszony do przejęcia kontroli nad „bigger picture”, co paraliżuje jego zdolności analityczne (jego mózg działa na 100% wyłącznie przy reakcji na wąski szczegół).
* **Cel inżynieryjny:** Sprawdzić granice modeli LLM i zaprojektować mechanizm oparty o **zespół modeli**, który w tle pilnuje stanu całości bez angażowania użytkownika.

---

## 2. Kierunki badania dla zespołu modeli (Do rozwijania w tle)

Zespół modeli operujący na tym pliku ma:
1. **Analizować surowe rozmowy** (`rozmowy/`): Wychwytywać momenty, w których model tracił wątek lub zmuszał użytkownika do pilnowania ogółu.
2. **Budować hipotezy:** Jak technicznie kotwiczyć stan projektu (np. zewnętrzny rejestr stanu, dynamiczny system prompt z mapą zależności, podział ról w zespole: model-obserwator vs model-rozmówca).
3. **Generować pytania do pliku roboczego:** Wszelkie kluczowe wątpliwości zrzucać do specjalnego pliku pytań, aby Jarvis mógł je później sformatować i zadać użytkownikowi w dogodnym momencie.

---

## 3. Żywy wzorzec rozwiązania (Zaobserwowany w praktyce 2026-09-20)

**Cytat użytkownika 1:1:**
> „i teraz zauwaz tryb  co teraz robie, mowie z gory co o czyms sadze i model to poprawia. jakbym mial  kiedykolwiek nie mowie ze teraz bo to ciezkie system gdzie lancuch sam robi wszystko tylko daje mi pytani na ktore odpowiadam w taki spsobo iidelanie interpretuje moje odpowiedzi wdraza i poprawia to no. to jest przyklad bigger picture jakby byl rozwiazany ten problem”

### Jak w praktyce wygląda rozwiązany problem Bigger Picture:
* **Użytkownik (Władza / Sędzia):** Mówi krótko „z góry”, co sądzi o danej propozycji (bez konieczności pamiętania o 10 plikach, kodzie czy strukturze katalogów).
* **Łańcuch AI w tle (Zarządca całości):** Sam trzyma w ryzach mapę projektu, przygotowuje konkretne punkty do reakcji, a po otrzymaniu intuicyjnej odpowiedzi użytkownika – idealnie ją interpretuje, wdraża we właściwe miejsca i natychmiast aktualizuje stan.
* **Esencja:** Użytkownik nie musi pilnować ani trzymać w głowie całości – to łańcuch w tle bierze na siebie 100% odpowiedzialności za strukturę, spójność i wdrożenie.

