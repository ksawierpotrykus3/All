# INDEKS PLIKÓW ANALITYCZNYCH — CZYTAJ ZANIM UŻYJESZ

Ten folder zawiera analizy inżynierii wstecznej gry (event helikoptera). Pliki NIE są w pełni spójne — zawierają sprzeczne parametry. Poniżej co jest pewne, a co kwestionowane.

## NAJWAŻNIEJSZE SPRZECZNOŚCI (zweryfikuj zanim użyjesz parametru)

### 1. Hold DOWN (czas trzymania przycisku myszy, 60 FPS)
| Plik | Wartość |
|---|---|
| full_event_analysis_knowledge5.md | 18.0 ms |
| szczegolowy_przeplyw_danych_klikania.md | 5.0 ms |
| weryfikacja_kodu_gry.md | 5.0–6.0 ms |
| nowe_odkrycia_i_waskie_gardla_eventu_helikoptera.md | 20.0–22.0 ms |
| dlaczego_klik_po_pakiecie_marnuje_uderzenie_race_condition.md | 20.0 ms |

**Wniosek:** brak konsensusu. knowledge5 twierdzi "gra nie rejestruje kliknięć krótszych niż ~16 ms", co kłóci się z wartościami 5-6 ms. Wartości 5-6 ms są wewnętrznie nielogiczne (weryfikacja_kodu_gry sama pisze "wymaga pełnej klatki 16.6 ms"). **Najbardziej wiarygodny zakres: 18-22 ms.**

### 2. Maksymalny CPS (kliknięć na sekundę)
| Plik | Wartość |
|---|---|
| full_event_analysis_knowledge5.md | 38.0 CPS (okres 26.32 ms) |
| szczegolowy_przeplyw_danych_klikania.md | 38.46 CPS (okres 26.0 ms) |
| weryfikacja_kodu_gry.md | 38.46 CPS |
| nowe_odkrycia | 38.46 CPS |

**Wniosek:** próg ClickIntervalMonitor = 25.0 ms (pewne). Wartość 38.46 CPS (okres 26.0 ms) występuje w 3 plikach — traktuj jako poprawniejszą niż 38.0 CPS.

### 3. Nazwa komendy RPC otwarcia skrzynki
| Plik | Komenda |
|---|---|
| pelne_odkrycie_struktury_pakietow_i_rpc_skrzynki.md | get.dig.treasure.reward |
| full_event_analysis_knowledge5.md | get.treasure.info |
| szczegolowy_przeplyw_danych_klikania.md | get.treasure.info |
| renderowanie_vs_pakiet_sieciowy_tajemnica_top1.md | get.treasure.info |

**Wniosek:** NIE rozstrzygnięte. Możliwe, że to dwie różne komendy (info vs reward) lub zmiana nazwy między sesjami. `pelne_odkrycie` deklaruje "prawdziwa nazwa to get.dig.treasure.reward" — zweryfikuj w pcapach zanim użyjesz.

### 4. RTT sieciowy
| Plik | Wartość |
|---|---|
| renderowanie_vs_pakiet_sieciowy_tajemnica_top1.md | 5.47 ms (wysoce podejrzane) |
| full_event_analysis_knowledge5.md | RTT 70–90 ms |
| nowe_odkrycia | ping 35–50 ms |

**Wniosek:** 5.47 ms jest niemal na pewno błędne (sugeruje localhost). Realny RTT ~70-90 ms.

### 5. Trigger spawnu helikoptera
| Plik | Twierdzenie |
|---|---|
| weryfikacja_kodu_gry.md | push.world.march.new (258 ms wyprzedzenie) |
| ukryte_przyczyny_zlych_czasow_analiza_wszystkich_pcapow.md | march.new status=1 to HELIKOPTER W LOCIE, NIE spawn — klikanie na to to "pusta ziemia" |

**Wniosek:** weryfikacja_kodu_gry jest tutaj BŁĘDNA. Poprawny trigger to push.world.point.update (skrzynka w RAM), nie march.new status=1.

---

## OCENA POSZCZEGÓLNYCH PLIKÓW

### WYSOKA WIARYGODNOŚĆ (używaj pewnie)
- **diagnoza_spam_click_unity_i_autoklikery.md** — kompleksowa diagnoza i wdrożone Podejście B (wrzesień 2026): konflikt MobileTouchCamera (1.5px) vs ClickDetector (5.0px/300ms), 40/60 split, optymalizacja CPU (>80% mniej spinlocka) oraz weryfikacja UIPI (Error 5).
- **pelne_odkrycie_struktury_pakietow_i_rpc_skrzynki.md** — nazwy komend RPC, kody błędów (5560006 = limit nagród wyczerpany). Pewne: komenda otwarcia wysyła dwa zapytania.

- **ukryte_przyczyny_zlych_czasow_analiza_wszystkich_pcapow.md** — diagnoza realnych błędów bota z logów. Pewne: status=1 to lot, nie spawn; bot klikał w pustą ziemię.
- **dlaczego_klik_po_pakiecie_marnuje_uderzenie_race_condition.md** — wyścig czasowy mysz vs BoxCollider. Pewne: kliknięcie opiera się na Physics.Raycast, pierwsze kliknięcie trafia w pusty grunt.

### ŚREDNIA WIARYGODNOŚĆ (sprawdzaj parametry)
- **full_event_analysis_knowledge5.md** — master-rejestr, dobra architektura, ale hold 18ms i CPS 38.0 kwestionowane.
- **szczegolowy_przeplyw_danych_klikania.md** — dobry pipeline end-to-end, ale hold 5ms jest błędny.
- **nowe_odkrycia_i_waskie_gardla_eventu_helikoptera.md** — dobre odkrycia strukturalne (izometria 45°, async), ale hold 20-22ms i ping rozbieżne.
- **ukryte_mechanizmy_i_dlawiki_w_grze.md** — dobre mechanizmy (fokus, GC, Nagle), ale 85 bajtów i 33ms niezweryfikowane.

### NISKA WIARYGODNOŚĆ (uważaj)
- **renderowanie_vs_pakiet_sieciowy_tajemnica_top1.md** — koncepcja (serwer nie widzi renderu) OK, ale RTT 5.47ms błędne.
- **weryfikacja_kodu_gry.md** — dobra weryfikacja symboli IL2CPP (38/38), ale czasy DOWN 5-6ms i trigger march.new są błędne.
- **01_raport_wejscie_i_siec.txt** — ogólny raport o API wejścia Windows, bez danych specyficznych dla gry.

---

## CO JEST PEWNE (można polegać bez weryfikacji)
- Serwer gry: `15.197.67.229:8851` (TCP + HTTPS/Cloudflare)
- Silnik: Unity 64-bit IL2CPP + XLua
- ClickIntervalMonitor próg = 25.0 ms
- ClickDetector double-click = 300 ms, threshold ≈ 5.0 px
- MobileTouchCamera thresholdRelative ≈ 1.5 px (ruch > 1.5px anuluje kliknięcie)
- TCP_NODELAY = true, GetUseAsyncTcp = true
- Skrzynka pojawia się w RAM w push.world.point.update
- Serwer liczy cost = T_odebrania - T_zrzutu
- Kod błędu 5560006 = limit nagród wyczerpany
- FCFS: tylko pierwszy dostaje nagrodę (obalona teoria "top 10 nagród")