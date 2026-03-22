
import json
import os
from typing import Optional

import google.generativeai as genai

def code_review(file_path: str, diff: Optional[str] = None) -> str:
    """
    Performs an LLM-powered code review on a given file or diff.

    Args:
        file_path: The path to the file to be reviewed.
        diff: Optional. A string containing the diff to be reviewed.
              If provided, the LLM will focus on the changes.

    Returns:
        A JSON string with actionable recommendations.
    """
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-pro') # Using 1.5 Pro as 3.1 Pro might not be available or might be 1.5 Pro internally

    try:
        with open(file_path, 'r') as f:
            file_content = f.read()
    except FileNotFoundError:
        return json.dumps({"error": f"File not found: {file_path}"})
    except Exception as e:
        return json.dumps({"error": f"Error reading file {file_path}: {str(e)}"})

    prompt_parts = [
        "You are an expert code reviewer. Perform a thorough code review focusing on:",
        "- Potential bugs and logical errors",
        "- Security vulnerabilities (e.g., injection, XSS, insecure deserialization)",
        "- Performance issues (e.g., inefficient algorithms, N+1 queries)",
        "- Style guide violations (e.g., PEP8 for Python, ESLint for JS, etc.)",
        "- Best practices and design patterns",
        "- Readability and maintainability",
        "Provide actionable recommendations in a JSON array format. Each recommendation should include: `category`, `severity` (low, medium, high, critical), `line_number` (if applicable), `description`, and `recommendation`.",
        "If there are no issues, return an empty array.",
        "\n---",
        f"\nFile: {file_path}"
    ]

    if diff:
        prompt_parts.append("\nReview the following diff:")
        prompt_parts.append(f"\n```diff\n{diff}\n```")
        prompt_parts.append("\nAnd the full file content for context:")
        prompt_parts.append(f"\n```\n{file_content}\n```")
    else:
        prompt_parts.append("Review the following file content:")
        prompt_parts.append(f"\n```\n{file_content}\n```")

    try:
        response = model.generate_content("\n".join(prompt_parts))
        # Attempt to parse the response as JSON. Handle cases where the LLM might wrap it in markdown.
        text_response = response.text.strip()
        if text_response.startswith('```json') and text_response.endswith('```'):
            text_response = text_response[7:-3].strip()
        json_output = json.loads(text_response)
        return json.dumps(json_output, indent=2)
    except Exception as e:
        return json.dumps({"error": f"LLM generation or parsing failed: {str(e)}", "llm_raw_response": response.text if 'response' in locals() else "No response"})


if __name__ == '__main__':
    # Example usage (for local testing)
    # Create a dummy file for testing
    test_file_path = "test_code.py"
    with open(test_file_path, "w") as f:
        f.write("""
def add(a, b):
    # This is a comment
    result = a + b
    print(f"The result is {result}")
    return result

def insecure_func(user_input):
    # Potential security vulnerability: direct string concatenation in eval
    eval("print('" + user_input + "')")

def performance_issue():
    # Inefficient loop example
    data = list(range(10000))
    for i in range(len(data)):
        for j in range(len(data)):
            pass # O(n^2) operation

if __name__ == '__main__':
    add(1, 2)
    insecure_func("__import__('os').system('echo pwned')")
    performance_issue()
""")

    print("""
--- Reviewing example code with diff ---
""")
    review_output = code_review(test_file_path)
    print(review_output)

    # Example with a diff (simulated)
    print(f"\n--- Reviewing diff for {test_file_path} ---")
    dummy_diff = """
--- a/test_code.py
+++ b/test_code.py
@@ -1,7 +1,8 @@
 def add(a, b):
     # This is a comment
     result = a + b
-    print(f"The result is {result}")
+    # Added a new line here
+    print(f"Calculated: {result}")
     return result
 """
    diff_review_output = code_review(test_file_path, diff=dummy_diff)
    print(diff_review_output)

    os.remove(test_file_path)
