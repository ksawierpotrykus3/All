"""All proxy constants in one place - now backed by Pydantic Settings."""

from __future__ import annotations

import re
from server.config.settings import settings

# --- Accounts ---
MAX_ACCOUNTS = settings.max_accounts
MAX_PARALLEL_TOOL_CALLS = settings.max_parallel_tool_calls
MAX_SESSIONS_PER_ACCOUNT = settings.max_sessions_per_account

# --- Conversation state ---
_TTL = settings.ttl
DEDUP_TTL = settings.dedup_ttl

# --- Watermark ---
WATERMARK_ENABLED = settings.watermark_enabled

# Watermark pattern for conversation continuity
WM_PATTERN = re.compile(r'<!--\s*PROXY_SID:\s*([a-f0-9\-]+)\s*-->', re.IGNORECASE)

# Content strip pattern - strips internal DeepSeek formatting/status tags from stream content
_CONTENT_STRIP_PATTERN = re.compile(
    r"<thinking[^>]*>(?:.*?</thinking>|.*)|"
    r"</?center[^>]*>|"
    r"<tool_result[^>]*>(?:.*?</tool_result>|.*)|</?tool_result>|"
    r"<tool_call[^>]*>(?:.*?？|.*)|</?tool_call>|"
    r"<function_call[^>]*>(?:.*?</function_call>|.*)|</?function_call>|"
    r"<function_calls[^>]*>(?:.*?</function_calls>|.*)|</?function_calls>|"
    r"<toolcall_status[^>]*>(?:.*?</toolcall_status>|.*)|</?toolcall_status>|"
    r"<toolcall_result[^>]*>(?:.*?</toolcall_result>|.*)|</?toolcall_result>|"
    r"<result[^>]*>|</result>|"
    r"<status[^>]*>(?:.*?</status>|.*)|"
    r"</?attempt_completion[^>]*>.*?</attempt_completion>|"
    r"</?(?:attempt_completion)[^>]*\s*/?>|"
    r"<reasoning[^>]*>(?:.*?</reasoning>|.*)",
    re.DOTALL | re.IGNORECASE
)

# --- Dashboard ---
DB_PATH = settings.dashboard_db_path
