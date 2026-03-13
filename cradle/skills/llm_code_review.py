
import os
import json
from typing import Optional, Dict, Any
import google.generativeai as genai

def llm_code_review(file_path: str, diff: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs an LLM-powered code review on a given file or diff.

    Args:
        file_path (str): The path to the file to review.
        diff (Optional[str]): An optional diff string to review. If provided,
                              the review will focus on the changes.

    Returns:
        Dict[str, Any]: A JSON object with actionable recommendations.
    """
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    with open(file_path, 'r') as f:
        file_content = f.read()

    # Configure Gemini API
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        return {"error": "GEMINI_API_KEY environment variable not set."}
    genai.configure(api_key=gemini_api_key)

    model = genai.GenerativeModel('gemini-1.5-pro') # Using 1.5 Pro as 3.1 Pro might not be available or stable yet

    prompt_parts = [
        "You are an expert code reviewer. Perform a thorough code review focusing on potential bugs, security vulnerabilities, performance issues, and style guide violations.",
        "Provide actionable recommendations in a JSON format. The JSON should be an array of objects, where each object has 'line', 'severity' (e.g., 'critical', 'high', 'medium', 'low', 'info'), 'category' (e.g., 'bug', 'security', 'performance', 'style'), and 'recommendation' fields.",
        "If there are no issues, return an empty array. Do not include any other text outside the JSON.",
        "---
"
    ]

    if diff:
        prompt_parts.append(f"Review the following diff for file `{file_path}`:
```diff
{diff}
```
")
        prompt_parts.append(f"Here is the full file content for context:
```
{file_content}
```
")
    else:
        prompt_parts.append(f"Review the following file content for `{file_path}`:
```
{file_content}
```
")

    prompt_parts.append("---
JSON Output:")

    try:
        response = model.generate_content("
".join(prompt_parts))
        # The API might return text with markdown fences, try to extract JSON
        response_text = response.text.strip()
        if response_text.startswith('```json') and response_text.endswith('```'):
            json_str = response_text[7:-3].strip()
        else:
            json_str = response_text

        review_results = json.loads(json_str)
        return {"review_results": review_results}
    except Exception as e:
        return {"error": f"LLM API call or JSON parsing failed: {e}", "raw_response": response.text if 'response' in locals() else 'No response'}

