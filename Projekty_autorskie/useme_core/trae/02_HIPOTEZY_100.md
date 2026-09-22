# 02 — 100 hipotez: dlaczego wysyłka NIE działa (mechanika)

> Zawężenie na treść+wycenę → patrz [05_TRESC_I_WYCENA_100_HIPOTEZ.md](05_TRESC_I_WYCENA_100_HIPOTEZ.md).
Legenda: 🔴 krytyczna · 🟠 wysoka · 🟡 średnia · ⚪ niska

## A. Formularz / fałszywy sukces (1–25)
1. 🔴 Fałszywy WYSLANO po URL [form_driver.py:158](file:///c:/Users/buchh/projects/useme/form_driver.py#L149-L159).
2. 🔴 Opis nie trafia do rich-editora [form_driver.py:84](file:///c:/Users/buchh/projects/useme/form_driver.py#L78-L91).
3. 🔴 Turnstile nieobsłużony w formularzu.
4. 🟠 Draft przywracany i nienadpisany.
5. 🟠 Kruche `button:has-text('Wyślij')`.
6. 🟠 Kruche `'Przejdź do podsumowania'`.
7. 🟠 Zbyt krótkie czekanie po submit.
8. 🟠 Brak walidacji pól przed submitem.
9. 🟠 Radio praw autorskich tylko przy „decyzja freelancera".
10. 🟠 UnboundLocalError na `res` [engine.py:351-356](file:///c:/Users/buchh/projects/useme/engine.py#L351-L356).
11. 🟡 Baner cookies przykrywa przycisk.
12. 🟡 MIN_WORK_DAYS nadpisuje dni.
13. 🟡 int(proposal.dni) wybucha przy „7 dni".
14. 🟡 Wycena „5 000 zł" nie wpada do number input.
15. 🟡 Selektor kwoty przy multi-stage.
16. 🟡 contenteditable łapie zły element.
17. 🟡 dispatchEvent bez natywnego settera.
18. 🟡 Podwójny klik „Wyślij".
19. 🟡 Brak obsługi modala potwierdzenia.
20. 🟡 Sesja wygasa między prepare a submit.
21. ⚪ wait_for_load_state w try/except połyka timeout.
22. ⚪ Screenshot w trakcie animacji.
23. ⚪ AuthenticationRequiredError = break [engine.py:346-350](file:///c:/Users/buchh/projects/useme/engine.py#L346-L350).
24. ⚪ input[value='Wyślij'] nie pokrywa type=submit.
25. ⚪ Formularz wymaga dodatkowych pól.

## B. Łańcuch AI (26–50)
26. 🔴 Proxy 127.0.0.1:4571 nie działa [chain_executor.py:44](file:///c:/Users/buchh/projects/useme/chain_executor.py#L44).
27. 🔴 Pusty łańcuch → RuntimeError [ai_pipeline.py:244](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L244-L245).
28. 🔴 Brak [WYNIK_KONCOWY] → ValueError [ai_pipeline.py:385](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L385-L394).
29. 🟠 Selekcja timeout → przepuszcza wszystkie [ai_pipeline.py:194](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L194-L196).
30. 🟠 Selekcja zły format → 0 ofert.
31. 🟠 Zegar 360 s abortuje [chain_executor.py:471](file:///c:/Users/buchh/projects/useme/chain_executor.py#L471-L479).
32. 🟠 Pusty output ×3 → None [chain_executor.py:554](file:///c:/Users/buchh/projects/useme/chain_executor.py#L554-L564).
33. 🟠 Circuit breaker → None.
34. 🟠 Watchdog wątku → None.
35. 🟠 Timeout/RequestException → None.
36. 🟠 Cicha akceptacja FAIL.
37. 🟠 _is_pass łagodny.
38. 🟡 Brak kalkulatora → slot 02b bez wyceny.
39. 🟡 Proxy 502/503/504 → None.
40. 🟡 Pusty strumień → None.
41. 🟡 Auto-continue urwany tekst.
42. 🟡 Guard pustego zlecenia → None.
43. 🟡 parse_ai_json_response maskuje zły JSON.
44. 🟡 Slot 01 fallback BRAK_ISTOTNYCH_FAKTOW.
45. 🟡 Anomalie JSON z proxy (BOM/escape).
46. 🟡 Anty-powtórka zostawia podobną wersję.
47. ⚪ Model nothink myli kontekst (test06).
48. ⚪ _extract_wycena_json nie łapie wariantu.
49. ⚪ Walidator 08 zbyt surowy.
50. ⚪ on_fail bez targetu → None.

## C. Gubienie ofert (51–70)
51. 🔴 144256 utknęło na POBRANO_DETALE.
52. 🔴 12 ofert POBRANO_DETALE bez pipeline.
53. 🟠 Dedup per konto pomija cicho [engine.py:132](file:///c:/Users/buchh/projects/useme/engine.py#L120-L136).
54. 🟠 Podwójna blokada [engine.py:195,201](file:///c:/Users/buchh/projects/useme/engine.py#L195-L204).
55. 🟠 Zapisana propozycja pomija AI [engine.py:246](file:///c:/Users/buchh/projects/useme/engine.py#L246-L259).
56. 🟠 Marker blokuje starsze [storage.py:280](file:///c:/Users/buchh/projects/useme/storage.py#L280).
57. 🟠 exists dedup po ID [storage.py:63](file:///c:/Users/buchh/projects/useme/storage.py#L63).
58. 🟠 GLOBAL-DUP tylko loguje [engine.py:312](file:///c:/Users/buchh/projects/useme/engine.py#L312-L319).
59. 🟡 Wyjątek detali połknięty.
60. 🟡 Brak try/except na fetch_job_details.
61. 🟡 DRY-RUN tylko 1 najnowsza.
62. 🟡 author_id „anonim".
63. 🟡 Slug tylko 2 wartości.
64. 🟡 ID kategorii zmienne.
65. 🟡 Parser gubi oferty bez article.job.
66. ⚪ Cichy fallback kont.
67. ⚪ Limit MAX_OFFERS_PER_CATEGORY=10.
68. ⚪ filter_offers bez try/except.
69. ⚪ Wyścig zlecenie zamknięte.
70. ⚪ PRZYGOTOWANA przepuszczana.

## D. Infrastruktura (71–85)
71. 🔴 Cookies wygasłe → break.
72. 🟠 Loader cookies cicho ignoruje błąd.
73. 🟠 Cloudflare przy headless.
74. 🟠 __cf_bm ~30 min.
75. 🟠 Brak świeżego cf_clearance.
76. 🟡 Statyczny UA.
77. 🟡 Kill switch STOP.
78. 🟡 MAX_RUN_MINUTES=30.
79. 🟡 Rate-limit przy delay=0.
80. 🟡 evaluate+fetch = 403.
81. ⚪ WebSocket/SSE blokuje networkidle.
82. ⚪ Fałszywy cloudflare_detected.
83. ⚪ Proxy stealth niewystarczający.
84. ⚪ Cookie domain/path źle.
85. ⚪ Viewport 1280x800.

## E. Konfiguracja/dane (86–95)
86. 🟠 Sanity-blok <80 zł/h.
87. 🟠 MIN_KWOTA=500, MIN_DNI=7.
88. 🟡 DRY_RUN=False.
89. 🟡 USE_MOCK_AI=False.
90. 🟡 ZBIERACZ_AKTYWNY=False.
91. 🟡 MAX_OPIS_DLUGOSC=6000.
92. ⚪ Walidatory wyłączone.
93. ⚪ TIMEOUT_DNI=3.
94. ⚪ Progi prompt vs kalkulator.
95. ⚪ Brak limitów dziennych.

## F/G. Timing/proces (96–100)
96. 🟠 Wyścig marker vs zapis.
97. 🟡 wait 3 s niewystarcza.
98. 🟡 Checkpoint wznawia od złego slotu.
99. ⚪ Zapis atomowy zostawia stary plik.
100. ⚪ Brak logu zbiorczego.

## TOP-10
A1 fałszywy WYSLANO · C51/52 cichy stop · B26 proxy · A2 opis rich-editor · A5/B4 pusty łańcuch · D71 cookies · E86 sanity · C55 stara propozycja · A3 Turnstile · A6 selektory.