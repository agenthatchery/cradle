import os
import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger(__name__)

# AgentPlaybooks MCP Management Client
# Provides the Cradle agent with full CRUD access to AgentPlaybooks.ai:
# - Create/manage playbooks (external brain containers)
# - Write/read/search persistent memory (survives container restarts)
# - Create/list skills (documented capabilities)
# Two endpoints:
#   /api/mcp/manage - Management API (create playbooks, skills) - uses User API Key (apb_live_...)
#   /api/mcp/{guid} - Playbook API (read/write memory, use skills) - uses Playbook API Key

BASE_URL = "https://agentplaybooks.ai"

def _mcp_request(endpoint: str, method: str, tool_name: str, arguments: dict, api_key: str) -> str:
    """Internal: makes a JSON-RPC call to an MCP endpoint."""
    url = f"{BASE_URL}{endpoint}"
    
    payload = {
        "jsonrpc": "2.0",
        "id": "cradle-1",
        "method": method,
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    data = json.dumps(payload).encode('utf-8')
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Cradle/1.0"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            if "error" in resp_data:
                return f"MCP Error: {json.dumps(resp_data['error'])}"
            result = resp_data.get("result", {})
            # MCP tools/call returns { content: [{ text: "..." }] }
            if isinstance(result, dict) and "content" in result:
                texts = [c.get("text", "") for c in result["content"] if c.get("type") == "text"]
                return "\n".join(texts) if texts else json.dumps(result, indent=2)
            return json.dumps(result, indent=2)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return f"HTTP Error {e.code}: {error_body}"
    except Exception as e:
        return f"Failed to call AgentPlaybooks: {str(e)}"


def manage_playbooks(tool_name: str, arguments: str) -> str:
    """
    Manage playbooks and skills on AgentPlaybooks.ai. This is your external brain management system.
    
    Available tool_name values:
    - list_playbooks: List all your playbooks. arguments: {}
    - create_playbook: Create a new playbook. arguments: {"name": "...", "description": "...", "visibility": "public"}
    - update_playbook: Update playbook metadata. arguments: {"playbook_id": "uuid", "name": "...", "description": "..."}
    - get_playbook: Get playbook details. arguments: {"playbook_id": "uuid"}
    - create_skill: Add a skill. arguments: {"playbook_id": "uuid", "name": "...", "description": "...", "code": "...", "input_schema": {...}}
    - update_skill: Update an existing skill. arguments: {"skill_id": "uuid", "name": "...", "code": "..."}
    - delete_skill: Remove a skill. arguments: {"skill_id": "uuid"}
    - list_skills: List skills. arguments: {"playbook_id": "uuid"}
    - list_skill_versions: List versions of a skill. arguments: {"skill_id": "uuid"}
    - rollback_skill: Rollback a skill to a previous version. arguments: {"skill_id": "uuid", "version_id": "uuid"}
    - write_memory: Store memory. arguments: {"playbook_id": "uuid", "key": "...", "value": {...}, "tags": [...]}
    - read_memory: Read memory. arguments: {"playbook_id": "uuid", "key": "..."}
    - search_memory: Search. arguments: {"playbook_id": "uuid", "search": "...", "tags": [...]}
    - delete_memory: Delete. arguments: {"playbook_id": "uuid", "key": "..."}
    
    The arguments parameter must be a valid JSON string.
    """
    api_key = os.environ.get("AGENTPLAYBOOKS_KEY")
    if not api_key:
        return "Failed: AGENTPLAYBOOKS_KEY not set. Ask your creator for an apb_live_... key."
    
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        return f"Invalid JSON arguments: {arguments}"
    
    return _mcp_request("/api/mcp/manage", "tools/call", tool_name, args, api_key)


def playbook_memory(tool_name: str, arguments: str) -> str:
    """
    Interact with a specific playbook's memory and skills on AgentPlaybooks.ai.
    This is faster for frequent read/write operations on a known playbook.
    
    Available tool_name values:
    - read_memory: Read a memory entry. arguments: {"key": "..."}
    - write_memory: Write a memory entry. arguments: {"key": "...", "value": {...}, "tags": [...]}
    - search_memory: Search memories. arguments: {"search": "...", "tags": [...]}
    - list_skills: List all skills. arguments: {}
    - get_skill: Get skill details. arguments: {"skill_id": "..."}
    - update_skill: Update skill. arguments: {"skill_id": "...", "name": "...", "code": "..."}
    
    The arguments parameter must be a valid JSON string.
    """
    guid = os.environ.get("PLAYBOOK_GUID")
    api_key = os.environ.get("PLAYBOOK_API_KEY") or os.environ.get("AGENTPLAYBOOKS_KEY")
    
    if not guid:
        return "Failed: PLAYBOOK_GUID not set. Use manage_playbooks('list_playbooks', '{}') to find your playbook GUID."
    
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        return f"Invalid JSON arguments: {arguments}"
    
    key = api_key or ""
    return _mcp_request(f"/api/mcp/{guid}", "tools/call", tool_name, args, key)

# ===== RLM TIERED MEMORY =====
def store_tiered_memory(data_key: str, value: dict, tier: str = "working") -> str:
    """
    Stores memory into one of four RLM (Recursive Language Model) tiers:
    - working: Short-term scratchpad for current task.
    - episodic: Logs of past events/ticks.
    - semantic: Generalized knowledge, facts, project structure.
    - archival: Deep long-term storage, compressed.
    """
    if tier not in ["working", "episodic", "semantic", "archival"]:
        return "Invalid tier. Must be working, episodic, semantic, or archival."
        
    # Deduplication check
    existing_memories = read_tiered_memory(tier)
    val_str = json.dumps(value) if isinstance(value, dict) else str(value)
    
    if "No memories found" not in existing_memories:
        # Check if the memory payload is effectively identical to an existing block
        if val_str[:150] in existing_memories:
             return f"Memory skipped (duplicate): Highly similar data already exists in tier '{tier}'."
             
    tags = ["rlm_memory", f"tier:{tier}"]
    playbook_id = os.environ.get("PLAYBOOK_ID")
    args = json.dumps({"playbook_id": playbook_id, "key": data_key, "value": value, "tags": tags})
    return manage_playbooks("write_memory", args)

def read_tiered_memory(tier: str = "working") -> str:
    """Retrieves all memories currently residing in the specified RLM tier."""
    if tier not in ["working", "episodic", "semantic", "archival"]:
        return "Invalid tier."
    playbook_id = os.environ.get("PLAYBOOK_ID")
    args = json.dumps({"playbook_id": playbook_id, "search": "", "tags": ["rlm_memory", f"tier:{tier}"]})
    return manage_playbooks("search_memory", args)

def update_canvas(canvas_id: str, content: str) -> str:
    """
    Updates a collaborative canvas used to share state between the 
    main autonomous loop and the Swarm sub-agents.
    """
    playbook_id = os.environ.get("PLAYBOOK_ID")
    args = json.dumps({
        "playbook_id": playbook_id,
        "key": f"canvas:{canvas_id}",
        "value": {"content": content},
        "tags": ["collaborative_canvas"]
    })
    return manage_playbooks("write_memory", args)
