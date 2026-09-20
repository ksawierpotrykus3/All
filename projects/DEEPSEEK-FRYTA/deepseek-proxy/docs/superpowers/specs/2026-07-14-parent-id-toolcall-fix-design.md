# Parent ID & Tool Call Fix — Design Spec

## 1. Fix Parent ID — real-time `result_meta` update

**Problem**: `deepseek_client.py` aktualizuje `result_meta["resp_msg_id"]` dopiero po wyczerpaniu generatora (linia 467). `stream_service.py` czyta tę wartość w ścieżkach wczesnego powrotu (tool_calls, thinking_fallback, JSON), zanim generator się zakończy — otrzymuje nieaktualną wartość z preambuły.

**Rozwiązanie**: Wewnątrz `_stream()`, przy każdej zmianie `resp_msg_id`, natychmiast aktualizować `result_meta["resp_msg_id"]`. Usunąć zbędną linię 467.

**Plik**: `server/core/deepseek_client.py`

## 2. Fix Tool Call SID — osadzenie conv_uuid w tool_call ID

**Problem**: `_tc_id()` generuje `call_{uuid}`, ale `_TC_SID_PATTERN` w `state_service.py` szuka `call_sid:{conv_uuid}_`. SID nie jest wysyłany w tool_calls paths, więc Trae IDE nie może wznowić konwersacji po tool callach.

**Rozwiązanie**:
- `_tc_id(conv_uuid)` generuje `call_sid:{conv_uuid}_{random}` gdy conv_uuid dostępny
- We wszystkich 4 ścieżkach tool_calls (DSML, EOS, thinking_fallback, JSON) przekazać `conv_uuid` do `_tc_id()`
- Dodać `sid=conv_uuid` do końcowego chunka `fr="tool_calls"` we wszystkich ścieżkach

**Plik**: `server/services/stream_service.py`

## 3. Agent behavior — reasoning_effort

**Problem**: Brak wsparcia dla `reasoning_effort` w `ChatRequest`.

**Rozwiązanie**:
- Dodać `reasoning_effort: str | None` do `ChatRequest` w `models.py`
- Przekazać przez `proxy.py` do `deepseek_client.py` (już wspiera jako parametr w body requestu)

**Pliki**: `server/core/models.py`, `server/core/proxy.py`

## Zakres zmian

| Plik | Zmiana |
|------|--------|
| `server/core/deepseek_client.py` | +1 linia (aktualizacja `result_meta` w _stream) |
| `server/services/stream_service.py` | `_tc_id(conv_uuid)`, SID w chunkach tool_calls |
| `server/core/models.py` | +1 pole `reasoning_effort` |
| `server/core/proxy.py` | przekazanie `reasoning_effort` |
