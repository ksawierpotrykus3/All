import pytest
from server.core.input_parser import InputParser, ParsedRequest


class TestDetectToolsInSystem:
    def test_tools_detected_in_system_prompt(self):
        raw = {
            "messages": [
                {"role": "system", "content": "You are a helper.\n\n<tool_call name=\"Read\">\n  <file_path>test.txt</file_path>\n</tool_call>\n\nAvailable tools:\n\n<tools>\n  <tool_call name=\"Read\">\n    <file_path type=\"string\" required=\"true\"/>\n  </tool_call>\n</tools>"},
                {"role": "user", "content": "hello"},
            ],
            "tools": [{"function": {"name": "Read", "description": "Read a file"}}],
        }
        result = InputParser.parse(raw)
        assert result.has_tools_in_system_prompt is True


class TestToolsNotInSystem:
    def test_tools_not_detected_when_absent(self):
        raw = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "hello"},
            ],
            "tools": [{"function": {"name": "Read"}}],
        }
        result = InputParser.parse(raw)
        assert result.has_tools_in_system_prompt is False
        assert result.tools is not None
        assert result.tools[0]["function"]["name"] == "Read"


class TestSystemReminderFilter:
    def test_only_last_reminder_kept(self):
        raw = {
            "messages": [
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "<system-reminder>old context</system-reminder>"},
                {"role": "user", "content": "hello"},
                {"role": "user", "content": "<system-reminder>current context</system-reminder>"},
            ],
        }
        result = InputParser.parse(raw)
        reminders = [
            m for m in result.messages
            if isinstance(m.get("content", ""), str) and "<system-reminder>" in m["content"]
        ]
        assert len(reminders) == 1
        assert "current" in reminders[0]["content"]


class TestFlashRouting:
    """Test routing for simple/generic tasks to Flash model."""
    
    def test_title_generation_routes_to_flash(self):
        """Title generation should use Flash (default) not Expert."""
        raw = {
            "model": "deepseek-v4-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "Generate a short, descriptive name for a chat from the user'''s first message. "
                               "Rules: use a concise topic noun phrase of 2-6 words; Title Case; no punctuation."
                },
                {"role": "user", "content": "How do I fix rate limit errors?"}
            ]
        }
        parsed = InputParser.parse(raw)
        assert parsed.model_type == "default"  # Flash
        assert parsed.thinking_enabled == False
        assert parsed.search_enabled == False
    
    def test_chat_title_keyword_routes_to_flash(self):
        """System prompts with '''chat title''' keyword → Flash."""
        raw = {
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "system", "content": "Create a chat title for this conversation in Title Case"},
                {"role": "user", "content": "Debug my code"}
            ]
        }
        parsed = InputParser.parse(raw)
        assert parsed.model_type == "default"
    
    def test_code_task_still_routes_to_expert(self):
        """Code tasks should still use Expert, not affected by Flash routing."""
        raw = {
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "system", "content": "You are Kiro. Write code to solve problems."},
                {"role": "user", "content": "Write a Python function"}
            ]
        }
        parsed = InputParser.parse(raw)
        assert parsed.model_type == "expert"
        assert parsed.thinking_enabled == True
