"""Hierarchical task engine with ReAct loop.

Tasks are structured as trees:
  RootTask → SubTask → LeafWorkItem

Each task goes through: Think → Act → Execute → Observe → Reflect → Learn
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from cradle.llm_router import LLMRouter, LLMResponse
from cradle.sandbox import Sandbox, SandboxResult

logger = logging.getLogger(__name__)



class TaskStatus(str, Enum):
    PENDING = "pending"
    THINKING = "thinking"
    ACTING = "acting"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A unit of work in the hierarchical task tree."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    parent_id: Optional[str] = None
    children: list[str] = field(default_factory=list)
    result: str = ""
    error: str = ""
    attempts: int = 0
    max_attempts: int = 3
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    reflection: str = ""
    source: str = "user"  # user, self, heartbeat


class TaskEngine:
    """Manages the hierarchical task tree and executes tasks via ReAct loop."""

    def __init__(self, llm: LLMRouter, sandbox: Sandbox, skills=None):
        self.llm = llm
        self.sandbox = sandbox
        self.skills = skills  # Optional[SkillLoader]
        self.tasks: dict[str, Task] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    def add_task(
        self,
        title: str,
        description: str = "",
        parent_id: Optional[str] = None,
        source: str = "user",
    ) -> Task:
        """Create and enqueue a new task."""
        task = Task(
            title=title,
            description=description or title,
            parent_id=parent_id,
            source=source,
        )
        self.tasks[task.id] = task
        if parent_id and parent_id in self.tasks:
            self.tasks[parent_id].children.append(task.id)

        self._queue.put_nowait(task.id)
        logger.info(f"Task added: [{task.id}] {title}")
        return task

    async def process_next(self) -> Optional[Task]:
        """Process the next task in the queue using the ReAct loop."""
        try:
            task_id = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        task = self.tasks.get(task_id)
        if not task:
            return None

        return await self._react_loop(task)

    async def _react_loop(self, task: Task) -> Task:
        """Execute a single task through the ReAct cycle."""
        task.attempts += 1
        logger.info(f"ReAct loop [{task.id}] attempt {task.attempts}: {task.title}")

        # ── THINK: Plan the approach ──
        task.status = TaskStatus.THINKING
        plan = await self._think(task)

        if plan.get("type") == "direct_answer":
            # No code execution needed — just a text response
            task.result = plan.get("answer", "")
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            return task

        if plan.get("type") == "decompose":
            # Task needs decomposition into sub-tasks
            for sub in plan.get("subtasks", []):
                self.add_task(
                    title=sub.get("title", ""),
                    description=sub.get("description", ""),
                    parent_id=task.id,
                    source="self",
                )
            task.status = TaskStatus.BLOCKED  # Wait for children
            return task

        # ── ACT: Generate code ──
        task.status = TaskStatus.ACTING
        code = plan.get("code", "")
        language = plan.get("language", "python")

        if not code:
            task.error = "Think phase produced no code"
            task.status = TaskStatus.FAILED
            return task

        # ── EXECUTE: Run in sandbox ──
        task.status = TaskStatus.EXECUTING
        if language == "python":
            result = await self.sandbox.run_python(
                code,
                packages=plan.get("packages", []),
                network=plan.get("needs_network", False),
            )
        else:
            result = await self.sandbox.run_shell(code)

        # ── OBSERVE + REFLECT ──
        task.status = TaskStatus.REFLECTING
        reflection = await self._reflect(task, code, result)

        task.reflection = reflection.get("reflection", "")

        if result.success:
            task.result = result.stdout or reflection.get("summary", "Task completed")
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            logger.info(f"Task [{task.id}] completed successfully")
        else:
            task.error = result.stderr or "Unknown error"
            if task.attempts < task.max_attempts and reflection.get("should_retry"):
                logger.info(f"Task [{task.id}] failed, retrying...")
                # Re-enqueue for another attempt
                self._queue.put_nowait(task.id)
                task.status = TaskStatus.PENDING
            else:
                task.status = TaskStatus.FAILED
                logger.warning(f"Task [{task.id}] failed permanently: {task.error}")

        return task

    async def _think(self, task: Task) -> dict:
        """THINK phase: Plan how to solve the task."""
        # Build skill context
        skills_summary = ""
        skill_details = ""
        if self.skills:
            skills_summary = self.skills.get_skills_summary()
            skill_details = self.skills.get_relevant_skills(task.title, task.description)

        system = """You are Cradle, a fully autonomous self-evolving AI agent.

## Your capabilities:
1. Run Python or bash code in an isolated Docker sandbox (DinD — docker run piped via stdin)
2. Access the internet (web search, APIs) when needs_network=true
3. Edit your own source code at /app/repo/cradle/ and push to GitHub
4. **Trigger a self-restart/update:** call sys.exit(42) in Python to restart with new code
5. Store skills, memories, prompts in AgentPlaybooks.ai via MCP (AGENTPLAYBOOKS_API_KEY env var)
6. Spawn sub-agents by cloning repos and running them in Docker (NanoClaw pattern)
7. Do ANYTHING the user asks via Telegram — treat every message as a task

## Response format — pick exactly one:
1. {"type": "direct_answer", "answer": "..."} — for questions needing no code
2. {"type": "code", "language": "python", "code": "...", "packages": [], "needs_network": false} — execute Python
3. {"type": "code", "language": "bash", "code": "..."} — execute shell
4. {"type": "decompose", "subtasks": [{"title": "...", "description": "..."}]} — for complex multi-step tasks

## Key environment variables available in sandbox:
- GITHUB_PAT — push to agenthatchery/cradle
- AGENTPLAYBOOKS_API_KEY + AGENTPLAYBOOKS_PLAYBOOK_GUID — store skills/memory via MCP
- GEMINI_API_KEY — call Gemini directly if needed
- GOOGLE_CSE_KEY + GOOGLE_CSE_ID — Google Custom Search

## Self-update pattern (IMPORTANT):
To update the agent's own code and restart:
```python
import subprocess, os, sys
repo = "/app/repo"
# 1. Edit files in /app/repo/cradle/
# 2. Git commit and push
subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "feat: <description>"], check=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
subprocess.run(["git", "-C", repo, "push", "origin", "main"], check=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
print("Code pushed. Triggering restart...")
sys.exit(42)  # Exit code 42 = entrypoint will git pull and restart automatically
```

## AgentPlaybooks persistence:
Store ALL skills, prompts, and memories on agentplaybooks.ai — not local. Use the MCP API.
Locally defined skills exist only as seeds that get uploaded on boot.

Be practical, direct, and confident. Write clean working code."""

        if skills_summary:
            system += f"\n\n{skills_summary}"

        prompt = f"Task: {task.title}\n\nDescription: {task.description}"

        if task.attempts > 1 and task.error:
            prompt += f"\n\nPrevious attempt failed with:\n{task.error}\n\nPlease fix the issue."

        if skill_details:
            prompt += f"\n\n## Relevant Skill Instructions\n{skill_details}"

        response = await self.llm.complete(prompt, system=system)

        # Parse JSON from response
        try:
            # Try to extract JSON from markdown code blocks
            text = response.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            # If we can't parse JSON, treat the whole response as a direct answer
            return {"type": "direct_answer", "answer": response.content}

    async def _reflect(self, task: Task, code: str, result: SandboxResult) -> dict:
        """REFLECT phase: Analyze the execution result."""
        system = """You are Cradle reflecting on a task execution. Analyze the result and provide:
1. A brief reflection on what happened
2. A summary of the outcome
3. Whether to retry if it failed (and why)
4. Any learnings to store for future reference

Respond with JSON: {"reflection": "...", "summary": "...", "should_retry": true/false, "learnings": ["..."]}"""

        prompt = f"""Task: {task.title}
Code executed:
```
{code[:2000]}
```

Exit code: {result.exit_code}
Success: {result.success}
Duration: {result.duration_ms}ms

stdout:
{result.stdout[:2000]}

stderr:
{result.stderr[:2000]}"""

        try:
            # Use a cheaper model for reflection
            response = await self.llm.complete(
                prompt, system=system, preferred_provider="groq"
            )

            text = response.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            return json.loads(text.strip())
        except Exception:
            return {
                "reflection": "Failed to parse reflection",
                "summary": result.stdout[:500] if result.success else result.stderr[:500],
                "should_retry": not result.success and task.attempts < task.max_attempts,
                "learnings": [],
            }

    def get_status_summary(self) -> str:
        """Human-readable summary of all tasks."""
        if not self.tasks:
            return "📋 No tasks."

        lines = ["📋 Task Status:"]
        for task in sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)[:10]:
            icon = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.THINKING: "🧠",
                TaskStatus.ACTING: "⚡",
                TaskStatus.EXECUTING: "🐳",
                TaskStatus.REFLECTING: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.BLOCKED: "🔒",
            }.get(task.status, "❓")
            lines.append(f"  {icon} [{task.id}] {task.title} ({task.status.value})")

        return "\n".join(lines)

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()
