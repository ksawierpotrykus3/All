> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Ukryte Przyczyny Zlych Czasow Cost: Analiza Porownawcza Wszystkich Nagranych Sesji i PCAPow

> **Katalog docelowy:** `f:\Last Z\docs`  
> **Data opracowania:** 17 sierpnia 2026 r.  
> **Przebadany material dowodowy:** 28 sesji PCAPNG (`helikopter1` - `helikopter28`) oraz logi wykonawcze bota (`log_helikopter14`, `log_helikoper20`, `log_helikopter22`, `log_helikopter25`)

---

## 1. Glowna Przyczyna Problemow: Falszywy Trigger i Mylenie Stanu Lotu ze Spawnem

Porownanie logow bota z fizycznymi pakietami sieciowymi w `pcaps/` ujawnia **dwie fundamentalne pulapki czasowe**:

### 🛑 Pulapka A: Mylenie `status=1` (Helikopter w Locie) ze Spawnem Skrzynki
W `log_helikopter22_miejsce4_0.292s.log`:
```
02:05:20,271 Beacon detected (march.new): size=953B, ownerUid=1461030734000751, status=1
02:05:20,272 dig spam start: first click @ t+0.0ms ... duration=2.0s
02:05:22,262 dig spam done: 46 clicks delivered over 2.0s
02:05:22,264 Beacon detected (push.mail reward): size=593B
02:05:22,265 dig spam start (drugi spam) -> wynik cost = 0.292s
```

#### Co wydarzylo sie w rzeczywistosci na osi czasu?
1. Pakiet `push.world.march.new` ze **`status=1`** to pakiet synchronizacji marszu helikoptera, ktory **LECI JESZCZE W POWIETRZU** i dotrze do celu dopiero za **`1.992 sekundy`** (wskazane w polu `endTime`).
2. Bot uznal ten pakiet za "zrzut" i **klikal w pusta ziemie przez 2.0 sekundy** (od `02:05:20.272` do `02:05:22.262`).
3. O `02:05:22.262` bot **ZAKONCZYL KLIKANIE** (`dig spam done`).
4. Dokladnie **2 milisekundy pozniej (`02:05:22.264`) skrzynka FIZYCZNIE SPADLA NA ZIEMIE!**
5. W chwili zrzutu bot NIE KLIKAL. Zostal obudzony dopiero przez pakiet `push.mail`, przez co jego reakcja byla spozniona o **`+292 ms`**!

---

### 🛑 Pulapka B: Jitter OCR Timera w `watch_timer` (Przypadek `helikopter20`)
W `log_helikoper20_5miejsce_0.495s.log`:
1. OCR Tesseract/EasyOCR odczytal `00:00:05` (5 sekund).
2. Bot wszedl w faze `spam` z parametrem `duration=2.0s` o godzinie `12:59:14.096`.
3. Bot wyklikal 47 uderzen i zatrzymal sie o `12:59:16.096`.
4. Skrzynka wyladowala na serwerze dopiero o **`12:59:18.752`** (**2.65 sekundy PO ZAKONCZENIU SPAMU**).
5. Bot trafil w skrzynke dopiero spoznionym, przypadkowym kliknieciem o `12:59:19.249`, notujac czas **`cost = 0.495s` (5. miejsce)**.

---

## 2. Prawdziwa Anatomia Pakietow Sieciowych Marszu i Spawnu

| Pakiet | Pole Kluczowe | Znaczenie w Silniku Gry | Czy Klikać? |
| :--- | :--- | :--- | :---: |
| `push.world.march.new` | `status = 1`, `endTime = T_future` | Helikopter jest w locie. Lądowanie nastąpi w chwili `endTime`. | ❌ **NIE! (Pusta ziemia)** |
| `push.world.march.new` | `diffPoint = "0;-2"` | Wskazuje przesunięcie kafelka zrzutu względem bazy. | 🎯 Ustaw kamerę / kursor |
| `push.world.point.update` | `type = "change" / "create"`, `points` | **FIZYCZNY ZAPIS OBIEKTU W RAM (T0)**. BoxCollider aktywowany! | 🚀 **TAK! (NATYCHMIAST)** |
| `push.dig.treasure.reward` | `uid`, `name`, `point` | Potwierdzenie odebrania nagrody przez pierwszego gracza. | ⚠️ Już po T0 |
| `push.mail` | `dialog: {"id": "897957"}` | Tekstowe powiadomienie UI (spóźnione o 250-300 ms). | ❌ Za późno na Top 1 |

---

## 3. Dokładna Recepta na Osiągnięcie Czasów Poniżej 0.05s

1. **Obliczanie $T_0$ z Pola `endTime`:**
   Nie wolno uruchamiać klikera w momencie odebrania pakietu `status=1`. Należy odczytać pole `endTime` z pakietu `push.world.march.new` i zsynchronizować start uderzeń na **$T_{\text{start}} = \text{endTime} - 50\text{ ms}$**.
2. **Alternatywny, Bezbłędny Trigger Sieciowy:**
   Wyzwolenie klikera na pakiet `push.world.point.update` (rozmiar 227-248 B, zawierający pole `change points` / `pointId`).
3. **Czas Trwania Spamu (`duration`):**
   Parametr `duration` musi wynosić minimum **`4.0 – 5.0s`** (a nie 2.0s), aby pokryć ewentualny jitter zegara serwera i zapewnić ciągłość klikania w chwili fizycznego pojawienia się `BoxCollidera`.
