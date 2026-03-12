
import json
import os
from pathlib import Path

# Placeholder for actual LLM interaction logic
def _call_llm(prompt):
    # Simulate LLM response for code generation
    if "generate test for" in prompt.lower():
        return {"code": "def test_example(): assert True"}
    return {"code": "# New feature code
def new_feature():
    return 'hello'"}

def evolve(current_code: str, objective: str) -> str:
    print(f"Evolving code for objective: {objective}")

    # Step 1: Propose a change
    proposed_change_prompt = f"Given the current code:

```python
{current_code}
```

Propose a change to achieve the objective: {objective}. Provide only the changed/new function bodies or classes, or a complete new file content if necessary. Enclose the code in a JSON object with a 'code' key." # noqa: E501
    proposed_change_response = _call_llm(proposed_change_prompt)
    proposed_code = proposed_change_response.get("code", "")

    if not proposed_code:
        print("LLM failed to propose a change.")
        return current_code

    # Step 2: Generate unit tests for the proposed change
    test_generation_prompt = f"Generate unit tests for the following proposed code change, focusing on the new or modified functionality:

```python
{proposed_code}
```

Provide only the test code in a JSON object with a 'code' key." # noqa: E501
    test_response = _call_llm(test_generation_prompt)
    generated_tests = test_response.get("code", "")

    if not generated_tests:
        print("LLM failed to generate tests.")
        return current_code

    # Create a temporary directory for execution
    temp_dir = Path("/tmp/cradle/temp_evolution_run")
    temp_dir.mkdir(exist_ok=True)

    # Write the proposed code to a temporary file
    proposed_file_path = temp_dir / "proposed_module.py"
    with open(proposed_file_path, "w") as f:
        f.write(proposed_code)
    
    # Write the generated tests to a temporary test file
    test_file_path = temp_dir / "test_proposed_module.py"
    with open(test_file_path, "w") as f:
        # Ensure pytest can discover and run tests. Add imports if needed.
        f.write("import pytest
")
        f.write(f"import sys
sys.path.insert(0, str(Path(__file__).parent))
") # Add temp_dir to path
        f.write(f"from proposed_module import *

") # Import everything from the proposed module
        f.write(generated_tests)

    # Step 3: Run the tests in the sandbox
    print("Running generated tests...")
    try:
        # Use pytest to discover and run tests
        test_result = subprocess.run(
            ["pytest", str(test_file_path)],
            capture_output=True, text=True, check=False, cwd=temp_dir
        )
        print("Test stdout:
", test_result.stdout)
        print("Test stderr:
", test_result.stderr)

        if test_result.returncode == 0:
            print("Tests passed successfully!")
            # If tests pass, integrate the proposed code
            # This integration logic would be more complex in a real scenario
            # For now, we'll just return the proposed code as the new current_code
            return proposed_code
        else:
            print(f"Tests failed with exit code {test_result.returncode}.")
            # Optionally, ask LLM to fix based on test results
            return current_code # Revert to original if tests fail
    except Exception as e:
        print(f"Error running tests: {e}")
        return current_code
    finally:
        # Clean up temporary files
        import shutil
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    initial_code = 