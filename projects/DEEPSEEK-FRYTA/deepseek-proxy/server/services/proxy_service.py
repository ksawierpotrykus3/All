"""proxy_service.py — Thin ProxyService orchestrator.

Uses the new components (InputParser, PromptBuilder, StreamHandler)
instead of inline logic from the legacy proxy.py.
"""

from __future__ import annotations

import asyncio
import datetime
import inspect
import json
import random
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Generator

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from server.core.deepseek_client import ap, ds, DeepSeekRateLimitError
from server.config import (
    MAX_ACCOUNTS,
    MAX_PARALLEL_TOOL_CALLS,
    MAX_SESSIONS_PER_ACCOUNT,
    WATERMARK_ENABLED,
)
from server.logging import get_logger

logger = get_logger(__name__)
from server.services.state_service import (
    conv_lock,
    conv_state,
    get_conv,
    set_conv,
    load_conv_state,
)
from server.core.input_parser import InputParser
from server.core.prompt_builder import PromptBuilder
from server.core.stream_handler import StreamHandler, ToolMgr, detect_repetition_loop
from server.core.image_processor import extract_images_from_messages
from server.utils.helpers import _chunk as _chunk_fn, _ensure_valid_json
from server.dashboard.instrumentor import DashboardInstrumentor
from server.services.session_manager import session_manager
from server.services.account_selector import account_selector
from server.services.rate_limiter import rate_limiter
from server.core.mcp_catalog import build_mcp_catalog
from server.services.prompt_chunker import (
    split_prompt_payload,
    PROMPT_CHUNK_THRESHOLD,
)
from server.services.document_attachment_service import (
    extract_oversized_blocks_to_attachments,
    create_history_attachments,
)

# Global dashboard instrumentor instance
_dashboard = DashboardInstrumentor()

_DRAIN_TIMEOUT = 5.0


_INTENT_ACTION_RE = re.compile(
    r"(?i)\b("
    # Badanie, dociekanie, kopanie, odczyt, wyszukiwanie, parsowanie
    r"sprawdz[aęą]m?|zbadam?|badam|kopi[eę]|kop|pokopi[eę]|dr[aą][zż][eę]|dr[aą][zż]|"
    r"dociekam|zg[łl][eę]bi[aę]m?|zagl[aą]dam|zagl[aą]dn[eę]|wchodz[eę]|spojrz[eę]|patrz[eę]|wracam|"
    r"przeszuk[aą]m?|szukam|czytam|odczytu?j[ęe]|"
    r"parsuj[ęe]|wyci[aą]g[aęą]m?|przeanalizuj[eę]|analizuj[eę]|inspekcjonuj[eę]|"
    # Cząstkowe odkrycia, hipotezy i status updates bez wykonania akcji
    r"znalaz[łl][a-ząćęłńóśźż]*|odkry[łl][a-ząćęłńóśźż]*|okaza[łl]o\s+si[eę]|mam\s+hipotez[eę]|"
    r"zauwa[żz]y[łl][a-ząćęłńóśźż]*|widz[eę]\s+(problem|b[łl][aą]d|przyczyn|rozwi[aą]zanie)|"
    r"found\s+(something|an?\s+issue|a\s+bug)|discovered|"
    # Naprawa, poprawki, modyfikacja, usuwanie, czyszczenie
    r"naprawi[aę]m?|poprawi[aę]m?|usuw[aęą]m?|usun[eę]|kasuj[eę]|porz[aą]dkuj[eę]|"
    r"uporz[aą]dkuj[eę]|sprz[aą]t[aęą]m?|czyszcz[eę]|zmieni[aę]m?|zmieni[eę]|"
    r"zmodyfikuj[eę]|modyfikuj[eę]|edytuj[eę]|aktualizuj[eę]|zoptymalizuj[eę]|"
    r"optymalizuj[eę]|przepisuj[eę]|przepisz[eę]|podmieniam|podmieni[eę]|"
    r"zamieniam|zamieni[eę]|wdra[zż]am|wdro[zż][eę]|"
    # Tworzenie, zapis, dodawanie, uruchamianie, testowanie
    r"tworz[eę]|stworz[eę]|utw[oó]rz[eę]|generuj[eę]|wygeneruj[eę]|zapisz[eę]|"
    r"zapisuj[eę]|dodaj[eę]|dodam|uruchami?am|odpal[aęą]m?|odpal[eę]|puszcz[aęą]m?|"
    r"puszcz[eę]|doka[nń]czam|doko[nń]cz[eę]|wznawiam|kontynuuj[eę]|"
    r"testuj[eę]|przetestuj[eę]|weryfikuj[eę]|zweryfikuj[eę]|dzia[łl]am|"
    # Delegowanie, zlecanie, subagenci
    r"deleguj[aęą]m?|oddelegowuj[aęą]m?|oddeleguj[eę]|zlec[aęą]m?|zleci[aę]m?|"
    r"przekazuj[aęą]m?|przeka[zż][eę]|powo[łl]uj[aęą]m?|powo[łl]am|"
    # Frazy czasu/przejścia w języku polskim
    r"zaraz|za chwil[eę]|w nast[eę]pnym kroku|w kolejnym kroku|nast[eę]pnie|"
    r"przechodz[eę]|zajmuj[eę]|robimy|zrobi[eę]|robi[eę]|"
    # Język angielski
    r"let me|i will|i'll|let's|lets|going to|about to|"
    r"reading|checking|searching|inspecting|running|parsing|"
    r"fixing|repairing|removing|deleting|cleaning|updating|editing|"
    r"modifying|creating|generating|saving|writing|adding|testing|"
    r"verifying|optimizing|rewriting|replacing|"
    r"dig|digging|digs|delv(e|ing)|investigat(e|ing)|explor(e|ing)|"
    r"delegat(e|ing)|assign(ing)?|dispatch(ing)?"
    r")\b"
)


def _is_intent_without_action(text: str) -> bool:
    """Return True if model emitted a statement of intent or action description without tool calls."""
    s = text.strip()
    if not s:
        return False
    if "FINAL ANSWER:" in s:
        return False
    # Check if whole text matches intent keywords
    if len(s) <= 600 and _INTENT_ACTION_RE.search(s):
        return True
    # For longer texts, check if the concluding tail (last 300 chars) expresses intent
    tail = s[-300:]
    if _INTENT_ACTION_RE.search(tail):
        return True
    # Check words in the concluding tail (last 150 chars) for active first-person verbs
    # Handles structures like "Kopię głębiej.", "Badam to dalej.", "Naprawiam plik."
    tail_words = re.findall(r"(?i)\b([a-ząćęłńóśźż]+)\b", s[-150:])
    for w in tail_words:
        w_lower = w.lower()
        if re.search(r"(?i)(am|em|ę|e)$", w_lower) and len(w_lower) >= 3:
            if any(w_lower.startswith(prefix) for prefix in (
                "kop", "drąż", "draz", "dociek", "zgleb", "zgłęb", "bad", "sprawdz",
                "napraw", "popraw", "usuw", "usun", "zmien", "edyt", "dod", "tworz",
                "rob", "pisz", "czyszcz", "porz", "odpal", "puszcz", "deleg", "oddeleg",
                "zlec", "przekaz", "powol", "zaglad", "zagląd", "patrz", "weryfik"
            )):
                return True
    return False


def _is_response_truncated(text: str, stream_meta: dict | None = None) -> bool:
    """Return True if model response was truncated (incomplete SSE, open code fences, or unclosed XML tags)."""
    if stream_meta and not stream_meta.get("is_finished", True):
        return True
    s = text.strip() if text else ""
    if not s:
        return False
    # Check for unclosed markdown code block (odd count of ```)
    code_fences = len(re.findall(r"(?<!`)```{1,}(?!`)", s))
    if code_fences % 2 != 0:
        return True
    # Check for unclosed tool call XML tags (using word boundaries to avoid matching <tool_calls as <tool_call)
    open_invokes = len(re.findall(r"<invoke\b", s, re.IGNORECASE))
    close_invokes = len(re.findall(r"</invoke\s*>", s, re.IGNORECASE))
    if open_invokes > close_invokes:
        return True

    open_tcalls = len(re.findall(r"<tool_calls\b", s, re.IGNORECASE))
    close_tcalls = len(re.findall(r"</tool_calls\s*>", s, re.IGNORECASE))
    if open_tcalls > close_tcalls:
        return True

    open_tcall = len(re.findall(r"<tool_call\b", s, re.IGNORECASE))
    close_tcall = len(re.findall(r"</tool_call\s*>", s, re.IGNORECASE))
    if open_tcall > close_tcall:
        return True
    return False



def _tc_id(conv_uuid: str = "") -> str:
    if conv_uuid:
        return f"call_sid:{conv_uuid}_{uuid.uuid4().hex[:8]}"
    return f"call_{uuid.uuid4().hex[:8]}"


def _build_tc_list(found_calls: list[dict], conv_uuid: str) -> list[dict]:
    result = []
    for idx, tc in enumerate(found_calls[:10]):
        if "function" in tc:
            fn = tc["function"]
            args_raw = fn.get("arguments", "{}")
            # Wrap in try/except to diagnose serialization truncation
            args_serialized = _ensure_valid_json(args_raw)
            logger.info(
                f"[TC_BUILD] call[{idx}] name={fn.get('name', '?')} raw_args_len={len(str(args_raw))} serialized_len={len(args_serialized)}"
            )
            result.append(
                {
                    "index": idx,
                    "id": tc.get("id", _tc_id(conv_uuid)),
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "arguments": args_serialized,
                    },
                }
            )
        else:
            args_raw = tc.get("arguments", "{}")
            args_serialized = _ensure_valid_json(args_raw)
            logger.info(
                f"[TC_BUILD] call[{idx}] name={tc.get('name', '?')} raw_args_len={len(str(args_raw))} serialized_len={len(args_serialized)}"
            )
            result.append(
                {
                    "index": idx,
                    "id": tc.get("id", _tc_id(conv_uuid)),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": args_serialized,
                    },
                }
            )
    return result


def _repair_empty_tc_args(
    found_calls: list[dict] | None,
    tools: list[dict] | None,
) -> list[dict]:
    """Drop tool calls whose arguments are empty/missing BEFORE they reach the IDE.

    Regression for the dominant failure mode in server_stdout.log: DeepSeek
    emits ``<invoke name="Write">`` with no ``<parameter>`` blocks, the parser
    returns ``arguments: "{}"``, and the IDE rejects the call with
    ``Invalid arguments: path: Required`` (433 hits, 402 ``path: Required``).

    Malformed calls are removed with a loud ``[TOOL_ARGS_WARN]`` diagnostic so
    the IDE never sees a spurious rejection and the model retries on the next
    turn.  We deliberately do NOT fabricate values for required parameters
    (e.g. ``Write.path``/``contents``) — guessing could corrupt the user's work.

    The helper is exception-safe: if inspecting a call raises, the call is kept
    so a single malformed entry never crashes the whole stream generator.
    """
    if not found_calls:
        return []
    result: list[dict] = []
    dropped = 0
    for idx, tc in enumerate(found_calls):
        try:
            if isinstance(tc, dict) and "function" in tc:
                fn = tc["function"] or {}
                args_raw = fn.get("arguments", "")
                name = fn.get("name", "?")
                # Fallback: parser puts arguments at top-level, not inside
                # function dict.  ToolMgr.validate() may add function={}
                # with only name, leaving arguments at tc["arguments"].
                if not args_raw or args_raw.strip() in ("", "{}"):
                    args_raw = tc.get("arguments", "{}")
            elif isinstance(tc, dict):
                args_raw = tc.get("arguments", "{}")
                name = tc.get("name", "?")
            else:
                # Un-inspectable entry — keep it, don't crash the stream.
                result.append(tc)
                continue
            if isinstance(args_raw, str):
                empty = args_raw.strip() in ("", "{}")
            elif isinstance(args_raw, dict):
                empty = not args_raw
            else:
                empty = False
            if empty:
                dropped += 1
                logger.warning(
                    f"[TOOL_ARGS_WARN] call[{idx}] name={name} dropped: empty arguments "
                    f"({args_raw!r}) — model likely emitted <invoke> without <parameter> blocks"
                )
                continue
            result.append(tc)
        except Exception as e:  # pragma: no cover - defensive
            logger.exception(
                f"[TOOL_ARGS_WARN] call[{idx}] inspection failed, keeping call: {e}"
            )
            result.append(tc)
    if dropped:
        logger.warning(
            f"[TOOL_ARGS_WARN] dropped {dropped}/{len(found_calls)} empty-argument tool call(s)"
        )
    return result


def _save_state(
    messages: list[dict],
    stream_meta: dict,
    parent_id: str | None,
    chat_id: str,
    conv_uuid: str,
    account_idx: int,
    tools: list[dict] | None,
    text_buffer: str,
    user_uuid: str = "",
    model_type: str | None = None,
    thinking_enabled: bool | None = None,
    search_enabled: bool | None = None,
) -> None:
    new_parent_id = stream_meta.get("resp_msg_id") or parent_id
    set_conv(
        messages,
        chat_id,
        new_parent_id,
        account_idx,
        user_uuid=user_uuid,
        model_type=model_type,
        thinking_enabled=True if thinking_enabled is None else thinking_enabled,
        search_enabled=False if search_enabled is None else search_enabled,
        tools=tools,
    )


# ── Extract messages for PromptBuilder ────────────────────────────────────────


def _extract_text_content(content: Any) -> str:
    """Extract plain text from message content (str or list of parts, OpenAI format)."""
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
        return "\n".join(texts)
    return str(content) if content else ""


def _extract_prompt_parts(msgs: list[dict], is_resume: bool = False) -> tuple[str | None, list[dict], str]:
    """Extract (system_prompt, history, user_message) from preprocessed messages."""
    _WATERMARK_RE = re.compile(
        r"<!--\s*PROXY_CHAT:\s*[a-f0-9\-]+(?:\s*\|\s*PROXY_UUID:\s*[a-f0-9\-]+)?\s*-->",
        re.IGNORECASE,
    )
    _SYS_REMINDER_RE = re.compile(
        r"<system-reminder>.*?</system-reminder>", re.DOTALL | re.IGNORECASE
    )
    _SYS_REMINDER_TAG_RE = re.compile(r"</?system-reminder[^>]*>", re.IGNORECASE)
    system_prompt = None
    history: list[dict] = []

    # Find last user message index
    last_user_idx = -1
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "user":
            last_user_idx = i
            break

    user_message = ""
    for i, m in enumerate(msgs):
        role = m.get("role", "")
        content = _extract_text_content(m.get("content", ""))

        if role == "system":
            system_prompt = content
        elif i == last_user_idx:
            # ── Last user message: always keep full content in user_message ──
            user_message = content
            # Fallback: extract <system-reminder> as system_prompt ONLY when
            # no role: system exists (e.g. Trae sends it differently).
            if not system_prompt:
                sys_match = _SYS_REMINDER_RE.search(content)
                if sys_match:
                    sys_cleaned = _SYS_REMINDER_TAG_RE.sub(
                        "", sys_match.group(0)
                    ).strip()
                    if sys_cleaned:
                        system_prompt = sys_cleaned
        elif role == "assistant":
            # Keep assistant content + tool calls in history so the model
            # sees its own previous tool calls as in-context learning examples
            content_stripped = _WATERMARK_RE.sub("", content).strip()
            tool_calls = m.get("tool_calls")
            if tool_calls:
                history.append(
                    {
                        "role": "assistant",
                        "content": content_stripped,
                        "tool_calls": tool_calls,
                    }
                )
            else:
                history.append({"role": "assistant", "content": content_stripped})
        elif role == "tool":
            # Use standard DSML tool_result format instead of fake user message.
            # No truncation: Trae IDE already controls content size, and the model
            # specifies via tool arguments how much it wants to receive.
            tool_name = m.get("name", "tool")
            tc_id = m.get("tool_call_id", "")
            result_tag = f"<tool_result>\n<t>{tool_name}</t>\n<id>{tc_id}</id>\n<content>\n{content}\n</content>\n</tool_result>"
            history.append({"role": "assistant", "content": result_tag})
        elif role == "user":
            # ── Non-last user message: skip system-reminders, detect tool_results ──
            if _SYS_REMINDER_RE.search(content):
                # Trae system-reminder in history — no longer needed,
                # it was already sent as system_prompt on first turn
                continue
            if content.strip().startswith("<tool_result>"):
                history.append({"role": "assistant", "content": content.strip()})
            else:
                history.append({"role": "user", "content": content})

    if not user_message and history:
        user_message = history.pop()["content"]

    # ── NEW-SESSION FIX ────────────────────────────────────────────────────────
    # IDE sometimes sends multiple consecutive user messages before the first
    # assistant reply (e.g. [user_info, user_query]). _extract_prompt_parts treats
    # the LAST one as user_message and pushes earlier ones into history as role:user.
    # On a brand-new session there are NO assistant/tool turns yet, so history must
    # be empty — all user content belongs in user_message so PromptBuilder includes
    # it with system_prompt and tools_schema in the initial prompt.
    #
    # CRITICAL: This fix MUST ONLY run for brand-new sessions (not is_resume)!
    # In resume mode (is_resume=True), multiple user messages in delta must NOT be merged
    # into a duplicated prompt.
    if history:
        _roles = [msg.get('role', "?") for msg in history]
        logger.info(f"[NEW_SESSION_DEBUG] is_resume={is_resume} history_len={len(history)} roles={_roles[:10]}")
    else:
        logger.info(f"[NEW_SESSION_DEBUG] is_resume={is_resume} history is empty")
    if not is_resume and history and all(msg.get('role') == 'user' for msg in history):
        all_user_parts = [msg['content'] for msg in history] + ([user_message] if user_message else [])
        user_message = '\n\n'.join(p for p in all_user_parts if p)
        logger.info(
            f'[NEW_SESSION_FIX] merged {len(all_user_parts)} consecutive user messages '
            f'into single user_message (history cleared)'
        )
        history = []

    return system_prompt, history, user_message


def _select_least_loaded_account(exclude_slot: int | None = None) -> int:
    """Select the least loaded valid account that is not currently rate-limited.

    Prefers accounts other than exclude_slot if available.
    Sorts candidates by:
    1. Is excluded slot (0 for other accounts, 1 for excluded slot)
    2. Active session count on that account
    3. Last request timestamp (earliest timestamp = longest idle time)
    """
    now_ac = time.time()
    candidates = []
    for i in range(MAX_ACCOUNTS):
        if not ap.is_valid(i):
            continue
        if now_ac < rate_limiter.get_until(i):
            continue
        is_excluded = (exclude_slot is not None and i == exclude_slot)
        last_req = ds._last_request_time[i] if i < len(ds._last_request_time) else 0.0
        sess_cnt = session_manager.get_count(i)
        candidates.append((1 if is_excluded else 0, sess_cnt, last_req, i))

    if not candidates:
        valid = [i for i in range(MAX_ACCOUNTS) if ap.is_valid(i)]
        return valid[0] if valid else (exclude_slot if exclude_slot is not None else 0)

    candidates.sort()
    return candidates[0][3]


def _prepare_new_session_payload(
    target_slot: int,
    messages: list[dict],
    tools: list[dict] | None = None,
    model_type: str = "default",
) -> tuple[str, list[str]]:
    """Builds prompt for brand-new session (or rollover/migrate) with full prior conversation

    history attached as `conversation_history.md` (via ref_file_ids) rather than bloating the prompt.
    """
    from server.services.document_attachment_service import (
        create_history_attachments,
        extract_oversized_blocks_to_attachments,
    )
    from server.services.prompt_chunker import PROMPT_CHUNK_THRESHOLD
    from server.core.prompt_builder import PromptBuilder

    system_prompt, history, user_message = _extract_prompt_parts(messages, is_resume=False)
    doc_attachments: list[dict] = []

    if history:
        has_prior_dialogue = any(
            h.get("role") in ("assistant", "tool") for h in history
        ) or len(history) > 1
        if has_prior_dialogue:
            logger.info(
                f"[PREPARE_NEW_SESSION] Packaging {len(history)} prior history entries into conversation_history.md for slot={target_slot}"
            )
            hist_docs = create_history_attachments(history)
            if hist_docs:
                doc_attachments.extend(hist_docs)
                doc_names = ", ".join(d["filename"] for d in hist_docs)
                hist_note = (
                    f"[Full prior conversation history from IDE ({len(history)} turns) is attached in document(s): {doc_names}. "
                    f"Please carefully review the attached history to understand prior context and fulfill the user's latest request below.]\n\n"
                )
                user_message = hist_note + (user_message or "")
            history = []
        else:
            user_parts_from_history = [
                h["content"] for h in history if h.get("role") == "user" and h.get("content")
            ]
            if user_parts_from_history:
                user_message = "\n\n".join(
                    user_parts_from_history + ([user_message] if user_message else [])
                )
            history = []

    prompt = PromptBuilder.build(
        user_message=user_message or "",
        system_prompt=system_prompt,
        history=None,
        tools_schema=tools if tools else None,
    )

    if len(prompt) > PROMPT_CHUNK_THRESHOLD:
        try:
            lean_prompt, docs = extract_oversized_blocks_to_attachments(prompt)
            if docs:
                prompt = lean_prompt
                doc_attachments.extend(docs)
        except Exception as de:
            logger.warning(f"[PREPARE_NEW_SESSION] Attachment extraction failed: {de}")

    uploaded_file_ids: list[str] = []
    if doc_attachments:
        logger.info(
            f"[PREPARE_NEW_SESSION] Uploading {len(doc_attachments)} document attachment(s) for slot={target_slot}..."
        )
        for doc in doc_attachments:
            try:
                dfid = ds.upload_file(
                    slot=target_slot,
                    file_data=doc["data"],
                    filename=doc["filename"],
                    mime_type=doc["mime_type"],
                    model_type=model_type,
                )
                uploaded_file_ids.append(dfid)
            except Exception as ue:
                logger.error(f"[PREPARE_NEW_SESSION] Failed uploading document {doc.get('filename')}: {ue}")

    return prompt, uploaded_file_ids


# ── Stream generator ──────────────────────────────────────────────────────────


def _stream_gen(
    *,
    stream_gen: Any,
    stream_meta: dict,
    messages: list[dict],
    parent_id: str | None,
    chat_id: str,
    conv_uuid: str,
    account_idx: int,
    tools: list[dict] | None,
    model: str,
    t0: float,
    t4: float,
    prompt: str = "",
    user_uuid: str = "",
    stop: list[str] | str | None = None,
    model_type: str | None = None,
    thinking_enabled: bool | None = None,
    search_enabled: bool | None = None,
    ref_file_ids: list[str] | None = None,
    _depth: int = 0,
    _reprompt_depth: int = 0,
    _rollover_depth: int = 0,
    _rate_retry: int = 0,
) -> Generator[str, None, None]:
    """Consume DeepSeek stream, detect tool calls via StreamHandler, yield SSE.

    ``_depth`` guards recursive retry re-entry (STREAM MIGRATE / STREAM
    BACKOFF re-call this generator with a fresh stream so retried tokens go
    through the same StreamHandler/sieve pipeline as the main loop).
    ``_reprompt_depth`` tracks auto-reprompt recursion independently.
    ``_rollover_depth`` tracks session rollover recursion.
    """
    global _dashboard
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def _chunk(delta: dict, fr: str | None = None, sid: str | None = None) -> str:
        return _chunk_fn(completion_id, created, model, delta, fr, sid)

    mcp_catalog = build_mcp_catalog(messages)
    tool_names = [t.get("function", t).get("name", "") for t in (tools or [])]
    handler = StreamHandler(tool_names=tool_names, mcp_catalog=mcp_catalog)
    text_buffer = ""
    yield_buffer = ""
    text_yielded_len = (
        0  # how many chars from text_buffer have been yielded (via flush)
    )
    _ttft: float | None = None
    _ttft_ms: float | None = None

    try:
        for text_chunk in stream_gen:
            if _ttft is None:
                _ttft = time.time()
                _ttft_ms = (_ttft - t4) * 1000
                logger.info(
                    f"[TIMING] ttft: {_ttft - t4:.3f}s (total: {_ttft - t0:.1f}s)"
                )
            if not text_chunk:
                continue

            text_buffer += text_chunk

            # Repetition loop guard (stops runaway autoregressive repetition loops)
            rep_pattern = detect_repetition_loop(text_buffer)
            if rep_pattern:
                logger.warning(
                    f"[REPETITION_GUARD] Degenerate repetition loop detected in stream! "
                    f"Pattern: {rep_pattern!r}. Aborting stream to protect client."
                )
                break

            # Stop sequence check
            if stop:
                stop_list = [stop] if isinstance(stop, str) else stop
                for seq in stop_list:
                    idx = text_buffer.find(seq)
                    if idx >= 0:
                        text_buffer = text_buffer[:idx]
                        # Yield only the UNYIELDED portion of text_buffer.
                        # text_yielded_len tracks chars already sent to client
                        # (via flush at line 314-317). text_buffer[text_yielded_len:]
                        # gives exactly the new text before the stop,
                        # avoiding DUPLICATION of already-yielded content.
                        new_content = text_buffer[text_yielded_len:]
                        if new_content:
                            yield _chunk({"content": new_content})
                        yield _chunk({}, fr="stop")
                        yield "data: [DONE]\n\n"
                        return

            try:
                events = handler.feed(text_chunk)
            except Exception as _feed_err:  # pragma: no cover - defensive
                # A single malformed chunk must not crash the stream or trigger
                # the whole-stream retry/migration path. Swallow and continue.
                logger.exception(
                    f"[FEED_ERROR] handler.feed raised for {len(text_chunk)}-char chunk; "
                    f"skipping chunk (remaining tool calls may be lost): {_feed_err}"
                )
                events = []

            # ── Diagnostic: log event types from handler ──
            if events:
                _etypes = [e["type"] for e in events]
                if "tool_calls" in _etypes:
                    logger.info(
                        f"[HANDLER_EVENTS] ✅ tool_calls detected! events={_etypes}"
                    )
                elif events and len(text_chunk) < 200:
                    logger.info(
                        f"[HANDLER_EVENTS] events={_etypes} chunk={text_chunk[:150]!r}"
                    )

            for event in events:
                if event["type"] == "tool_calls":
                    logger.info(
                        f"[DETECT_TOOL] {len(event['data'])} call(s) from handler (limit={MAX_PARALLEL_TOOL_CALLS})"
                    )
                    if yield_buffer:
                        yield _chunk({"content": yield_buffer})
                        text_yielded_len += len(yield_buffer)
                        yield_buffer = ""

                    found_calls = list(event["data"][:MAX_PARALLEL_TOOL_CALLS])

                    # Drain remaining stream for additional tool calls
                    if len(event["data"]) < MAX_PARALLEL_TOOL_CALLS:
                        _drain_start = time.time()
                        for remaining_chunk in stream_gen:
                            if time.time() - _drain_start > _DRAIN_TIMEOUT:
                                logger.info(
                                    f"[DRAIN TIMEOUT] exceeded {_DRAIN_TIMEOUT}s"
                                )
                                break
                            if not remaining_chunk:
                                continue
                            text_buffer += remaining_chunk
                            try:
                                _drain_events = handler.feed(remaining_chunk)
                            except (
                                Exception
                            ) as _drain_err:  # pragma: no cover - defensive
                                logger.exception(
                                    f"[FEED_ERROR] handler.feed raised during drain; "
                                    f"skipping chunk: {_drain_err}"
                                )
                                _drain_events = []
                            for de in _drain_events:
                                if (
                                    de["type"] == "tool_calls"
                                    and len(found_calls) < MAX_PARALLEL_TOOL_CALLS
                                ):
                                    remaining_slots = MAX_PARALLEL_TOOL_CALLS - len(
                                        found_calls
                                    )
                                    found_calls.extend(
                                        list(de["data"][:remaining_slots])
                                    )
                                    break

                    logger.info(f"[DETECT_TOOL] {len(found_calls)} call(s) after drain")

                    # Check if model signaled completion via FINAL ANSWER
                    completed = handler._found_final_answer
                    if not completed:
                        logger.info(
                            f"[COMPLETION_CHECK] tool calls emitted but no FINAL ANSWER marker — model may not be done"
                        )

                    # Drop empty-argument tool calls before they reach the IDE
                    # (dominant failure: model emits <invoke> with no <parameter>).
                    try:
                        found_calls = _repair_empty_tc_args(found_calls, tools)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.exception(
                            f"[TOOL_ARGS_WARN] repair step failed, using raw calls: {e}"
                        )
                    tc_list = _build_tc_list(found_calls, conv_uuid)
                    # Diagnose tool call argument sizes
                    for _i, _tc in enumerate(tc_list):
                        _fn = _tc.get("function", {})
                        _args_raw = _fn.get("arguments", "")
                        logger.info(
                            f"[TOOL_ARGS_DIAG] call[{_i}] name={_fn.get('name', '?')} args_len={len(_args_raw)}"
                        )
                    _save_state(
                        messages,
                        stream_meta,
                        parent_id,
                        chat_id,
                        conv_uuid,
                        account_idx,
                        tools,
                        text_buffer,
                        user_uuid=user_uuid,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                    )
                    # Watermark BEFORE tool_calls — prevents content chunk between
                    # tool_calls and finish_reason from confusing the client.
                    if WATERMARK_ENABLED:
                        yield _chunk(
                            {
                                "content": f"\n<!-- PROXY_CHAT: {chat_id} | PROXY_UUID: {user_uuid} -->"
                            }
                        )
                    if tc_list:
                        yield _chunk({"role": "assistant", "tool_calls": tc_list})
                    _dashboard.on_conversation_completed(
                        conv_id=conv_uuid,
                        total_tokens=len(text_buffer),
                        duration_ms=(time.time() - t0) * 1000,
                    )
                    yield _chunk({}, fr="tool_calls", sid=conv_uuid)
                    yield "data: [DONE]\n\n"
                    return

                elif event["type"] == "text":
                    yield_buffer += event["data"]

            # Flush buffer every 50 chars
            if len(text_buffer) >= 50 and yield_buffer:
                yield _chunk({"content": yield_buffer})
                text_yielded_len += len(yield_buffer)
                yield_buffer = ""

            # Periodic metrics for dashboard
            _dashboard.on_metric(
                conv_id=conv_uuid,
                timestamp=time.time(),
                ttft_ms=_ttft_ms if _ttft_ms else None,
                tokens_per_sec=len(text_buffer) / (time.time() - t4)
                if (time.time() - t4) > 0
                else None,
                tokens_total=len(text_buffer),
                latency_ms=(time.time() - _ttft) * 1000 if _ttft else None,
            )

        # ── End of stream ─────────────────────────────────────────────
        if yield_buffer:
            yield _chunk({"content": yield_buffer})
            text_yielded_len += len(yield_buffer)

        try:
            flush_events = handler.flush()
        except Exception as _flush_err:  # pragma: no cover - defensive
            logger.exception(
                f"[FLUSH_ERROR] handler.flush raised; treating as empty: {_flush_err}"
            )
            flush_events = []
        end_tool_calls: list[tuple] = []
        flush_text_buf = ""

        for fe in flush_events:
            if fe["type"] == "tool_calls":
                for tc in fe["data"][:MAX_PARALLEL_TOOL_CALLS]:
                    if "function" in tc:
                        fn = tc["function"]
                        end_tool_calls.append(
                            (fn.get("name", ""), fn.get("arguments", "{}"))
                        )
                    else:
                        end_tool_calls.append(
                            (tc.get("name", ""), tc.get("arguments", "{}"))
                        )
            elif fe["type"] == "text":
                flush_text_buf += fe["data"]

        if end_tool_calls:
            # Don't yield flush_text_buf — it's raw tool call XML content from
            # StreamSieve's _capture_buf that wasn't parsed during feed().
            # Tier 3 repair in handler.flush() already extracted the tool calls.
            # Yielding the raw XML text would leak e.g. "</tool_calls>" to the client.
            logger.info(f"[DETECT_TOOL] flush found {len(end_tool_calls)} call(s)")
            # Drop empty-argument calls from the flush path too (same dominant
            # failure as the live path).
            try:
                _dict_calls = [
                    {"name": name, "arguments": args} for name, args in end_tool_calls
                ]
                _repaired = _repair_empty_tc_args(_dict_calls, tools)
                end_tool_calls = [
                    (c.get("name", ""), c.get("arguments", "{}")) for c in _repaired
                ]
            except Exception as e:  # pragma: no cover - defensive
                logger.exception(
                    f"[TOOL_ARGS_WARN] flush repair failed, using raw calls: {e}"
                )
            tc_list = [
                {
                    "index": i,
                    "id": _tc_id(conv_uuid),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": _ensure_valid_json(args),
                    },
                }
                for i, (name, args) in enumerate(end_tool_calls[:10])
            ]
            _save_state(
                messages,
                stream_meta,
                parent_id,
                chat_id,
                conv_uuid,
                account_idx,
                tools,
                text_buffer,
                user_uuid=user_uuid,
                model_type=model_type,
                thinking_enabled=thinking_enabled,
                search_enabled=search_enabled,
            )
            if WATERMARK_ENABLED:
                yield _chunk(
                    {
                        "content": f"\n<!-- PROXY_CHAT: {chat_id} | PROXY_UUID: {user_uuid} -->"
                    }
                )
            if tc_list:
                yield _chunk({"role": "assistant", "tool_calls": tc_list})
            _dashboard.on_conversation_completed(
                conv_id=conv_uuid,
                total_tokens=len(text_buffer),
                duration_ms=(time.time() - t0) * 1000,
            )
            yield _chunk({}, fr="tool_calls", sid=conv_uuid)
            yield "data: [DONE]\n\n"
            return

        # Thinking fallback
        is_treated_as_text = False
        thinking_fallback = stream_meta.get("thinking_fallback", "")
        if thinking_fallback:
            try:
                fb_result = (
                    ToolMgr.try_parse(thinking_fallback, tool_names)
                    if thinking_fallback
                    else []
                )
                fb_result = ToolMgr.validate(fb_result, tool_names)
            except Exception as _fb_err:  # pragma: no cover - defensive
                logger.exception(
                    f"[FEED_ERROR] thinking-fallback parse failed; treating as text: {_fb_err}"
                )
                fb_result = []
            if len(fb_result) > 8:
                logger.info(
                    f"[THINKING_FALLBACK] {len(fb_result)} calls — too many, treating as text"
                )
                fb_result = []
                is_treated_as_text = True
            if fb_result:
                # Drop empty-argument calls from the thinking-fallback path too.
                try:
                    fb_result = _repair_empty_tc_args(fb_result, tools)
                except Exception as e:  # pragma: no cover - defensive
                    logger.exception(
                        f"[TOOL_ARGS_WARN] fallback repair failed, using raw calls: {e}"
                    )
                fb_list = _build_tc_list(fb_result, conv_uuid)
                logger.info(f"[THINKING_FALLBACK] emitting {len(fb_list)} call(s)")
                _save_state(
                    messages,
                    stream_meta,
                    parent_id,
                    chat_id,
                    conv_uuid,
                    account_idx,
                    tools,
                    text_buffer,
                    user_uuid=user_uuid,
                    model_type=model_type,
                    thinking_enabled=thinking_enabled,
                    search_enabled=search_enabled,
                )
                if WATERMARK_ENABLED:
                    yield _chunk(
                        {
                            "content": f"\n<!-- PROXY_CHAT: {chat_id} | PROXY_UUID: {user_uuid} -->"
                        }
                    )
                if fb_list:
                    yield _chunk({"role": "assistant", "tool_calls": fb_list})
                _dashboard.on_conversation_completed(
                    conv_id=conv_uuid,
                    total_tokens=len(text_buffer),
                    duration_ms=(time.time() - t0) * 1000,
                )
                # Reset rate limit on successful completion
                rate_limiter.reset(account_idx)
                yield _chunk({}, fr="tool_calls", sid=conv_uuid)
                yield "data: [DONE]\n\n"
                return

        # Check if model stopped prematurely or was cut off (e.g. max token limit, unclosed markdown/xml, intent without action, or silence after thinking)
        continue_count = 0
        while continue_count < 2 and _reprompt_depth < 3:
            has_final_answer = "FINAL ANSWER:" in thinking_fallback or (text_buffer and "FINAL ANSWER:" in text_buffer)
            is_truncated = _is_response_truncated(text_buffer, stream_meta)
            unparsed_tool_markup = bool(
                tools
                and not handler._had_tool_calls
                and not has_final_answer
                and re.search(
                    r"<(?:\|?(?:TOOL|DSML)\|?)?(?:tool_calls?|tool_dispatch|tool_call|toolcall|invoke)\b",
                    text_buffer,
                    re.IGNORECASE,
                )
            )
            intent_without_action = bool(
                tools
                and not handler._had_tool_calls
                and not has_final_answer
                and not unparsed_tool_markup
                and _is_intent_without_action(text_buffer)
            )
            silent_model = (
                text_yielded_len == 0
                and not text_buffer.strip()
                and not has_final_answer
                and bool(tools)
            )

            should_continue = (
                not has_final_answer
                and (
                    is_truncated
                    or (
                        continue_count == 0
                        and (intent_without_action or silent_model or unparsed_tool_markup)
                    )
                )
            )

            if not should_continue:
                break

            raw_pid = stream_meta.get("resp_msg_id") or parent_id
            try:
                current_resp_id = int(raw_pid) if raw_pid is not None else None
            except (ValueError, TypeError):
                current_resp_id = None

            if not current_resp_id:
                break

            continue_count += 1
            reason_desc = (
                "truncated response (code fence / unclosed tag / incomplete stream)"
                if is_truncated
                else (
                    f"unparsed tool markup: {text_buffer.strip()[:60]!r}"
                    if unparsed_tool_markup
                    else (
                        f"intent without tool calls: {text_buffer.strip()[:60]!r}"
                        if intent_without_action
                        else (
                            f"silent after thinking: {thinking_fallback.strip()[:60]!r}"
                            if thinking_fallback.strip()
                            else "silent model (0 tokens yielded in tool mode)"
                        )
                    )
                )
            )
            logger.info(
                f"[NATIVE_CONTINUE] Model requires continuation ({reason_desc}). "
                f"Resuming DeepSeek session={chat_id[:12]} msg_id={current_resp_id} attempt={continue_count}"
            )
            try:
                gen_continue, meta_continue = ds.stream_continue(
                    account_idx,
                    chat_id,
                    current_resp_id,
                    model_type=model_type,
                    thinking_enabled=thinking_enabled,
                    throttle=False,
                )
                if meta_continue.get("already_finished"):
                    stream_meta["already_finished"] = True
                    logger.info(
                        f"[NATIVE_CONTINUE] DeepSeek message {current_resp_id} is already FINISHED on server. "
                        f"Preserving existing session {chat_id[:12]} with parent_id={current_resp_id}."
                    )
                    should_reprompt = (
                        unparsed_tool_markup
                        or intent_without_action
                        or (text_yielded_len == 0 and bool(tools))
                    )
                    if should_reprompt and _reprompt_depth < 2:
                        logger.info(
                            f"[ALREADY_FINISHED_REPROMPT] Model finished without tool calls ({reason_desc}). "
                            f"Sending instant agentic reprompt on session={chat_id[:12]} parent_id={current_resp_id}..."
                        )
                        if unparsed_tool_markup:
                            chatter_part = f"You emitted raw/malformed XML markup that could not be parsed as a tool call: {text_buffer.strip()[-200:]!r}."
                        elif intent_without_action:
                            chatter_part = f"You emitted a partial observation or chatter without a tool call: {text_buffer.strip()[-150:]!r}."
                        else:
                            chatter_part = "You stopped generation without emitting a tool call or output."
                        reprompt_msg = (
                            f"CRITICAL: You are an autonomous coding AGENT with tools. {chatter_part} "
                            "The task is NOT completed (no FINAL ANSWER:). You MUST NOT output conversational text, explanations, or broken XML. "
                            "You MUST IMMEDIATELY execute the tool call in exact format (<tool_calls><invoke name=\"...\"><parameter name=\"...\">...</parameter></invoke></tool_calls>) NOW:"
                        )
                        try:
                            gen_reprompt, meta_reprompt = ds.stream_completion(
                                slot=account_idx,
                                chat_session_id=chat_id,
                                prompt=reprompt_msg,
                                parent_message_id=current_resp_id,
                                model_type=model_type,
                                thinking_enabled=thinking_enabled,
                                search_enabled=search_enabled,
                                throttle=False,
                            )
                            yield from _stream_gen(
                                stream_gen=gen_reprompt,
                                stream_meta=meta_reprompt,
                                messages=messages,
                                parent_id=current_resp_id,
                                chat_id=chat_id,
                                conv_uuid=conv_uuid,
                                account_idx=account_idx,
                                tools=tools,
                                model=model,
                                t0=t0,
                                t4=t4,
                                prompt=reprompt_msg,
                                user_uuid=user_uuid,
                                stop=stop,
                                model_type=model_type,
                                thinking_enabled=thinking_enabled,
                                search_enabled=search_enabled,
                                _depth=_depth,
                                _reprompt_depth=_reprompt_depth + 1,
                                _rollover_depth=_rollover_depth,
                            )
                            return
                        except Exception as _rep_err:
                            logger.warning(f"[ALREADY_FINISHED_REPROMPT] Reprompt failed: {_rep_err}")
                            raise
                    break

                # Stream continuation tokens through the SAME handler and buffer
                logger.info(
                    f"[NATIVE_CONTINUE] Continuation active, streaming tokens..."
                )
                for cont_chunk in gen_continue:
                    if not cont_chunk:
                        continue
                    text_buffer += cont_chunk
                    try:
                        cont_events = handler.feed(cont_chunk)
                    except Exception as _fe:
                        logger.warning(f"[FEED_ERROR] in continue feed: {_fe}")
                        cont_events = []
                    for event in cont_events:
                        if event["type"] == "tool_calls":
                            logger.info(
                                f"[DETECT_TOOL] {len(event['data'])} call(s) from handler during continue"
                            )
                            if yield_buffer:
                                yield _chunk({"content": yield_buffer})
                                text_yielded_len += len(yield_buffer)
                                yield_buffer = ""
                            found_calls = list(event["data"][:MAX_PARALLEL_TOOL_CALLS])
                            try:
                                found_calls = _repair_empty_tc_args(found_calls, tools)
                            except Exception:
                                pass
                            tc_list = _build_tc_list(found_calls, conv_uuid)
                            _save_state(
                                messages,
                                meta_continue,
                                parent_id,
                                chat_id,
                                conv_uuid,
                                account_idx,
                                tools,
                                text_buffer,
                                user_uuid=user_uuid,
                                model_type=model_type,
                                thinking_enabled=thinking_enabled,
                                search_enabled=search_enabled,
                            )
                            if WATERMARK_ENABLED:
                                yield _chunk({"content": f"\n<!-- PROXY_CHAT: {chat_id} | PROXY_UUID: {user_uuid} -->"})
                            if tc_list:
                                yield _chunk({"role": "assistant", "tool_calls": tc_list})
                            _dashboard.on_conversation_completed(
                                conv_id=conv_uuid,
                                total_tokens=len(text_buffer),
                                duration_ms=(time.time() - t0) * 1000,
                            )
                            yield _chunk({}, fr="tool_calls", sid=conv_uuid)
                            yield "data: [DONE]\n\n"
                            return
                        elif event["type"] == "text":
                            yield_buffer += event["data"]

                    if len(text_buffer) >= 50 and yield_buffer:
                        yield _chunk({"content": yield_buffer})
                        text_yielded_len += len(yield_buffer)
                        yield_buffer = ""

                if yield_buffer:
                    yield _chunk({"content": yield_buffer})
                    text_yielded_len += len(yield_buffer)
                    yield_buffer = ""

                stream_meta.update(meta_continue)
            except Exception as _cont_err:
                logger.warning(f"[NATIVE_CONTINUE] Continue failed: {_cont_err}")
                break

        if thinking_fallback:
            if is_treated_as_text or (not tools and not text_buffer.strip() and not thinking_enabled):
                logger.info(
                    f"[THINKING_FALLBACK] no text, yielding thinking as response (chat or doc mode)"
                )
                yield _chunk({"content": thinking_fallback})
                text_yielded_len += len(thinking_fallback)

        # Text-only finish — check if model signaled completion
        # Yield any remaining flush text (non-tool-call content from sieve flush)
        if flush_text_buf.strip():
            yield _chunk({"content": flush_text_buf})
        completed = handler._found_final_answer or not handler._had_tool_calls
        if handler._had_tool_calls and not handler._found_final_answer:
            logger.info(
                f"[COMPLETION_CHECK] model had tool calls in history but did not output FINAL ANSWER — may need re-prompt"
            )

        if bool(tools) and text_yielded_len == 0 and not text_buffer.strip() and not handler._had_tool_calls:
            logger.warning(
                f"[PREMATURE STOP] Model finished without response text or tool calls in tool mode (thinking: {thinking_fallback.strip()[:60]!r}). Raising Premature Stop."
            )
            raise RuntimeError(
                f"Premature stop: model stopped after thinking without tool call or response (intent: {thinking_fallback.strip()[:60]!r})"
            )

        if _depth > 0 and text_yielded_len == 0 and not text_buffer and (bool(tools) or not thinking_fallback):
            logger.warning(
                f"[STREAM RETRY EMPTY] Retried stream produced 0 usable tokens at depth={_depth}. Failing retry to trigger next backoff."
            )
            raise RuntimeError(
                f"Retried stream empty at depth {_depth} (intent: {thinking_fallback.strip()[:40]!r})"
            )

        _save_state(
            messages,
            stream_meta,
            parent_id,
            chat_id,
            conv_uuid,
            account_idx,
            tools,
            text_buffer,
            user_uuid=user_uuid,
            model_type=model_type,
            thinking_enabled=thinking_enabled,
            search_enabled=search_enabled,
        )
        if WATERMARK_ENABLED:
            yield _chunk(
                {
                    "content": f"\n<!-- PROXY_CHAT: {chat_id} | PROXY_UUID: {user_uuid} -->"
                }
            )
        _dashboard.on_conversation_completed(
            conv_id=conv_uuid,
            total_tokens=len(text_buffer),
            duration_ms=(time.time() - t0) * 1000,
        )
        # Reset rate limit on successful completion
        rate_limiter.reset(account_idx)
        yield _chunk({}, fr="stop", sid=conv_uuid)
        yield "data: [DONE]\n\n"
        return

    except Exception as e:
        if _depth > 0:
            raise
        err_str = str(e)
        logger.error(f"[STREAM ERROR] {err_str}")

        is_rate = any(
            t in err_str.lower()
            for t in (
                "busy",
                "rate_limit",
                "too frequent",
                "try again later",
                "too many requests",
                "service unavailable",
                "unavailable",
                "temporarily unavailable",
            )
        )
        is_len = any(
            t in err_str.lower()
            for t in (
                "length limit",
                "start a new chat",
                "context_length",
                "too long",
                "length_limit",
                "shorten",
                "input_exceeds_limit",
            )
        )
        active_resp_id = stream_meta.get("resp_msg_id")
        try:
            active_resp_id = int(active_resp_id) if active_resp_id is not None else None
        except (ValueError, TypeError):
            active_resp_id = None

        content_already_sent = text_yielded_len > 0
        is_existing_session = (parent_id is not None) or (active_resp_id is not None)
        is_session_dead = any(
            t in err_str.lower()
            for t in (
                "session not found",
                "chat session not found",
                "session does not exist",
            )
        )

        if (is_session_dead or is_len) and not content_already_sent and _depth < 4:
            cause_name = "LENGTH LIMIT EXCEEDED" if is_len else "SESSION DEAD"
            logger.warning(
                f"[{cause_name} ROLLOVER] Session {chat_id[:12]} ({err_str}). Immediately rolling over to fresh session with conversation_history.md on least loaded account..."
            )
            try:
                from server.services.state_service import clear_conv_by_messages
                clear_conv_by_messages(messages)
            except Exception as _ce:
                logger.warning(f"[{cause_name} ROLLOVER] Failed to clear conv state: {_ce}")

            import sys
            sys.stdout.write(f"\n[{cause_name} ROLLOVER] DIRECT_STDOUT_CHECK STEP 0\n")
            sys.stdout.flush()
            logger.warning(f"[{cause_name} ROLLOVER] STEP0: entering rollover selection...")

            target_slot = _select_least_loaded_account(exclude_slot=account_idx)
            logger.warning(f"[{cause_name} ROLLOVER] STEP1: selected target_slot={target_slot} (excluded account_idx={account_idx})")
            sys.stdout.write(f"[{cause_name} ROLLOVER] DIRECT_STDOUT_CHECK STEP 1 target_slot={target_slot}\n")
            sys.stdout.flush()
            try:
                logger.warning(f"[{cause_name} ROLLOVER] STEP2: creating session on slot={target_slot} (throttle=False)...")
                new_chat_id = ds.create_session(target_slot, throttle=False)
                logger.warning(f"[{cause_name} ROLLOVER] STEP3: session created {new_chat_id}, preparing payload with conversation_history.md...")
                full_prompt, file_ids = _prepare_new_session_payload(
                    target_slot=target_slot,
                    messages=messages,
                    tools=tools,
                    model_type=model_type or "default",
                )
                logger.warning(f"[{cause_name} ROLLOVER] STEP4: payload ready (prompt_len={len(full_prompt)}, file_ids={file_ids}), starting stream_completion...")
                gen_roll, meta_roll = ds.stream_completion(
                    target_slot,
                    new_chat_id,
                    full_prompt,
                    None,
                    ref_file_ids=file_ids if file_ids else None,
                    model_type=model_type,
                    thinking_enabled=thinking_enabled,
                    search_enabled=search_enabled,
                    throttle=False,
                )
                logger.warning(f"[{cause_name} ROLLOVER] STEP5: stream started, delegating to _stream_gen...")
                yield from _stream_gen(
                    stream_gen=gen_roll,
                    stream_meta=meta_roll,
                    messages=messages,
                    parent_id=None,
                    chat_id=new_chat_id,
                    conv_uuid=conv_uuid,
                    account_idx=target_slot,
                    tools=tools,
                    model=model,
                    t0=t0,
                    t4=t4,
                    prompt=full_prompt,
                    user_uuid=user_uuid,
                    stop=stop,
                    model_type=model_type,
                    thinking_enabled=thinking_enabled,
                    search_enabled=search_enabled,
                    ref_file_ids=file_ids,
                    _depth=0,
                    _reprompt_depth=_reprompt_depth,
                    _rollover_depth=_rollover_depth + 1,
                )
                return
            except Exception as e_dead:
                logger.exception(f"[{cause_name} ROLLOVER] Rollover failed: {e_dead}")

        # ── 1. ON EXISTING SESSION: ALWAYS RETRY / CONTINUE ON THE SAME SESSION ──
        # NEVER create new sessions or wipe conv_state during multi-turn conversation!
        if is_existing_session and not is_session_dead and not is_len and not content_already_sent and _depth < 4:
            _STREAM_BACKOFF = [2, 4, 8, 12]
            for _si, _sd in enumerate(_STREAM_BACKOFF):
                logger.info(
                    f"[STREAM RESILIENCE] Waiting {_sd}s before retrying on SAME session={chat_id[:12]} (attempt {_si + 1}/{len(_STREAM_BACKOFF)})"
                )
                yield ": keep-alive\n\n"
                time.sleep(_sd)
                try:
                    can_continue = (
                        active_resp_id is not None
                        and not stream_meta.get("already_finished")
                        and not stream_meta.get("is_finished")
                    )
                    if can_continue:
                        logger.info(
                            f"[STREAM RESILIENCE] Calling stream_continue (POST /continue) on SAME session={chat_id[:12]} msg_id={active_resp_id}"
                        )
                        gen_retry, meta_retry = ds.stream_continue(
                            account_idx,
                            chat_id,
                            active_resp_id,
                            model_type=model_type or "default",
                            thinking_enabled=thinking_enabled if thinking_enabled is not None else True,
                            throttle=False,
                        )
                    else:
                        logger.info(
                            f"[STREAM RESILIENCE] Calling stream_completion on SAME session={chat_id[:12]} parent={parent_id}"
                        )
                        gen_retry, meta_retry = ds.stream_completion(
                            account_idx,
                            chat_id,
                            prompt,
                            parent_id,
                            model_type=model_type,
                            thinking_enabled=thinking_enabled,
                            search_enabled=search_enabled,
                        )

                    yield from _stream_gen(
                        stream_gen=gen_retry,
                        stream_meta=meta_retry,
                        messages=messages,
                        parent_id=parent_id,
                        chat_id=chat_id,
                        conv_uuid=conv_uuid,
                        account_idx=account_idx,
                        tools=tools,
                        model=model,
                        t0=t0,
                        t4=t4,
                        prompt=prompt,
                        user_uuid=user_uuid,
                        stop=stop,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        _depth=99,
                        _reprompt_depth=0,
                        _rollover_depth=_rollover_depth,
                    )
                    return
                except Exception as e_retry:
                    logger.warning(
                        f"[STREAM RESILIENCE] Retry {_si + 1} failed on session {chat_id[:12]}: {e_retry}"
                    )
            logger.info(
                f"[STREAM BACKOFF] Exhausted — all {len(_STREAM_BACKOFF)} retries failed on session={chat_id[:12]} account={account_idx}"
            )
            # Upewniamy się, że po wyczerpaniu ponowień uszkodzony resp_msg_id nie zatruwa conv_state
            if parent_id is not None:
                try:
                    set_conv(
                        messages,
                        chat_id,
                        parent_id,
                        account_idx,
                        user_uuid=user_uuid,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        tools=tools,
                    )
                except Exception as _sc_err:
                    pass

            # Failover or Rollover on exhausted retries if no content sent yet
            if not content_already_sent and _rollover_depth < 2:
                target_slot = _select_least_loaded_account(exclude_slot=account_idx)
                action_name = "Account Failover" if target_slot != account_idx else "Session Rollover"
                logger.info(
                    f"[STREAM RESILIENCE EXHAUSTED] {action_name} triggered from session={chat_id[:12]} (account {account_idx} -> target slot {target_slot}) with conversation_history.md..."
                )
                try:
                    new_chat_id = ds.create_session(target_slot, throttle=False)
                    full_prompt, file_ids = _prepare_new_session_payload(
                        target_slot=target_slot,
                        messages=messages,
                        tools=tools,
                        model_type=model_type or "default",
                    )
                    gen_rescue, meta_rescue = ds.stream_completion(
                        target_slot,
                        new_chat_id,
                        full_prompt,
                        None,
                        ref_file_ids=file_ids if file_ids else None,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        throttle=False,
                    )
                    yield from _stream_gen(
                        stream_gen=gen_rescue,
                        stream_meta=meta_rescue,
                        messages=messages,
                        parent_id=None,
                        chat_id=new_chat_id,
                        conv_uuid=conv_uuid,
                        account_idx=target_slot,
                        tools=tools,
                        model=model,
                        t0=t0,
                        t4=t4,
                        prompt=full_prompt,
                        user_uuid=user_uuid,
                        stop=stop,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        ref_file_ids=file_ids,
                        _depth=0,
                        _reprompt_depth=0,
                        _rollover_depth=_rollover_depth + 1,
                    )
                    return
                except Exception as e_rescue:
                    logger.warning(
                        f"[STREAM RESILIENCE EXHAUSTED] {action_name} to slot {target_slot} failed: {e_rescue}"
                    )

        # ── 2. ON BRAND NEW SESSION (parent_id is None): FAILOVER TO ALT ACCOUNT ──
        if not is_existing_session and is_rate and _depth < 3:
            now_ac = time.time()
            alts = [
                i
                for i in range(MAX_ACCOUNTS)
                if i != account_idx
                and ap.is_valid(i)
                and now_ac >= rate_limiter.get_until(i)
            ]
            if alts:
                alt_acc = alts[0]
                logger.info(
                    f"[STREAM MIGRATE] New session failed on account {account_idx}, switching to account {alt_acc}"
                )
                try:
                    new_chat_id = ds.create_session(alt_acc)
                    gen2, meta2 = ds.stream_completion(
                        alt_acc,
                        new_chat_id,
                        prompt,
                        None,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        throttle=False,
                    )
                    yield from _stream_gen(
                        stream_gen=gen2,
                        stream_meta=meta2,
                        messages=messages,
                        parent_id=None,
                        chat_id=new_chat_id,
                        conv_uuid=conv_uuid,
                        account_idx=alt_acc,
                        tools=tools,
                        model=model,
                        t0=t0,
                        t4=t4,
                        prompt=prompt,
                        user_uuid=user_uuid,
                        stop=stop,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        _depth=_depth + 1,
                        _reprompt_depth=_reprompt_depth,
                        _rollover_depth=_rollover_depth,
                    )
                    return
                except Exception as e2:
                    logger.warning(f"[STREAM MIGRATE] Failover to account {alt_acc} failed: {e2}")

        if is_rate and not content_already_sent:
            MAX_RATE_RETRIES = 10
            if _rate_retry < MAX_RATE_RETRIES:
                _dashboard.on_conversation_error(
                    conv_id=conv_uuid,
                    error_message=err_str[:500],
                    total_tokens=len(text_buffer),
                    duration_ms=(time.time() - t0) * 1000,
                )
                rl_time = getattr(e, "retry_after", 20)
                try:
                    wait_seconds = min(int(rl_time), 25)
                except (ValueError, TypeError):
                    wait_seconds = 20
                logger.info(
                    f"[STREAM RATE_LIMIT_RETRY] account={account_idx} waiting {wait_seconds}s with SSE keep-alive "
                    f"before seamless retry (attempt {_rate_retry + 1}/{MAX_RATE_RETRIES})..."
                )
                _wait_start = time.time()
                while time.time() - _wait_start < wait_seconds:
                    yield ": keep-alive\n\n"
                    time.sleep(2.0)

                # Check if an alternate account became available while waiting
                now_ac2 = time.time()
                alts2 = [
                    i
                    for i in range(MAX_ACCOUNTS)
                    if i != account_idx
                    and ap.is_valid(i)
                    and now_ac2 >= rate_limiter.get_until(i)
                ]
                if alts2 and _depth < 3:
                    alt_acc2 = alts2[0]
                    logger.info(
                        f"[STREAM RATE_LIMIT_RETRY] alternate account {alt_acc2} is available! Migrating session with conversation_history.md..."
                    )
                    try:
                        new_chat_id = ds.create_session(alt_acc2)
                        full_prompt, file_ids = _prepare_new_session_payload(
                            target_slot=alt_acc2,
                            messages=messages,
                            tools=tools,
                            model_type=model_type or "default",
                        )
                        gen2, meta2 = ds.stream_completion(
                            alt_acc2,
                            new_chat_id,
                            full_prompt,
                            None,
                            ref_file_ids=file_ids if file_ids else None,
                            model_type=model_type,
                            thinking_enabled=thinking_enabled,
                            search_enabled=search_enabled,
                            throttle=False,
                        )
                        yield from _stream_gen(
                            stream_gen=gen2,
                            stream_meta=meta2,
                            messages=messages,
                            parent_id=None,
                            chat_id=new_chat_id,
                            conv_uuid=conv_uuid,
                            account_idx=alt_acc2,
                            tools=tools,
                            model=model,
                            t0=t0,
                            t4=t4,
                            prompt=full_prompt,
                            user_uuid=user_uuid,
                            stop=stop,
                            model_type=model_type,
                            thinking_enabled=thinking_enabled,
                            search_enabled=search_enabled,
                            ref_file_ids=file_ids,
                            _depth=_depth + 1,
                            _reprompt_depth=_reprompt_depth,
                            _rollover_depth=_rollover_depth,
                            _rate_retry=0,
                        )
                        return
                    except Exception as _mig_err:
                        logger.warning(f"[STREAM RATE_LIMIT_RETRY] Migration to {alt_acc2} failed: {_mig_err}")

                try:
                    # After rate limit or stream error, any pending resp_msg_id was discarded by DeepSeek (clear_response).
                    # Clear it and ensure conv_state is reverted to the original valid parent_id.
                    stream_meta.pop("resp_msg_id", None)
                    if parent_id is not None:
                        try:
                            set_conv(
                                messages,
                                chat_id,
                                parent_id,
                                account_idx,
                                user_uuid=user_uuid,
                                model_type=model_type,
                                thinking_enabled=thinking_enabled,
                                search_enabled=search_enabled,
                                tools=tools,
                            )
                        except Exception as _revert_err:
                            logger.warning(f"[STREAM RATE_LIMIT_RETRY] Failed to revert conv_state: {_revert_err}")

                    gen_retry, meta_retry = ds.stream_completion(
                        account_idx,
                        chat_id,
                        prompt,
                        parent_id,
                        ref_file_ids=ref_file_ids,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        throttle=False,
                    )
                    yield from _stream_gen(
                        stream_gen=gen_retry,
                        stream_meta=meta_retry,
                        messages=messages,
                        parent_id=parent_id,
                        chat_id=chat_id,
                        conv_uuid=conv_uuid,
                        account_idx=account_idx,
                        tools=tools,
                        model=model,
                        t0=t0,
                        t4=t4,
                        prompt=prompt,
                        user_uuid=user_uuid,
                        stop=stop,
                        model_type=model_type,
                        thinking_enabled=thinking_enabled,
                        search_enabled=search_enabled,
                        ref_file_ids=ref_file_ids,
                        _depth=0,
                        _reprompt_depth=0,
                        _rollover_depth=_rollover_depth,
                        _rate_retry=_rate_retry + 1,
                    )
                    return
                except Exception as _rr_err:
                    logger.warning(f"[STREAM RATE_LIMIT_RETRY] Retry attempt {_rate_retry + 1} failed: {_rr_err}")

            _dashboard.on_conversation_error(
                conv_id=conv_uuid,
                error_message=err_str[:500],
                total_tokens=len(text_buffer),
                duration_ms=(time.time() - t0) * 1000,
            )
            # Emit graceful inline notice without throwing 429 to avoid breaking conversation in IDE
            yield _chunk({"content": "\n\n*(Serwer DeepSeek jest chwilowo mocno obciążony. Odczekaj chwilę przed wysłaniem kolejnej wiadomości.)*"})
            yield _chunk({}, fr="stop")
            return


        elif is_len and not content_already_sent:
            logger.info(
                f"[LENGTH_LIMIT] Content too long ({len(text_buffer)} chars buffered, "
                f"prompt={len(prompt)} chars) — propagating to outer retry for truncation"
            )
            _dashboard.on_conversation_error(
                conv_id=conv_uuid,
                error_message=err_str[:500],
                total_tokens=len(text_buffer),
                duration_ms=(time.time() - t0) * 1000,
            )
            # Clear state so next retry creates NEW session
            from server.services.state_service import clear_conv_by_messages
            try:
                cleared = clear_conv_by_messages(messages)
                if cleared:
                    logger.info(
                        f"[LENGTH_LIMIT_FIX] Cleared state hash={cleared} "
                        f"— next retry will create new DeepSeek session"
                    )
            except Exception as e:
                logger.warning(f"[LENGTH_LIMIT_FIX] Failed to clear state: {e}")
            raise

        _dashboard.on_conversation_error(
            conv_id=conv_uuid,
            error_message=err_str[:500],
            total_tokens=len(text_buffer),
            duration_ms=(time.time() - t0) * 1000,
        )
        yield _chunk({"content": f"\n\n[Stream error: {err_str}]"})
        yield _chunk({}, fr="stop")


# ── ProxyService ──────────────────────────────────────────────────────────────


class ProxyService:
    """Thin orchestrator for /v1/chat/completions."""

    def __init__(self) -> None:
        load_conv_state()

    # ── Validation ──────────────────────────────────────────────────

    @staticmethod
    def _validate_messages(messages: list[dict]) -> None:
        if not messages:
            raise HTTPException(400, "messages cannot be empty")
        for m in messages:
            role = m.get("role", "")
            if role not in ("system", "user", "assistant", "tool"):
                raise HTTPException(400, f"Invalid role: {role}")
            if role in ("user", "system") and not m.get("content"):
                raise HTTPException(
                    400, f"Message with role '{role}' must have content"
                )

    @staticmethod
    def _validate_tools(tools: list[dict] | None) -> None:
        if not tools:
            return
        names: set[str] = set()
        for t in tools:
            fn = t.get("function", t)
            name = fn.get("name", "")
            if not name:
                raise HTTPException(400, "Tool without name")
            if name in names:
                raise HTTPException(400, f"Duplicate tool name: {name}")
            names.add(name)

    @staticmethod
    def _validate_params(temperature, top_p, max_tokens) -> None:
        if temperature is not None and not (0 <= temperature <= 2):
            raise HTTPException(400, "temperature must be in [0, 2]")
        if top_p is not None and not (0 <= top_p <= 1):
            raise HTTPException(400, "top_p must be in [0, 1]")
        if max_tokens is not None and max_tokens < 1:
            raise HTTPException(400, "max_tokens must be >= 1")

    async def _orchestrate_chunks_if_needed(
        self,
        prompt: str,
        account_idx: int,
        chat_id: str,
        parent_id: int | str | None,
        model_type: str,
        messages: list[dict],
        tools: list[dict] | None,
        thinking_enabled: bool,
        search_enabled: bool,
        user_uuid: str | None = None,
    ) -> tuple[str, int | str | None, bool]:
        """Multi-part chunked prompt injection for oversized payloads."""
        if len(prompt) <= PROMPT_CHUNK_THRESHOLD:
            return prompt, parent_id, False

        chunks = split_prompt_payload(prompt, max_chunk_size=PROMPT_CHUNK_THRESHOLD)
        if len(chunks) <= 1:
            return prompt, parent_id, False

        logger.info(
            f"[CHUNK_ORCHESTRATION] Prompt is oversized ({len(prompt)} chars) "
            f"— splitting into {len(chunks)} sequential parts"
        )
        for ci, interim_chunk in enumerate(chunks[:-1]):
            logger.info(
                f"[CHUNK_ORCHESTRATION] Injecting interim part {ci + 1}/{len(chunks)} "
                f"({len(interim_chunk)} chars) into session={chat_id[:12] if chat_id else 'none'} parent={parent_id}"
            )
            interim_resp_id = None
            for chunk_att in range(3):
                try:
                    interim_resp_id = ds.send_interim_chunk(
                        account_idx,
                        chat_id,
                        interim_chunk,
                        parent_id,
                        model_type=model_type,
                    )
                    break
                except Exception as ce:
                    logger.warning(
                        f"[CHUNK_ORCHESTRATION] Interim chunk {ci + 1} attempt {chunk_att + 1}/3 failed: {ce}"
                    )
                    if chunk_att < 2:
                        await asyncio.sleep(2.0 * (chunk_att + 1))
                    else:
                        raise ce

            parent_id = interim_resp_id
            # Update conv_state with intermediate parent_id as safety guard
            if chat_id and parent_id is not None:
                set_conv(
                    messages,
                    chat_id,
                    parent_id,
                    account_idx,
                    user_uuid=user_uuid,
                    model_type=model_type,
                    thinking_enabled=thinking_enabled,
                    search_enabled=search_enabled,
                    tools=tools,
                )
            # Settling delay so cloud session state registers the interim message node reliably
            await asyncio.sleep(0.2)

        prompt = chunks[-1]
        logger.info(
            f"[CHUNK_ORCHESTRATION] Final part ready ({len(prompt)} chars) with parent={parent_id}"
        )
        return prompt, parent_id, True

    # ── Main endpoint ──────────────────────────────────────────────────

    async def chat_completions(self, raw_request: Request) -> Any:
        t0 = time.time()

        # ── Debug: log ALL headers ─────────────────────────────────
        logger.info(f"[REQUEST_HEADERS] {dict(raw_request.headers)}")

        body_bytes = await raw_request.body()
        body_str = body_bytes.decode("utf-8", "ignore")
        try:
            raw_json: dict = json.loads(body_str)
        except Exception as e:
            raise HTTPException(400, f"Invalid JSON body: {e}")

        model = raw_json.get("model", "deepseek-v4-pro")

        # ── Diagnostic: log messages from Trae ────────────────────
        raw_msgs = raw_json.get("messages", [])
        for _mi, _m in enumerate(raw_msgs):
            _role = _m.get("role", "?")
            _content = str(_m.get("content", ""))
            _has_tools = bool(_m.get("tool_calls"))
            _preview = _content[:300].replace("\n", "\\n")
            logger.info(
                f"[RAW MSG] [{_mi}] role={_role} tools={_has_tools} content={_preview}..."
            )
            if _mi == 0:
                _extra_keys = [k for k in _m.keys() if k not in ("role", "content")]
                logger.info(f"[RAW MSG0] extra_keys={_extra_keys}")
        logger.info(
            f"[RAW] tools_count={len(raw_json.get('tools') or [])} msgs_count={len(raw_msgs)}"
        )
        _top_keys = [
            k
            for k in raw_json.keys()
            if k
            not in (
                "messages",
                "tools",
                "model",
                "stream",
                "max_tokens",
                "temperature",
                "top_p",
            )
        ]
        if _top_keys:
            logger.info(f"[RAW TOP] extra_keys={_top_keys}")
        # Dump full body to file for analysis (with rotation at 10MB)
        _dump_path = Path(__file__).parent.parent.parent / "request_dump.ndjson"
        try:
            if _dump_path.exists() and _dump_path.stat().st_size > 10 * 1024 * 1024:
                _bak = _dump_path.with_suffix(".ndjson.bak")
                _bak.unlink(missing_ok=True)
                _dump_path.rename(_bak)
            with open(_dump_path, "a", encoding="utf-8") as _f:
                _f.write(
                    json.dumps(
                        {"ts": datetime.datetime.now().isoformat(), "body": raw_json},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception as _dump_err:
            logger.warning(f"[DUMP] failed to write request dump: {_dump_err}")
        # Log first 1500 chars of body for new-session analysis
        _first_msg_raw = str(raw_msgs[0]) if raw_msgs else "NO MESSAGES"
        if len(_first_msg_raw) > 1500:
            _first_msg_raw = _first_msg_raw[:1500] + "..."
        logger.info(f"[RAW FIRST MSG FULL] {_first_msg_raw}")

        # ── Validate ──────────────────────────────────────────────
        self._validate_messages(raw_json.get("messages", []))
        self._validate_tools(raw_json.get("tools"))
        self._validate_params(
            raw_json.get("temperature"),
            raw_json.get("top_p"),
            raw_json.get("max_tokens"),
        )

        # ── Tool choice ───────────────────────────────────────────
        tools = list(raw_json.get("tools") or [])
        tool_choice = raw_json.get("tool_choice")
        if not tool_choice and tools:
            tool_choice = "auto"
        if tool_choice == "none":
            tools = []
        elif isinstance(tool_choice, dict) and tools:
            fn_name = tool_choice.get("function", {}).get("name", "")
            if fn_name:
                tools = [
                    t for t in tools if t.get("function", {}).get("name") == fn_name
                ]

        # ── Conversation lookup ───────────────────────────────────
        messages = list(raw_json.get("messages", []))
        state = get_conv(messages)
        # Fallback: if Trae didn't send tools, use saved ones from state
        if not tools and state:
            tools = list(state.get("tools") or [])

        # ── Parse ─────────────────────────────────────────────────
        parsed = InputParser.parse(raw_json, state)

        # ── Diagnostic: dump all request keys at resume ──────────
        _all_keys = {k: type(v).__name__ for k, v in raw_json.items()}
        _array_lens = {
            k: len(v) for k, v in raw_json.items() if isinstance(v, (list, dict))
        }
        logger.info(
            f"[DIAG] resume={parsed.is_resume} all_keys={_all_keys} array_lens={_array_lens}"
        )
        _ignored = [
            k
            for k in raw_json
            if k
            not in (
                "messages",
                "tools",
                "model",
                "stream",
                "max_tokens",
                "max_completion_tokens",
                "temperature",
                "top_p",
                "stop",
                "tool_choice",
                "parallel_tool_calls",
                "reasoning_effort",
                "frequency_penalty",
                "presence_penalty",
                "user",
                "n",
                "seed",
                "response_format",
                "metadata",
            )
        ]
        if _ignored:
            logger.info(f"[DIAG] unknown_keys={_ignored}")

        # ── Account selection ─────────────────────────────────────
        account_idx = account_selector.select_account(messages, state, parsed.is_resume)

        logger.info(f"[CONV] resume={parsed.is_resume} account={account_idx}")

        # ── Message preprocessing ─────────────────────────────────
        msgs_to_send: list[dict] = []
        if parsed.is_resume and state:
            all_msgs = list(parsed.messages)
            last_asst_idx = max(
                (i for i, m in enumerate(all_msgs) if m.get("role") == "assistant"),
                default=-1,
            )
            delta_msgs = (
                all_msgs[last_asst_idx + 1 :] if last_asst_idx >= 0 else all_msgs
            )
            if not delta_msgs:
                logger.info(
                    "[DELTA] delta_msgs is empty because last message is assistant — injecting 'Continue' prompt"
                )
                delta_msgs = [{"role": "user", "content": "Continue"}]

            # ── Deduplicate user messages in delta ──
            # Uses ORIGINAL raw messages from Trae (not InputParser-cleaned) for the
            # pre-delta set, because InputParser strips system-reminder wrapped user
            # messages from parsed.messages.  Uses _extract_text_content() instead of
            # str(content) because Trae sends content as a list of parts.
            # Comparison extracts the <user_input>...</user_input> text, which is
            # the actual user-written message that Trae re-sends in every pipeline
            # turn.  System-reminder content differs each turn (different tool
            # results), so comparing raw text would never match.
            _USER_INPUT_RE = re.compile(
                r"<user_input>(.*?)</user_input>", re.DOTALL | re.IGNORECASE
            )

            def _get_user_core(content: Any) -> str:
                """Extract the user-written text from a message.
                Prefers <user_input>...</user_input> content, otherwise strips
                system-reminder wrappers and returns remaining text."""
                text = _extract_text_content(content)
                m = _USER_INPUT_RE.search(text)
                if m:
                    return m.group(1).strip()
                # Fallback: strip system-reminder wrapper
                _SYS_TAG_STRIP = re.compile(
                    r"<system-reminder>.*?</system-reminder>", re.DOTALL | re.IGNORECASE
                )
                return _SYS_TAG_STRIP.sub("", text).strip()

            _last_user_core = None
            # Use raw messages (from Trae, before InputParser cleaning) for pre-delta
            # user message collection, so system-reminder wrapped user messages are seen.
            _raw_all = list(raw_json.get("messages", []))
            _raw_last_asst = max(
                (i for i, m in enumerate(_raw_all) if m.get("role") == "assistant"),
                default=-1,
            )
            for _m in _raw_all[: _raw_last_asst + 1]:
                if _m.get("role") == "user":
                    _uc = _get_user_core(_m.get("content", ""))
                    if _uc:
                        _last_user_core = _uc
            for _delta_idx, _m in enumerate(delta_msgs):
                m_copy = dict(_m)
                if m_copy.get("role") == "user":
                    _uc = _get_user_core(m_copy.get("content", ""))
                    if _uc and _uc == _last_user_core:
                        # If the previous message already in msgs_to_send was a user message,
                        # do not append a consecutive duplicate user message! Merge/update instead.
                        if msgs_to_send and msgs_to_send[-1].get("role") == "user":
                            _content_str = str(m_copy.get("content", ""))
                            _sys_tag_match = re.search(
                                r"(<system-reminder>.*?</system-reminder>)",
                                _content_str,
                                re.DOTALL | re.IGNORECASE,
                            )
                            if _sys_tag_match and _sys_tag_match.group(1) not in str(msgs_to_send[-1].get("content", "")):
                                msgs_to_send[-1]["content"] = (
                                    str(msgs_to_send[-1].get("content", ""))
                                    + "\n\n"
                                    + _sys_tag_match.group(1)
                                )
                            logger.info(
                                f"[DEDUP] delta[{_delta_idx}] consecutive user duplicate merged with previous user message"
                            )
                            continue

                        # Preserve system-reminder from delta content, replace
                        # the rest with "Continue working on the task"
                        _content_str = str(m_copy.get("content", ""))
                        _sys_tag_match = re.search(
                            r"(<system-reminder>.*?</system-reminder>)",
                            _content_str,
                            re.DOTALL | re.IGNORECASE,
                        )
                        if _sys_tag_match:
                            m_copy["content"] = (
                                _sys_tag_match.group(1)
                                + "\nContinue working on the task"
                            )
                        else:
                            m_copy["content"] = "Continue working on the task"
                        logger.info(
                            f"[DEDUP] delta[{_delta_idx}] user msg deduped (core={_uc!r})"
                        )
                    elif _uc:
                        _last_user_core = _uc
                msgs_to_send.append(m_copy)
        else:
            # New session: preserve ALL messages from IDE (no artificial 20-message capping)
            for m in parsed.messages:
                msgs_to_send.append(dict(m))
            logger.info(f"[NEW_SESSION_MSGS] Preserving full IDE messages count={len(msgs_to_send)}")

        # ── Extract images from messages (OpenAI Vision) ──────────
        extracted_images, msgs_to_send = extract_images_from_messages(
            msgs_to_send, only_last_turn=True
        )
        if extracted_images:
            logger.info(
                f"[VISION] Extracted {len(extracted_images)} image(s) from current turn"
            )

        # ── Build prompt via PromptBuilder ────────────────────────
        system_prompt, history, user_message = _extract_prompt_parts(msgs_to_send, is_resume=parsed.is_resume)

        # Document Attachment Strategy: initialize document attachments list
        doc_attachments: list[dict] = []

        # ── NEW SESSION WITH PRIOR CONVERSATION TURNS ────────────────────────
        # When IDE sends a rich multi-turn conversation on a new DeepSeek session
        # (e.g. 50-150 turns after proxy restart, timeout, or branch switch),
        # pack all prior turns into a clean `conversation_history.md` attachment
        # (up to 100 MB per file) and attach it via ref_file_ids.
        # This keeps the inline prompt lean (<25k) while preserving 100% of the context.
        if not parsed.is_resume and history:
            has_prior_dialogue = any(
                h.get("role") in ("assistant", "tool") for h in history
            ) or len(history) > 1

            if has_prior_dialogue:
                logger.info(
                    f"[HISTORY_ATTACHMENT] Formatting {len(history)} prior history entries into conversation_history.md"
                )
                hist_docs = create_history_attachments(history)
                if hist_docs:
                    doc_attachments.extend(hist_docs)
                    doc_names = ", ".join(d["filename"] for d in hist_docs)
                    hist_note = (
                        f"[Full prior conversation history from IDE ({len(history)} turns) is attached in document(s): {doc_names}. "
                        f"Please carefully review the attached history to understand prior context and fulfill the user's latest request below.]\n\n"
                    )
                    user_message = hist_note + (user_message or "")
                history = []
            else:
                # Pure preliminary user messages (e.g. user_info + user_query)
                user_parts_from_history = [
                    h["content"] for h in history if h.get("role") == "user" and h.get("content")
                ]
                if user_parts_from_history:
                    user_message = "\n\n".join(
                        user_parts_from_history + ([user_message] if user_message else [])
                    )
                history = []


        # ── Diagnostic: trace preamble through pipeline ──────────
        _sp_len = len(system_prompt) if system_prompt else 0
        _sp_preview = (
            (system_prompt[:120] + "...")
            if system_prompt and len(system_prompt) > 120
            else (system_prompt or "NONE")
        )
        logger.info(
            f"[PREAMBLE DEBUG] system_prompt_len={_sp_len} value={_sp_preview!r}"
        )
        logger.info(
            f"[PREAMBLE DEBUG] is_resume={parsed.is_resume} tools={len(tools)} history={len(history)}"
        )

        # ── Diagnostic: count user message occurrences ───────────
        if parsed.is_resume:
            _um_preview = (
                (user_message[:80] + "...") if len(user_message) > 80 else user_message
            )
            _history_user_count = sum(
                1 for h in (history or []) if h.get("role") == "user"
            )
            _history_user_previews = [
                str(h.get("content", "")[:60])
                for h in (history or [])
                if h.get("role") == "user"
            ]
            _um_in_history_count = sum(
                1
                for h in (history or [])
                if h.get("role") == "user"
                and user_message
                and user_message[:60] in str(h.get("content", ""))
            )
            logger.info(f"[DEDUP DIAG] is_resume=True user_msg={_um_preview!r}")
            logger.info(
                f"[DEDUP DIAG] user_msgs_in_history={_history_user_count} previews={_history_user_previews}"
            )
            logger.info(
                f"[DEDUP DIAG] user_msg_appears_in_history={_um_in_history_count} times"
            )
            logger.info(
                f"[DEDUP DIAG] msgs_to_send_len={len(msgs_to_send)} delta_only=True"
            )

        if parsed.is_resume:
            # Resume: DeepSeek session has context up to last response.
            # Must send CURRENT turn's tool results (in `history`) so model sees them.
            # Do NOT resend old conversation history (already in DeepSeek session).
            prompt = PromptBuilder.build(
                user_message=user_message or "",
                system_prompt=None,
                history=history if history else None,
                tools_schema=None,
            )
        else:
            # ── DIAGNOSTIC: tools schema injection ────────────────────────────────
            if tools:
                logger.info(f'[TOOLS_PRE_BUILD] tools_count={len(tools)} sys_prompt_len={len(system_prompt) if system_prompt else 0}')
                _t0 = tools[0].get('function', tools[0])
                logger.info(f'[TOOLS_PRE_BUILD] tool[0] name={_t0.get("name","?")} type={tools[0].get("type","?")} has_func_key={"function" in tools[0]}')

            prompt = PromptBuilder.build(
                user_message=user_message or "",
                system_prompt=system_prompt,
                history=history if history else None,
                tools_schema=tools if tools else None,
            )
            # ── DIAGNOSTIC POST-BUILD: czy tools trafiły do promptu? ──────────────
            if tools and not parsed.is_resume:
                if '[Available Tool]:' in prompt:
                    logger.info(f'[TOOLS_POST_BUILD] ✅ Tools schema IN prompt (prompt_len={len(prompt)})')
                else:
                    logger.warning(f'[TOOLS_POST_BUILD] ❌ Tools schema MISSING from prompt! tools={len(tools)} prompt_len={len(prompt)}')
                    if system_prompt and len(system_prompt) > 200:
                        _sys_prev = system_prompt[:200].replace(chr(10), "\n")
                        logger.info(f'[TOOLS_POST_BUILD] sys_prompt preview: {_sys_prev!r}')

        # ── Diagnostic: does prompt start with preamble? ─────────
        if prompt and prompt.startswith("You are "):
            logger.info(
                f"[PREAMBLE DEBUG] ✅ Prompt STARTS with preamble ({len(prompt)} chars)"
            )
        elif prompt and not parsed.is_resume:
            _first_120 = prompt[:120].replace("\n", "\\n")
            logger.info(
                f"[PREAMBLE DEBUG] ❌ New-session prompt MISSING preamble! First 120 chars: {_first_120!r}"
            )

        # ── Diagnostic: count user message appearances in prompt ──
        if parsed.is_resume and user_message:
            _um_short = user_message[:80].replace("\n", "\\n")
            _um_in_prompt = (
                prompt.count(user_message[:100])
                if len(user_message) > 100
                else prompt.count(user_message)
            )
            logger.info(f"[PROMPT DUMP] isinstance user_message um_short={_um_short!r}")
            logger.info(
                f"[PROMPT DUMP] user_message appears in prompt={_um_in_prompt} times (exact match)"
            )
            # Also check the "[User]:" prefix count
            _user_prefix_count = prompt.count("[User]:")
            logger.info(f"[PROMPT DUMP] [User]: count in prompt={_user_prefix_count}")
        t2 = time.time()
        logger.info(
            f"[TIMING] t2-prompt_built: {t2 - t0:.3f}s (prompt={len(prompt)} chars)"
        )

        # ── Acquire session slot ──────────────────────────────────
        chat_id: str
        parent_id: str | None

        if parsed.is_resume and state:
            chat_id = state["chat_id"]
            parent_id = state["parent_id"]
        else:
            if not session_manager.acquire_slot(account_idx):
                raise HTTPException(
                    503,
                    f"Account {account_idx} session pool full (max {MAX_SESSIONS_PER_ACCOUNT})",
                )
            try:
                chat_id = ds.create_session(account_idx)
            except Exception:
                session_manager.release_slot(account_idx)
                raise
            parent_id = None
            logger.info(
                f"[NEW SESSION] account={account_idx} chat_id={chat_id[:12]}..."
            )

        user_uuid = state.get("user_uuid", "") if state else ""
        if not user_uuid:
            user_uuid = uuid.uuid4().hex[:12]

        # ── Call DeepSeek with retry ──────────────────────────────
        stream_gen_obj = None
        stream_meta_obj: dict = {}
        t3 = time.time()

        _RATE_ERRORS = (
            "busy",
            "rate_limit",
            "too frequent",
            "try again later",
            "too many requests",
            "service unavailable",
            "unavailable",
            "temporarily unavailable",
        )
        _LENGTH_ERRORS = (
            "length limit",
            "start a new chat",
            "context_length",
            "too long",
            "length_limit",
            "shorten",
            "input_exceeds_limit",
        )

        # Document Attachment Strategy: extract oversized tool results / context
        # into lightweight document attachments (up to 100 MB per file) to keep prompt lean (<35k chars)
        # Document Attachment Strategy: extract oversized tool results / context
        # into lightweight document attachments (up to 100 MB per file) to keep prompt lean (<35k chars)
        if len(prompt) > PROMPT_CHUNK_THRESHOLD:
            try:
                lean_prompt, docs = extract_oversized_blocks_to_attachments(prompt)
                if docs:
                    logger.info(
                        f"[DOC_ATTACHMENT] Extracted {len(docs)} document attachment(s), "
                        f"prompt reduced from {len(prompt)} to {len(lean_prompt)} chars"
                    )
                    prompt = lean_prompt
                    doc_attachments.extend(docs)
            except Exception as de:
                logger.warning(f"[DOC_ATTACHMENT] Extraction failed, falling back to chunker: {de}")


        # Multi-part chunked prompt injection for oversized payloads
        was_chunked = False
        try:
            prompt, parent_id, was_chunked = await self._orchestrate_chunks_if_needed(
                prompt=prompt,
                account_idx=account_idx,
                chat_id=chat_id,
                parent_id=parent_id,
                model_type=parsed.model_type,
                messages=messages,
                tools=tools,
                thinking_enabled=parsed.thinking_enabled,
                search_enabled=parsed.search_enabled,
                user_uuid=user_uuid,
            )
        except Exception as oe:
            if "invalid message id" in str(oe).lower() or "biz_code\":26" in str(oe).lower():
                logger.warning(
                    f"[CHUNK_ORCHESTRATION] Irrecoverable invalid message id in session {chat_id[:12] if chat_id else 'none'}: {oe}. Forcing new session..."
                )
                chat_id = ds.create_session(account_idx)
                parent_id = None
                prompt, parent_id, was_chunked = await self._orchestrate_chunks_if_needed(
                    prompt=prompt,
                    account_idx=account_idx,
                    chat_id=chat_id,
                    parent_id=None,
                    model_type=parsed.model_type,
                    messages=messages,
                    tools=tools,
                    thinking_enabled=parsed.thinking_enabled,
                    search_enabled=parsed.search_enabled,
                    user_uuid=user_uuid,
                )
            else:
                raise

        for attempt in range(MAX_ACCOUNTS):
            uploaded_file_ids: list[str] = []
            try:
                if doc_attachments:
                    logger.info(
                        f"[DOC_ATTACHMENT] Uploading {len(doc_attachments)} document attachment(s) for account={account_idx} (attempt {attempt + 1})..."
                    )
                    for doc in doc_attachments:
                        dfid = ds.upload_file(
                            slot=account_idx,
                            file_data=doc["data"],
                            filename=doc["filename"],
                            mime_type=doc["mime_type"],
                            model_type=parsed.model_type,
                        )
                        uploaded_file_ids.append(dfid)
                    logger.info(
                        f"[DOC_ATTACHMENT] Successfully uploaded {len(doc_attachments)} document(s): {uploaded_file_ids}"
                    )
                if extracted_images:
                    logger.info(
                        f"[VISION] Uploading {len(extracted_images)} image(s) for account={account_idx} (attempt {attempt + 1})..."
                    )
                    for img in extracted_images:
                        fid = ds.upload_file(
                            slot=account_idx,
                            file_data=img.data,
                            filename=img.filename,
                            mime_type=img.mime_type,
                            model_type=parsed.model_type,
                        )
                        uploaded_file_ids.append(fid)
                    logger.info(
                        f"[VISION] Successfully uploaded {len(uploaded_file_ids)} image(s): {uploaded_file_ids}"
                    )

                throttle_res = ds.async_throttle(account_idx, is_resume=parsed.is_resume)
                if inspect.isawaitable(throttle_res):
                    await throttle_res
                stream_gen_obj, stream_meta_obj = ds.stream_completion(
                    account_idx,
                    chat_id,

                    prompt,
                    parent_id,
                    model_type=parsed.model_type,
                    ref_file_ids=uploaded_file_ids,
                    thinking_enabled=parsed.thinking_enabled,
                    search_enabled=parsed.search_enabled,
                    reasoning_effort=parsed.reasoning_effort,
                    max_tokens=parsed.max_tokens,
                    temperature=parsed.temperature,
                    top_p=parsed.top_p,
                    is_chunk_continuation=was_chunked,
                    throttle=False,
                )
            except DeepSeekRateLimitError as e:
                # Convert to regular exception so outer retry loop can handle it
                # (allows backoff + account switching instead of immediate 429)
                err_str = f"DeepSeek rate limit: {e}"
                logger.info(f"[RATE_LIMIT_CONVERT] Converting DeepSeekRateLimitError to Exception for outer retry")
                raise Exception(err_str)
            except Exception as e:
                err_str = str(e)
                is_rate_e = any(t in err_str.lower() for t in _RATE_ERRORS)
                is_len_e = any(t in err_str.lower() for t in _LENGTH_ERRORS)

                if is_rate_e:
                    # Shorter penalty for transient "Server is busy" / "unavailable" vs hard rate limits
                    if "server is busy" in err_str.lower() or "unavailable" in err_str.lower():
                        jitter = 15 + random.randint(0, 10)
                    else:
                        jitter = 60 + random.randint(-10, 15)
                    rate_limiter.set_limited(account_idx, time.time() + jitter)
                    now_ac = time.time()
                    alt_indices = [
                        i
                        for i in range(MAX_ACCOUNTS)
                        if i != account_idx
                        and ap.is_valid(i)
                        and now_ac >= rate_limiter.get_until(i)
                    ]
                    # FIX 2026-09-04: Nie przełączaj konta przy resume
                    # Resume MUSI pozostać na tym samym koncie
                    if alt_indices and not parsed.is_resume:
                        # Release current slot before switching accounts
                        old_idx = account_idx
                        alt = session_manager._find_slot_with_capacity(alt_indices)
                        if alt is None:
                            raise HTTPException(
                                503, "All remaining accounts have full session pools"
                            )
                        account_idx = alt
                        session_manager.release_slot(old_idx)
                        session_manager.acquire_slot(account_idx)
                        try:
                            chat_id = ds.create_session(account_idx)
                        except Exception:
                            session_manager.release_slot(account_idx)
                            raise
                        parent_id = None
                        logger.info(
                            f"[RATE SWITCH] switched account={old_idx}->{account_idx}"
                        )
                        continue
                    # All accounts rate-limited — retry with backoff instead of failing immediately
                    _BACKOFF_DELAYS = [3, 6, 12, 25]
                    _switched = False
                    for _bi, _delay in enumerate(_BACKOFF_DELAYS):
                        logger.info(
                            f"[RATE BACKOFF] All accounts busy, waiting {_delay}s (backoff {_bi + 1}/{len(_BACKOFF_DELAYS)})"
                        )
                        await asyncio.sleep(_delay)
                        now_ac = time.time()
                        _available = [
                            i
                            for i in range(MAX_ACCOUNTS)
                            if ap.is_valid(i) and now_ac >= rate_limiter.get_until(i)
                        ]
                        # FIX 2026-09-04: Nie przełączaj konta przy resume
                        # Resume retry na tym samym koncie
                        if _available and not parsed.is_resume:
                            _alt = session_manager._find_slot_with_capacity(_available)
                            if _alt is not None:
                                old_idx = account_idx
                                account_idx = _alt
                                if old_idx != _alt:
                                    session_manager.release_slot(old_idx)
                                    session_manager.acquire_slot(account_idx)
                                try:
                                    chat_id = ds.create_session(account_idx)
                                except Exception:
                                    session_manager.release_slot(account_idx)
                                    raise
                                parent_id = None
                                logger.info(
                                    f"[RATE BACKOFF] switched account={old_idx}->{account_idx} after {_delay}s backoff"
                                )
                                _switched = True
                                break
                        elif _available and parsed.is_resume:
                            # Resume: konto jest znowu dostępne, retry na tym samym
                            logger.info(
                                f"[RATE BACKOFF] account={account_idx} available after {_delay}s, retrying on SAME account (resume)"
                            )
                            _switched = True
                            break
                    if _switched:
                        continue
                    raise HTTPException(
                        429, f"All accounts rate limited after backoff: {err_str}"
                    )

                if is_len_e and attempt == 0:
                    if parsed.is_resume:
                        try:
                            from server.services.state_service import clear_conv_by_messages
                            clear_conv_by_messages(messages)
                        except Exception:
                            pass
                        target_slot = _select_least_loaded_account(exclude_slot=account_idx)
                        account_idx = target_slot
                        chat_id = ds.create_session(account_idx)
                        parent_id = None
                        parsed.is_resume = False
                        prompt, ref_file_ids = _prepare_new_session_payload(
                            target_slot=account_idx,
                            messages=messages,
                            tools=tools,
                            model_type=parsed.model_type or "default",
                        )
                        logger.info(
                            f"[LENGTH RESUME ROLLOVER] Session context exceeded limit on resume. "
                            f"Rolled over to fresh session {chat_id[:12]} on slot {account_idx} with conversation_history.md"
                        )
                        continue
                    else:
                        chat_id = ds.create_session(account_idx)
                        parent_id = None
                        prompt, parent_id, was_chunked = await self._orchestrate_chunks_if_needed(
                            prompt=prompt,
                            account_idx=account_idx,
                            chat_id=chat_id,
                            parent_id=parent_id,
                            model_type=parsed.model_type,
                            messages=messages,
                            tools=tools,
                            thinking_enabled=parsed.thinking_enabled,
                            search_enabled=parsed.search_enabled,
                            user_uuid=user_uuid,
                        )
                        logger.info(f"[LENGTH RETRY] new session {chat_id[:12]}...")
                        continue

                logger.error(
                    f"[STREAM_FAILED] attempt={attempt} account={account_idx} chat_id={chat_id[:12] if chat_id else 'none'}: {err_str}"
                )
                raise HTTPException(
                    502, f"DeepSeek stream failed (attempt={attempt}): {err_str}"
                )
            else:
                # ── Success path (no exception raised by stream_completion) ──
                # stream_meta_obj is only meaningful here — on exception it is
                # never assigned, so this check has to live here, NOT in the
                # except block (that was dead code in older revisions).
                if stream_meta_obj.get("no_data") and parsed.is_resume and attempt == 0:
                    # EMPTY RESUME: session returned no preamble data lines — dead.
                    # Start a fresh session and retry once.
                    logger.info(
                        f"[EMPTY RESUME] session {chat_id[:12]} is dead — creating new session"
                    )
                    with conv_lock:
                        dead_keys = [
                            k
                            for k, v in conv_state.items()
                            if v.get("chat_id") == chat_id
                        ]
                        for k in dead_keys:
                            conv_state.pop(k, None)
                    chat_id = ds.create_session(account_idx)
                    parent_id = None
                    # Rebuild prompt for new session (full context, including tools)
                    raw_msgs_new = list(parsed.messages)
                    msg_limit = 20
                    if len(raw_msgs_new) > msg_limit:
                        sys_m = [m for m in raw_msgs_new if m.get("role") == "system"]
                        non_sys_m = [
                            m for m in raw_msgs_new if m.get("role") != "system"
                        ]
                        raw_msgs_new = sys_m + non_sys_m[-(msg_limit - len(sys_m)) :]
                    msgs_to_send_new: list[dict] = []
                    # No truncation of tool results: Trae already truncates
                    # files before sending, so pass content through unchanged.
                    for m in raw_msgs_new:
                        mc = dict(m)
                        msgs_to_send_new.append(mc)
                    sp, hist, um = _extract_prompt_parts(msgs_to_send_new)
                    _empty_um_preview = (um[:80] + "...") if len(um) > 80 else um
                    _empty_hist_user_count = sum(
                        1 for h in (hist or []) if h.get("role") == "user"
                    )
                    _empty_hist_user_previews = [
                        str(h.get("content", "")[:60])
                        for h in (hist or [])
                        if h.get("role") == "user"
                    ]
                    _empty_um_in_hist = sum(
                        1
                        for h in (hist or [])
                        if h.get("role") == "user"
                        and um
                        and um[:60] in str(h.get("content", ""))
                    )
                    logger.info(
                        f"[EMPTY RESUME DIAG] raw_msgs_new_len={len(raw_msgs_new)} msgs_to_send_new_len={len(msgs_to_send_new)}"
                    )
                    logger.info(
                        f"[EMPTY RESUME DIAG] um={_empty_um_preview!r} hist_user_count={_empty_hist_user_count}"
                    )
                    logger.info(
                        f"[EMPTY RESUME DIAG] hist_user_previews={_empty_hist_user_previews}"
                    )
                    logger.info(
                        f"[EMPTY RESUME DIAG] um_in_hist_count={_empty_um_in_hist}"
                    )
                    prompt = PromptBuilder.build(
                        user_message=um or "",
                        system_prompt=sp,
                        history=hist if hist else None,
                        tools_schema=tools if tools else None,
                    )
                    if len(prompt) > PROMPT_CHUNK_THRESHOLD:
                        try:
                            lean_prompt, docs = extract_oversized_blocks_to_attachments(prompt)
                            if docs:
                                logger.info(
                                    f"[DOC_ATTACHMENT] Empty resume extracted {len(docs)} attachment(s), "
                                    f"prompt reduced from {len(prompt)} to {len(lean_prompt)} chars"
                                )
                                prompt = lean_prompt
                                doc_attachments = docs
                        except Exception as de:
                            logger.warning(f"[DOC_ATTACHMENT] Extraction failed in empty resume: {de}")
                    prompt, parent_id, was_chunked = await self._orchestrate_chunks_if_needed(
                        prompt=prompt,
                        account_idx=account_idx,
                        chat_id=chat_id,
                        parent_id=parent_id,
                        model_type=parsed.model_type,
                        messages=messages,
                        tools=tools,
                        thinking_enabled=parsed.thinking_enabled,
                        search_enabled=parsed.search_enabled,
                        user_uuid=user_uuid,
                    )
                    logger.info(
                        f"[EMPTY RESUME] retrying with new session {chat_id[:12]}"
                    )
                    continue

                if stream_meta_obj.get("no_data") and not parsed.is_resume:
                    # New session with empty preamble — server may still stream
                    # content. Don't raise RuntimeError; let _stream_gen handle.
                    logger.warning(
                        f"[NO_DATA] preamble has no data lines for session={chat_id[:12]}, but stream may still have content — proceeding"
                    )

                # Success: stop the retry loop immediately.
                # Without this break every successful attempt runs
                # stream_completion again, re-sending the same user message.
                break

        if stream_gen_obj is None:
            session_manager.release_slot(account_idx)
            raise HTTPException(503, "All DeepSeek accounts unavailable")

        # Immediately persist the new response_message_id as the parent for subsequent requests.
        # This prevents branching/sibling creation (< 1 / 2 >) in DeepSeek Web Chat if a concurrent request arrives,
        # if the stream is interrupted, or if the server restarts while the model is thinking.
        initial_resp_id = stream_meta_obj.get("resp_msg_id")
        if initial_resp_id is not None and chat_id:
            set_conv(
                messages,
                chat_id,
                initial_resp_id,
                account_idx,
                user_uuid=user_uuid,
                model_type=parsed.model_type,
                thinking_enabled=parsed.thinking_enabled,
                search_enabled=parsed.search_enabled,
                tools=tools,
            )
            logger.info(
                f"[CONV_PERSIST] Early persisted active response_id={initial_resp_id} as new parent_id for session={chat_id[:12]}"
            )

        t4 = time.time()
        logger.info(
            f"[TIMING] t3-stream_started: {t4 - t3:.3f}s (total: {t4 - t0:.3f}s)"
        )

        conv_uuid = uuid.uuid4().hex[:12]

        # ── Dashboard instrumentation ─────────────────────────────
        _dashboard.on_conversation_started(
            conv_id=conv_uuid,
            chat_id=chat_id,
            account_slot=account_idx,
            user_uuid=user_uuid,
            model=model,
        )

        # ── Wrap generator with slot release ─────────────────────────
        def _wrap(gen: Generator, slot: int) -> Generator:
            try:
                yield from gen
            finally:
                session_manager.release_slot(slot)

        gen = _wrap(
            _stream_gen(
                stream_gen=stream_gen_obj,
                stream_meta=stream_meta_obj,
                messages=messages,
                parent_id=parent_id,
                chat_id=chat_id,
                conv_uuid=conv_uuid,
                account_idx=account_idx,
                tools=tools,
                model=model,
                t0=t0,
                t4=t4,
                prompt=prompt,
                user_uuid=user_uuid,
                stop=raw_json.get("stop"),
                model_type=parsed.model_type,
                thinking_enabled=parsed.thinking_enabled,
                search_enabled=parsed.search_enabled,
                ref_file_ids=uploaded_file_ids,
            ),
            account_idx,
        )

        # ── Streaming mode: return StreamingResponse immediately without blocking asyncio loop ──
        if parsed.stream:
            return StreamingResponse(
                gen,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # ── Non-stream mode ───────────────────────────────────────────
        content_accum = ""
        tc_accum: list[dict] = []
        finish_reason = "stop"

        for chunk in gen:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                try:
                    data = json.loads(chunk[6:].strip())
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})
                    if delta.get("content"):
                        content_accum += delta["content"]
                    if delta.get("tool_calls"):
                        tc_accum.extend(delta["tool_calls"])
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
                except Exception:
                    pass

        response = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content_accum or None,
                    },
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
        if tc_accum:
            response["choices"][0]["message"]["tool_calls"] = tc_accum
        return JSONResponse(content=response)

    # ── Dry-run endpoint ────────────────────────────────────────────

    async def dry_run(self, raw_request: Request) -> JSONResponse:
        LOG_FILE = Path("dry_run_logs.ndjson")
        body_bytes = await raw_request.body()
        body_str = body_bytes.decode("utf-8", "ignore")
        try:
            raw_json: dict = json.loads(body_str)
        except Exception as e:
            return JSONResponse(
                status_code=400, content={"error": f"Invalid JSON: {e}"}
            )

        t0 = time.time()

        tools = list(raw_json.get("tools") or [])
        tool_choice = raw_json.get("tool_choice")
        if not tool_choice and tools:
            tool_choice = "auto"
        if tool_choice == "none":
            tools = []
        elif isinstance(tool_choice, dict) and tools:
            fn_name = tool_choice.get("function", {}).get("name", "")
            if fn_name:
                tools = [
                    t for t in tools if t.get("function", {}).get("name") == fn_name
                ]

        messages = list(raw_json.get("messages", []))
        state = get_conv(messages)
        # Fallback: if Trae didn't send tools, use saved ones from state
        if not tools and state:
            tools = list(state.get("tools") or [])
        parsed = InputParser.parse(raw_json, state)

        # ── Diagnostic: dump all request keys ──────────────────
        _all_keys = {k: type(v).__name__ for k, v in raw_json.items()}
        _array_lens = {
            k: len(v) for k, v in raw_json.items() if isinstance(v, (list, dict))
        }
        logger.info(
            f"[DIAG DRY] resume={parsed.is_resume} all_keys={_all_keys} array_lens={_array_lens}"
        )
        _ignored = [
            k
            for k in raw_json
            if k
            not in (
                "messages",
                "tools",
                "model",
                "stream",
                "max_tokens",
                "max_completion_tokens",
                "temperature",
                "top_p",
                "stop",
                "tool_choice",
                "parallel_tool_calls",
                "reasoning_effort",
                "frequency_penalty",
                "presence_penalty",
                "user",
                "n",
                "seed",
                "response_format",
                "metadata",
            )
        ]
        if _ignored:
            logger.info(f"[DIAG DRY] unknown_keys={_ignored}")

        account_idx = account_selector.select_account(messages, state, parsed.is_resume)

        # Message preprocessing (mirrors chat_completions)
        msgs_to_send: list[dict] = []
        raw_msgs = list(parsed.messages)
        msg_limit = 20 if not parsed.is_resume else 30

        raw_msg_summary = []
        for m in raw_msgs:
            role = m.get("role", "?")
            content = m.get("content", "")
            c_str = str(content) if not isinstance(content, str) else content
            raw_msg_summary.append(
                {
                    "role": role,
                    "content_len": len(c_str),
                    "content_preview": c_str[:200],
                }
            )

        if len(raw_msgs) > msg_limit:
            sys_msgs = [m for m in raw_msgs if m.get("role") == "system"]
            non_sys = [m for m in raw_msgs if m.get("role") != "system"]
            recent = max(1, msg_limit - len(sys_msgs))
            raw_msgs = sys_msgs + non_sys[-recent:]

        processing_notes = []
        # No truncation of tool results: Trae already truncates files
        # before sending, so pass content through unchanged.
        for m in raw_msgs:
            m_copy = dict(m)
            msgs_to_send.append(m_copy)

        # Build prompt
        system_prompt, history, user_message = _extract_prompt_parts(msgs_to_send, is_resume=parsed.is_resume)
        try:
            prompt = PromptBuilder.build(
                user_message=user_message or "",
                system_prompt=system_prompt,
                history=history if history else None,
                tools_schema=tools if tools else None,
            )
        except Exception as e:
            prompt = f"[PROMPT BUILD ERROR: {e}]"

        session_info: dict = {}
        if state:
            session_info = {
                "found": True,
                "chat_id": state.get("chat_id", "")[:20] + "...",
                "parent_id": str(state.get("parent_id", ""))[:30],
                "account": state.get("account"),
                "resume": parsed.is_resume,
            }
        else:
            session_info = {"found": False, "resume": False}

        ts = datetime.datetime.now().isoformat()
        log_entry = {
            "ts": ts,
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
            "model": raw_json.get("model"),
            "stream": raw_json.get("stream", True),
            "account_idx": account_idx,
            "session": session_info,
            "raw": {
                "msg_count": len(raw_json.get("messages", [])),
                "messages": raw_msg_summary,
                "tools_count": len(tools),
            },
            "processed": {
                "msg_count_after_trim": len(msgs_to_send),
                "msg_limit_applied": msg_limit,
                "processing_notes": processing_notes,
                "prompt_chars": len(prompt),
                "prompt_preview": prompt[:500],
                "prompt_tail": prompt[-300:] if len(prompt) > 500 else None,
            },
        }

        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.info(f"[DRY-RUN] log write error: {e}")

        return JSONResponse(content=log_entry)

    # ── Other endpoints ────────────────────────────────────────────

    async def list_models(self) -> dict:
        return {
            "object": "list",
            "data": [
                {
                    "id": "deepseek-v4-pro",
                    "object": "model",
                    "created": 1745452800,
                    "owned_by": "deepseek",
                },
                {
                    "id": "deepseek-v4-flash",
                    "object": "model",
                    "created": 1745452800,
                    "owned_by": "deepseek",
                },
                {
                    "id": "deepseek-vision",
                    "object": "model",
                    "created": 1745452800,
                    "owned_by": "deepseek",
                },
            ],
        }

    async def list_accounts(self) -> dict:
        accounts_data = []
        for i in range(MAX_ACCOUNTS):
            is_valid = ap.is_valid(i)
            rate_until = rate_limiter.get_until(i)
            accounts_data.append(
                {
                    "slot": i,
                    "valid": is_valid,
                    "rate_limited_until": rate_until,
                    "rate_limited": time.time() < rate_until,
                }
            )
        return {"accounts": accounts_data}

    async def login(self, slot: int = 0) -> dict:
        from server.services.auth_service import AuthService
        from server.core.deepseek_client import ap as _ap

        auth_service = AuthService(pool=_ap)
        return await auth_service.login(slot)


