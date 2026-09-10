# Rejestr Ukrytych Dławików i Pułapek w Silniku Gry (`Survival.exe` - Last Z)

> **Podstawa:** Analiza metadanych IL2CPP (`global-metadata.dat`), struktur pamięci RAM, modułów sieciowych i pętli Unity.

Oprócz warstwy `TouchInputController` i `ClickIntervalMonitor` w grze zidentyfikowano **7 innych ukrytych mechanizmów** ("niespodzianek") na różnych terminalach i podsystemach, które mogą sztucznie dodawać **100–300 ms opóźnienia**:

---

## 1. Terminal Okna i Fokus: Dławik Klatkażu w Tle (`OnApplicationFocus`)

* **Gdzie w kodzie:** `GameMain.OnApplicationFocus` / `m_RunInBackground` (offset `0x1840C3` i `0xABAE2`).
* **Mechanizm:** 
  - Jeśli okno gry `Survival.exe` nie jest w 100% aktywnym, pierwszym oknem Windowsa (`ForegroundWindow`):
  - Silnik Unity automatycznie włącza tryb oszczędzania energii / tła i **obniża klatkaż z 60 FPS do 15–30 FPS**.
  - Przy 15 FPS jedna klatka trwa **$66.6\text{ ms}$** zamiast $16.6\text{ ms}$!
  - Wtedy kliknięcie musi trwać $> 70\text{ ms}$, a cała pętla przetwarzania wejścia zwalnia **4-krotnie**.
* **Pułapka:** Uruchomienie klikera z innego monitora lub okna konsoli bez natychmiastowego przywrócenia `SetForegroundWindow(hwnd)` natychmiast wrzuca Cię w czas `0.3–0.4s`.

---

## 2. Terminal Sieciowy: Algorytm Nagle'a i Buforowanie TCP (`TCP_NODELAY`)

* **Gdzie w kodzie:** `NetworkManager.GetTcpNoDelay` (offset `0x16F0A7`).
* **Mechanizm:**
  - Pakiet otwarcia skrzynki `get.treasure.info` jest mikroskopijny (**85 bajtów**).
  - Standardowy stos gniazd sieciowych TCP na Windowsie (jeśli nie ma włączonej opcji `TCP_NODELAY`) wstrzymuje wysyłanie małych pakietów do momentu uzbierania pełnego segmentu MTU (1460 bajtów) lub nadejścia potwierdzenia ACK poprzedniego pakietu (tzw. **Delayed ACK Timer = 40–200 ms**).
* **Stan w grze:** `NetworkManager` włącza `TcpNoDelay = true`, ale jeśli połączenie jest pośredniczone przez proxy / VPN / warstwę filtrującą z buforowaniem, pakiet zostaje opóźniony w kolejce gniazda.

---

## 3. Terminal Renderowania: Spike Pamięci i Garbage Collector Unity (`GC Stop-The-World`)

* **Gdzie w kodzie:** `GarbageCollector` / `CollectGarbage begin` (offset `0xABD01`).
* **Mechanizm:**
  - W chwili $T_0 - 100\text{ ms}$ do punktu zrzutu zjeżdża się kilkunastu graczy.
  - Generuje to falę pakietów: `push.world.march.new`, `push.formation.update`, `push.march.emoji`, dymki czatu.
  - Silnik Unity alokuje dziesiątki tymczasowych obiektów C# i struktur XLua.
  - W momencie przekroczenia limitu sterty pamięci, Unity IL2CPP odpala **Garbage Collector**, który zamraża główny wątek gry na **20–50 ms** (tzw. *GC Hitch / Micro-stutter*).
* **Skutek:** Jeśli kliknięcie trafi w moment odpalenia GC, klatka wejścia zostaje opóźniona o czas trwania zrzutu pamięci.

---

## 4. Terminal UI: Niewidzialne Maski Raycastu (`GraphicRaycaster.blockingObjects`)

* **Gdzie w kodzie:** `UnityEngine.UI.GraphicRaycaster` / `EventSystem.RaycastAll`.
* **Mechanizm:**
  - Gdy helikopter ląduje, nad strefą zrzutu pojawiają się:
    - Tabliczki nicków (`[MAVE] Abby`),
    - Emotki marszu (`push.march.emoji`),
    - Paski życia pojazdów (`ShowAllianceCitySoldierBlood`).
  - Każdy z tych elementów w Canvasie posiada niewidzialny prostokąt kolizyjny (`Raycast Target = true`).
  - Unity `EventSystem` sprawdza **najpierw Canvas UI (2D), a dopiero potem obiekty mapy 3D (`PhysicsRaycaster`)**.
  - Jeśli kursor uderzy w strefę objętą przezroczystym polem nicku, kliknięcie zostaje zutylizowane przez UI i **nie trafia w `BoxCollider` skrzynki**.

---

## 5. Terminal Systemowy: Rozdzielczość Zegara Windows (`15.6 ms Tick Resolution`)

* **Gdzie w systemie:** `winmm.dll` / `timeBeginPeriod`.
* **Mechanizm:**
  - Domyślny zegar systemowy Windows (używany przez `time.sleep()`, wątki OS i pętle sterowników) ma dokładność **15.625 ms** (64 Hz).
  - Każde wywołanie `time.sleep(0.005)` na Windowsie bez włączonego zegara precyzyjnego fizycznie czeka **15.6 ms**.
  - Bez wywołania `ctypes.windll.winmm.timeBeginPeriod(1)` synchronizacja z klatkami 60 FPS rozjeżdża się o wielokrotności 15.6 ms.

---

## 6. Terminal XLua: Serializacja i Kolejkowanie Worker Thread (`WorldMsgProcessor`)

* **Gdzie w kodzie:** `WorldMsgProcessor.WorkerThread` / `PbTreeMap` (offset `0x4ED0F`).
* **Mechanizm:**
  - Pakiety sieciowe ze strumienia TCP nie trafiają od razu do silnika graficznego.
  - Odbiera je wątek w tle (`WorkerThread`), deserializuje z formatu Protobuf / SFS (`SfsTreeNode`), wrzuca do kolejki `PbTreeMap`, a dopiero pętla `Update()` głównego wątku w kolejnej klatce przekazuje dane do XLua.
  - Jeśli wątek główny ma wysokie obciążenie (dużo obiektów na ekranie), przejście z `WorkerThread` do `XLua` zajmuje **1-2 klatki (16–33 ms)**.

---

## 7. Terminal Bezpieczeństwa: Licznik Sekwencji `_id` i Walidacja Uprawnień

* **Gdzie w kodzie:** `NetworkManager._id` / `GetSessionToken`.
* **Mechanizm:**
  - Każde zapytanie wychodzące z klienta posiada ściśle sprawdzany licznik sekwencji `_id`.
  - Jeśli skrypt zewnętrzny wyśle surowy pakiet z pominięciem kolejki gry:
    - Serwer wykrywa desynchronizację licznika `_id` $\rightarrow$ natychmiast cicho ignoruje pakiet lub zrywa sesję TCP.
    - Wszelkie zapytania muszą przechodzić przez legalny łańcuch wywołań w grze lub idealnie synchronizować stan licznika `_id`.
