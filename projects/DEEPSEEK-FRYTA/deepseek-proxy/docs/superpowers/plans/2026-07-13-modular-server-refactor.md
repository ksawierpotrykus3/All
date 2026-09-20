# Modular Server Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split monolithic `server.py` (3096 lines) into a structured package with service-oriented architecture, DI, and full async migration.

**Architecture:** Service classes with dependency injection orchestrated by `ProxyService`. Pure functions in `parser/` and `utils/` stay sync. 5 phases: Cleanup → Package → Services → Async → Polish.

**Tech Stack:** Python 3.11+, FastAPI, asyncio, pytest, pydantic

---

## File Structure

```
deepseek-proxy/
├── server/                          # NEW — becomes the package
│   ├── __init__.py                  # FastAPI app, lifespan
│   ├── main.py                      # uvicorn.run() entry point
│   ├── config.py                    # All constants
│   ├── core/
│   │   ├── __init__.py
│   │   ├── proxy.py                 # ProxyService orchestrator
│   │   └── models.py                # ChatRequest pydantic model
│   ├── services/
│   │   ├── __init__.py
│   │   ├── account_service.py       # AccountPool + Session
│   │   ├── auth_service.py          # Playwright auth, login
│   │   ├── prompt_service.py        # _build_prompt, trim, inject, format
│   │   ├── state_service.py         # conv_state CRUD, conv_key
│   │   └── stream_service.py        # Streaming loop, SSE
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── stream_parser.py         # StructuredResponseStreamParser
│   │   └── tool_parser.py           # _parse_tool_calls, helpers
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                # FastAPI endpoints
│   │   └── deps.py                  # DI wiring
│   └── utils/
│       ├── __init__.py
│       └── helpers.py               # _fix_json_strings, _compress_image, regex
├── server.py                         # OLD — keeps re-exports until Phase 4
├── tests/
│   ├── __init__.py
│   ├── test_parsing.py               # Stays unchanged
│   ├── test_structured_parser.py
│   ├── test_new_format.py
│   ├── test_watermark.py
│   └── services/                     # NEW service tests
│       ├── __init__.py
│       ├── test_prompt_service.py
│       ├── test_state_service.py
│       └── test_stream_service.py
├── .gitignore                         # NEW
├── CloudflareBypasser.py              # Stays (moved in Phase 4)
└── pow.py                             # Stays (moved in Phase 4)
```

---

### Phase 0: Workspace Cleanup

### Task 0.1: Create .gitignore

**Files:**
- Create: `deepseek-proxy/.gitignore`

- [ ] **Step 1: Write .gitignore**

```gitignore
# Runtime
__pycache__/
*.pyc
.conv_state.json
conv_state_backup.json

# Chrome / Playwright
.chrome_slot/

# Logs
*.log
*.err
server_out.txt
sv_out.txt
sv_err.txt
legid_log.txt
user_fp_log.txt
token_fields.txt

# Temp debug scripts
_check_*.py
_analyze_*.py
check_state.py
msg_structure.txt

# Environment
.env
*.session
```

- [ ] **Step 2: Verify gitignore is in place**

Run: `Get-Item f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\.gitignore`
Expected: file exists

- [ ] **Step 3: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add .gitignore
git commit -m "chore: add .gitignore for logs, cache, temp files"
```

### Task 0.2: Delete temp/log/cache files

**Files:**
- Delete: `.chrome_slot/`, `server_out.txt`, `sv_out.txt`, `sv_err.txt`, `sv_out.log`, `sv_err.log`, `server_stdout.log`, `server_stderr.log`, `server.err`, `legid_log.txt`, `user_fp_log.txt`, `token_fields.txt`, `msg_structure.txt`, `_check_state.py`, `_check_trae_prompt.py`, `_analyze_debug.py`, `check_state.py`, `conv_state_backup.json`

- [ ] **Step 1: Delete all identified files**

Run PowerShell:
```powershell
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
$files = @(
    ".chrome_slot", "server_out.txt", "sv_out.txt", "sv_err.txt",
    "sv_out.log", "sv_err.log", "server_stdout.log", "server_stderr.log",
    "server.err", "legid_log.txt", "user_fp_log.txt", "token_fields.txt",
    "msg_structure.txt", "_check_state.py", "_check_trae_prompt.py",
    "_analyze_debug.py", "check_state.py", "conv_state_backup.json"
)
foreach ($f in $files) { if (Test-Path $f) { Remove-Item -Recurse -Force $f; Write-Host "Deleted: $f" } }
```

Expected: no errors, all files deleted

- [ ] **Step 2: Verify workspace is clean**

Run: `Get-ChildItem -Name f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\`
Expected: clean listing (no _check_*.py, no .log files, no .chrome_slot)

- [ ] **Step 3: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add -A
git commit -m "chore: delete temp logs, cache, and debug scripts"
```

---

### Phase 1: Package Creation

### Task 1.1: Create server/ directory tree

**Files:**
- Create: `deepseek-proxy/server/__init__.py`
- Create: `deepseek-proxy/server/main.py`
- Create: `deepseek-proxy/server/config.py`
- Create: `deepseek-proxy/server/core/__init__.py`
- Create: `deepseek-proxy/server/core/proxy.py`
- Create: `deepseek-proxy/server/core/models.py`
- Create: `deepseek-proxy/server/services/__init__.py`
- Create: `deepseek-proxy/server/services/account_service.py`
- Create: `deepseek-proxy/server/services/auth_service.py`
- Create: `deepseek-proxy/server/services/prompt_service.py`
- Create: `deepseek-proxy/server/services/state_service.py`
- Create: `deepseek-proxy/server/services/stream_service.py`
- Create: `deepseek-proxy/server/parser/__init__.py`
- Create: `deepseek-proxy/server/parser/stream_parser.py`
- Create: `deepseek-proxy/server/parser/tool_parser.py`
- Create: `deepseek-proxy/server/api/__init__.py`
- Create: `deepseek-proxy/server/api/routes.py`
- Create: `deepseek-proxy/server/api/deps.py`
- Create: `deepseek-proxy/server/utils/__init__.py`
- Create: `deepseek-proxy/server/utils/helpers.py`

- [ ] **Step 1: Create all __init__.py files (empty)**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
mkdir -p server/core server/services server/parser server/api server/utils
New-Item server/__init__.py, server/main.py, server/config.py,
          server/core/__init__.py, server/core/proxy.py, server/core/models.py,
          server/services/__init__.py, server/services/account_service.py,
          server/services/auth_service.py, server/services/prompt_service.py,
          server/services/state_service.py, server/services/stream_service.py,
          server/parser/__init__.py, server/parser/stream_parser.py,
          server/parser/tool_parser.py, server/api/__init__.py,
          server/api/routes.py, server/api/deps.py,
          server/utils/__init__.py, server/utils/helpers.py -Force
```

- [ ] **Step 2: Verify structure exists**

Run: `Get-ChildItem -Recurse -Name f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\`
Expected: all files listed

- [ ] **Step 3: Commit empty structure**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/
git commit -m "feat: create server/ package directory structure"
```

### Task 1.2: Copy constants to config.py

**Files:**
- Create: `deepseek-proxy/server/config.py`
- Modify: `deepseek-proxy/server.py` (add import from config)

- [ ] **Step 1: Write config.py with all constants from server.py**

Extract these constants from server.py and put them in config.py:

```python
# server/config.py
"""All proxy constants in one place."""

import re

# --- Character Limits ---
MAX_PROMPT_LEN = 150000
CONTEXT_CHAR_LIMIT = 150_000
_MAX_CONTENT_REFINE_LEN = 2000
_MIN_KEEP_RECENT = 12
_TRUNCATE_CHARS = 600
RECENT_HISTORY_KEEP = 25
_NEW_SESSION_MSG_LIMIT = 25
_RESUME_KEEP_RECENT = 8
_MAX_CONVERSATION_FILE_SIZE = 1024 * 1024  # 1 MB

# --- Tool Call Patterns ---
_STRIP_TAGS_PATTERN = re.compile(r'<(/?)(tool_call|tool_calls|invoke|function_call|tool_use_json|thinking|result)\b[^>]*>')
_STRIP_XML_TOOL_TAGS = re.compile(r'<(/?)(tool_call|tool_calls)\b[^>]*>')

# --- URL / API ---
DEEPSEEK_CHAT_URL = "https://chat.deepseek.com/api/v0/chat/completion"
DEEPSEEK_CREATE_SESSION = "https://chat.deepseek.com/api/v0/chat/create_session"

# --- Timing ---
MAX_RETRIES = 5
STATE_FLUSH_INTERVAL = 0.5       # seconds (debounce)
STATE_FLUSH_THRESHOLD = 5        # mutations before forced flush

# --- Watermark ---
WATERMARK_MARKER = "<!-- PROXY_SID:"
```

- [ ] **Step 2: Update server.py to import from config**

Add at top of server.py (after existing imports):

```python
from server.config import (
    MAX_PROMPT_LEN, CONTEXT_CHAR_LIMIT, _STRIP_TAGS_PATTERN,
    _STRIP_XML_TOOL_TAGS, DEEPSEEK_CHAT_URL, DEEPSEEK_CREATE_SESSION,
    _NEW_SESSION_MSG_LIMIT, _RESUME_KEEP_RECENT, _MIN_KEEP_RECENT,
    _TRUNCATE_CHARS, RECENT_HISTORY_KEEP, _MAX_CONTENT_REFINE_LEN,
    _MAX_CONVERSATION_FILE_SIZE, MAX_RETRIES, WATERMARK_MARKER,
)
```

- [ ] **Step 3: Remove constant definitions from server.py**

Delete the corresponding constant definitions from server.py (MAX_PROMPT_LEN, CONTEXT_CHAR_LIMIT, _STRIP_TAGS_PATTERN, etc.) that were just moved to config.py.

- [ ] **Step 4: Run tests to verify no regression**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/test_parsing.py test_structured_parser.py -v`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/config.py server.py
git commit -m "refactor: extract constants to server/config.py"
```

### Task 1.3: Copy parser functions to server/parser/

**Files:**
- Create: `deepseek-proxy/server/parser/stream_parser.py`
- Create: `deepseek-proxy/server/parser/tool_parser.py`
- Modify: `deepseek-proxy/server.py` (add re-exports)

- [ ] **Step 1: Write server/parser/stream_parser.py**

Copy the entire `StructuredResponseStreamParser` class from server.py into this file. Keep the class exactly as-is.

```python
# server/parser/stream_parser.py
"""Incremental JSON parser for DeepSeek tool-call streaming responses."""

class StructuredResponseStreamParser:
    # ... exact copy from server.py lines 1575-1825 ...

    def __init__(self):
        self.buf = ""
        self.json_start = -1
        self.json_depth = 0
        self.action = None
        # ... rest of properties ...
```

- [ ] **Step 2: Write server/parser/tool_parser.py**

Copy these functions from server.py into this file:
- `_parse_tool_calls`
- `_parse_param_value`
- `_parse_param`
- `_get_param_type`
- `_clean_xml_string`
- `_parse_tool_name`
- `_snake_to_canonical_key`
- `_snake_to_canonical` (dict)
- `reserved_tags`
- `_CONTENT_STRIP_PATTERN`
- `_fix_json_strings`

```python
# server/parser/tool_parser.py
"""XML and JSON tool call parsing utilities."""

import re
import json

# ... paste all functions from server.py ...
```

- [ ] **Step 3: Add re-exports in server.py**

Add at the top of server.py (in the existing import section):

```python
from server.parser.stream_parser import StructuredResponseStreamParser
from server.parser.tool_parser import (
    _parse_tool_calls, _parse_param_value, _parse_param, _get_param_type,
    _clean_xml_string, _parse_tool_name, _fix_json_strings,
    _CONTENT_STRIP_PATTERN,
)
```

- [ ] **Step 4: Run tests**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/test_parsing.py test_structured_parser.py -v`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/parser/ server.py
git commit -m "refactor: extract parser classes to server/parser/"
```

### Task 1.4: Copy utils functions to server/utils/

**Files:**
- Create: `deepseek-proxy/server/utils/helpers.py`
- Modify: `deepseek-proxy/server.py`

- [ ] **Step 1: Write server/utils/helpers.py**

Copy these utility functions from server.py:
- `_compress_image`
- `_ensure_valid_json`
- `_rebuild_structured`
- `_get_safe_yield_len`
- `_chunk`
- `_calc_tool_cost`

```python
# server/utils/helpers.py
"""Pure utility functions — no I/O, no service dependencies."""

import json
import re
from typing import Any

# ... paste functions from server.py ...
```

- [ ] **Step 2: Add re-export in server.py**

```python
from server.utils.helpers import (
    _compress_image, _ensure_valid_json, _rebuild_structured,
    _get_safe_yield_len, _chunk, _calc_tool_cost,
)
```

- [ ] **Step 3: Run tests**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/utils/ server.py
git commit -m "refactor: extract utility functions to server/utils/"
```

### Task 1.5: Copy service functions to placeholder files

**Files:**
- Create content in: `server/services/prompt_service.py`, `state_service.py`, `stream_service.py`, `account_service.py`, `auth_service.py`
- Modify: `server.py`

For now, each service file gets a module docstring and placeholder. The actual service classes come in Phase 2. The functions remain in server.py, re-exported.

- [ ] **Step 1: Write placeholder service files**

Each file gets a docstring and `__all__` listing what will be moved here in Phase 2.

Example for `state_service.py`:
```python
# server/services/state_service.py
"""Conversation state management.

Phase 2 will add StateService class here.
Currently functions are re-exported from server.py.
"""

# Functions to be moved in Phase 2:
# _save_conv_state, _load_conv_state, _get_conv_key,
# _hash_last_user_message, _extract_conversation_uuid
```

- [ ] **Step 2: Verify nothing broke**

Run: `python -c "import sys; sys.path.insert(0,'.'); import server" 2>&1`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/services/
git commit -m "refactor: add service module placeholders"
```

### Task 1.6: Create server/__init__.py and server/main.py

**Files:**
- Create: `deepseek-proxy/server/__init__.py` (FastAPI app)
- Create: `deepseek-proxy/server/main.py` (entry point)
- Create: `deepseek-proxy/server/core/models.py`
- Modify: `server.py` (add re-exports)

- [ ] **Step 1: Write server/core/models.py**

Extract the `ChatRequest` class from server.py:
```python
# server/core/models.py
"""Pydantic models for API requests/responses."""

from pydantic import BaseModel
from typing import Any, Optional

class ChatRequest(BaseModel):
    messages: list[dict]
    model: str = "deepseek-chat"
    stream: bool = True
    tools: Optional[list[dict]] = None
    tool_choice: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    parallel_tool_calls: Optional[bool] = None
    images: Optional[list[dict]] = None
```

- [ ] **Step 2: Write server/__init__.py**

Copy FastAPI app creation from the bottom of server.py (around lines 3000-3096):
```python
# server/__init__.py
"""DeepSeek Proxy — FastAPI application."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Server starting...")
    yield
    # Shutdown
    logger.info("Server shutting down...")

app = FastAPI(title="DeepSeek Proxy", version="4.0", lifespan=lifespan)

# Import routes to register them
from server.api import routes  # noqa: F401, E402
```

- [ ] **Step 3: Write server/main.py**

```python
# server/main.py
"""Entry point: run with `python -m server.main` or `uvicorn server:app`."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=4570, reload=False)
```

- [ ] **Step 4: Add re-exports in server.py**

```python
from server.core.models import ChatRequest
```

- [ ] **Step 5: Verify import chain works**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -c "from server import app; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/__init__.py server/main.py server/core/models.py server.py
git commit -m "refactor: add server package with FastAPI app and main entry point"
```

---

### Phase 2: Service Interfaces with DI

### Task 2.1: Implement PromptService

**Files:**
- Modify: `deepseek-proxy/server/services/prompt_service.py`
- Create: `deepseek-proxy/tests/services/__init__.py`
- Create: `deepseek-proxy/tests/services/test_prompt_service.py`

- [ ] **Step 1: Copy prompt-related functions into PromptService class**

```python
# server/services/prompt_service.py
"""Prompt building, tool injection, message formatting, context trimming."""

from typing import Any
from server.parser.tool_parser import _CONTENT_STRIP_PATTERN
from server.utils.helpers import _rebuild_structured

class PromptService:
    """Builds and formats prompts sent to DeepSeek."""

    async def build_prompt(
        self, messages: list[dict], tools: list[dict] | None = None,
        images: list[dict] | None = None, max_history_len: int = 2000,
    ) -> str:
        """Build final prompt with tool definitions and format instructions."""
        # Paste _build_prompt logic from server.py here
        # Replace direct references to constants with server.config imports
        ...

    async def inject_tools_as_system(
        self, messages: list[dict], tools: list[dict] | None,
    ) -> list[dict]:
        """Inject tool definitions into system prompt."""
        # Paste _inject_tools_as_system logic from server.py here
        ...

    async def format_messages(self, msgs: list[dict]) -> list[str]:
        """Format messages list into text lines with role prefixes."""
        # Paste _format_msgs logic from server.py here
        ...

    async def trim_context(self, messages: list[dict]) -> list[dict]:
        """Trim conversation history to fit within character limit."""
        # Paste _trim_context logic from server.py here
        ...

    async def cascade_compress_tool_results(
        self, messages: list[dict], max_chars: int = 200,
    ) -> list[dict]:
        """Compress long tool results to brief summaries."""
        # Paste _cascade_compress_tool_results logic from server.py here
        ...

    async def reconstruct_resume_messages(
        self, messages: list[dict],
    ) -> list[dict]:
        """Prepare messages for resume (keep recent history)."""
        # Paste _reconstruct_resume_messages logic from server.py here
        ...
```

- [ ] **Step 2: Write the failing test**

```python
# tests/services/test_prompt_service.py
"""Tests for PromptService."""

import pytest
from server.services.prompt_service import PromptService

@pytest.fixture
def svc():
    return PromptService()

@pytest.mark.asyncio
async def test_format_messages_simple(svc):
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]
    result = await svc.format_messages(msgs)
    assert "role: system" in result[0]
    assert "You are a helpful assistant" in result[0]
    assert "role: user" in result[1]
    assert "Hello" in result[1]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/services/test_prompt_service.py -v`
Expected: FAIL (PromptService has `...` methods)

- [ ] **Step 4: Implement the methods with real code from server.py**

Copy the full implementation from server.py into each PromptService method, replacing `...`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/services/test_prompt_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/services/prompt_service.py tests/services/
git commit -m "feat: implement PromptService with format, trim, build methods"
```

### Task 2.2: Implement StateService

**Files:**
- Modify: `deepseek-proxy/server/services/state_service.py`
- Create: `deepseek-proxy/tests/services/test_state_service.py`

- [ ] **Step 1: Write StateService with async interface (sync impl for now)**

```python
# server/services/state_service.py
"""Conversation state management with in-memory cache and batch flush."""

import asyncio
import json
import hashlib
from typing import Any

class StateService:
    """Manages conv_state.json read/write with async lock and batch flush."""

    def __init__(self, state_path: str = "conv_state.json"):
        self._state_path = state_path
        self._lock = asyncio.Lock()
        self._state: dict[str, dict] = {}
        self._dirty = False
        self._mutations = 0
        self._flush_task: asyncio.Task | None = None

    async def load_state(self, conv_uuid: str) -> dict:
        async with self._lock:
            if not self._state:
                await self._load_from_disk()
            return self._state.get(conv_uuid, {})

    async def save_state(
        self, conv_uuid: str, state_data: dict,
        *, force: bool = False, history_messages: list[dict] | None = None,
    ):
        async with self._lock:
            self._state[conv_uuid] = state_data
            self._dirty = True
            self._mutations += 1
            if force or self._mutations >= 5:
                await self._flush_to_disk()
            elif self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._debounced_flush())

    async def get_conv_key(
        self, messages: list[dict], acl_payload: dict | None = None,
        chat_id: str | None = None, thread_id: str | None = None,
    ) -> str:
        # Paste _get_conv_key logic from server.py here
        ...

    async def _load_from_disk(self):
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                self._state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._state = {}

    async def _flush_to_disk(self):
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)
        self._dirty = False
        self._mutations = 0

    async def _debounced_flush(self):
        await asyncio.sleep(0.5)
        if self._dirty:
            async with self._lock:
                await self._flush_to_disk()
```

- [ ] **Step 2: Write test**

```python
# tests/services/test_state_service.py
import pytest
from server.services.state_service import StateService

@pytest.fixture
def svc(tmp_path):
    s = StateService(state_path=str(tmp_path / "test_state.json"))
    return s

@pytest.mark.asyncio
async def test_save_and_load_state(svc):
    await svc.save_state("test-uuid", {"parent_id": 42}, force=True)
    loaded = await svc.load_state("test-uuid")
    assert loaded.get("parent_id") == 42
```

- [ ] **Step 3: Run tests**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/services/test_state_service.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/services/state_service.py tests/services/test_state_service.py
git commit -m "feat: implement StateService with async lock and batch flush"
```

### Task 2.3: Implement AccountService, AuthService, StreamService stubs

**Files:**
- Modify: `deepseek-proxy/server/services/account_service.py`
- Modify: `deepseek-proxy/server/services/auth_service.py`
- Modify: `deepseek-proxy/server/services/stream_service.py`

- [ ] **Step 1: Implement AccountService**

Copy AccountPool, Session, DeepSeek classes into AccountService. Add `assign()`, `release()`, `get_deepseek_client()` methods.

```python
# server/services/account_service.py
"""Account pool management and DeepSeek session handling."""

from typing import Any

class AccountService:
    """Manages account pool and DeepSeek sessions."""

    def __init__(self):
        # Copy AccountPool, Session, DeepSeek instantiation from server.py
        self._pool = ...  # AccountPool instance
        ...

    async def assign(self, user_hash: str, model: str = "deepseek-chat") -> tuple[int, dict]:
        """Assign an account slot for the user."""
        # Paste assign logic from server.py (around line 2360-2420)
        ...

    async def release(self, account_idx: int):
        """Release the account slot."""
        ...

    async def get_deepseek_client(self, account_idx: int):
        """Get DeepSeek client for the account slot."""
        ...
```

- [ ] **Step 2: Implement AuthService stub**

```python
# server/services/auth_service.py
"""Playwright-based authentication and token handling."""

class AuthService:
    """Handles login via Playwright and bearer token extraction."""

    async def authenticate(self) -> str:
        """Return a valid bearer token."""
        # Paste authenticate_via_playwright logic from server.py
        ...

    async def verify_token(self, token: str) -> bool:
        """Check if token is still valid."""
        ...
```

- [ ] **Step 3: Implement StreamService stub**

```python
# server/services/stream_service.py
"""Streaming loop, SSE emit, watermarks, tool call detection."""

from typing import AsyncGenerator, Any

class StreamService:
    """Handles DeepSeek streaming response parsing and SSE emission."""

    async def generate(
        self, conv_uuid: str, account_idx: int, prompt: str,
        tools: list[dict] | None, watermark_uuid: str,
        parent_id: int | str | None, account_service, state_service,
    ) -> AsyncGenerator[str, None]:
        """Main streaming loop — reads from DeepSeek, parses, emits SSE."""
        # Paste generate() logic from server.py
        # This will call account_service to get the DeepSeek client
        # and state_service to manage state
        ...
        yield f"data: {chunk}\n\n"

    async def save_conversation_log(
        self, conv_uuid: str, turn: int, prompt: str, response: str,
    ):
        """Save prompt/response to conversation_logs/ directory."""
        ...
```

- [ ] **Step 4: Verify imports work**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -c "from server.services.account_service import AccountService; from server.services.state_service import StateService; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/services/
git commit -m "feat: implement AccountService, AuthService, StreamService stubs"
```

### Task 2.4: Create ProxyService orchestrator

**Files:**
- Modify: `deepseek-proxy/server/core/proxy.py`
- Modify: `deepseek-proxy/server/api/deps.py`
- Modify: `deepseek-proxy/server/api/routes.py`

- [ ] **Step 1: Write ProxyService**

```python
# server/core/proxy.py
"""ProxyService — orchestrates the full request lifecycle."""

from fastapi import Request
from fastapi.responses import StreamingResponse
from server.core.models import ChatRequest

class ProxyService:
    """Orchestrator: auth → assign → build → stream → persist."""

    def __init__(self, account_svc, auth_svc, prompt_svc, state_svc, stream_svc):
        self.account = account_svc
        self.auth = auth_svc
        self.prompt = prompt_svc
        self.state = state_svc
        self.stream = stream_svc

    async def handle_chat_completion(
        self, req: ChatRequest, raw_request: Request,
    ) -> StreamingResponse:
        """Full request lifecycle."""
        # 1. Extract auth
        acl_payload = await self._extract_auth(raw_request)

        # 2. Build conv key and load state
        conv_uuid = await self.state.get_conv_key(
            req.messages, acl_payload,
            chat_id=req.model, thread_id=req.stream,
        )
        conv_state = await self.state.load_state(conv_uuid)

        # 3. Assign account
        account_idx, session_meta = await self.account.assign(conv_uuid)

        # 4. Build prompt
        prompt = await self.prompt.build_prompt(
            req.messages, req.tools, req.images,
        )

        # 5. Stream response
        watermark_uuid = conv_state.get("watermark", conv_uuid)
        parent_id = conv_state.get("parent_message_id")

        async def event_stream():
            async for chunk in self.stream.generate(
                conv_uuid, account_idx, prompt, req.tools,
                watermark_uuid, parent_id, self.account, self.state,
            ):
                yield chunk

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    async def _extract_auth(self, raw_request: Request) -> dict | None:
        """Extract and verify JWT/ACL from request."""
        # Paste auth extraction logic from server.py
        ...
```

- [ ] **Step 2: Write DI wiring**

```python
# server/api/deps.py
"""FastAPI dependency injection."""

from functools import lru_cache
from server.core.proxy import ProxyService
from server.services.account_service import AccountService
from server.services.auth_service import AuthService
from server.services.prompt_service import PromptService
from server.services.state_service import StateService
from server.services.stream_service import StreamService

@lru_cache
def get_proxy_service() -> ProxyService:
    return ProxyService(
        account_svc=AccountService(),
        auth_svc=AuthService(),
        prompt_svc=PromptService(),
        state_svc=StateService(),
        stream_svc=StreamService(),
    )
```

- [ ] **Step 3: Write routes.py**

```python
# server/api/routes.py
"""FastAPI endpoints."""

from fastapi import APIRouter, Depends, Request
from server.core.models import ChatRequest
from server.core.proxy import ProxyService
from server.api.deps import get_proxy_service

router = APIRouter()

@router.post("/v1/chat/completions")
async def chat_completions(
    req: ChatRequest,
    raw_request: Request,
    svc: ProxyService = Depends(get_proxy_service),
):
    return await svc.handle_chat_completion(req, raw_request)

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/v1/models")
async def list_models():
    return {"data": [{"id": "deepseek-chat", "object": "model"}]}

# Export router for registration in __init__.py
__all__ = ["router"]
```

- [ ] **Step 4: Register router in server/__init__.py**

```python
# Add to server/__init__.py
from server.api.routes import router
app.include_router(router)
```

- [ ] **Step 5: Verify import chain**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -c "from server import app; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/core/proxy.py server/api/ server/__init__.py
git commit -m "feat: add ProxyService orchestrator with DI wiring"
```

---

### Phase 3: Async Migration

### Task 3.1: Convert StateService to full async (batch flush)

**Files:**
- Modify: `deepseek-proxy/server/services/state_service.py`
- Modify: `deepseek-proxy/tests/services/test_state_service.py`

- [ ] **Step 1: Ensure StateService uses asyncio.Lock and batch flush**

Already done in Task 2.2 — verify the implementation:
- `asyncio.Lock` for concurrent access
- `_debounced_flush` using `asyncio.sleep(0.5)`
- Immediate flush after 5 mutations or on `force=True`

- [ ] **Step 2: Add shutdown flush**

```python
# Add to StateService
async def shutdown(self):
    """Flush any pending state on graceful shutdown."""
    async with self._lock:
        if self._dirty:
            await self._flush_to_disk()
```

- [ ] **Step 3: Update test**

```python
@pytest.mark.asyncio
async def test_batch_flush(svc):
    """Verify debounced flush triggers after threshold."""
    await svc.save_state("a", {"data": 1})
    assert svc._mutations == 1
    assert svc._dirty is True
    # Force flush
    await svc.save_state("b", {"data": 2}, force=True)
    assert svc._mutations == 0
```

- [ ] **Step 4: Run tests**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/services/test_state_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/services/state_service.py tests/services/test_state_service.py
git commit -m "feat: full async StateService with batch flush and shutdown"
```

### Task 3.2: Convert AccountService to async

**Files:**
- Modify: `deepseek-proxy/server/services/account_service.py`

- [ ] **Step 1: Convert assign/release to async**

```python
class AccountService:
    async def assign(self, user_hash: str, model: str = "deepseek-chat") -> tuple[int, dict]:
        """Async account assignment with load-aware balancing."""
        # Use asyncio.Lock instead of threading.Lock
        async with self._assign_lock:
            # existing logic from server.py, but now in async context
            ...

    async def release(self, account_idx: int):
        async with self._assign_lock:
            self._pool.release(account_idx)
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/services/account_service.py
git commit -m "feat: convert AccountService to async"
```

### Task 3.3: Convert StreamService to async generator

**Files:**
- Modify: `deepseek-proxy/server/services/stream_service.py`
- Modify: `deepseek-proxy/tests/services/test_stream_service.py`

- [ ] **Step 1: Implement async generate method**

```python
class StreamService:
    async def generate(
        self, conv_uuid: str, account_idx: int, prompt: str,
        tools: list[dict] | None, watermark_uuid: str,
        parent_id: int | str | None, account_service, state_service,
    ) -> AsyncGenerator[str, None]:
        """Async generator for streaming response from DeepSeek."""
        # Paste generate() logic from server.py
        # Use await for state_service calls
        # Use async for HTTP streaming from DeepSeek
        ...
        yield f"data: {chunk}\n\n"
```

- [ ] **Step 2: Write test for stream service**

```python
@pytest.mark.asyncio
async def test_generate_with_mock(svc):
    """Test stream service with a mock DeepSeek response."""
    chunks = []
    async for chunk in svc.generate(...):
        chunks.append(chunk)
    assert len(chunks) > 0
```

- [ ] **Step 3: Run tests**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/services/test_stream_service.py -v -x`
Expected: PASS (or skip if mock is too complex; test can be added in Phase 4)

- [ ] **Step 4: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/services/stream_service.py tests/services/test_stream_service.py
git commit -m "feat: convert StreamService to async generator"
```

### Task 3.4: Wire ProxyService with async services

**Files:**
- Modify: `deepseek-proxy/server/core/proxy.py`
- Modify: `deepseek-proxy/server.php` (actually server.py — add re-exports for new service classes)

- [ ] **Step 1: Ensure ProxyService.handle_chat_completion uses await for all service calls**

```python
async def handle_chat_completion(self, req, raw_request):
    acl_payload = await self._extract_auth(raw_request)
    conv_uuid = await self.state.get_conv_key(...)
    conv_state = await self.state.load_state(conv_uuid)
    account_idx, session_meta = await self.account.assign(conv_uuid)
    prompt = await self.prompt.build_prompt(...)
    # ...streaming returns response...
```

- [ ] **Step 2: Verify tests still pass**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/core/proxy.py
git commit -m "feat: wire ProxyService with async services"
```

---

### Phase 4: Polish

### Task 4.1: Move external modules into utils

**Files:**
- Create: `deepseek-proxy/server/utils/cloudflare.py`
- Modify: `deepseek-proxy/server/utils/helpers.py` (or new file)

- [ ] **Step 1: Copy CloudflareBypasser.py content**

```python
# server/utils/cloudflare.py
"""Cloudflare Turnstile bypass via Playwright."""

# Copy entire CloudflareBypasser.py content here
```

- [ ] **Step 2: Add re-export**

In `server/__init__.py` or server.py:
```python
from server.utils.cloudflare import CloudflareBypasser
```

- [ ] **Step 3: Verify import works**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -c "from server.utils.cloudflare import CloudflareBypasser; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add server/utils/cloudflare.py
git commit -m "feat: move CloudflareBypasser into server/utils/"
```

### Task 4.2: Add new service tests

**Files:**
- Modify: `deepseek-proxy/tests/services/test_prompt_service.py`
- Modify: `deepseek-proxy/tests/services/test_state_service.py`
- Modify: `deepseek-proxy/tests/services/test_stream_service.py`

- [ ] **Step 1: Add comprehensive PromptService tests**

```python
# Add to test_prompt_service.py
@pytest.mark.asyncio
async def test_inject_tools_as_system(svc):
    msgs = [{"role": "system", "content": "You are a helpful assistant."}]
    tools = [
        {
            "function": {
                "name": "Read",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"}
                    },
                    "required": ["file_path"],
                },
            }
        }
    ]
    result = await svc.inject_tools_as_system(msgs, tools)
    assert len(result) == 1
    assert "## Available Tools" in result[0]["content"]
    assert "### Read" in result[0]["content"]

@pytest.mark.asyncio
async def test_trim_context_simple(svc):
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    trimmed = await svc.trim_context(msgs)
    assert len(trimmed) == 3
```

- [ ] **Step 2: Run all tests**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add tests/services/
git commit -m "test: add comprehensive service tests"
```

### Task 4.3: Delete old server.py

**Files:**
- Delete: `deepseek-proxy/server.py`

- [ ] **Step 1: Verify everything works without server.py**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 2: Verify server starts from new entry point**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && timeout 5 python -m server.main --help 2>&1 || true`
Expected: no import errors

- [ ] **Step 3: Delete server.py**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git rm server.py
```

- [ ] **Step 4: Final test run**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git add -A
git commit -m "refactor: remove legacy server.py, finalize package structure"
```

---

## Spec Coverage

| Spec section | Covered by |
|---|---|
| Directory structure | Task 1.1, 1.6 |
| Service interfaces (DI) | Task 2.1-2.4 |
| Async migration | Task 3.1-3.4 |
| Workspace cleanup | Task 0.1-0.2 |
| Module dependency rules | Enforced via imports in Tasks 1.3-1.6, 2.4 |
| Migration phases | Task grouping 0-4 |
| Testing | Tasks 2.1-2.2, 4.2 |
