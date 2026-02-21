import json
import uuid
import datetime
import os
from agentplaybooks_tools import manage_playbooks

def enqueue_task(goal: str, priority: int = 5, parent_task_id: str = None, assigned_agent: str = None) -> str:
    """
    Adds a new task to the background execution queue.
    Checks for exact or highly similar duplicates first.
    """
    # 1. Deduplication check
    existing_tasks = list_tasks("pending")
    if "No tasks found" not in existing_tasks:
        check_prefix = goal[:80]
        if check_prefix in existing_tasks:
            return f"Task skipped (duplicate): A pending task with a matching goal already exists."
            
    task_id = str(uuid.uuid4())[:8]
    task_obj = {
        "id": task_id,
        "goal": goal,
        "priority": priority,
        "status": "pending",
        "parent_task_id": parent_task_id,
        "assigned_agent": assigned_agent,
        "created_at": datetime.datetime.now().isoformat(),
        "log": []
    }
    
    playbook_id = os.environ.get("PLAYBOOK_ID")
    args = json.dumps({
        "playbook_id": playbook_id,
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
    """
    tag = f"{status}_task"
    playbook_id = os.environ.get("PLAYBOOK_ID")
    args = json.dumps({
        "playbook_id": playbook_id,
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
        seen_goals = set()
        for t in tasks:
            v = t.get("value", {})
            if isinstance(v, str):
                try: v = json.loads(v)
                except: pass
            
            goal = v.get("goal")
            if not goal: continue
            
            # Client-side deduplication to handle server-side orphans
            if goal in seen_goals:
                continue
            seen_goals.add(goal)
            
            summary.append(f"[{v.get('id', 'unknown')}] Priority: {v.get('priority', '5')} | Goal: {goal}")
            
        return "\n".join(summary)
    except Exception as e:
        return f"Failed to parse task list: {str(e)}"
