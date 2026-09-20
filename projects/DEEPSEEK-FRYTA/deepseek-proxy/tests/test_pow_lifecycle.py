"""Unit tests for DeepSeek PoW token single-use lifecycle and caching behavior."""

import time
from unittest.mock import MagicMock, patch
import pytest

from server.core.deepseek_client import (
    DeepSeek,
    _pow_cache,
    _pow_expires,
    _pow_lock,
)


@pytest.fixture(autouse=True)
def clean_pow_cache():
    """Ensure PoW cache is empty before and after each test."""
    with _pow_lock:
        _pow_cache.clear()
        _pow_expires.clear()
    yield
    with _pow_lock:
        _pow_cache.clear()
        _pow_expires.clear()


class TestPoWLifecycle:
    """Test suite verifying that PoW tokens are treated as single-use nonces."""

    def test_cached_pow_is_consumed_on_get(self):
        """A cached PoW token must be popped/consumed so it cannot be re-used."""
        client = DeepSeek(pool=MagicMock())
        slot = 0
        target_path = "/api/v0/chat/completion"
        key = (slot, target_path)

        # Populate cache with a valid token
        with _pow_lock:
            _pow_cache[key] = "token_abc_123"
            _pow_expires[key] = time.time() + 100

        with patch.object(client, "_prefetch_pow") as mock_prefetch:
            token = client._get_pow(slot, target_path=target_path)
            assert token == "token_abc_123"

            # Cache must now be EMPTY for this key (single-use pop)
            with _pow_lock:
                assert key not in _pow_cache

            # Prefetch must be triggered to replenish for the next request
            mock_prefetch.assert_called_once_with(slot)

    def test_cache_miss_solves_challenge_and_triggers_prefetch(self):
        """When cache is empty, solve challenge synchronously without leaving consumed token in cache."""
        client = DeepSeek(pool=MagicMock())
        slot = 0
        target_path = "/api/v0/chat/completion"
        key = (slot, target_path)

        fake_challenge = {"algorithm": "sha256", "expire_at": (time.time() + 100) * 1000}
        client._get_challenge = MagicMock(return_value=fake_challenge)
        client.pow.solve_challenge = MagicMock(return_value="solved_token_xyz")

        with patch.object(client, "_prefetch_pow") as mock_prefetch:
            token = client._get_pow(slot, target_path=target_path)
            assert token == "solved_token_xyz"

            # The synchronously solved token is consumed immediately by the caller,
            # so it should NOT remain in cache as an available reusable token!
            with _pow_lock:
                assert _pow_cache.get(key) != "solved_token_xyz"

            # Prefetch is started to prepare the NEXT token
            mock_prefetch.assert_called_once_with(slot)

    def test_expired_cached_token_is_discarded(self):
        """If a cached token is expired, it must be discarded and a fresh challenge solved."""
        client = DeepSeek(pool=MagicMock())
        slot = 0
        target_path = "/api/v0/chat/completion"
        key = (slot, target_path)

        # Cache expired token
        with _pow_lock:
            _pow_cache[key] = "expired_token"
            _pow_expires[key] = time.time() - 10

        fake_challenge = {"algorithm": "sha256", "expire_at": (time.time() + 100) * 1000}
        client._get_challenge = MagicMock(return_value=fake_challenge)
        client.pow.solve_challenge = MagicMock(return_value="fresh_token_123")

        with patch.object(client, "_prefetch_pow"):
            token = client._get_pow(slot, target_path=target_path)
            assert token == "fresh_token_123"

    def test_consecutive_requests_never_share_same_pow(self):
        """Two consecutive requests must never receive the exact same PoW response."""
        client = DeepSeek(pool=MagicMock())
        slot = 0
        target_path = "/api/v0/chat/completion"

        tokens = ["token_1", "token_2", "token_3"]
        client._get_challenge = MagicMock(return_value={"expire_at": (time.time() + 100) * 1000})
        client.pow.solve_challenge = MagicMock(side_effect=tokens)

        with patch.object(client, "_prefetch_pow"):
            t1 = client._get_pow(slot, target_path=target_path)
            t2 = client._get_pow(slot, target_path=target_path)
            assert t1 != t2
            assert t1 == "token_1"
            assert t2 == "token_2"
