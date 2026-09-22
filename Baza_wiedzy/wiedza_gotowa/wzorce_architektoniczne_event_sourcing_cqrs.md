# WZORCE ARCHITEKTONICZNE: EVENT SOURCING I CQRS (Opracowanie)

> **Kategoria:** Wiedza technologiczna / Wzorce projektowe systemów danych.  
> **Status:** Gotowe opracowanie wzorców sprawdzonych w sieci (z badania 2026-09-13).

---

## 1. Event Sourcing (Rejestr zdarzeń append-only)

* **Źródło:** Microsoft Architecture Patterns, Martin Fowler.
* **Zasada działania:**
  * Zamiast przechowywać w bazie tylko aktualny stan obiektu (który nadpisuje poprzednie wartości), system zapisuje pełną, nienaruszalną historię wszystkich zdarzeń w trybie dopisywania (*append-only*).
  * Strumień zdarzeń jest jedynym i ostatecznym źródłem prawdy (*System of Record*).
  * Bieżący stan aplikacji można w dowolnym momencie odtworzyć od zera, odtwarzając sekwencję zdarzeń (*replay*).
* **Zaleta:** Całkowity brak ryzyka przypadkowego skasowania lub uszkodzenia historii. Brak sztywnego schematu przy zapisie.

---

## 2. CQRS (Command Query Responsibility Segregation)

* **Źródło:** Greg Young, Microsoft Patterns & Practices.
* **Zasada działania:**
  * Całkowite oddzielenie operacji **zapisu danych** (Command) od operacji **odczytu danych** (Query).
  * Zapis trafia szybko do prostego rejestru (np. surowy plik / log).
  * Odczyt opiera się na **projekcjach** (*read models* / widokach zmaterializowanych) – specjalnie przeliczonych widokach danych zoptymalizowanych pod szybkie wyszukiwanie.
* **Właściwość kluczowa:**
  * Projekcję można w dowolnym momencie skasować, zmienić jej format i przeliczyć od nowa ze strumienia źródłowego.
  * Zmiana sposobu prezentacji danych nie wymaga migracji bazy ani ryzyka utraty danych źródłowych.
