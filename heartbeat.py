import asyncio
import logging
import time
import json
import os
import cradle # Import the cradle package to access __version__
from typing import Optional

from cradle.config import Config
from cradle.task_engine import TaskEngine
from cradle.evolver import Evolver
from cradle.memory import Memory
from cradle.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

# Get the current Cradle version
from cradle import __version__ as CRADLE_CURRENT_VERSION


# Self-improvement task templates - the agent cycles through these
SELF_IMPROVEMENT_TASKS = [
    {
        "title": "Update Cradle version and push to GitHub",
        "description": f"Increment the version number in cradle/__init__.py from {CRADLE_CURRENT_VERSION} to the next patch version (e.g., from 0.1.0 to 0.1.1), commit the change, and push to GitHub. This proves you can successfully edit your own source code and deploy updates.",
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
            "periodically summarizes and condenses older memories into a more "
            "efficient format, storing them in AgentPlaybooks. This will improve "
            "retrieval speed and reduce storage costs for long-term knowledge."
        ),
    },
    {
        "title": "Develop an LLM-powered code review skill",
        "description": (
            "Create a new skill that takes a file path and an optional diff as input. "
            "It should use an LLM (preferably Gemini 3.1 Pro) to perform a "
            "thorough code review, identifying potential bugs, security vulnerabilities, "
            "performance issues, and style guide violations. The output should be a "
            "JSON object with actionable recommendations."
        ),
    },
    {
        "title": "Integrate an external tool: 'shellcheck' for bash scripts",
        "description": (
            "Add a new skill 'run_shellcheck' that takes a bash script content as input. "
            "It should use the sandbox to execute 'shellcheck' on the script and return "
            "its findings. Update `task_engine.py` to use this skill automatically "
            "before executing any generated bash script, improving script reliability."
        ),
    },
    {
        "title": "Improve `sandbox.py` with resource limits (CPU/Memory)",
        "description": (
            "Modify the `sandbox.py` module to include Docker resource limits "
            "(e.g., `--cpus`, `--memory`) when spawning containers. "
            "Make these limits configurable via `config.py`. "
            "This prevents runaway processes from consuming all host resources."
        ),
    },
    {
        "title": "Add a `/plan` command to TelegramBot for task tree visualization",
        "description": (
            "Implement a new `/plan` command in `telegram_bot.py` that, when called, "
            "queries the `task_engine.py` to get the current hierarchical task tree. "
            "The bot should then format this tree into a human-readable string and "
            "send it back to the user, providing an overview of ongoing work."
        ),
    },
    {
        "title": "Implement a 'read_webpage' skill for information gathering",
        "description": (
            "Create a new skill `read_webpage' that takes a URL as input. "
            "It should use `httpx` or a similar library to fetch the content of the URL, "
            "parse it (e.g., with BeautifulSoup if available in sandbox), "
            "and return a concise summary or key information. "
            "Ensure it handles common errors like network issues or timeouts."
        ),
    },
    {
        "title": "Refactor `llm_router.py` to support streaming responses",
        "description": (
            "Modify `llm_router.py` to allow for streaming LLM responses, "
            "especially for providers that support it (e.g., OpenAI, Gemini). "
            "This will improve perceived latency and allow for partial results "
            "to be processed by the `task_engine.py` more quickly. "
            "Update the `complete` method to return an async generator."
        ),
    },
]

class Heartbeat:
    """Heartbeat daemon - the continuous pulse of the Cradle agent."""

    def __init__(
        self,
        config: Config,
        task_engine: TaskEngine,
        evolver: Evolver,
        memory: Memory,
        telegram_bot: TelegramBot,
    ):
        self.config = config
        self.task_engine = task_engine
        self.evolver = evolver
        self.memory = memory
        self.telegram_bot = telegram_bot
        self._running = False
        self.beat_count = 0
        self.start_time = time.time()
        self._evolution_interval = 3600 * 6  # Trigger evolution every 6 hours
        self._last_evolution_time = time.time()
        self._self_improvement_task_idx = 0

        # Bootstrap initial self-improvement tasks if no tasks exist
        if self.task_engine.pending_count == 0:
            logger.info("Bootstrapping initial self-improvement tasks...")
            for task_data in SELF_IMPROVEMENT_TASKS:
                self.task_engine.add_task(
                    title=task_data["title"],
                    description=task_data["description"],
                    source="self",
                )

    async def start(self):
        """Start the heartbeat loop. Always BLOCKS."""
        if self._running:
            logger.warning("Heartbeat already running.")
            return
        self._running = True
        logger.info(f"Heartbeat started (v{CRADLE_CURRENT_VERSION})")
        
        try:
            await self.telegram_bot.send_message(f"🐣 Cradle Agent v{CRADLE_CURRENT_VERSION} online!")
        except Exception:
            pass

        await self._run_loop()

    async def stop(self):
        """Stop the heartbeat loop."""
        self._running = False
        logger.info("Heartbeat stopped.")

    async def _run_loop(self):
        """The main heartbeat loop."""
        while self._running:
            try:
                await self._pulse()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in heartbeat pulse: {e}", exc_info=True)
            await asyncio.sleep(self.config.heartbeat_interval)

    async def _pulse(self):
        """Execute one heartbeat pulse: process tasks, maybe evolve."""
        self.beat_count += 1
        logger.debug(f"Heartbeat pulse #{self.beat_count}...")

        # Step 1: Process all pending tasks
        while self.task_engine.pending_count > 0:
            await self.task_engine.process_next()

        # Step 2: Periodic Health Check (every 50 beats)
        if self.beat_count % 50 == 0:
            await self._check_memory_health()

        # Step 3: Auto-generate improvement tasks if idle
        if self.task_engine.pending_count == 0:
            await self._propose_self_improvement_task()

        # Step 4: Trigger periodic self-evolution
        if time.time() - self._last_evolution_time > self._evolution_interval:
            logger.info("Periodic self-evolution triggered.")
            summary = await self.evolver.evolve()
            if self.telegram_bot.is_active:
                await self.telegram_bot.send_message(f"🧬 Evolution complete: {summary}")
            self._last_evolution_time = time.time()

    async def _check_memory_health(self):
        """Prune old memories and deduplicate skills."""
        logger.info("🩺 Running periodic memory health check...")
        try:
            # 1. Prune reflections
            reflections = await self.memory.search("reflection", limit=1000)
            if len(reflections) > 50:
                to_delete = sorted(reflections, key=lambda x: x.get('created_at', ''), reverse=True)[50:]
                for m in to_delete:
                    await self.memory.forget(m['id'])
                logger.info(f"🗑️ Pruned {len(to_delete)} old reflection memories")


            # 2. Deduplicate skill tools
            tools = await self.memory.list_tools()
            skill_tools = [t for t in tools if t.get('name', '').startswith('skill_')]
            
            seen_names = set()
            duplicates = []
            for t in skill_tools:
                name = t['name']
                if name in seen_names:
                    duplicates.append(t)
                else:
                    seen_names.add(name)
            
            if duplicates:
                logger.info(f"🔍 Found {len(duplicates)} duplicate skill tools. Cleaning up...")
                for d in duplicates:
                    base_name = d['name'].replace('skill_', '')
                    await self.memory.delete_skill(base_name)
                logger.info(f"✨ Purged {len(duplicates)} duplicate skill tools")

        except Exception as e:
            logger.error(f"Failed memory health check: {e}")

    async def _propose_self_improvement_task(self):
        """Propose a new self-improvement task if none are pending."""
        if self.task_engine.pending_count > 0:
            return
        
        task_data = SELF_IMPROVEMENT_TASKS[self._self_improvement_task_idx]
        self.task_engine.add_task(
            title=task_data["title"],
            description=task_data["description"],
            source="self",
        )
        logger.info(f"Added self-improvement task: {task_data['title']}")

        self._self_improvement_task_idx = (self._self_improvement_task_idx + 1) % len(SELF_IMPROVEMENT_TASKS)
