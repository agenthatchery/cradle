
import httpx
import json
import os

def code_review(file_path: str, file_content: str, diff: str = None) -> dict:
    """
    Performs an LLM-powered code review on the given file content or diff.

    Args:
        file_path (str): The path to the file being reviewed.
        file_content (str): The full content of the file.
        diff (str, optional): A diff string representing changes. If provided,
                              the review focuses on the diff. Defaults to None.

    Returns:
        dict: A JSON object with actionable recommendations.
    """
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    headers = {"Content-Type": "application/json"}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={gemini_api_key}"

    prompt = f"""
You are an expert code reviewer. Perform a thorough code review for the following {file_path}. Identify potential bugs, security vulnerabilities, performance issues, and style guide violations. Provide actionable recommendations in a JSON array format. Each item in the array should be an object with 'line_number' (if applicable, otherwise null), 'type' (e.g., 'bug', 'security', 'performance', 'style', 'suggestion'), 'description', and 'recommendation'.

File: {file_path}
"""

    if diff:
        prompt += f"""
Review the following diff:
```diff
{diff}
```

And the current file content:
```
{file_content}
```
"""
    else:
        prompt += f"""
Review the following file content:
```
{file_content}
```
"""

    prompt += """
Your response MUST be a JSON array. Example:
[
  {
    "line_number": 15,
    "type": "bug",
    "description": "Possible off-by-one error in loop condition.",
    "recommendation": "Change `range(len(list))` to `range(len(list) - 1)` if last element is not to be included."
  },
  {
    "line_number": null,
    "type": "security",
    "description": "Hardcoded credentials found.",
    "recommendation": "Move sensitive information to environment variables or a secure configuration system."
  }
]
"""

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        
        # Extract the text content from the response
        # Gemini's response structure can be nested
        text_content = ""
        if 'candidates' in response_data and response_data['candidates']:
            for candidate in response_data['candidates']:
                if 'content' in candidate and 'parts' in candidate['content']:
                    for part in candidate['content']['parts']:
                        if 'text' in part:
                            text_content += part['text']
        
        # Attempt to parse the JSON output
        # Sometimes the LLM might include markdown fences or extra text
        json_start = text_content.find('[')
        json_end = text_content.rfind(']')
        
        if json_start != -1 and json_end != -1 and json_end > json_start:
            json_string = text_content[json_start : json_end + 1]
            return json.loads(json_string)
        else:
            # If direct JSON parsing fails, return a generic error or the raw text
            return {"error": "Failed to parse LLM response as JSON", "raw_response": text_content}

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error occurred: {e.response.status_code} - {e.response.text}"}
    except httpx.RequestError as e:
        return {"error": f"Request error occurred: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode error: {e}", "raw_response": text_content}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

