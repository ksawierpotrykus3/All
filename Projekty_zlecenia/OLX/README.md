# OLX Bot Workspace

Autobuy OLX BuyWithDelivery + detektor okazji. Metoda: najpierw twardy dowód na żywo, potem kod (jak Vinted).

---

## Centralne Źródło Prawdy

Cała zweryfikowana dokumentacja inżynierska projektu znajduje się w jednym nadrzędnym pliku:
👉 **[gemini/KOMPENDIUM_OLX.md](gemini/KOMPENDIUM_OLX.md)**

Struktura folderu badawczego:
- `gemini/README.md` — indeks repozytorium badawczego
- `gemini/raporty/` — raporty z poszczególnych eksperymentów (raporty 00-04)
- `gemini/skrypty/` — skrypty testowe (logowanie headed, auto-refresh, testy API)
- `gemini/dane/` — surowe dowody JSON i zrzuty ekranu

---

## Status Projektu (2026-09-02)

| Moduł | Status | Szczegóły |
|---|---|---|
| **Detektor ofert** | [UDOWODNIONE] | Sekwencyjne ID + sliding window + hole sweeper (9-14 min przewagi) |
| **Obejście CloudFront** | [UDOWODNIONE] | `curl_cffi` z profilem `chrome124` |
| **Trwała sesja / Auto-refresh** | [UDOWODNIONE] | Wdrożony `persistent_context` z Vinted (`profiles/olx_profile`), token odnawia się w tle |
| **Slider CAPTCHA (DataDome/WAF)** | [UDOWODNIONE] | Odblokowany przez trwały profil; w trybie headless brak blokad |
| **Silnik Pay & Ship** | [UDOWODNIONE] | Prawdziwy backend to `pl.ps.prd.eu.olx.org` (przechwycone wszystkie kroki do podsumowania) |
| **Blokada 15 minut** | [HIPOTEZA] | Do ekranu podsumowania oferta jest aktywna; blokada prawdopodobnie zapada przy „Zamawiam i płacę” |
