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
        "title": "Migrate Cradle system prompt to AgentPlaybooks Persona",
        "description": (
            "Extract the full system prompt from task_engine.py and config instructions. "
            "Use the memory.update_playbook tool to set the persona_system_prompt in AgentPlaybooks. "
            "This makes the agent's core instructions editable from the web UI."
        ),
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
                f"🐣 Cradle Agent v0.5.0 online!\n"
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

        # ── Fetch latest skills from AgentPlaybooks (every 10 beats) ──
        if self.beat_count > 0 and self.beat_count % 10 == 0:
            if getattr(self.task_engine, "skills", None):
                try:
                    await self.task_engine.skills.fetch_from_agentplaybooks()
                except Exception as e:
                    logger.debug(f"Background skill fetch failed: {e}")

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
            f"🐣 Cradle Agent v0.5.0\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"⏱️ Uptime: {hours}h {minutes}m\n"
            f"💓 Heartbeats: {self.beat_count}\n"
            f"📋 Pending tasks: {self.task_engine.pending_count}\n"
            f"📊 Total tasks: {len(self.task_engine.tasks)}\n"
            f"🧬 Evolutions: {self.evolver.evolution_count}\n"
            f"🔄 Improvement cycle: {self._improvement_index}/{len(SELF_IMPROVEMENT_TASKS)}"
        )
