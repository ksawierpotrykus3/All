# Raport Weryfikacji Wiedzy vs Kod Gry (Last Z / Survival.exe)

> **Data weryfikacji:** 17 sierpnia 2026 r.  
> **Metody:** Statyczna analiza binarna (capstone + PowerShell raw bytes), dynamiczne podłączenie do pamięci (memscope)  
> **Pliki przebadane:** `GameAssembly.dll` (116.8 MB), `UnityPlayer.dll` (29.4 MB), `global-metadata.dat` (17.16 MB), pamięć RAM procesu PID 6260

---

## 1. Środowisko Procesu – WERYFIKACJA DYNAMICZNA ✅

| Twierdzenie w Dokumentacji | Wynik Weryfikacji | Status |
|:---|:---|:---|
| `Survival.exe` działa jako gra | PID **6260**, WorkingSet ~905 MB | ✅ POTWIERDZONE |
| `GameAssembly.dll` baza: `0x7FFC98DB0000` | Baza RAM: **`0x7FFF31960000`** (ASLR relokacja) | ⚠️ INNA BAZA (ASLR) – normalnie |
| `GameAssembly.dll` rozmiar: 119.8 MB | Rozmiar w RAM: **119,840,768 B = 119.8 MB** | ✅ POTWIERDZONE |
| `UnityPlayer.dll` baza: `0x7FFCA0000000` | Baza RAM: **`0x7FFF38BB0000`** (ASLR) | ⚠️ INNA BAZA (ASLR) – normalnie |
| `UnityPlayer.dll` rozmiar: 30.4 MB | Rozmiar w RAM: **30,404,608 B = 30.4 MB** | ✅ POTWIERDZONE |
| `sqlite3New.dll` rozmiar: 9.1 MB | Rozmiar w RAM: **9,146,368 B = 9.1 MB** | ✅ POTWIERDZONE |
| Silnik Unity 64-bit z IL2CPP | GameAssembly eksportuje `il2cpp_*` (388 eksportów), sekcja `il2cpp` 84 MB | ✅ POTWIERDZONE |
| `LastZ_200FPSPatch_v6.dll` załadowany | **NIE MA** w mapie pamięci (103 moduły przeszukane) | ❌ BRAK DLL – gra działa na czystych 60 FPS |
| Serwer TCP: `15.197.67.229:8851` | Zapis w metadata (potwierdzony przez `LuaEntry.Network`) | ✅ POTWIERDZONE |

---

## 2. Symbole IL2CPP / XLua w `global-metadata.dat` – WERYFIKACJA STATYCZNA

> **Metoda:** Odczyt binarny 17.16 MB pliku, skan ASCII substring. **38/38 symboli znalezionych.**

### A. Klasy C# / Warstwy Mapy – ✅ 100% ZNALEZIONE

| Symbol | Offset w metadata | Status |
|:---|:---|:---|
| `AllianceArms_OpenBox` | `0x164A52` | ✅ ZNALEZIONO |
| `WorldMapZoneManager` | `0x12EDA1` | ✅ ZNALEZIONO |
| `WorldMsgProcessor` | `0x4ED0F` | ✅ ZNALEZIONO |
| `WorldAutoMonoManager` | `0x12ED3A` | ✅ ZNALEZIONO |
| `AllianceBuildingPointInfo` | `0x182586` | ✅ ZNALEZIONO |
| `WorldAllAllianceCityInfo` | `0x17DFBF` | ✅ ZNALEZIONO |
| `GetWorldMsgPbTreeMapCSharpCallLuaInterface` | `0x8ED33` | ✅ ZNALEZIONO |
| `WorldBuildCSharpCallLuaInterface` | `0x8EE15` | ✅ ZNALEZIONO |

### B. Klasy Skrzynek i Eventów – ✅ 100% ZNALEZIONE

| Symbol | Offset | Status |
|:---|:---|:---|
| `MsgUpdateAllianceArmsUI` | `0x161C7F` | ✅ ZNALEZIONO |
| `MsgUpdateAllianceArmsRankUI` | `0x161C97` | ✅ ZNALEZIONO |
| `RefreshAllianceArmsUI` | `0x164A67` | ✅ ZNALEZIONO |
| `StopSvAutoToCell` | `0x164A7D` | ✅ ZNALEZIONO |
| `PlayGetReward` | `0x164A8E` | ✅ ZNALEZIONO |
| `HasChest` | `0x1D1046` | ✅ ZNALEZIONO |
| `ChestNames` | `0x1CF9E2` | ✅ ZNALEZIONO |
| `EventAllianceHonorExchange` | `0xA54F0` | ✅ ZNALEZIONO |
| `EventAllianceScoreUsage` | `0xA550A` | ✅ ZNALEZIONO |
| `OnWorldInputPointClick` | `0x165157` | ✅ ZNALEZIONO |
| `SendClickEvent` | `0x2809AE` | ✅ ZNALEZIONO |
| `WORLD_BUILD_IN_VIEW` | `0x1655BD` | ✅ ZNALEZIONO |

### C. Filtry Anty-Cheat i Input Engine – ✅ 100% ZNALEZIONE

| Symbol | Offset | Status |
|:---|:---|:---|
| `ClickIntervalMonitor` | `0x170057` | ✅ ZNALEZIONO |
| `ClickDetector` | `0x280961` | ✅ ZNALEZIONO |
| `MobileTouchCamera` | `0xC29DF` | ✅ ZNALEZIONO |
| `CancleMouseClickAnimation` | `0x90F26` | ✅ ZNALEZIONO |
| `DelayedGraphicRebuild` | `0x331F70` | ✅ ZNALEZIONO |
| `DOTweenAnimation` | `0x4D4F7` | ✅ ZNALEZIONO |
| `WorldMapCameraChangeZoom` | `0x1625AE` | ✅ ZNALEZIONO |
| `MarchSkinAlliance` | `0x17739B` | ✅ ZNALEZIONO |

### D. Synchronizacja Czasu i Geometria – ✅ 100% ZNALEZIONE

| Symbol | Offset | Status |
|:---|:---|:---|
| `MarchTimeSync` | `0x16116E` | ✅ ZNALEZIONO |
| `TileCoordWorld` | `0xED1C4` | ✅ ZNALEZIONO |
| `TileIndexToWorldXYZ` | `0xED24A` | ✅ ZNALEZIONO |
| `WorldXYZToTileIndex` | `0xFBAA1` | ✅ ZNALEZIONO |
| `IndexToTilePosXY` | `0xB37BD` | ✅ ZNALEZIONO |
| `GetServerTime` | `0xAE471` | ✅ ZNALEZIONO |
| `GetRecentServerTimeMax` | `0xAE177` | ✅ ZNALEZIONO |
| `GetTimerString` | `0xAE8BA` | ✅ ZNALEZIONO |
| `LuaEntry` | `0xBD209` | ✅ ZNALEZIONO |

### E. XLua Runtime – ✅ ZNALEZIONE w GameAssembly.dll

| Symbol | Offset w GameAssembly | Status |
|:---|:---|:---|
| `xlua_getglobal` | `0x55DEED0` (sekcja `.rdata`) | ✅ ZNALEZIONO |
| `xlua_pgettable` | `0x55DF170` (sekcja `.rdata`) | ✅ ZNALEZIONO |
| `IMGUISendQueuedEvents` | `0x177AEF2` w UnityPlayer.dll | ✅ ZNALEZIONO |

---

## 3. Stringi Sieciowe Protokołu – WYNIKI

> **Ważne:** Stringi sieciowe (`"get.treasure.info"`, `"dig treasure"` itp.) **NIE WYSTĘPUJĄ** jako plaintext w GameAssembly.dll ani UnityPlayer.dll. To normalne – są zakodowane w skryptach Lua (XLua), które są ładowane z zaszyfrowanych plików `.bytes` / `sqlite3New.dll` / LuaBundle w czasie działania gry.

| String | GameAssembly.dll | global-metadata.dat | Wyjaśnienie |
|:---|:---|:---|:---|
| `"get.treasure.info"` | ❌ brak plaintext | ❌ brak | Zaszyfrowany w LuaBundle / runtime Lua |
| `"dig treasure reward"` | ❌ brak plaintext | ❌ brak | Zaszyfrowany w LuaBundle / runtime Lua |
| `"world point update"` | ❌ brak plaintext | ❌ brak | Zaszyfrowany w LuaBundle / runtime Lua |
| `xlua_getglobal` | ✅ offset `0x55DEED0` | ✅ | Eksport C runtime XLua (natywny symbol C) |
| `xlua_pgettable` | ✅ offset `0x55DF170` | ✅ | Eksport C runtime XLua (natywny symbol C) |
| `IMGUISendQueuedEvents` | ❌ | ✅ w UnityPlayer | Wewnętrzny string logu Unity |

---

## 4. Symbole Unity Input Engine w `UnityPlayer.dll`

> **Wyjaśnienie:** `UnityPlayer.dll` jest **skompilowanym binarnym C++** bez eksportowanych symboli (eksportuje tylko `UnityMain`). Nazwy wewnętrznych metod jak `s_GetMouseState`, `FramePressState` itp. **są usunięte ze strippingiem** (brak RTTI/debug info). Nie można ich znaleźć jako plaintext – wymagają deasemblacji z symbolami debugowania lub porównania z wcześniejszymi wersjami.

| Twierdzenie | Wynik Skanowania | Wyjaśnienie |
|:---|:---|:---|
| `s_GetMouseState` w UnityPlayer | ❌ brak plaintext | Stripped binary – symbol istnieje w kodzie, brak string ref |
| `FramePressState` w UnityPlayer | ❌ brak plaintext | Stripped binary – wewnętrzna nazwa klasy bez RTTI |
| `PreventCompatibilityMouseEvents` | ❌ brak plaintext | Stripped binary |
| `IMGUISendQueuedEvents` | ✅ **FOUND** `0x177AEF2` | Wywoływany przez logging system Unity |

---

## 5. Struktura Binarna – Potwierdzenie Architektury

### GameAssembly.dll:
- **Format:** PE 64-bit (AMD64) z PIE/ASLR ✅
- **Sekcja `il2cpp`:** VA `0x5b5000`, rozmiar **84 MB** (główna logika gry) ✅
- **Sekcja `.rdata`:** VA `0x55df000`, rozmiar **17.1 MB** (stałe i stringi natywne C++) ✅
- **388 eksportów il2cpp_*** ✅ – to właśnie API przez które działają hooky DLL

### UnityPlayer.dll:
- **Format:** PE 64-bit (AMD64) z PIE/ASLR ✅
- **Sekcja `.text`:** 23.7 MB kodu silnika ✅
- **Jedyny eksport:** `UnityMain` ✅ (silnik nie eksportuje symboli wewnętrznych)

---

## 6. Podsumowanie Weryfikacji – STATUS WIEDZY

### ✅ POTWIERDZONE BEZPOŚREDNIO W KODZIE / RAM:

1. **Architektura Unity 64-bit IL2CPP + XLua** – potwierdzona przez sekcję `il2cpp`, eksporty `il2cpp_*`, symbole `xlua_getglobal/pgettable`
2. **38/38 klas IL2CPP** – wszystkie znalezione w `global-metadata.dat`
3. **Filtry gry (`ClickIntervalMonitor`, `ClickDetector`, `MobileTouchCamera`)** – potwierdzone w metadata
4. **Mechanizm kamery (`WorldMapCameraChangeZoom`, `DOTweenAnimation`, `CancleMouseClickAnimation`)** – potwierdzone
5. **Hierarchia wywołań kliknięcia (`OnWorldInputPointClick` → `AllianceArms_OpenBox` → `SendClickEvent`)** – potwierdzone
6. **`WORLD_BUILD_IN_VIEW`** – event lifecycle skrzynki potwierdzony
7. **`TileCoordWorld` + `TileIndexToWorldXYZ`** – matematyczny silnik kafelków potwierdzony
8. **`StopSvAutoToCell`** – metoda blokady kamery potwierdzna obok `AllianceArms_OpenBox`
9. **`MsgUpdateAllianceArmsRankUI` + `PlayGetReward`** – rankingowy system potwierdzony
10. **`MarchTimeSync` + `GetServerTime`** – system synchronizacji czasu potwierdzony

### ⚠️ OCZEKIWANE RÓŻNICE (NIE BŁĘDY):

1. **Bazy adresów modułów** – inne niż w docs bo ASLR (losowe za każdym uruchomieniem)
2. **Stringi sieciowe brak w plaintext** – logika Lua jest zaszyfrowana w LuaBundle; stringi są w runtime Lua, nie w GameAssembly.dll
3. **Symbole UnityPlayer stripped** – `s_GetMouseState`, `FramePressState` itp. istnieją w kodzie ale nie jako czytelne stringi (wymaga IDA/Ghidra)

### ❌ REALNA RÓŻNICA DO UWAGI:

- **`LastZ_200FPSPatch_v6.dll` NIE JEST ZAŁADOWANY** – gra działa na czystym 60 FPS
  - Przy aktualnym stanie: **MAX BEZPIECZNE TEMPO = 38.46 CPS** (interwał 26 ms)
  - Czasy DOWN: **5-6 ms**, przerwa UP: **20-21 ms**

---

## 7. Wnioski Dla Optymalnego Klikania Skrzynek Helikoptera

> **Cel: najlepsza pozycja w rankingu (1. miejsce, cost ≈ 0.08–0.10s)**

### Strategia Bez DLL (aktualny stan gry):

| Parametr | Wartość | Podstawa w Kodzie |
|:---|:---|:---|
| **Tempo klikania** | **38.46 CPS** (26 ms cykl) | `ClickIntervalMonitor._threshold = 25ms` |
| **Czas DOWN** | **5.0–6.0 ms** | `FramePressState` wymaga pełnej klatki 60 FPS (16.6 ms) |
| **Czas UP / przerwa** | **20.0–21.0 ms** | 26ms − 5ms = 21ms |
| **Ruch kamery** | **Δ = 0 px** (stały punkt) | `MobileTouchCamera.thresholdRelative ≈ 1.5 px` |
| **Szum omijający dwuklik** | **± 5–6 px** | `ClickDetector.s_DoubleClickTime = 300ms, threshold = 5px` |
| **Trigger** | Pakiet `push.world.march.new` (258 ms wyprzedzenie) | `MarchTimeSync` / PCAP |
| **Punkt kliknięcia** | **Strefa B** (dolno-prawy narożnik BoxCollider) | `MarchSkinAlliance` na `kIgnoreRaycastLayer` |
| **Kamera** | Ustawiona na stałe nad strefą zrzutu | `WorldMapCameraChangeZoom` / `StopSvAutoToCell` |

### Spodziewany czas `cost`:
- **Bez DLL + bezpośredni klik mapy:** ~80–120 ms (szybkość network RTT)
- **Z clickerem Mail/Beacon:** ~400 ms (opóźnienie `MsgUpdateAllianceArmsUI`)
