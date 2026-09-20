import pytest
from unittest.mock import MagicMock, patch
from server.core.deepseek_client import DeepSeek, Session, AccountPool

@pytest.fixture
def mock_setup():
    mock_pool = MagicMock(spec=AccountPool)
    session = Session(
        auth_token="test_token_123",
        cookies={"ds_session_id": "test_cookie"},
        user_agent="Mozilla/5.0 Test",
    )
    mock_pool.slots = [session]
    mock_pool.is_valid.return_value = True
    client = DeepSeek(mock_pool)
    return client, session

def test_send_interim_chunk_autocorrects_invalid_parent(mock_setup):
    client, session = mock_setup
    client._get_pow = MagicMock(return_value="mock_pow")
    client._throttle = MagicMock()

    # Pierwsze żądanie zwraca biz_code: 26 (invalid message id)
    # Drugie żądanie (po autokorekcie) zwraca poprawną odpowiedź SSE z response_message_id: 10
    resp_invalid = MagicMock()
    resp_invalid.status_code = 200
    resp_invalid.iter_lines.return_value = [
        b'{"code":0,"msg":"","data":{"biz_code":26,"biz_msg":"invalid message id","biz_data":null}}'
    ]

    resp_valid = MagicMock()
    resp_valid.status_code = 200
    resp_valid.iter_lines.return_value = [
        b'data: {"response_message_id": 10, "model_type": "default"}'
    ]

    with patch("curl_cffi.requests.post", side_effect=[resp_invalid, resp_valid]) as mock_post:
        # Mockujemy get_last_message_id, aby zwróciło rzeczywisty ostatni ID = 4
        client.get_last_message_id = MagicMock(return_value=4)

        result_id = client.send_interim_chunk(
            slot=0,
            chat_session_id="test_session_123",
            prompt="Test prompt",
            parent_message_id=6,  # desynchronizowane ID (6 zamiast 4)
            model_type="default",
        )

        assert result_id == 10
        # Weryfikujemy, że get_last_message_id zostało wywołane
        client.get_last_message_id.assert_called_once_with(0, "test_session_123")
        # Weryfikujemy, że drugie wywołanie POST poszło z parent_message_id = 4
        assert mock_post.call_count == 2
        second_call_body = mock_post.call_args_list[1][1]["json"]
        assert second_call_body["parent_message_id"] == 4
