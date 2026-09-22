"""tests/test_dsml_fullwidth_pipes.py — regression tests for DSML tool blocks
using full-width pipe characters (U+FF5C).

DeepSeek Pro sometimes emits DSML tags with full-width pipes (��) instead of
ASCII pipes (|), e.g. <����DSML����_calls> instead of <|DSML|tool_calls>.
These must be normalized and captured as tool calls, not leaked as prose.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.core.stream_handler import StreamHandler
from server.parser.dsml_parser import _normalize_tag_delimiters
from server.parser.dsml_sieve import StreamSieve, SieveEvent

TOOL_NAMES = ["bash", "edit", "Read", "Write", "grep"]

# Full-width pipe test blocks
FULLWIDTH_WITH_WRAPPER = (
    "<\uff5c\uff5cDSML\uff5c\uff5c_calls>"
    '<\uff5c\uff5cDSML\uff5c\uff5cinvoke name="bash">'
    '<\uff5c\uff5cDSML\uff5c\uff5cparameter name="command">cd test</\uff5c\uff5cDSML\uff5c\uff5cparameter>'
    "</\uff5c\uff5cDSML\uff5c\uff5cinvoke>"
    "</\uff5c\uff5cDSML\uff5c\uff5c_calls>"
)

FULLWIDTH_INVOKE_ONLY = (
    '<\uff5c\uff5cDSML\uff5c\uff5cinvoke name="bash">'
    '<\uff5c\uff5cDSML\uff5c\uff5cparameter name="command">cd test</\uff5c\uff5cDSML\uff5c\uff5cparameter>'
    "</\uff5c\uff5cDSML\uff5c\uff5cinvoke>"
)

FULLWIDTH_DISPATCH = (
    "<\uff5c\uff5cDSML\uff5c\uff5c_dispatch>"
    '<\uff5c\uff5cDSML\uff5c\uff5cinvoke name="bash">'
    '<\uff5c\uff5cDSML\uff5c\uff5cparameter name="command">cd test</\uff5c\uff5cDSML\uff5c\uff5cparameter>'
    "</\uff5c\uff5cDSML\uff5c\uff5cinvoke>"
    "</\uff5c\uff5cDSML\uff5c\uff5c_dispatch>"
)

NORMALIZED_WITH_WRAPPER = (
    "<|DSML|tool_calls>"
    '<|DSML|invoke name="bash">'
    '<|DSML|parameter name="command">cd test</|DSML|parameter>'
    "</|DSML|invoke>"
    "</|DSML|tool_calls>"
)

NORMALIZED_INVOKE_ONLY = (
    '<|DSML|invoke name="bash">'
    '<|DSML|parameter name="command">cd test</|DSML|parameter>'
    "</|DSML|invoke>"
)

NORMALIZED_DISPATCH = (
    "<|DSML|tool_dispatch>"
    '<|DSML|invoke name="bash">'
    '<|DSML|parameter name="command">cd test</|DSML|parameter>'
    "</|DSML|invoke>"
    "</|DSML|tool_dispatch>"
)

# Bare dispatch (without underscore prefix)
FULLWIDTH_BARE_DISPATCH = (
    "<\uff5c\uff5cDSML\uff5c\uff5cdispatch>"
    '<\uff5c\uff5cDSML\uff5c\uff5cinvoke name="bash">'
    '<\uff5c\uff5cDSML\uff5c\uff5cparameter name="command">cd test</\uff5c\uff5cDSML\uff5c\uff5cparameter>'
    "</\uff5c\uff5cDSML\uff5c\uff5cinvoke>"
    "</\uff5c\uff5cDSML\uff5c\uff5cdispatch>"
)

NORMALIZED_BARE_DISPATCH = (
    "<|DSML|tool_dispatch>"
    '<|DSML|invoke name="bash">'
    '<|DSML|parameter name="command">cd test</|DSML|parameter>'
    "</|DSML|invoke>"
    "</|DSML|tool_dispatch>"
)


def test_normalize_fullwidth_pipes():
    """Full-width pipes are normalized to ASCII."""
    assert _normalize_tag_delimiters(FULLWIDTH_WITH_WRAPPER) == NORMALIZED_WITH_WRAPPER
    assert _normalize_tag_delimiters(FULLWIDTH_INVOKE_ONLY) == NORMALIZED_INVOKE_ONLY
    assert _normalize_tag_delimiters(FULLWIDTH_DISPATCH) == NORMALIZED_DISPATCH
    assert (
        _normalize_tag_delimiters(FULLWIDTH_BARE_DISPATCH) == NORMALIZED_BARE_DISPATCH
    )


def test_sieve_captures_fullwidth_with_wrapper_single_chunk():
    """Sieve captures full-width _calls wrapper format in single chunk."""
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    events = sieve.feed(FULLWIDTH_WITH_WRAPPER)
    tc = [e for e in events if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"
    assert "command" in tc[0].data[0]["arguments"]


def test_sieve_captures_fullwidth_invoke_only_single_chunk():
    """Sieve captures full-width invoke-only format in single chunk."""
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    events = sieve.feed(FULLWIDTH_INVOKE_ONLY)
    tc = [e for e in events if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"


def test_sieve_captures_fullwidth_dispatch_single_chunk():
    """Sieve captures full-width _dispatch wrapper format in single chunk."""
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    events = sieve.feed(FULLWIDTH_DISPATCH)
    tc = [e for e in events if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"


def test_sieve_captures_fullwidth_bare_dispatch_single_chunk():
    """Sieve captures full-width bare dispatch (no underscore) in single chunk."""
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    events = sieve.feed(FULLWIDTH_BARE_DISPATCH)
    tc = [e for e in events if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"


def test_sieve_captures_fullwidth_incremental():
    """Sieve captures full-width format when fed incrementally."""
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    events = sieve.feed("<\uff5c\uff5cDSML\uff5c\uff5c_calls>")
    assert events == []
    events = sieve.feed('<\uff5c\uff5cDSML\uff5c\uff5cinvoke name="bash">')
    assert events == []
    events = sieve.feed(
        '<\uff5c\uff5cDSML\uff5c\uff5cparameter name="command">cd test</\uff5c\uff5cDSML\uff5c\uff5cparameter>'
    )
    assert events == []
    events = sieve.feed("</\uff5c\uff5cDSML\uff5c\uff5cinvoke>")
    assert events == []
    events = sieve.feed("</\uff5c\uff5cDSML\uff5c\uff5c_calls>")
    tc = [e for e in events if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"


def test_handler_captures_fullwidth_with_wrapper():
    """StreamHandler captures full-width _calls wrapper format."""
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed(FULLWIDTH_WITH_WRAPPER)
    tc = [e for e in events if e["type"] == "tool_calls"]
    text = [e for e in events if e["type"] == "text"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"
    assert not any("��" in e["data"] for e in text)


def test_handler_captures_fullwidth_invoke_only():
    """StreamHandler captures full-width invoke-only format without text leak."""
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed(FULLWIDTH_INVOKE_ONLY)
    tc = [e for e in events if e["type"] == "tool_calls"]
    text = [e for e in events if e["type"] == "text"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"
    # No DSML markup should leak to text
    assert not any("��" in e["data"] or "<|DSML|" in e["data"] for e in text)


def test_handler_captures_fullwidth_dispatch():
    """StreamHandler captures full-width _dispatch wrapper format without text leak."""
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed(FULLWIDTH_DISPATCH)
    tc = [e for e in events if e["type"] == "tool_calls"]
    text = [e for e in events if e["type"] == "text"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"
    # No DSML markup should leak to text
    assert not any("��" in e["data"] or "<|DSML|" in e["data"] for e in text)


def test_handler_captures_fullwidth_bare_dispatch():
    """StreamHandler captures full-width bare dispatch (no underscore) without text leak."""
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed(FULLWIDTH_BARE_DISPATCH)
    tc = [e for e in events if e["type"] == "tool_calls"]
    text = [e for e in events if e["type"] == "text"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"
    # No DSML markup should leak to text
    assert not any("��" in e["data"] or "<|DSML|" in e["data"] for e in text)


def test_handler_flush_fullwidth_invoke_only():
    """Flush also captures full-width invoke-only format."""
    handler = StreamHandler(tool_names=TOOL_NAMES)
    # Feed partial then flush (with closing tag)
    all_events = []
    all_events.extend(handler.feed('<\uff5c\uff5cDSML\uff5c\uff5cinvoke name="bash">'))
    all_events.extend(
        handler.feed(
            '<\uff5c\uff5cDSML\uff5c\uff5cparameter name="command">cd test</\uff5c\uff5cDSML\uff5c\uff5cparameter>'
        )
    )
    all_events.extend(handler.feed("</\uff5c\uff5cDSML\uff5c\uff5cinvoke>"))
    all_events.extend(handler.flush())
    tc = [e for e in all_events if e["type"] == "tool_calls"]
    text = [e for e in all_events if e["type"] == "text"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"
    # No DSML markup should leak to text
    assert not any("��" in e["data"] or "<|DSML|" in e["data"] for e in text)


def test_handler_mixed_fullwidth_and_ascii():
    """Handler handles mixed full-width and ASCII pipes."""
    handler = StreamHandler(tool_names=TOOL_NAMES)
    mixed = (
        '<\uff5c\uff5cDSML\uff5c\uff5cinvoke name="bash">'
        '<|DSML|parameter name="command">cd test</|DSML|parameter>'
        "</\uff5c\uff5cDSML\uff5c\uff5cinvoke>"
    )
    events = handler.feed(mixed)
    tc = [e for e in events if e["type"] == "tool_calls"]
    text = [e for e in events if e["type"] == "text"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"
    assert not any("��" in e["data"] or "<|DSML|" in e["data"] for e in text)


def test_handler_prose_with_fullwidth_tool_block():
    """Prose before/after full-width tool block is handled correctly."""
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed("Let me run: ")
    text = [e for e in events if e["type"] == "text"]
    assert text and "Let me run:" in text[0]["data"]

    events = handler.feed(FULLWIDTH_WITH_WRAPPER)
    tc = [e for e in events if e["type"] == "tool_calls"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"

    events = handler.feed(" Done.")
    text = [e for e in events if e["type"] == "text"]
    assert text and "Done." in text[0]["data"]


def test_sieve_fullwidth_no_marker_boundary_splits():
    """Splitting the bare double-full-width-pipe format (<｜｜tool_calls>)
    at every kind of boundary must capture, not leak.

    Regression: chunks split mid-tag (``</｜｜tool_calls`` + ``>``, or
    ``<｜｜`` + ``tool_calls>``) used to leak the whole block as prose
    because the split regions were never normalized.
    """
    fw = "\uff5c"
    block = (
        f"<{fw}{fw}tool_calls>"
        f'<{fw}{fw}invoke name="Read">'
        f'<{fw}{fw}parameter name="file_path" string="true">f:\\\\PROJEKTY\\\\joaxx\\\\mvp\\\\gui\\\\main_window.py</{fw}{fw}parameter>'
        f'<{fw}{fw}parameter name="offset" string="true">420</{fw}{fw}parameter>'
        f'<{fw}{fw}parameter name="limit" string="true">380</{fw}{fw}parameter>'
        f"</{fw}{fw}invoke>"
        f"</{fw}{fw}tool_calls>"
    )

    def feed_all(parts):
        sieve = StreamSieve(tool_names=["Read"])
        events = []
        for p in parts:
            events.extend(sieve.feed(p))
        events.extend(sieve.flush())
        return events

    split_points = [2, 3, 4, len(block) - 20, len(block) - 19, len(block) - 17]
    close_pos = block.rfind(f"</{fw}{fw}tool_calls>")
    split_points += [close_pos, close_pos + 1, close_pos + 2, close_pos + 4]
    inv_close = block.rfind(f"</{fw}{fw}invoke>")
    split_points += [inv_close]

    cases = []
    for sp in split_points:
        cases.append([block[:sp], block[sp:]])
    # char-by-char is the extreme case
    cases.append([c for c in block])
    # random-ish multi-splits
    import random

    random.seed(42)
    for num in (10, 30, 50, 100):
        remaining = block
        parts = []
        for _ in range(num - 1):
            if len(remaining) <= 1:
                break
            sp = random.randint(1, len(remaining) - 1)
            parts.append(remaining[:sp])
            remaining = remaining[sp:]
        if remaining:
            parts.append(remaining)
        cases.append(parts)

    for parts in cases:
        events = feed_all(parts)
        tc = [e for e in events if e.type == "tool_calls"]
        text = [e for e in events if e.type == "text"]
        assert tc, (
            f"expected tool_calls for {len(parts)} chunks, got text: {text[:1]!r}"
        )
        assert not text, f"leaked {len(text)} text events for {len(parts)} chunks"
        assert tc[0].data[0]["name"] == "Read"
        args = json.loads(tc[0].data[0]["arguments"])
        assert args["file_path"].endswith("main_window.py")
        assert str(args["offset"]) == "420"
        assert str(args["limit"]) == "380"


def test_sieve_all_formats_boundary_splits():
    """Every DSML tag format must survive arbitrary chunk splits (incl.
    char-by-char) without leaking the block as prose."""
    fw = "\uff5c"
    formats = {
        "bare_double_fw": (
            f"<{fw}{fw}tool_calls>"
            f'<{fw}{fw}invoke name="bash">'
            f'<{fw}{fw}parameter name="command">cd test</{fw}{fw}parameter>'
            f"</{fw}{fw}invoke>"
            f"</{fw}{fw}tool_calls>"
        ),
        "marker_double_fw": (
            f"<{fw}{fw}DSML{fw}{fw}_calls>"
            f'<{fw}{fw}DSML{fw}{fw}invoke name="bash">'
            f'<{fw}{fw}DSML{fw}{fw}parameter name="command">cd test</{fw}{fw}DSML{fw}{fw}parameter>'
            f"</{fw}{fw}DSML{fw}{fw}invoke>"
            f"</{fw}{fw}DSML{fw}{fw}_calls>"
        ),
        "single_fw": (
            f"<{fw}tool_calls>"
            f'<{fw}invoke name="bash">'
            f'<{fw}parameter name="command">cd test</{fw}parameter>'
            f"</{fw}invoke>"
            f"</{fw}tool_calls>"
        ),
        "ascii_double": (
            "<||tool_calls>"
            '<||invoke name="bash">'
            '<||parameter name="command">cd test</||parameter>'
            "</||invoke>"
            "</||tool_calls>"
        ),
        "ascii_single_marker": (
            "<|DSML|tool_calls>"
            '<|DSML|invoke name="bash">'
            '<|DSML|parameter name="command">cd test</|DSML|parameter>'
            "</|DSML|invoke>"
            "</|DSML|tool_calls>"
        ),
        "invoke_only": (
            f'<{fw}{fw}invoke name="bash">'
            f'<{fw}{fw}parameter name="command">cd test</{fw}{fw}parameter>'
            f"</{fw}{fw}invoke>"
        ),
        "dispatch": (
            f"<{fw}{fw}tool_dispatch>"
            f'<{fw}{fw}invoke name="bash">'
            f'<{fw}{fw}parameter name="command">cd test</{fw}{fw}parameter>'
            f"</{fw}{fw}invoke>"
            f"</{fw}{fw}tool_dispatch>"
        ),
    }

    def feed_all(parts):
        sieve = StreamSieve(tool_names=["bash"])
        events = []
        for p in parts:
            events.extend(sieve.feed(p))
        events.extend(sieve.flush())
        return events

    for name, block in formats.items():
        cases = [[c for c in block]]
        close_pos = block.rfind(">")
        cases.append([block[: close_pos - 2], block[close_pos - 2 :]])
        cases.append([block[: close_pos + 1], block[close_pos + 1 :]])
        import random

        random.seed(7)
        for num in (6, 11):
            remaining = block
            parts = []
            for _ in range(num - 1):
                if len(remaining) <= 1:
                    break
                sp = random.randint(1, len(remaining) - 1)
                parts.append(remaining[:sp])
                remaining = remaining[sp:]
            if remaining:
                parts.append(remaining)
            cases.append(parts)
        for parts in cases:
            events = feed_all(parts)
            tc = [e for e in events if e.type == "tool_calls"]
            text = [e for e in events if e.type == "text"]
            assert tc, (
                f"{name}: expected tool_calls for {len(parts)} chunks, "
                f"got text: {text[:1]!r}"
            )
            assert not text, (
                f"{name}: leaked {len(text)} text events for {len(parts)} chunks"
            )
            assert tc[0].data[0]["name"] == "bash"
            args = json.loads(tc[0].data[0]["arguments"])
            assert args["command"] == "cd test"


if __name__ == "__main__":
    # Run tests manually
    test_normalize_fullwidth_pipes()
    print("test_normalize_fullwidth_pipes: PASSED")

    test_sieve_captures_fullwidth_with_wrapper_single_chunk()
    print("test_sieve_captures_fullwidth_with_wrapper_single_chunk: PASSED")

    test_sieve_captures_fullwidth_invoke_only_single_chunk()
    print("test_sieve_captures_fullwidth_invoke_only_single_chunk: PASSED")

    test_sieve_captures_fullwidth_dispatch_single_chunk()
    print("test_sieve_captures_fullwidth_dispatch_single_chunk: PASSED")

    test_sieve_captures_fullwidth_incremental()
    print("test_sieve_captures_fullwidth_incremental: PASSED")

    test_handler_captures_fullwidth_with_wrapper()
    print("test_handler_captures_fullwidth_with_wrapper: PASSED")

    test_handler_captures_fullwidth_invoke_only()
    print("test_handler_captures_fullwidth_invoke_only: PASSED")

    test_handler_captures_fullwidth_dispatch()
    print("test_handler_captures_fullwidth_dispatch: PASSED")

    test_handler_flush_fullwidth_invoke_only()
    print("test_handler_flush_fullwidth_invoke_only: PASSED")

    test_handler_mixed_fullwidth_and_ascii()
    print("test_handler_mixed_fullwidth_and_ascii: PASSED")

    test_handler_prose_with_fullwidth_tool_block()
    print("test_handler_prose_with_fullwidth_tool_block: PASSED")

    test_sieve_fullwidth_no_marker_boundary_splits()
    print("test_sieve_fullwidth_no_marker_boundary_splits: PASSED")

    test_sieve_all_formats_boundary_splits()
    print("test_sieve_all_formats_boundary_splits: PASSED")

    print("\nAll tests passed!")
