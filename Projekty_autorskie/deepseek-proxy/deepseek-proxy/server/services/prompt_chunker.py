"""server/services/prompt_chunker.py — Multi-part prompt chunker.

Splits oversized prompts (e.g. huge tool results exceeding DeepSeek Web Chat
per-request limits) into smaller sequential chunks that can be injected
into the cloud session without exceeding payload limits.
"""

from __future__ import annotations

import re



# Cloud Web Chat rejects prompts > ~35k-40k chars with "Server is temporarily unavailable" / 503.
# Safe chunk threshold is 35,000 chars.
PROMPT_CHUNK_THRESHOLD = 35_000

_TOOL_RESULT_BLOCK_RE = re.compile(
    r"<tool_result\b[^>]*>.*?</tool_result\s*>",
    re.DOTALL | re.IGNORECASE,
)

_AGENTIC_FORCING_PREFIX = "CRITICAL: You are an AGENT with tools."


def _split_oversized_tool_result(
    block: str,
    max_chunk_size: int,
) -> list[str]:
    """Split a single oversized <tool_result> block inside its <content> tag."""
    content_match = re.search(
        r"(<tool_result\b[^>]*>.*?(?:<content>))(.*?)(</content>\s*</tool_result\s*>)",
        block,
        re.DOTALL | re.IGNORECASE,
    )
    if not content_match:
        # Fallback: slice block directly
        return [
            block[i : i + max_chunk_size]
            for i in range(0, len(block), max_chunk_size)
        ]

    header = content_match.group(1)
    body = content_match.group(2)
    footer = content_match.group(3)

    overhead = len(header) + len(footer) + 200
    effective_max = max(500, max_chunk_size - overhead)

    lines = body.splitlines(keepends=True)
    pieces: list[str] = []
    curr_lines: list[str] = []
    curr_len = 0

    for line in lines:
        if len(line) > effective_max:
            if curr_lines:
                pieces.append("".join(curr_lines))
                curr_lines = []
                curr_len = 0
            for j in range(0, len(line), effective_max):
                pieces.append(line[j : j + effective_max])
        elif curr_len + len(line) > effective_max and curr_lines:
            pieces.append("".join(curr_lines))
            curr_lines = [line]
            curr_len = len(line)
        else:
            curr_lines.append(line)
            curr_len += len(line)

    if curr_lines:
        pieces.append("".join(curr_lines))

    if not pieces:
        pieces = [body]

    total_pieces = len(pieces)
    result_blocks: list[str] = []
    for idx, piece in enumerate(pieces):
        part_tag = f"<!-- Part {idx + 1} of {total_pieces} -->\n"
        result_blocks.append(f"{header}\n{part_tag}{piece}\n{footer}")

    return result_blocks


def split_prompt_payload(
    prompt: str,
    max_chunk_size: int = PROMPT_CHUNK_THRESHOLD,
) -> list[str]:
    """Split an oversized prompt payload into safe sequential chunks.

    Returns a list of strings. If the prompt is <= max_chunk_size,
    returns [prompt] unchanged.
    """
    if not prompt or len(prompt) <= max_chunk_size:
        return [prompt]

    # Extract any trailing agentic forcing block and assistant prompt so they are
    # placed ONLY on the final chunk.
    forcing_tail = ""
    clean_prompt = prompt
    forcing_idx = clean_prompt.find("<system-reminder>")
    if forcing_idx == -1:
        forcing_idx = clean_prompt.find(_AGENTIC_FORCING_PREFIX)
    if forcing_idx != -1:
        forcing_tail = clean_prompt[forcing_idx:].strip()
        clean_prompt = clean_prompt[:forcing_idx].strip()
    elif "[Assistant]:" in clean_prompt:
        asst_idx = clean_prompt.rfind("[Assistant]:")
        forcing_tail = clean_prompt[asst_idx:].strip()
        clean_prompt = clean_prompt[:asst_idx].strip()

    # Find tool_result blocks
    blocks = []
    last_end = 0
    for m in _TOOL_RESULT_BLOCK_RE.finditer(clean_prompt):
        if m.start() > last_end:
            interim = clean_prompt[last_end : m.start()].strip()
            if interim:
                # Keep preamble / [User]: prefix attached to the first block
                if not blocks:
                    blocks.append(interim + "\n\n" + m.group(0))
                    last_end = m.end()
                    continue
        blocks.append(m.group(0))
        last_end = m.end()

    if last_end < len(clean_prompt):
        remainder = clean_prompt[last_end:].strip()
        if remainder:
            blocks.append(remainder)

    if not blocks:
        # No <tool_result> blocks — split raw text by lines
        lines = clean_prompt.splitlines(keepends=True)
        chunks_raw = []
        curr_lines = []
        curr_len = 0
        for line in lines:
            if curr_len + len(line) > max_chunk_size and curr_lines:
                chunks_raw.append("".join(curr_lines))
                curr_lines = [line]
                curr_len = len(line)
            else:
                curr_lines.append(line)
                curr_len += len(line)
        if curr_lines:
            chunks_raw.append("".join(curr_lines))
        blocks = chunks_raw

    # Now group blocks into chunks <= max_chunk_size
    chunks: list[str] = []
    current_chunk_blocks: list[str] = []
    current_chunk_len = 0

    for b in blocks:
        if len(b) > max_chunk_size:
            # If current chunk has content, flush it first
            if current_chunk_blocks:
                chunks.append("\n\n".join(current_chunk_blocks))
                current_chunk_blocks = []
                current_chunk_len = 0
            # Split this oversized block
            sub_blocks = _split_oversized_tool_result(b, max_chunk_size)
            for sb in sub_blocks:
                chunks.append(sb)
        elif current_chunk_len + len(b) > max_chunk_size and current_chunk_blocks:
            chunks.append("\n\n".join(current_chunk_blocks))
            current_chunk_blocks = [b]
            current_chunk_len = len(b)
        else:
            current_chunk_blocks.append(b)
            current_chunk_len += len(b)

    if current_chunk_blocks:
        chunks.append("\n\n".join(current_chunk_blocks))

    if len(chunks) <= 1:
        # Nothing split
        return [prompt]

    total_chunks = len(chunks)
    formatted_chunks: list[str] = []

    for i, ch in enumerate(chunks):
        part_num = i + 1
        is_last = (part_num == total_chunks)

        # Clean any leading [User]: from ch to avoid doubling
        ch_body = ch.strip()
        if ch_body.startswith("[User]:"):
            ch_body = ch_body[len("[User]:") :].strip()

        if not is_last:
            header = (
                f"[User]:\n"
                f"[SYSTEM NOTE: Part {part_num} of {total_chunks} of tool results. "
                f"Continuation follows immediately in the next message. "
                f"Do NOT execute any tools or analyze yet. Reply ONLY with: ACK]\n\n"
            )
            interim_tail = (
                f"\n\n[SYSTEM DIRECTIVE: Interim buffer chunk {part_num}/{total_chunks}. "
                f"Reply ONLY with the exact word 'ACK'.]\n\n[Assistant]:\nACK"
            )
            formatted_chunks.append(f"{header}{ch_body}{interim_tail}")
        else:
            header = (
                f"[User]:\n"
                f"[SYSTEM NOTE: Part {part_num} of {total_chunks} of tool results. "
                f"All context is now provided. Please analyze all parts and provide your response or tool calls.]\n\n"
            )
            tail = f"\n\n{forcing_tail}" if forcing_tail else "\n\n[Assistant]:\n"
            formatted_chunks.append(f"{header}{ch_body}{tail}")

    return formatted_chunks
