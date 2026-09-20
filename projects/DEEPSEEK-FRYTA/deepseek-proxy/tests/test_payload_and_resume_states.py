import pytest
from unittest.mock import MagicMock, patch
from server.core.deepseek_client import DeepSeek, Session, AccountPool

@pytest.fixture
def mock_setup():
    mock_pool = MagicMock(spec=AccountPool)
    mock_session = Session(
        auth_token="token_xyz_987",
        cookies={"ds_session_id": "cookie_val_123"},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    mock_pool.slots = [mock_session]
    mock_pool.is_valid.return_value = True
    client = DeepSeek(mock_pool)
    return client, mock_session

@patch("curl_cffi.requests.post")
def test_new_session_payload_and_headers(mock_global_post, mock_setup):
    client, session = mock_setup
    
    # Mockujemy PoW w kliencie, by uniknąć zapytania o challenge i PoW solvera
    client._get_pow = MagicMock(return_value="mocked_pow_response")

    # Mockujemy pomyślną odpowiedź streamu od DeepSeek
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        b'data: {"type": "message", "response_message_id": 101}',
        b'data: {"p": "", "v": "Hello world"}'
    ]
    mock_global_post.return_value = mock_resp

    # Wywołujemy stream_completion dla nowej sesji
    client.stream_completion(
        slot=0,
        chat_session_id="new-chat-uuid-111",
        prompt="This is a new session prompt",
        parent_message_id=None
    )

    # Weryfikujemy globalny POST (główny request completion)
    mock_global_post.assert_called_once()
    kwargs = mock_global_post.call_args[1]

    # Weryfikacja nagłówków (Headers)
    headers = kwargs["headers"]
    assert headers["authorization"] == f"Bearer {session.auth_token}"
    assert headers["user-agent"] == session.user_agent
    assert headers["referer"] == "https://chat.deepseek.com/a/chat/s/new-chat-uuid-111"
    assert headers["x-ds-pow-response"] == "mocked_pow_response"
    assert headers["x-client-bundle-id"] == "com.deepseek.chat"
    assert "sec-ch-ua" not in headers

    # Weryfikacja Payload (JSON body)
    payload = kwargs["json"]
    assert payload["chat_session_id"] == "new-chat-uuid-111"
    assert payload["parent_message_id"] is None
    assert payload["model_type"] == "expert"
    assert payload["prompt"] == "This is a new session prompt"
    assert payload["thinking_enabled"] is True

@patch("curl_cffi.requests.post")
def test_resume_session_payload_and_headers(mock_global_post, mock_setup):
    client, session = mock_setup
    
    # Mockujemy PoW
    client._get_pow = MagicMock(return_value="mocked_pow_response")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        b'data: {"type": "message", "response_message_id": 102}',
        b'data: {"p": "", "v": "Continued response"}'
    ]
    mock_global_post.return_value = mock_resp

    # Wywołujemy stream_completion dla wznawiania (parent_message_id=101)
    client.stream_completion(
        slot=0,
        chat_session_id="existing-chat-uuid-222",
        prompt="This is a resume session prompt",
        parent_message_id=101
    )

    # Weryfikujemy globalny POST
    mock_global_post.assert_called_once()
    kwargs = mock_global_post.call_args[1]

    # Weryfikacja nagłówków (Headers)
    headers = kwargs["headers"]
    assert headers["authorization"] == f"Bearer {session.auth_token}"
    assert headers["referer"] == "https://chat.deepseek.com/a/chat/s/existing-chat-uuid-222"
    assert headers["x-client-bundle-id"] == "com.deepseek.chat"
    assert "sec-ch-ua" not in headers

    # Weryfikacja Payload (JSON body)
    payload = kwargs["json"]
    assert payload["chat_session_id"] == "existing-chat-uuid-222"
    assert payload["parent_message_id"] == 101
    assert payload["model_type"] is None
    assert payload["prompt"] == "This is a resume session prompt"
