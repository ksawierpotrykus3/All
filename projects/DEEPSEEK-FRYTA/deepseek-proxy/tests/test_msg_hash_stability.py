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
        assert h1 == h2, (
            "Hash must be stable when only open_and_recently_viewed_files changes"
        )


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
        text = (
            "Hello\n<system_notification>\nTask finished\n</system_notification>\nWorld"
        )
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


class TestMsgHashMultiTurnFollowUp:
    def test_follow_up_user_message_does_not_break_hash(self):
        """When user replies with follow-up like 'tak' or 'continue',
        the conversation hash must remain identical to Turn 1."""
        msgs_turn1 = [
            {"role": "system", "content": "You are assistant"},
            {"role": "user", "content": "<user_info>Workspace: F:\\PROJEKTY\\vinted</user_info>"},
            {"role": "user", "content": "<manually_attached_skills>skills</manually_attached_skills>"},
        ]
        h_turn1 = _msg_hash(msgs_turn1)

        msgs_during_tools = msgs_turn1 + [
            {"role": "assistant", "content": "Running tool..."},
            {"role": "tool", "content": "result 1"},
            {"role": "assistant", "content": "FINAL ANSWER: Done."},
        ]
        h_tools = _msg_hash(msgs_during_tools)
        assert h_turn1 == h_tools

        # Turn 2: User says 'tak'
        msgs_turn2 = msgs_during_tools + [
            {"role": "user", "content": "<user_query>\ntak\n</user_query>"}
        ]
        h_turn2 = _msg_hash(msgs_turn2)
        assert h_turn1 == h_turn2, "Hash must not change when user sends follow-up 'tak' in Turn 2"


class TestWatermarkExtraction:
    def test_watermark_with_uuid_and_pipe(self):
        """Verify _PROXY_CHAT_RE matches UUID chat_id with PROXY_UUID pipe delimiter."""
        from server.services.state_service import _PROXY_CHAT_RE
        text = "Some answer\n<!-- PROXY_CHAT: 93517fc8-1da8-4855-9fbe-a5ed8b3a4ecc | PROXY_UUID: 4f1a2b3c4d5e -->"
        match = _PROXY_CHAT_RE.search(text)
        assert match is not None
        assert match.group(1) == "93517fc8-1da8-4855-9fbe-a5ed8b3a4ecc"


class TestSystemPromptOnlyHashSafety:
    def test_hash_empty_when_no_user_message(self):
        """When request only has system prompt, _msg_hash must return empty string."""
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        assert _msg_hash(msgs) == ""
        assert _msg_hash_legacy(msgs) == ""

    def test_hash_empty_when_user_message_only_has_system_reminder(self):
        """When user message contains ONLY volatile system-reminder, _msg_hash must return empty."""
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "<system-reminder>\nThis is a reminder that your todo list is currently empty.\n</system-reminder>",
            },
        ]
        assert _msg_hash(msgs) == ""
        assert _msg_hash_legacy(msgs) == ""

    def test_get_conv_returns_none_when_only_system_prompt_present(self):
        """get_conv must return None (new session) if there is no stable user query."""
        from server.services.state_service import get_conv
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "<system-reminder>\nThis is a reminder that your todo list is currently empty.\n</system-reminder>",
            },
        ]
        assert get_conv(msgs) is None


