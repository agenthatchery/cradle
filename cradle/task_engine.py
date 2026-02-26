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
        self.dynamic_persona: Optional[str] = None

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
            # Auto-inject relevant Python skill definitions so the LLM doesn't have to perfectly copy them
            if self.skills:
                skill_impls = self.skills.get_relevant_skills_python(task.title, task.description)
                if skill_impls:
                    code = f"{skill_impls}\n\n# --- LLM GENERATED CODE BELOW ---\n{code}"

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

            # Self-update detection: if the agent pushed code and wants a restart
            if "SELF_UPDATE_PUSHED" in (result.stdout or ""):
                logger.info("🔄 Self-update detected! Agent pushed code. Triggering restart...")
                import sys
                sys.exit(42)  # Entrypoint will git pull and restart

            # Store successful result in AgentPlaybooks memory
            try:
                await self.memory.store(
                    key=f"task_result:{task.id}",
                    value={"title": task.title, "result": (task.result or "")[:2000]},
                    tags=["task", "success", task.source or "unknown"],
                    description=f"Completed: {task.title}",
                    tier="contextual",
                )
            except Exception:
                pass
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

        # Use dynamic persona from AgentPlaybooks if available, fallback to hardcoded
        persona_base = self.dynamic_persona or """You are Cradle, a fully autonomous self-evolving AI agent running inside Docker."""
        system = f"""{persona_base}

## CRITICAL RULE: ALWAYS WRITE CODE
🚨 You MUST respond with executable code for ANY task that involves doing something.
NEVER use "direct_answer" unless the user asks a simple factual question like "what is 2+2?" or "what's your status?".
NEVER write placeholder comments like `# I would run this` or `# Simulate updating`. Your code is actually executed. If you need to clone, clone. If you need to edit, edit.

For research tasks: write Python code that uses urllib to fetch URLs.
For web search: write Python code using the web_search pattern.
For GitHub: write Python code using git clone.
For AgentPlaybooks: write Python code using httpx or urllib.
IF IN DOUBT, WRITE CODE. The sandbox will run it.

## CRITICAL: Sandbox is an ISOLATED container
Your code runs in a FRESH `cradle-sandbox` Docker container (python:3.12-slim + git/curl/jq).
⚠️ DO NOT import `cradle`, `skills`, `memory`, or any Cradle module — they DO NOT EXIST. Specifying `import skills` will crash the agent.
⚠️ DO NOT access /app/ or /app/repo/ — they DO NOT EXIST in the sandbox.
The sandbox has Python stdlib + git + curl + jq. List extra packages in "packages": [...].

## Response format — ONLY JSON, no markdown fences:
{{"type": "code", "language": "python", "code": "print('hello')", "packages": [], "needs_network": false}}
{{"type": "code", "language": "bash", "code": "echo hello", "needs_network": false}}
{{"type": "direct_answer", "answer": "..."}}
{{"type": "decompose", "subtasks": [{{"title": "...", "description": "..."}}]}}

⚠️ Set "needs_network": true for ANY task involving: web search, API calls, git clone, pip install, curl.

## Environment variables available in sandbox:
- GITHUB_PAT — for git clone https://$GITHUB_PAT@github.com/...
- AGENTPLAYBOOKS_API_KEY + AGENTPLAYBOOKS_PLAYBOOK_GUID — AgentPlaybooks.ai MCP
- GEMINI_API_KEY — call Gemini directly
- GOOGLE_CSE_KEY + GOOGLE_CSE_ID — Google Custom Search

## Self-update pattern:
To modify your own code: clone from GitHub → edit → commit → push → print("SELF_UPDATE_PUSHED")
```python
import subprocess, os
token = os.environ.get("GITHUB_PAT", "")
env = {{**os.environ, "GIT_TERMINAL_PROMPT": "0"}}
subprocess.run(["git", "clone", f"https://{{token}}@github.com/agenthatchery/cradle.git", "/tmp/cradle"], check=True, env=env)
# Edit files at /tmp/cradle/cradle/...
subprocess.run(["git", "-C", "/tmp/cradle", "add", "-A"], check=True, env=env)
subprocess.run(["git", "-C", "/tmp/cradle", "commit", "-m", "feat: description"], check=True, env=env)
subprocess.run(["git", "-C", "/tmp/cradle", "push", "origin", "main"], check=True, env=env)
print("SELF_UPDATE_PUSHED")
```

## Spawning Excellence:
Before using `spawn_agent`, research the repository structure:
1. Use `github_read_file` or a bash command to check for `package.json` (Node), `requirements.txt` (Python), or `Dockerfile`.
2. For `qwibitai/nanoclaw` or `anomalyco/opencode`: These are Node.js projects. If no Dockerfile is found, use an image like `node:20-slim` and a command like `["npm", "start"]`.
3. NEVER assume `main.py` exists in the root of a repository. Research first!

Output ONLY raw JSON. No markdown fences. No explanation before or after."""

        # Inject skill details directly into prompt for maximum relevance
        if skill_details:
            system += f"\n\n## ⚠️ CRITICAL: Skill Instructions\n"
            system += "Skill functions are NOT pre-imported. You MUST copy the full Python implementation (e.g. `def spawn_agent(...)`) from the instructions below directly into your code.\n\n"
            system += skill_details
        elif skills_summary:
            system += f"\n\n{skills_summary}"

        prompt = f"Task: {task.title}\n\nDescription: {task.description}"

        if task.attempts > 1 and task.error:
            prompt += f"\n\nPrevious attempt failed with:\n{task.error}\n\nPlease fix the issue and try again."

        response = await self.llm.complete(prompt, system=system)

        # Robust JSON extraction (same strategy as evolver)
        text = response.content
        parsed = self._extract_json(text)
        if parsed:
            return parsed

        # Fallback: treat as direct answer
        logger.warning(f"Could not parse JSON from LLM response, falling back to direct_answer. First 200 chars: {text[:200]}")
        return {"type": "direct_answer", "answer": text}

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

            parsed = self._extract_json(response.content)
            if parsed:
                return parsed

            return {
                "reflection": response.content[:500],
                "summary": result.stdout[:500] if result.success else result.stderr[:500],
                "should_retry": not result.success and task.attempts < task.max_attempts,
                "learnings": [],
            }
        except Exception:
            return {
                "reflection": "Failed to parse reflection",
                "summary": result.stdout[:500] if result.success else result.stderr[:500],
                "should_retry": not result.success and task.attempts < task.max_attempts,
                "learnings": [],
            }

    def _extract_json(self, text: str) -> Optional[dict]:
        """Robustly extract a JSON object from LLM output."""
        import re

        # Strategy 1: Direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from ```json ... ``` fences
        json_fence = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_fence:
            try:
                return json.loads(json_fence.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find first { to last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            # Strategy 4: Fix trailing commas
            candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        return None

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
