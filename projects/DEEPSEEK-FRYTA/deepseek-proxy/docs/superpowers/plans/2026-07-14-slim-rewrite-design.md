# Slim Rewrite — DeepSeek Proxy Anti-Detection Design

**Data:** 2026-07-14
**Status:** Zatwierdzony
**Problem:** Nowy modularny serwer (server/main.py) powoduje mute kont na DeepSeek.

## Zidentyfikowane przyczyny mute

1. Retry na tym samym koncie po rate-limit — deepseek_client.py przy rate_limit_detected czeka 60s i ponawia na TYM SAMYM koncie.
2. 3x wywołania HTTP na jeden turn — _throttle() w _get_challenge() i stream_completion() + _prefetch_pow() w tle.
3. Przestarzale naglowki — x-client-version: 2.0.0, przeglarka wysyla 2.2.0 bez x-app-version.
4. Nadmiernie zlozony stan — watermark, dedup, acl_sub, session pool, SILENT_ROTATION.

## Podejscie: Slim Rewrite

Cel: prostota jak legacy server.py z poprawnymi poprawkami.

### Architektura po zmianach

- main.py: bez zmian
- config.py: uproszczony
- core/deepseek_client.py: naglowki 2.2.0, throttle 1x/req, brak prefetch
- core/proxy.py: scalony z stream_service, ~250 linii
- services/prompt_service.py: jeden _format_msgs() plaintext
- services/state_service.py: hash→{chat_id, parent_id, account, ts}
- services/dsml_prompt.py: USUNIETY
- services/stream_service.py: USUNIETY

### Stan konwersacji

Jeden mechanizm: hash ostatnich 6 wiadomosci (bez najnowszej) → {chat_id, parent_id, account}.
TTL: 1 godzina. Zapis do conv_state.json (debounce 30s).

Usuniete: WATERMARK_ENABLED, request_dedup, acl_sub, session pool semaphore.

### Prompt builder (plaintext)

Jeden format:
  [System]: ...
  [User]: ...
  [Assistant]: ...
  [Tool Call]: name(args)
  [Tool Result:id]\n content
  [Tools available]: name1, name2

Hard cap: 150000 znakow. Brak COSTAR_TOOL_CALLING_RULES. Brak pelnych JSON schematow narzedzi.

### Stealth w deepseek_client.py

- x-client-version: 2.2.0 (bylo 2.0.0)
- x-app-version: USUNIETY
- _MIN_REQUEST_INTERVAL: 3.0s (bylo 2.0)
- _prefetch_pow(): USUNIETY
- Retry na rate_limit: USUNIETY (rzuca RuntimeError natychmiast)
- Retry na INVALID_POW_RESPONSE: zostaje (jeden retry OK)

### Rate limit i account switch

Przy RateLimitError: jeden switch na alternatywne konto bez retry na tym samym.
Brak alternatywy → 429 do klienta.

Usuniete: kaskada _try_send, _handle_rate(), SILENT_ROTATION, _wrap_release(), StreamService.

## Metryki sukcesu

- Brak mute po 30+ min uzycia TRAE IDE
- proxy.py <= 300 linii
- prompt_service.py <= 80 linii
- state_service.py <= 60 linii
