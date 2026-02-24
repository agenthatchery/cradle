"""Heartbeat daemon — the continuous pulse of the Cradle agent.

Runs every N seconds and:
1. Processes pending tasks from the queue
2. Checks for self-evolution opportunities
3. Monitors sub-agent health
4. Persists state
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

    async def start(self):
        """Start the heartbeat loop."""
        self._running = True
        logger.info(f"Heartbeat starting (interval={self.interval}s)")

        # Announce on Telegram
        await self.telegram.send_message(
            f"🐣 Cradle Agent v0.1.0 online!\n"
            f"⏱️ Heartbeat: every {self.interval}s\n"
            f"🤖 Ready for tasks.\n\n"
            f"Send /status for info, or just send me a task."
        )

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

        # ── Process pending tasks ──
        if self.task_engine.pending_count > 0:
            task = await self.task_engine.process_next()
            if task:
                # Notify via Telegram
                if task.status.value in ("completed", "failed"):
                    icon = "✅" if task.status.value == "completed" else "❌"
                    msg = f"{icon} Task [{task.id}]: {task.title}\n"
                    if task.result:
                        msg += f"\n{task.result[:3000]}"
                    if task.error:
                        msg += f"\n⚠️ Error: {task.error[:1000]}"
                    await self.telegram.send_message(msg)

                # Store reflections
                if task.reflection:
                    await self.memory.store_reflection(
                        task.id,
                        task.reflection,
                        [],  # Learnings extracted separately
                    )

        # ── Periodic self-evolution (every 100 beats ≈ ~50 min) ──
        if self.beat_count % 100 == 0 and self.beat_count > 0:
            logger.info("Triggering periodic self-evolution check")
            try:
                result = await self.evolver.evolve()
                await self.telegram.send_message(f"🧬 Auto-evolution:\n{result}")
            except Exception as e:
                logger.error(f"Auto-evolution failed: {e}")

        # ── Periodic status persistence (every 10 beats) ──
        if self.beat_count % 10 == 0:
            await self._persist_state()

        # ── Log heartbeat ──
        if self.beat_count % 20 == 0:
            uptime = int(time.time() - self.start_time)
            logger.info(
                f"💓 Beat #{self.beat_count} | uptime={uptime}s | "
                f"pending_tasks={self.task_engine.pending_count}"
            )

    async def _persist_state(self):
        """Save current state to disk for crash recovery."""
        state = {
            "beat_count": self.beat_count,
            "start_time": self.start_time,
            "tasks": {
                tid: {
                    "title": t.title,
                    "status": t.status.value,
                    "result": t.result[:500],
                    "error": t.error[:500],
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
            f"🐣 Cradle Agent Status\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"⏱️ Uptime: {hours}h {minutes}m\n"
            f"💓 Heartbeats: {self.beat_count}\n"
            f"📋 Pending tasks: {self.task_engine.pending_count}\n"
            f"📊 Total tasks: {len(self.task_engine.tasks)}\n"
            f"🧬 Evolutions: {self.evolver.evolution_count}\n"
        )
