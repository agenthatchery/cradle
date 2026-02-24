"""AgentPlaybooks.ai memory client — stores skills, learnings, and reflections.

Uses the Playbook API with the agent's API key for memory write-back.
Memory is hierarchical:
  - Strategic: long-term goals, plans
  - Skill: learned capabilities, patterns
  - Task: specific task results, reflections
"""

import json
import logging
from typing import Optional

import httpx

from cradle.config import Config

logger = logging.getLogger(__name__)


class Memory:
    """Client for AgentPlaybooks.ai memory and skills API."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.agentplaybooks_base_url
        self.api_key = config.agentplaybooks_key
        self.guid = config.agentplaybooks_guid
        self.playbook_id = config.agentplaybooks_playbook_id
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ── Memory Operations ──

    async def store(self, key: str, value: str, tags: Optional[list[str]] = None) -> bool:
        """Store a memory entry."""
        if not self.guid or not self.api_key:
            logger.debug("Memory: no API key or GUID configured, skipping store")
            return False

        try:
            url = f"{self.base_url}/playbooks/{self.guid}/memory/{key}"
            body = {"value": value}
            if tags:
                body["tags"] = tags

            resp = await self._client.put(url, json=body, headers=self._headers())
            resp.raise_for_status()
            logger.info(f"Memory stored: {key}")
            return True
        except Exception as e:
            logger.error(f"Memory store failed for {key}: {e}")
            return False

    async def recall(self, key: str) -> Optional[str]:
        """Retrieve a memory entry."""
        if not self.guid:
            return None

        try:
            url = f"{self.base_url}/playbooks/{self.guid}/memory"
            resp = await self._client.get(url, headers=self._headers())
            resp.raise_for_status()
            memories = resp.json()

            # Search through memories for the key
            if isinstance(memories, list):
                for mem in memories:
                    if mem.get("key") == key:
                        return mem.get("value")
            elif isinstance(memories, dict):
                return memories.get(key)

            return None
        except Exception as e:
            logger.error(f"Memory recall failed for {key}: {e}")
            return None

    async def recall_all(self) -> dict:
        """Retrieve all memory entries."""
        if not self.guid:
            return {}

        try:
            url = f"{self.base_url}/playbooks/{self.guid}/memory"
            resp = await self._client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Memory recall_all failed: {e}")
            return {}

    async def forget(self, key: str) -> bool:
        """Delete a memory entry."""
        if not self.guid or not self.api_key:
            return False

        try:
            url = f"{self.base_url}/playbooks/{self.guid}/memory/{key}"
            resp = await self._client.delete(url, headers=self._headers())
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Memory forget failed for {key}: {e}")
            return False

    # ── Skill Operations ──

    async def store_skill(self, name: str, content: str) -> bool:
        """Store a learned skill."""
        if not self.playbook_id or not self.api_key:
            logger.debug("Memory: no playbook_id configured, storing skill as memory")
            return await self.store(f"skill:{name}", content, tags=["skill"])

        try:
            url = f"{self.base_url}/playbooks/{self.playbook_id}/skills"
            body = {
                "name": name,
                "content": content,
            }
            resp = await self._client.post(url, json=body, headers=self._headers())
            resp.raise_for_status()
            logger.info(f"Skill stored: {name}")
            return True
        except Exception as e:
            logger.error(f"Skill store failed for {name}: {e}")
            # Fall back to memory storage
            return await self.store(f"skill:{name}", content, tags=["skill"])

    async def list_skills(self) -> list:
        """List all stored skills."""
        if not self.playbook_id:
            return []

        try:
            url = f"{self.base_url}/playbooks/{self.playbook_id}/skills"
            resp = await self._client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Skill list failed: {e}")
            return []

    # ── Reflection Storage ──

    async def store_reflection(self, task_id: str, reflection: str, learnings: list[str]):
        """Store a task reflection and any learnings."""
        await self.store(
            f"reflection:{task_id}",
            json.dumps({
                "reflection": reflection,
                "learnings": learnings,
            }),
            tags=["reflection"],
        )

        # Store each learning as a separate skill-like memory
        for i, learning in enumerate(learnings):
            if learning.strip():
                await self.store(
                    f"learning:{task_id}:{i}",
                    learning,
                    tags=["learning"],
                )

    async def get_learnings(self) -> list[str]:
        """Retrieve all stored learnings."""
        memories = await self.recall_all()
        learnings = []

        if isinstance(memories, list):
            for mem in memories:
                if "learning" in (mem.get("tags", []) or []):
                    learnings.append(mem.get("value", ""))
                elif isinstance(mem.get("key", ""), str) and mem["key"].startswith("learning:"):
                    learnings.append(mem.get("value", ""))
        elif isinstance(memories, dict):
            for key, value in memories.items():
                if key.startswith("learning:"):
                    learnings.append(value if isinstance(value, str) else str(value))

        return learnings
