
import google.generativeai as genai
import os
import json

def code_review(file_path: str, file_content: str, diff: str = None) -> dict:
    """
    Performs an LLM-powered code review.

    Args:
        file_path: The path to the file being reviewed.
        file_content: The full content of the file.
        diff: An optional diff string if only changes are to be reviewed.

    Returns:
        A JSON object with actionable recommendations.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY not found in environment variables."}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro') # Using 1.5 Pro as 3.1 Pro might not be directly available yet

    prompt = f"""You are an expert code reviewer. Review the following code for potential bugs, security vulnerabilities, performance issues, and style guide violations. Provide actionable recommendations in a JSON format.

File: {file_path}

Code:
```
{file_content}
```

"""

    if diff:
        prompt += f"""Diff:
```diff
{diff}
```

Focus your review on the changes introduced by the diff, but also consider the overall context of the file.
"""

    prompt += """Your output MUST be a JSON object with the following structure:
{
  "summary": "Overall summary of the review.",
  "recommendations": [
    {
      "type": "bug" | "security" | "performance" | "style" | "other",
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "line": <line_number_if_applicable>,
      "message": "Detailed description of the issue and how to fix it."
    }
  ]
}
If no issues are found, the 'recommendations' array should be empty.
"""

    try:
        response = model.generate_content(prompt)
        # Attempt to parse the text as JSON, handling potential markdown fences
        text = response.text.strip()
        if text.startswith('```json') and text.endswith('```'):
            text = text[len('```json'):-len('```')].strip()
        elif text.startswith('```') and text.endswith('```'): # Fallback for plain code block
            text = text[len('```'):-len('```')].strip()

        review_output = json.loads(text)
        return review_output
    except Exception as e:
        return {"error": f"Failed to get or parse LLM response: {e}", "raw_response": response.text if 'response' in locals() else "No response"}

if __name__ == '__main__':
    # Example usage (for testing purposes)
    example_code = """
def add(a, b):
    # This is a comment
    return a + b

class MyClass:
    def __init__(self):
        pass

def insecure_function(user_input):
    eval(user_input) # Potential security vulnerability

def long_function(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z):
    # This function is too long, violating style guides and readability
    result = a+b+c+d+e+f+g+h+i+j+k+l+m+n+o+p+q+r+s+t+u+v+w+x+y+z
    return result

"""
    example_diff = """
--- a/example.py
+++ b/example.py
@@ -1,5 +1,6 @@
 def add(a, b):
     # This is a comment
-    return a + b
+    result = a + b
+    return result
 
 class MyClass:
     def __init__(self):
"""

    print("
--- Reviewing example code with diff ---
")
    review_result_with_diff = code_review("example.py", example_code, example_diff)
    print(json.dumps(review_result_with_diff, indent=2))

    print("
--- Reviewing example code without diff ---
")
    review_result_no_diff = code_review("example.py", example_code)
    print(json.dumps(review_result_no_diff, indent=2))
