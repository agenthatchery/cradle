"""Cradle — Main entry point.

Initializes all subsystems and runs them concurrently:
- Telegram bot (polling)
- Heartbeat daemon
- Task engine (driven by heartbeat)
"""

import asyncio
import logging
import os
import signal
import sys

from cradle.config import Config
from cradle.llm_router import LLMRouter
from cradle.sandbox import Sandbox
from cradle.task_engine import TaskEngine
from cradle.telegram_bot import TelegramBot
from cradle.memory import Memory
from cradle.github_client import GitHubClient
from cradle.evolver import Evolver
from cradle.heartbeat import Heartbeat

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("cradle")

# Suppress noisy HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


class CradleAgent:
    """The main agent that owns and orchestrates all subsystems."""

    def __init__(self):
        self.config = Config.from_env()
        self.llm = LLMRouter(self.config)
        self.sandbox = Sandbox()
        self.task_engine = TaskEngine(self.llm, self.sandbox)
        self.telegram = TelegramBot(self.config)
        self.memory = Memory(self.config)
        self.github = GitHubClient(self.config)
        self.evolver = Evolver(
            self.config, self.llm, self.sandbox, self.github, self.memory
        )
        self.heartbeat = Heartbeat(
            self.config, self.task_engine, self.evolver, self.memory, self.telegram
        )

        # Wire up Telegram callbacks
        self.telegram.on_task = self._handle_task
        self.telegram.on_status = self._handle_status
        self.telegram.on_evolve = self._handle_evolve
        self.telegram.on_cost = self._handle_cost

    async def _handle_task(self, description: str) -> str:
        """Handle a task submitted via Telegram."""
        task = self.task_engine.add_task(title=description, source="user")
        # Process immediately (don't wait for heartbeat)
        result = await self.task_engine.process_next()
        if result:
            if result.result:
                return f"✅ [{result.id}] {result.title}\n\n{result.result[:3500]}"
            elif result.error:
                return f"❌ [{result.id}] {result.title}\n\n{result.error[:3500]}"
            else:
                return f"⏳ [{result.id}] {result.title} — status: {result.status.value}"
        return f"⏳ Task queued: {description}"

    async def _handle_status(self) -> str:
        """Handle /status command."""
        status = self.heartbeat.get_status()
        status += "\n" + self.task_engine.get_status_summary()
        status += "\n\n" + self.llm.get_stats_summary()
        return status

    async def _handle_evolve(self) -> str:
        """Handle /evolve command."""
        return await self.evolver.evolve()

    async def _handle_cost(self) -> str:
        """Handle /cost command."""
        return self.llm.get_stats_summary()

    async def startup(self):
        """Initialize everything."""
        logger.info("=" * 60)
        logger.info("🐣 CRADLE AGENT STARTING")
        logger.info("=" * 60)

        # Validate config
        warnings = self.config.validate()
        for w in warnings:
            logger.warning(f"Config: {w}")

        # Log provider info
        for p in self.config.llm_providers:
            logger.info(f"LLM provider: {p.name} ({p.model}) priority={p.priority}")

        # Ensure data directory exists
        os.makedirs(self.config.data_dir, exist_ok=True)

        # Add file handler for persistent logging
        log_dir = os.environ.get("LOG_DIR", "/app/logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(log_dir, "cradle.log"))
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(file_handler)

        # Ensure GitHub repo exists
        if self.config.github_pat:
            await self.github.ensure_repo_exists()

    async def run(self):
        """Run all subsystems concurrently."""
        await self.startup()

        # Start Telegram bot
        await self.telegram.start()

        # Run heartbeat (this blocks forever)
        try:
            await self.heartbeat.start()
        except asyncio.CancelledError:
            logger.info("Cradle shutting down...")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Clean shutdown of all subsystems."""
        logger.info("Shutting down...")
        await self.heartbeat.stop()
        await self.telegram.stop()
        await self.llm.close()
        await self.memory.close()
        await self.github.close()
        logger.info("Cradle shut down complete.")


def main():
    """Entry point."""
    agent = CradleAgent()

    # Handle signals for graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler():
        logger.info("Signal received, shutting down...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
