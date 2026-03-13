
import os
import json
import httpx

def llm_code_review(file_content: str, file_path: str, diff: str = None) -> dict:
    """
    Performs an LLM-powered code review on the given file content or diff.

    Args:
        file_content: The full content of the file to review.
        file_path: The path of the file being reviewed.
        diff: An optional diff string to review. If provided, the LLM will focus on the changes.

    Returns:
        A JSON object with actionable recommendations.
    """
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    headers = {
        "Content-Type": "application/json",
    }

    prompt_parts = [
        f"You are an expert code reviewer. Your task is to perform a thorough code review on the following {'diff' if diff else 'file content'}. "
        "Identify potential bugs, security vulnerabilities, performance issues, and style guide violations. "
        "Provide actionable recommendations in a JSON object format. The JSON should have a 'summary' string "
        "and a 'recommendations' list, where each recommendation is an object with 'type' (e.g., 'bug', 'security', 'performance', 'style'), "
        "'description', and 'severity' (e.g., 'critical', 'high', 'medium', 'low').

"
    ]

    if diff:
        prompt_parts.append(f"File: {file_path}
Diff:
```diff
{diff}
```
")
    else:
        prompt_parts.append(f"File: {file_path}
Content:
```
{file_content}
```
")

    prompt_parts.append("
Review result (JSON object):
")

    try:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={gemini_api_key}",
            headers=headers,
            json={
                "contents": [{
                    "parts": [{
                        "text": "".join(prompt_parts)
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                ]
            },
            timeout=60 # Increased timeout for potentially longer LLM responses
        )
        response.raise_for_status() # Raise an exception for HTTP errors

        response_data = response.json()
        
        # Extract the text content from the response
        # The structure can be complex, so we need to navigate it carefully
        if 'candidates' in response_data and response_data['candidates']:
            first_candidate = response_data['candidates'][0]
            if 'content' in first_candidate and 'parts' in first_candidate['content']:
                for part in first_candidate['content']['parts']:
                    if 'text' in part:
                        # Attempt to parse the text as JSON
                        try:
                            # Gemini sometimes wraps JSON in markdown fences
                            text_content = part['text'].strip()
                            if text_content.startswith('```json') and text_content.endswith('```'):
                                text_content = text_content[7:-3].strip()
                            elif text_content.startswith('```') and text_content.endswith('```'):
                                text_content = text_content[3:-3].strip()

                            return json.loads(text_content)
                        except json.JSONDecodeError:
                            print(f"Warning: LLM response was not valid JSON: {part['text']}")
                            # If not valid JSON, return a basic error structure
                            return {"summary": "LLM response could not be parsed as JSON.", "recommendations": []}
        
        return {"summary": "No valid content found in LLM response.", "recommendations": []}

    except httpx.RequestError as e:
        return {"summary": f"Network or HTTP error during LLM call: {e}", "recommendations": []}
    except Exception as e:
        return {"summary": f"An unexpected error occurred: {e}", "recommendations": []}

