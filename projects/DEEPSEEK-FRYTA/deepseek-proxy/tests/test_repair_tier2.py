"""Tests for tier 2 — JSON argument repair."""

from __future__ import annotations

from server.repair.repair_tier2 import repair_tier2


def test_fix_trailing_comma():
    """Remove trailing commas in JSON objects."""
    fixed = repair_tier2('Bash', '{"command": "ls",}')
    assert fixed is not None
    assert '"ls"' in fixed
    assert ',}' not in fixed


def test_fix_single_quotes():
    """Replace single quotes with double quotes in JSON."""
    fixed = repair_tier2('Bash', "{'command': 'ls -la'}")
    assert fixed is not None
    assert '"command"' in fixed
    assert '"ls -la"' in fixed


def test_fix_unescaped_backslashes():
    """Fix unescaped backslashes in JSON strings."""
    fixed = repair_tier2('Read', '{"file_path": "C:\\Users\\test\\file.txt"}')
    assert fixed is not None
    assert "\\\\" in fixed  # properly escaped


def test_fix_bare_string_to_json():
    """Wrap bare string value into expected JSON schema."""
    fixed = repair_tier2('Bash', 'ls -la')
    assert fixed is not None
    assert '"command"' in fixed
    assert 'ls -la' in fixed


def test_fix_bare_string_read():
    """Wrap bare file path into Read tool schema."""
    fixed = repair_tier2('Read', '/tmp/file.txt')
    assert fixed is not None
    assert '"file_path"' in fixed


def test_valid_json_unchanged():
    """Valid JSON passes through unchanged."""
    fixed = repair_tier2('Bash', '{"command": "echo hello"}')
    assert fixed is not None
    assert '"command"' in fixed
    assert 'echo hello' in fixed


def test_empty_returns_none():
    """Return None for empty input."""
    assert repair_tier2('Bash', '') is None
    assert repair_tier2('Read', '{}') is not None  # valid empty object


def test_xml_double_encoded():
    """Fix XML-encoded JSON: {""key"": ""val""} → {"key": "val"}."""
    fixed = repair_tier2('Bash', '{"command": "echo ""hello world"""}')
    assert fixed is not None
    assert 'hello world' in fixed
