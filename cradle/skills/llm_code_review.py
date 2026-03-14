
import google.generativeai as genai
import json
import os

def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-pro')

def llm_code_review(file_content: str, file_path: str = "", diff: str = "") -> dict:
    """
    Performs an LLM-powered code review using Gemini 1.5 Pro.

    Args:
        file_content (str): The content of the file to review.
        file_path (str): The path to the file (optional, for context).
        diff (str): A diff string if only changes are to be reviewed (optional).

    Returns:
        dict: A JSON object with actionable recommendations.
    """
    model = setup_gemini()

    prompt = f"""You are an expert code reviewer. Perform a thorough code review for the following code. Focus on identifying potential bugs, security vulnerabilities, performance issues, and style guide violations. Provide actionable recommendations.

File Path: {file_path}

"""
    if diff:
        prompt += "Review the following diff:

" + diff + "

"
        prompt += "Consider the overall file context provided below, but prioritize the changes in the diff.

"
        prompt += "Full File Content (for context):

" + file_content
    else:
        prompt += "Code to review:

" + file_content

    prompt += "

Provide your review as a JSON object with a single key 'recommendations'. The value should be a list of objects, each with 'type' (e.g., 'bug', 'security', 'performance', 'style', 'refactor'), 'line_number' (if applicable, null otherwise), 'description', and 'severity' (e.g., 'critical', 'high', 'medium', 'low', 'info').

Example:
{{"recommendations": [
  {{"type": "bug", "line_number": 42, "description": "Potential off-by-one error in loop condition.", "severity": "high"}},
  {{"type": "security", "line_number": null, "description": "Consider input sanitization for user-provided data.", "severity": "medium"}},
  {{"type": "style", "line_number": 15, "description": "Missing docstring for function `my_func`.", "severity": "info"}}
]}}"

    try:
        response = model.generate_content(prompt)
        # The LLM might return markdown code block, try to parse it.
        text_response = response.text.strip()
        if text_response.startswith('```json') and text_response.endswith('```'):
            json_str = text_response[7:-3].strip()
        else:
            json_str = text_response
        return json.loads(json_str)
    except Exception as e:
        return {{"error": str(e), "raw_response": response.text if 'response' in locals() else "No response received"}}

