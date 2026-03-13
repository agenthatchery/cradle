
import os
import json
from typing import Optional

# Placeholder for Gemini client import. Replace with actual client when available.
# For now, we'll simulate it or use a direct HTTP call if necessary.

# Assuming GEMINI_API_KEY is available in the environment
def _call_gemini_api(prompt: str) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-1.5-pro') # Using 1.5 Pro as 3.1 Pro might not be generally available or stable.
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error calling Gemini API: {e}"

def code_review(file_path: str, diff: Optional[str] = None) -> dict:
    """
    Performs an LLM-powered code review on a given file or diff.

    Args:
        file_path (str): The path to the file to be reviewed.
        diff (Optional[str]): An optional diff string to review specific changes.

    Returns:
        dict: A JSON object with actionable recommendations.
    """
    content_to_review = ""
    if diff:
        review_type = "diff"
        content_to_review = diff
    elif os.path.exists(file_path):
        review_type = "file"
        with open(file_path, 'r') as f:
            content_to_review = f.read()
    else:
        return {"error": f"File not found: {file_path} and no diff provided."}

    if not content_to_review:
        return {"error": "No content to review.", "file_path": file_path, "diff_provided": bool(diff)}

    prompt = f"""You are an expert code reviewer. Your task is to perform a thorough code review.
Focus on identifying potential bugs, security vulnerabilities, performance issues, and style guide violations.
Provide actionable recommendations in a JSON format.

Review the following {review_type} for '{file_path}':

```
{content_to_review}
```

Your output MUST be a JSON object with the following structure:
{{
    "summary": "Overall summary of the review.",
    "recommendations": [
        {{
            "type": "bug" | "security" | "performance" | "style" | "other",
            "description": "Detailed description of the issue.",
            "severity": "low" | "medium" | "high",
            "line_numbers": [int], // Optional, relevant line numbers if applicable
            "suggested_fix": "Code snippet or detailed instruction for fixing the issue."
        }}
    ]
}}

Ensure the JSON is well-formed and directly parsable.
"""

    print(f"[*] Sending {review_type} for '{file_path}' to Gemini for review...")
    try:
        llm_response_text = _call_gemini_api(prompt)
        # Attempt to parse the JSON response
        if llm_response_text.startswith('```json') and llm_response_text.endswith('```'):
            llm_response_text = llm_response_text[7:-3].strip()
        elif llm_response_text.startswith('```') and llm_response_text.endswith('```'): # Handle cases where it might just be ```
            llm_response_text = llm_response_text[3:-3].strip()

        review_result = json.loads(llm_response_text)
        return review_result
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}")
        print(f"LLM Raw Response: {llm_response_text}")
        return {"error": "Failed to parse LLM response as JSON", "raw_response": llm_response_text, "exception": str(e)}
    except Exception as e:
        return {"error": f"An unexpected error occurred during LLM call or processing: {e}", "details": str(e)}

