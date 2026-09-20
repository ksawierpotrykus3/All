# Test 06 – Wynik

**Status:** ✅
**Data:** 2026-08-06 15:05

## Flow
1. Pobieranie listy: ✅ (10 ofert, metoda: playwright)
2. Marker: ✅ (NOWE – pierwsze uruchomienie)
3. AI Selekcja: ✅ (5 wybranych, 5 odrzuconych)
4. Pobieranie szczegółów: ✅ (5/5)
5. AI Propozycje: ✅ (5/5 wygenerowanych)
6. Wyniki: ✅

## Wybrane oferty
- Automatyzacja Make/n8n/Python: web scraping, OCR i AI (powód: idealne dopasowanie – Python, scraping, automatyzacja)
- Stworzenie Inteligentnej Platformy AI do Zakupu i zarzadzadzania Bazami (powód: AI + automatyzacja 24/7)
- API Allegro, Shopper (powód: integracje API)
- Integrator pomiędzy Optima a Base.com (powód: integracja systemów)
- Wykonawca automatyzacji procesów i AI – Nextcloud, e-mail, ChatGPT Business, Make/n8n (powód: automatyzacja + AI)

## Wygenerowane propozycje
| Oferta | Proponowana stawka | Propozycja (skrót) |
|--------|-------------------|-------------------|
| Automatyzacja Make/n8n/Python: web scraping, OCR i AI | 110 PLN/h netto | Profesjonalna propozycja z wymienieniem konkretnych bibliotek (BeautifulSoup, Scrapy, Playwright, Tesseract) |
| Stworzenie Inteligentnej Platformy AI | 90 PLN/h | Propozycja – AI błędnie zinterpretowało jako aplikację desktopową do PDF (zamiast platformy AI) |
| API Allegro, Shopper | 95 PLN/h netto (1500-2000 PLN całość) | Propozycja z szacunkowym budżetem |
| Integrator Optima-Base.com | 100 zł/h netto | Propozycja z konkretami o ERP i e-commerce |
| Automatyzacja procesów i AI | 120 PLN/h netto | Dobra propozycja łącząca Python + no-code |

## Problemy
- **Cloudflare blokuje Playwright headless** – pierwsze uruchomienie dało Cloudflare challenge (0 ofert). Drugie uruchomienie przeszło pomyślnie – Cloudflare czasem przepuszcza ruch.
- **Fallback do offers.json z test02** – zaimplementowano jako zabezpieczenie, ale nie został użyty (Playwright zadziałał).
- **AI dla oferty nr 2 (Platforma AI)** – DeepSeek wygenerował propozycję dotyczącą "aplikacji desktopowej do PDF" zamiast platformy AI. Prawdopodobnie pomyliło kontekst z inną ofertą (drukowanie PDF z Płatnika) – do poprawy w prompt engineering.
- **WebFetch** – zwraca markdown, nie surowy HTML; nie można na nim używać selektorów CSS. Nadaje się tylko jako referencja.

## Pliki
- Skrypt: `lab/test06_full_flow/test06_full_flow.py`
- Wyniki: `lab/test06_full_flow/full_flow_results.json`
- Selekcja AI: `lab/test06_full_flow/intermediate/ai_selection.json`
- Propozycje: `lab/test06_full_flow/intermediate/ai_proposals.json`
- Szczegóły ofert: `lab/test06_full_flow/intermediate/details/*.json`
- Parsowane oferty: `lab/test06_full_flow/intermediate/parsed_offers.json`
- Marker: `lab/test06_full_flow/last_offer.txt`