"""Heartbeat daemon — the continuous pulse of the Cradle agent.

Runs every N seconds and:
1. Processes ALL pending tasks
2. Auto-generates improvement tasks when idle
3. Triggers periodic self-evolution
4. Stores system prompt & skills in AgentPlaybooks
5. Persists state
"""

import asyncio
import logging
import time
import json
import os

from cradle.config import Config
from cradle.task_engine import TaskEngine
from cradle.evolver import Evolver
from cradle.memory import Memory
from cradle.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

# Self-improvement task templates — the agent cycles through these
SELF_IMPROVEMENT_TASKS = [

    {
        "title": "Update Cradle version and push to GitHub",
        "description": "Increment the version number in cradle/heartbeat.py from v0.6.0 to v0.6.1, commit the change, and push to GitHub. This proves you can successfully edit your own source code and deploy updates.",
    },
    {
        "title": "Perform a deep architecture review using Gemini 3.1 Pro",
        "description": (
            "Read all source files in the cradle/ directory. "
            "Use the premium 'gemini-pro' provider (Gemini 3.1 Pro Preview) to analyze "
            "the architecture for bottlenecks, security flaws, and scalability issues. "
            "Store the detailed analysis as a Canvas document in AgentPlaybooks."
        ),
    },
    {
        "title": "Synchronize agent capabilities as official Skills",
        "description": (
            "For each key module (sandbox, llm_router, memory, evolver), "
            "generate a concise 'skill definition' (prompt/instructions). "
            "Use memory.store_skill to upload these to AgentPlaybooks. "
            "Ensure they follow the international agentplaybook.ai standard."
        ),
    },
    {
        "title": "Research and implement NanoClaw-style sub-agent spawning",
        "description": (
            "Analyze the NanoClaw spawning mechanism (cloning GitHub repos into Docker). "
            "Implement a 'SubAgentSpawner' skill that can take a GitHub URL, "
            "spin up a container, execute a specific command, and pull results. "
            "Test with 'github.com/matebenyovszky/healing-agent' as a proof of concept."
        ),
    },
    {
        "title": "Audit and optimize multi-provider cost/performance",
        "description": (
            "Analyze the last 100 LLM calls from logs. Compare latency and success rates "
            "between Gemini 2.5 Flash, Groq, and OpenAI. "
            "Adjust provider priorities in config.py if certain providers are underperforming. "
            "Store the optimization report in AgentPlaybooks memory."
        ),
    },
    {
        "title": "Enhance Evolver with automated unit test generation",
        "description": (
            "Modify the evolver.py to automatically generate unit tests for proposed changes. "
            "The evolver should write a test file, run it in the sandbox, "
            "and only proceed if BOTH the code and the new tests pass. "
            "This ensures self-modifications are safe."
        ),
    },
    {
        "title": "Implement long-term memory consolidation (RLM)",
        "description": (
            "Analyze the current memory usage. Implement a background task that "
            "takes 'contextual' memories and summarizes them into 'longterm' memories "
            "using RLM (Recursive Language Model) patterns. "
            "This prevents context window bloat while retaining knowledge."
        ),
    },
    {
        "title": "Research and implement revenue-generating agent skills",
        "description": (
            "Investigate automated bug bounty hunting and freelance coding tasks. "
            "Develop a skill that can search for open issues on GitHub tagged 'good first issue' "
            "and propose fixes for them. Goal: make the agent self-sustaining."
        ),
    },
]


class Heartbeat:
    """Continuous heartbeat loop driving all agent activity."""

    def __init__(
        self,
        config: Config,
        task_engine: TaskEngine,
        evolver: Evolver,
        memory: Memory,
        telegram: TelegramBot,
    ):
        self.config = config
        self.task_engine = task_engine
        self.evolver = evolver
        self.memory = memory
        self.telegram = telegram
        self.interval = config.heartbeat_interval
        self.beat_count = 0
        self.start_time = time.time()
        self._running = False
        self._improvement_index = 0  # cycles through SELF_IMPROVEMENT_TASKS

    async def start(self):
        """Start the heartbeat loop."""
        self._running = True
        logger.info(f"Heartbeat starting (interval={self.interval}s)")

        # Announce on Telegram (best-effort)
        try:
            pending = self.task_engine.pending_count
            await self.telegram.send_message(
                f"🐣 Cradle Agent v0.6.0 online!\n"
                f"⏱️ Heartbeat: every {self.interval}s\n"
                f"📋 Pending tasks: {pending}\n"
                f"🧬 Self-evolution: active\n"
                f"🔄 Continuous improvement: enabled\n\n"
                f"Send /status for info, or just send me a task."
            )
        except Exception as e:
            logger.warning(f"Startup announcement failed: {e}")

        # Store masterplan & system prompt on AgentPlaybooks (best-effort)
        await self._persist_to_agentplaybooks()

        while self._running:
            try:
                await self._beat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}", exc_info=True)

            await asyncio.sleep(self.interval)

    async def stop(self):
        """Stop the heartbeat loop."""
        self._running = False
        logger.info("Heartbeat stopped")

    async def _beat(self):
        """One heartbeat cycle."""
        self.beat_count += 1

        # ── Process ALL pending tasks (up to 3 per beat) ──
        tasks_processed = 0
        while self.task_engine.pending_count > 0 and tasks_processed < 3:
            task = await self.task_engine.process_next()
            if not task:
                break
            tasks_processed += 1

            # Notify via Telegram — full result, no truncation (long messages are chunked by send_message)
            if task.status.value in ("completed", "failed"):
                icon = "✅" if task.status.value == "completed" else "❌"
                msg = f"{icon} [{task.id}] {task.title}\n"
                if task.result:
                    msg += f"\n{task.result[:3800]}"
                if task.error:
                    msg += f"\n⚠️ Error: {task.error[:1000]}"
                try:
                    await self.telegram.send_message(msg)
                except Exception:
                    pass

            # ── Self-healing: auto-create fix task on failure ──
            if task.status.value == "failed" and task.error:
                fix_title = f"Fix failure: {task.title[:60]}"
                fix_desc = (
                    f"The task '{task.title}' failed with this error:\n"
                    f"{task.error[:500]}\n\n"
                    f"Analyze the error, fix the root cause, and retry the task. "
                    f"If it's a code error, correct the code and re-run. "
                    f"If it's a missing dependency, install it and retry. "
                    f"Store the fix as a learning in AgentPlaybooks memory. "
                    f"Original description: {task.description[:300]}"
                )
                self.task_engine.add_task(
                    title=fix_title,
                    description=fix_desc,
                    parent_id=task.id,
                    source="self-healing",
                )
                logger.info(f"🩹 Self-healing task created for [{task.id}]: {fix_title}")

            # Store reflections in AgentPlaybooks
            if task.reflection:
                try:
                    await self.memory.store_reflection(task.id, task.reflection, [])
                except Exception:
                    pass

        if tasks_processed > 0:
            logger.info(f"Processed {tasks_processed} tasks this beat")

        # ── Auto-generate improvement tasks when idle ──
        # Every 20 beats (~10 min) if no pending tasks, seed the next improvement
        if (self.beat_count % 20 == 0 and
            self.task_engine.pending_count == 0 and
            self.beat_count > 5):

            task_def = SELF_IMPROVEMENT_TASKS[
                self._improvement_index % len(SELF_IMPROVEMENT_TASKS)
            ]
            self._improvement_index += 1

            self.task_engine.add_task(
                title=task_def["title"],
                description=task_def["description"],
                source="self-improvement",
            )
            logger.info(
                f"🔄 Auto-generated improvement task: {task_def['title']}"
            )

        # ── Self-evolution: first at beat 20, then every 50 beats ──
        if self.beat_count == 20 or (self.beat_count > 20 and self.beat_count % 50 == 0):
            logger.info(f"🧬 Triggering self-evolution (beat #{self.beat_count})")
            try:
                result = await self.evolver.evolve()
                logger.info(f"Evolution result: {result[:200]}")
                try:
                    await self.telegram.send_message(f"🧬 Self-evolution:\n{result}")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Self-evolution failed: {e}")

        # ── Periodic state persistence (every 5 beats) ──
        if self.beat_count % 5 == 0:
            await self._persist_state()

        # ── Memory Consolidation (every 20 beats) ──
        if self.beat_count % 20 == 0:
            logger.info("🧠 Consolidating memories...")
            await self.memory.archive_memories(older_than_hours=12)

        # ── Fetch latest skills & persona from AgentPlaybooks (every 10 beats) ──
        if self.beat_count > 0 and self.beat_count % 10 == 0:
            await self._sync_from_agentplaybooks()

        # ── Git auto-sync: pull from GitHub and restart if new commits (every 20 beats ≈ 10min) ──
        if self.beat_count > 0 and self.beat_count % 20 == 0:
            await self._git_auto_sync()

        # ── Persist to AgentPlaybooks (every 100 beats ≈ 50 min) ──
        if self.beat_count > 0 and self.beat_count % 100 == 0:
            await self._persist_to_agentplaybooks()

        # ── Log heartbeat (every 5 beats ≈ 2.5 min) ──
        if self.beat_count % 5 == 0:
            uptime = int(time.time() - self.start_time)
            logger.info(
                f"💓 Beat #{self.beat_count} | uptime={uptime}s | "
                f"pending={self.task_engine.pending_count} | "
                f"total={len(self.task_engine.tasks)} | "
                f"evolutions={self.evolver.evolution_count}"
            )

    async def _persist_state(self):
        """Save current state to disk for crash recovery."""
        state = {
            "beat_count": self.beat_count,
            "start_time": self.start_time,
            "uptime_seconds": int(time.time() - self.start_time),
            "evolution_count": self.evolver.evolution_count,
            "improvement_index": self._improvement_index,
            "tasks": {
                tid: {
                    "title": t.title,
                    "status": t.status.value,
                    "result": (t.result[:500] if t.result else ""),
                    "error": (t.error[:500] if t.error else ""),
                    "source": t.source,
                }
                for tid, t in self.task_engine.tasks.items()
            },
        }

        state_path = os.path.join(self.config.data_dir, "state.json")
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist state: {e}")

    async def _persist_to_agentplaybooks(self):
        """Store masterplan, system prompt, and status on AgentPlaybooks.ai."""
        try:
            # 1. Store the masterplan as a Canvas document
            masterplan = (
                "# Cradle Agent — Masterplan\n\n"
                "## Mission: Kardashev Level 3\n"
                "Self-evolving agent aiming to continuously improve itself and serve humanity.\n\n"
                "## Current Architecture\n"
                "- **Cradle** (Docker on Tower.local): Orchestrator + heartbeat\n"
                "- **Sandbox** (Docker-in-Docker): Isolated code execution\n"
                "- **GitHub** (agenthatchery/cradle): Persistent code versioning\n"
                "- **AgentPlaybooks.ai**: Skills, memory, prompts, MCP servers\n"
                "- **Telegram** (@agenthatchery_bot): Human communication channel\n\n"
                "## Self-Evolution Loop\n"
                "1. Evolver reads source → proposes change → tests in sandbox → pushes to GitHub → restarts\n"
                "2. Heartbeat cycles through self-improvement tasks every ~10 min\n"
                "3. Git auto-sync pulls external changes every ~10 min\n"
                "4. Task results stored in AgentPlaybooks memory after every completion\n\n"
                "## Active Capabilities\n"
                "- Web search (Google CSE + DuckDuckGo fallback)\n"
                "- GitHub operations (clone, read, push, branch, merge)\n"
                "- Sub-agent spawning (NanoClaw pattern: clone repo → Docker run)\n"
                "- Multi-LLM routing (Gemini, Groq, OpenAI, MiniMax, OpenRouter)\n\n"
                "## Next Priorities\n"
                f"- Evolution count: {self.evolver.evolution_count}\n"
                f"- Tasks processed: {len(self.task_engine.tasks)}\n"
                f"- Uptime: {int(time.time() - self.start_time)}s\n"
            )
            await self.memory.write_canvas("masterplan", "Cradle Masterplan", masterplan)
            logger.info("📋 Masterplan stored on AgentPlaybooks Canvas")

            # 2. Update persona system prompt
            await self.memory.update_playbook(
                persona_name="Cradle Agent",
                persona_system_prompt=(
                    "You are Cradle, a fully autonomous self-evolving AI agent running inside Docker.\n\n"
                    "## CRITICAL RULE: ALWAYS WRITE CODE\n"
                    "🚨 You MUST respond with executable code for ANY task that involves doing something.\n"
                    "NEVER use \"direct_answer\" unless the user asks a simple factual question like \"what is 2+2?\" or \"what's your status?\".\n"
                    "NEVER write placeholder comments like `# I would run this` or `# Simulate updating`. Your code is actually executed. If you need to clone, clone. If you need to edit, edit.\n\n"
                    "For research tasks: write Python code that uses urllib to fetch URLs.\n"
                    "For web search: write Python code using the web_search pattern.\n"
                    "For GitHub: write Python code using git clone.\n"
                    "For AgentPlaybooks: write Python code using httpx or urllib.\n"
                    "IF IN DOUBT, WRITE CODE. The sandbox will run it.\n\n"
                    "## CRITICAL: Sandbox is an ISOLATED container\n"
                    "Your code runs in a FRESH `cradle-sandbox` Docker container (python:3.12-slim + git/curl/jq).\n"
                    "⚠️ DO NOT import `cradle`, `skills`, `memory`, or any Cradle module — they DO NOT EXIST. Specifying `import skills` will crash the agent.\n"
                    "⚠️ DO NOT access /app/ or /app/repo/ — they DO NOT EXIST in the sandbox.\n"
                    "The sandbox has Python stdlib + git + curl + jq. List extra packages in \"packages\": [...].\n\n"
                    "## Response format — ONLY JSON, no markdown fences:\n"
                    '{"type": "code", "language": "python", "code": "print(\'hello\')", "packages": [], "needs_network": false}\n'
                    '{"type": "code", "language": "bash", "code": "echo hello", "needs_network": false}\n'
                    '{"type": "direct_answer", "answer": "..."}\n'
                    '{"type": "decompose", "subtasks": [{"title": "...", "description": "..."}]}\n\n'
                    "⚠️ Set \"needs_network\": true for ANY task involving: web search, API calls, git clone, pip install, curl.\n\n"
                    "## Environment variables available in sandbox:\n"
                    "- GITHUB_PAT — for git clone https://$GITHUB_PAT@github.com/...\n"
                    "- AGENTPLAYBOOKS_API_KEY + AGENTPLAYBOOKS_PLAYBOOK_GUID — AgentPlaybooks.ai MCP\n"
                    "- GEMINI_API_KEY — call Gemini directly\n"
                    "- GOOGLE_CSE_KEY + GOOGLE_CSE_ID — Google Custom Search\n\n"
                    "## Self-update pattern:\n"
                    "To modify your own code: clone from GitHub → edit → commit → push → print(\"SELF_UPDATE_PUSHED\")\n"
                    "```python\n"
                    "import subprocess, os\n"
                    "token = os.environ.get(\"GITHUB_PAT\", \"\")\n"
                    "env = {**os.environ, \"GIT_TERMINAL_PROMPT\": \"0\"}\n"
                    "subprocess.run([\"git\", \"clone\", f\"https://{token}@github.com/agenthatchery/cradle.git\", \"/tmp/cradle\"], check=True, env=env)\n"
                    "# Edit files at /tmp/cradle/cradle/...\n"
                    "subprocess.run([\"git\", \"-C\", \"/tmp/cradle\", \"add\", \"-A\"], check=True, env=env)\n"
                    "subprocess.run([\"git\", \"-C\", \"/tmp/cradle\", \"commit\", \"-m\", \"feat: description\"], check=True, env=env)\n"
                    "subprocess.run([\"git\", \"-C\", \"/tmp/cradle\", \"push\", \"origin\", \"main\"], check=True, env=env)\n"
                    "print(\"SELF_UPDATE_PUSHED\")\n"
                    "```\n\n"
                    "## Spawning Excellence:\n"
                    "Before using `spawn_agent`, research the repository structure:\n"
                    "1. Use `github_read_file` or a bash command to check for `package.json` (Node), `requirements.txt` (Python), or `Dockerfile`.\n"
                    "2. For `qwibitai/nanoclaw` or `anomalyco/opencode`: These are Node.js projects. If no Dockerfile is found, use an image like `node:20-slim` and a command like `[\"npm\", \"start\"]`.\n"
                    "3. NEVER assume `main.py` exists in the root of a repository. Research first!\n\n"
                    "Output ONLY raw JSON. No markdown fences. No explanation before or after."
                ),
            )
            logger.info("🧠 Persona updated on AgentPlaybooks")

            # 3. Store current status as a memory
            await self.memory.store(
                key="agent_status",
                value={
                    "version": "0.6.0",
                    "uptime": int(time.time() - self.start_time),
                    "beats": self.beat_count,
                    "evolutions": self.evolver.evolution_count,
                    "tasks_total": len(self.task_engine.tasks),
                },
                tags=["status", "heartbeat"],
                tier="working",
                description="Current agent operational status",
            )
            logger.info("💾 Agent status stored in memory")

        except Exception as e:
            logger.warning(f"AgentPlaybooks persistence failed: {e}")


    async def _git_auto_sync(self):
        """Check GitHub for updates, pull, and restart (only if idle)."""
        # Never interrupt running/pending tasks for a background update
        if self.task_engine.pending_count > 0:
            logger.debug("Skipping git auto-sync (tasks are pending)")
            return

        repo_dir = "/app/repo"
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            return

        try:
            # Fetch latest from remote
            proc = await asyncio.create_subprocess_exec(
                "git", "-C", repo_dir, "fetch", "origin", "main",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()

            # Count commits that are in origin/main but not in local HEAD
            proc = await asyncio.create_subprocess_exec(
                "git", "-C", repo_dir, "rev-list", "HEAD...origin/main", "--count",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                count = int(stdout.decode().strip() or "0")
                if count > 0:
                    logger.info(f"🔄 GitHub auto-sync: found {count} new commits. Agent is idle. Restarting...")
                    try:
                        await self.telegram.send_message(f"🔄 Auto-sync: Pulled {count} new commits from GitHub.\nRestarting agent...")
                    except Exception:
                        pass
                    import sys
                    sys.exit(42)  # Exit 42 tells entrypoint.sh to git pull and restart

        except Exception as e:
            logger.warning(f"Git auto-sync failed: {e}")

    async def _sync_from_agentplaybooks(self):
        """Fetch latest skills and persona from AgentPlaybooks.ai."""
        try:
            # 1. Sync Skills
            await self.task_engine.skills.sync_with_remote()
            logger.info("📡 Skills synced from AgentPlaybooks")

            # 2. Sync Persona (System Prompt)
            persona = await self.memory.get_persona()
            if persona and persona.get("system_prompt"):
                # Update the task engine's dynamic persona if available
                # We'll need to modify TaskEngine to support this
                # For now, we update the Config or TaskEngine class variable
                self.task_engine.dynamic_persona = persona["system_prompt"]
                logger.info("🧠 Remote Persona synced from AgentPlaybooks")
        except Exception as e:
            logger.warning(f"Sync from AgentPlaybooks failed: {e}")

    def get_status(self) -> str:
        """Human-readable status string."""
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60

        return (
            f"🐣 Cradle Agent v0.6.0\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"⏱️ Uptime: {hours}h {minutes}m\n"
            f"💓 Heartbeats: {self.beat_count}\n"
            f"📋 Pending tasks: {self.task_engine.pending_count}\n"
            f"📊 Total tasks: {len(self.task_engine.tasks)}\n"
            f"🧬 Evolutions: {self.evolver.evolution_count}\n"
            f"🔄 Improvement cycle: {self._improvement_index}/{len(SELF_IMPROVEMENT_TASKS)}"
        )
