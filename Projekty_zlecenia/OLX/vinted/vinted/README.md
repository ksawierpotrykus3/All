# Vinted — mapa projektu

Repozytorium wiedzy o bocie Vinted. Punkt startowy: [raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md](raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md).

## Struktura

```
vinted/
├── README.md                      ← jesteś tutaj
├── raporty/
│   ├── 00_POWTORZENIA_I_SPRZECZNOSCI.md   ← ZACZNIJ TU
│   ├── 01_sonda_api/             pomiary API (wysoka wiarygodność)
│   ├── 02_reverse_engineering/   deklarowany checkout (nieudowodniony)
│   ├── 03_weryfikacja/           audyt + wyniki testów (wysoka wiarygodność)
│   ├── 04_niewiadome/            uczciwa mapa luk
│   ├── 05_konkurencja/           kops.gg i jak zejść poniżej
│   ├── 06_biznes/                wycena i odpowiedź klientowi
│   └── 07_niezweryfikowane/      treści AI/niepotwierdzone (NIE ufać)
├── dane/                          zrzuty, cookies, JS, odpowiedzi API
├── narzedzia/                     skrypty pomocnicze
└── testy/                         skrypty testowe (probe_*, test_*)
```

## Najważniejszy wniosek

Warstwa **detekcji** (katalog, filtry, rate-limit, losowość ID) jest solidnie zmierzona i spójna. Warstwa **zakupu** (checkout, płatność, 3DS, omijanie DataDome) jest **nieudowodniona** — jedyny realny pomiar to HTTP 403. Każda liczba o „czasie zakupu" poniżej 5–6 s (kops) nie ma pokrycia w testach.