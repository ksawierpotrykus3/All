import pytest
from server.repair.repair_tier3 import repair_tier3


class TestTier3Repair:
    def test_reconstruct_partial_tool_call(self):
        # Model emitted <tool_call name="Read" but stream ended before closing
        fragment = '<tool_call name="Read"><parameter name="file_path">/tmp/test.txt</parameter>'
        tool_names = ["Read", "Write", "Bash"]
        result = repair_tier3(fragment, tool_names)
        assert result is not None
        assert "name=\"Read\"" in result
        assert "file_path" in result
        assert "</tool_call>" in result
