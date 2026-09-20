"""tests/test_prompt_chunker.py — Tests for multi-part prompt chunking."""

import pytest
from server.services.prompt_chunker import split_prompt_payload, PROMPT_CHUNK_THRESHOLD


def test_split_prompt_payload_no_split_under_threshold():
    """Prompt below threshold should be returned as a single item."""
    short_prompt = "Short prompt content that does not exceed threshold."
    chunks = split_prompt_payload(short_prompt, max_chunk_size=1000)
    assert len(chunks) == 1
    assert chunks[0] == short_prompt


def test_split_prompt_payload_multiple_tool_results():
    """Multiple <tool_result> blocks should split cleanly along block boundaries."""
    block1 = (
        "<tool_result>\n<t>read_file</t>\n<id>call_1</id>\n<content>\n"
        + ("A" * 600)
        + "\n</content>\n</tool_result>"
    )
    block2 = (
        "<tool_result>\n<t>read_file</t>\n<id>call_2</id>\n<content>\n"
        + ("B" * 600)
        + "\n</content>\n</tool_result>"
    )
    full_prompt = f"[User]:\n{block1}\n\n{block2}"

    # Threshold set to 800 — each block is ~680 chars, together ~1400 chars.
    chunks = split_prompt_payload(full_prompt, max_chunk_size=800)
    assert len(chunks) == 2

    # First chunk contains block 1 and system continuation notice
    assert "call_1" in chunks[0]
    assert "call_2" not in chunks[0]
    assert "[SYSTEM NOTE: Part 1 of 2" in chunks[0]

    # Second chunk contains block 2 and completion notice
    assert "call_2" in chunks[1]
    assert "call_1" not in chunks[1]
    assert "[SYSTEM NOTE: Part 2 of 2" in chunks[1]


def test_split_prompt_payload_single_oversized_block():
    """A single oversized <tool_result> block should split inside <content> without breaking XML."""
    huge_content = "X" * 2500
    huge_block = (
        "<tool_result>\n<t>read_file</t>\n<id>call_huge</id>\n<content>\n"
        + huge_content
        + "\n</content>\n</tool_result>"
    )
    full_prompt = f"[User]:\n{huge_block}"

    chunks = split_prompt_payload(full_prompt, max_chunk_size=1000)
    assert len(chunks) >= 3

    # Every chunk must be within reasonable bounds
    for i, ch in enumerate(chunks):
        assert len(ch) <= 1500  # Including headers/tags
        assert f"Part {i + 1} of {len(chunks)}" in ch
        # XML tags should be validly wrapped in each part
        assert "<tool_result>" in ch
        assert "</tool_result>" in ch


def test_split_prompt_payload_preserves_agentic_forcing_block_on_last_chunk():
    """Agentic forcing block must ONLY be present on the final chunk."""
    block1 = "<tool_result>\n<t>t1</t>\n<id>c1</id>\n<content>\n" + ("1" * 800) + "\n</content>\n</tool_result>"
    block2 = "<tool_result>\n<t>t2</t>\n<id>c2</id>\n<content>\n" + ("2" * 800) + "\n</content>\n</tool_result>"
    forcing = "CRITICAL: You are an AGENT with tools. When you need to perform any action"
    full_prompt = f"[User]:\n{block1}\n\n{block2}\n\n{forcing}\n\n[Assistant]:\n"

    chunks = split_prompt_payload(full_prompt, max_chunk_size=1000)
    assert len(chunks) == 2

    # First chunk: NO full forcing block, deterministic ACK directive & tail
    assert forcing not in chunks[0]
    assert "[Assistant]:\nACK" in chunks[0]
    assert "[SYSTEM DIRECTIVE: Interim buffer chunk" in chunks[0]

    # Last chunk: MUST have forcing block and assistant prompt, NO ACK directive
    assert forcing in chunks[1]
    assert "[Assistant]:" in chunks[1]
    assert "Reply ONLY with: ACK" not in chunks[1]
