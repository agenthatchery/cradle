import os
import json
from agentplaybooks_tools import manage_playbooks
from dotenv import load_dotenv

load_dotenv()
playbook_id = os.environ.get("PLAYBOOK_ID")

with open("/app/search_web.py", "r") as f:
    code = f.read()

args = json.dumps({
    "playbook_id": playbook_id,
    "name": "search_web",
    "description": "Searches the internet for information matching the query using the DuckDuckGo Lite HTML interface and returns a summary of the top results.",
    "code": code,
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            }
        },
        "required": ["query"]
    }
})

print("Migrating search_web to AgentPlaybooks...")
res = manage_playbooks("create_skill", args)
print("Result:")
print(res)
