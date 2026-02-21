import time
import logging
import json
import agent
import concurrent.futures
import os
from agentplaybooks_tools import manage_playbooks

logger = logging.getLogger(__name__)

# Parallel executor for background tasks
task_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

def execute_single_task(task_id, goal, val):
    """Worker function to execute a single task in a thread."""
    try:
        logger.info(f"Heartbeat [Task {task_id}]: Starting...")
        
        # 3. Execute the task via Agent
        # We use agent.process_message as the task engine
        result = agent.process_message(f"BACKGROUND TASK EXECUTION (ID: {task_id}): {goal}")
        
        # 4. Mark as completed
        val["status"] = "completed"
        val["result"] = result
        val["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        
        playbook_id = os.environ.get("PLAYBOOK_ID")
        manage_playbooks("write_memory", json.dumps({
            "playbook_id": playbook_id,
            "key": f"task:{task_id}",
            "value": val,
            "tags": ["completed_task", f"id:{task_id}"]
        }))
        logger.info(f"Heartbeat [Task {task_id}]: Completed.")
        
    except Exception as e:
        logger.error(f"Heartbeat [Task {task_id}]: Failed: {e}")
        val["status"] = "failed"
        val["error"] = str(e)
        playbook_id = os.environ.get("PLAYBOOK_ID")
        manage_playbooks("write_memory", json.dumps({
            "playbook_id": playbook_id,
            "key": f"task:{task_id}",
            "value": val,
            "tags": ["failed_task", f"id:{task_id}"]
        }))

def heartbeat_step():
    """
    Advanced Heartbeat:
    1. Scans for 'pending_task'.
    2. Sorts by priority.
    3. Dispatches to multi-threaded executor.
    """
    logger.debug("Heartbeat: Checking for pending work...")
    
    playbook_id = os.environ.get("PLAYBOOK_ID")
    args = json.dumps({
        "playbook_id": playbook_id,
        "search": "",
        "tags": ["pending_task"]
    })
    
    res = manage_playbooks("search_memory", args)
    if not res or "Failed" in res or "error" in res.lower():
        return
    
    try:
        data = json.loads(res)
        if not isinstance(data, list) or not data:
            return
            
        # Parse and sort by priority (1 is highest)
        task_list = []
        for item in data:
            val = item.get("value", {})
            if isinstance(val, str): 
                try: val = json.loads(val)
                except: continue
            
            if val.get("status") == "pending":
                task_list.append((val.get("priority", 5), val))
        
        # Sort by priority ascending
        task_list.sort(key=lambda x: x[0])
        
        for priority, val in task_list:
            task_id = val.get("id")
            goal = val.get("goal")
            
            val["status"] = "processing"
            val["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            manage_playbooks("write_memory", json.dumps({
                "playbook_id": os.environ.get("PLAYBOOK_ID"),
                "key": f"task:{task_id}",
                "value": val,
                "tags": ["processing_task", f"id:{task_id}"]
            }))
            
            # Dispatch to thread pool
            task_executor.submit(execute_single_task, task_id, goal, val)
            logger.info(f"Heartbeat: Dispatched Task {task_id} (Priority {priority})")
            
    except Exception as e:
        logger.error(f"Heartbeat processing error: {e}")

def run_heartbeat_loop(interval=30):
    """Indefinite loop for background heartbeat."""
    logger.info("Advanced Heartbeat Service active (Parallel Mode).")
    while True:
        try:
            heartbeat_step()
        except Exception as e:
            logger.error(f"Heartbeat loop crash-prevented: {e}")
        time.sleep(interval)
