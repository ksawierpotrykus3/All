# 01 — Diagnoza: fakty z dowodami (mechanika)

## 1. Przepływ wysyłki
1. [engine.run_pipeline](file:///c:/Users/buchh/projects/useme/engine.py#L32)
2. kategorie [config.py:41](file:///c:/Users/buchh/projects/useme/config.py#L41)
3. dedup [engine.py:120](file:///c:/Users/buchh/projects/useme/engine.py#L120)
4. detale [engine.py:149](file:///c:/Users/buchh/projects/useme/engine.py#L149)
5. AI1 [ai_pipeline.py:140](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L140)
6. AI2 [ai_pipeline.py:231](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L231) → [chain_executor.py:370](file:///c:/Users/buchh/projects/useme/chain_executor.py#L370)
7. formularz [form_driver.py:35](file:///c:/Users/buchh/projects/useme/form_driver.py#L35)

## 2. Formularz (obszar A)
- **F-A1 fałszywy sukces po URL** — [form_driver.py:158](file:///c:/Users/buchh/projects/useme/form_driver.py#L149-L159).
- **F-A2 TurnstileSolver niepodpięty** — brak importu w form_driver/engine.
- **F-A3 opis do hidden pola JS-em** — [form_driver.py:84-91](file:///c:/Users/buchh/projects/useme/form_driver.py#L78-L91).
- **F-A4 brak walidacji przed submitem** — [form_driver.py:63-109](file:///c:/Users/buchh/projects/useme/form_driver.py#L63-L109).
- **F-A5 za krótkie czekanie** — [form_driver.py:137-142](file:///c:/Users/buchh/projects/useme/form_driver.py#L137-L142).
- **F-A6 kruche selektory** — [form_driver.py:129](file:///c:/Users/buchh/projects/useme/form_driver.py#L129).
- **F-A9 UnboundLocalError res** — [engine.py:351-356](file:///c:/Users/buchh/projects/useme/engine.py#L351-L356).

## 3. Łańcuch AI (obszar B)
- **F-B1 lokalne proxy** [chain_executor.py:44](file:///c:/Users/buchh/projects/useme/chain_executor.py#L44).
- **F-B2 selekcja przepuszcza wszystko** [ai_pipeline.py:194-196](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L194-L196).
- **F-B4 pusty łańcuch → RuntimeError** [ai_pipeline.py:244-245](file:///c:/Users/buchh/projects/useme/ai_pipeline.py#L244-L245).
- **F-B5 twarde return None** [chain_executor.py:411/468/479/562/631](file:///c:/Users/buchh/projects/useme/chain_executor.py).
- **F-B7 cicha akceptacja FAIL** [chain_executor.py:619-624](file:///c:/Users/buchh/projects/useme/chain_executor.py#L619-L624).

## 4. Gubienie ofert (obszar C)
- 144256 utknęło na POBRANO_DETALE (brak pipeline).
- 12 ofert POBRANO_DETALE.
- Podwójna blokada (martwy kod) [engine.py:195,201](file:///c:/Users/buchh/projects/useme/engine.py#L195-L204).
- Zapisana propozycja pomija AI [engine.py:246-259](file:///c:/Users/buchh/projects/useme/engine.py#L246-L259).

## 5. Infrastruktura (obszar D)
- cookies [tech/cookies.json](file:///c:/Users/buchh/projects/useme/tech/cookies.json); wygaśnięcie → [form_driver.py:44-50](file:///c:/Users/buchh/projects/useme/form_driver.py#L44-L50) → break [engine.py:346-350](file:///c:/Users/buchh/projects/useme/engine.py#L346-L350).
- loader cicho ignoruje błąd [browser_driver.py:63-64](file:///c:/Users/buchh/projects/useme/browser_driver.py#L51-L64).
- sanity-blok [engine.py:269-276](file:///c:/Users/buchh/projects/useme/engine.py#L269-L276).

## 6. Niespójność dowodów
22 WYSLANO vs 11 PNG → 11 bez dowodu. Magazyn 36. Aktywne: 1 (144353).