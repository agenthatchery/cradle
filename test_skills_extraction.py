from cradle.skills import SkillLoader

# Create a dummy skill loader to test python code extraction
skills = SkillLoader(None)
skills._cache = {
    "web_search": {
        "description": "desc",
        "content": """
```python
import os

def web_search(query: str):
    return [{"title": "test"}]

# Example usage:
results = web_search("test")
```
"""
    }
}

code = skills.get_relevant_skills_python("web search", "")
print("EXTRACTED CODE:")
print(code)
