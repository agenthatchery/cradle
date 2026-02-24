"""Self-evolution engine — the agent improves its own code.

Flow:
1. Analyze current source code with Gemini
2. Generate improvement proposal
3. Test in sandbox
4. If tests pass: git branch → commit → merge → watchdog restarts container
"""

import logging
import os
import time
from typing import Optional

from cradle.config import Config
from cradle.llm_router import LLMRouter
from cradle.sandbox import Sandbox
from cradle.github_client import GitHubClient
from cradle.memory import Memory

logger = logging.getLogger(__name__)


class Evolver:
    """Self-evolution engine for the Cradle agent."""

    def __init__(
        self,
        config: Config,
        llm: LLMRouter,
        sandbox: Sandbox,
        github: GitHubClient,
        memory: Memory,
    ):
        self.config = config
        self.llm = llm
        self.sandbox = sandbox
        self.github = github
        self.memory = memory
        self.evolution_count = 0

    async def evolve(self) -> str:
        """Run one evolution cycle. Returns a summary of what happened."""
        self.evolution_count += 1
        branch_name = f"evolve-{self.evolution_count}-{int(time.time())}"
        logger.info(f"Evolution cycle #{self.evolution_count} starting on branch {branch_name}")

        try:
            # Step 1: Read current source code
            source_files = await self._read_source()
            if not source_files:
                return "❌ Evolution failed: could not read source files"

            # Step 2: Ask LLM for improvement
            proposal = await self._propose_improvement(source_files)
            if not proposal:
                return "🤷 No improvements proposed this cycle"

            # Step 3: Test the proposed changes in sandbox
            test_result = await self._test_proposal(proposal)
            if not test_result:
                return f"⚠️ Proposed changes failed testing:\n{proposal.get('description', '')}"

            # Step 4: Push to GitHub branch and merge
            files_to_push = proposal.get("files", {})
            if not files_to_push:
                return "🤷 No file changes in proposal"

            # Create branch
            await self.github.create_branch(branch_name)

            # Push files
            commit_msg = f"🧬 Evolution #{self.evolution_count}: {proposal.get('description', 'improvement')}"
            pushed = await self.github.push_files(files_to_push, branch_name, commit_msg)

            if not pushed:
                return "❌ Failed to push changes to GitHub"

            # Merge
            merged = await self.github.merge_branch(branch_name, message=commit_msg)
            if not merged:
                return "❌ Failed to merge evolution branch"

            # Clean up branch
            await self.github.delete_branch(branch_name)

            # Store the evolution as a memory
            await self.memory.store(
                f"evolution:{self.evolution_count}",
                proposal.get("description", ""),
                tags=["evolution"],
            )

            return (
                f"✅ Evolution #{self.evolution_count} complete!\n"
                f"📝 {proposal.get('description', '')}\n"
                f"📂 Files changed: {', '.join(files_to_push.keys())}\n"
                f"🔄 Watchdog will restart container with new code."
            )

        except Exception as e:
            logger.error(f"Evolution failed: {e}", exc_info=True)
            return f"❌ Evolution failed: {e}"

    async def _read_source(self) -> dict[str, str]:
        """Read all Python source files from the cradle package."""
        source_dir = os.path.join(os.path.dirname(__file__))
        files = {}

        for filename in os.listdir(source_dir):
            if filename.endswith(".py"):
                filepath = os.path.join(source_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        files[f"cradle/{filename}"] = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {filepath}: {e}")

        # Also read top-level files
        project_root = os.path.dirname(source_dir)
        for filename in ["requirements.txt", "Dockerfile", "docker-compose.yml"]:
            filepath = os.path.join(project_root, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        files[filename] = f.read()
                except Exception:
                    pass

        return files

    async def _propose_improvement(self, source_files: dict[str, str]) -> Optional[dict]:
        """Ask the LLM to propose an improvement to the codebase."""
        # Get past learnings for context
        learnings = await self.memory.get_learnings()
        learnings_text = "\n".join(f"- {l}" for l in learnings[-10:]) if learnings else "None yet"

        system = """You are Cradle's self-evolution engine. Analyze the source code and propose ONE specific, testable improvement.

Focus on:
- Bug fixes or error handling improvements
- New capabilities (tools, skills)
- Performance or token efficiency optimizations
- Better error messages or logging
- Code clarity and documentation

Respond with JSON:
{
  "description": "Brief description of the change",
  "files": {"path/to/file.py": "full new file content"},
  "test_code": "Python code to test the change works",
  "risk": "low|medium|high"
}

IMPORTANT:
- Only propose LOW RISK changes for now
- Include the COMPLETE file content for changed files
- Test code should be self-contained and exit 0 on success
- Do NOT change config.py or main.py (too risky for self-modification)"""

        # Build source summary (truncate to avoid huge prompts)
        source_summary = ""
        for path, content in sorted(source_files.items()):
            lines = content.split("\n")
            if len(lines) > 100:
                content = "\n".join(lines[:100]) + f"\n... ({len(lines) - 100} more lines)"
            source_summary += f"\n### {path}\n```python\n{content}\n```\n"

        prompt = f"""# Current source code:
{source_summary}

# Previous learnings:
{learnings_text}

# Evolution count: {self.evolution_count}

Propose one improvement. Focus on making the agent more capable and robust."""

        try:
            response = await self.llm.complete(prompt, system=system, max_tokens=8192)
            text = response.content

            # Parse JSON
            import json
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            proposal = json.loads(text.strip())
            if proposal.get("risk", "high") == "high":
                logger.warning("Rejecting high-risk evolution proposal")
                return None

            return proposal
        except Exception as e:
            logger.error(f"Failed to generate evolution proposal: {e}")
            return None

    async def _test_proposal(self, proposal: dict) -> bool:
        """Test the proposed changes in a sandbox."""
        test_code = proposal.get("test_code", "")
        if not test_code:
            logger.warning("No test code in proposal — skipping")
            return True  # Accept if no tests needed

        result = await self.sandbox.run_python(test_code, timeout=30, network=False)

        if result.success:
            logger.info("Evolution proposal passed tests")
            return True
        else:
            logger.warning(f"Evolution proposal failed tests: {result.stderr}")
            return False
