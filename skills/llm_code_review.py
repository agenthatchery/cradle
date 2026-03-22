
import os
import json
from typing import Optional
import google.generativeai as genai

def llm_code_review(file_path: str, diff: Optional[str] = None) -> dict:
    """
    Performs an LLM-powered code review on a given file or diff.

    Args:
        file_path: The path to the file to be reviewed.
        diff: An optional diff string to review. If provided, the LLM will focus on the diff.

    Returns:
        A dictionary containing code review recommendations.
    """
    # Ensure GEMINI_API_KEY is set
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY environment variable not set."}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')

    try:
        if diff:
            content_to_review = f"""Review the following code diff:

```diff
{diff}
```
"""
        else:
            with open(file_path, 'r') as f:
                file_content = f.read()
            content_to_review = f"""Review the following file: {file_path}

```
{file_content}
```
"""

        prompt = f"""
        You are an expert code reviewer. Perform a thorough code review of the provided code/diff.
        Identify potential bugs, security vulnerabilities, performance issues, and style guide violations.
        Provide actionable recommendations in a JSON array format. Each item in the array should have:
        - "type": ("bug", "security", "performance", "style", "other")
        - "line": (optional) The line number where the issue is found (if applicable).
        - "severity": ("critical", "high", "medium", "low", "info")
        - "description": A detailed description of the issue.
        - "recommendation": A clear, actionable recommendation to fix the issue.

        Focus on one issue per JSON object. If no issues are found, return an empty array.

        {content_to_review}

        Your response MUST be a JSON array. Do not include any other text or markdown fences outside the JSON.
        """

        response = model.generate_content(prompt)
        review_output = response.text.strip()

        # Attempt to parse the JSON response
        try:
            recommendations = json.loads(review_output)
            if not isinstance(recommendations, list):
                raise ValueError("LLM response is not a JSON array.")
            return {"review": recommendations}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse LLM response as JSON: {e}", "raw_llm_output": review_output}
        except ValueError as e:
            return {"error": str(e), "raw_llm_output": review_output}

    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

