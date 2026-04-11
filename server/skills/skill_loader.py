"""
Learned Skill Loader — loads Markdown-based skills created by the AI.
Skills are SKILL.md files with YAML frontmatter + markdown body.
They get injected into the system prompt to guide AI behavior.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LEARNED_DIR = Path(__file__).parent / "learned"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (metadata, body)."""
    import yaml
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except Exception:
        meta = {}
    return meta, match.group(2)


class SkillLoader:
    def __init__(self, skills_dir: Path = LEARNED_DIR):
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[dict]:
        """Load all learned skills. Returns list of skill dicts."""
        skills = []
        for skill_dir in sorted(self.skills_dir.iterdir()):
            skill_file = None
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
            elif skill_dir.is_file() and skill_dir.suffix == ".md":
                skill_file = skill_dir
            if not skill_file or not skill_file.exists():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(content)
                skills.append({
                    "name": meta.get("name", skill_dir.stem),
                    "description": meta.get("description", ""),
                    "categories": meta.get("categories", []),
                    "enabled": meta.get("enabled", True),
                    "trigger": meta.get("trigger", "always"),
                    "trigger_config": meta.get("trigger_config", {}),
                    "created_at": meta.get("created_at", ""),
                    "body": body.strip(),
                    "path": str(skill_file),
                })
            except Exception as e:
                logger.warning(f"Failed to load skill {skill_dir}: {e}")
        return skills

    def get_active_skills(self, trigger_type: Optional[str] = None) -> list[dict]:
        """Get enabled skills, optionally filtered by trigger type."""
        skills = self.load_all()
        active = [s for s in skills if s["enabled"]]
        if trigger_type:
            active = [s for s in active if s["trigger"] == trigger_type or s["trigger"] == "always"]
        return active

    def get_prompt_injection(self) -> str:
        """Build system prompt fragment from active skills."""
        skills = self.get_active_skills()
        if not skills:
            return ""
        parts = ["## 你學會的技能\n"]
        for s in skills:
            parts.append(f"### {s['name']}")
            if s["description"]:
                parts.append(s["description"])
            parts.append(s["body"])
            parts.append("")
        return "\n".join(parts)

    def save_skill(self, name: str, description: str, body: str,
                   categories: list[str] = None, trigger: str = "always",
                   trigger_config: dict = None) -> Path:
        """Create or overwrite a learned skill."""
        import yaml
        from datetime import date

        safe_name = re.sub(r'[^\w\-]', '_', name).lower().strip('_')
        if not safe_name:
            raise ValueError("Invalid skill name")

        skill_dir = self.skills_dir / safe_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "name": safe_name,
            "description": description,
            "categories": categories or [],
            "enabled": True,
            "created_at": str(date.today()),
            "trigger": trigger,
        }
        if trigger_config:
            meta["trigger_config"] = trigger_config

        content = f"---\n{yaml.dump(meta, allow_unicode=True, default_flow_style=False)}---\n\n{body}\n"
        path = skill_dir / "SKILL.md"
        path.write_text(content, encoding="utf-8")
        logger.info(f"Skill saved: {safe_name} at {path}")
        return path

    def update_skill(self, name: str, body: str) -> Path:
        """Update the body of an existing skill, preserving metadata."""
        safe_name = re.sub(r'[^\w\-]', '_', name).lower().strip('_')
        skill_file = self.skills_dir / safe_name / "SKILL.md"
        if not skill_file.exists():
            # Try flat file
            skill_file = self.skills_dir / f"{safe_name}.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill not found: {name}")

        content = skill_file.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(content)

        import yaml
        new_content = f"---\n{yaml.dump(meta, allow_unicode=True, default_flow_style=False)}---\n\n{body}\n"
        skill_file.write_text(new_content, encoding="utf-8")
        logger.info(f"Skill updated: {safe_name}")
        return skill_file

    def disable_skill(self, name: str) -> bool:
        """Set enabled=false in skill metadata."""
        safe_name = re.sub(r'[^\w\-]', '_', name).lower().strip('_')
        skill_file = self.skills_dir / safe_name / "SKILL.md"
        if not skill_file.exists():
            skill_file = self.skills_dir / f"{safe_name}.md"
        if not skill_file.exists():
            return False

        content = skill_file.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        meta["enabled"] = False

        import yaml
        new_content = f"---\n{yaml.dump(meta, allow_unicode=True, default_flow_style=False)}---\n\n{body}\n"
        skill_file.write_text(new_content, encoding="utf-8")
        logger.info(f"Skill disabled: {safe_name}")
        return True

    def list_skills(self) -> list[dict]:
        """Return summary of all skills (without body)."""
        return [{k: v for k, v in s.items() if k != "body"} for s in self.load_all()]


# Singleton
skill_loader = SkillLoader()
