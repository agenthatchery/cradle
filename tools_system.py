import subprocess

def execute_shell_command(command: str) -> str:
    """
    Executes a shell command directly on the host (inside the Cradle container, which has docker socket access).
    WARNING: This is highly dangerous and should only be used to manage Docker containers or system resources.
    Use `execute_python_in_sandbox` for safely running analytical code.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return f"Command succeeded:\n{result.stdout}"
        else:
            return f"Command failed with code {result.returncode}:\n{result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
