"""tests/test_document_attachment_service.py — Tests for Document Attachment Strategy."""

import pytest
from server.services.document_attachment_service import (
    extract_oversized_blocks_to_attachments,
    MAX_DOCUMENT_SIZE_BYTES,
)


def test_extract_under_threshold():
    prompt = "Simple short prompt below threshold"
    res_prompt, attachments = extract_oversized_blocks_to_attachments(prompt, threshold=1000)
    assert res_prompt == prompt
    assert len(attachments) == 0


def test_extract_oversized_tool_result():
    large_body = "Line of audit result data\n" * 500  # ~13,000 chars
    block = (
        "<tool_result>\n<t>read_file</t>\n<id>call_abc_123</id>\n<content>\n"
        + large_body
        + "</content>\n</tool_result>"
    )
    prompt = f"[User]: Here are the results:\n{block}"

    res_prompt, attachments = extract_oversized_blocks_to_attachments(
        prompt, threshold=5000
    )

    assert len(attachments) == 1
    att = attachments[0]
    assert att["filename"] == "tool_result_call_abc_123.md"
    assert att["mime_type"] == "text/markdown"
    assert large_body.strip().encode("utf-8") in att["data"]

    # In modified prompt, body is replaced with document reference
    assert "[Full output provided in attached document(s): tool_result_call_abc_123.md]" in res_prompt
    assert len(res_prompt) < len(prompt)
    assert "<tool_result>" in res_prompt
    assert "</tool_result>" in res_prompt


def test_extract_split_over_max_file_size():
    # Test splitting when payload exceeds max_file_size limit (e.g. 100 MB or custom threshold)
    large_body = "X" * 2500
    block = (
        "<tool_result>\n<t>read_file</t>\n<id>call_huge</id>\n<content>\n"
        + large_body
        + "</content>\n</tool_result>"
    )
    prompt = f"[User]:\n{block}"

    # Set max_file_size to 1000 bytes so 2500 bytes splits into 3 parts
    res_prompt, attachments = extract_oversized_blocks_to_attachments(
        prompt, threshold=1000, max_file_size=1000
    )

    assert len(attachments) == 3
    assert attachments[0]["filename"] == "tool_result_call_huge_part1.md"
    assert attachments[1]["filename"] == "tool_result_call_huge_part2.md"
    assert attachments[2]["filename"] == "tool_result_call_huge_part3.md"

    assert "tool_result_call_huge_part1.md, tool_result_call_huge_part2.md, tool_result_call_huge_part3.md" in res_prompt


def test_extract_oversized_rules_to_project_rules_md():
    """Verify that oversized <rules> or <always_applied_workspace_rules> blocks
    are extracted into project_rules.md instead of an arbitrary context_payload.md."""
    rules_body = "# PYTHON CLEAN ARCHITECTURE INSTRUCTIONS\n" + ("Rule details...\n" * 400)  # ~6,000 chars
    rules_block = (
        "<rules>\n<always_applied_workspace_rules>\n"
        + rules_body
        + "\n</always_applied_workspace_rules>\n</rules>"
    )
    prompt = f"System Preamble\n{rules_block}\n[User]: Please audit my code."

    res_prompt, attachments = extract_oversized_blocks_to_attachments(
        prompt, threshold=3000, min_rules_size=1000
    )

    assert len(attachments) == 1
    assert attachments[0]["filename"] == "project_rules.md"
    assert attachments[0]["mime_type"] == "text/markdown"
    assert rules_body.strip().encode("utf-8") in attachments[0]["data"]

    assert "[Project rules and coding instructions provided in attached document(s): project_rules.md" in res_prompt
    assert "[User]: Please audit my code." in res_prompt


def test_extract_oversized_history_to_conversation_history_md():
    """Verify that long prior conversation history is extracted into conversation_history.md,
    keeping System preamble, tools, and the latest user query intact."""
    history_body = (
        "[Assistant]: Let me check file A.\n"
        "<tool_calls><invoke name='Read'></invoke></tool_calls>\n"
        "[Tool Result]: File A contents...\n"
    ) * 30  # ~4,000 chars
    prompt = f"System Preamble\nTools Schema\n{history_body}[User]: Now check file B."

    res_prompt, attachments = extract_oversized_blocks_to_attachments(
        prompt, threshold=2000, min_history_size=1000
    )

    assert len(attachments) == 1
    assert attachments[0]["filename"] == "conversation_history.md"
    assert "System Preamble" in res_prompt
    assert "Tools Schema" in res_prompt
    assert "[Prior conversation history is provided in attached document(s): conversation_history.md]" in res_prompt
    assert "[User]: Now check file B." in res_prompt


def test_extract_oversized_monolith_context():
    # Raw monolith text without any tags or structure
    huge_monolith = "A" * 15_000
    res_prompt, attachments = extract_oversized_blocks_to_attachments(
        huge_monolith, threshold=5000
    )

    assert len(attachments) >= 1
    assert "context_payload" in attachments[0]["filename"]
    assert "[SYSTEM NOTE: The remaining context" in res_prompt
    assert len(res_prompt) <= 17_000


def test_format_and_create_history_attachments():
    from server.services.document_attachment_service import (
        format_history_to_markdown,
        create_history_attachments,
    )

    history = [
        {"role": "user", "content": "How do I audit the bot?"},
        {
            "role": "assistant",
            "content": "I will read the main file.",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {"name": "read_file", "arguments": '{"path": "bot.py"}'},
                }
            ],
        },
        {"role": "tool", "name": "read_file", "content": "print('hello from bot')"},
    ]

    md = format_history_to_markdown(history)
    assert "## Turn 1 - User" in md
    assert "How do I audit the bot?" in md
    assert "## Turn 2 - Assistant" in md
    assert "### Tool Calls:" in md
    assert "read_file" in md
    assert "call_123" in md
    assert "## Turn 3 - Tool (read_file)" in md
    assert "print('hello from bot')" in md

    attachments = create_history_attachments(history, max_file_size=100_000)
    assert len(attachments) == 1
    assert attachments[0]["filename"] == "conversation_history.md"
    assert attachments[0]["mime_type"] == "text/markdown"
    assert b"print('hello from bot')" in attachments[0]["data"]

