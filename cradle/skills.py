"""Skills — SKILL.md-compatible capabilities for the Cradle agent.

Skills follow the Anthropic open standard (used by NanoClaw, Claude Code, Cursor):
- YAML frontmatter with name, description
- Markdown body with detailed instructions
- Stored in AgentPlaybooks.ai for persistent, editable management
- Loaded dynamically and injected into task context

The agent loads skill name+description on every task, and loads full
instructions only when the skill is relevant (progressive disclosure).
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Built-in skills (also uploaded to AgentPlaybooks on boot) ──
# Format: (name, description, content as SKILL.md markdown)

BUILTIN_SKILLS = [
    {
        "name": "web_search",
        "description": "Search the web for information. Use for research, current events, documentation lookups, and any question requiring up-to-date data.",
        "content": """\
---
name: web_search
description: Search the web using Google Custom Search API or DuckDuckGo fallback.
---

# Web Search Skill

Use this skill whenever you need to look up information on the web.

## How to Use

Write Python code that calls the web search function:

```python
import os, urllib.parse, urllib.request, json

def web_search(query: str, num_results: int = 5) -> list[dict]:
    \"\"\"Search the web. Returns list of {title, url, snippet}.\"\"\"
    # Try Google Custom Search API first
    cse_key = os.getenv("GOOGLE_CSE_KEY", "")
    cse_id = os.getenv("GOOGLE_CSE_ID", "")
    if cse_key and cse_id:
        url = (
            f"https://www.googleapis.com/customsearch/v1"
            f"?key={cse_key}&cx={cse_id}"
            f"&q={urllib.parse.quote(query)}&num={num_results}"
        )
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
            return [
                {"title": i["title"], "url": i["link"], "snippet": i.get("snippet", "")}
                for i in data.get("items", [])
            ]
        except Exception as e:
            print(f"Google CSE failed: {e}, falling back to DuckDuckGo")

    # Fallback: DuckDuckGo Lite (no API key needed)
    import html, re
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", errors="replace")
        results = []
        for m in re.finditer(
            r'class="result__title".*?href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</span>',
            body, re.DOTALL
        )[:num_results]:
            results.append({
                "title": html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip(),
                "url": m.group(1),
                "snippet": html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip(),
            })
        return results
    except Exception as e:
        return [{"title": "Search failed", "url": "", "snippet": str(e)}]

# Example usage:
results = web_search("NanoClaw agent framework SKILL.md")
for r in results:
    print(f"- {r['title']}\\n  {r['url']}\\n  {r['snippet']}\\n")
```

## Key Notes
- Set `needs_network: true` in your task plan when using this skill
- Google CSE gives better results but needs env vars GOOGLE_CSE_KEY + GOOGLE_CSE_ID
- DuckDuckGo Lite works without any API keys as a fallback
- Always print results to stdout so the agent can read them
""",
    },
    {
        "name": "github_cli",
        "description": "Read files from GitHub repos, clone repositories, commit and push code changes. Use for code downloads, uploads, and version control operations.",
        "content": """\
---
name: github_cli
description: Interact with GitHub using git CLI and GitHub API. Clone, read, commit, push.
---

# GitHub CLI Skill

Use this skill for all GitHub operations: reading files, cloning repos, pushing changes.

## Available Operations

### 1. Read a file from GitHub (no clone needed)
```python
import os, urllib.request, json, base64

def github_read_file(repo: str, path: str, ref: str = "main") -> str:
    \"\"\"Read a file from a GitHub repo via API.\"\"\"
    token = os.getenv("GITHUB_PAT", "")
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return base64.b64decode(data["content"]).decode("utf-8")

content = github_read_file("agenthatchery/cradle", "README.md")
print(content[:2000])
```

### 2. Clone a repo and read files
```bash
#!/bin/bash
git clone https://$GITHUB_PAT@github.com/OWNER/REPO.git /workspace/repo
cat /workspace/repo/README.md
```

### 3. Commit and push a change
```python
import os, subprocess

def git_push(repo_path: str, files: dict[str, str], message: str, branch: str = "main"):
    \"\"\"Write files, commit, and push to GitHub.\"\"\"
    for path, content in files.items():
        full_path = os.path.join(repo_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
    
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    subprocess.run(["git", "-C", repo_path, "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", repo_path, "commit", "-m", message], check=True, env=env)
    subprocess.run(["git", "-C", repo_path, "push", "origin", branch], check=True, env=env)
    print(f"Pushed: {message}")
```

## Key Notes
- `set needs_network: true` in task plan
- The container has `git` installed and `GITHUB_PAT` env var
- Always clone to `/tmp/` or `/workspace/` paths
""",
    },
    {
        "name": "spawn_agent",
        "description": "Clone a GitHub repo and run it as an ephemeral Docker sub-agent (NanoClaw pattern). Use for running specialized agents, healing-agent, OpenCode instances, or any containerized AI tool.",
        "content": """\
---
name: spawn_agent
description: Spawn a sub-agent from a GitHub repository using Docker. NanoClaw-style agent spawning.
---

# Spawn Agent Skill

Use this skill to run another agent or tool from a GitHub repository.

## How It Works (NanoClaw Pattern)
1. Clone the target repo to a temp directory
2. Build or pull its Docker image
3. Run the container with mounted input/output volumes
4. Read and return the results

## Python Implementation
```python
import os, subprocess, tempfile, shutil, json

def spawn_agent(
    github_repo: str,
    command: list[str],
    input_data: str = "",
    image: str = None,
    timeout: int = 120,
) -> dict:
    \"\"\"
    Clone a GitHub repo and run it as a Docker sub-agent.
    
    Args:
        github_repo: e.g. "matebenyovszky/healing-agent"
        command: command to run inside container, e.g. ["python", "main.py"]
        input_data: optional input to write to /workspace/input.txt
        image: Docker image name (if None, attempts to build from Dockerfile)
        timeout: max seconds to wait
    
    Returns: {"success": bool, "stdout": str, "stderr": str}
    \"\"\"
    tmpdir = tempfile.mkdtemp(prefix="cradle_agent_")
    try:
        token = os.getenv("GITHUB_PAT", "")
        clone_url = f"https://{token}@github.com/{github_repo}.git"
        repo_dir = os.path.join(tmpdir, "repo")
        
        # Clone
        result = subprocess.run(
            ["git", "clone", "--depth=1", clone_url, repo_dir],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return {"success": False, "stdout": "", "stderr": f"Clone failed: {result.stderr}"}
        
        # Write input if provided
        results_dir = os.path.join(tmpdir, "results")
        os.makedirs(results_dir, exist_ok=True)
        if input_data:
            with open(os.path.join(results_dir, "input.txt"), "w") as f:
                f.write(input_data)
        
        # Build image if Dockerfile exists and no image specified
        if image is None and os.path.exists(os.path.join(repo_dir, "Dockerfile")):
            image = f"cradle-subagent-{github_repo.replace('/', '-').lower()}"
            build = subprocess.run(
                ["docker", "build", "-t", image, repo_dir],
                capture_output=True, text=True, timeout=120
            )
            if build.returncode != 0:
                # Fallback to python image
                image = "python:3.12-slim"
        elif image is None:
            image = "python:3.12-slim"
        
        # Run the sub-agent
        docker_cmd = [
            "docker", "run", "--rm",
            "--memory=512m", "--cpus=2",
            "-v", f"{repo_dir}:/workspace",
            "-v", f"{results_dir}:/results",
            "-w", "/workspace",
            "--env", f"GITHUB_PAT={token}",
        ] + [image] + command
        
        proc = subprocess.run(
            docker_cmd, capture_output=True, text=True, timeout=timeout
        )
        
        # Check for output file
        output_file = os.path.join(results_dir, "output.txt")
        output_extra = ""
        if os.path.exists(output_file):
            with open(output_file) as f:
                output_extra = "\\n[output.txt]:\\n" + f.read()
        
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout[:10000] + output_extra,
            "stderr": proc.stderr[:3000],
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# Example: run healing-agent on current code
result = spawn_agent(
    "matebenyovszky/healing-agent",
    ["python", "main.py", "--target", "/workspace"],
)
print(f"Success: {result['success']}")
print(result["stdout"][:3000])
```

## Key Notes
- Always `set needs_network: true` (clone requires internet)
- The container has Docker socket mounted — Docker-in-Docker works
- Results go to stdout or `/results/output.txt`
- Timeout default is 120s — increase for heavy tasks
""",
    },
]


class SkillLoader:
    """Loads skills from AgentPlaybooks and provides them to the task engine."""

    def __init__(self, memory):
        self.memory = memory
        self._cache: dict[str, dict] = {}  # name -> {description, content}
        self._loaded = False

    async def sync_builtin_skills(self) -> int:
        """Upload all built-in skills to AgentPlaybooks. Returns count uploaded."""
        count = 0
        for skill in BUILTIN_SKILLS:
            ok = await self.memory.store_skill(
                name=skill["name"],
                content=skill["content"],
                description=skill["description"],
            )
            if ok:
                # Cache locally too
                self._cache[skill["name"]] = {
                    "description": skill["description"],
                    "content": skill["content"],
                }
                count += 1
                logger.info(f"Skill synced to AgentPlaybooks: {skill['name']}")
            else:
                logger.warning(f"Failed to sync skill: {skill['name']}")
        self._loaded = True
        return count

    def load_builtin_skills_local(self):
        """Load built-in skills from local definitions (no network)."""
        for skill in BUILTIN_SKILLS:
            self._cache[skill["name"]] = {
                "description": skill["description"],
                "content": skill["content"],
            }
        self._loaded = True

    async def fetch_from_agentplaybooks(self) -> int:
        """Fetch skills from AgentPlaybooks (merges with local cache)."""
        try:
            remote_skills = await self.memory.list_skills()
            count = 0
            for s in remote_skills or []:
                name = s.get("name", "")
                if name and name not in self._cache:
                    self._cache[name] = {
                        "description": s.get("description", ""),
                        "content": s.get("content", ""),
                    }
                    count += 1
            if count:
                logger.info(f"Fetched {count} extra skills from AgentPlaybooks")
            return count
        except Exception as e:
            logger.warning(f"Could not fetch skills from AgentPlaybooks: {e}")
            return 0

    def get_skills_summary(self) -> str:
        """Short list of available skills for system prompt injection."""
        if not self._cache:
            return ""
        lines = ["## Available Skills (use these in your code)"]
        for name, skill in self._cache.items():
            desc = skill["description"][:120]
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)

    def get_skill_content(self, name: str) -> Optional[str]:
        """Get the full SKILL.md content for a specific skill."""
        skill = self._cache.get(name)
        return skill["content"] if skill else None

    def get_relevant_skills(self, task_title: str, task_description: str) -> str:
        """Return full content of skills relevant to this task."""
        text = (task_title + " " + task_description).lower()
        relevant = []

        keywords = {
            "web_search": ["search", "web", "internet", "research", "find", "look up", "browse", "google", "url", "http"],
            "github_cli": ["github", "git", "repo", "clone", "commit", "push", "pull", "code", "file", "repository"],
            "spawn_agent": ["spawn", "sub-agent", "agent", "docker", "nanoclaw", "run", "execute", "healing"],
        }

        for name, kws in keywords.items():
            if any(kw in text for kw in kws) and name in self._cache:
                relevant.append(self._cache[name]["content"])

        return "\n\n---\n\n".join(relevant) if relevant else ""
