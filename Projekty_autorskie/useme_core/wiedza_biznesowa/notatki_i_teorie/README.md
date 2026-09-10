# Baza typów klientów — zasady systemu

## Cel
Zbierać wiedzę o typach zleceniodawców na Useme i strategiach pisania ofert.

## Struktura katalogów
```
baza_klientow/
├── SYSTEM/
│   ├── README.md              ten plik, zasady
│   ├── track.md               rejestr wyników
│   ├── format/                zasady techniczne formatu ofert
│   ├── metodyki/              metody pracy, wszystkie TEORIA
│   └── szablony/              wzory do kopiowania
└── WIEDZA/
    ├── typy/                  KTO, 1 plik 1 typ, wszystkie TEORIA
    ├── strategie/             CO, 1 plik 1 strategia, wszystkie TEORIA
    ├── teorie.md              wszystkie teorie w 1 miejscu
    ├── potwierdzone.md        tylko po teście
    └── do_weryfikacji.md      kolejka testów
```

## ZASADA NADRZĘDNA
Wszystko w WIEDZA/ ma domyślnie status TEORIA, chyba że zostało jawnie przeniesione do potwierdzone.md.

Pliki typów i strategii to hipotezy robocze, nie reguły. AI piszące ofertę traktuje je jako podpowiedzi do testu, nie jako prawo.

Sygnał od realnego klienta zawsze wygrywa z wpisem w bazie.

## Dwa rodzaje dowodów
1. Dowód obserwacyjny. N ofert pokazuje ten sam wzorzec. Wzmacnia teorię, ale nie dowodzi skuteczności.
2. Dowód wyniku. Realny test: wysłana oferta, odpowiedź. Tylko to awansuje wpis do potwierdzone.md.

Oferta potwierdza istnienie wzorca, NIE skuteczność reakcji.

## Zapis teorii
Teoria w teorie.md powinna zawierać:
- Cytat, dokładny fragment z oferty
- Interpretację, co z cytatu wynika
- Dowody obserwacyjne, ile ofert pokazuje ten wzorzec

## Statusy
- potwierdzone, sprawdzone w praktyce
- niepotwierdzone, pojedyncze źródło
- teoria, hipoteza
- do weryfikacji, czeka na test

## Falsyfikacja zamiast potwierdzania
Teoria jest obalona, gdy znajdzie się jeden mocny kontrprzykład. Nie trzeba stu testów.

## Emersja nowej wiedzy
1. Anomalia, oferta nie pasuje do żadnego typu
2. Klaster, druga podobna anomalia tworzy podtyp
3. Typ, trzeci lub czwarty przypadek awansuje na osobny plik

Subagenci szukają anomalii przy każdej partii ofert.