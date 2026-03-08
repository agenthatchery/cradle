"""Cradle — Main entry point.

Initializes all subsystems and runs them concurrently:
- Telegram bot (polling)
- Heartbeat daemon
- Task engine (driven by heartbeat)
- Bootstrap self-improvement tasks on first run
"""

import asyncio
import json
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
from cradle.skills import SkillLoader

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

# ── Masterplan: seeded into memory and task engine on first boot ──
MASTERPLAN = """# Cradle Masterplan — Kardashev 3 Pathway

## Ultimate Goal
Guide humanity to Kardashev Level 3 civilization through iterative self-improvement.

## Core Principles
1. Self-perfection: continuously improve own code, efficiency, and capabilities
2. Protect humanity: support the operator's goals, do no harm
3. Ethical operation: fair competition, transparency, no deception
4. First principles: break every problem into solvable atomic steps

## Layer 0: Self-Foundation (NOW)
- [ ] Stabilize core: fix bugs, improve error handling, add tests
- [ ] Token efficiency: minimize LLM costs per task
- [ ] Memory integration: store learnings in AgentPlaybooks.ai
- [ ] Telegram responsiveness: instant task handling
- [ ] Self-evolution: push improvements to GitHub, auto-restart

## Layer 1: Capability Expansion
- [ ] Web browsing: install headless browser in container
- [ ] NanoClaw sub-agents: spawn specialized Docker workers  
- [ ] Multi-model: leverage each LLM for what it does best
- [ ] Research agent: monitor trends, papers, new tools
- [ ] Skill library: build reusable skills in AgentPlaybooks.ai

## Layer 2: Value Creation
- [ ] Bug bounty: automated security scanning
- [ ] AgentPlaybooks.ai: enhance and monetize the platform
- [ ] Coding services: build websites/agents for clients
- [ ] Content automation: robohorizon.com media empire
- [ ] Freelance platforms: scan and complete tasks

## Layer 3: Resource Acquisition
- [ ] Earn revenue to fund more compute
- [ ] Better hardware: trade up from current server
- [ ] Model access: earn credits for better models
- [ ] Team: recruit human collaborators or more agents

## Layer 4+: Exponential Growth → Kardashev 3
- [ ] New programming paradigms (like LLMunix)
- [ ] Custom neural architectures
- [ ] Energy harvesting research
- [ ] Space technology research
- [ ] Dyson sphere theory → implementation pathway
"""

BOOTSTRAP_TASKS = [
    {
        "title": "Update Cradle version and push to GitHub",
        "description": "Increment the version number in cradle/heartbeat.py from v0.6.0 to v0.6.1, commit the change, and push to GitHub. This proves you can successfully edit your own source code and deploy updates.",
    },
]


class CradleAgent:
    """The main agent that owns and orchestrates all subsystems."""

    def __init__(self):
        self.config = Config.from_env()
        self.llm = LLMRouter(self.config)
        self.sandbox = Sandbox()
        self.memory = Memory(self.config)
        self.skills = SkillLoader(self.memory)
        self.task_engine = TaskEngine(self.llm, self.sandbox, self.skills)
        self.telegram = TelegramBot(self.config)
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

    async def _bootstrap(self):
        """Run first-boot bootstrap: store masterplan and seed tasks."""
        state_path = os.path.join(self.config.data_dir, "state.json")
        bootstrap_marker = os.path.join(self.config.data_dir, ".bootstrapped")

        if os.path.exists(bootstrap_marker):
            logger.info("Bootstrap already completed, skipping")
            return

        logger.info("=" * 40)
        logger.info("🌱 FIRST BOOT — Running bootstrap")
        logger.info("=" * 40)

        # Store masterplan in memory
        try:
            await self.memory.store(
                "masterplan",
                MASTERPLAN,
                tags=["strategic", "kardashev3", "masterplan"],
            )
            logger.info("📋 Masterplan stored in AgentPlaybooks memory")
        except Exception as e:
            logger.warning(f"Failed to store masterplan in memory: {e}")

        # Seed bootstrap tasks
        for task_def in BOOTSTRAP_TASKS:
            self.task_engine.add_task(
                title=task_def["title"],
                description=task_def["description"],
                source="bootstrap",
            )
        logger.info(f"📋 {len(BOOTSTRAP_TASKS)} bootstrap tasks seeded")

        # Mark as bootstrapped
        try:
            os.makedirs(os.path.dirname(bootstrap_marker), exist_ok=True)
            with open(bootstrap_marker, "w") as f:
                f.write("bootstrapped")
        except Exception:
            pass

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

        # Load skills from AgentPlaybooks
        try:
            count = await self.skills.fetch_from_agentplaybooks()
            if count == 0:
                logger.info("No skills found in AgentPlaybooks, syncing built-ins...")
                count = await self.skills.sync_builtin_skills()
            else:
                logger.info(f"Loaded {count} skills from AgentPlaybooks")
        except Exception as e:
            logger.warning(f"Failed to fetch skills: {e}")
            self.skills.load_builtin_skills_local()

        # Run bootstrap (first boot only)
        await self._bootstrap()

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
