import pytest
from unittest.mock import MagicMock, patch
from server.core.deepseek_client import DeepSeek, Session, AccountPool

def test_headers_structure_matches_legacy():
    # Mockujemy AccountPool oraz sesję
    mock_pool = MagicMock(spec=AccountPool)
    mock_session = Session(
        auth_token="test_token_123",
        cookies={"ds_session_id": "xyz"},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    mock_pool.slots = [mock_session]
    mock_pool.is_valid.return_value = True

    client = DeepSeek(mock_pool)
    
    # Generujemy nagłówki z chat_session_id
    headers = client._headers(
        slot=0,
        pow_resp="pow_challenge_response",
        chat_session_id="session_xyz_123",
    )

    # Weryfikacja obecności wymaganych nagłówków z oficjalnego DeepSeek Web v2.5.0
    assert headers["authorization"] == "Bearer test_token_123"
    assert headers["x-client-locale"] == "en_US"
    assert headers["x-client-platform"] == "web"
    assert headers["x-client-version"] == "2.5.0"
    assert headers["x-client-bundle-id"] == "com.deepseek.chat"
    assert headers["x-client-timezone-offset"] == "7200"
    assert "x-device-id" in headers
    assert headers["x-device-model"] == ""
    assert headers["referer"] == "https://chat.deepseek.com/a/chat/s/session_xyz_123"
    assert headers["x-ds-pow-response"] == "pow_challenge_response"
    assert headers["user-agent"] == mock_session.user_agent

    # Weryfikacja BRAKU anachronicznych nagłówków (x-app-version zniknęło w webappie)
    bad_headers = [
        "x-app-version",
        "sec-ch-ua", 
        "sec-ch-ua-mobile", 
        "sec-ch-ua-platform", 
        "accept-language", 
        "priority", 
    ]
    for h in bad_headers:
        assert h not in headers, f"Wykryto niepożądany nagłówek {h} w żądaniu!"

def test_headers_fallback_user_agent():
    mock_pool = MagicMock(spec=AccountPool)
    # Sesja bez podanego User-Agent (pusta wartość)
    mock_session = Session(
        auth_token="test_token_123",
        cookies={"ds_session_id": "xyz"},
        user_agent=""
    )
    mock_pool.slots = [mock_session]
    mock_pool.is_valid.return_value = True

    client = DeepSeek(mock_pool)
    headers = client._headers(slot=0)

    # Powinien użyć fallbacku opartego o Chrome 120
    assert "Chrome/120.0.0.0" in headers["user-agent"]
