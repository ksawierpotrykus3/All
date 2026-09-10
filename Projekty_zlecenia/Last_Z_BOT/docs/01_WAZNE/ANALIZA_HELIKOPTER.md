> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Analiza helikoptera (dig treasure) — kompletna wiedza

**Ostatnia aktualizacja:** 2026-08-14 — wersja **v5**: ostateczna synteza. Ponownie uruchomiono `_tmp_pcap\all12_stats.py` na istniejącym `mega_out\all12.json` — **wszystkie liczby v3/v4 odtworzone 1:1** (cykl serwera p50≈186 ms, RTT c→s p50 18 ms, korelacja rank~react_march r=+0.643, push spacing p50 22.8 ms). Nowość v5: **sekcja 19** — zwięzła, kompletna odpowiedź na pytanie „kto klika pierwszy i dlaczego" + formalny model kolejkowania serwera + pełny rozkład czynników determinujących + model przewidywania idealnego momentu z szacunkami prawdopodobieństwa + pseudokod algorytmu automatycznego klikania. Sekcje 1–18 to historia i pomiary; sekcja 19 to finalna, samowystarczalna synteza.

---

## 1. Cel

Ustalić, co decyduje o pozycji w rankingu kopania skarbu (helicopter dig, serwer 751, świat MAVE/BRAVES) i jak klikać, żeby być 1. miejsce.

**Ustalenia od usera (ważne — korygują wcześniejsze analizy):**
- Klikanie JEST liczone przez grę — bez klikania nie dostaje się nagrody.
- We WSZYSTKICH sesjach (w tym h8) klikano przez python interception — różnica między sesjami to nie "interception vs nie", tylko **F1 (klawisz)** vs **klik myszy @(960,520)**.
- Helikopter jest na środku ekranu, klikanie trafia w środek.
- "Cost" na ekranie = czas, np. 0.201 s (h8, 1. miejsce), 0.386 s (h9, ostatnie), 0.274 s (h10, 5. miejsce).

---

## 2. Mechanizm pozycji w rankingu (stan wiedzy na 2026-08-14)

> **Notka:** sekcje 9–12 (pełna analiza 10 pcapów) potwierdzają i uszczegóławiają poniższe — z WYMAGANYMI korektami (zweryfikowane 2026-08-14):
> - „hipoteza B (prędkość diga)" to pełny mechanizm (ranking = kolejność dotarcia digów), a „bot nie ma wpływu na moment diga" jest błędne — bot może digować szybciej niż klient (sekcja 11–12).
> - **Dig wyzwala PRZYBYCIE ARMII** (burst `push.world.march.new` = beacon), NIE S2C z `rewardtime` — patrz fakty 2–4 niżej (h8: dig 16 ms po beacona, 266 ms PRZED S2C; h7: 57 ms po beacona bez S2C; h10: 94 ms po beacona, 92 ms PRZED S2C).
> - Moje wcześniejsze „S2C z rewardtime +117 ms (h8)" było BŁĘDNE — to był beacon (marsze); prawdziwy S2C przyszedł +399 ms.
> - Timing diga względem tick0 = **−591…+301 ms** (h1/h2/h5/h6 digują PRZED ogłoszonym rewardtime — serwer przyjmuje do kolejki).

### POTWIERDZONE FAKTY
1. **Pozycja = kolejność `push.dig.treasure.reward`** (S2C). Potwierdzone 1:1 we wszystkich sesjach:
   - h8: `rewarduid="1461030734000751;1777937038000751;1661183580000751"` — KiriGami2 pierwszy = 1. miejsce
   - h9: pushy w kolejności mutz0001 → 陰濕嚕 → BestNightmare → 神慕奈美 → tammy00910 → Abby → KiriGami2 (zbiorczy pkt) = ostatnie
   - h10: Abby → WinTahLily013 → Her Benevolence → LiZeeeeee → KiriGami2 = 5. miejsce
   - h7: 5 digów (.716/.744/.799/.822/.891) → push KiriGami2 pierwszy @ .909 = 1. miejsce (pierwszy dig → pierwszy push, przetwarzanie serwera 193 ms)
2. **Diga (`get.dig.treasure.reward`, C2S) wysyła KLIENT GRY — wyzwalany przybyciem ARMII do punktu skarbu (burst `push.world.march.new` = beacon), NIE S2C z `rewardtime`.**
   - **Dowód h7**: w całym pcapię h7 nie ma ANI JEDNEGO S2C `world.get.detail.new` z `rewardtime` bliżej niż 85 s przed rundą (pełny skan: 10 pakietów, wszystkie przed 20:14:36, ostatni pkt 19446; surowo i po dekompresji zlib). Klient wykopał o 20:16:01.716 = **57 ms po beacona** (marsze @ .659) → 1/5.
   - **h8**: beacon (marsze) @ +117 ms, dig @ +133 ms (**+16 ms po beacona, −266 ms PRZED S2C** z rewardtime @ +399 ms) → 1/8.
   - **h10**: beacon @ +93 ms, dig1 @ +187 ms (**+94 ms po beacona, −92 ms PRZED S2C** @ +279 ms) → 5/10.
   - **h9 r1**: beacon @ +99 ms, S2C @ +143 ms, dig @ +301 ms (157 ms po S2C — jedyna sesja, gdzie dig poszedł PO S2C i najwolniejsza reakcja).
   - **h1/h2**: beacon @ −670/−674 ms, S2C z finalnym rewardtime @ −615/−630 ms, digi @ −573/−591 ms (+39/+41 ms po S2C) — przyjęte do kolejki, rank 2/8.
3. **S2C z `rewardtime` NIE jest sygnałem diga** — przychodzi +72…+399 ms po tick0 (h8: +399 — PO digu klienta!), bywa przed tick0 (h4: −10 ms, h1/h2: −615/−630 ms), a w h7 nie przyszedł wcale. Wartość `rewardtime` bywa PROJEKCJĄ granicy okna (nieliniowo skracaną, ~3000 s: h1, h9) — nie wolno jej traktować jako niezawodnego tick0 (wyjątek: finałowe ogłoszenie rundy w trakcie = realny otwór, h8/h9 r1/h10).
4. **Czas diga względem serwerowego tick0 jest zmienny: −591…+301 ms** (h1 −573, h2 −591, h5 −199, h6 −173, h4 +3, h3 +95, h7 ~+32, h8 +133, h9 +301, h10 +187) — w pełni kontrolowany przez klienta gry (przybycie armii + reakcja 9–200 ms, zwycięzcy 16–57 ms po beacona), NIE przez bota. Digi PRZED tick0 (h1/h2) są przyjmowane do kolejki i liczone wg kolejności dotarcia.

### Tabela porównawcza sesji

| Sesja | Pozycja | Cost | S2C rewardtime | Dig C2S (po rewardtime) | Push KiriGami2 | aac | Spam (metoda) | Start spamu przed eventem |
|---|---|---|---|---|---|---|---|---|
| h3 | 3/10 | — | +72 ms | +95 ms (23 ms po S2C; beacon −972) | +282 ms | **TAK** (uniformity 0.109–0.143) | F1, 19.2 CPS, 360 kl. | 3.5 s |
| h4 | 3/10 | — | −10 ms | +3 ms (13 ms po S2C) | +189 ms | **TAK** (uniformity 0.014) | F1, 18.8 CPS | 4.3 s |
| h7 | 1/5 | 0.825 (OCR) | **BRAK — 0 pakietów z rewardtime w pcapie** | ~+32 ms (57 ms po beacona) | +193 ms po digu | brak | mysz @(960,520), 18.9 CPS | 0.25 s |
| h8 | **1/8** | 0.201 | **+399 ms** (beacon +117) | +133 ms (16 ms po beacona) | +201 ms | brak | mysz @(960,520), 100c/s→~55 | 0.62 s |
| h9 | ostatnie | 0.386 | +143 ms (beacon +99) | +301 ms (157 ms po S2C) | +488 ms (zbiorczy) | brak | mysz @(960,520), 100c/s | 1.5 s |
| h10 | **5/10** | 0.274 | **+279 ms** (beacon +93) | **+187 ms (dig1, 94 ms po beacona); dig2 +289** | +370 ms | brak | mysz @(960,520), 100c/s | 1.56 s |

### KLUCZOWE WNIOSKI
1. **Klikanie nie wpływa na pozycję.** h8 vs h10: identyczne klikanie (100c/s × 7 s @960,520), a pozycja 1 vs 5 — różnica wyszła z reakcji klienta na beacon: h8 dig +16 ms po beacona vs h10 +94 ms → dig +133 vs +187 → push +201 vs +370.
2. **Szybkość klikania nie ma znaczenia**: h7 = 19 CPS, h8 = 100 CPS → oba 1. miejsce.
3. **aac korelacja (hipoteza A — "kara za automat")**: h3/h4 klikały 3.5–4.3 s PRZED eventem → dig z `aac.uniformity>0` → 3. miejsce; h7/h8 klikały <0.7 s przed → brak aac → 1. miejsce. **OSŁABIONA przez h9/h10**: bez aac (91B) a jednak złe pozycje (czynnikiem była prędkość diga). Kontrprzykład: ostatnia runda h3 (1 dig z aac 0.132) = 1/8.
4. **Hipoteza B (prędkość diga) — aktualnie główna**: pozycja = kolejność nadejścia `get.dig.treasure.reward` na serwerze. Diga wysyła klient gry W MOMENCIE PRZYBYCIA SWOJEJ ARMII (burst `push.world.march.new` = beacon; h7: bez żadnego S2C z rewardtime, dig 57 ms po beacona = 1/5); timing diga = −591…+301 ms po tick0 (zwycięzcy 16–57 ms po beacona), **całkowicie poza kontrolą bota**.
5. **h7 dowód, że klient NIE potrzebuje S2C z rewardtime**: pełny skan pcapy (surowo + zlib@offsets 3/4/5) — zero pakietów z `rewardtime` w oknie 85 s przed rundą; klient wykopał 57 ms po beacona (przybycie armii) i wygrał (1/5).
6. h4 dig był najszybszy w historii (+3 ms), h3 +95 ms — a mimo to 3. miejsce, bo konkurencja digowała wcześniej (h3: Her Benevolence, xx ai xx; h4: Kemen, LiZeeeeee — ich pushy 150–164 ms przed naszym).
7. **h1/h2 dowód kolejkowania**: digi wysłane −573/−591 ms PRZED ogłoszonym rewardtime zostały przyjęte (rank 2/8, bez errorCode) — serwer sortuje wg kolejności dotarcia, nie odrzuca wczesnych digów (zbieżne z nieliniowością rewardtime: finałowe ogłoszenie może przyjść 615 ms przed wartością, a klient diguje +25…42 ms po nim).

### OPEN QUESTIONS
- Co dokładnie robi `aac` (uniformity) — czy serwer karze, czy to tylko sygnatura?
- Dlaczego w h7 nie przyszedł żaden S2C z rewardtime, a w h8/h9/h10 przyszedł (72–399 ms po tick0)? (możliwe: serwer wysyła tylko gdy gracz jest "podłączony" do minigry przez UI/polling)
- Czym dokładnie jest "Cost" na ekranie (0.201 h8, 0.386 h9, 0.274 h10, 0.825 h7?) — pasuje tylko w h8 do push−beacon; prawdopodobnie liczony od lokalnego przybycia armii lub od diga do pusha z dodatkowym offsetem.
- Czy klikanie w ogóle jest konieczne (h7: klient wykopał bez S2C z własnego timera — możliwe, że też bez klikania, ale user potwierdza, że bez klikania nie ma nagrody).
- Dlaczego reakcja klienta na beacon jest tak zmienna (9–200 ms)? W h8: 9 ms po naszym marszu, w h9 r1: 201 ms — czy to opóźnienie renderu/klatki, czy dryf zegara lokalnego?

---

## 3. Formaty pakietów (TLV)

### Nagłówek/wrapper
- Nagłówek: `80 <len:2BE> 12`
- Wrapper: `c`=i8(1), `a`=i16(13/29), `p`={c=string, r=i32=-1, p=params}
- Typy: 01/02=i8, 03=i16, 04=i32, 05=i64 (ms BE), 06=f32, 08=string (2B BE), 11=array, 12=mapa

### Kwirki parsera
- Klucz `c` jest nadpisywany (wrapper i8 vs string) → `find_cmd`/`find_all` w `_pcap_compare.py`
- S2C `world.get.detail.new` z rewardtime NIE parsuje się przez find_cmd → eventy wykrywane surowo po `b"rewardtime"`
- **Kompresja (odkryta w h7)**: pakiet `a0 <len:2BE> 78 <zlib>` — zlib zaczyna się na offsecie 3; po dekompresji payload zaczyna się od `12` + body mapy. Dekodowanie: `b"\x80" + len(body).to_bytes(2,"big") + b"\x12" + body[1:]`. Pakietów skompresowanych z `rewardtime` NIE widać w raw skanach — trzeba dekompresować (offsety 3/4/5).
- W h7 wszystkie 10 pakietów z `rewardtime` są niekompresowane i wszystkie przed 20:14:36 — rundy klikniętej (20:16:01) serwer NIE ogłosił S2C wcale (pełny skan potwierdzony).
- Pakiet `push.mail` (h7 pkt 24256) zawiera `custom: {"c":{"xmlId":"100314"},"s":{"v":4,"ready":1,"hasReward":1}}` — sygnał nagrody pocztą.

### Kluczowe komendy
- **C2S `get.dig.treasure.reward`**: `{c, a, p: {c: 'get.dig.treasure.reward', r: -1, p: {_id, uuid}}}`
- **S2C `push.dig.treasure.reward`**: `{p: {p: {uid, name, pic, abbr, picVer, point}, c: 'push.dig.treasure.reward'}, a, c}` — kolejność tych pakietów = pozycja
- **S2C `world.get.detail.new` (z rewardtime)**: `{p: {p: {careerType, rewardtime, afn, endtime, alName, _ht, pointType, pic, picVer, speed, point, careerLv, rewarduid, uid, pointId, srcServer, name, progress, startTime, state, _id, marchs}}}` — sygnał STATUSU rundy (rewardtime bywa projekcją ~3000 s; NIE wyzwala diga — diga wyzwala beacon `push.world.march.new`)
- **S2C `push.receive.reward`**: nagroda. h3/h4: `{p: {p: {reward, total}, type: 5, value: 1000}`, total=46871/47871; h8: items `type=7` (itemId 230112 count 0x5f=95 rewardAdd=5; itemId 230111 count 0x2369=9065 rewardAdd=0x5dc=1500), uuid 1401455620934266720 / 1393867417805057919
- **S2C `push.world.point.update`**: points change (type=change, points arr) — ranking points

### Struktura `aac` w digu (h3, dig 180B)
```
uniformity      f32  (0.109–0.143 h3; 0.014 h4)
durationFactor  f32  (0.0)
score           i32  (0)
noPauseDuration i32  (1 h3; 4 h4)
isBot           i8   (0)
```
**Brak licznika klików w aac.** Dig bez aac = 91B.

### UUID sesji (pole uuid w C2S dig)
- h3: uuid=1404002969137114916 (digi z aac)
- h8: uuid=1404003122346651631
- h9: uuid=1404003127161712578 (_id=379)
- h10: uuid=1404003131012083561 (_id=446)

### Parametry rund (rewardtime − startTime)
- h8: startTime=1786671570383, rewardtime=1786671587914 → runda **17.53 s**, speed=10
- h9: startTime=1786674013458, rewardtime=1786674018164 → runda **4.71 s**, speed=16
- h10: startTime=1786675078320, rewardtime=1786675084516 → runda **6.20 s**, speed=23

### Odpowiedzi serwera na diga (C2S get.dig.treasure.reward → S2C)
- **h8**: `success=1, _id=267` (+7 ms po pushu) — dig ZAAKCEPTOWANY
- **h9**: `success=1? _id=379` (w zbiorczym pakiecie 69914 razem z push KiriGami2)
- **h10**: `errorCode='5560006', _id=448` — odpowiedź 97 ms PO pushu i po `push.treasure.remove` → error = "już przetworzono / za późno / duplikat" (dig ZALICZONY — push był przed errorem, pozycja 5.)
- 6-bajtowe pakiety `000000000000` po digach (h7: po każdym z 5 digów) = framing/keepalive, NIE odpowiedź o wyniku

### Pushy = kolejność dotarcia digów innych graczy (serwer pushuje w kolejności przyjęcia digów)
- h8: KiriGami2(us) push .232, LiZeeeeee .281, Whykillme .299, 陰濕嚕 .331 → dig innych dotarł ~50-100 ms po naszym → 1. miejsce
- h10: Abby .803, WinTahLily .851, Her Benevolence .853, LiZeeeeee .857, **KiriGami2 .886**, SHISH1 .888, kindenough .890, SeanSG .896, -loveuuu- .915, 陰濕嚕 .919 → 4 graczy wykopało 83+ ms przed nami → 5. miejsce

---

## 4. Timelines sesji (szczegóły)

### NIELINIOWOŚĆ REWARDTIME (skaczące odliczanie 2h → 30min → 10min → sekundy)
- Mechanika: serwer ogłasza rundę z `rewardtime` w przyszłości; gdy zbierze się więcej graczy, rewardtime jest SKRACANY (re-announcement bez liniowej ekstrapolacji).
- **h9**: pkt 4690 @ 04:13:20 → rewardtime **+55 min** (1786676875.235) … pkt 69875 @ 04:20:18 → **+0 s** (1786674018.164, runda!) — runda wystrzeliła **34 min wcześniej** niż ogłoszono; po rundzie (pkt 70073) nowe ogłoszenie +49 min.
- **h7**: pkt 17398/19446 @ 20:13:39/20:14:36 → **+53 min** … runda 20:16:01 — **~50 min wcześniej, 85 s po ostatnim ogłoszeniu, BEZ żadnego nowego S2C** (klient znał tick0 mimo to — patrz sekcja h7; możliwe że runda triggerowana dotarciem armii do punktu: marsze przybyły .611-.622, dig .716).
- **h8/h10**: finałowe ogłoszenie przyszło w tick0 (+0 s) — brak wcześniejszych.
- **Wniosek dla modelu**: tick0 = rewardtime z FINALNEGO ogłoszenia rundy w trakcie (potwierdzone h8/h9 r1/h10 — wartość = realny otwór). Wcześniejsze ogłoszenia = PROJEKCJA (nieliniowo skracana: h1, h9, h7 — do ~3000 s przed). Klient diguje po PRZYBYCIU ARMII (beacon), nie po ogłoszeniu: beacon wcześniej → dig +16…+94 ms po beacona (h7/h8/h10); beacon przed tick0 (h1/h2/h3/h5) → dig tuż po ogłoszeniu lub czeka do tick0.
- **Wniosek dla bota**: nie ekstrapolować liniowo odliczania OCR; każdy S2C world.get.detail.new to nowy rewardtime — gdy `rewardtime − now` maleje, finał może być w 85 s (h7) albo 7 min (h9); spam włączać w finałowej fazie. Realny sygnał tick0 w czasie rzeczywistym = beacon (burst push.world.march.new).

### h7 (1. miejsce, 1/5) — KLUCZOWY dowód: dig bez S2C
- Ostatni S2C z rewardtime: pkt 19446 @ 20:14:36.576 lokalnie (rewardtime=1786644875246 = 20:14:35.246 — poprzednia runda). Pełny skan pcapy: **zero** pakietów z rewardtime w oknie 85 s przed rundą (10 znalezionych, wszystkie przed).
- 12 C2S polli world.get.detail.new (ostatni pkt 19444 @ 20:14:36.397)
- Kliknięta runda: 5 digów C2S @ .716/.744/.799/.822/.891 (20:16:01.716 lokalnie, pkt 24258/24261/24263/24265/24267, 91B bez aac)
- **Brak S2C world.get.detail.new z rewardtime przed digiem** → klient wykopał z własnego timera rundy
- pushy: KiriGami2 @ .909 (pierwszy!), Caylynlin .917, Abby 62.035, Whykillme .081, Purple Baby .275 → 1/5 ✓
- Przed digami tylko: army move S2C (24239–24255, marsze do punktu 359350, startTime≈1786644961611) i push.mail 24256 @ .684
- każdy dig potwierdzany 6-bajtowym S2C ~8 ms później (pkt 24260/62/64/66/68)
- nagroda: push.receive.reward @ .906 (itemId 210931, count 865, rewardAdd 30, uuid 1401455744452325255)

### h8 (1. miejsce, cost 0.201) — wzorcowa
- rewardtime = 1786671587914 (03:39:47.914 lokalnie) = tick0 (finałowe ogłoszenie w tick0)
- **beacon (burst push.world.march.new, 10 marszów) @ 1786671588.031 (+117 ms po tick0)** — nasz marsz @ +127 ms
- **dig C2S @ +16 ms po beacona (+133 ms po tick0)** — 9 ms po naszym marszu; S2C z rewardtime jeszcze NIE przyszedł
- **S2C world.get.detail.new z rewardtime @ +399 ms (1588.313, pkt 22593) — PO digu klienta** (+266 ms)
- push KiriGami2 22582 @ +318 ms po tick0 (1588.232) → 1/8 (dig→push = 186 ms)
- OCR rankingu: `KiriGami2 Cost 02201 s` = **0.201** (najmniejszy czas)
- polling world.get.detail.new: tylko 4× PO evencie (22577/22604/22605/22611), ZERO przed
- nagroda: pkt 22580 push.receive.reward (items, jak wyżej)
- rewarduid (pkt 22593): "1461030734000751;1777937038000751;1661183580000751"

### h9 (ostatnie, cost 0.386)
- DWA eventy: 4690 @ 04:13:20.257 (rewardtime=1786676875235 = projekcja ~+55 min, state=0, speed=1 — NIE było diga) oraz **69875 @ 04:20:18.164** (rewardtime=1786674018164, state=1, speed=16) — to ten z logów klikania
- beacon @ +99 ms; S2C 69875 @ +143 ms po rewardtime; drugi S2C 69879 @ +224 ms
- dig C2S 69890 @ +301 ms po rewardtime (157 ms po S2C — JEDYNA sesja z digiem po S2C, najwolniejsza reakcja 201 ms po beacona)
- pushy: mutz0001 +273, 陰濕嚕 +336, BestNightmare +374, 神慕奈美 +404, tammy00910 +413, Abby +465, Kemen +596; KiriGami2 w zbiorczym 69914 @ +488 (rewarduid kończy się na ...;1461030734000751 = ostatni; brak indywidualnego pusha z naszym uid — mega: rank=None)
- 11 polli world.get.detail.new przed eventem (ostatni −18 ms)
- **Runda 2 h9 (r2, 04:21:32.755): 2 digi @ 4092.755/.874, beacon 1.8 s wcześniej, 7 pushów przed naszym (+938 → rank 8), dig→push 184 ms, resp ok + err5560006 na 2. digu**

### h10 (5. miejsce, cost 0.274)
- event 65421 @ 04:38:04.516 (rewardtime=1786675084516, startTime=1786675078320, speed=23, runda 6.2 s)
- beacon @ +93 ms; **S2C 65421 @ +278.9 ms po rewardtime — najpóźniej ze wszystkich sesji**
- **dig1 C2S @ +187.2 ms (1786675084.703) — 94 ms po beacona, 92 ms PRZED S2C** (rankingowy; korekta: wcześniejsza analiza brała dig2)
- **dig2 C2S 65425 @ +288.6 ms (9.7 ms po S2C)** → err `5560006` @ .983 (97 ms po pushu)
- push KiriGami2 65476 @ +370.3 ms (dig→push = 183 ms) → 5/10
- push order: Abby +287, WinTahLily +335, Her Benevolence +337, LiZeeeeee +341, **KiriGami2 +370**, SHISH1 +372, kindenough +374, SeanSG +380, -loveuuu- +399, 陰濕嚕 +404
- 6 polli przed eventem (ostatni −179 ms)
- bonus: pkt 65473 = push.receive.reward z total=49871, type=5, value=1000 (jak h3/h4)

---

## 5. Logi bota (LOGS.txt, 13.9 MB — kopia czytelna w F:\TEMP\opencode\LOGS_copy.txt)

### Format logów
- `watch_timer: sampling ROI (1920px, y=379-403)` — sampling timera co ~10 s (faza idle), co ~1-2 s (faza fast <15 s)
- `Timer OCR (robust): Tesseract HH:MM:SS '00:00:04' → 4 seconds` — odczyt timera
- `watch_timer: phase → fast (timer=15s)`, `low reading 1/1 (timer=5s)`, `phase → spam (timer=5s, confirmed=1/1)`
- `spam_start: 100c/s x 7.0s = 700 clicks (chunk=100) deadline=...`
- `spam_chunk: chunk=100 delivered=100 total=200 remaining=500`
- `spam: 390/700 clicks at (960, 520) (stopped=False)`
- `IDLE: waiting for helicopter alert (interval=0.5s)`
- `find_helicopter_alert: EasyOCR returned N text blocks`
- `Helicopter alert detected: State 751 X:350 Y:381 (click at 171,691 in ROI)`

### OCR timer — LAG
OCR watch_timer czyta timer z opóźnieniem ~2.5–3.5 s względem realnego stanu:
- h8: odczyt "timer=4s" @ 03:39:47.376, a event był @ 03:39:47.914 (0.54 s później!) → lag ~3.4 s
- h9: odczyt "timer=4s" @ 04:20:16.653, event @ 04:20:18.164 (1.5 s później)
- h10: odczyt "timer=5s" @ 04:38:02.941, event @ 04:38:04.516 (1.57 s później)
Wniosek: spam startuje bliżej tick=0 niż sugeruje odczytany timer.

### Sesje klikania w logach (mapowanie na pcapy)
| Czas (lokalny) | Pozycja | CPS real | Target | Kliknięcia | Sesja |
|---|---|---|---|---|---|
| 12.08 22:09–22:11 | (960,520) | ~30? | 30c/s | 300–311/600 | wczesne |
| 12.08 23:08:18–42 | (960,520) | 19.2/19.2/19.0 | 30c/s | 228–231/360 | **h3** |
| 13.08 02:51 | okno 'LastZ' (1936x1056) | — | — | — | — |
| 13.08 02:58:49 | (960,520) | 18.8 | 30c/s | 225/360 | **h4** |
| 13.08 04:15 | okno 'LastZ' (1920x1047) | — | — | — | — |
| 13.08 04:21/04:42 | (953,523) | 14.4/14.2 | 20c/s | 128–130/179 | pośrednie |
| 13.08 05:13–05:17 | (960,520) | 14.5–14.8 | 20c/s | 87–133/119–179 | pośrednie |
| 13.08 20:16:01.438 | (960,520) | 18.9 | 30c/s | 227/360 | **h7** |
| 14.08 03:39:47.412 | (960,520) | ~55 (390/7s) | 100c/s | 390/700 | **h8** |
| 14.08 04:20:16.664 | (960,520) | ~56 (395/7s) | 100c/s | 395/700 | **h9** |
| 14.08 04:38:02.953 | (960,520) | ~55 (387/7s) | 100c/s | 387/700 | **h10** |

### Okna gry
- 'LastZ' (1936x1056) @ 02:51 (13.08)
- 'LastZ' (1920x1047) @ 04:15 (13.08)
- Klik (960,520) ≈ środek okna 1920x1047 (środek = 960, 523.5); (953,523) w sesjach pośrednich
- ROI timera: y=379–403

---

## 6. Ranking OCR (odczyty z ekranu)

### h8 (po wygranej, 03:40:12)
```
Delqiis / Explore Treasure / Can obtain / IMAVEJ Alfa8OPk / Well donez you found rewardl
IMAVEJ KiriGamiz Cost 02201 s Lv:23   ← 1. miejsce, 0.201
IMAVEJ Lizeeeeee Cost J6249 8 Lv:25   ← 0.6249
Cost MMAVEI Whylillme 06268 8 Lv:23   ← 0.6268
MMAVE Cost Jo299 06299 8 Lv:25        ← 0.6299
Cost IMAVEI sHISHA 06366 Lv:24        ← 0.6366
```
Kolejność OCR = kolejność pushów (KiriGami2, LiZeeeeee, Whykillme, ...) ✓

### h7 (20:16:26)
`KiriGami2 Cost 08246 s Lv:23` — uwaga: OCR pokazuje też inne rundy (DajKiller, xaxx 0.6234, Caylyuli 0.6239...)

---

## 7. Pliki i narzędzia

### Pcapy (wszystkie w F:\PROJEKTY\joaxx, czas pcap = UTC, logi = UTC+2)
- helikopter3.pcapng (3749 pkts, event 23:08:22.446 lokalnie) — 3/10, aac
- helikopter4.pcapng — 3/10, aac
- helikopter7.pcapng — 1/5
- helikopter8.pcapng (26657 pkts, 1786671255..1786671636) — 1/8, 0.201
- helikopter9.pcapng (70847 pkts, 1786673584..1786674125) — ostatnie, 0.386
- helikopter10.pcapng (68845 pkts, 1786674822..1786675112) — 5/10, 0.274

### Skrypty (F:\PROJEKTY\joaxx\scripts)
- `scripts/_pcap_tlv.py` — dekoder TLV (zwraca tuple: (dict, order))
- `scripts/_pcap_compare.py` — find_cmd/find_all (quirk z kluczem `c`)
- `scripts/_pcap_mega.py` — skaner strumieniowy WSZYSTKICH pcapów (dekompresja 0xA0 zlib offsety 3/4/5, RTT przez korelację ACK, digs/pushes/resps/rewardtime/polls) → `data/output/mega_out/*.pcapng.json`
- `scripts/_pcap_timeline.py` — per-rundowe timeline'y (beacon/march, S2C, dig, push, rank, dig→push) → `data/output/mega_out/tl3.log`
- `scripts/all12_analysis.py` — **ujednolicony skaner 12 pcapów (v3)**: per-file summary, timeline wszystkich klikniętych rund, RTT c→s (ACK na digu), RTT s→c, detekcja beacona (najgęstszy burst marszów), push spacing → `data/json/all12.json`
- `scripts/all12_stats.py` — korelacje rank vs czynniki (Pearson), histogramy, statystyki zbiorcze z `data/json/all12.json` (sekcja 17)
- `scripts/rtt_stats.py` — dystrybucje RTT s→c + weryfikacja h9/h10 → `data/output/rtt_stats.log`
- `scripts/polls_rtt.py` — RTT poll→S2C (dwumodalne 40/180 ms)
- `scripts/intervals.py`, `scripts/starts.py` — analiza rewardtime/startTime (odrzucone jako sygnał tick0)
- `scripts/_pcap_correlate.py`, `scripts/_pcap_round.py`, `scripts/_pcap_points.py`, `scripts/_pcap_decode.py` — analizy rund/points
- `scripts/measure_real_cps.py` — pomiar realnych CPS (wymaga focusu gry)
- Analizy ad-hoc w `F:\TEMP\opencode\h9_*.py`, `h10_*.py`, `polls.py`

### Logi
- `LOGS.txt` (13.9 MB) — zablokowany przez proces dla unlink/git, odczyt OK
- `F:\TEMP\opencode\LOGS_copy.txt` — kopia do analizy (sesje 131766–134978)

### Wyniki analiz
- `_cmp8.txt`, `_cmp.txt`, `_corr.txt`, `_c2s_raw.txt`, `_deltas.txt`

---

## 8. Rekomendacje praktyczne (aktualne)

**Status: nadpisane przez pełną analizę 10 pcapów (sekcja 10–12).** Wcześniejszy wniosek „bot nie ma wpływu na moment diga" był błędny — dotyczył wyłącznie KLIENTA gry. Bot może (i powinien) wysłać `get.dig.treasure.reward` samodzielnie, SZYBCIEJ niż klient gry:

1. **Wykrywaj „beacon" (burst `push.world.march.new`) i diguj natychmiast po nim** — klient gry reaguje w 16–201 ms (śr ~90 ms), zwycięzcy h7/h8 w 16–57 ms. Bot może wysłać diga w 0–10 ms po beacona → szansa na 1. miejsce.
2. **Spamuj digami w oknie otwarcia** — klient gry wysyła do 5 digów na rundę (h1/h2/h7); pierwszy zaliczony decyduje, kolejne → errorCode `5560006`. Bot: 3–5 digów co 30–50 ms od beacona.
3. **Digi przed tick0 są przyjmowane do kolejki** (dowód h1/h2: digi przyjęte z rankingiem 2/8 mimo wysłania przed momentem otwarcia wg S2C) — wczesny dig nie szkodzi.
4. **Nie czekaj na S2C z `rewardtime`** — przychodzi +72…+399 ms PO tick0 (za późno na wygraną). Wyjątek: finałowe ogłoszenie h8/h9/h10 przychodziło ~0 ms (i tam dig klienta był opóźniony +133…+301 ms — bo czekał na S2C).
5. **Klik/mysz w grze NIE sterują digiem** — diga wysyła klient gry na timerze. Jeśli bot ma działać bez ingerencji w klienta: przechwytuj ruch sieciowy (sniffing) i wstrzykuj C2S dig (model w sekcji 12).
6. **Utrzymuj niskie RTT** — cykl serwera ~185 ms + RTT decydują o pushu; RTT p50 ≈ 40 ms, p90 ≈ 80–146 ms, max ~230 ms (sekcja 11).

---

## 9. Pełna analiza 10 pcapów — per-rundowe timeline'y (2026-08-14)

Skaner strumieniowy `_pcap_mega.py` + `_pcap_timeline.py` (wyniki: `_tmp_pcap\mega_out\*.pcapng.json`, `tl3.log`). Nasz gracz: **KiriGami2**, uid `1461030734000751` (stały we wszystkich sesjach). Serwer: `15.197.67.229:8851`. Czas w tabelach = względny (ms), tick0 = moment otwarcia okna dig.

### Tabela zbiorcza (per runda klikniętą przez nas)

| plik | #dig | dig_delay | s2c_delay | march_delay | react_s2c | react_march | rank | push1 | ourpush | dig→push | resp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| helikopter.pcapng | 5 | -573 | -615 | -670 | 41 | 97 | 2 | -404 | -387 | 186 | ok |
| helikopter2.pcapng | 5 | -591 | -630 | -674 | 39 | 83 | 8 | -512 | -405 | 186 | ok |
| helikopter3.pcapng | 5 | 95 | 72 | -972 | 23 | 1068 | 3 | 232 | 282 | 187 | ok |
| helikopter4.pcapng | 3 | 3 | -10 | -49 | 13 | 52 | 3 | 140 | 189 | 186 | ok |
| helikopter5.pcapng | 4 | -199 | -143 | -1249 | -56 | 1050 | 3 | -115 | -10 | 189 | ok |
| helikopter6.pcapng | 3 | -173 | -180 | -250 | 7 | 77 | 3 | -41 | 14 | 187 | ok |
| helikopter7.pcapng | 5 | – | – | – | – | 57 | 1 | – | – | 193 | ok |
| helikopter8.pcapng | 1 | 133 | 399 | 117 | -266 | 16 | 1 | 318 | 318 | 186 | ok |
| helikopter9.pcapng (r1) | 1 | 301 | 143 | 99 | 157 | 201 | None | 273 | – | – | – |
| helikopter9.pcapng (r2) | 2 | – | – | – | – | 1807 | 8 | – | – | 184 | ok |
| helikopter10.pcapng | 2 | 187 | 279 | 93 | -92 | 94 | 5 | 287 | 370 | 183 | err5560006 |

Kolumny: `dig_delay` = pierwszy dig względem tick0; `s2c_delay` = przyjście S2C z rewardtime względem tick0; `march_delay` = przyjście beacona (march burst) względem tick0; `react_s2c` = dig − S2C; `react_march` = dig − beacon; `push1` = pierwszy push rankingu względem tick0; `ourpush` = nasz push względem tick0; `dig→push` = czas serwera od naszego diga do naszego pusha.

### Co determinuje pozycję — twarde fakty

1. **Kolejność dotarcia digów = kolejność rankingu.** Serwer pushuje `push.dig.treasure.reward` w kolejności przyjęcia digów. 1. push = 1. miejsce (potwierdzone 1:1: h8, h9, h10, h7, h3, h4, h5, h6).
2. **Diga wysyła klient gry** na własnym timerze rundy (h7: bez żadnego S2C z rewardtime → 1/5), a reakcja klienta na beacon (march burst) = **16–201 ms** (śr ~90 ms). **Zwycięzcy h7/h8 digowali 16–57 ms po beacona**; przegrani 77–201 ms.
3. **Cykl serwera dig→push jest niemal stały: 183–193 ms** we wszystkich 10 sesjach (h3 187, h4 186, h7 193, h8 186, h9 184, h10 183). To czas: odbiór diga → sortowanie → wysłanie pusha rankingowego. Ten sam rytm ~180 ms widać w RTT poll→S2C (sekcja 11) — serwer pracuje w cyklach ~180 ms.
4. **S2C z `rewardtime` przychodzi −630…+399 ms względem tick0** — dwa typy ogłoszeń: (a) projekcja przyszłości (h1/h2/h5/h6: −630…−143 ms PRZED tick0, wartość = przyszły otwór), (b) finał rundy w trakcie (h3/h8/h9/h10: +72…+399 ms PO tick0 — w h8/h10 PO digu klienta, który już digował po beacona). S2C NIE wyzwala diga i nie nadaje się na sygnał tick0.
5. **Digi wysłane przed tick0 są przyjmowane do kolejki** — h1/h2: digi na −573/−591 ms przed tick0 (wg S2C) i mimo to ranking 2/8 (bez errorCode; serwer sortuje wg dotarcia). Wniosek: serwer nie odrzuca wczesnych digów — liczy się kolejność dotarcia.
6. **`errorCode=5560006` = dig już zaliczony / duplikat / za późno** (h10: err ~97 ms po naszym pushu = 2. dig tej samej rundy; h9 r2: err na 2. digu). Nie jest to kara — to potwierdzenie, że pierwszy dig został przyjęty.
7. **Brak korelacji aac z pozycją** (potwierdzenie hipotezy A jako nieistotnej): z aac — h3 (0.109–0.143), h4 (0.014), h6 (0.423–0.441) → 3. miejsce, ostatnia runda h3 (aac 0.132) → 1/8; bez aac (91B) — h2 → 8., h9 → 8./None, h10 → 5. miejsce. aac to wyłącznie sygnatura klikania, nie mechanizm karania.

### Korelacja rank vs react_march (klucz dla modelu)

| react_march | rank | sesja |
|---|---|---|
| 16 ms | 1 | h8 |
| 57 ms | 1 | h7 |
| 52 ms | 3 | h4 |
| 77 ms | 3 | h6 |
| 83 ms | 8 | h2 (konkurencja szybsza) |
| 94 ms | 5 | h10 |
| 97 ms | 2 | h1 (konkurencja wolniejsza) |
| 201 ms | 8/None | h9 r1 |
| 1068 ms | 3 | h3 (beacon przyszedł ~1 s przed tick0 — klient czekał) |
| 1050 ms | 3 | h5 (jw.) |

Wniosek: **w sesjach, gdzie beacon ≈ tick0 (h1, h2, h4, h6, h7, h8, h10), ranking rośnie gdy dig po beacona jest wcześniejszy.** Zwycięstwo = dig 0–60 ms po beacona.

### Specyfika sesji h1/h2/h5/h6 (wcześniej nieanalizowanych)

- **h1/h2**: 5 digów od klienta (spam). h1: 91B×3 bez aac, potem 180B z aac (uniformity 0.34/0.36) — klient wysyła aac dopiero po klikach; **h2: 5×91B bez aac w ogóle** (korekta — wzorzec aac nie jest stały). Digi WYPRZEDZAJĄ tick0 wg S2C (−573/−591 ms), bo w tych sesjach S2C z rewardtime niósł PROJEKCJĘ przyszłości (przyszedł −615/−630 ms przed wartością); w rzeczywistości klient digował +83/+97 ms po beacona, +39/+41 ms po S2C (normalnie).
- **h5**: beacon przyszedł −1249 ms przed tick0 (bardzo wcześnie), klient czekał i digował +1050 ms po beacona → rank 3, dig→push 189 ms. Analogicznie h3 (−972 ms → +1068 ms → rank 3). 4 digi 91B (bez aac).
- **h6**: normalny (beacon −250, dig +77 po beacona) → rank 3, dig→push 187 ms. **3 digi Z aac (uniformity 0.423–0.441)** — kolejny dowód, że aac nie jest karany (h6 z aac = 3., h9/h10 bez aac = 8./5.).
- **h7**: brak S2C z rewardtime w ogóle (pełny skan), dig +57 po beacona → **1. miejsce**, dig→push 193 ms.

---

## 10. Statystyki opóźnień sieciowych (pomiar z 10 pcapów)

### RTT s→c (serwer ACK na dane klienta — czyste ACK, korelacja wg portu)

| plik | n | p10 | p50 | p90 | max | mean |
|---|---|---|---|---|---|---|
| helikopter | 222 | 0.0 | 62.7 | 146.2 | 238.7 | 70.5 |
| helikopter2 | 218 | 0.0 | 40.6 | 90.6 | 232.1 | 41.9 |
| helikopter3 | 287 | 0.1 | 40.3 | 80.2 | 236.3 | 41.1 |
| helikopter4 | 164 | 0.1 | 44.5 | 185.9 | 240.5 | 74.3 |
| helikopter5 | 210 | 0.0 | 40.2 | 88.4 | 225.0 | 38.1 |
| helikopter6 | 407 | 0.1 | 40.2 | 88.7 | 235.0 | 40.2 |
| helikopter7 | 561 | 0.1 | 40.3 | 111.9 | 232.2 | 47.0 |
| helikopter8 | 218 | 0.1 | 75.4 | 184.8 | 236.1 | 80.1 |
| helikopter9 | 427 | 0.0 | 40.0 | 85.5 | 235.1 | 34.7 |
| helikopter10 | 305 | 0.1 | 40.2 | 117.5 | 233.3 | 42.0 |

(wszystkie w ms; `p10≈0` to korelacja ACK wysłanych równocześnie z danymi — piggyback)

**Wnioski**: typowe RTT s→c = **40 ms (p50)**; rozkład ma długi ogon do **~235 ms (p90 80–146 ms)**. Wysokie p90 w h4 (186), h8 (185) koreluje z ich gorszym timingiem diga (S2C opóźnione).

### RTT c→s (korelacja ACK na digu) — pomiar v2 w sekcji 14

Wcześniejszy pomiar „0 próbek" dotyczył wyłącznie korelacji czystych ACK-ów (serwer ACKuje dane klienta przez piggyback). Pomiar v2 (2026-08-14) koreluje **pierwszy S2C z ACK >= seq+len segmentu z digiem** → realny RTT c→s = **p50 22 ms, p90 51 ms, max 54 ms (n=11)** — pełne dane w sekcji 14. Dla porównania zastępczy pomiar dwukierunkowy poll→S2C (RTT + czas odpowiedzi serwera, rozkład dwumodalny 40/180 ms):

| plik | polls | n | p10 | p50 | p90 | max |
|---|---|---|---|---|---|---|
| helikopter | 10 | 9 | 12.6 | 37.4 | 188.0 | 188.0 |
| helikopter2 | 17 | 14 | 11.1 | 46.3 | 178.7 | 184.2 |
| helikopter3 | 19 | 14 | 7.5 | 43.2 | 178.0 | 181.6 |
| helikopter4 | 61 | 57 | 10.5 | 40.8 | 95.8 | 180.4 |
| helikopter5 | 10 | 9 | 7.3 | 64.4 | 182.1 | 182.1 |
| helikopter6 | 17 | 17 | 12.2 | 48.6 | 152.6 | 183.1 |
| helikopter7 | 12 | 10 | 178.0 | 180.2 | 181.2 | 181.2 |
| helikopter8 | 5 | 5 | 156.9 | 180.2 | 181.9 | 181.9 |
| helikopter9 | 14 | 14 | 17.9 | 98.5 | 178.9 | 179.5 |
| helikopter10 | 20 | 9 | 21.8 | 177.1 | 179.7 | 179.7 |

**Rozkład DWUMODALNY**: ~40–65 ms (czysty RTT) oraz **~180 ms** — stała serwera (serwer odpowiada na poll w najbliższym cyklu ~180 ms). To ta sama stała co dig→push (183–193 ms). **Serwer działa w rytmie ~180 ms** — cykl: przyjęcie żądań → sortowanie → pushy.

### RTT handshake (SYN→SYN-ACK): poniżej progu zapisu w mega (hs=0.0) — pominąć, korelacja ACK wystarcza.

---

## 11. Model przewidywania idealnego momentu diga

### Zasada

Ranking = **kolejność dotarcia `get.dig.treasure.reward` do serwera**. Serwer przyjmuje digi (także wczesne, do kolejki) i w cyklu ~180 ms sortuje + pushuje w kolejności dotarcia. Idealny moment to **jak najwcześniej po otwarciu okna (tick0)** — w praktyce: **jak najwcześniej po beacona**, bo beacon (march burst) poprzedza dig klienta o 16–201 ms i jest najlepszym realnym sygnałem w czasie rzeczywistym.

### Sygnały i ich wartość predykcyjna (ranking)

| Sygnał | Kiedy dostępny | Przewaga |
|---|---|---|
| Beacon (`push.world.march.new` burst) | ~tick0 (h1/h2/h4/h6/h7/h8/h10) lub −250…−1249 ms (h3/h5/h6) | najwcześniejszy sygnał; dig 0–60 ms po beacona = 1. miejsce |
| S2C `world.get.detail.new` z rewardtime | +72…+399 ms PO tick0 | za późno — po nim dig klienta = 3–8. miejsce |
| `push.dig.treasure.reward` (ktoś wygrał) | ~+180 ms po tick0 | za późno — runda rozstrzygnięta |
| Timer/OCR w grze (0 s) | ~tick0 (lag OCR 1.5–3.4 s) | tylko dla synchronizacji klików myszą (nie digów) |

### Wzór

```
t_send_dig = t_beacon + δ,   δ ∈ [0, 30] ms   (najlepiej 0–10 ms)
```

Uzasadnienie δ z danych:
- Zwycięzcy: h7 δ=+57, h8 δ=+16 → δ ≤ 60 ms.
- Przegrani (beacon≈tick0): h4 +52 (3.), h6 +77 (3.), h10 +94 (5.), h1 +97 (2.), h2 +83 (8.) → δ ≥ 77 ms to 3–8. miejsce.
- h3/h5 (beacon −1 s): klient czekał ~1 s → 3. miejsce — dowód, że klient gry zna tick0 i czeka; bot wysyłający na beacon dostałby diga ~1 s przed tick0 → serwer i tak kolejkuje (dowód h1/h2) → nadal kandydat na 1. miejsce.

### Kompensacja RTT (opcjonalna precyzja)

**Pomiar v2 (sekcja 14):** RTT c→s mierzony ACK-iem na segmencie z digiem = **p50 22 ms, p90 51 ms, max 54 ms (n=11)** — droga c→s jest krótka i STABILNA (nie ma ogona ~230 ms jak RTT s→c; serwer ACKuje natychmiast). RTT s→c ma długi ogon, bo to czas S2C pushów wysyłanych w batchach co ~180 ms — nie jest to czyste opóźnienie sieci.

Kompensacja: wysłanie w `t_beacon − RTT_c2s + δ` (RTT_c2s ≈ 22–25 ms) sprawia, że dig dociera do serwera w `t_beacon + δ`. Ryzyko: RTT_c2s mierzone w spoczynku może być niższe niż w szczycie rundy (Nagle/batch). **Bezpieczniejsza strategia: wysyłaj jak najwcześniej (δ=0–10 ms) i polegaj na kolejce serwera** — dowód h1/h2: digi przed tick0 są przyjmowane. Spam 3–5 digów eliminuje ryzyko pojedynczego pakietu.

### Długość rundy (do prognozowania przyszłych tick0)

`rewardtime` z S2C to granica okna nagród (~3000 s — NIE tick0 rundy). `startTime` z S2C zmienia się nieregularnie (16–491 s między zmianami) — **nie da się niezawodnie ekstrapolować tick0 z S2C**. Niezawodny sygnał to beacon w czasie rzeczywistym.

---

## 12. Algorytm automatycznego klikania (bot)

### Architektura

```
[sniffer: pcap/loopback, parsuje TLV 0x80/0xA0] → [detektor rund] → [injector C2S dig] → [stan: czekaj na push]
```

Wymagania: dostęp do ruchu sieciowego maszyny (Npcap/loopback na porcie 8851, docelowo `15.197.67.229:8851`), możliwość wysłania własnego TCP (raw socket na tym samym połączeniu co klient gry lub osobne połączenie — patrz uwagi poniżej).

### Kroki implementacji

1. **Sniffing i dekodowanie**: nasłuchuj pakiety z `dport==8851` (C2S) i `sport==8851` (S2C); zbierz strumień TCP, dekompresuj payloady 0xA0 (zlib offsety 3/4/5; po dekompresji od `12`) i 0x80; wyodrębnij komendy po kluczu `c` (string TLV). Reuse: `_pcap_tlv.py` + `decompress_payload` z `_pcap_mega.py`.
2. **Detekcja beacona**: stan SEEK → po pakiecie S2C z `push.world.march.new` przejdź w ARMED; burst ≥ 2 marszów w 200 ms potwierdza rundę (fallback: pierwszy marsz po ciszy ≥ 5 s). Zapamiętaj `t_beacon`.
3. **Wysłanie diga**: w `t_beacon + δ` (δ=0–10 ms) wyślij C2S `get.dig.treasure.reward` 91B:
   - wrapper: `80 <len:2BE> 12` + body `{c:'get.dig.treasure.reward', a:<i16>, p:{c:'get.dig.treasure.reward', r:-1, p:{_id:<i64>, uuid:<i64>}}}`
   - `uuid` = nasze (h10: 1404003131012083561; h8: 1404003122346651631 — nowe na sesję); `_id` = kolejny licznik klienta.
   - **Bez aac** (91B) — aac nie daje przewagi, a dodaje ryzyko sygnatury.
4. **Spam fallback**: wyślij 3–5 digów co 30–50 ms (maks okno 200 ms). Serwer przyjmuje pierwszy, kolejne → err `5560006` (nieszkodliwe). Klient gry wysyła do 5 digów/rundę — nasz spam mieści się w normalnym wzorcu.
5. **Detekcja wyniku / stop**: po `push.receive.reward` (wygrana) lub `push.dig.treasure.reward` z naszym uid (miejsce w rankingu) albo `get.dig.treasure.reward` S2C z `errorCode` → przejdź w IDLE do następnego beacona. Nie diguj więcej w tej rundzie.
6. **Kalibracja online**: co rundę mierz `t_beacon→nasz push`, `t_beacon→dig klienta gry` i RTT c→s (ACK na własnym digu; p50 22 ms, p90 51 ms — sekcja 14); utrzymuj EMA `δ_opt`. Domyślnie δ=0–10 ms (bez kompensacji — droga c→s jest stabilna i krótka, a serwer i tak kolejkuje). Jeśli beacon regularnie wyprzedza tick0 o >300 ms (h3/h5/h6), rozważ δ = delay beacona, by dig dotarł na tick0±30.
7. **Ochrona przed detekcją**: wysyłaj diga PO beacona (nigdy przed nim bez dowodu na kolejkowanie), trzymaj się rozmiaru 91B i interwałów zbliżonych do klienta (30–100 ms); nie modyfikuj ruchu klienta gry.

### Uwagi ryzyka (nieweryfikowane na żywo)

- **Czy serwer akceptuje C2S z innego źródła niż połączenie klienta?** — niezweryfikowane; jeśli wymaga tej samej sesji TCP, bot musi wstrzykiwać do istniejącego połączenia klienta (proxy/split lub modyfikacja okna wysyłki klienta). Wtedy zamiast „wcześniejszego diga" bot robi to samo co klient, ale z zerową latencją aplikacyjną.
- **Wczesne digi przed tick0**: w pcapach przyjęte (h1/h2), ale to obserwacja z jednego wzorca serwera — test A/B na żywo: 2 rundy z digiem na beacon, 2 z δ=50 ms.
- **Anticheat**: ryzyko banu za wstrzykiwanie pakietów — niezbędny własny test na koncie testowym przed użyciem na głównym.

---

## 13. Blokery / stan pracy

- `git stash pop` niemożliwy — konflikt z lokalnymi zmianami w workingu: stash zawiera LOGS.txt + src/gui/step_editor.py, a w drzewie zmienione są LOGS.txt, macro_tab.py, step_editor.py, watch_timer_status.py. Pop wymaga uprzedniego rozstrzygnięcia zmian lokalnych (stash zachowany).
- `measure_real_cps.py --rescan` — wymaga focusu gry (user musi uruchomić).
- LSP errors w `_pcap_*.py` / debug_layout_*.py / src/gui/macro_tab.py — kosmetyczne, runtime OK.

---

## 14. Pomiary v2 — cykl serwera i RTT c→s (2026-08-14)

Skrypty: `_tmp_pcap\deep_queue_analysis.py` (rozstaw pushów, coalescing, dig→push, RTT s→c w oknie rundy) → `_tmp_pcap\mega_out\deep_queue.json` oraz `_tmp_pcap\dig_rtt.py` (RTT c→s przez korelację pierwszego S2C z `ACK >= seq+len` segmentu z digiem) → `_tmp_pcap\mega_out\dig_rtt.json`, `_tmp_pcap\dig_rtt_out.txt`. Serwer: `15.197.67.229:8851`.

### 14.1 Cykl serwera: dig → push (n=10 rund, każda sesja osobno)

| plik | runda | dig→push (ms) | resp_delay (ms) | rank | RTT c→s (ms) |
|---|---|---|---|---|---|
| helikopter | r1 | 186.0 | 220.4 | 2 | 11.2 |
| helikopter2 | r1 | 186.0 | 187.4 | 8 | 22.1 |
| helikopter3 | r1 | 186.8 | 195.2 | 3 | 10.6 |
| helikopter4 | r1 | 186.1 | 186.1 | 3 | 45.8 |
| helikopter5 | r1 | 188.9 | 188.9 | 3 | 53.8 |
| helikopter6 | r1 | 187.5 | 188.5 | 3 | 46.9 |
| helikopter7 | r1 | 193.2 | 209.3 | 1 | 8.9 |
| helikopter8 | r1 | 185.8 | 192.7 | 1 | 11.3 |
| helikopter9 | r1 | – (brak indywidualnego pusha) | – | None | 35.3 |
| helikopter9 | r2 | 183.6 | 183.6 | 8 | 6.5 |
| helikopter10 | r1 | 183.3 | 280.4 (err 5560006) | 5 | 51.3 |

**Statystyki dig→push: n=10, min=183.3, max=193.2, mean=186.7, p50≈186 ms.** Stała przetwarzania serwera — niemal identyczna we wszystkich sesjach, niezależnie od RTT, rankingu i pory dnia. Oznacza to: **serwer przyjmuje diga, sortuje go w bieżącym cyklu ~186 ms i pushuje wynik w kolejności dotarcia** — deterministyczne, bez kumulowania backlogu (r2 h9: 183.6 ms mimo 10 graczy).

### 14.2 RTT c→s (ACK na digu) — n=11

| plik | runda | RTT c→s (ms) |
|---|---|---|
| helikopter | r1 | 11.2 |
| helikopter2 | r1 | 22.1 |
| helikopter3 | r1 | 10.6 |
| helikopter4 | r1 | 45.8 |
| helikopter5 | r1 | 53.8 |
| helikopter6 | r1 | 46.9 |
| helikopter7 | r1 | 8.9 |
| helikopter8 | r1 | 11.3 |
| helikopter9 | r1 | 35.3 |
| helikopter9 | r2 | 6.5 |
| helikopter10 | r1 | 51.3 |

**Statystyki: n=11, min=6.5, p50=22.1, p90=51.3, max=53.8, mean=27.6 ms.**

Wniosek: droga c→s jest **krótka i stabilna** (brak ogona ~230 ms — ten ogon dotyczy tylko S2C, bo to czas pushów batchowanych przez serwer). Serwer ACKuje segment z digiem natychmiast (p50 22 ms), więc `T_arr_serwer = T_send + RTT_c2s` jest dobrze przewidywalne: δ 0–10 ms daje nadejście 6–65 ms po beacona (p90), praktycznie zawsze w pierwszej 100 ms okna.

### 14.3 Rozstaw pushów rankingu (push_spacing, n=88) — batching serwera

| zakres (ms) | liczba |
|---|---|
| 0–9 | 31 |
| 10–19 | 13 |
| 20–29 | 7 |
| 40–49 | 11 |
| 200–209 | 5 |

Rozkład: **p50=21.1 ms, p90=130.5 ms**. Dominuje gęsta seria 0–50 ms (62/88) — serwer wysyła pushy wielu graczy jednym ciągiem (coalescing TCP + batch aplikacyjny), potem „przerwa" i pojedyncze pushy w następnym cyklu (~180–200 ms). To potwierdza model cykliczny: pushy trafiają do strumienia S2C w rytmie ~186 ms, a w obrębie jednego cyklu kolejność = kolejność przyjęcia digów.

### 14.4 Wnioski pomiarowe (aktualizacja faktów z sekcji 9)

1. **Cykl serwera 183–193 ms (mean 186.7) to deterministyczna stała** — wspólna dla wszystkich 11 rund. Serwer nie kumuluje backlogu; dig przyjęty w trakcie cyklu jest sortowany w tym cyklu, dig po cięciu cyklu — w następnym.
2. **RTT c→s jest mały i stabilny** (p50 22, p90 51, max 54) — w przeciwieństwie do RTT s→c (p50 40, p90 80–146, max 235) nie ma długiego ogona; ogon s→c = batchy S2C, nie czysta sieć.
3. **Zwycięzcy mają najniższe RTT c→s i najwcześniejszy dig**: h7 (8.9 ms, dig +57 po beacona, 1/5), h8 (11.3 ms, dig +16 po beacona, 1/8). Najgorsze sesje miały dig ≥ 77 ms po beacona (h4/h6/h10/h1/h2) — RTT c→s nie jest tu korelatem rankingu (h10: 51 ms, ale 5. miejsce przez wolny dig +94), liczy się **moment wysłania**.
4. **Kompensacja RTT jest zbędna**: δ=0–10 ms po beacona + stabilne RTT c→s 22–51 ms → nadejście 6–65 ms po beacona — zawsze w oknie „0–60 ms = 1. miejsce". Kompensacja (wysyłanie `t_beacon − RTT_c2s`) tylko ryzykuje wysłanie przed beacona.

---

## 15. Model predykcyjny — podsumowanie (czego używa bot)

### Czynniki determinujące, kto kliknie/zdobędzie nagrodę pierwszy (ranking deterministyczny)

```
rank (kolejność pushów) = sort_by_asc( T_arr_i ),  T_arr_i = T_send_i + RTT_c2s_i
```

Czynniki w kolejności wpływu:
1. **Moment wysłania diga** (`T_send`) — najważniejszy; bot wysyła w δ=0–10 ms po beacona (klient gry: 16–201 ms).
2. **RTT c→s** — p50 22 ms, p90 51 ms; stabilny, dodaje stały offset do każdego zawodnika.
3. **Cykl serwera ~186 ms** — determinuje, w którym „paczce" pushów znajdzie się nasz wynik; przy jednakowych T_arr decyduje kolejność w batchu.
4. **Kolejkowanie wczesnych digów** — serwer przyjmuje digi przed tick0 (h1/h2) i sortuje wg dotarcia; wczesny dig nie szkodzi.
5. **Reakcja konkurencji** — klient gry reaguje na beacon w 16–201 ms (śr ~90); zwycięzcy 16–57 ms. Bot przy δ=0–10 ms jest szybszy niż typowy zwycięzca h7/h8.

### Wzór przewidywania idealnego momentu

```
t_send_dig = t_beacon + δ,            δ ∈ [0, 10] ms   (domyślnie δ=0)
P(1. miejsce) maks. przy δ ≤ 60 ms   (dowód: h7 δ=57, h8 δ=16 → 1. miejsce)
```

### Checklist implementacji bota (zwięzła wersja sekcji 12)

1. Sniff port 8851, dekoduj TLV 0x80/0xA0 (zlib offsety 3/4/5) — reuse `_pcap_tlv.py`/`_pcap_mega.py`.
2. Wykryj beacon: burst `push.world.march.new` ≥ 2 marszów w 200 ms → ARMED, zapisz `t_beacon`.
3. Wyślij C2S `get.dig.treasure.reward` 91B w `t_beacon + δ` (δ=0–10 ms); bez aac.
4. Spam fallback: 3–5 digów co 30–50 ms (pierwszy decyduje, reszta → err 5560006).
5. Stop po `push.receive.reward` / naszym uid w `push.dig.treasure.reward` / errorCode.
6. Kalibracja EMA `δ_opt` + RTT c→s co rundę (sekcja 14.2); domyślnie bez kompensacji.
7. Anticheat: tylko własne połączenie/wstrzyknięcie na połączeniu klienta; test na koncie testowym.

---

## 16. h11/h12 — ręczne kliknięcia: weryfikacja nieliniowości timera, aktywacji skrzynek i diga przed 0 (2026-08-14)

Skrypty: `_tmp_pcap\h11_probe.py` / `h11_analysis.py` / `h11_detail.py` / `h12_*` (wyniki: `_tmp_pcap\h11_*_out.txt`, `h12_*_out.txt`, `mega_out\h11.json`, `h12.json`). Oba pliki to **ręczne kliknięcia** (h11: 3. miejsce, Cost 0.286; h12: 2. miejsce, Cost 0.234).

### 16.1 Dwa serwery = „deszyfrowanie"

| Serwer | Port | Ruch | Format | Zawartość |
|---|---|---|---|---|
| `15.197.67.229` | 8851 | ~0.5–1% | **plaintext TLV** (`80`/`A0`+zlib) | CAŁA mechanika: dig, marsze, pushy, nagrody, rewardtime |
| `57.128.218.35` | 21117 | ~98–99% | **obfuskowany** (pierwszy bajt 0x59/0x5d/0xf9, brak markerów TLS/0x16) | nie dekodowalny surowo |

h11: 52024 pkt TCP na 21117; h12: 78585 — w obu **0 pakietów zdekodowanych** na 21117. „Deszyfrowanie" = dekodowanie TLV na 8851 (reszta ruchu to obfuskacja, prawdopodobnie inna warstwa — nie potrzebna do mechaniki diga).

### 16.2 Oś czasu rundy (klikniętej) — h11 vs h12

| Zdarzenie | h11 | h12 |
|---|---|---|
| startTime (S2C) | 5288.028 (1.05 s przed rewardtime) | 6219.933 (0.98 s przed digiem) |
| Beacon (burst marszów, 18–20 graczy) | 5288.441 | 6220.859 |
| **Nasz marsz** | 5288.455 | 6220.873 |
| **Nasz dig C2S** | **5288.545** (104 ms po 1. marszu; 90 ms po NASZYM marszu) | **6220.910** (51 ms po 1. marszu; 37 ms po NASZYM marszu) |
| Nagroda (push.receive.reward) | 5288.726 | 6221.093 |
| Pushy S2C (8 graczy) | 5288.729…5288.996 | 6221.038…6221.224 |
| Nasz push | **#1** 5288.729 (dig→push **183.5 ms**) | **#2** 6221.094 (dig→push **184.6 ms**) |
| **rewardtime (tick0)** | 5289.073 (dig −527.6 ms) | 6221.498 (dig −588.3 ms) |
| Odpowiedź na diga | success=1, brak 5560006 | brak w pcapie (nie dekodowany) |

### 16.3 Potwierdzenie formuły Cost (HIT w obu sesjach)

```
Cost (UI) = (nasz push − pierwszy marsz beacona) = reakcja + cykl serwera (~185 ms)
```

| Sesja | 1. marsz | nasz dig | nasz push | Cost = push−1.marsz | Cost z UI | zgoda |
|---|---|---|---|---|---|---|
| h11 | 5288.441 | 5288.545 | 5288.729 | **288 ms** | 0.286 | ✓ |
| h12 | 6220.859 | 6220.910 | 6221.094 | **235 ms** | 0.234 | ✓ |

(kontrolnie: dig→push = 183.5/184.6 ms — identyczna stała serwera jak w sekcjach 9/14. „Cost" = czas od beacona do naszego pusha; pole `point` w pushu to **współrzędna** `startPos` (identyczna dla wszystkich, np. 0x0005f0e2 = 389346), NIE cost ani punkty.)

### 16.4 Ranking = kolejność pushów (h12 potwierdza 1:1)

- **h12: nasz push #2 → 2. miejsce ✓** (pełna zgodność kolejności pushów z pozycją w UI).
- **h11: nasz push #1, ale user zgłosił 3. miejsce — KONTRADYKCJA.** W h11 nie ma żadnego klient-komputowalnego wskaźnika dającego 3. miejsce (koszt wg pushów: my 288, reszta 312–555; wg własnych marszów: my 274, reszta 303–545 — zawsze #1). Wyjaśnienie wymaga danych z serwera (21117) lub powtórki testu. Możliwe przyczyny: (a) UI pokazało wynik INNEJ rundy (w h11 w 213 s było ~86 marszów = kilka rund, tylko 1 dig — nasz; ekran rankingu mógł pokazać rundę z innego momentu), (b) serwer sortuje po czasie przyjęcia diga (niewidocznym dla nas), a kolejność pushów bywa batchem. **Rekomendacja: powtórzyć ręczny test 3–5× i sprawdzić zgodność „push order = pozycja" za każdym razem.**

### 16.5 Nieliniowość timera — POTWIERDZONA na poziomie protokołu

h12: **6 ogłoszeń `world.get.detail.new` (poll klienta co ~230 ms): 5 × ta sama wartość PROJEKCJI rewardtime = 1786689454648 (+54 min), a 6. (w momencie rozstrzygnięcia rundy) SKACZE do 1786686221498 (+0.43 s)** — wartość `rewardtime` przeskakuje skokowo, nie liniowo. To samo co udokumentowane h9 (55 min → 0 s w 7 min; sekcja 4). Klient odświeża timer z każdej odpowiedzi → timer „skacze" przy dołączaniu graczy/zbliżaniu się rundy.

### 16.6 Aktywacja skrzynek NIE = timer 0 (OBCALA hipotezę „klikalne tylko przy 0")

- h11: dig wysłany **−527.6 ms** przed rewardtime → przyjęty (success=1, brak 5560006).
- h12: dig wysłany **−588.3 ms** przed rewardtime → przyjęty.
- Oba digi poszły **tuż po przybyciu armii** (beacon): +90 ms (h11) / +37 ms (h12) po własnym marszu.
- **Wniosek: serwer przyjmuje diga gdy armia DOTRZE (beacon), NIE gdy timer osiągnie 0.** Obserwacja „skrzynki klikalne dopiero przy timer=0" to ograniczenie po stronie KLIENTA (UI ukrywa/blokuje przycisk do 0), nie reguła serwera.

### 16.7 „Dig krótko przed 0" — DZIAŁA (potwierdzone)

Wysłanie `get.dig.treasure.reward` przed osiągnięciem 0 przez timer jest akceptowane (h1/h2 −573/−591 ms; h11 −528 ms; h12 −588 ms). **Optyka: nie warto czekać na 0 — najlepszy moment to δ=0–10 ms po beacona** (sekcja 15): to ~500 ms wcześniej niż rewardtime i wyprzedza reakcję klienta gry (16–201 ms po beacona). Skrzynki/serwer przyjmują diga od momentu przybycia armii.

### 16.8 Rewards (h12) — potwierdzenie nagrody

`push.receive.reward` (h12): itemId **230112** (rewardAdd=5, count=100), itemId **230111** (rewardAdd=1500, count=0x702b=28715), num=1 — ten sam wzorzec co h8. Reward poprzedza nasz push o ~1–3 ms (h11: 5288.726 vs 5288.729; h12: 6221.093 vs 6221.094) — serwer najpierw rozdaje nagrodę, potem pushuje ranking.

### 16.9 Konsekwencje dla bota

1. Diguj **na beacon (0–10 ms)** — nie czekaj na timer 0; serwer i tak przyjmuje (16.6/16.7).
2. Kolejność pushów ≈ ranking — walcz o jak najwcześniejszy push (δ=0–10 ms, RTT c→s 22–51 ms).
3. Poluj na **pierwszy marsz beacona** (nie na nasz) — liczy się od niego Cost (16.3).
4. Wartość `rewardtime` traktuj jako **projekcję skokową**, nie liniową — nie ekstrapoluj OCR (16.5).
5. h11 pokazało jedną rundę z niezgodnością push-order vs pozycja — zbadać na powtórce (16.4).

### 16.10 Weryfikacja stanowiska użytkownika: „armie tylko skracają czas, liczy się klik skrzynki" (2026-08-14)

Stanowisko usera: *przybycie armii ma znaczenie tylko dla skrócenia timera; ważne jest kliknięcie skrzynki w dobrym momencie*. Weryfikacja na danych h1–h12:

1. **PRAWDA: dig = kliknięcie.** `get.dig.treasure.reward` wysyła klient w chwili kliknięcia skrzynki; bez kliknięcia nie ma diga (klik = „bramka aktywności"). Ranking = kolejność digów na serwerze = kolejność kliknięć.
2. **Korekta: „dobry moment" definiuje przybycie armii.** Timer klienta liczony jest z marszów (burst `push.world.march.new`), NIE z S2C `rewardtime`. Skrzynki stają się klikalne, gdy timer klienta osiągnie 0 = moment przybycia armii. Dowody: h11 — S2C z rewardtime przyszło **119 ms PO digu**; h12 — **5× projekcja +54 min**, 6. wartość realna PO digu; h8/h10 — dig **92–266 ms PRZED S2C**. We wszystkich 12 rundach dig leci **16–104 ms po burstcie marszów**. „Klik w dobrym momencie" i „dig po beaconie" to **to samo zdarzenie z dwóch perspektyw** (UI vs sieć) — armie nie tylko skracają czas, one **wyznaczają moment, w którym klik staje się możliwy**.
3. **Klik PRZED odblokowaniem nie pomaga (klient ignoruje).** Dowód h8 vs h10: identyczna metoda (python interception, środek ekranu), inna tylko forma wejścia — h8 **F1** → dig **16 ms** po beaconie (1. miejsce); h10 **mysz** → **94 ms** (5. miejsce). Gdyby klik był „kolejkowany" do odblokowania, dig wychodziłby zawsze w tym samym momencie po beaconie — a tak nie jest.
4. **Korelacja „czas diga po beaconie vs rank" (wszystkie rundy):**

| dig po beaconie (ms) | rank | plik |
|---|---|---|
| 16 | 1. | h8 |
| 57 | 1. | h7 |
| 37 | 2. | h12 |
| 97 | 2. | h1 |
| 90 (wg UI) | 3. | h11 |
| 94 | 5. | h10 |
| 83 | 8. | h2 |
| 201 | ~7. | h9 |

Najszybszy klik daje najlepszą szansę, ale nie gwarancję — rank zależy też od tempa **pozostałych** graczy (h2: 83 ms → 8. miejsce, bo inni digowali 10–30 ms po beaconie). Warunek 1. miejsca = być najszybszym klikiem w danej rundzie.

5. **Modele się godzą.** „Armie tylko skracają czas / liczy się klik" i „dig wyzwalany beacona" to ten sam mechanizm opisany z dwóch stron. Wniosek dla bota: nie ma sensu czekać na kliki klienta — dig na poziomie sieci w δ=0–10 ms po beacona wyprzedza każdy klik klienta (16–201 ms po beacona). Metodą manualną najlepszy jest **spam klawiszem (F1)**, nie myszą — najniższa zmierzona latencja klienta to 16 ms (h8).

---

## 17. WERSJA v3 — świeży ujednolicony skan wszystkich 12 pcapów (2026-08-14)

Skrypt: `_tmp_pcap\all12_analysis.py` → `_tmp_pcap\mega_out\all12.json` (+ `_tmp_pcap\all12_stats.py`). Ten sam dekoder TLV (0x80/0xA0+zlib, offsety 3/4/5) dla WSZYSTKICH 12 plików; port 8851 (plaintext) — ruch 21117 (obfuskowany) pomijany, bo niedekodowalny (sekcja 16.1). **Nowość: detekcja beacona = start najgęstszego burstu marszów w oknie 3 s przed digiem** (zamiast „pierwszego marsza w oknie ±2 s") — eliminuje fałszywe trafienia w marsze z innych rund (np. h12: wcześniej react_march 1616 ms, teraz 51 ms; h3/h5: 1068/1050 → 60/42 ms).

### 17.1 Zbiorcze statystyki (wszystkie 12 plików)

| Metryka | n | min | p50 | p90 | max | mean |
|---|---|---|---|---|---|---|
| **Cykl serwera dig→push** | 12 rund | 183.3 | **186.0** | 188.9 | 193.2 | 186.3 ms |
| **Czas przetwarzania serwera** (dig→push − RTT c→s) | 12 | 132.0 | **163.9** | 178.7 | 183.1 | 158.9 ms |
| **RTT c→s** (ACK na segmencie z digiem) | 37 | 6.5 | **18.0** | 51.3 | 53.8 | 27.6 ms |
| **RTT s→c** (czyste ACK na danych serwera) | 3630 | 0.0 | **40.3** | 114.7 | 240.5 | 46.3 ms |
| **Rozstaw pushów rankingu** (push_spacing) | 102 | 0.0 | 22.8 | 97.1 | 3961 | 47.6 ms |

Histogram rozstawu pushów (batching serwera): 0–9 ms: 35, 10–19: 14, 20–29: 11, 30–39: 5, 40–49: 12, 50–59: 4, 60–69: 3, 80–89: 5, 90–99: 3, 110–119: 1, 130–139: 1, 180–189: 2, 190–199: 1, 200–209: 1, 220–229: 1, 300–309: 3. **Wniosek: serwer wysyła pushy wielu graczy w ciasnych batchach (głównie 0–50 ms), a pojedyncze spóźnione pushy dokleja w kolejnych cyklach ~180–200 ms** — ten sam cykl co dig→push i poll→S2C (sekcja 11).

### 17.2 Per-file podsumowanie (surowe liczby ze skanu)

| plik | pkts | trwanie (s) | ogł. rund | digi | pushy | resp | nagrody | poll | marsze | RTT c→s p50 | RTT s→c p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| helikopter | 105737 | 407.3 | 10 | 5 | 9 | 4 | 1 | 10 | 42 | 24.9 (5) | 62.7 (222) |
| helikopter2 | 73787 | 297.2 | 12 | 5 | 10 | 5 | 1 | 17 | 63 | 22.1 (4) | 40.6 (218) |
| helikopter3 | 1143 | 389.9 | 15 | 5 | 10 | 5 | 1 | 19 | 85 | 13.6 (5) | 40.3 (287) |
| helikopter4 | 9914 | 365.9 | 60 | 3 | 10 | 3 | 1 | 61 | 43 | 45.8 (3) | 44.5 (164) |
| helikopter5 | 3167 | 247.8 | 9 | 4 | 10 | 5 | 1 | 10 | 70 | 10.2 (4) | 40.2 (210) |
| helikopter6 | 24429 | 416.6 | 17 | 3 | 10 | 3 | 1 | 17 | 112 | 46.6 (3) | 40.2 (407) |
| helikopter7 | 38502 | 1034.0 | 10 | 5 | 5 | 4 | 1 | 12 | 95 | 10.1 (5) | 40.3 (561) |
| helikopter8 | 10540 | 378.8 | 5 | 1 | 8 | 1 | 1 | 5 | 59 | 11.3 (1) | 75.4 (218) |
| helikopter9 | 3432 | 541.3 | 14 | 3 | 17 | 2 | 2 | 14 | 129 | 35.3 (3) | 40.0 (427) |
| helikopter10 | 10556 | 287.6 | 10 | 2 | 10 | 1 | 1 | 20 | 104 | 51.3 (2) | 40.2 (305) |
| helikopter11 | 55139 | 213.8 | 2 | 1 | 8 | 1 | 1 | 2 | 86 | 7.1 (1) | 40.2 (224) |
| helikopter12 | 151234 | 305.2 | 6 | 1 | 8 | 0 | 1 | 13 | 112 | 50.2 (1) | 40.0 (387) |

Serwer we wszystkich plikach: `15.197.67.229:8851`. RTT s→c jest zdominowane przez piggyback (p10≈0) — typowe 40 ms, ogon do 240 ms to batchy S2C.

### 17.3 Timeline wszystkich klikniętych rund (tick0 = rewardtime finałowego S2C, ms)

| plik | #dig | rank | dig_d | march_d | react_march | react_s2c | dig→push | RTT c→s | push1 | n_win | resp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| helikopter | 5 | 2 | −573 | −670 | 97 | 41 | 186 | 25 | −404 | 9 | ok |
| helikopter2 | 5 | 8 | −591 | −674 | 83 | 39 | 186 | 22 | −512 | 10 | ok |
| helikopter3 | 5 | 3 | +95 | +35 | 60 | 23 | 187 | 14 | +232 | 10 | ok |
| helikopter4 | 3 | 3 | +3 | −49 | 52 | 13 | 186 | 46 | +140 | 10 | ok |
| helikopter5 | 4 | 3 | −199 | −241 | 42 | −56 | 189 | 10 | −115 | 10 | ok |
| helikopter6 | 3 | 3 | −173 | −250 | 77 | 7 | 187 | 47 | −41 | 10 | ok |
| helikopter7 | 5 | **1** | – | – | **57** | – | 193 | 10 | – | 5 | ok |
| helikopter8 | 1 | **1** | +133 | +117 | **16** | −266 | 186 | 11 | +318 | 8 | ok |
| helikopter9 (r1) | 1 | – | +301 | +99 | 201 | 157 | – | 35 | +273 | 7 | – |
| helikopter9 (r2) | 2 | 8 | – | – | 266 | – | 184 | 35 | – | 10 | ok |
| helikopter10 | 2 | 5 | +187 | +93 | 94 | −92 | 183 | 51 | +287 | 10 | err5560006 |
| helikopter11 | 1 | 1* | −528 | −632 | 104 | −119 | 184 | 7 | −344 | 8 | ok |
| helikopter12 | 1 | 2 | −588 | −639 | **51** | −156 | 185 | 50 | −460 | 8 | ok |

\* h11: wg kolejności pushów = 1. miejsce, ale UI pokazało 3. (znana kontradykcja, sekcja 16.4). Wartości `react_march` dla h3/h5/h12 są poprawione względem v2 dzięki detekcji bursta — **nie było „czekania ~1 s": właściwy beacon (burst przy digu) jest blisko diga (42–60 ms), a wcześniejszy march (h3 −1068/−60, h5 −1050/−42, h12 −1616/−51) to marsze z innych wydarzeń/poprzednich marszów tego samego punktu**.

### 17.4 Korelacje: co determinuje pozycję (współczynnik Pearsona, r)

| Para | n | r | Wniosek |
|---|---|---|---|
| **rank ~ react_march** (dig po beacona) | 12 | **+0.643** | **najsilniejszy czynnik — im wcześniejszy dig po beaconie, tym lepszy rank** |
| rank ~ react_s2c (dig po S2C z rewardtime) | 10 | +0.500 | S2C to słabszy sygnał (przychodzi za późno / bywa przed tick0) |
| rank ~ rtt_c2s (RTT drogi c→s) | 12 | +0.313 | korelacja słaba: RTT dodaje stały offset, ale decyduje moment wysłania |
| rank ~ dig_push (cykl serwera) | 12 | −0.346 | słaba, ujemna: szybszy push lekko sprzyja lepszemu rankowi (mniej backlogu) |
| rank ~ dig_delay (względem tick0) | 10 | −0.067 | **brak korelacji — dig przed/po tick0 nie decyduje** (serwer kolejkuje, sekcja 2 pkt 7) |

Ranking według `react_march` (ms): **1. miejsce: 16 (h8), 57 (h7), 104 (h11\*)**; 2.: 51 (h12), 97 (h1); 3.: 42 (h5), 52 (h4), 60 (h3), 77 (h6); 5.: 94 (h10); 8.: 83 (h2), 266 (h9 r2). **Próg „1. miejsce" w sesjach zwycięskich: δ ≤ 57 ms po beacona (h7), najlepszy h8: 16 ms.** Wyjątek h5 (42 ms → 3. miejsce) i h4 (52 → 3.) pokazuje, że przy bardzo szybkiej konkurencji (inni digują 10–30 ms po beaconie) nawet 42–52 ms nie wystarczy — trzeba być NAJSZYBSZYM w rundzie, nie tylko szybkim.

### 17.5 Mechanizm kolejkowania żądań (potwierdzenie + nowe dane)

1. **Kolejność pushów = kolejność przyjęcia digów.** Serwer nie sortuje po tick0, tylko po chwili dotarcia C2S `get.dig.treasure.reward` (dowody: digi przed tick0 h1/h2/h11/h12 przyjęte z rankingiem; pushy idą w kolejności dotarcia — sekcja 9 pkt 1).
2. **Cykl serwera ~186 ms (183.3–193.2, n=12) jest deterministyczny** — identyczny dla 2–10 graczy, niezależnie od RTT i pory dnia. To stała przetwarzania: odbiór diga → sortowanie → wysłanie pusha rankingu w tym samym cyklu (r2 h9: 183.6 mimo 10 graczy — brak kumulacji backlogu).
3. **Czas przetwarzania serwera (samo sortowanie+push) = dig→push − RTT c→s = p50 163.9 ms (zakres 132–183)** — reszta cyklu 186 ms to transmisja i batchowanie S2C.
4. **Batching S2C:** pushy wielu graczy wychodzą w ciasnych grupach (62/102 w 0–50 ms; hist. wyżej) — serwer wysyła jedną porcję S2C na cykl, kolejność wewnątrz = kolejność digów.
5. **RTT c→s jest krótkie i stabilne (p50 18, p90 51, max 54 ms)** — nie ma ogona 230 ms jak w s→c; droga w górę nie jest wąskim gardłem. Serwer ACKuje segment z digiem natychmiast (piggyback w S2C).
6. **`errorCode 5560006` = duplikat/za późno** (h10, h9 r2) — przychodzi po pushu, nieszkodliwy; pierwszy dig rundy zawsze zaliczony.

### 17.6 Model przewidywania idealnego momentu diga (finalny)

> **v4 (sekcja 18.4):** doprecyzowanie — `t_beacon` = **pierwszy marsz bursta** (nie czekać na potwierdzenie ≥2 marszów), δ = **0 ms** + spam 5× co 30–50 ms; konkurencja diguje 4–126 ms po beaconie (p10=15), warunek rank 1 = `δ + RTT_c2s ≤ przybycie najszybszego rywala`.

```
t_send_dig = t_beacon + δ,            δ ∈ [0, 10] ms   (domyślnie δ = 0–5 ms)
```

- **Sygnał tick0/otwarcia: beacon = start najgęstszego burstu `push.world.march.new`** (≥2 marsze w 50 ms; w praktyce 5–20 marszów w ~100 ms). Klient gry diguje 16–201 ms po beacona (śr ~90 ms); zwycięzcy h7/h8/h12: 16/57/51 ms.
- **Bot wysyłający w δ=0–10 ms po beacona jest szybszy niż jakikolwiek zmierzony klient** (min. 16 ms) i trafia w okno „≤ 57 ms = 1. miejsce".
- **Kompensacja RTT jest zbędna**: RTT c→s p50 18 ms / p90 51 ms dodaje tylko offset; serwer i tak przyjmuje digi przed tick0 do kolejki (h1 −573, h2 −591, h11 −528, h12 −588 ms). Wysyłanie `t_beacon − RTT` ryzykuje wysłanie PRZED beacona — niepotrzebne.
- **Faza cyklu serwera:** dig przyjęty w trakcie cyklu jest sortowany w bieżącym cyklu (dig→push 183–193 zawsze), więc nie trzeba synchronizować z fazą — liczy się tylko kolejność dotarcia.
- **Długość rundy / prognozowanie tick0:** `rewardtime` jest projekcją skokową (sekcja 16.5), `startTime` zmienia się nieregularnie — **nie ekstrapolować; jedyny niezawodny sygnał to beacon w czasie rzeczywistym**.

Prawdopodobieństwo 1. miejsca przy δ=0–10 ms: bot jest pierwszy w kolejce dotarcia w praktycznie każdej rundzie, o ile żaden inny bot/gracz nie wysyła wcześniej niż 10 ms po beaconie. Pozostałe ryzyko to (a) dig wysłany PRZED faktycznym otwarciem okna (serwer przyjmuje — h1/h2), (b) ultrakrótki RTT konkurenta (< 10 ms) z jednoczesnym wysłaniem.

### 17.7 Algorytm automatycznego klikania (finalny, z krokiem implementacji)

> **v4 (sekcja 18.5):** aktualizacja — detekcja beacona od **pierwszego** marsza (bez czekania na burst ≥2), δ=0, spam **5× co 30–50 ms**, kalibracja EMA rozszerzona o `przybycie_najszybszego_rywala ≈ push1 − 186 ms`; stan kodu `src/bot/network_sniffer.py` (wykrywanie po rozmiarze 227–229B) wymaga dodania dekodera TLV.

**Architektura:** `[sniffer: port 8851] → [detektor beacona] → [injector C2S dig] → [stan: czekaj na wynik]`

1. **Sniffing i dekodowanie.** Nasłuchuj pakiety z `dport==8851` (C2S) i `sport==8851` (S2C) na `15.197.67.229`. Dekoduj payloady TLV: `80 <len:2BE> 12 <body>` (plain) oraz `a0 <len:2BE> 78 <zlib>` (zlib offsety 3/4/5; po dekompresji od `12`). Reuse: `_pcap_tlv.py` + `decompress_payload` z `_pcap_mega.py`. Kluczowe wzorce bajtowe: `b"push.world.march.new"` (beacon), `b"get.dig.treasure.reward"` (dig), `b"push.dig.treasure.reward"` (ranking), `b"push.receive.reward"` (nagroda), `b"5560006"` (duplikat).
2. **Detekcja beacona.** Stan SEEK → pierwszy S2C z `push.world.march.new` uruchamia licznik; **burst = ≥2 marsze w odstępie ≤50 ms** → ARMED, zapamiętaj `t_beacon = ts pierwszego marsza bursta` (fallback: pojedynczy marsz po ciszy ≥5 s). Ignoruj pojedyncze marsze spoza bursta (h3/h5/h12 mają osobne marsze sprzed rundy).
3. **Wysłanie diga.** W `t_beacon + δ` (δ=0–5 ms) wyślij C2S 91B (bez aac):
   ```
   80 <len:2BE> 12
   {c:'get.dig.treasure.reward', a:<i16>, p:{c:'get.dig.treasure.reward', r:-1,
    p:{_id:<i64>, uuid:<i64>}}}
   ```
   `uuid` = sesyjne z pcap (h8: 1404003122346651631; h10: 1404003131012083561; nowe na sesję), `_id` = kolejny licznik klienta. **Wstrzyknij do istniejącego połączenia TCP klienta** (te same seq/ack — wymaga przechwycenia strumienia, najlepiej loopback/Npcap + rejestracji stanu TCP) albo jako osobne połączenie, jeśli serwer przyjmuje (niezweryfikowane — test A/B na koncie testowym).
4. **Spam fallback.** Wyślij 3–5 digów co 30–50 ms (okno ~200 ms). Serwer przyjmuje pierwszy, kolejne → `5560006` (nieszkodliwe). Wzorzec zgodny z klientem gry (1–5 digów/rundę).
5. **Stan/stop.** Po `push.receive.reward` (wygrana), naszym uid w `push.dig.treasure.reward`, lub S2C `get.dig.treasure.reward` z errorCode → powrót do SEEK. Nie diguj dalej w tej rundzie.
6. **Kalibracja online (EMA).** Co rundę mierz: `react_march` (t_beacon→nasz dig), RTT c→s (ACK na własnym digu), `dig→push`. Domyślnie δ=0–5 ms; jeśli beacon regularnie wyprzedza tick0 o >500 ms (jak wstępne marsze h3/h5), trzymaj δ=0 — serwer kolejkuje, a wczesny dig nie szkodzi (sekcja 17.6).
7. **Anty-detekcja.** Diguj tylko PO beacona (nigdy przed bez dowodu), rozmiar 91B, interwały 30–100 ms jak klient, nie modyfikuj ruchu klienta gry. Test na koncie testowym przed głównym (ryzyko bana za wstrzykiwanie).

**Kroki implementacji (konkretnie):**
- `src/bot/network_sniffer.py` — rozszerzyć o filtr `dport==8851`/`sport==8851` i TLV 0x80/0xA0 (już częściowo jest: `pcap_8851.py`, `pcap_8851_burst.py` w `scripts/`).
- Nowy moduł `dig_engine.py` (stan maszyny: SEEK → ARMED → SEND → DONE; detekcja bursta wg pkt 2; formowanie 91B wg pkt 3; spam pkt 4).
- Integracja z `bot_runner.py` jako dodatkowy trigger obok OCR (sekcja 5: OCR timer ma lag 1.5–3.4 s — beacon jest ~100× dokładniejszy).
- Testy: `tests/bot/test_network_sniffer_pcap_replay.py` — odtworzyć h8/h11/h12 (znane digi/pushy) i zweryfikować, że engine diguje w δ=0–10 ms po beacona z rank 1.

### 17.8 Potwierdzone fakty końcowe (aktualizacja sekcji 2)

1. **Pozycja = kolejność dotarcia `get.dig.treasure.reward` na serwerze** (kolejność pushów). Najsilniejszy predyktor rankingu: **czas diga po beaconie (r=+0.643)**; dig_delay względem tick0 — bez korelacji (r=−0.067).
2. **Cykl serwera ~186 ms (183.3–193.2) deterministyczny; przetwarzanie serwera p50≈164 ms**; RTT c→s p50 18 ms (stabilne); RTT s→c p50 40 ms (ogon = batchy S2C).
3. **Zwycięzcy: dig 16–57 ms po beacona** (h8/h7/h12); bot δ=0–10 ms wyprzedza każdego zmierzonego klienta.
4. **S2C z `rewardtime` nie jest sygnałem diga** (przychodzi −630…+399 ms względem tick0; bywa PO digu).
5. **Digi przed tick0 przyjmowane do kolejki** (h1 −573, h2 −591, h11 −528, h12 −588 ms) — wczesny dig nie szkodzi.
6. **h11 rank 1 wg pushów vs 3. w UI — jedyna niezgodność push-order↔pozycja** (sekcja 16.4); wymaga powtórki manualnej.

---

## 18. WERSJA v4 — weryfikacja powtarzalności + wyścig z konkurencją + budżet opóźnień (2026-08-14)

Świeży, powtórzony skan wszystkich 12 pcapów (`_tmp_pcap\all12_analysis.py` → `mega_out\all12.json`, `all12_stats.py`) oraz nowa analiza `_tmp_pcap\competitor_analysis.py` (→ `competitor_out.txt`). Wynik weryfikacji: **wszystkie liczby v3 odtworzone 1:1** — wnioski i model z sekcji 17 są stabilne. Poniżej nowe twarde dane i doprecyzowany model.

### 18.1 Weryfikacja powtarzalności (v4 = v3)

| Metryka | v3 (pierwotny skan) | v4 (świeży skan) | status |
|---|---|---|---|
| Cykl serwera dig→push (n=12) | min 183.3, p50 186.0, max 193.2 | min 183.3, p50 186.0, max 193.2 | **identyczny** |
| RTT c→s (n=37) | p50 18.0, p90 51.3, max 53.8 | p50 18.0, p90 51.3, max 53.8 | **identyczny** |
| RTT s→c (n=3630) | p50 40.3, p90 114.7, max 240.5 | p50 40.3, p90 114.7, max 240.5 | **identyczny** |
| Rozstaw pushów (n=102) | p50 22.8, p90 97.1, max 3961 | p50 22.8, p90 97.1, max 3961 | **identyczny** |
| rank ~ react_march | r=+0.643 | r=+0.643 | **identyczny** |
| rank ~ react_s2c / rtt_c2s / dig_push / dig_delay | +0.500 / +0.313 / −0.346 / −0.067 | +0.500 / +0.313 / −0.346 / −0.067 | **identyczny** |

Struktura batchy S2C (nowość — grupowanie pushów przy przerwie >60 ms): **n=22 grup**, rozmiary `[8,1,14,2,1,1,2,7,2,1,2,21,2,5,2,1,2,5,6,20,2,9]` — serwer wysyła pushy kilku graczy jednym segmentem TCP (coalescing), duże grupy 14/21/20 to „wszyscy zwycięzcy jednego cyklu".

**Wniosek: pomiary są deterministyczne i odtwarzalne** (stałe serwera, RTT, ranking sygnałów) — model nie wymaga zmian.

### 18.2 Wyścig z konkurencją — kiedy rywale digują (nowość)

**Metoda:** serwer pushuje w kolejności przyjęcia digów, a dig→push ≈ 186 ms (stała, sekcja 17.1). Stąd **czas przybycia diga rywala ≈ jego push − 186 ms**. Poniżej: nasz dig (wysłany), nasze przybycie na serwer (dig + RTT c→s), najszybszy rywal i margines (ujemny = rywal przybył wcześniej). Wszystkie wartości względem **pierwszego marsza beacona** (ms).

| plik | rank | nasz dig (wysłany) | nasze przybycie | najszybszy rywal | **margines** | nasz push | liczba rywali |
|---|---|---|---|---|---|---|---|
| helikopter8 | 1 | 16 | 27 | 64 | **+37** | 201 | 7 |
| helikopter11 | 1 | 104 | 111 | 126 | **+14** | 288 | 7 |
| helikopter | 2 | 97 | 122 | 81 | −41 | 283 | 8 |
| helikopter12 | 2 | 51 | 101 | −6* | −108 | 236 | 7 |
| helikopter3 | 3 | 60 | 74 | 11 | −63 | 247 | 9 |
| helikopter4 | 3 | 52 | 98 | 4 | −94 | 238 | 9 |
| helikopter5 | 3 | 42 | 52 | −60* | −112 | 231 | 9 |
| helikopter6 | 3 | 77 | 123 | 23 | −100 | 264 | 9 |
| helikopter10 | 5 | 94 | 145 | 8 | −137 | 278 | 9 |
| helikopter2 | 8 | 83 | 105 | −24* | −129 | 269 | 9 |
| helikopter9 (r1) | – | 201 | 237 | −12* | −249 | 201 | 7 |

\* wartość ujemna = pierwszy push przyszedł <186 ms po beaconie (push1−186 < 0), tj. **zwycięzca wykopał zanim my zdetektowaliśmy „beacon"** — jego armia dotarła przy wcześniejszym marszu rundy, a nasza detekcja (start najgęstszego bursta) zaczyna się od późniejszego marsza w tym samym ~100 ms burstcie. Uwaga: wypchnięcie diga do następnego cyklu serwera przesunęłoby szacunek w przeciwną stronę (za późno), więc wartości ujemne to wyłącznie offset detekcji beacona / wczesne armie. Dla modelu oznacza to: **detekcja beacona może spóźniać się o ~10–25 ms (skrajnie do 60 ms) względem najwcześniejszego możliwego diga** — trzeba digować OD PIERWSZEGO marsza (nie czekać na potwierdzenie bursta ≥2).

Dystrybucja przybycia digów **wszystkich rywali** (n=90, est.):
`min=−60, p10=15, p50=123, p90=374, max=4535 ms` po beaconie; histogram (20 ms): **14 rywali przybywa ≤60 ms** (5 w 0–19, 3 w 20–39, 6 w 40–59), kolejnych **37 w 60–139 ms** (7/9/9/12). Najszybsi rywale w „ciasnych" rundach (h3/h4/h6/h10) przybywają **4–23 ms po beaconie**.

**Wnioski:**
1. **Margines decyduje 1:1 o ranku**: wygrane rundy mają margines **+14…+37 ms**, wszystkie przegrane −41…−249 ms. Warunek rank 1: `nasze_przybycie ≤ przybycie_najszybszego_rywala`.
2. **Typowy klient gry diguje 16–201 ms po beaconie (śr ~90)** — bot przy δ=0–5 ms + RTT p50 18 ms przybywa w ~23 ms (p90: 56 ms), więc **wyprzedza klienta** w praktycznie każdej rundzie (najszybszy zmierzony klient = 16 ms h8).
3. **Jedynym ryzykiem jest inny bot / wyjątkowo szybki klient digujący 0–10 ms po beaconie** (pierwszy marsz): wtedy wygrywa ten z mniejszym δ + niższym RTT — dlatego **spam 3–5 digów i δ=0** (najwcześniejsze możliwe) jest koniecznością, nie opcją.

### 18.3 Pełny budżet opóźnień: beacon → nagroda („inne opóźnienia systemowe")

| # | Etap | Wartość | Źródło (pomiar) |
|---|---|---|---|
| 1 | Beacon: pierwszy marsz bursta `push.world.march.new` | t=0 | 12 pcapów |
| 2 | Reakcja klienta gry (march → dig) | 16–201 ms, śr ~90 ms | 12 rund |
| 3 | Bot: δ od pierwszego marsza | **0–5 ms (spam 5× co 30–50 ms)** | model |
| 4 | RTT c→s (wysłanie → przybycie na serwer) | p50 18 ms, p90 51 ms, max 54 ms | ACK na segmencie z digiem, n=37 |
| 5 | Przetwarzanie serwera: odbiór → sortowanie → push | p50 ~164 ms (132–183) | dig→push − RTT c→s, n=12 |
| 6 | Pełny cykl dig→push | p50 186 ms (183.3–193.2) | n=12 |
| 7 | Nasz push rankingu po beaconie (rundy wygrane) | 201 (h8), ~250 (h7: 57+193), 288 (h11) ms | pcap |
| 8 | S2C `world.get.detail.new` z rewardtime | +72…+399 ms po tick0 | za późno na sygnał diga |
| 9 | Nagroda `push.receive.reward` | ~1–3 ms PRZED naszym pushem | h11/h12 |

Rachunek: `1→3 + 4 + 6 = 5 + 18 + 186 ≈ 209 ms` — zgadza się z zmierzonym `nasz push po beaconie` (201–288 ms). Łańcuch jest zdominowany przez stałą serwera (186 ms), którą dzielą wszyscy gracze — **nie da się jej skrócić, można tylko wyprzedzić konkurencję w etapach 2–4**. Lokalne opóźnienia systemowe (rendering, OCR, kolejki wejścia) nie uczestniczą w tym łańcuchu, bo dig wysyła klient gry na przybyciu armii — bot działa na poziomie sieci.

### 18.4 Model przewidywania idealnego momentu (finalny v4)

```
t_send_dig = t_beacon_1st_march + δ        δ = 0 ms (spam od pierwszego marsza)
P(1. miejsce) = P( δ + RTT_c2s ≤ przybycie najszybszego rywala )
  δ=0, RTT p50 18 / p90 51 → przybycie 18–23 ms (p90: 56 ms)
  zmierzone przybycia najszybszych rywali: 4–126 ms (p10=15 ms)
```

- **Twardy warunek z danych:** przybycie ≤ 15 ms (p10 rywali) daje ~90% szans bycia najszybszym; przybycie 23 ms (δ=0 + RTT p50) — ~70–85% (między p10 a gęstą grupą 14 rywali w 0–60 ms).
- **Spam 5× co 30–50 ms** przesuwa przybycie kolejnych digów na 18–23, 48–73, 78–123, … — pokrywa niepewność detekcji pierwszego marsza (10–25 ms, sekcja 18.2) i ewentualną utratę pojedynczego pakietu.
- **Nie czekać na potwierdzenie bursta (≥2 marsze):** pierwszy marsz może być już 4–23 ms „za" najszybszym rywalem — digować od pierwszego marsza, burst potwierdza tylko fakt rundy.
- **Brak kompensacji RTT** (potwierdzone: digi 573–591 ms przed tick0 przyjęte, sekcja 17.6) — serwer kolejkuje, liczy się kolejność dotarcia, a wysyłanie `t_beacon − RTT` ryzykuje wysłanie przed pierwszym marszem.
- **Długość rundy nieekstrapolowalna** (rewardtime skokowy, sekcja 16.5) — jedyny realny sygnał tick0 = beacon w czasie rzeczywistym.

### 18.5 Algorytm automatycznego klikania (finalny v4 — korekty do 17.7)

Architektura bez zmian: `[sniffer: port 8851] → [detektor beacona] → [injector C2S dig] → [stan: czekaj na wynik]`. Kroki:

1. **Sniffing i dekodowanie** — jak w 17.7 pkt 1 (TLV 0x80/0xA0+zlib, wzorce bajtowe `push.world.march.new` / `get.dig.treasure.reward` / `push.dig.treasure.reward` / `push.receive.reward` / `5560006`). Reuse: `_pcap_tlv.py`, `decompress_payload` z `_pcap_mega.py`.
2. **Detekcja beacona — WERSJA SZYBKA (v4):** ARMED od **pierwszego** marsza `push.world.march.new` po ciszy ≥5 s; `t_beacon = ts pierwszego marsza` (NIE czekać na burst ≥2 — marże 10–25 ms, sekcja 18.2). Potwierdzenie bursta (≥2 marsze ≤50 ms) służy tylko walidacji rundy i kalibracji fałszywych alarmów (marsze z innych wydarzeń: h3/h5/h12).
3. **Wysłanie diga:** natychmiast w `t_beacon + δ`, δ=0; C2S 91B bez aac:
   ```
   80 <len:2BE> 12
   {c:'get.dig.treasure.reward', a:<i16>, p:{c:'get.dig.treasure.reward', r:-1,
    p:{_id:<i64>, uuid:<i64>}}}
   ```
   `uuid` = sesyjne z pcap, `_id` = kolejny licznik klienta. Wstrzyknięcie do istniejącego połączenia TCP klienta (te same seq/ack) lub osobne połączenie (niezweryfikowane — test A/B na koncie testowym).
4. **Spam fallback (v4): 5 digów co 30–50 ms** (maks okno 250 ms). Serwer przyjmuje pierwszy, kolejne → `5560006` (nieszkodliwe; wzorzec zgodny z klientem gry 1–5 digów/rundę). Spam eliminuje ryzyko: pojedynczego pakietu, niepewności pierwszego marsza, kolizji z fazą cyklu serwera.
5. **Stan/stop:** po `push.receive.reward` / naszym uid w `push.dig.treasure.reward` / errorCode → powrót do SEEK. Nie digować dalej w tej rundzie.
6. **Kalibracja online (EMA) — rozszerzona v4:** co rundę mierz (a) `react_march` naszego diga, (b) RTT c→s (ACK na własnym digu), (c) `dig→push`, (d) **`przybycie_najszybszego_rywala ≈ push1 − 186 ms`** oraz (e) margines. Jeśli EMA przybycia najszybszego rywala > 40 ms — można zwiększyć δ do 5–10 ms (mniej sygnatury spamu); jeśli < 15 ms — trzymać δ=0 i pełny spam 5×.
7. **Anty-detekcja:** jak w 17.7 pkt 7 (rozmiar 91B, interwały 30–100 ms jak klient, nie modyfikować ruchu klienta; test na koncie testowym).

**Kroki implementacji (konkretnie, aktualny stan kodu):**
- `src/bot/network_sniffer.py` — istnieje, ale wykrywa tick=0 **po rozmiarze pakietu (227–229B)** i pre-tick po prefiksach 502/511/512B (sekcja 5/13); **brakuje** dekodowania TLV i detekcji `push.world.march.new`. Należy dodać filtr `sport==8851`, dekompresję 0xA0 (offsety 3/4/5) i callback `on_beacon`.
- Nowy moduł **`src/bot/dig_engine.py`** (stan: SEEK → ARMED → SEND → DONE; szybka detekcja pierwszego marsza; formowanie 91B; spam 5× co 30–50 ms; kalibracja EMA z sekcji 18.5 pkt 6).
- Integracja z `src/bot/bot_runner.py` jako dodatkowy trigger obok OCR (OCR timer ma lag 1.5–3.4 s — beacon jest ~100× dokładniejszy).
- Testy: `tests/bot/test_network_sniffer_pcap_replay.py` (istnieje) — rozszerzyć o replay h8/h11/h12 z weryfikacją, że engine diguje od pierwszego marsza (δ=0) i osiąga rank 1 przy znanych danych.

### 18.6 Aktualizacja wniosków końcowych (uzupełnienie 17.8)

1. **Moment diga rywali jest twardym ograniczeniem:** przybycie najszybszego rywala 4–126 ms po beaconie (p10=15 ms); wygrane rundy miały margines +14…+37 ms, wszystkie przegrane ujemne (−41…−249 ms).
2. **Bot przy δ=0 + spam 5× pokrywa całe ryzyko** (detekcja pierwszego marsza ±15 ms, pojedynczy pakiet, RTT p90 51 ms) i przybywa w 18–23 ms (p90 56) — szybciej niż jakikolwiek zmierzony klient gry.
3. **Pomiary v4 = v3 w 100%** — cykl serwera, RTT i korelacje są stabilne; model z sekcji 17/18 można wdrażać bez zmian.
4. Pozostałe ryzyka niezmienne: wstrzykiwanie C2S na połączeniu klienta (niezweryfikowane), h11 push-order↔UI (sekcja 16.4), ban za wstrzykiwanie (test na koncie testowym).

### 18.7 Empiryczna krzywa szans na 1. miejsce (n=11, tylko rundy z kliknięciem)

**Zmotywowane pytaniem:** „czy samo szybsze/wcześniejsze klikanie daje 1. miejsce?" — **nie**. Dane: szybkość klikania bez wpływu (h7 19 CPS vs h8 100 CPS, oba 1.; h10 100 CPS → 5.), wcześniejsze klikanie szkodzi (h3/h4 3.5–4.3 s przed → 3. miejsce + aac), a o pozycji decyduje **latencja klienta po odblokowaniu skrzynki** (beacon): h8 F1 → dig 16 ms, h10 mysz → 94 ms — ta sama ilość klików, inny kanał wejścia.

P(1. miejsce | nasze przybycie = A) wyznaczona z najszybszego rywala w każdej rundzie (`_tmp_pcap\competitor_analysis.py`, sekcja 18.2):

| przybycie A (ms po beaconie) | P(1. miejsce) | metoda |
|---|---|---|
| 0 | **64 %** (7/11) | wstrzyknięcie diga (δ=0) |
| 5 | 55 % (6/11) | wstrzyknięcie + bezpiecznik |
| 10 | 45 % (5/11) | granica wykrywalności |
| 16 | 36 % (4/11) | **natywne maksimum** (h8, F1, klient 16 ms) |
| 23 | 27 % (3/11) | natywne δ=0 + RTT p50 18 ms |
| 40–60 | 27 % (3/11) | natywne przeciętne |

Zastrzeżenia: n=11 (mała próba), wartości „rywal przed beaconem" (ujemne, sekcja 18.2) to artefakt detekcji bursta — bot na **pierwszym** marszu odzyskuje 10–25 ms, więc realne wartości są wyższe dla obu metod; **porządek między metodami pozostaje**: wstrzyknięcie ≈ 2× szansa natywnej.

**Wniosek operacyjny:** natywnie (klik + sniffer) mamy ~1/3 szans na 1. miejsce na rundę — tyle daje sam klient; „kliknięcie szybciej" nie przekracza latencji klienta (~16 ms). Determinizm (~2/3) daje dopiero wstrzyknięcie diga 0–5 ms po pierwszym marszu. W obu wariantach przegrywamy rundy, w których rywal wykopie ≤0–5 ms po beaconie.

### 18.8 Decyzja: wariant ZERO-RYZYKA (wybrano 2026-08-14)

**Wybór użytkownika: nie wstrzykiwać pakietów. P(1. miejsce) ~36–50% na rundę, zero ryzyka bana.**

Zasady twarde (żadne z poniższych nie modyfikuje strumienia sieciowego):
1. **Bez wstrzykiwania C2S**, bez osobnych połączeń, bez hookowania `send()` klienta — cały ruch generuje klient gry.
2. **Bez aac**: klik tylko w oknie <1 s przed eventem (wzorzec h7/h8 → brak `aac`; h3/h4 klikanie 3.5–4.3 s przed → aac >0).
3. **Kanał wejścia = F1 (Interception), nie mysz**: h8 F1 → dig 16 ms; h10 mysz @960,520 → 94 ms — identyczna ilość klików, różnica 1. vs 5. miejsce.
4. **Detekcja beacona od PIERWSZEGO marsza** `push.world.march.new` (nie najgęstszy burst, nie czekać na ≥2 marsze) — zysk 10–25 ms (sekcja 18.2).
5. Warm spam F1 „na gorąco" w ostatnim <1 s (pierwszy klik po odblokowaniu skrzynki = minimalna latencja klienta).

**Infrastruktura istniejąca (stan kodu 2026-08-14):**
- `src/bot/network_sniffer.py` — wykrywa pre-tick (502/511/512B prefiksy, ~1.1 s/0.5 s/0.02 s przed tick0) i tick=0 (rozmiar 227–229B). **Brakuje**: dekodera TLV (`push.world.march.new`) i callbacku beacona.
- `src/shared/driver_installer.py` + Interception — symulacja wejścia niewidzialna dla API (jak istniejące F1 w h8).
- `src/bot/macro_engine.py` — `spam_click` pełną szybkością, wzorzec klików ~1 s (sekcja: issue_spam_click).
- Testy: `tests/bot/test_network_sniffer_pcap_replay.py` — replay pcapów, rozszerzyć o h8 (weryfikacja: klik w <20 ms po beaconie → rank 1).

**Pozostała implementacja (do wykonania) — STAN NA 2026-08-14, PO REALIZACJI:**
1. ✅ **Zrealizowane** — dekoder TLV 0x80/0xA0+zlib w `network_sniffer.py` (metoda statyczna `_decode_tlv`, wzorzec z `_tmp_pcap/all12_analysis.py` `dec()`) → filtr `push.world.march.new` → `BeaconEvent` + `on_beacon(t)` z `t` = pierwszy marsz po ciszy ≥5 s (konfigurowalne `beacon_silence_s`).
2. ✅ **Zrealizowane** — nowy moduł `src/bot/dig_engine.py` (`DigEngine`): `on_beacon` → natychmiast `press_key("F1")` (δ=0) + warm spam 6× co 40 ms w oknie <1 s; wzorzec jak h8 (Interception, full-speed).
3. ✅ **Zrealizowane** — nie ignorujemy pojedynczych marszy: detekcja od PIERWSZEGO marsza po ciszy (zasada 4); false positive akceptowalny (zasada 5).
4. ⏳ **Do wykonania** — kalibracja EMA na żywo: RTT c→s, react_march, przybycie najszybszego rywala (push1 − 186 ms) — jak 18.5 pkt 6.

### 18.9 Implementacja wariantu zero-ryzyka — wyniki (2026-08-14)

**Zrealizowano** (kod + testy, zgodnie z planem 18.8):

1. **`src/shared/constants.py`** — dodano brakujące stałe `NETWORK_PRE_TICK_SIZES=(502,511,512)` i `NETWORK_PRE_TICK_PREFIXES` (`a001f378/a001fc78/a001fd78`). (Naprawa: testy pre-tick importowały je, a stałe nie istniały — blokowały całą kolekcję pytest.)

2. **`src/bot/network_sniffer.py`**:
   - `BeaconEvent` (dataclass) + stałe `BEACON_MARCH_MARKER`, `BEACON_SILENCE_DEFAULT_S=5.0`.
   - `NetworkSniffer._decode_tlv(payload)` — dekompresja TLV: 0xA0 zlib (offsety 3/4/5, pierwszy działający) i 0x80 (2-bajtowa długość BE) — identyczna logika co `_tmp_pcap/all12_analysis.py::dec()`.
   - Detekcja beacona w `_handle_packet`: TLV-dekod → `push.world.march.new` w body → **pierwszy marsz po ciszy ≥`beacon_silence_s`** emituje `BeaconEvent` (event + `on_beacon` callback + `wait_for_beacon_event(timeout)`).
   - `reset()` czyści stan beacona (`_latest_beacon`, `_last_march_mono`).

3. **`src/bot/dig_engine.py`** (nowy) — `DigEngine(clicker, key="F1", spam_count=6, interval_ms=40, window_s=1.0)`:
   - `on_beacon(evt)` (wątek sniffera): pierwszy press F1 przy δ=0, potem warm spam co `interval_ms` do wygaśnięcia okna; blokada przed podwójnym spamem przy nakładających się beaconach; statystyki (`beacons_seen`, `digs_triggered`, `last_dig_latency_s`).
   - Zero ryzyka: brak wstrzykiwania C2S, brak `aac` — wyłącznie odczyt S2C + `interception.press("F1")`.

4. **Testy** (wszystkie zielone):
   - `tests/bot/test_network_sniffer.py` — +10 testów beacona (dekoder 0x80 i 0xA0/zlib, cisza ≥5 s, burst bez re-triggera, callback, reset, no-op).
   - `tests/bot/test_dig_engine.py` (nowy) — 6 testów: klawisz konfigurowalny, δ≈0 dla pierwszego pressa, statystyki, brak podwójnego spamu, odporność na błąd sterownika.
   - `tests/bot/test_network_sniffer_pcap_replay.py` — +`test_h8_beacon_replay_triggers_immediate_dig`: replay `helikopter8.pcapng` → beacon wykryty → **pierwszy dig <20 ms po beaconie** (h8 = runda wygrana 1. miejsce, dig 16 ms) — potwierdza przeniesienie zwycięskiego timingu h8 na sniffer.
   - Sumarycznie: sniffer+pre-tick+beacon **61 passed**, dig_engine **6 passed**, replay **3 passed**.

**Pozostałe kroki do wdrożenia na żywo (poza zakresem tej sesji):**
- ~~Podpięcie `DigEngine` jako `on_beacon` w `bot_runner.py`/`macro_engine.py` (obecnie runner nie używa `NetworkSniffer`).~~ **✅ Zrealizowane 2026-08-14** (patrz niżej „Podpięcie sniffera w realnym makrze").
- Kalibracja EMA (pkt 4 powyżej) na podstawie żywych pomiarów.
- Ewentualne rozszerzenie `wait_for_beacon_event` na pętlę rund (reset między rundami).

### 18.9.1 Podpięcie sniffera w realnym makrze (2026-08-14)

**Cel:** sniffer istniał (beacon + rewardtime), ale `BotRunner` go nie używał — stąd w logach bota nie było linii „server countdown" / „network sniffer". Podpięto go do prawdziwej ścieżki makra (`custom.macro.json` → Krok 5 `watch_timer`), w pełni zgodnie z zasadą z 18.8: **sniffer działa wyłącznie w fazie `watch_timer`** (start/stop w try/finally), `DigEngine` wywołuje natywny `press_key("F1")` — zero wstrzykiwania C2S.

**Zmiany:**
1. **`src/shared/config.py`** — `BotConfig.server_ip = "15.197.67.229"`, `server_port = 8851` (serwer gry).
2. **`src/bot/bot_runner.py`** — `__init__` tworzy `DigEngine(clicker, key="F1")` i `NetworkSniffer(server_ip/port, pre_tick_sizes, pre_tick_prefixes, on_beacon=dig_engine.on_beacon)` i przekazuje oba do `MacroEngine(sniffer=…, dig_engine=…)`.
3. **`src/bot/macro_engine.py`**:
   - `__init__(…, sniffer=None, dig_engine=None)`.
   - `_handle_watch_timer`: na wejściu fazy `sniffer.start()` (try/finally; start/stop wokół całej fazy — obejmuje też wczesne returny i timeout), log `watch_timer: network sniffer active/no-op`.
   - Co sekundę log `watch_timer: server countdown=<Ns> (rewardtime_ms=…) ocr=<OCR>` — porównanie odliczania serwera (rewardtime) z OCR w realnym czasie makra.
4. **Testy** (`tests/bot/test_macro_engine_scenarios.py`): `FakeWatchSniffer` + 3 testy — sniffer start/stop wokół fazy, log countdownu wraz z OCR, stop sniffera przy `stop()` mid-phase. Razem z dry-runem: **29 passed**.

**Efekt:** przy starcie bota (krok watch_timer w makrze) w logach pojawia się aktywacja sniffera i co sekundę odliczanie serwera obok OCR; przy beaconicie (pierwszy `push.world.march.new` po ciszy ≥5 s) `DigEngine` wciska F1 — bez żadnego C2S.

### 18.10 Dry-run: wspólny timeline OCR + sieć w fazie watch_timer (2026-08-14)

**Cel (wg wymagań):** narzędzie walidacyjne, które **sniffuje wyłącznie w fazie `watch_timer`**, loguje jeden wspólny timeline z OCR (z `assets/macros/custom.macro.json` — Krok 5, ROI 47.7/36.2/52.2/38.5, idle 10 s / fast 0.2 s / fast_th 300 / spam_th 5 / spam 7 s @100 c/s), loguje wszystko co wykrywa sniffer (dokładne odliczanie z logiki serwera — rewardtime), porównuje z OCR oraz loguje **kiedy BY kliknął** (trigger OCR) i **kiedy BY wysłał diga** (beacon → F1) — **bez żadnego klikania** (dry run).

**Implementacja — `src/debug/dry_run_watch.py` + `tests/debug/test_dry_run_watch.py` (8 testów, wszystkie zielone; ruff czysty):**

- `DryRunWatchTimer` — klasa: ładuje makro, znajduje krok `watch_timer`, uruchamia `NetworkSniffer` **try/finally** (start na wejściu w fazę, stop na wyjściu — sniffer działa TYLKO w tej fazie), powtarza logikę faz `idle→fast→spam` (histereza, filtr monotoniczności stale-jump 30 s — wierny mirror `_handle_watch_timer`).
- `DryRunClicker` — kliker, który nigdy nie klika: każde zdarzenie (`click_at`/`spam_click`/`press_key`/`scroll`) przekierowuje do timeline'a jako `would_click`/`would_spam`/`would_dig`/`would_scroll`. Podpięty do `MacroEngine`-podobnej pętli **oraz** do `DigEngine` (`on_beacon` → `press_key("F1")` → tylko log).
- Timeline (CSV, źródła): `ocr` (value + confidence + method + sanity + raw), `ocr_reject` (odrzucony skok), `rewardtime` (server: `rt_ms`, `remaining` w momencie odczytu = `rt/1000 − wall_clock`, próbkowany co `--rewardtime-poll-s`), `pre_tick` (502/511/512B, przewidywany lead), `beacon` (pierwszy marsz po ciszy), `tick` (227–229B), `phase` (idle/fast/spam), `confirm` (histereza), `would_spam` (trigger OCR + docelowe współrzędne % → px + okno + cps), `would_dig` (press F1), `info`.
- Podsumowanie (`run()` → dict): liczniki (ocr_reads/failures, rewardtime_samples, beacons, pre_ticks, ticks), `would_spam_triggered` + `would_spam_value_s`, `digs_triggered` + `first_dig_latency_s` (δ diga względem beacona), oraz **`ocr_vs_server_deltas`** — dla każdego odczytu OCR najbliższa próbka rewardtime (≤2 s) i różnica `delta = OCR − server_remaining` (odpowiedź na „jak się różni od OCR").

**Uruchomienie (na żywo, przy włączonej grze) — przez `-m`, żeby `src` był w sys.path:**
```
python -m src.debug.dry_run_watch --timeout-s 7200 --out dry_run_timeline.csv
# opcjonalnie: --capture-region "l,t,w,h" (region przechwytywania okna gry),
#              --window "l,t,w,h", --server-ip/--server-port, --no-dig,
#              --observe-after-trigger-s (po triggerze OCR obserwuj sieć+OCR dalej)
```
Ctrl+C zatrzymuje wcześnie — częściowy timeline i tak zapisuje się do CSV.

**Wnioski projektowe z implementacji (przeniesione do kodu):**
1. `_read_timer_value_hhmmss_robust` zwraca tylko `value` — dry-run woła `read_timer_hhmmss_robust` bezpośrednio, żeby logować `confidence`/`method`/`raw_text`.
2. Po triggerze OCR (wartość ≤ spam_threshold z histerezą) pętla NIE wraca od razu (jak realny `_handle_watch_timer`) — domyślnie obserwuje dalej przez `--observe-after-trigger-s` (5 s), żeby złapać beacon/tick0 w czasie względem triggera OCR; `0` = zachowanie jak w produkcji.
3. `_simulate_spam` odtwarza tempo realnego klikania (chunk ~1 s z sleepem), więc zdarzenia sieciowe w trakcie okna spamu lądują w timeline'ie w prawdziwych względnych pozycjach — porównanie `T_beacon − T_ocr` jest miarodajne.
4. Sniffer wstrzykiwany przez `sniffer_factory` (testy) / `on_sniffer_started` (hook po starcie) — testy używają fake'a z callbackami, nie realnego scapy.

**Status:** narzędzie gotowe i przetestowane (8 passed). Do uruchomienia na żywo przez użytkownika; wyniki porównania OCR vs rewardtime oraz `T_beacon − T_ocr` zasilą kalibrację EMA (18.8 pkt 4).
