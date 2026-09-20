# 05 — TREŚĆ OFERT I WYCENY: 100 hipotez

**Zawężenie:** ten dokument dotyczy WYŁĄCZNIE jakości generowanej **treści oferty** i **wyceny (kwota + dni)**. Pomija mechanikę wysyłki (osobne pliki `01`–`04`).

**Dowód kluczowy:** realne oferty bota są **dobre** (144357, 144275 — poziom ekspercki), ale **wyceny wymagają ciągłej korekty walidatorem** (liczne FAIL → obniżki 7000→6000, 7000→4500, 3500→3000). Problem nie jest w „brzydkiej treści", lecz w **spójności zakres↔cena↔brief**.

Legenda: 🔴 krytyczna · 🟠 wysoka · 🟡 średnia · ⚪ niska

---

## A. Struktura i styl treści (1–25)

1. 🔴 **Sprzeczny limit długości** — „max 35 linijek" (checklist) vs „tak długa jak wymaga zlecenie". [jak_pisac_oferty.md:228](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md) vs [:175-183](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md). Ryzyko: raz ucięte konkrety, raz rozwlekłość.
2. 🔴 **Sprzeczność nawiasów** — podręcznik zaleca nawiasy do żargonu ([:93](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md)), a [oferty_useme.md:9-10](file:///c:/Users/buchh/projects/useme/wiedza_biznesowa/notatki_i_teorie/oferty_useme.md) zabrania ich całkowicie.
3. 🟠 **Sprzeczność myślników** — „zero myślników" vs dopuszczenie list „inline w zdaniu" ([:169](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md)).
4. 🟠 **Brak sekcji struktury w generatorze** — [agent_02a](file:///c:/Users/buchh/projects/useme/prompts/generatory/agent_02a_opis_oferty.md) nie definiuje OTWARCIE/SEDNO/WYCENA/CTA; są tylko w podręczniku → model może je pominąć.
5. 🟠 **Sekcje „WYCENA:" zakazane**, a wycena musi być w treści → ryzyko, że kwota nie pojawi się w tekście.
6. 🟠 **Żargon nadmiarowy** — ton „DZIAŁA" chwali techniczne nazwy („DXGI", „webhook HMAC") u nietechnicznych klientów. [jak_pisac_oferty.md:160](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md).
7. 🟠 **Literówki dozwolone celowo** — „2-3 na całą ofertę", a walidator języka (06) wyłączony → ryzyko nadmiaru.
8. 🟠 **Brak wpięcia profili klienta** — profile/strategie nie są wprost ładowane do generatora → ton niedopasowany.
9. 🟡 **Otwarcie może łamać zakazy** — model może wygenerować „Szanowni Państwo"/„Przeczytałem ogłoszenie".
10. 🟡 **Zakończenie zakazane zwroty** — „Czekam na kontakt" może się pojawić.
11. 🟡 **Gwarancja sztywno wszędzie** — model może wstawiać „14 dni" nawet przy audycie (zakazane).
12. 🟡 **CTA „15-min call" sztywno** — powtarzalne w każdej ofercie → AI-smell.
13. 🟡 **Brak podpisu** — [agent_02a:64](file:///c:/Users/buchh/projects/useme/prompts/generatory/agent_02a_opis_oferty.md) zakazuje, ale wygrane oferty miały podpisy (Martin Smith, Paweł) → konflikt z „złotym wzorcem".
14. 🟡 **Powtarzalność otwarć** między ofertami** (mimo anty-powtórki).
15. 🟡 **Parafraza ogłoszenia** — zakazana, ale model często recytuje brief.
16. 🟡 **Recytowanie liczb/budżetu klienta** — zakazane (agent_08:88-91), ale kusi.
17. 🟡 **URL w treści** — zakazany, ale research może go wciągnąć.
18. 🟡 **Fakty o kliencie z researchu** — zakazane, ale to „najczęstszy błąd" (agent_08:16).
19. 🟡 **Długość nie skaluje się do budżetu** — wzorzec: 3 zdania dla 400 zł, 6 akapitów dla 14000 zł. Prompt tego nie wymusza wprost.
20. ⚪ **Format wyjścia `[RESEARCH_QUERY]`** może przeciec do treści.
21. ⚪ **Brak sekcji o problemie B przy słabym briefie** → ogólniki.
22. ⚪ **Korpo-język** („kompleksowe rozwiązanie", „dedykowany zespół").
23. ⚪ **Brak konkretu technologicznego** przy prostych zleceniach.
24. ⚪ **Za mało case'ów z liczbami** — złoty wzorzec ich wymaga (YOLO 80 typów, OpenCV).
25. ⚪ **Brak „wspólnika"** w CTA — wygrane często go mają.

## B. Kompletność i kontrola jakości (26–45)

26. 🔴 **Tylko 1 z 7 walidatorów aktywny** — działa wyłącznie agent_08; 03,04,05,06,07,20 = `enabled:false`. [chain_config.json:43,54,65,76,87,109](file:///c:/Users/buchh/projects/useme/prompts/chain_config.json).
27. 🔴 **Brak kontroli kompletności** — agent_07 (pokrycie wymagań) wyłączony → oferta może pominąć wymagania klienta.
28. 🟠 **Brak kontroli spójności** — agent_04 wyłączony → kwota może nie pasować do zakresu.
29. 🟠 **Brak kontroli tonu** — agent_05 wyłączony.
30. 🟠 **Brak kontroli języka** — agent_06 wyłączony.
31. 🟠 **Brak „ostatniego rzutu oka"** — agent_20 (AI-smell) wyłączony → słowa-wytrychy/gwiazdki mogą przejść.
32. 🟠 **Retry z 08 regeneruje tylko treść** — `retry_from_02a`, ale FAIL bywa o wycenie (02b) → naprawa nietrafiona. [chain_config.json:101](file:///c:/Users/buchh/projects/useme/prompts/chain_config.json).
33. 🟠 **`_is_pass` łagodny** — „PASS, ale..." przechodzi. [chain_executor.py:364-367](file:///c:/Users/buchh/projects/useme/chain_executor.py#L364-L367).
34. 🟠 **Cicha akceptacja FAIL** po wyczerpaniu rund. [chain_executor.py:619-624](file:///c:/Users/buchh/projects/useme/chain_executor.py#L619-L624).
35. 🟠 **Brak górnego capu kwoty** — `_waliduj` podnosi tylko dolny limit. [ai_pipeline.py:392-393](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L385-L394).
36. 🟡 **`_waliduj_kwote_w_tresci` tylko loguje** — kwota kalkulatora może nie być w treści. [ai_pipeline.py:292-295](file:///c:/Users/buchh/projects/useme/ai_pipeline.py).
37. 🟡 **`sanity_ok` tylko logowane** (nie blokuje w pipeline). [ai_pipeline.py:297-300](file:///c:/Users/buchh/projects/useme/ai_pipeline.py).
38. 🟡 **`sanity_ok` prawie nigdy False** — stawka liczona z godzin przed narzutami → ~96 zł/h > 80. [wycena_kalkulator.py:293-294](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py).
39. 🟡 **Brak kontroli dni vs kwota** — dni liczone z godzin, kwota dodatkowo z korekt i budżetu.
40. 🟡 **Brak walidatora pokrycia wymagań przy niepełnym briefie**.
41. 🟡 **`requires` agenta_08** wymaga research — brak research = walidator bez kontekstu.
42. ⚪ **Anty-powtórka: próg Jaccard 0.70** może przepuszczać podobne.
43. ⚪ **Po wyczerpaniu prób zostaje podobna wersja**. [ai_pipeline.py:281-282](file:///c:/Users/buchh/projects/useme/ai_pipeline.py).
44. ⚪ **Brak logu jakości** — nie wiadomo które oferty przeszły z FAIL.
45. ⚪ **Brak A/B testu strategii** — wszystkie 7 strategii ma pusty track.

## C. Wycena — mechanika i kalkulator (46–70)

46. 🔴 **AI dorzuca zakres spoza ogłoszenia** — dowód: moduł „Raporty PDF" (10h) w 144357 usunięty przez walidator. [stan.json 144357](file:///c:/Users/buchh/projects/useme/data/pipelines).
47. 🔴 **AI zawyża stawkę** — dowód: „stawka efektywna 96 vs 90 zł/h" (144357), „92 vs 90" (144188).
48. 🟠 **`brak modułów` → godziny 1.0** — kwota minimalna, maskowana przez MIN_KWOTA=500. [wycena_kalkulator.py:212-214](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py).
49. 🟠 **Rozjazd stawki mechanika↔kalkulator** — mechanika mówi 120 zł/h baza, kalkulator zaszyte 90. [wycena_kalkulator.py:20-22](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py).
50. 🟠 **Budżet tylko w górę** — `cena = budzet*0.85` gdy budżet wyższy; brak korekty w dół i brak ostrzeżenia. [wycena_kalkulator.py:282-284](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py).
51. 🟠 **Korekta konkurencyjna zaniża** — >30 ofert → ×0.85 → realnie ~70 zł/h. [wycena_kalkulator.py:42](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py).
52. 🟠 **Niespójność prompt↔parser** — agent_02b wymaga `[WYCENA_JSON]`, parser szuka `[WYNIK_KONCOWY]`. [agent_02b](file:///c:/Users/buchh/projects/useme/prompts/generatory/agent_02b_wycena_dni.md) vs [ai_pipeline.py:390](file:///c:/Users/buchh/projects/useme/ai_pipeline.py).
53. 🟠 **ValueError przy braku bloku** — kalkulator padnie/brak JSON → surowy JSON → brak `KWOTA:` → błąd. [ai_pipeline.py:387-391](file:///c:/Users/buchh/projects/useme/ai_pipeline.py).
54. 🟠 **Dni i kwota liczone rozłącznie** — duży budżet podnosi kwotę bez zmiany dni → możliwa niespójność.
55. 🟡 **`kwota_rynek` dla „male" brane wprost** — może być oderwane od nakładu. [wycena_kalkulator.py:170-172](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py).
56. 🟡 **Mnożniki ryzyka cap 1.8** — może nie pokryć realnego ryzyka.
57. 🟡 **Stawka losowana z pasma 82–110** — niedeterministyczna między runami.
58. 🟡 **Retainer `retainer_stawka_mies`** słabo zwalidowany.
59. 🟡 **Zaokrąglanie** ≤2000→50, ≤10000→500, >10000→1000 — może tworzyć „sztuczne" kwoty. [wycena_kalkulator.py:136-142](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py).
60. 🟡 **MIN_DNI=7 sztywne** — wymusza 7 dni nawet dla małych zleceń.
61. 🟡 **Landing cap 22h / one-page 25h** — może ucinać realny zakres.
62. 🟡 **Mnożnik „brak specyfikacji" ×1.3** — przy niepełnym briefie zawyża.
63. 🟡 **`nowa_technologia` bufor ×1.3** — detekcja niepewna.
64. ⚪ **KROK 8 prowizja/PIT (~88%)** — może nie wpływać na kwotę oferty.
65. ⚪ **KROK 9.5 cel 80–90% budżetu** — arbitralny.
66. ⚪ **Brak wyceny dla „retainer" w kalkulatorze** — może wychodzić dziwnie.
67. ⚪ **`DNI_WEEKEND=1.30`** — rzadko używane, ryzyko przeszacowania dni.
68. ⚪ **CAP_MNOZNIKOW=1.8** — globalny, może kolidować z korektą konkurencyjną.
69. ⚪ **Brak wyceny wartości/korzyści** — tylko koszt.
70. ⚪ **Kwota nie odzwierciedla poziomu profilu** (2 mies./5 umów) poza mnożnikiem ×0.75.

## D. Brief/kontekst zlecenia → treść (71–85)

71. 🟠 **Zlecenia z niepełną specyfikacją brane** — `prompt_ai1.md:14` → generator nie ma z czego zbudować problemu B → ogólniki.
72. 🟠 **Brak walidatora kompletności przy słabym briefie** (agent_07 OFF).
73. 🟠 **`full_desc` z tagami HTML** — `<p>` może przeciec do treści. [test15](file:///c:/Users/buchh/projects/useme/lab/test_results/test15_result_tura3.md).
74. 🟡 **Umiejętności puste** — brak na detalu → brak kontekstu technicznego. [test13](file:///c:/Users/buchh/projects/useme/lab/test_results/test13_result_tura3.md).
75. 🟡 **Detale pobrane niekompletne** — wyjątek połknięty → brief niepełny. [engine.py:162](file:///c:/Users/buchh/projects/useme/engine.py).
76. 🟡 **Tytuł może być „?"** — błąd parsowania z test10. [ai_proposals.json](file:///c:/Users/buchh/projects/useme/lab/test10_flow_v2/intermediate/ai_proposals.json).
77. 🟡 **Research może wstrzyknąć obce fakty** — zakaz, ale ryzyko.
78. 🟡 **Brak danych o budżecie klienta** — większość „Do negocjacji" → wycena „od zera".
79. 🟡 **Profil klienta nie rozpoznany** — mimo 9 profili w wiedzy.
80. 🟡 **Strategia nie dobrana automatycznie** — 7 strategii nieaktywnych.
81. ⚪ **Kategoria może być źle wykryta** → kontekst branżowy zły.
82. ⚪ **Brief mieszany (np. mobile+web)** → trudny do rozbicia.
83. ⚪ **Zlecenie „dokończenie po kimś"** — wyceniane bez zapasu.
84. ⚪ **Pośrednik („mój klient")** — marża w dół, nie wykrywane.
85. ⚪ **Brak wykrycia „rekrutacyjny pod przykrywką"** → zła wycena zamiast aplikacji.

## E. Spójność treść↔wycena↔strategia (86–100)

86. 🟠 **Kwota w treści może nie zgadzać się z kalkulatorem** — tylko logowane (pkt 36).
87. 🟠 **144330 sprzedaje audyt zamiast realizacji** — AI samo przyznaje, że nie rozumie zlecenia, i proponuje etap wstępny za 4500 zł. Ryzyko utraty klienta szukającego wykonawcy.
88. 🟡 **Case study nie zawsze dopasowany** do stacku klienta.
89. 🟡 **Widełki zamiast kwoty** — zakazane, ale Klaudia (wzorzec) miała widełki → konflikt.
90. 🟡 **„Do negocjacji" w wycenie** — zakazane, ale kusi przy niepełnym briefie.
91. 🟡 **Stawka godzinowa** — zakazana, ale model może ją podać.
92. 🟡 **Gwarancja/opieka** niedopasowana do typu zlecenia.
93. 🟡 **Brak Blueprint/audytu przy dużym niejasnym zakresie** — wzorzec (KZKujawska) tego wymaga.
94. ⚪ **Mnożnik antyhourly** nieaktywny przy kliencie hourly.
95. ⚪ **Brak weryfikacji „czy kwota < budżet"** gdy budżet jawny niższy.
96. ⚪ **Brak sekcji ryzyka** w treści (wzorce ją mają).
97. ⚪ **Brak mierzalnych celów** dla „świadomy-wymagający".
98. ⚪ **Ton entuzjastyczny** wymagany dla „firmowy-emocjonalny" — prompt tego nie wymusza.
99. ⚪ **Brak personalizacji „Pani/Pan + imię"** z ogłoszenia.
100. ⚪ **Brak jednego źródła prawdy o „złotym wzorcu"** — wygrane oferty to ręczne notatki, nie wpięte w prompt.

---

## TOP-10 hipotez (treść + wycena)

| # | Hipoteza | Dowód | Test |
|---|---|---|---|
| 1 | AI dorzuca zakres spoza briefu | „Raporty PDF" usunięte z 144357 | log walidatora 08 |
| 2 | AI zawyża stawkę | 96 vs 90 zł/h (144357), 92 vs 90 (144188) | porównaj kwotę przed/po retry |
| 3 | Tylko 1/7 walidatorów aktywny | chain_config.json | włącz 03,04,05,06,07,20 i porównaj |
| 4 | Retry z 08 regeneruje złą warstwę | on_fail=retry_from_02a | sprawdź FAIL-y o wycenie |
| 5 | Sprzeczny limit długości | :228 vs :175 | zmierz długość wygenerowanych |
| 6 | Nawiasy: podręcznik vs notatka | :93 vs oferty_useme:9 | grep nawiasów w treści |
| 7 | sanity_ok nie łapie zaniżeń | wycena_kalkulator:293 | policz stawki z magazynu |
| 8 | Budżet tylko w górę | wycena_kalkulator:282 | przypadek budżet < cena |
| 9 | 144330 audyt zamiast realizacji | treść 144330 | oceń dopasowanie do briefu |
| 10 | Brak wpięcia „złotego wzorca" | wygrane = ręczne notatki | porównaj z wygenerowanymi |

---

## Wniosek przekrojowy

**Treść ofert NIE jest głównym problemem** — obecne oferty (144357, 144275) są konkretne i eksperckie, na poziomie wygranych. **Głównym problemem jest WYCENA i spójność zakres↔cena↔brief**:
- AI **systematycznie zawyża i dorzuca zakres** spoza ogłoszenia.
- Poprawność ratuje **deterministyczny kalkulator + walidator 08** (który wymusza retry i obniża kwoty).
- System jest **kruchy**: opiera się na 1 aktywnym walidatorze z 7; gdy on zawiedzie, nikt nie sprawdzi kompletności, tonu ani spójności.

Kierunek naprawy (gdy użytkownik zechce): (1) włączyć walidatory 03–07 i 20, (2) rozdzielić retry wyceny (02b) od treści (02a), (3) dodać górny cap i twardą blokadę sanity, (4) rozstrzygnąć sprzeczności w podręczniku, (5) wpiąć „złoty wzorzec" i profile klientów do promptu generatora. **Nic nie zmieniono w kodzie — to plan.**