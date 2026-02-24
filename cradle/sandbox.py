"""Sandbox — executes agent-generated code safely.

Primary: Docker containers (if Docker socket is available)
Fallback: Direct subprocess with /tmp isolation (when Docker is not available)

Every sub-agent runs here, never in the main process.
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = "python:3.12-slim"
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

    async def _check_docker(self) -> bool:
        """Check if Docker CLI is available."""
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
                logger.info("Docker CLI available — using Docker sandbox")
            else:
                logger.warning("Docker CLI found but not working — using subprocess fallback")
        except (FileNotFoundError, asyncio.TimeoutError):
            self._docker_available = False
            logger.warning("Docker CLI not found — using subprocess fallback (less isolated)")

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
            return await self._run_docker(code, timeout, packages, network)
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
            return await self._run_docker_shell(script, image, timeout, network)
        else:
            return await self._run_subprocess_shell(script, timeout)

    # ── Docker Sandbox ──

    async def _run_docker(
        self, code: str, timeout: int, packages: Optional[list[str]], network: bool
    ) -> SandboxResult:
        """Run Python in a Docker container."""
        t0 = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="cradle_sandbox_") as tmpdir:
            # Write code file
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w") as f:
                f.write(code)

            # Write runner script
            runner = "#!/bin/bash\nset -e\n"
            if packages:
                runner += f"pip install --quiet {' '.join(packages)}\n"
            runner += "python /workspace/script.py\n"

            runner_path = os.path.join(tmpdir, "run.sh")
            with open(runner_path, "w") as f:
                f.write(runner)
            os.chmod(runner_path, 0o755)

            # Build docker command
            docker_cmd = [
                "docker", "run", "--rm",
                "--cap-drop=ALL",
                "--memory=256m", "--cpus=1",
                "--pids-limit=100",
                "-v", f"{tmpdir}:/workspace:ro",
                "-w", "/workspace",
            ]
            if not network:
                docker_cmd.append("--network=none")

            docker_cmd.extend([SANDBOX_IMAGE, "bash", "/workspace/run.sh"])

            return await self._exec(docker_cmd, timeout, t0, method="docker")

    async def _run_docker_shell(
        self, script: str, image: str, timeout: int, network: bool
    ) -> SandboxResult:
        """Run shell script in Docker."""
        t0 = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="cradle_sandbox_") as tmpdir:
            script_path = os.path.join(tmpdir, "script.sh")
            with open(script_path, "w") as f:
                f.write(script)
            os.chmod(script_path, 0o755)

            docker_cmd = [
                "docker", "run", "--rm",
                "--cap-drop=ALL",
                "--memory=256m", "--cpus=1",
                "-v", f"{tmpdir}:/workspace:ro",
                "-w", "/workspace",
            ]
            if not network:
                docker_cmd.append("--network=none")

            docker_cmd.extend([image, "bash", "/workspace/script.sh"])

            return await self._exec(docker_cmd, timeout, t0, method="docker")

    # ── Subprocess Fallback ──

    async def _run_subprocess(
        self, code: str, timeout: int, packages: Optional[list[str]]
    ) -> SandboxResult:
        """Run Python code as a subprocess (fallback when Docker not available)."""
        t0 = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="cradle_sub_") as tmpdir:
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w") as f:
                f.write(code)

            # Install packages first if needed
            if packages:
                pip_proc = await asyncio.create_subprocess_exec(
                    "pip", "install", "--quiet", *packages,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    await asyncio.wait_for(pip_proc.communicate(), timeout=30)
                except asyncio.TimeoutError:
                    pass

            cmd = ["python", script_path]
            return await self._exec(cmd, timeout, t0, method="subprocess")

    async def _run_subprocess_shell(self, script: str, timeout: int) -> SandboxResult:
        """Run shell script as subprocess."""
        t0 = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="cradle_sub_") as tmpdir:
            script_path = os.path.join(tmpdir, "script.sh")
            with open(script_path, "w") as f:
                f.write(script)
            os.chmod(script_path, 0o755)

            cmd = ["bash", script_path]
            return await self._exec(cmd, timeout, t0, method="subprocess")

    # ── Common execution ──

    async def _exec(
        self, cmd: list[str], timeout: int, t0: float, method: str
    ) -> SandboxResult:
        """Execute a command and capture output."""
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
            await proc.wait()
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to pull image {image}: {e}")
            return False
