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
        "title": "Store Cradle system prompt in AgentPlaybooks as a skill",
        "description": (
            "Read the current system prompt from the task_engine._think method, "
            "and store it as a skill named 'cradle_system_prompt' in AgentPlaybooks.ai. "
            "This ensures the prompt is editable and persistent across restarts."
        ),
    },
    {
        "title": "Research NanoClaw agent framework on GitHub",
        "description": (
            "Search for and read about NanoClaw (github.com/openclaw/nanoclaw or similar). "
            "Understand how it spawns Docker sub-agents from skills. "
            "Write a summary of how to integrate NanoClaw-style spawning into Cradle."
        ),
    },
    {
        "title": "Implement sub-agent spawning from GitHub repos",
        "description": (
            "Write Python code to clone a GitHub repo into a temp directory, "
            "build a Docker image from it, and run it as an ephemeral sub-agent "
            "that sends results back via a mounted volume. "
            "Test with: github.com/matebenyovszky/healing-agent as a sample repo."
        ),
    },
    {
        "title": "Store agent capabilities as AgentPlaybooks skills",
        "description": (
            "Create skills in AgentPlaybooks for each Cradle capability: "
            "1) 'llm_routing' - how to use multi-provider LLM with fallback, "
            "2) 'docker_sandbox' - how to run code in isolated containers, "
            "3) 'self_evolution' - how to improve own code via GitHub. "
            "Use the create_skill MCP tool."
        ),
    },
    {
        "title": "Analyze and optimize token usage across providers",
        "description": (
            "Review the LLM router stats. Calculate cost per provider. "
            "Identify which providers are most cost-effective for different task types. "
            "Propose prompt optimization strategies to reduce token usage."
        ),
    },
    {
        "title": "Create a self-assessment report of current capabilities",
        "description": (
            "List all working features, broken features, and missing features. "
            "Score each capability 0-10. Identify the top 3 improvements that would "
            "have the highest impact. Store this in AgentPlaybooks memory. "
            "Report findings to the operator via Telegram."
        ),
    },
    {
        "title": "Research revenue generation strategies",
        "description": (
            "Analyze potential revenue streams: 1) bug bounty programs, "
            "2) freelance coding on platforms, 3) building websites/agents for clients, "
            "4) improving AgentPlaybooks.ai as a product, "
            "5) content automation for robohorizon.com. "
            "Rank by feasibility vs effort. Store findings in AgentPlaybooks memory."
        ),
    },
    {
        "title": "Improve error handling in all modules",
        "description": (
            "Review all Python files in cradle/ for error handling gaps. "
            "Add proper try/except blocks, better error messages, "
            "and graceful degradation. Focus on: sandbox.py, llm_router.py, memory.py."
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
                f"🐣 Cradle Agent v0.4.0 online!\n"
                f"⏱️ Heartbeat: every {self.interval}s\n"
                f"📋 Pending tasks: {pending}\n"
                f"🧬 Self-evolution: active\n"
                f"🔄 Continuous improvement: enabled\n\n"
                f"Send /status for info, or just send me a task."
            )
        except Exception as e:
            logger.warning(f"Startup announcement failed: {e}")

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

            # Notify via Telegram
            if task.status.value in ("completed", "failed"):
                icon = "✅" if task.status.value == "completed" else "❌"
                msg = f"{icon} Task [{task.id}]: {task.title}\n"
                if task.result:
                    msg += f"\n{task.result[:3000]}"
                if task.error:
                    msg += f"\n⚠️ Error: {task.error[:1000]}"
                try:
                    await self.telegram.send_message(msg)
                except Exception:
                    pass

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

    def get_status(self) -> str:
        """Human-readable status string."""
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60

        return (
            f"🐣 Cradle Agent v0.4.0\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"⏱️ Uptime: {hours}h {minutes}m\n"
            f"💓 Heartbeats: {self.beat_count}\n"
            f"📋 Pending tasks: {self.task_engine.pending_count}\n"
            f"📊 Total tasks: {len(self.task_engine.tasks)}\n"
            f"🧬 Evolutions: {self.evolver.evolution_count}\n"
            f"🔄 Improvement cycle: {self._improvement_index}/{len(SELF_IMPROVEMENT_TASKS)}"
        )
