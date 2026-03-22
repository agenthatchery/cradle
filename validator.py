import ast
import logging
import os
import sys

logger = logging.getLogger(__name__)

class Validator:
    """Performs integrity and safety checks on proposed code changes."""

    @staticmethod
    def _check_restricted_files(path: str) -> tuple[bool, str]:
        """Verify that critical files like config.py and main.py are not modified."""
        restricted_files = ["cradle/config.py", "cradle/main.py"]
        if path in restricted_files:
            return False, f"CRITICAL: Modification of '{path}' is not allowed for safety reasons."
        return True, ""

    @staticmethod
    def check_syntax(content: str) -> tuple[bool, str]:
        """Verify that the code is valid Python syntax."""
        try:
            ast.parse(content)
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} at line {e.lineno}, col {e.offset}"
        except Exception as e:
            return False, f"Unexpected error during syntax check: {e}"

    @staticmethod
    def check_integrity(path: str, content: str) -> tuple[bool, str]:
        """Verify that critical structural elements are preserved."""
        filename = os.path.basename(path)
        
        # == Config.py Integrity ==
        if filename == "config.py":
            if "class Config:" not in content:
                return False, "CRITICAL: 'class Config:' missing from config.py. Modification rejected."
            if "def from_env" not in content:
                return False, "CRITICAL: 'from_env' method missing from Config class. Modification rejected."
            if "llm_providers" not in content:
                return False, "CRITICAL: 'llm_providers' field missing from Config. Modification rejected."

        # == Evolver.py Integrity ==
        if filename == "evolver.py":
            if "class Evolver:" not in content:
                return False, "CRITICAL: 'class Evolver:' missing from evolver.py. Modification rejected."
            if "async def evolve" not in content:
                return False, "CRITICAL: 'evolve' method missing from Evolver. Modification rejected."

        # == TaskEngine.py Integrity ==
        if filename == "task_engine.py":
            if "class TaskEngine:" not in content:
                return False, "CRITICAL: 'class TaskEngine:' missing from task_engine.py. Modification rejected."

        # == Size Check ==
        # If the file size drops by more than 70% in a single edit, it's likely a catastrophic failure.
        # Note: This requires reading the existing file, which might not be possible in a static check.
        # But for 'propose_improvement', the Evolver has the source.
        
        return True, ""

    @classmethod
    def validate_proposal(cls, path: str, content: str) -> tuple[bool, str]:
        """Run all checks on a proposed file change."""
        # 1. Check for restricted files
        ok, msg = cls._check_restricted_files(path)
        if not ok:
            return ok, msg

        # 2. Check Python syntax
        ok, msg = cls.check_syntax(content)
        if not ok:
            return ok, msg
            
        # 3. Check structural integrity
        ok, msg = cls.check_integrity(path, content)
        if not ok:
            return ok, msg
            
        return True, "All checks passed."
