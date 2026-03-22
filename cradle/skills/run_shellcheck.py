
import subprocess
import tempfile
import os

def run_shellcheck(script_content: str) -> str:
    """
    Executes 'shellcheck' on the provided bash script content and returns its findings.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as f:
        f.write(script_content)
        script_path = f.name

    try:
        # Make the script executable for shellcheck if needed (though shellcheck usually just reads)
        os.chmod(script_path, 0o755)
        
        # Run shellcheck
        result = subprocess.run(
            ['shellcheck', script_path],
            capture_output=True,
            text=True,
            check=False  # Don't raise an error for non-zero exit code (shellcheck returns 1 if issues found)
        )
        return result.stdout + result.stderr
    finally:
        os.remove(script_path)

