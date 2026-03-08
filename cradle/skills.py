import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)




class SkillLoader:
    """Loads skills from AgentPlaybooks and provides them to the task engine."""

    def __init__(self, memory):
        self.memory = memory
        self._cache: dict[str, dict] = {}  # name -> {description, content}
        self._loaded = False

    async def sync_builtin_skills(self) -> int:
        """Deprecated. Skills are now managed entirely via AgentPlaybooks."""
        self._loaded = True
        return 0

    async def sync_with_remote(self):
        """Standard sync method used by Heartbeat. Pulls all skills from remote."""
        # Pull skills from remote AgentPlaybooks via memory.py
        await self.fetch_from_agentplaybooks()

    def load_builtin_skills_local(self):
        """Deprecated. Skills are now managed entirely via AgentPlaybooks."""
        self._loaded = True

    async def fetch_from_agentplaybooks(self) -> int:
        """Fetch skills from AgentPlaybooks (merges with local cache)."""
        try:
            remote_skills = await self.memory.list_skills()
            count = 0
            for s in remote_skills or []:
                name = s.get("name", "")
                if name and name not in self._cache:
                    self._cache[name] = {
                        "description": s.get("description", ""),
                        "content": s.get("content", ""),
                    }
                    count += 1
            if count:
                logger.info(f"Fetched {count} extra skills from AgentPlaybooks")
            return count
        except Exception as e:
            logger.warning(f"Could not fetch skills from AgentPlaybooks: {e}")
            return 0

    def get_skills_summary(self) -> str:
        """Short list of available skills for system prompt injection."""
        if not self._cache:
            return ""
        lines = ["## Available Skills (use these in your code)"]
        for name, skill in self._cache.items():
            desc = skill["description"][:120]
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)

    def get_skill_content(self, name: str) -> Optional[str]:
        """Get the full SKILL.md content for a specific skill."""
        skill = self._cache.get(name)
        return skill["content"] if skill else None

    def get_relevant_skills(self, task_title: str, task_description: str) -> str:
        """Return full content of skills relevant to this task, including descriptions."""
        # For now, return all skills. In the future, use an LLM to select relevant ones.
        if not self._cache:
            return ""

        lines = ["## Relevant Skills"]
        for name, skill in self._cache.items():
            lines.append(f"\n### Skill: {name}\n")
            if skill.get("description"):
                lines.append(f"Description: {skill['description']}\n")
            lines.append(skill["content"])
        return "\n".join(lines)
