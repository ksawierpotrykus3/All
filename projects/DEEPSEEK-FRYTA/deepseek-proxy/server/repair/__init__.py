"""server/repair/__init__.py — 3-tier tool call repair pipeline.

Repair pipeline for malformed DSML/XML tool calls from DeepSeek V4 Pro web chat.
Tier 1 fixes text-level XML errors; Tier 2 fixes JSON argument errors.
"""

from __future__ import annotations

from typing import Callable, Optional

from server.repair.repair_tier1 import repair_tier1
from server.repair.repair_tier2 import repair_tier2
from server.repair.repair_tier3 import repair_tier3


def repair_pipeline(
    capture_buf: str,
    tool_names: Optional[list[str]] = None,
    tier3_callback: Optional[Callable[[str], str]] = None,
) -> str | None:
    """Run tier1 -> tier2 repair sequentially.

    Args:
        capture_buf: Raw capture buffer containing an unparseable DSML block.
        tool_names: Known tool names for name resolution.
        tier3_callback: Optional callback for model self-repair (deferred).

    Returns:
        Repaired text if any tier succeeded, None if all tiers failed.
    """
    if capture_buf is None:
        return None

    # Tier 1: text-level repair
    repaired = repair_tier1(capture_buf, tool_names)
    if repaired is not None:
        return repaired

    # Tier 2: JSON-level repair (only meaningful if tier1 extracted the structure)
    repaired = repair_tier2(capture_buf, tool_names)
    if repaired is not None:
        return repaired

    # Tier 3: reconstruct truncated tool call fragments
    repaired = repair_tier3(capture_buf, tool_names)
    if repaired is not None:
        return repaired

    # Tier 3b: model self-repair fallback
    if tier3_callback is not None:
        repaired = tier3_callback(capture_buf)
        if repaired and len(repaired.strip()) > 0:
            return repaired

    return None
