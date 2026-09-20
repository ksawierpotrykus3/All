"""pytest configuration and fixtures for deepseek-proxy tests."""
import pytest
from pathlib import Path
import server.services.state_service as ss


@pytest.fixture(autouse=True)
def isolate_conv_state(tmp_path, monkeypatch):
    """Ensure tests never read or overwrite the production conv_state.json."""
    test_file = tmp_path / "test_conv_state.json"
    monkeypatch.setattr(ss, "CONV_STATE_FILE", test_file)
    # Start each test with an empty state dictionary isolated from production
    monkeypatch.setattr(ss, "conv_state", {})
    monkeypatch.setattr(ss, "chat_state", {})
