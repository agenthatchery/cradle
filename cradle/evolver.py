"""Self-evolution engine — the agent improves its own code.

Flow:
1. Read current source from local /app/repo (inside Cradle container)
2. Ask LLM for ONE focused improvement via GitHub API (not sandbox)
3. Push to branch via GitHub API, merge, trigger restart

IMPORTANT: This runs in the Cradle container itself, NOT in the sandbox.
It uses the GitHub REST API (via github_client.py) to push changes,
so there's no need for git CLI or sandbox access.
"""

import json
import logging
import os
import re
import sys
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
            # Step 1: Read current source code from local filesystem
            source_files = self._read_source()
            if not source_files:
                return "❌ Evolution failed: could not read source files"

            # Step 2: Ask LLM for improvement
            proposal = await self._propose_improvement(source_files)
            if not proposal:
                return "🤷 No improvements proposed this cycle"

            description = proposal.get("description", "improvement")
            files_to_push = proposal.get("files", {})
            if not files_to_push:
                return "🤷 No file changes in proposal"

            # Step 3: Validate — don't touch critical files
            PROTECTED = {"cradle/main.py", "cradle/config.py", "cradle/evolver.py",
                         "main.py", "config.py", "evolver.py", "Dockerfile", "entrypoint.sh"}
            for path in list(files_to_push.keys()):
                if path in PROTECTED or os.path.basename(path) in PROTECTED:
                    logger.warning(f"Removing protected file from proposal: {path}")
                    del files_to_push[path]

            if not files_to_push:
                return "🤷 All proposed files are protected — skipping"

            # Step 4: Test the proposed changes in sandbox (if test code provided)
            test_code = proposal.get("test_code", "")
            if test_code:
                test_ok = await self._test_proposal(test_code)
                if not test_ok:
                    # Store the failure as a learning
                    await self.memory.store(
                        key=f"evolution_failure:{self.evolution_count}",
                        value={"description": description, "reason": "test_failed"},
                        tags=["evolution", "failure"],
                        tier="contextual",
                    )
                    return f"⚠️ Proposed changes failed testing: {description}"

            # Step 5: Push to GitHub branch via API and merge
            logger.info(f"Pushing evolution to branch {branch_name}: {description}")

            # Create branch
            branch_ok = await self.github.create_branch(branch_name)
            if not branch_ok:
                return "❌ Failed to create evolution branch"

            # Push files one by one via GitHub API
            commit_msg = f"🧬 Evolution #{self.evolution_count}: {description}"
            pushed = await self.github.push_files(files_to_push, branch_name, commit_msg)

            if not pushed:
                await self.github.delete_branch(branch_name)
                return "❌ Failed to push changes to GitHub"

            # Merge into main
            merged = await self.github.merge_branch(branch_name, message=commit_msg)
            if not merged:
                await self.github.delete_branch(branch_name)
                return "❌ Failed to merge evolution branch"

            # Clean up branch
            await self.github.delete_branch(branch_name)

            # Store the evolution as a memory
            await self.memory.store(
                key=f"evolution:{self.evolution_count}",
                value={
                    "description": description,
                    "files_changed": list(files_to_push.keys()),
                    "branch": branch_name,
                },
                tags=["evolution", "success"],
                tier="longterm",
                priority=80,
            )

            result_msg = (
                f"✅ Evolution #{self.evolution_count} pushed to GitHub!\n"
                f"📝 {description}\n"
                f"📂 Files: {', '.join(files_to_push.keys())}\n"
                f"🔄 Restarting agent with new code..."
            )
            logger.info(result_msg)

            # Trigger restart — entrypoint will git pull and pick up the new code
            logger.info("🔄 Triggering self-restart after evolution (exit code 42)")
            sys.exit(42)

        except SystemExit:
            raise  # Don't catch sys.exit(42)
        except Exception as e:
            logger.error(f"Evolution failed: {e}", exc_info=True)
            return f"❌ Evolution failed: {e}"

    def _read_source(self) -> dict[str, str]:
        """Read all Python source files from the cradle package (local filesystem)."""
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
        for filename in ["requirements.txt", "Dockerfile", "docker-compose.yml",
                         "Dockerfile.sandbox", "entrypoint.sh", "README.md"]:
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
        # Get past learnings and evolution history for context
        learnings = await self.memory.get_learnings()
        learnings_text = "\n".join(f"- {l}" for l in learnings[-10:]) if learnings else "None yet"

        evolution_memories = await self.memory.search(tags=["evolution"])
        past_evolutions = ""
        if evolution_memories:
            for mem in evolution_memories[-5:]:
                val = mem.get("value", {})
                if isinstance(val, dict):
                    past_evolutions += f"- {val.get('description', 'unknown')}\n"

        system = """You are Cradle's self-evolution engine. Analyze the source code and propose ONE specific, testable improvement.

IMPORTANT RULES:
1. Propose EXACTLY ONE change to ONE file (not multiple files)
2. The proposed file must contain the COMPLETE new content — not a diff
3. Only propose LOW or MEDIUM risk changes
4. NEVER modify: main.py, config.py, evolver.py, Dockerfile, entrypoint.sh
5. Focus on changes that make the agent MORE CAPABLE:
   - Better error handling in sandbox.py or task_engine.py
   - New or improved skills in skills.py
   - Better memory usage in heartbeat.py
   - Improved LLM prompt engineering
   - New built-in capabilities

Respond with a SINGLE JSON object (no markdown fences, no commentary before/after):
{"description": "Brief description", "files": {"cradle/filename.py": "full file content"}, "test_code": "python code that exits 0 on success", "risk": "low"}

CRITICAL: Output ONLY the JSON. No ```json fences, no explanation text. Just the raw JSON object."""

        # Build source summary — truncate long files but show structure
        source_summary = ""
        for path, content in sorted(source_files.items()):
            lines = content.split("\n")
            if len(lines) > 80:
                content = "\n".join(lines[:80]) + f"\n... ({len(lines) - 80} more lines)"
            source_summary += f"\n### {path}\n```python\n{content}\n```\n"

        prompt = f"""# Current source code:
{source_summary}

# Previous learnings:
{learnings_text}

# Past evolutions:
{past_evolutions or "None yet"}

# Evolution count: {self.evolution_count}

Propose ONE improvement. Output ONLY a JSON object."""

        try:
            response = await self.llm.complete(prompt, system=system, max_tokens=8192)
            raw_text = response.content
            logger.debug(f"Evolution LLM raw response ({len(raw_text)} chars): {raw_text[:500]}")

            # Robust JSON extraction
            proposal = self._extract_json(raw_text)
            if not proposal:
                logger.error(f"Failed to extract JSON from evolution response. First 500 chars: {raw_text[:500]}")
                return None

            risk = proposal.get("risk", "high")
            if risk == "high":
                logger.warning("Rejecting high-risk evolution proposal")
                return None

            # Validate structure
            if "files" not in proposal or not isinstance(proposal["files"], dict):
                logger.warning("Proposal missing 'files' dict")
                return None

            if len(proposal["files"]) > 2:
                logger.warning(f"Proposal modifies {len(proposal['files'])} files — trimming to 1")
                first_key = next(iter(proposal["files"]))
                proposal["files"] = {first_key: proposal["files"][first_key]}

            return proposal
        except Exception as e:
            logger.error(f"Failed to generate evolution proposal: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[dict]:
        """Robustly extract a JSON object from LLM output."""
        # Strategy 1: Try direct parse
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

        # Strategy 3: Find the first { and match to last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # Strategy 4: Try to fix common issues (trailing commas, unescaped newlines in strings)
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            # Remove trailing commas before } or ]
            candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        return None

    async def _test_proposal(self, test_code: str) -> bool:
        """Test the proposed changes in a sandbox."""
        if not test_code.strip():
            return True  # Accept if no tests needed

        result = await self.sandbox.run_python(test_code, timeout=30, network=False)

        if result.success:
            logger.info("Evolution proposal passed tests")
            return True
        else:
            logger.warning(f"Evolution proposal failed tests: {result.stderr[:500]}")
            return False
