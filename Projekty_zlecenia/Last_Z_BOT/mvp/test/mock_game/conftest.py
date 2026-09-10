"""Pytest fixtures for mock game testing"""

import pytest
from mvp.test.mock_game.game_process import MockGameProcess
from mvp.test.mock_game.click_handler import ClickHandler


@pytest.fixture
def mock_game_process():
    """Provide a MockGameProcess instance for testing"""
    return MockGameProcess()


@pytest.fixture
def click_handler():
    """Provide a ClickHandler instance for testing"""
    return ClickHandler()
