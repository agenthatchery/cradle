
import json
import os
import httpx

async def llm_code_review(file_path: str, diff: str = None) -> dict:
    """
    Performs an LLM-powered code review on a given file or diff.

    Args:
        file_path (str): The path to the file to review.
        diff (str, optional): An optional diff string to review. If provided,
                              the LLM will focus on the changes.

    Returns:
        dict: A JSON object with actionable recommendations.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY environment variable not set."}

    try:
        with open(file_path, 'r') as f:
            file_content = f.read()
    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except Exception as e:
        return {"error": f"Error reading file {file_path}: {str(e)}"}

    prompt_parts = [
        "You are an expert code reviewer. Perform a thorough code review focusing on potential bugs, security vulnerabilities, performance issues, and style guide violations.",
        "Provide actionable recommendations in a JSON format. The JSON should be an array of objects, where each object has 'line' (int), 'type' (bug, security, performance, style, general), 'severity' (low, medium, high), and 'recommendation' (str).",
        "If the issue is general to the entire file or diff, set 'line' to 0.",
        "Here is the code to review:

",
        f"File: {file_path}
",
        "```
",
        file_content,
        "
```
"
    ]

    if diff:
        prompt_parts.append("Here is the diff to review (focus on these changes):

")
        prompt_parts.append("```diff
")
        prompt_parts.append(diff)
        prompt_parts.append("
```
")

    prompt_parts.append("Your JSON output should start immediately after this sentence, without any preceding text or markdown fences.")

    prompt = ''.join(prompt_parts)

    headers = {
        "Content-Type": "application/json",
    }
    json_data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 2048,
        }
    }

    # Using httpx for async request
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key={api_key}",
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            response.raise_for_status()
            response_data = response.json()

            # Extracting the text part from the response
            if 'candidates' in response_data and response_data['candidates']:
                first_candidate = response_data['candidates'][0]
                if 'content' in first_candidate and 'parts' in first_candidate['content']:
                    for part in first_candidate['content']['parts']:
                        if 'text' in part:
                            try:
                                # The model should output raw JSON, but sometimes adds markdown fences
                                raw_text = part['text'].strip()
                                if raw_text.startswith('```json') and raw_text.endswith('```'):
                                    raw_text = raw_text[7:-3].strip()
                                elif raw_text.startswith('```') and raw_text.endswith('```'): # Generic markdown
                                    raw_text = raw_text[3:-3].strip()

                                return json.loads(raw_text)
                            except json.JSONDecodeError as e:
                                return {"error": "Failed to parse LLM response as JSON", "llm_raw_response": part['text'], "details": str(e)}

            return {"error": "LLM response did not contain expected content structure.", "raw_response": response_data}

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error during LLM call: {e.response.status_code} - {e.response.text}"}
        except httpx.RequestError as e:
            return {"error": f"Network error during LLM call: {str(e)}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred during LLM call: {str(e)}"}

