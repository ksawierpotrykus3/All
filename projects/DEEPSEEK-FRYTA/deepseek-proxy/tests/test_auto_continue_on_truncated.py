import pytest
import re
from server.services.proxy_service import _is_response_truncated
from server.services.document_attachment_service import format_history_to_markdown

def test_is_response_truncated_detection():
    # 1. Server did not report finished
    assert _is_response_truncated("All good", {"is_finished": False}) is True
    assert _is_response_truncated("All good", {"is_finished": True}) is False

    # 2. Odd count of code fences (truncated code block)
    fence = "```"
    truncated_code = f"Here is the code:\n{fence}python\ndef calculate():\n    return 42"
    completed_code = f"Here is the code:\n{fence}python\ndef calculate():\n    return 42\n{fence}\nDone."
    assert _is_response_truncated(truncated_code, {"is_finished": True}) is True
    assert _is_response_truncated(completed_code, {"is_finished": True}) is False

    # 3. Multiple code blocks, one unclosed
    two_blocks_one_open = f"{fence}python\nprint(1)\n{fence}\nAnd then:\n{fence}bash\npytest"
    assert _is_response_truncated(two_blocks_one_open, {"is_finished": True}) is True

    # 4. Unclosed invoke XML tags
    truncated_invoke = '<tool_calls><invoke name="run_script"><parameter name="cmd">python'
    completed_invoke = '<tool_calls><invoke name="run_script"><parameter name="cmd">python</parameter></invoke></tool_calls>'
    assert _is_response_truncated(truncated_invoke, {"is_finished": True}) is True
    assert _is_response_truncated(completed_invoke, {"is_finished": True}) is False


def test_format_history_full_retention():
    # Construct 30 turns with oversized content in middle turns
    history = []
    # Turn 1: user
    history.append({"role": "user", "content": "Initial user task requirements"})
    # Turn 2: assistant
    history.append({"role": "assistant", "content": "I understand the plan."})
    
    # Intermediate turns (turns 3 to 25) with heavy tool results
    for i in range(3, 26):
        history.append({
            "role": "tool",
            "name": f"tool_{i}",
            "content": f"Result of execution for tool_{i}: data output.",
        })
        history.append({
            "role": "assistant",
            "content": f"Processing turn {i} result.",
        })

    # Last 5 turns
    for i in range(26, 31):
        history.append({
            "role": "user",
            "content": f"User query turn {i}",
        })
        history.append({
            "role": "assistant",
            "content": f"Assistant response turn {i}",
        })

    md = format_history_to_markdown(history)
    assert "# Full Conversation History from IDE" in md
    assert "Initial user task requirements" in md
    # Make sure every single turn is retained (100% context retention)
    for i in range(3, 26):
        assert f"tool_{i}" in md
        assert f"Processing turn {i} result." in md
    assert "User query turn 30" in md
    assert "Assistant response turn 30" in md


def test_stream_continue_seamless_assembly(monkeypatch):
    from unittest.mock import MagicMock
    from server.services.proxy_service import _stream_gen

    # Mock DeepSeek client
    mock_ds = MagicMock()
    # Continuation stream returns remaining tokens and finishes
    mock_ds.stream_continue.return_value = (
        iter(["    return 'success'\n```\nFinished execution!"]),
        {"resp_msg_id": 101, "is_finished": True}
    )

    import server.services.proxy_service as ps
    monkeypatch.setattr(ps, "ds", mock_ds)

    # Initial stream yields incomplete code fence (truncated)
    initial_gen = iter(["Here is the python code:\n```python\ndef run():\n"])
    initial_meta = {"resp_msg_id": 101, "is_finished": False}

    chunks = list(_stream_gen(
        stream_gen=initial_gen,
        stream_meta=initial_meta,
        messages=[{"role": "user", "content": "Write python code"}],
        parent_id=None,
        chat_id="sess_auto_cont_123",
        conv_uuid="uuid_test",
        account_idx=0,
        tools=None,
        model="deepseek-chat",
        t0=0,
        t4=0,
        prompt="Write python code",
        user_uuid="user_123",
        stop=None,
        model_type="default",
        thinking_enabled=True,
        search_enabled=False,
    ))

    # Verify stream_continue was called on the mock
    assert mock_ds.stream_continue.called
    args, kwargs = mock_ds.stream_continue.call_args
    assert args[1] == "sess_auto_cont_123"
    assert args[2] == 101

    full_output = "".join(chunks)
    assert "Here is the python code:" in full_output
    assert "def run():" in full_output
    assert "return 'success'" in full_output
    assert "Finished execution!" in full_output
    assert "data: [DONE]\n\n" in full_output

