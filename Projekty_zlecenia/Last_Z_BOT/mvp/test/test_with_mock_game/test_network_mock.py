"""Tests for network mock and API simulation"""

import pytest
import time
from mvp.test.mock_game.network_mock import NetworkMock, APIResponse, ErrorInjection


def test_fake_api_responses():
    """Test receiving fake API responses"""
    mock = NetworkMock()
    
    # Register fake response
    mock.register_response("get.treasure.info", {
        "success": True,
        "treasure_id": 12345,
        "reward": 100
    })
    
    # Get response
    response = mock.get_response("get.treasure.info")
    
    assert response is not None
    assert response.success is True
    assert response.data["treasure_id"] == 12345
    assert response.data["reward"] == 100


def test_network_error_handling():
    """Test network error injection and handling"""
    mock = NetworkMock()
    
    # Register error response
    error_response = APIResponse(
        success=False,
        status_code=500,
        data={"error": "Server error"}
    )
    mock.register_response("get.treasure.info", error_response)
    
    # Get response
    response = mock.get_response("get.treasure.info")
    
    assert response.success is False
    assert response.status_code == 500
    assert response.data["error"] == "Server error"


def test_network_timeout_behavior():
    """Test simulating network timeouts"""
    mock = NetworkMock()
    
    # Register response with delay
    delay_response = APIResponse(
        success=True,
        data={"status": "ok"},
        delay_ms=500  # 500ms delay
    )
    mock.register_response("slow.endpoint", delay_response)
    
    # Measure actual delay
    start = time.time()
    response = mock.get_response("slow.endpoint", timeout_ms=1000)
    elapsed = time.time() - start
    
    # Should have approximately 500ms delay
    assert response.success is True
    assert elapsed >= 0.45  # At least 450ms


def test_offline_mode_fallback():
    """Test offline mode fallback responses"""
    mock = NetworkMock()
    mock.set_offline(True)
    
    # When offline, responses should be cached or error
    mock.register_response("get.treasure.info", {
        "success": True,
        "treasure_id": 999
    })
    
    # Should still get response if available
    response = mock.get_response("get.treasure.info")
    assert response is not None
    
    # But new requests should fail or return cached
    response2 = mock.get_response("unknown.endpoint")
    assert response2.success is False
    
    # Go back online
    mock.set_offline(False)
    response3 = mock.get_response("unknown.endpoint")
    # Should try to connect (but fail with 404)
    assert response3 is not None
