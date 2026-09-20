"""tests/test_conversation_history_preservation.py — Verify preservation of full IDE conversation history."""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import Request


from server.services.proxy_service import ProxyService
from server.services.document_attachment_service import create_history_attachments, format_history_to_markdown


def test_format_history_markdown_content():
    """Verify that history formatting correctly captures multi-turn user/assistant/tool dialogues."""
    history = [
        {"role": "user", "content": "Initial workspace setup"},
        {
            "role": "assistant",
            "content": "Running git status",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "function": {"name": "git_status", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "name": "git_status", "content": "Clean tree"},
        {"role": "assistant", "content": "Everything is clean. What next?"},
    ]

    md = format_history_to_markdown(history)
    assert "## Turn 1 - User" in md
    assert "Initial workspace setup" in md
    assert "## Turn 2 - Assistant" in md
    assert "git_status" in md
    assert "## Turn 3 - Tool (git_status)" in md
    assert "Clean tree" in md
    assert "## Turn 4 - Assistant" in md
    assert "Everything is clean" in md

    attachments = create_history_attachments(history)
    assert len(attachments) == 1
    assert attachments[0]["filename"] == "conversation_history.md"
    assert b"Initial workspace setup" in attachments[0]["data"]
    assert b"Clean tree" in attachments[0]["data"]


@pytest.mark.asyncio
async def test_full_history_preservation_on_new_session():
    """Verify that when IDE sends 120 messages on a new session,
    the proxy preserves all of them without capping at 20,
    packs prior history into conversation_history.md,
    and uploads it to ref_file_ids."""
    proxy = ProxyService()

    # Create 120 alternating messages (simulating long IDE history)
    messages = [{"role": "system", "content": "You are an AI coding assistant."}]
    for i in range(1, 120):
        if i % 3 == 1:
            messages.append({"role": "user", "content": f"User prompt step {i}"})
        elif i % 3 == 2:
            messages.append({
                "role": "assistant",
                "content": f"Assistant reply step {i}",
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "function": {"name": "read_file", "arguments": f'{{"path": "file_{i}.py"}}'},
                    }
                ],
            })
        else:
            messages.append({"role": "tool", "name": "read_file", "content": f"Content of file_{i}.py"})

    # Final user prompt
    messages.append({"role": "user", "content": "przejrzyj mój projekt"})

    assert len(messages) == 121

    body = {
        "model": "deepseek-chat",
        "messages": messages,
        "stream": True,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run shell command",
                    "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}},
                },
            }
        ],
    }

    req = MagicMock(spec=Request)
    req.is_disconnected = AsyncMock(return_value=False)
    req.headers = {"user-agent": "test"}
    req.body = AsyncMock(return_value=json.dumps(body).encode("utf-8"))

    uploaded_files = []

    def fake_upload_file(slot, file_data, filename, mime_type, model_type):
        fid = f"uploaded_{filename}"
        uploaded_files.append((fid, filename, len(file_data)))
        return fid

    completion_calls = []

    def fake_stream_completion(account_idx, chat_id, prompt, parent_id, **kwargs):
        completion_calls.append({
            "account_idx": account_idx,
            "chat_id": chat_id,
            "prompt": prompt,
            "parent_id": parent_id,
            "ref_file_ids": kwargs.get("ref_file_ids"),
        })

        def gen():
            yield {"content": "Oto przegląd Twojego projektu"}

        return gen(), {}

    with (
        patch("server.services.proxy_service.ds.upload_file", side_effect=fake_upload_file),
        patch("server.services.proxy_service.ds.stream_completion", side_effect=fake_stream_completion),
        patch("server.services.proxy_service.ds.create_session", return_value="sess_test_123"),
        patch("server.services.proxy_service.session_manager.acquire_slot", return_value=True),
        patch("server.services.proxy_service.session_manager.release_slot"),
        patch("server.services.proxy_service.ap.is_valid", return_value=True),
        patch("server.services.proxy_service.get_conv", return_value=None),  # New session
        patch("server.services.proxy_service.set_conv"),
    ):
        resp = await proxy.chat_completions(req)
        assert resp.status_code == 200


        # Verify that conversation_history.md was uploaded
        hist_uploads = [u for u in uploaded_files if "conversation_history" in u[1]]
        assert len(hist_uploads) >= 1, "conversation_history.md was NOT uploaded!"

        # Verify that the upload contained earlier turns
        assert any("uploaded_conversation_history.md" in call.get("ref_file_ids", []) for call in completion_calls)

        # Verify that the prompt sent to DeepSeek contains the note and latest prompt, but not bloated history
        call = completion_calls[0]
        sent_prompt = call["prompt"]
        assert "przejrzyj mój projekt" in sent_prompt
        assert "Full prior conversation history from IDE" in sent_prompt
        assert "attached in document(s): conversation_history.md" in sent_prompt

        # Verify prompt is lean (< 35,000 chars)
        assert len(sent_prompt) < 35_000
