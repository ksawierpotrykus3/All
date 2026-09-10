# Szczegółowy Przepływ Danych (End-to-End Pipeline) – Kliknięcie Skrzynki do Pakietu TCP

> **Podstawa:** Analiza metadanych IL2CPP (`global-metadata.dat`), pamięci RAM procesu `Survival.exe`, bibliotek `GameAssembly.dll` i `UnityPlayer.dll` oraz zrzutów sieciowych.

---

## 1. Architektura Przepływu Danych (Wizualizacja)

```
[SPRZĘT / STEROWNIK]
  │ (USB 1000Hz / interception.sys)
  ▼
[WARSTWA 1: UnityPlayer.dll (C++)]
  │ ProcessMouseEvent -> PointerInputModule
  │ Sprawdzenie: pixelDragThreshold (1.5 px) -> eligibleForClick
  ▼
[WARSTWA 2: ClickDetector & Anty-Spam C# (GameAssembly.dll)]
  │ ClickDetector: s_DoubleClickTime (300 ms) & clickThreshold (5.0 px)
  │ ClickIntervalMonitor: _threshold (25.0 ms) -> ReportFastClick()
  ▼
[WARSTWA 3: Silnik Raycastingu i Geometrii Mapy]
  │ PhysicsRaycaster (BoxCollider 3D) vs GraphicRaycaster (Canvas UI)
  │ MarchSkinAlliance: kIgnoreRaycastLayer (przenikanie przez wozy)
  ▼
[WARSTWA 4: IL2CPP C# Map Controller]
  │ OnWorldInputPointClick(pointId, hitPoint)
  │ Most: WorldBuildCSharpCallLuaInterface / SetLuaCallback
  ▼
[WARSTWA 5: XLua Scripting Engine]
  │ AllianceArms_OpenBox(pointId, chestUuid)
  │ StopSvAutoToCell() (blokada kamery)
  │ Walidacja stanu gracza i sojuszu (LuaEntry.Player:GetAllianceUid)
  ▼
[WARSTWA 6: Stos Sieciowy Klienta (NetworkManager)]
  │ NetworkManager.SendLuaMessage -> SfsTreeNode / Protobuf / JSON TLV
  │ Serializacja: {"c": "get.treasure.info", "uuid": "...", "_id": seqId}
  │ TcpNoDelay = true -> WSASend (Gniazdo TCP 15.197.67.229:8851)
  ▼
[WARSTWA 7: Serwer Gry (Walidacja, Flagi & Ranking)]
  │ Sprawdzenie T0, sojuszu, puli nagród, unikalności uid i licznika _id
  │ Obliczenie costTime = T_odebrania - T_spawnu
  │ Aktualizacja rankingu: MsgUpdateAllianceArmsRankUI / PlayGetReward
```

---

## 2. Krok po Kroku: Dokładny Łańcuch Wykonania i Warunki Sprawdzane

### KROK 1: Sprzęt $\rightarrow$ Pętla Wejścia Unity (`UnityPlayer.dll`)
1. **Generowanie impulsu:**
   - Sterownik jądra (`interception.sys`) wstrzykuje rekord bajtowy `MouseStroke(state=1)` (DOWN) bezpośrednio do bufora urządzenia.
   - Flaga syntetyczna `LLMHF_INJECTED = 0` (gra traktuje sygnał jako fizyczny mikrostyk myszy USB).
2. **Próbkowanie w silniku Unity:**
   - `UnityPlayer.dll` w metodzie `ProcessMouseEvent` odczytuje stan rejestru myszy w bieżącej klatce renderowania.
   - **Warunek 1 (Czas trzymania DOWN):** Impuls `DOWN` musi trwać co najmniej czas trwania 1 klatki renderowania ($\ge 5.0\text{ ms}$ dla 60 FPS), aby `FramePressState` zarejestrował stan `Pressed`. Zbyt krótki impuls zostaje zignorowany.

---

### KROK 2: Sprawdzenie Przeciągania Kamery i Dwukliku (`GameAssembly.dll`)
1. **Filtr przeciągania (`BitBenderGames.MobileTouchCamera`):**
   - **Warunek 2 (Próg ruchu w trakcie kliku):** $\Delta r = \|\text{CurrentTouchPos} - \text{StartTouchPos}\|$.
   - **Reguła:** Jeśli $\Delta r > \mathbf{1.5\text{ px}}$, silnik aktywuje tryb `Drag` i ustawia:
     ```csharp
     pointerEvent.eligibleForClick = false; // ANULOWANIE KLIKNIĘCIA!
     ```
   - **Wniosek:** Ruch kursora podczas trzymania `DOWN` niszczy kliknięcie i uruchamia przesuwanie terenu mapy.
2. **Filtr wielokliku (`ClickDetector`):**
   - **Warunek 3 (Odstęp dwukliku):** `s_DoubleClickTime = 0.30s (300 ms)` oraz `clickThreshold = 5.0 px`.
   - **Reguła:** Jeśli drugie kliknięcie nastąpi w odległości $< 5.0\text{ px}$ w czasie $< 300\text{ ms}$, Unity rzutuje zdarzenie na `ExecuteDoubleClick` zamiast standardowego `OnPointerClick`.
   - **Rozwiązanie:** Przesunięcie pozycji o $\pm 5\text{ px}$ **w fazie UP (przerwy)** kasuje licznik dwukliku.

---

### KROK 3: Filtr Anty-Spamowy C# (`ClickIntervalMonitor`)
W klasie `ClickIntervalMonitor` bezpośrednio przed przekazaniem zdarzenia do logiki gry sprawdzany jest warunek:
$$\Delta t = T_{\text{now}} - T_{\text{lastClickTime}}$$
- **Warunek 4 (Minimalny interwał czasowy):** $\Delta t \ge \mathbf{\_threshold} = \mathbf{25.0\text{ ms}}$.
- **Skutek niespełnienia ($\Delta t < 25.0\text{ ms}$):**
  - Wywołanie wewnętrznej metody **`ReportFastClick()`**.
  - Ustawienie flagi `_reported = true`.
  - **Całkowita blokada wywołania `SendClickEvent`** (pakiet otwarcia w ogóle nie opuszcza klienta gry!).
- **Maksymalne dozwolone tempo:** $\text{CPS}_{\max} = \frac{1000\text{ ms}}{26.0\text{ ms}} = \mathbf{38.46\text{ CPS}}$.

---

### KROK 4: Raycasting i Detekcja Kolizji 3D
1. **Hierarchia warstw:**
   - Promień kamery `Camera.ScreenPointToRay(mousePos)` bada scenę.
   - Modele pojazdów graczy (`MarchSkinAlliance`) mają warstwę **`kIgnoreRaycastLayer`** – promień przechodzi przez nie na wylot.
   - Bryła skrzynki posiada komponent **`BoxCollider`** o powiększonym zasięgu (`raycastPadding`).
2. **Warunek 5 (Kolizja z interfejsem UI):**
   - Jeśli kursor trafi w element Canvasu UI (tabliczka z nickiem gracza `[MAVE] Abby`, dymek emoji marszu `push.march.emoji`), zdarzenie przejmuje **`GraphicRaycaster`**, blokując fizykę mapy.
   - **Rozwiązanie:** Klikanie w prawy dolny róg bryły skrzynki (**Strefa B**), która jest wolna od napisów UI.

---

### KROK 5: Przejście C# $\rightarrow$ Most XLua $\rightarrow$ Logika Lua
1. **Wywołanie kontrolera mapy:**
   - Silnik C# wywołuje `OnWorldInputPointClick(pointId, worldPos)`.
   - Przez interfejs `WorldBuildCSharpCallLuaInterface` wywoływana jest funkcja Lua:
     ```lua
     AllianceArms_OpenBox(pointId, chestUuid)
     ```
2. **Lokalne weryfikacje w skrypcie Lua:**
   - **Wywołanie `StopSvAutoToCell()`:** Natychmiastowe zamrożenie przesuwania kamery w renderze.
   - **Sprawdzenie 1:** Czy `LuaEntry.Player:GetAllianceUid()` jest zgodne z `allianceId` strefy zrzutu?
   - **Sprawdzenie 2:** Czy gracz nie jest w stanie blokującym (`isPause`, `InBattle`, animacja teleportacji)?
   - **Sprawdzenie 3:** Czy obiekt nie otrzymał wcześniej flagi `push.treasure.remove`?

---

### KROK 6: Konstrukcja i Wysłanie Pakietu TCP (`NetworkManager`)
1. **Metoda `NetworkManager.SendLuaMessage`:**
   - Skrypt przekazuje obiekt do serializatora protokołu (`SfsTreeNode` / Protobuf / TLV).
2. **Kluczowe pola payloadu:**
   ```json
   {
     "c": "get.treasure.info",
     "uuid": "1518644001000751",
     "_id": 142
   }
   ```
   - `_id`: **Monotoniczny licznik zapytań sesji**. Każde zapytanie zwiększa `_id` o $+1$.
3. **Wysłanie na gniazdo TCP:**
   - `NetworkManager.GetTcpNoDelay()` zwraca `true` (opcja gniazda `TCP_NODELAY` wyłącza buforowanie algorytmu Nagle'a).
   - Wywołanie systemowe `WSASend` wysyła surowe bajty natychmiast na IP `15.197.67.229:8851`.

---

## 3. Co Dzieje Się na Serwerze? (Weryfikacja, Flagi i Wyliczanie Rankingu)

Po odebraniu pakietu `get.treasure.info` serwer wykonuje serię testów w wątku zdarzeń:

### A. Sprawdzane Warunki Serwerowe (Walidacja):
1. **Warunek Czasu Spawnu ($T_{\text{serwer}} \ge T_0$):**
   - Jeśli żądanie dotrze przed wygenerowaniem skrzynki w bazie serwera ($T_{\text{odbioru}} < T_0$), serwer odrzuca pakiet z błędem `chest not spawned`.
2. **Warunek Licznika Sekwencji (`_id`):**
   - Jeśli `_id` jest zduplikowane, mniejsze od poprzedniego lub ominięto numer, serwer uznaje sesję za uszkodzoną i **zrywa połączenie TCP**.
3. **Warunek Dostępności Puli Nagród:**
   - Serwer sprawdza licznik pozostałych skrzynek. Jeśli skrzynka została już opróżniona przez szybszych graczy, serwer natychmiast rozsyła `push.treasure.remove` i zwraca odmowę.
4. **Warunek Uprawnień Gracza (`uid` / `allianceId`):**
   - Weryfikacja, czy gracz należy do sojuszu organizującego zrzut oraz czy nie odebrał już nagrody z tego zrzutu (`has_claimed = true`).

---

### B. Obliczanie Pola `cost` i Pozycji w Rankingu:
$$\text{cost} = T_{\text{odebrania get.treasure.info}} - T_{\text{zrzut T0 na serwerze}}$$

Serwer natychmiast odsyła pakiet zatwierdzający z wyliczonym czasem i pozycją:
```json
{
  "c": "treasure.reward.record",
  "uuid": "1518644001000751",
  "cost": 0.091,
  "rank": 1
}
```

Następnie serwer rozsyła do wszystkich graczy pakiet aktualizacji rankingu:
- `push.alliance.reward.new` $\rightarrow$ Klient wywołuje `MsgUpdateAllianceArmsRankUI` i animację `PlayGetReward`.

---

## 4. Co Daje Lepsze vs Gorsze Oceny i Flagi na Serwerze?

| Czynnik | Wpływ na Wynik / Flagi Serwera | Konsekwencja |
| :--- | :--- | :--- |
| **Pakiet w oknie $[T_0 + 80\text{ms}, T_0 + 120\text{ms}]$** | ✅ Naturalny, minimalny czas sieciowy (fizyczny RTT + processing) | **1. Miejsce (`cost = 0.08–0.10s`)**, brak flag anty-cheat |
| **Czas $< 20\text{ ms}$ od $T_0$ przy znanym RTT 60 ms** | ⚠️ Flaga: `Anomalous Pre-Fire / Packet Injection` | Możliwe odrzucenie pakietu przez serwer jako wyprzedzenie |
| **Spam z interwałem $< 25\text{ ms}$** | 🛑 Blokada po stronie klienta: `ClickIntervalMonitor.ReportFastClick` | Pakiet w ogóle nie wychodzi z klienta |
| **Ruch kursora $> 1.5\text{ px}$ w trakcie DOWN** | 🛑 Blokada po stronie klienta: `MobileTouchCameraDragMove` | Anulowanie kliknięcia (`eligibleForClick = false`) |
| **Czekanie na powiadomienie Mail/Beacon** | ❌ Naturalne opóźnienie serwera (+250–300 ms) | **Wynik `cost ≥ 0.40s`**, spadek poza czołowe miejsca |
| **Połączenie kablowe Ethernet zamiast Wi-Fi** | ✅ Obniżenie i stabilizacja RTT o 15–30 ms | Zmniejszenie wartości `cost` o $0.015\text{–}0.030\text{ s}$ |

---

## 5. Podsumowanie Wymogów dla Idealnego Wyzwolenia

Aby uzyskać **1. miejsce (`cost ≈ 0.08s – 0.10s`)**:
1. **Kamera:** Ustawiona sztywno nad punktem zrzutu na Max Zoom Out (brak animacji `DOTweenAnimation`).
2. **Pozycja kursora:** Prawy dolny narożnik bryły skrzynki (**Strefa B** – brak kolizji z Canvasem UI).
3. **Sterownik:** `Interception` (brak flagi syntetycznej `LLMHF_INJECTED`).
4. **Parametry klikania (dla czystej gry 60 FPS):**
   - Interwał cyklu: **$26.0\text{ ms}$** ($38.46\text{ CPS}$ $\rightarrow$ brak wyzwolenia `ClickIntervalMonitor`).
   - Czas trzymania `DOWN`: **$5.0\text{ ms}$** (rejestracja klatki Unity `FramePressState`).
   - Czas przerwy `UP`: **$21.0\text{ ms}$**.
   - Przesunięcie w trakcie uderzenia: **$\Delta r = 0.0\text{ px}$** (brak aktywacji `MobileTouchCamera`).
   - Szum pozycji pomiędzy cyklami: **$\pm 5\text{ px}$ wyłącznie w fazie UP** (unieważnienie `s_DoubleClickTime`).
5. **Punkt startu:** Rozpoczęcie serii kliknięć na **$100\text{ ms}$ przed $T_0$** (uzbrojenie na bazie pakietu marszu `push.world.march.new`).
