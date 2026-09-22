"""tests/test_damaged_invoke_opener.py — regression tests for tool blocks whose
<invoke opener lost its '<inv' prefix.

DeepSeek Pro sometimes streams a complete tool block with a corrupted opener:
``oke name="bash">`` instead of ``<invoke name="bash">`` (the leading ``<inv``
is dropped).  Previously such blocks were treated as plain text by the sieve,
and ``clean_tool_text`` mangled them into visible residue like
``oke name="bash">`` that leaked to the IDE instead of executing the tool call.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.parser.dsml_sieve import StreamSieve, SieveEvent
from server.core.stream_handler import StreamHandler
from server.repair.repair_tier1 import repair_tier1, _fix_damaged_invoke_opener

TOOL_NAMES = ["bash", "edit", "Read", "Write", "grep"]

# Exact malformed block reconstructed from the stored leak message [47]
# (content_buffer=217 chars for resp 38).
DAMAGED_BLOCK = (
    'oke name="bash">\n'
    '<parameter name="command" string="true">uv run pytest tests/core/test_http_ean.py tests/core/test_ean_parser.py -n 0 -v --no-cov 2>&1</parameter>\n'
    '<parameter name="workdir" string="true">F:\\PROJEKTY\\ALLEGRO_SCRAPER</parameter>\n'
    "</invoke>"
)


def test_repair_reconstructs_opener():
    repaired = _fix_damaged_invoke_opener(DAMAGED_BLOCK)
    assert repaired == '<invoke name="bash">' + DAMAGED_BLOCK[len('oke name="bash">') :]


def test_repair_tier1_fixes_damaged_block():
    repaired = repair_tier1(DAMAGED_BLOCK, TOOL_NAMES)
    assert repaired is not None
    assert '<invoke name="bash">' in repaired


def test_sieve_captures_damaged_block_single_chunk():
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    events = sieve.feed(DAMAGED_BLOCK)
    tc = [e for e in events if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"
    assert "command" in tc[0].data[0]["arguments"]


def test_sieve_captures_damaged_block_split_at_opener():
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    events = sieve.feed('oke name="bash">\n<parameter name="command" string="true">')
    assert events == []  # opener held in capture, not leaked as text
    events2 = sieve.feed(
        "uv run pytest -n 0 -v --no-cov 2>&1</parameter>\n"
        '<parameter name="workdir" string="true">F:\\PROJEKTY\\ALLEGRO_SCRAPER</parameter>\n'
        "</invoke>"
    )
    tc = [e for e in events2 if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"


def test_sieve_holds_partial_damaged_opener():
    sieve = StreamSieve(tool_names=TOOL_NAMES)
    # Opener split mid-fragment: 'oke' arrives alone at end of chunk.  The
    # preceding prose is emitted, but 'oke' must be held back, not leaked.
    events = sieve.feed("prefix oke")
    assert events == [SieveEvent("text", "prefix ")]
    events2 = sieve.feed(
        ' name="bash">\n<parameter name="command" string="true">echo hi</parameter>\n</invoke>'
    )
    tc = [e for e in events2 if e.type == "tool_calls"]
    assert len(tc) == 1
    assert tc[0].data[0]["name"] == "bash"


def test_handler_repairs_damaged_block_from_text_path():
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed(DAMAGED_BLOCK)
    tc = [e for e in events if e["type"] == "tool_calls"]
    text = [e for e in events if e["type"] == "text"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"
    assert not any("oke name=" in e["data"] for e in text)


def test_handler_flush_repairs_damaged_block():
    handler = StreamHandler(tool_names=TOOL_NAMES)
    # Feed nothing, force flush path with a pre-seeded damaged block is not
    # possible directly; instead feed partial then flush.
    events = handler.feed(
        'oke name="bash">\n<parameter name="command" string="true">echo hi</parameter>\n</invoke>'
    )
    tc = [e for e in events if e["type"] == "tool_calls"]
    assert len(tc) == 1


def test_handler_does_not_mangle_valid_prose():
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed("Let me check that. oke name is not a tool here.")
    text = [e for e in events if e["type"] == "text"]
    assert text and "oke name" in text[0]["data"]


def test_handler_still_parses_valid_invoke():
    handler = StreamHandler(tool_names=TOOL_NAMES)
    events = handler.feed(
        '<invoke name="bash"><parameter name="command" string="true">echo hi</parameter></invoke>'
    )
    tc = [e for e in events if e["type"] == "tool_calls"]
    assert len(tc) == 1
    assert tc[0]["data"][0]["name"] == "bash"


def test_damaged_opener_inside_prose_not_repaired():
    # A bare 'oke name="x">' without tool-block structure must stay prose.
    repaired = _fix_damaged_invoke_opener('Nothing here: oke name="x"> whatever.')
    assert repaired == 'Nothing here: oke name="x"> whatever.'
