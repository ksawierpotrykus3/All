# Zlecenie — smartcare

## Informacje ogólne

- **Zleceniodawca:** smartcare (OLX / Vinted)
- **Wykonawca:** Ksawier Potrykus (awatar)
- **Status:** start planowany od następnego miesiąca
- **Priorytet:** najpierw bot OLX, potem ewentualnie Vinted

## Bot OLX

### Stan obecny
- Poprzednia wersja bota została skasowana — do napisania od zera (nie poprawianie po zmianach OLX).
- Odbudowa po opłaceniu z góry.
- Klient ma wersję bota po kilku poprawkach, ale wtedy jeszcze nie wszystko działało dobrze.
- Link do najnowszej wersji bota (którą ma klient) został wysłany mailem.

### Klucze API OLX (deweloperskie)
- **Client ID:** 202745
- **Client Secret:** HucUsS3hhReAr5j5V4BN5I85rlOM0y2y5cFGoKjJbXuPO5YI

### Jak działał bot (do odtworzenia)
- Wysyłał powiadomienia na **Telegram**.
- Dawał czasem nawet **~10 minut przewagi** nad przeglądarką dzięki API OLX.
- Metoda: wyliczanie/przewidywanie **ID ogłoszeń** — bot brał całe ID i na ich podstawie wyliczał ID ogłoszeń, które dopiero zostaną wstawione (trafiał w przyszłe ID).

### Kategorie / filtry
- **iPhone'y** — cała Polska
- **MacBooki** — cała Polska
- **Auta do 12 000 zł** — Mazowsze

### Plan testów
- Puścić AI „w samopas", żeby wyłowiło to, czego potrzebujemy z OLX.
- AI ma mieć dostęp do strony OLX, żeby widzieć, co dokładnie wpada na OLX.
- Porównywać nasze powiadomienia (z API) z tym, co faktycznie pojawia się na stronie.
- Weryfikacja: czy klucz API OLX w ogóle działa po zmianach na OLX (nie wygasł / API się nie zmieniło).

## Bot Vinted (plan — później)

### Wymagania klienta
- Architektura serwerowa bez Discorda: VPS + panel webowy (Web UI) lub CLI.
- Ultra-wysoka prędkość (szybsze niż publiczne boty typu kops.gg).
- Zaawansowane filtry: marka, stan, cena, słowa kluczowe, kategorie, rozmiary.
- Multikonto Autocop: 3–4 konta jednocześnie.
- Ochrona przed banami: rotacyjne proxy rezydencjalne premium, fingerprint spoofing, losowe opóźnienia „ludzkie".

### Ustalenia / ryzyka (komunikat od wykonawcy)
- To inna liga niż OLX: monitoring + automatyczne kupowanie + multikonto + proxy + anty-fingerprint.
- Wycena zależna od: budżetu na start, kto ogarnia konta Vinted i proxy, ile zakupów dziennie i na ilu kategoriach.
- To projekt z utrzymaniem miesięcznym (Vinted regularnie zmienia zabezpieczenia).
- Brak gwarancji niebanowania kont — można tylko zmniejszyć ryzyko.