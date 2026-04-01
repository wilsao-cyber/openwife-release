from abc import ABC, abstractmethod


class BaseSkill(ABC):
    """Base class for all skills. Each skill provides one or more LLM tools."""

    @property
    @abstractmethod
    def tools(self) -> list[dict]:
        """Return list of OpenAI-format tool definitions.

        Each entry: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        ...

    @abstractmethod
    async def execute(self, tool_name: str, **kwargs) -> dict:
        """Execute a tool call. tool_name matches function.name in tools."""
        ...

    async def initialize(self):
        """Optional async initialization. Override if needed."""
        pass
