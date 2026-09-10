# Dlaczego Kliknięcie Myszki Natychmiast po Pakiecie point.update Trafia w Próżnię?

> **Katalog docelowy:** `f:\Last Z\docs`  
> **Data opracowania:** 17 sierpnia 2026 r.  
> **Zjawisko:** Wyścig Czasowy (Race Condition) pomiędzy Zewnętrznym Snifferem a Wątkiem Głównym Unity

---

## 1. Wyścig Czasowy: Mysz vs Inicjalizacja BoxCollidera w Unity

Gdy Twój zewnętrzny bot odbiera pakiet `push.world.point.update` i natychmiast wysyła kliknięcie myszą, zachodzi następująca **kolizja czasowa**:

```
CZAS       ZEWNĘTRZNY BOT / MYSZ                  WEWNĄTRZ PROCESU SURVIVAL.EXE (UNITY)
─────────────────────────────────────────────────────────────────────────────────────────────
T = 0.0ms  Sniffer PCAP wykrywa pakiet            Pakiet wpada do bufora TCP recv() w WS2_32
           'push.world.point.update'
           
T = 0.5ms  Bot wykonuje SendInput (Mysz)          Wątek główny Unity renderuje poprzednią klatkę.
           Komunikat WM_LBUTTONDOWN w kolejce     Pakiet point.update CZEKA w kolejce sieciowej!
           
T = 2.0ms  Unity odpytuje Input.GetMouseButton    Unity wykonuje Physics.Raycast myszy.
                                                  ⚠️ SKRZYNKA JESZCZE NIE ISTNIEJE W PHYSX!
                                                  Raycast trafia w PUSTY GRUNT (OnBgClick)!
                                                  ❌ PIERWSZE KLIKNIĘCIE ZMARNOWANE!
                                                  
T = 16.6ms (Kolejna klatka)                       Unity w końcu parsuje point.update,
                                                  alokuje prefab i wstawia BoxCollider do PhysX!
                                                  Dopiero TERAZ skrzynka istnieje fizycznie.
                                                  
T = 37.0ms (Drugie kliknięcie bota)               Drugie kliknięcie trafia w BoxCollider, ALE
                                                  ClickDetector wchodzi w stan MultiClick (300ms)!
                                                  
T = 290ms  Wylot pakietu get.treasure.info        Wynik: cost = 0.292s (4. miejsce).
```

---

## 2. Dlaczego Myszka NIE MOŻE Działać Przed Wyrenderowaniem?

1. **Zasada Działania Kliknięcia 3D w Unity:**
   Kliknięcie myszą w grze 3D opiera się na **`Physics.Raycast`**.
   Promień rzucany z kamery przez piksel kursora sprawdza przecięcie z trójwymiarową bryłą kolizyjną (`BoxCollider`).
2. **Fizyczny Brak Obiektu w Klatce $T_0$:**
   W momencie, gdy Twój sniffer widzi pakiet na karcie sieciowej, silnik gry **nie zdążył jeszcze wykonać metody `Instantiate()` ani aktywować `BoxCollidera`**.
   Dlatego kliknięcie wysłane w ułamku $0.5\text{ ms}$ po pakiecie trafia w pustą ziemię!

---

## 3. Jak Rozwiązać Ten Problem i Osiągnąć Top 1?

Istnieją dwa sposoby na pokonanie tego opóźnienia:

### Rozwiązanie 1: Prawidłowy Offset Opóźnienia dla Myszki (Frame Delay)
Zamiast klikać w $T+0.5\text{ ms}$ po pakiecie (co marnuje klik na pusty grunt), należy wprowadzić celowe mikro-opóźnienie na czas inicjalizacji PhysX:
$$\mathbf{T}_{\text{click}} = \mathbf{T}_{\text{packet}} + \mathbf{18.0\text{ ms}}$$
Z czasem trzymania **`HOLD = 20.0 ms`**. Wtedy pierwsze kliknięcie trafi idealnie w nowo narodzony `BoxCollider` w 1. klatce po jego utworzeniu!

### Rozwiązanie 2: Ominięcie Myszki przez Pakiet Sieciowy (Direct Packet / Proxy)
Pakiet `get.treasure.info` wysłany przez sieć/proxy **nie korzysta z Raycastu ani BoxCollidera**. Serwer przyjmuje go natychmiast, bez czekania na alokację prefabu w silniku Unity.
