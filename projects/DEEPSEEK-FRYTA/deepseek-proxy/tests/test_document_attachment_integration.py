"""tests/test_document_attachment_integration.py — Integration tests for document attachments."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from server.services.proxy_service import ProxyService
from server.services.document_attachment_service import (
    extract_oversized_blocks_to_attachments,
    PROMPT_ATTACHMENT_THRESHOLD,
)


@pytest.mark.asyncio
async def test_proxy_service_uploads_document_attachment_for_oversized_prompt():
    """Verify that ProxyService extracts oversized tool results, uploads them via ds.upload_file,
    and passes the file ID in ref_file_ids to ds.stream_completion."""
    svc = ProxyService()

    # Create an oversized tool result payload (> 35k characters)
    huge_content = "X" * 40_000
    oversized_prompt = (
        "[User]:\n<tool_result>\n<t>read_file</t>\n<id>call_large_123</id>\n<content>\n"
        + huge_content
        + "\n</content>\n</tool_result>\nPlease analyze this."
    )

    fake_body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": oversized_prompt},
        ],
        "stream": True,
    }

    fake_request = MagicMock()
    fake_request.headers = {}
    fake_request.body = AsyncMock(return_value=json.dumps(fake_body).encode("utf-8"))
    fake_request.is_disconnected = AsyncMock(return_value=False)

    uploaded_files = []

    def fake_upload_file(slot, file_data, filename, mime_type, model_type):
        uploaded_files.append({
            "slot": slot,
            "filename": filename,
            "mime_type": mime_type,
            "data_len": len(file_data),
        })
        return "file-doc-test-999"

    mock_stream_gen = (x for x in ["Hello from model", " with attachment knowledge"])
    stream_meta = {"resp_msg_id": 12345, "no_data": False}

    with patch("server.services.proxy_service.account_selector.select_account", return_value=0), \
         patch("server.services.proxy_service.session_manager.acquire_slot", return_value=True), \
         patch("server.services.proxy_service.session_manager.release_slot"), \
         patch("server.services.proxy_service.ds.create_session", return_value="sess-test-uuid"), \
         patch("server.services.proxy_service.ds.upload_file", side_effect=fake_upload_file) as mock_upload, \
         patch("server.services.proxy_service.ds.stream_completion", return_value=(mock_stream_gen, stream_meta)) as mock_stream, \
         patch("server.services.proxy_service.get_conv", return_value=None), \
         patch("server.services.proxy_service.set_conv"):

        # Call chat_completions
        response = await svc.chat_completions(fake_request)
        assert response is not None

        # Verify upload was called with markdown document
        assert len(uploaded_files) >= 1
        assert uploaded_files[0]["filename"] == "tool_result_call_large_123.md"
        assert uploaded_files[0]["mime_type"] == "text/markdown"
        assert uploaded_files[0]["data_len"] == len(huge_content.encode("utf-8"))

        # Verify stream_completion received the file ID in ref_file_ids
        mock_stream.assert_called_once()
        _, kwargs = mock_stream.call_args
        assert "file-doc-test-999" in kwargs.get("ref_file_ids", [])

        # Verify the prompt sent to stream_completion is now lean (< 35k)
        called_prompt = mock_stream.call_args[0][2]
        assert len(called_prompt) < PROMPT_ATTACHMENT_THRESHOLD
        assert "[Full output provided in attached document(s): tool_result_call_large_123.md]" in called_prompt
