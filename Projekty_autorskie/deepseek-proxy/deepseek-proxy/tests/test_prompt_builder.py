"""
Tests for PromptBuilder with tool dedup.
Run: python -m pytest tests/test_prompt_builder.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from server.core.prompt_builder import PromptBuilder


class TestBuild:
    def test_basic_prompt(self):
        result = PromptBuilder.build(
            "Hello",
            system_prompt="You are a helpful assistant.",
        )
        assert "You are a helpful assistant." in result
        assert "[User]:" in result
        assert "[Assistant]:" in result
        assert "Hello" in result

    def test_tools_always_added_when_provided(self):
        """FIX 2026-09-04: Tools are ALWAYS added when IDE sends them.
        
        Even if system_prompt contains tool-related keywords (e.g. in examples/docs),
        we must add tools_schema because IDE explicitly requested it.
        """
        tools = [{"name": "Read", "description": "Read files"}]
        result = PromptBuilder.build(
            "List files",
            system_prompt="You are an assistant. Use <tool_call> to call tools.",
            tools_schema=tools,
        )
        # Tools MUST be present even though system_prompt mentions <tool_call>
        assert "[Available Tool]: Read" in result
        assert "IMPORTANT: When you need to call a tool" in result

    def test_includes_history(self):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = PromptBuilder.build(
            "How are you?",
            history=history,
        )
        assert "Hello" in result
        assert "Hi!" in result

    def test_empty_system_prompt(self):
        result = PromptBuilder.build("Hello")
        assert "[User]:\nHello" in result

    def test_tool_injection_when_needed(self):
        tools = [{"name": "Read", "description": "Read files"}]
        result = PromptBuilder.build(
            "List files",
            system_prompt="You are an assistant.",
            tools_schema=tools,
        )
        assert "[Available Tool]: Read" in result
        assert "When you need to use a tool" not in result

class TestBuildWithToolNames:
    def test_no_dsml_in_tool_block(self):
        tools = [{"name": "Read", "description": "Read files"},
                 {"name": "Write", "description": "Write files"}]
        result = PromptBuilder.build(
            "Do something",
            system_prompt="You are helpful.",
            tools_schema=tools,
        )
        assert "[Available Tool]:" in result
        assert "<tool_calls>" in result
        assert "<invoke name=" in result
        assert "IMPORTANT" in result

    def test_tools_injected_even_when_mentioned_in_system(self):
        """FIX 2026-09-04: Tools are added even if system_prompt mentions them.
        
        System prompt might contain [Available Tool] in documentation/examples.
        We still add our tools_schema section because IDE requested it.
        """
        tools = [{"name": "Read", "description": "Read files"}]
        result = PromptBuilder.build(
            "Hi",
            system_prompt="Here is the tool list:\n[Available Tool]: Read()",
            tools_schema=tools,
        )
        # Count occurrences - should appear in both system_prompt AND tools section
        count = result.count("[Available Tool]:")
        assert count >= 2, f"Expected tools to appear at least twice (system + schema), got {count}"

    def test_resume_prompt_no_tools_no_system(self):
        result = PromptBuilder.build(
            "Continue",
            system_prompt=None,
            tools_schema=None,
        )
        assert "[System]:" not in result  # no system section at all
        assert "[User]:\nContinue" in result
        assert "[Assistant]:" in result

class TestToolsAlwaysIncluded:
    """Regression tests for tools schema injection bug (2026-09-04).
    
    Bug: System prompt contained <tool_call in documentation/examples.
    _tools_not_in_system_prompt() returned False, blocking tools injection.
    Fix: Always add tools_schema when IDE sends it, ignore system_prompt content.
    """
    
    def test_tools_added_despite_tool_call_in_docs(self):
        """Reproduce the exact bug: system_prompt with <tool_call at position ~1842."""
        # Simulate system_prompt with tool examples in documentation
        system_prompt = "You are helpful.\n" + " " * 1800 + "<tool_call>example</tool_call>"
        tools = [
            {"name": "Shell", "description": "Run shell commands"},
            {"name": "Read", "description": "Read files"},
        ]
        
        result = PromptBuilder.build(
            "Run tests",
            system_prompt=system_prompt,
            tools_schema=tools,
        )
        
        # Tools MUST be in prompt
        assert "[Available Tool]: Shell" in result
        assert "[Available Tool]: Read" in result
        assert "IMPORTANT: When you need to call a tool" in result
    
    def test_tools_added_with_empty_system_prompt(self):
        """Edge case: no system_prompt at all."""
        tools = [{"name": "Write", "description": "Write files"}]
        
        result = PromptBuilder.build(
            "Create file",
            system_prompt=None,
            tools_schema=tools,
        )
        
        assert "[Available Tool]: Write" in result
    
    def test_tools_added_with_multiple_user_messages(self):
        """Simulate the full bug scenario: multiple user messages + tools."""
        system_prompt = "You are AI.\n" + "x" * 1842 + "<tool_call>...</tool_call>"
        history = [{"role": "user", "content": "User info: workspace=/path"}]
        tools = [{"name": "Execute", "description": "Execute code"}]
        
        result = PromptBuilder.build(
            "Run python script",
            system_prompt=system_prompt,
            history=history,
            tools_schema=tools,
        )
        
        # All parts must be present
        assert "[Available Tool]: Execute" in result
        assert "User info: workspace=/path" in result
        assert "Run python script" in result

