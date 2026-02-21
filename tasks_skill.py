import json
import uuid
import datetime
from agentplaybooks_tools import manage_playbooks

def enqueue_task(goal: str, priority: int = 5) -> str:
    """
    Adds a new task to the background execution queue.
    The heartbeat processor will pick this up according to priority.
    
    Arguments:
    - goal: The natural language description of what the agent should do.
    - priority: 1 (highest) to 10 (lowest). Default is 5.
    """
    task_id = str(uuid.uuid4())[:8]
    task_obj = {
        "id": task_id,
        "goal": goal,
        "priority": int(priority),
        "status": "pending",
        "created_at": datetime.datetime.now().isoformat(),
        "log": []
    }
    
    args = json.dumps({
        "key": f"task:{task_id}",
        "value": task_obj,
        "tags": ["pending_task", f"priority:{priority}"]
    })
    
    res = manage_playbooks("write_memory", args)
    if "Failed" in res or "error" in res.lower():
        return f"Failed to enqueue task: {res}"
    
    return f"Task enqueued. ID: {task_id}. Goal: {goal}"

def list_tasks(status: str = "pending") -> str:
    """
    Lists tasks from the background queue filtered by status.
    Available statuses: pending, processing, completed, failed.
    """
    tag = f"{status}_task"
    args = json.dumps({
        "search": "",
        "tags": [tag]
    })
    
    res = manage_playbooks("search_memory", args)
    if "Failed" in res or "error" in res.lower():
        return f"Error listing tasks: {res}"
        
    try:
        tasks = json.loads(res)
        if not tasks:
            return f"No tasks found with status: {status}"
            
        summary = [f"--- {status.upper()} TASKS ---"]
        for t in tasks:
            v = t.get("value", {})
            if isinstance(v, str): v = json.loads(v)
            summary.append(f"[{v.get('id')}] Priority: {v.get('priority')} | Goal: {v.get('goal')}")
            
        return "\n".join(summary)
    except Exception as e:
        return f"Failed to parse task list: {str(e)}"
