"""AgentPlaybooks.ai memory client — persists skills, tasks, and reflections.

Uses the MCP JSON-RPC protocol for writes and REST API for reads.
Supports hierarchical memory with tiers (working/contextual/longterm),
task graphs, canvas, and skills.

API Endpoints:
  - GET  /api/playbooks/{guid}/memory          — list/read memories
  - POST /api/mcp/{guid}                       — MCP JSON-RPC (write_memory, create_skill, etc.)
"""

import json
import logging
from typing import Optional, Any

import httpx

from cradle.config import Config

logger = logging.getLogger(__name__)

BASE_URL = "https://agentplaybooks.ai"


class Memory:
    """Client for AgentPlaybooks.ai — MCP JSON-RPC + REST API."""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.agentplaybooks_key
        self.guid = config.agentplaybooks_guid
        self.playbook_id = config.agentplaybooks_playbook_id
        self._client = httpx.AsyncClient(timeout=30.0)
        self._rpc_id = 0

    async def close(self):
        await self._client.aclose()

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _next_rpc_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    # ── MCP JSON-RPC Call (for all write operations) ──

    async def _mcp_call(self, tool_name: str, arguments: dict) -> Optional[dict]:
        """Call an MCP tool via JSON-RPC on AgentPlaybooks."""
        if not self.guid or not self.api_key:
            logger.debug("Memory: no GUID or API key configured")
            return None

        url = f"{BASE_URL}/api/mcp/{self.guid}"
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_rpc_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            resp = await self._client.post(url, json=payload, headers=self._auth_headers())
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                logger.error(f"MCP error calling {tool_name}: {data['error']}")
                return None

            result = data.get("result", {})
            logger.info(f"MCP {tool_name} succeeded")
            return result
        except Exception as e:
            logger.error(f"MCP call {tool_name} failed: {e}")
            return None

    # ── REST API (for reads) ──

    async def _rest_get(self, path: str, params: Optional[dict] = None) -> Optional[Any]:
        """GET request to REST API."""
        if not self.guid:
            return None

        url = f"{BASE_URL}/api/playbooks/{self.guid}/{path}"
        try:
            resp = await self._client.get(url, params=params, headers=self._auth_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"REST GET {path} failed: {e}")
            return None

    # ── Memory Operations ──

    async def store(
        self,
        key: str,
        value: Any,
        tags: Optional[list[str]] = None,
        description: str = "",
        tier: str = "contextual",
        priority: int = 50,
        parent_key: Optional[str] = None,
        summary: Optional[str] = None,
        memory_type: str = "flat",
        status: Optional[str] = None,
    ) -> bool:
        """Store a memory entry via MCP write_memory tool."""
        args: dict = {"key": key, "value": value}
        if tags:
            args["tags"] = tags
        if description:
            args["description"] = description
        if tier != "contextual":
            args["tier"] = tier
        if priority != 50:
            args["priority"] = priority
        if parent_key:
            args["parent_key"] = parent_key
        if summary:
            args["summary"] = summary
        if memory_type != "flat":
            args["memory_type"] = memory_type
        if status:
            args["status"] = status

        result = await self._mcp_call("write_memory", args)
        if result is not None:
            logger.info(f"Memory stored: {key} (tier={tier})")
            return True
        return False

    async def recall(self, key: str) -> Optional[dict]:
        """Read a memory entry via MCP read_memory tool."""
        result = await self._mcp_call("read_memory", {"key": key})
        return result

    async def search(
        self,
        search: Optional[str] = None,
        tags: Optional[list[str]] = None,
        tier: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> list:
        """Search memories via MCP search_memory tool."""
        args: dict = {}
        if search:
            args["search"] = search
        if tags:
            args["tags"] = tags
        if tier:
            args["tier"] = tier
        if memory_type:
            args["memory_type"] = memory_type

        result = await self._mcp_call("search_memory", args)
        if result and isinstance(result, dict):
            # MCP returns content array
            content = result.get("content", [])
            if content and isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        try:
                            return json.loads(item.get("text", "[]"))
                        except json.JSONDecodeError:
                            return []
        return []

    async def recall_all(self) -> list:
        """Retrieve all memories via REST API (faster for bulk reads)."""
        data = await self._rest_get("memory")
        return data if isinstance(data, list) else []

    async def forget(self, key: str) -> bool:
        """Delete a memory entry."""
        result = await self._mcp_call("delete_memory", {"key": key})
        return result is not None

    # ── Task Graph Operations ──

    async def create_task_graph(
        self,
        plan_key: str,
        plan_summary: str,
        tasks: list[dict],
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Create a hierarchical task graph in AgentPlaybooks."""
        args: dict = {
            "plan_key": plan_key,
            "plan_summary": plan_summary,
            "tasks": tasks,
        }
        if tags:
            args["tags"] = tags

        result = await self._mcp_call("create_task_graph", args)
        if result is not None:
            logger.info(f"Task graph created: {plan_key} with {len(tasks)} tasks")
            return True
        return False

    async def update_task_status(
        self,
        key: str,
        status: str,
        result: Optional[dict] = None,
        summary: Optional[str] = None,
    ) -> bool:
        """Update a task's status in a hierarchical plan."""
        args: dict = {"key": key, "status": status}
        if result:
            args["result"] = result
        if summary:
            args["summary"] = summary

        r = await self._mcp_call("update_task_status", args)
        return r is not None

    # ── Skill Operations ──

    async def store_skill(self, name: str, content: str, description: str = "") -> bool:
        """Create or update a skill via MCP. deduplicates by name."""
        # Check if exists
        skills = await self.list_skills()
        exists = any(s.get("name") == name for s in skills)
        
        tool = "update_skill" if exists else "create_skill"
        result = await self._mcp_call(tool, {
            "name": name,
            "content": content,
            "description": description or name,
        })
        if result is not None:
            logger.info(f"Skill {tool}ed: {name}")
            return True
        return False

    async def list_skills(self) -> list:
        """List all skills via MCP."""
        result = await self._mcp_call("list_skills", {})
        if result and isinstance(result, dict):
            content = result.get("content", [])
            if content and isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        try:
                            return json.loads(item.get("text", "[]"))
                        except json.JSONDecodeError:
                            return []
        return []

    # ── Reflection & Learning Storage ──

    async def store_reflection(self, task_id: str, reflection: str, learnings: list[str]):
        """Store a task reflection in hierarchical memory."""
        await self.store(
            key=f"reflection:{task_id}",
            value={"reflection": reflection, "learnings": learnings},
            tags=["reflection", "self-evolution"],
            description=f"Reflection on task {task_id}",
            tier="contextual",
            summary=reflection[:200] if reflection else "",
        )

        # Store each learning as a separate memory for easy retrieval
        for i, learning in enumerate(learnings):
            if learning.strip():
                await self.store(
                    key=f"learning:{task_id}:{i}",
                    value={"learning": learning},
                    tags=["learning"],
                    description=learning[:200],
                    tier="longterm",
                )

    async def get_learnings(self) -> list[str]:
        """Retrieve all stored learnings."""
        memories = await self.search(tags=["learning"])
        learnings = []
        for mem in memories:
            val = mem.get("value", {})
            if isinstance(val, dict):
                learnings.append(val.get("learning", ""))
            elif isinstance(val, str):
                learnings.append(val)
        return [l for l in learnings if l]

    # ── Canvas Operations (for storing plans, docs) ──

    async def write_canvas(self, slug: str, name: str, content: str) -> bool:
        """Create or update a canvas document."""
        result = await self._mcp_call("write_canvas", {
            "slug": slug,
            "name": name,
            "content": content,
        })
        return result is not None

    async def read_canvas(self, slug: str) -> Optional[str]:
        """Read a canvas document."""
        result = await self._mcp_call("read_canvas", {"slug": slug})
        if result and isinstance(result, dict):
            content = result.get("content", [])
            if content and isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        return item.get("text", "")
        return None

    # ── Context View ──

    async def get_context(self, tiers: Optional[list[str]] = None) -> Optional[dict]:
        """Get optimized context view of memories."""
        args: dict = {}
        if tiers:
            args["include_tiers"] = tiers
        return await self._mcp_call("get_memory_context", args)

    async def update_playbook(
        self,
        persona_name: Optional[str] = None,
        persona_system_prompt: Optional[str] = None,
        persona_metadata: Optional[dict] = None,
    ) -> bool:
        """Update the agent's core persona and system prompt in AgentPlaybooks."""
        args: dict = {}
        if persona_name:
            args["persona_name"] = persona_name
        if persona_system_prompt:
            args["persona_system_prompt"] = persona_system_prompt
        if persona_metadata:
            args["persona_metadata"] = persona_metadata

        if not args:
            return False

        result = await self._mcp_call("update_playbook", args)
        return result is not None

    async def get_persona(self) -> Optional[dict]:
        """Fetch the agent's core persona (including system prompt) from the API."""
        # The REST API for playbook detail includes the persona fields
        data = await self._rest_get("")
        if data and isinstance(data, dict):
            return {
                "name": data.get("persona_name"),
                "system_prompt": data.get("persona_system_prompt"),
                "metadata": data.get("persona_metadata", {}),
            }
        return None

    async def archive_memories(self, keys: Optional[list[str]] = None, older_than_hours: Optional[float] = None) -> bool:
        """Consolidate/Archive memories into longterm tier."""
        args: dict = {}
        if keys:
            args["keys"] = keys
        if older_than_hours:
            args["older_than_hours"] = older_than_hours
        
        result = await self._mcp_call("archive_memories", args)
        return result is not None
