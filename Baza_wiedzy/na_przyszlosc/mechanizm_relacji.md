# MECHANIZM RELACJI I ŁĄCZENIA DANYCH (Linker)

> **Status:** Wymóg architektoniczny do zaprojektowania przed wdrożeniem.  
> **Kontekst nadrzędny:** Ten dokument jest potrzebny na kolejnym etapie do kontynuowania prac nad systemem – **najpierw trzeba precyzyjnie wymyślić ten mechanizm, zanim zacznie się go budować w kodzie.**

---

## Kontekst użytkownika (Cytaty 1:1)

**O konieczności zaprojektowania przed budową:**
> „i daj kontekst ze np 2 i 3 sa potrzebne potem do kontyniowania pracy bo pierw trzeba wymyslic zeby zaczac pracowac”

**O zakazie zanieczyszczania profili surowymi danymi:**
> „pdfy badan. podzielone dla stref PDF ale potem segregowane na kategorie. informacje o mnie. tez swoje miejsce. jesli ejst polaczenie miedzy pdf a mna to musi istniec cos innego niz wrzucenie PDFA z badaniem do wiedzy o mnie.”

**Relacje to nie folder, to osobny mechanizm:**
> „a relacje nie pasuja do tego w ogole! to powinien byc oddzielny mechanizm.”

---

## 1. Założenia mechanizmu

1. **Izolacja źródeł:**
   * Pobrane materiały (np. artykuł naukowy w PDF) znajdują się wyłącznie w swojej dedykowanej strefie.
   * Strefa profilu użytkownika (zasady, cechy myślenia) zawiera wyłącznie czyste fakty o użytkowniku.
2. **Most referencyjny (Relacja):**
   * Powiązanie między faktem o użytkowniku a zewnętrznym dokumentem tworzone jest jako **osobny łącznik**.
   * Łącznik zawiera:
     * Wskaźnik do wiedzy o użytkowniku (np. zasada inżynierii reaktywnej).
     * Wskaźnik do źródła zewnętrznego (np. badanie o cognitive offloading, strona 4).
     * Zwięzłe uzasadnienie powiązania (dlaczego to badanie potwierdza lub uzupełnia tę zasadę).
3. **Korzyść architektoniczna:**
   * Żadna ze stref nie zostaje zaśmiecona duplikatami ani nadmiarowym tekstem.
   * AI może analizować powiązania bez konieczności ładowania całych plików PDF do profilu użytkownika.
