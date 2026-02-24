"""Docker sandbox — spawns ephemeral containers for safe code execution.

Every piece of agent-generated code runs here, never on the host.
Containers are: --rm (auto-delete), --cap-drop=ALL, time-limited.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = "python:3.12-slim"
DEFAULT_TIMEOUT = 60  # seconds
MAX_OUTPUT_BYTES = 50_000  # truncate enormous outputs


@dataclass
class SandboxResult:
    """Result from running code in a sandbox container."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    container_id: str = ""
    truncated: bool = False


class Sandbox:
    """Manages ephemeral Docker containers for isolated code execution."""

    def __init__(self, docker_socket: str = "/var/run/docker.sock"):
        self.docker_socket = docker_socket

    async def run_python(
        self,
        code: str,
        timeout: int = DEFAULT_TIMEOUT,
        packages: Optional[list[str]] = None,
        network: bool = False,
    ) -> SandboxResult:
        """Run Python code in an isolated container.
        
        Args:
            code: Python source code to execute
            timeout: Max seconds before kill
            packages: pip packages to install before running
            network: Whether to allow network access (default: no)
        """
        # Build the script that runs inside the container
        setup_script = "#!/bin/bash\nset -e\n"
        if packages:
            setup_script += f"pip install --quiet {' '.join(packages)}\n"
        setup_script += "python /workspace/script.py\n"

        return await self._run_in_container(
            image=SANDBOX_IMAGE,
            files={"script.py": code, "run.sh": setup_script},
            command=["bash", "/workspace/run.sh"],
            timeout=timeout,
            network=network,
        )

    async def run_shell(
        self,
        script: str,
        image: str = "ubuntu:22.04",
        timeout: int = DEFAULT_TIMEOUT,
        network: bool = False,
    ) -> SandboxResult:
        """Run a shell script in an isolated container."""
        return await self._run_in_container(
            image=image,
            files={"script.sh": script},
            command=["bash", "/workspace/script.sh"],
            timeout=timeout,
            network=network,
        )

    async def _run_in_container(
        self,
        image: str,
        files: dict[str, str],
        command: list[str],
        timeout: int,
        network: bool,
    ) -> SandboxResult:
        """Core container execution logic."""
        t0 = time.monotonic()

        # Create temp directory with files
        with tempfile.TemporaryDirectory(prefix="cradle_sandbox_") as tmpdir:
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, "w") as f:
                    f.write(content)
                if filename.endswith(".sh"):
                    os.chmod(filepath, 0o755)

            # Build docker run command
            docker_cmd = [
                "docker", "run",
                "--rm",                          # Auto-remove after exit
                "--cap-drop=ALL",                # Drop all capabilities
                "--memory=256m",                 # Memory limit
                "--cpus=1",                      # CPU limit
                "--pids-limit=100",              # Process limit
                "-v", f"{tmpdir}:/workspace:ro", # Mount code read-only
                "-w", "/workspace",
            ]

            if not network:
                docker_cmd.append("--network=none")

            docker_cmd.append(image)
            docker_cmd.extend(command)

            logger.info(f"Sandbox: running in {image} with timeout={timeout}s network={network}")

            try:
                proc = await asyncio.create_subprocess_exec(
                    *docker_cmd,
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
                        success=False,
                        stdout="",
                        stderr=f"TIMEOUT: Container killed after {timeout}s",
                        exit_code=-1,
                        duration_ms=duration,
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
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    duration_ms=duration,
                    truncated=truncated,
                )

                logger.info(
                    f"Sandbox: done exit={exit_code} duration={duration}ms "
                    f"stdout={len(stdout)}b stderr={len(stderr)}b"
                )
                return result

            except FileNotFoundError:
                duration = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    success=False,
                    stdout="",
                    stderr="Docker CLI not found — is Docker installed?",
                    exit_code=-2,
                    duration_ms=duration,
                )
            except Exception as e:
                duration = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    success=False,
                    stdout="",
                    stderr=f"Sandbox error: {e}",
                    exit_code=-3,
                    duration_ms=duration,
                )

    async def pull_image(self, image: str) -> bool:
        """Pre-pull a Docker image."""
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
