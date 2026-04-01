import importlib
import inspect
import logging
from pathlib import Path
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}
        self._definitions: list[dict] = []

    def register(self, skill):
        for tool_def in skill.tools:
            tool_name = tool_def["function"]["name"]
            if tool_name in self._skills:
                logger.warning(f"Tool '{tool_name}' already registered, overwriting")
            self._skills[tool_name] = skill
            self._definitions.append(tool_def)
            logger.info(f"Registered tool: {tool_name}")

    def discover(self, skills_dir: str = "skills/builtin"):
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return

        module_prefix = str(skills_path).replace("/", ".").replace("\\", ".")

        for file in skills_path.glob("*.py"):
            if file.name.startswith("_"):
                continue
            module_name = f"{module_prefix}.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                for name, cls in inspect.getmembers(module, inspect.isclass):
                    if issubclass(cls, BaseSkill) and cls is not BaseSkill:
                        instance = cls()
                        self.register(instance)
                        logger.info(f"Discovered skill: {name} from {file.name}")
            except Exception as e:
                logger.error(f"Failed to load skill from {file.name}: {e}")

    def get_tool_definitions(self) -> list[dict]:
        return self._definitions

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        if tool_name not in self._skills:
            return {"error": f"Unknown tool: {tool_name}"}
        skill = self._skills[tool_name]
        try:
            return await skill.execute(tool_name, **arguments)
        except Exception as e:
            logger.error(f"Skill execution failed: {tool_name}: {e}")
            return {"error": str(e)}

    async def initialize_all(self):
        seen = set()
        for skill in self._skills.values():
            if id(skill) not in seen:
                seen.add(id(skill))
                try:
                    await skill.initialize()
                except Exception as e:
                    logger.warning(f"Skill initialization failed: {e}")
