# ANALIZA HELIKOPTERA — WNIOSKI I NASTĘPNE KROKI

**Data:** 2026-08-14
**Źródła:** `ANALIZA_HELIKOPTER.md` (v5, pomiary z 12 pcapów) + `research/` (teoria Unity/Windows, czytanie kodu) + weryfikacja stanu kodu w repo.

---

## 1. Werdykt w 3 zdaniach

1. Ranking = **kolejność dotarcia C2S `get.dig.treasure.reward` na serwer** (model FCFS) — potwierdzone 1:1 w 12 pcapach (push order = pozycja w UI). Intuicja „im szybciej wyślesz diga, tym lepsze miejsce" jest **prawdziwa**.
2. **Wojska tylko skracają licznik (z ~2 h w dół). NIE są sygnałem startu.** Sygnał startu = **zniknięcie licznika → helikopter zamienia się w skarb → dopiero wtedy można kliknąć**. Wcześniej fizycznie się nie da. Teoria „beacon = przybycie armii" była **BŁĘDNA** — zweryfikowane z userem 2026-08-14.
3. Rozwiązanie (sekcja 18 ANALIZY) było **zaimplementowane, ale martwe**: brak scapy w zależnościach + brak Npcap w systemie → sniffer działał jako NO-OP → bot realnie jeździł po starej ścieżce OCR+mysz, która daje dokładnie ~3. miejsce (Cost 0.220–0.300 s).

## 1b. Mechanizm potwierdzony przez usera (WAŻNIEJSZE niż teoria z pcap)

- Wojska **tylko skracają licznik**. Przyjazd 1., 2., n-tego konwoju **nie otwiera skarbu**.
- Kolejność: licznik znika → **helikopter zamienia się w skarb** → dopiero wtedy jest klikalny.
- Klikać można **dopiero po zniknięciu licznika**; wcześniej nic się nie dzieje.
- Model nagrody: **tylko pierwszy, który kliknie** (FCFS).
- „Cost" = **czas / szybkość w sekundach** (mniejsze = lepsze).
- **Twardy dowód z usera:** wygrana rundą z kliknięciem **0.231 s po zniknięciu licznika** → skarb NIE mógł być klikalny przed licznikiem. Gra dla ludzi, nie dla botów.
- Konkurencja jest **ostra na innych serwerach** (nie tylko na tym jednym).

## 2. Fakty potwierdzone pomiarami (n=12 rund, 12 pcapów)

| Metryka | Wartość | Źródło |
|---|---|---|
| Cykl serwera dig→push | 183–193 ms (mean 186) | 12 rund, deterministyczne |
| RTT c→s (ACK na digu) | p50 18 ms, p90 51 ms, max 54 ms | n=37 |
| RTT s→c | p50 40 ms (ogon = batchy S2C) | n=3630 |
| Rozstaw pushów rankingu | p50 22.8 ms (batching serwera) | n=102 |
| **rank ~ react_march** (dig po beaconie) | **r = +0.643** | najsilniejszy czynnik |
| rank ~ react_s2c / rtt_c2s / dig_push / dig_delay | +0.500 / +0.313 / −0.346 / −0.067 | S2C słaby, tick0 bez znaczenia |
| Reakcja klienta na beacon | 16–201 ms (śr ~90); zwycięzcy **16–57 ms** | h7/h8/h12 |
| Cost (UI) | = nasz push − pierwszy marsz = reakcja + ~186 ms | potwierdzone h11/h12 |
| P(1. miejsce) δ=0 (inject) / F1 16 ms / 23 ms / 40–60 ms | 64% / 36% / 27% / 27% | tabela 18.7 |

Warunek 1. miejsca: **dig ≤ 60 ms po beaconie** (zwycięzcy 16–57 ms). Wygrane rundy miały margines +14…+37 ms, przegrane −41…−249 ms.

## 3. Mity w modelu seniora (konfrontacja z dowodami)

- **„Wysłać można dopiero jak skrzynka się pojawi / timer 0"** — PRAWDA (potwierdzone przez usera). Skarb jest klikalny dopiero po zniknięciu licznika. Wcześniejsza teoria „digi przed tick0 są przyjmowane" opierała się na surowych pcapach, gdzie komenda `get.dig.treasure.reward` nosiła timestamp wcześniejszy niż rewardtime — ale to przesunięcie zegara serwera, NIE dowód że kliknięcie było możliwe przed licznikiem.
- **„DLL inject, żeby wysłać od razu przy timer 0"** — nadal zbędne/ryzykowne: bot MUSI czekać na zniknięcie licznika (skarb), bo wcześniej klik = brak efektu. Najszybsza legalna droga = zareagować na **helikopter → skarb** w sieci i kliknąć natychmiast. Wstrzyknięcie C2S na porcie 8851 dałoby tylko tyle, ile da naciśnięcie klawisza/myszy w momencie pojawienia się skarbu.
- **„3. miejsce 0.220–0.300 s — najgorzej nie jest"** — to strata o 30–80 ms z 1. miejscem; na tym serwerze bywa wygrane 0.231 s, ale na innych serwerach konkurencja jest ostra.

## 4. Znalezisko w kodzie — dlaczego nadal 3. miejsce

Ścieżka beacon→F1 (18.8/18.9) istnieje w kodzie:
- `src/bot/network_sniffer.py` — `BeaconEvent`, `_decode_tlv` (0x80/0xA0+zlib), `on_beacon`, detekcja pierwszego marsza po ciszy ≥5 s.
- `src/bot/dig_engine.py` — `on_beacon` → `press_key("F1")` przy δ=0 + warm spam 6× co 40 ms.
- `src/bot/bot_runner.py` — wiring `DigEngine` + `NetworkSniffer(on_beacon=…)`.
- `src/bot/macro_engine.py` — sniffer start/stop wokół fazy `watch_timer` (try/finally).

**Ale:**
- `scapy` NIE było w `pyproject.toml` → `NetworkSniffer.start()` zwracał `False` → log „no-op (scapy unavailable)".
- **Npcap NIE był zainstalowany** w systemie (brak usługi `npcap`, brak `C:\Program Files\Npcap`).
- `LOGS.txt` — **zero** linii `network sniffer` / `server countdown` → sniffer nigdy nie odpalił w żadnej sesji.

Wniosek: beacon nigdy nie wyzwalał F1; bot działał po ścieżce OCR+mysz (kanał ~90 ms po beaconie → 3. miejsce). To jest twarda przyczyna, nie teoria.

## 4b. Drugi martwy punkt: F1 trzymane tylko ~25 ms (za krótko o jedną klatkę)

Nawet po ożywieniu sniffera dig może być technicznie niewidzialny dla gry — to ten sam błąd co wcześniej z myszą (hold 3–15 ms), tylko w drugim kanale:

- `DigEngine.on_beacon` → `press_key("F1")` → `interception.press()` → `key_down` → `time.sleep(KEY_PRESS_DELAY)` → `key_up`.
- `KEY_PRESS_DELAY = 0.025` w `.venv\Lib\site-packages\interception\inputs.py:23` → **F1 trzymany ~25 ms**.
- Research/Unity: przy 60 FPS klawisz musi przetrwać ≥1 granicę klatki → **35–40 ms**; przy 120 FPS **17–20 ms**.
- Testy `tests/bot/test_dig_engine.py` sprawdzają liczbę naciśnięć i latencję, ale **nie weryfikują hold** → regresja jest niewidoczna.

Wniosek: przed testem A/B (krok 6) podnieść hold F1 do ≥35–40 ms (np. `KEY_PRESS_DELAY` na 0.035–0.040 lub jawny `hold_key` w `press_key`).

## 5. Co już zrobiono

- **scapy 2.7.0** dodane przez `uv add scapy` → `pyproject.toml` + `uv.lock` zaktualizowane.
- Weryfikacja: `import scapy.all` OK, `network_sniffer._scapy_async_sniffer` jest aktywne (sniffer wyszedł z no-op).

## 6. Następne kroki (nowa, prosta kolejność — 2026-08-14)

1. **Zmień hold kliku z ~15 ms na ~35 ms.** To jedyna zmiana, która odblokowuje ślepy spam. (Kod: `click_at` trzyma ~5–15 ms; klawisz `KEY_PRESS_DELAY = 0.025` → 25 ms. Oba podnieść do 35–40 ms.)
2. **Uruchom bota w trybie ślepego spamu** (klika wokół końca, bez wykrywania timera). Zbierz 3–5 rund.
   - Zaczyna wygrywać → KONIEC. Zero wykrywania licznika, zero sieci, zero Npcap.
   - Nadal 2–3. miejsce → dopiero wtedy krok 3.
3. **Opcjonalnie, tylko jak 2. zawiedzie:** wykryć zmianę „helikopter → skarb" obrazem i kliknąć natychmiast w tej samej chwili. (Nie czytając cyferek licznika — sam obraz zmiany.)

## 7. Czego NIE robić

- **Nie dotykać DLL / hookowania procesu gry** — ryzyko bana > zysk; nie omija limitu odczytu wejścia.
- **Nie budować nic na snifferze/beaconie/Npcap** dopóki ślepy spam z holdem 35 ms nie zostanie przetestowany — to martwa ścieżka z błędną teorią.
- **Nie ekstrapolować timera z OCR** — licznik to tylko ozdoba; jeśli już wykrywać moment, to obraz zamiany helikoptera w skarb.

## 8. Rysy w ANALIZA_HELIKOPTER.md (otwarte, do weryfikacji na żywo)

1. **h8: F1 vs mysz** — sekcje 2/5 (tabela sesji + LOGS) opisują h8 jako mysz @(960,520) 100c/s, a sekcje 16.10/18.8 jako F1 → 16 ms. Wniosek „F1 ~6× szybszy niż mysz" stoi na tej sprzecznej parze; wymaga A/B.
2. **h11: push order = 1. miejsce, UI pokazało 3.** — jedyna niezgodność „push = ranking"; wymaga powtórki manualnej (3–5×).
3. **aac (uniformity)** — nie koreluje z pozycją (h3/h4/h6 z aac = 3., h9/h10 bez = 8./5.); wyłącznie sygnatura, nie mechanizm kary.
4. **Brak sekcji 19 w ANALIZIE** — nagłówek v5 (linia 3) zapowiada „sekcję 19: kto klika pierwszy i dlaczego + formalny model kolejkowania + pseudokod", ale plik fizycznie kończy się na sekcji 18.10 (linia 1005). Finalna synteza nie została zapisana.
5. **Dwa serwery — ryzyko dla sniffera** — `15.197.67.229:8851` = plaintext TLV, ale tylko **0,5–1% ruchu**; `57.128.218.35:21117` = **98–99% ruchu, obfuskowany** (pierwszy bajt 0x59/0x5d/0xf9). Sniffer nasłuchuje wyłącznie 8851. Otwarte: czy beacon `push.world.march.new` jest w ogóle widoczny na 8851 w realnym ruchu, czy ginie na obfuskowanym kanale 21117.
6. **Test 5 sekund (model nagrody) — nadal bez wyniku** — research (`04_WNIOSKI_I_DECYZJA.md`) wymaga empirycznego testu: po zniknięciu licznika odczekać 5 s i dopiero kliknąć. Nagroda przyznana → model partycypacyjny (szybkość bez znaczenia, cały wyścig niepotrzebny); brak nagrody/błąd → FCFS (każda ms się liczy). Test rozstrzyga 80% decyzji i dalej wisi.
7. **Event merging w Unity** — `InputSettings.disableRedundantEventsMerging` domyślnie `false`; warm spam 6× F1 co 40 ms może być scalany przez silnik w jedno zdarzenie. Nie potwierdzono dla tej gry; do obserwacji przy A/B.
