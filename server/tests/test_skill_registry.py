import pytest
import asyncio


class FakeSkill:
    """A minimal skill for testing."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "fake_action",
                    "description": "A fake action for testing",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "input": {"type": "string", "description": "test input"}
                        },
                        "required": ["input"],
                    },
                },
            }
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if tool_name == "fake_action":
            return {"success": True, "echo": kwargs.get("input", "")}
        return {"error": f"Unknown tool: {tool_name}"}

    async def initialize(self):
        pass


def test_register_and_get_definitions():
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.register(FakeSkill())
    defs = reg.get_tool_definitions()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "fake_action"


def test_execute_registered_skill():
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.register(FakeSkill())
    result = asyncio.run(reg.execute("fake_action", {"input": "hello"}))
    assert result["success"] is True
    assert result["echo"] == "hello"


def test_execute_unknown_tool():
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    result = asyncio.run(reg.execute("nonexistent", {}))
    assert "error" in result


def test_register_multiple_tools():
    from skills.registry import SkillRegistry

    class MultiSkill:
        @property
        def tools(self):
            return [
                {"type": "function", "function": {"name": "tool_a", "description": "A", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "tool_b", "description": "B", "parameters": {"type": "object", "properties": {}}}},
            ]

        async def execute(self, tool_name, **kwargs):
            return {"tool": tool_name}

        async def initialize(self):
            pass

    reg = SkillRegistry()
    reg.register(MultiSkill())
    assert len(reg.get_tool_definitions()) == 2


def test_initialize_all():
    from skills.registry import SkillRegistry

    initialized = []

    class TrackingSkill:
        @property
        def tools(self):
            return [{"type": "function", "function": {"name": "tracked", "description": "t", "parameters": {"type": "object", "properties": {}}}}]

        async def execute(self, tool_name, **kwargs):
            return {}

        async def initialize(self):
            initialized.append(True)

    reg = SkillRegistry()
    reg.register(TrackingSkill())
    asyncio.run(reg.initialize_all())
    assert len(initialized) == 1
