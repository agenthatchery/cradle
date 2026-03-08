"""Skills — SKILL.md-compatible capabilities for the Cradle agent.

Skills follow the Anthropic open standard (used by NanoClaw, Claude Code, Cursor):
- YAML frontmatter with name, description
- Markdown body with detailed instructions
- Stored in AgentPlaybooks.ai for persistent, editable management
- Loaded dynamically and injected into task context

The agent loads skill name+description on every task, and loads full
instructions only when the skill is relevant (progressive disclosure).
"""

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
        """Return full content of skills relevant to this task."""
        text = (task_title + " " + task_description).lower()
        relevant = []

        keywords = {
            "web_search": ["search", "web", "internet", "research", "find", "look up", "browse", "google",
                          "url", "http", "trending", "news", "investigate", "money", "revenue", "bounty",
                          "discover", "explore", "scrape"],
            "github_cli": ["github", "git", "repo", "clone", "commit", "push", "pull", "code", "file",
                          "repository", "evolve", "self", "modify", "update", "branch", "merge", "source"],
            "spawn_agent": ["spawn", "sub-agent", "subagent", "agent", "nanoclaw", "healing",
                           "opencode", "openclaw", "container", "docker run"],
        }

        for name, kws in keywords.items():
            if any(kw in text for kw in kws) and name in self._cache:
                relevant.append(self._cache[name]["content"])

        return "\n\n".join(relevant)
        
    def get_relevant_skills_python(self, task_title: str, task_description: str) -> str:
        """Extract just the Python code blocks from relevant skills to auto-inject."""
        text = (task_title + " " + task_description).lower()
        python_code = []
        import re

        keywords = {
            "web_search": ["search", "web", "internet", "research", "find", "look up", "browse", "google",
                          "url", "http", "trending", "news", "investigate", "money", "revenue", "bounty",
                          "discover", "explore", "scrape"],
            "github_cli": ["github", "git", "repo", "clone", "commit", "push", "pull", "code", "file",
                          "repository", "evolve", "self", "modify", "update", "branch", "merge", "source"],
            "spawn_agent": ["spawn", "sub-agent", "subagent", "agent", "nanoclaw", "healing",
                           "opencode", "openclaw", "container", "docker run"],
        }

        for name, kws in keywords.items():
            if any(kw in text for kw in kws) and name in self._cache:
                content = self._cache[name]["content"]
                blocks = re.findall(r'```python\s*([\s\S]*?)```', content)
                for block in blocks:
                    clean_block = []
                    for line in block.split('\n'):
                        if '# Example usage:' in line or '## Example usage' in line:
                            break
                        clean_block.append(line)
                    python_code.append("\n".join(clean_block))

        return "\n\n".join(python_code)
