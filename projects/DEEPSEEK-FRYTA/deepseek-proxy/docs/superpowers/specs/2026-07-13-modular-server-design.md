# Modular Server Refactor — Design Spec

**Date:** 2026-07-13
**Status:** Draft
**Project:** deepseek-proxy

## 1. Goal

Split the monolithic `server.py` (3096 lines, 146KB) into a structured Python package with:
- Clear module boundaries per domain
- Service classes with dependency injection
- Full async migration (asyncio throughout)
- Clean workspace (remove log files, temp scripts, Chrome cache)
- No regression — all existing tests must pass after each phase

## 2. Directory Structure

```
deepseek-proxy/
├── server/
│   ├── __init__.py            # FastAPI app, lifespan
│   ├── main.py                # uvicorn entry point
│   ├── config.py              # Constants (MAX_PROMPT_LEN, CONTEXT_CHAR_LIMIT, etc.)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── proxy.py           # ProxyService — orchestrator
│   │   └── models.py          # ChatRequest (pydantic)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── account_service.py # AccountPool + Session management
│   │   ├── auth_service.py    # Playwright auth, login, token
│   │   ├── prompt_service.py  # _build_prompt, _inject_tools, _format_msgs, trim
│   │   ├── state_service.py   # conv_state CRUD, conv_key, watermark
│   │   └── stream_service.py  # Streaming loop, SSE emit, watermarks
│   │
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── stream_parser.py   # StructuredResponseStreamParser
│   │   └── tool_parser.py     # _parse_tool_calls, _parse_param, helpers
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py          # FastAPI endpoints
│   │   └── deps.py            # DI wiring (Depends)
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py         # _fix_json_strings, _compress_image, regex patterns
│
├── tests/
│   ├── __init__.py
│   ├── test_parsing.py
│   ├── test_structured_parser.py
│   ├── test_new_format.py
│   ├── test_watermark.py
│   └── services/              # New service tests
│       ├── test_prompt_service.py
│       ├── test_state_service.py
│       └── test_stream_service.py
│
├── conv_state.json
├── conv_history/
├── conversation_logs/
├── requirements.txt
├── run_proxy.bat
└── .gitignore
```

External files stay in place (no refactor needed):
- `CloudflareBypasser.py` — standalone
- `pow.py` — PoW solver, standalone

## 3. Service Interfaces (DI)

### ProxyService — orchestrator

```python
class ProxyService:
    def __init__(self, account_svc, auth_svc, prompt_svc, state_svc, stream_svc):
        ...

    async def handle_chat_completion(self, req: ChatRequest, raw_request: Request) -> StreamingResponse:
        """Full request lifecycle: auth → assign → build → stream → persist."""
```

### PromptService

```python
class PromptService:
    async def build_prompt(self, messages, tools=None, images=None, max_history_len=2000) -> str: ...
    async def inject_tools_as_system(self, messages, tools) -> list[dict]: ...
    async def format_messages(self, msgs) -> list[str]: ...
    async def trim_context(self, messages) -> list[dict]: ...
```

### StateService

```python
class StateService:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._state: dict[str, dict] = {}  # in-memory cache

    async def load_state(self, conv_uuid) -> dict: ...
    async def save_state(self, conv_uuid, state, *, force=False, history_messages=None): ...
    async def get_conv_key(self, messages, acl_payload=None, chat_id=None, thread_id=None) -> str: ...
    async def hash_last_user_message(self, messages, full=False) -> str: ...
    async def rotate_session(self, conv_uuid) -> str: ...
```

### AccountService

```python
class AccountService:
    async def assign(self, user_hash, model="deepseek-chat") -> tuple[int, dict]: ...
    async def release(self, account_idx): ...
    async def get_deepseek_client(self, account_idx): ...
```

### StreamService

```python
class StreamService:
    async def generate(self, req, conv_uuid, account_idx, prompt, tools,
                       watermark_uuid, parent_id, stream_gen) -> AsyncGenerator[str, None]: ...
    async def save_conversation_log(self, conv_uuid, turn, prompt, response): ...
```

### DI wiring (server/api/deps.py)

```python
@lru_cache
def get_proxy_service() -> ProxyService: ...
```

## 4. Async Migration Strategy

Sync-to-async conversion order, each building on the previous:

| Step | Module | What changes |
|------|--------|-------------|
| 0 | parser/, utils/ | Stay sync — pure functions, no I/O |
| 1 | StateService | `asyncio.Lock`, batch flush to disk (500ms debounce or 5-change threshold) |
| 2 | PromptService | async wrapper (internals sync until needed) |
| 3 | AccountService | async assign/release, async HTTP to DeepSeek |
| 4 | StreamService | async generator via ProxyService |
| 5 | ProxyService | async orchestrator, wires everything |
| 6 | api/routes.py | FastAPI `async def` with `Depends(get_proxy_service)` |

### State batch flush

Replace every-message disk writes with:
- In-memory dict cache
- `asyncio.Lock` for concurrent access
- Flush to `conv_state.json` every 500ms (debounced) or every 5 mutations
- Immediate flush on graceful shutdown (lifespan event)

Expected: ~90% reduction in file I/O.

## 5. Workspace Cleanup

### Files to delete
- `.chrome_slot/` — Playwright Chrome cache
- `server_out.txt`, `sv_out.txt`, `sv_err.txt`, `sv_out.log`, `sv_err.log`
- `server_stdout.log`, `server_stderr.log`, `server.err`
- `legid_log.txt`, `user_fp_log.txt`, `token_fields.txt`
- `msg_structure.txt`
- `_check_state.py`, `_check_trae_prompt.py`, `_analyze_debug.py`, `check_state.py`
- `conv_state_backup.json`

### .gitignore
```gitignore
__pycache__/
*.pyc
.conv_state.json
conv_state_backup.json
.chrome_slot/
*.log
*.err
server_out.txt
sv_out.txt
sv_err.txt
legid_log.txt
user_fp_log.txt
token_fields.txt
_check_*.py
_analyze_*.py
check_state.py
msg_structure.txt
.env
*.session
```

## 6. Module Dependency Rules

```
api/routes.py → core/proxy.py → services/* (via DI)
parser/*       → no imports from services/ or api/
utils/*        → no imports from services/ or api/
services/*     → no cross-service imports
```

No service imports another service directly. All orchestration goes through `ProxyService`.

## 7. Migration Phases

### Phase 0 — Cleanup (1 commit)
- Add `.gitignore`
- Delete all temp/log/cache files
- No logic changes

### Phase 1 — Package creation (1 commit)
- Create `server/` directory tree
- Copy functions to their new locations
- `server.py` becomes `server/__init__.py` + `server/main.py`
- **`server.py` re-exports all public symbols** from the new modules so that existing `from server import _parse_tool_calls` imports continue to work without changes
- All tests pass without any modifications

### Phase 2 — Service interfaces (1-2 commits)
- Add service classes with DI
- `ProxyService` as orchestrator
- Wire via `api/deps.py`
- Unit tests for each service

### Phase 3 — Async migration (2-3 commits)
- StateService: async lock + batch flush
- AccountService: async assign/release
- StreamService: async generator through ProxyService
- Tests converted to async

### Phase 4 — Polish (1 commit)
- Move `CloudflareBypasser.py` → `server/utils/cloudflare.py`
- Move `pow.py` → `server/utils/pow.py` (optional)
- New service tests
- Delete old `server.py` after verification

### Safety
Old `server.py` stays in place until Phase 4. Each phase is independently testable.

## 8. Testing

- All existing tests must pass after each phase
- New tests per service (unit tests with mocked dependencies)
- Integration test: full request lifecycle through ProxyService with mock DeepSeek
- No test changes required in Phase 0-1 (imports remain valid via re-exports)
