"""Sandbox — executes agent-generated code safely using DinD (Docker-in-Docker).

DinD works via the mounted /var/run/docker.sock. However, volume mounts
(-v /tmp/foo:/workspace) fail because the container's /tmp is NOT visible
to the host Docker daemon.

Solution: pipe code directly via STDIN — zero file mounts required.
  docker run python:3.12-slim python -   (reads from stdin)

For shell scripts: docker run ... bash -s < script.sh

Fallback: subprocess when Docker unavailable.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = "cradle-sandbox"  # Custom image with git, curl, jq pre-installed
SANDBOX_IMAGE_FALLBACK = "python:3.12-slim"  # Used if custom image not available
DEFAULT_TIMEOUT = 60
MAX_OUTPUT_BYTES = 50_000


@dataclass
class SandboxResult:
    """Result from running code in a sandbox."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    container_id: str = ""
    truncated: bool = False
    method: str = ""  # "docker" or "subprocess"


class Sandbox:
    """Manages code execution in isolated environments."""

    def __init__(self, docker_socket: str = "/var/run/docker.sock"):
        self.docker_socket = docker_socket
        self._docker_available: Optional[bool] = None
        self._sandbox_image: Optional[str] = None

    async def _get_sandbox_image(self) -> str:
        """Check if cradle-sandbox image exists, fall back to python:3.12-slim."""
        if self._sandbox_image is not None:
            return self._sandbox_image

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "image", "inspect", SANDBOX_IMAGE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            if proc.returncode == 0:
                self._sandbox_image = SANDBOX_IMAGE
                logger.info(f"Using custom sandbox image: {SANDBOX_IMAGE}")
            else:
                self._sandbox_image = SANDBOX_IMAGE_FALLBACK
                logger.warning(f"Custom sandbox image not found, using: {SANDBOX_IMAGE_FALLBACK}")
        except Exception:
            self._sandbox_image = SANDBOX_IMAGE_FALLBACK

        return self._sandbox_image

    async def _check_docker(self) -> bool:
        """Check if Docker CLI is available and DinD works."""
        if self._docker_available is not None:
            return self._docker_available

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            self._docker_available = proc.returncode == 0
            if self._docker_available:
                logger.info("Docker available — DinD sandbox active (stdin pipe mode)")
            else:
                logger.warning("Docker not working — using subprocess fallback")
        except (FileNotFoundError, asyncio.TimeoutError):
            self._docker_available = False
            logger.warning("Docker CLI not found — using subprocess fallback")

        return self._docker_available

    async def run_python(
        self,
        code: str,
        timeout: int = DEFAULT_TIMEOUT,
        packages: Optional[list[str]] = None,
        network: bool = False,
    ) -> SandboxResult:
        """Run Python code in the best available sandbox."""
        if await self._check_docker():
            return await self._run_docker_stdin(code, timeout, packages, network)
        else:
            return await self._run_subprocess(code, timeout, packages)

    async def run_shell(
        self,
        script: str,
        image: str = "ubuntu:22.04",
        timeout: int = DEFAULT_TIMEOUT,
        network: bool = False,
    ) -> SandboxResult:
        """Run a shell script."""
        if await self._check_docker():
            return await self._run_docker_shell_stdin(script, image, timeout, network)
        else:
            return await self._run_subprocess_shell(script, timeout)

    # ── DinD: stdin pipe mode (no volume mounts) ──

    async def _run_docker_stdin(
        self, code: str, timeout: int, packages: Optional[list[str]], network: bool
    ) -> SandboxResult:
        """Run Python code in Docker by piping via stdin — no file mounts needed.

        If packages are required, generates a wrapper script that installs them
        then runs the code, all via stdin pipe.
        """
        t0 = time.monotonic()

        # Build the actual Python payload
        if packages:
            # Prepend pip install in Python itself (no bash needed)
            pip_code = (
                "import subprocess, sys\n"
                f"subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', '--no-cache-dir', '--root-user-action=ignore', "
                f"{', '.join(repr(p) for p in packages)}], check=True, stderr=subprocess.DEVNULL)\n\n"
            )
            payload = pip_code + code
        else:
            payload = code

        docker_cmd = [
            "docker", "run", "--rm", "-i",  # -i = keep stdin open
            "--cap-drop=ALL",
            "--memory=512m", "--cpus=1",
            "--pids-limit=100",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
        ]
        if not network:
            docker_cmd.append("--network=none")
        else:
            # Explicit DNS fallback for reliable resolution
            docker_cmd.extend(["--dns", "1.1.1.1", "--dns", "8.8.8.8"])

        # Pass env vars the agent's code might use
        for env_var in ["AGENTPLAYBOOKS_API_KEY", "AGENTPLAYBOOKS_PLAYBOOK_GUID",
                         "GEMINI_API_KEY", "GITHUB_PAT", "GOOGLE_CSE_KEY", "GOOGLE_CSE_ID"]:
            val = os.environ.get(env_var, "")
            if val:
                docker_cmd += ["-e", f"{env_var}={val}"]

        docker_cmd.extend([await self._get_sandbox_image(), "python", "-"])

        return await self._exec_with_stdin(docker_cmd, payload, timeout, t0, method="dind-stdin")

    async def _run_docker_shell_stdin(
        self, script: str, image: str, timeout: int, network: bool
    ) -> SandboxResult:
        """Run shell script via stdin — no file mounts."""
        t0 = time.monotonic()

        docker_cmd = [
            "docker", "run", "--rm", "-i",
            "--cap-drop=ALL",
            "--memory=256m", "--cpus=1",
        ]
        if not network:
            docker_cmd.append("--network=none")

        docker_cmd.extend([image, "bash", "-s"])

        return await self._exec_with_stdin(docker_cmd, script, timeout, t0, method="dind-shell-stdin")

    # ── Subprocess Fallback ──

    async def _run_subprocess(
        self, code: str, timeout: int, packages: Optional[list[str]]
    ) -> SandboxResult:
        """Run Python code as a subprocess (fallback when Docker not available)."""
        t0 = time.monotonic()

        tmpdir = tempfile.mkdtemp(prefix="cradle_sub_")
        try:
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w") as f:
                f.write(code)

            # Install packages first if needed
            if packages:
                pip_proc = await asyncio.create_subprocess_exec(
                    "pip", "install", "--quiet", "--no-cache-dir", *packages,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(pip_proc.communicate(), timeout=120)

            cmd = ["python", script_path]
            return await self._exec(cmd, timeout, t0, method="subprocess")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _run_subprocess_shell(self, script: str, timeout: int) -> SandboxResult:
        """Run shell script as a subprocess."""
        t0 = time.monotonic()

        tmpdir = tempfile.mkdtemp(prefix="cradle_sub_")
        try:
            script_path = os.path.join(tmpdir, "script.sh")
            with open(script_path, "w") as f:
                f.write(script)
            os.chmod(script_path, 0o755)

            cmd = ["bash", script_path]
            return await self._exec(cmd, timeout, t0, method="subprocess")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ── Shared execution helpers ──

    async def _exec_with_stdin(
        self, cmd: list[str], stdin_data: str, timeout: int, t0: float, method: str
    ) -> SandboxResult:
        """Execute a command, feeding data via stdin. No file mounts needed."""
        logger.info(f"Sandbox ({method}): {cmd[0]} timeout={timeout}s stdin={len(stdin_data)}b")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin_data.encode("utf-8")),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                duration = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    success=False, stdout="", method=method,
                    stderr=f"TIMEOUT: Killed after {timeout}s",
                    exit_code=-1, duration_ms=duration,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            truncated = False
            if len(stdout) > MAX_OUTPUT_BYTES:
                stdout = stdout[:MAX_OUTPUT_BYTES] + "\n... [TRUNCATED]"
                truncated = True
            if len(stderr) > MAX_OUTPUT_BYTES:
                stderr = stderr[:MAX_OUTPUT_BYTES] + "\n... [TRUNCATED]"
                truncated = True

            duration = int((time.monotonic() - t0) * 1000)
            exit_code = proc.returncode or 0

            result = SandboxResult(
                success=(exit_code == 0),
                stdout=stdout, stderr=stderr,
                exit_code=exit_code, duration_ms=duration,
                truncated=truncated, method=method,
            )

            logger.info(
                f"Sandbox ({method}): exit={exit_code} duration={duration}ms "
                f"stdout={len(stdout)}b stderr={len(stderr)}b"
            )
            return result

        except FileNotFoundError:
            duration = int((time.monotonic() - t0) * 1000)
            return SandboxResult(
                success=False, stdout="", method=method,
                stderr=f"Command not found: {cmd[0]}",
                exit_code=-2, duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - t0) * 1000)
            return SandboxResult(
                success=False, stdout="", method=method,
                stderr=f"Sandbox error: {e}",
                exit_code=-3, duration_ms=duration,
            )

    async def _exec(
        self, cmd: list[str], timeout: int, t0: float, method: str
    ) -> SandboxResult:
        """Execute a command and capture output (no stdin)."""
        logger.info(f"Sandbox ({method}): running {cmd[0]} timeout={timeout}s")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                duration = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    success=False, stdout="", method=method,
                    stderr=f"TIMEOUT: Killed after {timeout}s",
                    exit_code=-1, duration_ms=duration,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            truncated = False
            if len(stdout) > MAX_OUTPUT_BYTES:
                stdout = stdout[:MAX_OUTPUT_BYTES] + "\n... [TRUNCATED]"
                truncated = True

            duration = int((time.monotonic() - t0) * 1000)
            exit_code = proc.returncode or 0

            return SandboxResult(
                success=(exit_code == 0),
                stdout=stdout, stderr=stderr,
                exit_code=exit_code, duration_ms=duration,
                truncated=truncated, method=method,
            )

        except FileNotFoundError:
            duration = int((time.monotonic() - t0) * 1000)
            return SandboxResult(
                success=False, stdout="", method=method,
                stderr=f"Command not found: {cmd[0]}",
                exit_code=-2, duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - t0) * 1000)
            return SandboxResult(
                success=False, stdout="", method=method,
                stderr=f"Sandbox error: {e}",
                exit_code=-3, duration_ms=duration,
            )

    async def pull_image(self, image: str) -> bool:
        """Pre-pull a Docker image."""
        if not await self._check_docker():
            return False
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "pull", image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
            return proc.returncode == 0
        except Exception:
            return False

    @property
    def mode(self) -> str:
        """Current sandbox mode description."""
        if self._docker_available is True:
            return "DinD (stdin pipe)"
        elif self._docker_available is False:
            return "subprocess fallback"
        return "unknown (not checked yet)"
