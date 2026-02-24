"""Heartbeat daemon — the continuous pulse of the Cradle agent.

Runs every N seconds and:
1. Processes ALL pending tasks immediately (not just one)
2. Triggers periodic self-evolution
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

        # Announce on Telegram (best-effort)
        try:
            await self.telegram.send_message(
                f"🐣 Cradle Agent v0.2.0 online!\n"
                f"⏱️ Heartbeat: every {self.interval}s\n"
                f"📋 Pending tasks: {self.task_engine.pending_count}\n"
                f"🤖 Self-evolution active!\n\n"
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

        # ── Process ALL pending tasks (drains the queue) ──
        tasks_processed = 0
        while self.task_engine.pending_count > 0 and tasks_processed < 3:
            # Limit to 3 per beat to avoid blocking too long
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

            # Store reflections
            if task.reflection:
                try:
                    await self.memory.store_reflection(
                        task.id, task.reflection, []
                    )
                except Exception:
                    pass

        if tasks_processed > 0:
            logger.info(f"Processed {tasks_processed} tasks this beat")

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
            "tasks": {
                tid: {
                    "title": t.title,
                    "status": t.status.value,
                    "result": t.result[:500] if t.result else "",
                    "error": t.error[:500] if t.error else "",
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
            f"🐣 Cradle Agent v0.2.0\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"⏱️ Uptime: {hours}h {minutes}m\n"
            f"💓 Heartbeats: {self.beat_count}\n"
            f"📋 Pending tasks: {self.task_engine.pending_count}\n"
            f"📊 Total tasks: {len(self.task_engine.tasks)}\n"
            f"🧬 Evolutions: {self.evolver.evolution_count}\n"
        )
