# Test 04 – Wynik

**Status:** ✅
**Data:** 2026-08-06

## Sprawdzenie endpointu
- Endpoint dostępny: tak
- Modele: `deepseek-v4-pro`, `deepseek-vision`

## Prompt
```
Przeanalizuj poniższe oferty i wybierz te, które pasują dla programisty Python specjalizującego się w web scrapingu i automatyzacji. Zwróć JSON z polami: selected (lista wybranych) i rejected (lista odrzuconych) z uzasadnieniem dla każdej decyzji.

[Lista 10 ofert z pliku offers.json - tytuły, kategorie, budżety, opisy]
```

## Odpowiedź AI
```json
{
  "selected": [
    {
      "title": "Automatyzacja Make/n8n/Python: web scraping, OCR i AI",
      "justification": "Tytuł i opis wprost wymieniają web scraping, Pythona i automatyzację. Zakres prac (tworzenie skryptów do scrapowania i automatyzacji procesów) idealnie odpowiada specjalizacji programisty."
    }
  ],
  "rejected": [
    {
      "title": "Stworzenie narzędzia do: drukowania w pdf zestawów z Płatnika",
      "justification": "Aplikacja desktopowa do generowania PDF. Nie dotyczy web scrapingu ani automatyzacji – typowe programowanie narzędziowe poza specjalizacją."
    },
    {
      "title": "Stworzenie Inteligentnej Platformy AI do Zakupu i zarzadzadzania Bazami.",
      "justification": "Choć system może wymagać pozyskiwania danych, to ogłoszenie koncentruje się na budowie pełnej platformy AI i systemu decyzyjnego. Wykracza poza wąską specjalizację w web scrapingu, nie wskazuje też Pythona jako wymagania."
    },
    {
      "title": "Oprogramowanie dedykowane ecommerce PHP + React/Vue z integracjami",
      "justification": "Stack technologiczny to PHP i JavaScript (React/Vue), nie Python. Projekt aplikacji e-commerce, bez elementów web scrapingu."
    },
    {
      "title": "Konfigurator wyglądu/personalizacji produktu na stronie internetowej Shoper Storefront",
      "justification": "Projekt frontendowy (konfigurator wizualny) dla platformy Shoper. Brak związku z web scrapingiem, automatyzacją czy Pythonem."
    },
    {
      "title": "API Allegro, Shopper",
      "justification": "Integracja API z preferowanym językiem VBA. Nie jest to projekt Pythonowy, a integracje e-commerce różnią się od specjalizacji w web scrapingu."
    },
    {
      "title": "Aplikacja po przeniesieniu na produkcje wywala się",
      "justification": "Zadanie z pogranicza administracji serwerami i debugowania wdrożeń. Nie dotyczy web scrapingu ani automatyzacji w Pythonie."
    },
    {
      "title": "Integrator pomiędzy Optima a Base.com",
      "justification": "Integracja systemów ERP z platformą sprzedażową. Ogłoszenie nie wymaga Pythona ani nie opisuje zadań związanych z web scrapingiem."
    },
    {
      "title": "Aplikacja webowa wspierająca zarządzanie siecią sprzedaży i działu handlowego",
      "justification": "Tworzenie aplikacji webowej w PHP od podstaw. Niezgodne ze specjalizacją (Python, web scraping, automatyzacja)."
    },
    {
      "title": "Wykonawca automatyzacji procesów i AI - ewidencja zleceń, Nextcloud, e-mail, ChatGPT Business, Make lub n8n",
      "justification": "Automatyzacja procesów firmowych za pomocą narzędzi no-code/low-code (Make, n8n). Nie wymaga programowania w Pythonie ani web scrapingu – kluczowa jest integracja gotowych rozwiązań."
    }
  ]
}
```

## Podsumowanie
- DeepSeek V4 Pro (`deepseek-v4-pro`) poprawnie odpowiedział na prompt
- AI trafnie wyselekcjonowała 1 ofertę pasującą do profilu (Python + web scraping + automatyzacja)
- 9 ofert zostało odrzuconych z logicznymi uzasadnieniami (inny stack technologiczny, brak Pythona, inna specjalizacja)
- Odpowiedź w formacie JSON zgodna z wymaganiami

## Problemy
- Biblioteka `openai` (v2.53.0) zwracała surowy strumień SSE (Server-Sent Events) mimo ustawienia `stream=False`. Rozwiązanie: użyto bezpośrednio `requests` z ręcznym parsowaniem chunków SSE.
- Należało zainstalować `openai` przez `python -m pip install openai` (zwykłe `pip install` nie działało w środowisku).