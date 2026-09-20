"""state_service.py — Conversation state via message-hash correlation."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from server.logging import get_logger

logger = get_logger(__name__)

# Local path constants
CONV_STATE_FILE = Path(__file__).parent.parent.parent / "conv_state.json"
_TTL = 86400  # 24h — prevents premature session expiry during long-running multi-turn tool tasks

conv_lock = threading.RLock()
conv_state: dict[str, dict] = {}  # hash → {chat_id, parent_id, account, ts}
chat_state: dict[
    str, dict
] = {}  # chat_id → {parent_id, account, ts} — separate index for resume


_PROXY_CHAT_RE = re.compile(r"<!--\s*PROXY_CHAT:\s*([a-f0-9\-]+)", re.IGNORECASE)
_WORKER_ID_RE = re.compile(r"\[Worker\s+#(\d+|SYSTEM)\]")
_TASK_ID_RE = re.compile(r"task_id:\s*([a-f0-9\-]{36})")  # UUID format

_SYSTEM_REMINDER_RE = re.compile(
    r"<system-reminder>.*?</system-reminder>", re.DOTALL | re.IGNORECASE
)
_RULES_RE = re.compile(r"<rules>.*?</rules>", re.DOTALL | re.IGNORECASE)
_GIT_STATUS_RE = re.compile(r"<git_status>.*?</git_status>", re.DOTALL | re.IGNORECASE)
_OPEN_FILES_RE = re.compile(
    r"<open_and_recently_viewed_files>.*?</open_and_recently_viewed_files>",
    re.DOTALL | re.IGNORECASE,
)
_SYS_NOTIFICATION_RE = re.compile(
    r"<system_notification>.*?</system_notification>", re.DOTALL | re.IGNORECASE
)
_TODAY_DATE_RE = re.compile(r"Today's date:.*\n?")



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
    before_reminder = text[:200]
    text = _SYSTEM_REMINDER_RE.sub("", text)
    after_reminder = text[:200]
    if before_reminder != after_reminder:
        logger.debug(f"[CLEAN] Stripped <system-reminder>: before={before_reminder!r} after={after_reminder!r}")
    # Strip other standard agent tags
    text = _RULES_RE.sub("", text)
    # ── Volatile IDE tags: content changes every turn ──────────────
    # Strip <git_status>...</git_status> (changes on every file save)
    text = _GIT_STATUS_RE.sub("", text)
    # Strip <open_and_recently_viewed_files>...</open_and_recently_viewed_files>
    text = _OPEN_FILES_RE.sub("", text)
    # Strip <system_notification>...</system_notification> (dynamic task completions)
    text = _SYS_NOTIFICATION_RE.sub("", text)
    # Strip "Today's date:" line (changes daily)
    text = _TODAY_DATE_RE.sub("", text)
    return text.strip()


def _msg_hash(messages: list[dict], n: int = 12) -> str:
    """Hash of stable conversation prefix: system + user messages only.

    Produces the SAME hash at save time (before assistant responds) and at
    lookup time (after assistant + tool results are in the history).

    Strategy: hash system + first K non-tool-result user messages with actual content
    that appear BEFORE the first assistant message (Turn 1 prefix).
    Any user messages occurring AFTER the first assistant message are follow-ups (Turn 2, 3...)
    and MUST NOT alter the conversation prefix hash.
    """
    MAX_USERS = 3  # system + first N non-tool-result user messages with content (user_info + user_query + skills)
    stable = []
    user_count = 0
    seen_assistant = False

    for m in messages:
        role = m.get("role", "")
        if role == "assistant":
            seen_assistant = True
            continue
        if role == "tool":
            continue

        raw = m.get("content", "")
        content = _clean_content(raw)
        if role == "system":
            stable.append({"role": role, "content": content})
        elif role == "user":
            if seen_assistant:
                # Follow-up user messages in multi-turn chats must not alter the prefix hash!
                continue
            if content.startswith("<tool_result>"):
                continue  # skip tool results sent as user messages by Trae
            if not content.strip():
                continue  # skip messages that are only system-reminders/rules (dynamic)
            if user_count < MAX_USERS:
                stable.append({"role": role, "content": content})
                logger.debug(f"[MSG_HASH] Added user msg #{user_count}: {content[:100]!r}...")
                user_count += 1

    tail = stable[-n:] if stable else []
    logger.debug(f"[MSG_HASH] Stable messages: {len(stable)}, tail: {len(tail)}")
    if not tail or user_count == 0:
        logger.debug(f"[MSG_HASH] Rejected: user_count={user_count} (requires >= 1 stable user message)")
        return ""
    key = json.dumps(tail, sort_keys=True, ensure_ascii=False)
    result = hashlib.sha256(key.encode()).hexdigest()[:16]
    logger.debug(f"[MSG_HASH] Final hash: {result!r} from {len(tail)} messages")
    return result


def _get_worker_id(messages: list[dict]) -> str | None:
    """Extract worker/subagent ID from message content.
    
    Supports:
    - [Worker #N] format (legacy)
    - task_id: UUID format (Cursor/Kiro subagents)
    """
    logger.debug(f"[WORKER_EXTRACT] Scanning {len(messages)} messages for worker/task_id")
    for m in messages:
        content = m.get("content", "")
        text_to_search = ""
        
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_to_search = part.get("text", "")
                    break
        elif isinstance(content, str):
            text_to_search = content
        
        # Log snippet for debugging
        
        snippet = text_to_search[:150].replace("\n", " ") if text_to_search else "(empty)"
        
        logger.debug(f"[WORKER_EXTRACT] role={m.get('role')!r} content_snippet={snippet!r}")
        
        if not text_to_search:
            continue
        
        # Check [Worker #N] pattern first
        ws = _WORKER_ID_RE.search(text_to_search)
        if ws:
            result = ws.group(0)
            logger.debug(f"[WORKER_EXTRACT] found Worker pattern={result!r} in role={m.get('role')}")
            return result
        
        # Check task_id: UUID pattern (Cursor/Kiro subagents)
        task_match = _TASK_ID_RE.search(text_to_search)
        if task_match:
            task_id = task_match.group(1)
            result = f"task:{task_id[:12]}"  # Truncate UUID to 12 chars
            logger.debug(f"[WORKER_EXTRACT] found task_id={result!r} in role={m.get('role')}")
            return result
    
    logger.debug(f"[WORKER_EXTRACT] no worker/task_id found in {len(messages)} messages")
    return None


def _msg_hash_legacy(messages: list[dict], n: int = 12) -> str:
    """Legacy hash: system + first user message (uses raw when cleaned empty).
    Kept for backward compatibility with states saved before the stability fix.
    """
    MAX_USERS = 1
    stable = []
    user_count = 0
    seen_assistant = False
    for m in messages:
        role = m.get("role", "")
        if role == "assistant":
            seen_assistant = True
            continue
        if role == "tool":
            continue
        raw = m.get("content", "")
        content = _clean_content(raw)
        if role == "system":
            stable.append({"role": role, "content": content})
        elif role == "user":
            if seen_assistant:
                continue
            if content.startswith("<tool_result>"):
                continue
            if not content.strip():
                continue
            if user_count < MAX_USERS:
                stable.append({"role": role, "content": content})
                user_count += 1

    tail = stable[-n:] if stable else []
    logger.debug(f"[MSG_HASH] Stable messages: {len(stable)}, tail: {len(tail)}")
    if not tail or user_count == 0:
        return ""
    key = json.dumps(tail, sort_keys=True, ensure_ascii=False)
    result = hashlib.sha256(key.encode()).hexdigest()[:16]
    logger.debug(f"[MSG_HASH] Final hash: {result!r} from {len(tail)} messages")
    return result


def get_conv(messages: list[dict]) -> dict | None:
    """Return existing conversation state if hash matches and not expired.

    Lookup order:
    1. Hash match: system + user messages fingerprint (new stable algorithm)
    2. Legacy hash match: backward compatibility with states saved before fix
    3. Watermark extraction: PROXY_CHAT from assistant content

    Sub-worker detection: if the state entry was saved with a worker_id
    and the current request has a DIFFERENT worker_id (or no worker_id),
    the hash match is rejected — sub-workers get their own DeepSeek session.

    Returns None for new sessions (no fallback to last active session).
    """
    # Check if conv_state.json was modified on disk externally
    try:
        if CONV_STATE_FILE.exists():
            mtime = CONV_STATE_FILE.stat().st_mtime
            if mtime > _last_mtime:
                load_conv_state()
    except Exception:
        pass

    logger.debug(f"[GET_CONV] Called with {len(messages)} messages")
    if len(messages) < 2:
        return None

    # 1. Hash match on stable prefix (system + first non-empty user message)
    h = _msg_hash(messages)
    logger.debug(f"[GET_CONV] Calculated hash: {h!r}")
    if h:
        with conv_lock:
            entry = conv_state.get(h)
        if entry and time.time() - entry["ts"] < _TTL:
            # ── Sub-worker guard ────────────────────────────────────
            if entry.get("worker_id"):
                current_wid = _get_worker_id(messages)
                logger.debug(f"[WORKER_GUARD] stored={entry.get('worker_id')!r} current={current_wid!r}")
                if current_wid != entry["worker_id"]:
                    logger.debug(f"[WORKER_GUARD] REJECT - different worker → new session")
                    return None  # different sub-worker → new session
            return entry

    # 2. Legacy hash match (backward compatibility)
    h_legacy = _msg_hash_legacy(messages)
    if h_legacy and h_legacy != h:
        with conv_lock:
            entry = conv_state.get(h_legacy)
        if entry and time.time() - entry["ts"] < _TTL:
            if entry.get("worker_id"):
                current_wid = _get_worker_id(messages)
                logger.debug(f"[WORKER_GUARD LEGACY] stored={entry.get('worker_id')!r} current={current_wid!r}")
                if current_wid != entry["worker_id"]:
                    logger.debug(f"[WORKER_GUARD LEGACY] REJECT - different worker")
                    return None
            return entry

    # 3. Watermark from assistant content
    for m in reversed(messages):
        if m.get("role") == "assistant":
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content if p.get("type") == "text"
                )
            match = _PROXY_CHAT_RE.search(str(content))
            if match:
                chat_id = match.group(1)
                with conv_lock:
                    entry = chat_state.get(chat_id)
                if entry and time.time() - entry["ts"] < _TTL:
                    return entry

    logger.debug("[GET_CONV] No match found - returning None (NEW SESSION)")
    return None




def clear_conv_by_messages(messages: list[dict]) -> str | None:
    """Clear conversation state for given messages.
    
    Used when DeepSeek session hits context limit — next retry must create 
    a NEW session instead of resume.
    
    Returns the cleared hash if found, None otherwise.
    """
    h = _msg_hash(messages)
    if not h:
        return None
    
    cleared = False
    with conv_lock:
        if h in conv_state:
            chat_id = conv_state[h].get("chat_id")
            del conv_state[h]
            if chat_id and chat_id in chat_state:
                del chat_state[chat_id]
            logger.info(f"[CLEAR_CONV] Cleared state for hash={h!r} chat_id={chat_id!r}")
            cleared = True

    if cleared:
        _flush_conv_state()
        return h
    
    logger.debug(f"[CLEAR_CONV] Hash {h!r} not in state, nothing to clear")
    return None
def set_conv(
    messages: list[dict],
    chat_id: str,
    parent_id,
    account: int,
    user_uuid: str = "",
    model_type: str | None = None,
    thinking_enabled: bool | None = None,
    search_enabled: bool | None = None,
    tools: list | None = None,
) -> None:
    """Save or update conversation state keyed by message hash and chat_id."""
    h = _msg_hash(messages)
    now = time.time()
    worker_id = _get_worker_id(messages)
    with conv_lock:
        if h:
            conv_state[h] = {
                "chat_id": chat_id,
            "parent_id": parent_id,
            "account": account,
            "user_uuid": user_uuid,
            "worker_id": worker_id,
            "model_type": model_type,
            "thinking_enabled": thinking_enabled,
            "search_enabled": search_enabled,
            "tools": tools,
            "ts": now,
        }
        chat_state[chat_id] = {
            "parent_id": parent_id,
            "account": account,
            "user_uuid": user_uuid,
            "worker_id": worker_id,
            "model_type": model_type,
            "thinking_enabled": thinking_enabled,
            "search_enabled": search_enabled,
            "tools": tools,
            "ts": now,
        }
    _flush_conv_state()


_last_mtime: float = 0.0


def load_conv_state() -> None:
    """Load conversation state from disk at startup or external change."""
    global conv_state, chat_state, _last_mtime
    try:
        if CONV_STATE_FILE.exists():
            _last_mtime = CONV_STATE_FILE.stat().st_mtime
            data = json.loads(CONV_STATE_FILE.read_text(encoding="utf-8"))
            now = time.time()
            with conv_lock:
                conv_state = {
                    k: v for k, v in data.items() if now - v.get("ts", 0) < _TTL
                }
                chat_state = {}
                for entry in conv_state.values():
                    c_id = entry.get("chat_id")
                    if c_id:
                        chat_state[c_id] = entry
    except Exception as e:
        logger.error(f"[STATE] load failed: {e}")


def _flush_conv_state() -> None:
    global _last_mtime
    with conv_lock:
        data = dict(conv_state)
    try:
        CONV_STATE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if CONV_STATE_FILE.exists():
            _last_mtime = CONV_STATE_FILE.stat().st_mtime
    except Exception as e:
        logger.error(f"[STATE] save failed: {e}")
