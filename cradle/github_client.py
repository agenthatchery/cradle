"""GitHub client for self-evolution — manages branches, commits, and merges.

The agent uses this to push improvements to its own codebase.
"""

import base64
import logging
from typing import Optional

import httpx

from cradle.config import Config

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubClient:
    """Minimal GitHub API client for self-evolution workflows."""

    def __init__(self, config: Config):
        self.config = config
        self.org = config.github_org
        self.repo = config.github_repo
        self.pat = config.github_pat
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self.pat}",
            "Accept": "application/vnd.github.v3+json",
        }

    @property
    def repo_url(self) -> str:
        return f"{GITHUB_API}/repos/{self.org}/{self.repo}"

    # ── Repository Operations ──

    async def ensure_repo_exists(self) -> bool:
        """Check if the repo exists, create if not."""
        try:
            resp = await self._client.get(self.repo_url, headers=self._headers())
            if resp.status_code == 200:
                logger.info(f"Repo {self.org}/{self.repo} exists")
                return True

            if resp.status_code == 404:
                return await self._create_repo()

            resp.raise_for_status()
            return False
        except Exception as e:
            logger.error(f"Failed to check repo: {e}")
            return False

    async def _create_repo(self) -> bool:
        """Create the repo in the organization."""
        try:
            url = f"{GITHUB_API}/orgs/{self.org}/repos"
            body = {
                "name": self.repo,
                "description": "🐣 Cradle — Self-Evolving Agent System",
                "private": False,
                "auto_init": True,
            }
            resp = await self._client.post(url, json=body, headers=self._headers())
            resp.raise_for_status()
            logger.info(f"Created repo {self.org}/{self.repo}")
            return True
        except Exception as e:
            logger.error(f"Failed to create repo: {e}")
            return False

    # ── File Operations ──

    async def get_file(self, path: str, ref: str = "main") -> Optional[dict]:
        """Get file content and SHA from the repo."""
        try:
            url = f"{self.repo_url}/contents/{path}"
            resp = await self._client.get(
                url, headers=self._headers(), params={"ref": ref}
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return {"content": content, "sha": data["sha"], "path": path}
        except Exception as e:
            logger.error(f"Failed to get file {path}: {e}")
            return None

    async def put_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: Optional[str] = None,
    ) -> bool:
        """Create or update a file in the repo."""
        try:
            url = f"{self.repo_url}/contents/{path}"
            body = {
                "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch,
            }
            if sha:
                body["sha"] = sha

            resp = await self._client.put(url, json=body, headers=self._headers())
            resp.raise_for_status()
            logger.info(f"Pushed file {path} to {branch}")
            return True
        except Exception as e:
            logger.error(f"Failed to push file {path}: {e}")
            return False

    # ── Branch Operations ──

    async def create_branch(self, branch_name: str, from_branch: str = "main") -> bool:
        """Create a new branch from an existing one."""
        try:
            # Get the SHA of the source branch
            url = f"{self.repo_url}/git/ref/heads/{from_branch}"
            resp = await self._client.get(url, headers=self._headers())
            resp.raise_for_status()
            sha = resp.json()["object"]["sha"]

            # Create the new branch
            url = f"{self.repo_url}/git/refs"
            body = {
                "ref": f"refs/heads/{branch_name}",
                "sha": sha,
            }
            resp = await self._client.post(url, json=body, headers=self._headers())
            if resp.status_code == 422:
                # Branch already exists
                logger.info(f"Branch {branch_name} already exists")
                return True
            resp.raise_for_status()
            logger.info(f"Created branch {branch_name} from {from_branch}")
            return True
        except Exception as e:
            logger.error(f"Failed to create branch {branch_name}: {e}")
            return False

    async def merge_branch(
        self, branch_name: str, into: str = "main", message: str = ""
    ) -> bool:
        """Merge a branch into another."""
        try:
            url = f"{self.repo_url}/merges"
            body = {
                "base": into,
                "head": branch_name,
                "commit_message": message or f"Merge {branch_name} into {into}",
            }
            resp = await self._client.post(url, json=body, headers=self._headers())
            if resp.status_code == 204:
                logger.info("Nothing to merge (already up to date)")
                return True
            resp.raise_for_status()
            logger.info(f"Merged {branch_name} into {into}")
            return True
        except Exception as e:
            logger.error(f"Failed to merge {branch_name}: {e}")
            return False

    async def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch."""
        try:
            url = f"{self.repo_url}/git/refs/heads/{branch_name}"
            resp = await self._client.delete(url, headers=self._headers())
            if resp.status_code == 204:
                logger.info(f"Deleted branch {branch_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete branch {branch_name}: {e}")
            return False

    # ── Bulk Push (for self-evolution) ──

    async def push_files(
        self,
        files: dict[str, str],
        branch: str,
        message: str,
    ) -> bool:
        """Push multiple files to a branch."""
        success = True
        for path, content in files.items():
            existing = await self.get_file(path, ref=branch)
            sha = existing["sha"] if existing else None
            if not await self.put_file(path, content, message, branch, sha):
                success = False
        return success
