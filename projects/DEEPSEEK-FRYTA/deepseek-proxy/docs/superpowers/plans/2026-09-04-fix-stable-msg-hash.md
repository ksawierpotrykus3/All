# Fix Stable Message Hash for Resume Continuity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `_msg_hash()` / `_msg_hash_legacy()` produce stable fingerprints across turns so `get_conv()` correctly resumes sessions instead of creating new ones every time git_status or date changes.

**Architecture:** Extend `_clean_content()` in `state_service.py` to strip volatile IDE-injected tags (`<git_status>`, `<open_and_recently_viewed_files>`, `<system_notification>`) and the `Today's date:` line from user messages before hashing. This keeps stable identifiers (workspace path, OS version, system prompt) while removing content that changes every turn.

**Tech Stack:** Python 3.12, pytest, hashlib/sha256

---

## Root Cause

`_msg_hash()` (line 58-94) hashes `system_prompt + first_user_message` as the state lookup key. The first user message from the IDE contains dynamic tags that change every turn:

```
<user_info>
OS Version: win32 10.0.19045
Workspace Path: f:\PROJEKTY\joaxx
Today's date: Friday Sep 4, 2026      ← changes daily
</user_info>
<git_status>
... files changed ...                  ← changes every turn
</git_status>
```

`_clean_content()` only strips `<system-reminder>` and `<rules>` — not these volatile tags. Result: hash changes every turn → `get_conv()` returns None → new DeepSeek session created instead of resuming.

**Evidence:** `conv_state.json` shows parent_id escalating monotonically (2→4→18→34→48→72→84→94→104→118→126→176→178→198) with every entry having a different `user_uuid` — every request creates a new session.

---

### Task 1: Add failing tests for stable hashing

**Files:**
- Create: `tests/test_msg_hash_stability.py`

- [ ] **Step 1: Create test file**

```python
"""tests/test_msg_hash_stability.py

Tests that _msg_hash produces the SAME fingerprint when only volatile
IDE content changes between turns (git_status, date, file lists).
"""
import pytest
from server.services.state_service import _msg_hash, _msg_hash_legacy, _clean_content


SYSTEM_PROMPT = "You are an AI coding assistant, powered by deepseek-v4-pro.\n\nYou are pair programming with a USER."


def _make_messages(user_content: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ── Stable: same hash when only git_status changes ──────────────────────

class TestMsgHashGitStatusStability:
    def test_hash_ignores_git_status_change(self):
        u1_day1 = (
            "<user_info>\n"
            "OS Version: win32 10.0.19045\n"
            "Workspace Path: f:\\PROJEKTY\\joaxx\n"
            "Today's date: Monday Sep 1, 2026\n"
            "</user_info>\n\n"
            "<git_status>\n"
            "On branch main\n"
            "nothing to commit\n"
            "</git_status>"
        )
        u1_day2 = (
            "<user_info>\n"
            "OS Version: win32 10.0.19045\n"
            "Workspace Path: f:\\PROJEKTY\\joaxx\n"
            "Today's date: Tuesday Sep 2, 2026\n"
            "</user_info>\n\n"
            "<git_status>\n"
            "On branch main\n"
            "Changes not staged for commit:\n"
            "  modified:   src/main.py\n"
            "</git_status>"
        )
        h1 = _msg_hash(_make_messages(u1_day1))
        h2 = _msg_hash(_make_messages(u1_day2))
        assert h1 == h2, "Hash must be stable when only date/git_status change"
        assert len(h1) == 16

    def test_hash_ignores_open_files_change(self):
        u1_v1 = (
            "<user_info>\n"
            "OS Version: win32 10.0.19045\n"
            "Workspace Path: f:\\PROJEKTY\\joaxx\n"
            "Today's date: Monday Sep 1, 2026\n"
            "</user_info>\n\n"
            "<git_status>\nOn branch main\nnothing to commit\n</git_status>\n\n"
            "<open_and_recently_viewed_files>\n"
            "- f:\\PROJEKTY\\joaxx\\src\\main.py\n"
            "</open_and_recently_viewed_files>"
        )
        u1_v2 = (
            "<user_info>\n"
            "OS Version: win32 10.0.19045\n"
            "Workspace Path: f:\\PROJEKTY\\joaxx\n"
            "Today's date: Monday Sep 1, 2026\n"
            "</user_info>\n\n"
            "<git_status>\nOn branch main\nnothing to commit\n</git_status>\n\n"
            "<open_and_recently_viewed_files>\n"
            "- f:\\PROJEKTY\\joaxx\\README.md\n"
            "- f:\\PROJEKTY\\joaxx\\tests\\test_main.py\n"
            "</open_and_recently_viewed_files>"
        )
        h1 = _msg_hash(_make_messages(u1_v1))
        h2 = _msg_hash(_make_messages(u1_v2))
        assert h1 == h2, "Hash must be stable when only open_and_recently_viewed_files changes"


# ── Sensitive: different workspace → different hash ─────────────────────

class TestMsgHashWorkspaceSensitivity:
    def test_different_workspace_different_hash(self):
        u1_ws1 = (
            "<user_info>\n"
            "OS Version: win32 10.0.19045\n"
            "Workspace Path: f:\\PROJEKTY\\joaxx\n"
            "Today's date: Monday Sep 1, 2026\n"
            "</user_info>\n\n"
            "<git_status>\nOn branch main\n</git_status>"
        )
        u1_ws2 = (
            "<user_info>\n"
            "OS Version: win32 10.0.19045\n"
            "Workspace Path: f:\\PROJEKTY\\deepseek-proxy\n"
            "Today's date: Monday Sep 1, 2026\n"
            "</user_info>\n\n"
            "<git_status>\nOn branch main\n</git_status>"
        )
        h1 = _msg_hash(_make_messages(u1_ws1))
        h2 = _msg_hash(_make_messages(u1_ws2))
        assert h1 != h2, "Different workspace paths must produce different hashes"


# ── _clean_content strips volatile tags ─────────────────────────────────

class TestCleanContentVolatileStrips:
    def test_strips_git_status_block(self):
        text = "Hello\n<git_status>\nOn branch main\nmodified: foo.py\n</git_status>\nWorld"
        result = _clean_content(text)
        assert "<git_status>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strips_open_files_block(self):
        text = "Hello\n<open_and_recently_viewed_files>\n- foo.py\n</open_and_recently_viewed_files>\nWorld"
        result = _clean_content(text)
        assert "<open_and_recently_viewed_files>" not in result

    def test_strips_system_notification_block(self):
        text = "Hello\n<system_notification>\nTask finished\n</system_notification>\nWorld"
        result = _clean_content(text)
        assert "<system_notification>" not in result

    def test_strips_today_date_line(self):
        text = "OS: win32\nToday's date: Friday Sep 4, 2026\nWorkspace: foo"
        result = _clean_content(text)
        assert "Today's date:" not in result
        assert "OS: win32" in result
        assert "Workspace: foo" in result

    def test_strips_system_reminder_still_works(self):
        text = "Hello\n<system-reminder>\nSome context\n</system-reminder>\nWorld"
        result = _clean_content(text)
        assert "<system-reminder>" not in result

    def test_strips_rules_still_works(self):
        text = "Hello\n<rules>\nSome rules\n</rules>\nWorld"
        result = _clean_content(text)
        assert "<rules>" not in result

    def test_preserves_workspace_path(self):
        text = "<user_info>\nWorkspace Path: f:\\PROJEKTY\\joaxx\nToday's date: Friday Sep 4, 2026\n</user_info>"
        result = _clean_content(text)
        assert "Workspace Path: f:\\PROJEKTY\\joaxx" in result

    def test_preserves_os_version(self):
        text = "<user_info>\nOS Version: win32 10.0.19045\nToday's date: Friday Sep 4, 2026\n</user_info>"
        result = _clean_content(text)
        assert "OS Version: win32 10.0.19045" in result


# ── _msg_hash_legacy also stable ────────────────────────────────────────

class TestMsgHashLegacyStability:
    def test_legacy_hash_ignores_git_status(self):
        u1_v1 = (
            "<user_info>\nWorkspace Path: f:\\PROJEKTY\\joaxx\n"
            "Today's date: Mon Sep 1, 2026\n</user_info>\n"
            "<git_status>\nnothing to commit\n</git_status>"
        )
        u1_v2 = (
            "<user_info>\nWorkspace Path: f:\\PROJEKTY\\joaxx\n"
            "Today's date: Tue Sep 2, 2026\n</user_info>\n"
            "<git_status>\nmodified: foo.py\n</git_status>"
        )
        h1 = _msg_hash_legacy(_make_messages(u1_v1))
        h2 = _msg_hash_legacy(_make_messages(u1_v2))
        assert h1 == h2, "Legacy hash must also be stable across git_status changes"
```

- [ ] **Step 2: Run tests — expect 3+ FAILURES**

Run: `pytest tests/test_msg_hash_stability.py -v`
Expected: `test_hash_ignores_git_status_change`, `test_strips_git_status_block`, `test_strips_today_date_line`, `test_strips_open_files_block`, `test_strips_system_notification_block` FAIL (old `_clean_content` doesn't strip these tags yet).

---

### Task 2: Extend `_clean_content()` to strip volatile IDE tags

**Files:**
- Modify: `server/services/state_service.py:32-55`

- [ ] **Step 1: Update `_clean_content`**

Replace the existing function body (lines 32-55) with:

```python
def _clean_content(content: Any) -> str:
    """Helper to clean volatile IDE-injected content from message texts to ensure stable hashing.

    Strips content that changes between turns (git status, file lists, notifications, dates)
    while preserving stable identifiers (workspace path, OS version).
    """
    if not content:
        return ""
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
        text = " ".join(texts)
    else:
        text = str(content)
    # Strip <system-reminder>...</system-reminder> blocks that IDE injects
    text = re.sub(
        r"<system-reminder>.*?</system-reminder>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip other standard agent tags
    text = re.sub(r"<rules>.*?</rules>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # ── Volatile IDE tags: content changes every turn ──────────────
    # Strip <git_status>...</git_status> (changes on every file save)
    text = re.sub(r"<git_status>.*?</git_status>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip <open_and_recently_viewed_files>...</open_and_recently_viewed_files>
    text = re.sub(
        r"<open_and_recently_viewed_files>.*?</open_and_recently_viewed_files>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip <system_notification>...</system_notification> (dynamic task completions)
    text = re.sub(
        r"<system_notification>.*?</system_notification>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip "Today's date:" line (changes daily)
    text = re.sub(r"Today's date:.*?\n?", "", text)
    return text.strip()
```

- [ ] **Step 2: Run stability tests — expect ALL PASS**

Run: `pytest tests/test_msg_hash_stability.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 3: Run full test suite — expect 0 regressions**

Run: `pytest tests/ -x -q`
Expected: 511+ passed, 2 xfailed, 0 failed.

- [ ] **Step 4: Run py_compile on changed file**

Run: `python -m py_compile server/services/state_service.py`
Expected: OK (no output).

---

### Task 3: Update existing edge-case test expectations (if any)

**Files:**
- Modify: `tests/test_edge_cases_round2.py` (only if needed)

- [ ] **Step 1: Check if any existing tests depend on old `_clean_content` behavior**

Run: `pytest tests/test_edge_cases_round2.py -v -k "hash or clean or state"`
Expected: All pass (existing tests don't test `_clean_content` directly — confirmed by grep).

---

### Task 4: Verify backward compatibility

- [ ] **Step 1: Verify old conv_state.json entries still don't match (expected)**

After the fix, old entries keyed by the unstable hash won't match the new stable hash. This is expected — it's a one-time disruption on the first request after deploying the fix. After that, all entries will use the stable hash.

- [ ] **Step 2: Verify legacy hash path works**

The `_msg_hash_legacy` function also uses `_clean_content`, so it will also produce new stable hashes. Old entries won't match via either path. This is acceptable.

---

### Task 5: Commit

- [ ] **Step 1: Stage and commit**

```bash
git add server/services/state_service.py tests/test_msg_hash_stability.py
git commit -m "fix: strip volatile IDE tags from _clean_content for stable hash

_clean_content now strips <git_status>, <open_and_recently_viewed_files>,
<system_notification> and 'Today's date:' line before hashing. This makes
_msg_hash stable across turns so get_conv correctly resumes sessions.

Previously every turn produced a different hash → new DeepSeek session."
```
