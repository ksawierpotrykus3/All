# Pełne Odkrycie Struktury Pakietów RPC i Mechanizmu Otwarcia Skrzynki w Last Z

> **Katalog docelowy:** `f:\Last Z\docs`  
> **Data opracowania:** 17 sierpnia 2026 r.  
> **Źródło:** Ekstrakcja surowych struktur binarnych RPC ze wszystkich 28 zrzutów PCAPNG

---

## 1. Prawdziwa Nazwa Komendy Otwarcia Skrzynki: `get.dig.treasure.reward`

W toku dekompozycji strumienia binarnego ustalono, że klient wysyła do serwera dokładnie **dwa zapytania RPC**:

```
+───────────────────────────────────────────────────────────────────────────────────+
| 1. Zapytanie Wstępne: 'world.get.detail.new'                                      |
|    • Pobiera szczegóły kafelka, na który spada helikopter                         |
|    • Pola: _id, worldId, serverId, point                                          |
+───────────────────────────────────────────────────────────────────────────────────+
                                          │
                                          ▼
+───────────────────────────────────────────────────────────────────────────────────+
| 2. Prawdziwe Zapytanie Otwarcia: 'get.dig.treasure.reward'                        |
|    • Główne żądanie pobrania nagrody ze skrzynki                                  |
|    • Pola wysyłane przez klienta:                                                 |
|      - 'c': "get.dig.treasure.reward"                                             |
|      - '_id': Numer sekwencyjny zapytania                                         |
|      - '_time': Timestamp klienta                                                 |
|      - '_ht': Licznik heartbeat                                                   |
|      - 'uuid' / 'point': Identyfikator skrzynki / współrzędne                     |
+───────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Odpowiedzi Serwera i Kody Zwrotne

1. **Sukces (Zajęcie slotu 1–10):**
   - Serwer zwraca do klienta: `{"success": 1, "_id": ..., "reward": [...]}`
   - Serwer natychmiast rozgłasza do wszystkich graczy w strefie pakiet:  
     `push.dig.treasure.reward` z danymi zwycięzcy (`uid`, `name`, `abbr`, `point`, `headSkinId`).
2. **Porażka (Spóźnienie / Skrzynka opróżniona):**
   - Serwer zwraca: **`{"errorCode": "5560006"}`** (`5560006` = Limit nagród wyczerpany / brak wolnych slotów).
3. **Koniec Eventu:**
   - Serwer rozsyła: `push.treasure.remove` i usuwa kafelek ze świata gry.

---

## 3. Kluczowe Wnioski dla Osiągnięcia 1. Miejsca

- Zapytanie **`get.dig.treasure.reward`** to jedyny pakiet decydujący o przydziale nagrody.
- Każdy pakiet niesie pole **`_time`** oraz **`_id`**.
- Zwycięzcy z czołówki (`KiriGami2`, `LiZeeeeee`, `SeanSG`) wysyłają `get.dig.treasure.reward` w ułamku milisekundy po zrzucie, rezerwując pierwsze 3 sloty z czasem $< 0.05\text{ s}$!
