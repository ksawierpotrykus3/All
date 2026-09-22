"""Test that _SYS_TAG_START_RE correctly distinguishes
Trae preamble text from actual <system-reminder> tags."""

from server.core.input_parser import InputParser, _SYS_TAG_START_RE

TRAE_PREAMBLE = (
    "You are an interactive agent in the Trae IDE that helps "
    "the USER with software engineering tasks.\n\n"
    "  - Each time the USER sends a message, we may automatically "
    "attach contextual information about their current state "
    "in <system-reminder> or other tags, such "
    "as what files they have open, recent edit history, "
    "terminal status, linter errors, and current mode."
)


def test_regex_does_not_match_preamble():
    """The preamble contains literal '<system-reminder>' as a word,
    not as an actual XML tag. The regex should NOT match."""
    result = bool(_SYS_TAG_START_RE.search(TRAE_PREAMBLE))
    assert not result, (
        f"Regex should NOT match preamble text, but it did. "
        f"Matched: {_SYS_TAG_START_RE.search(TRAE_PREAMBLE).group()!r}"
    )


def test_regex_matches_actual_tag():
    """An actual <system-reminder> tag at the start should match."""
    true_reminder = "<system-reminder>\nSomething went wrong\n</system-reminder>"
    assert _SYS_TAG_START_RE.search(true_reminder), (
        "Regex should match actual <system-reminder> tag"
    )


def test_regex_matches_indented_tag():
    """An actual <system-reminder> tag after newline should match."""
    reminder = "blah\n<system-reminder>\ncontent\n</system-reminder>"
    assert _SYS_TAG_START_RE.search(reminder), (
        "Regex should match <system-reminder> after newline"
    )


def test_input_parser_preserves_preamble():
    """InputParser.parse() should keep the Trae preamble as a system message."""
    raw = {
        "messages": [
            {"role": "system", "content": TRAE_PREAMBLE},
            {"role": "user", "content": "Hello"},
        ],
        "model": "deepseek-v4-pro",
    }
    parsed = InputParser.parse(raw)
    has_preamble = any(
        "You are an interactive agent" in m.get("content", "")
        for m in parsed.messages
    )
    assert has_preamble, "Preamble system message was lost by InputParser"


def test_input_parser_filters_old_reminders_keeps_preamble():
    """When there are both preamble and real <system-reminder> tags,
    the preamble should survive and only the last reminder should remain."""
    raw = {
        "messages": [
            {"role": "system", "content": TRAE_PREAMBLE},
            {"role": "system", "content": "<system-reminder>\nOld\n</system-reminder>"},
            {"role": "system", "content": "<system-reminder>\nNew\n</system-reminder>"},
            {"role": "user", "content": "Hello"},
        ],
        "model": "deepseek-v4-pro",
    }
    parsed = InputParser.parse(raw)
    sys_msgs = [m for m in parsed.messages if m.get("role") == "system"]
    preamble_ok = any(
        "You are an interactive agent" in m.get("content", "")
        for m in parsed.messages
    )
    last_reminder_ok = any(
        "New" in m.get("content", "") for m in parsed.messages
    )
    old_reminder_gone = not any(
        "Old" in m.get("content", "") for m in parsed.messages
    )
    assert preamble_ok, "Preamble was lost alongside reminders"
    assert last_reminder_ok, "Last reminder should be kept"
    assert old_reminder_gone, "Old reminders should be removed"
