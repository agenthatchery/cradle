import os
import logging
import concurrent.futures
import time
import uuid
from google import genai
from google.genai import types

# Optional: You can import tools if sub-agents need them natively, 
# but for now we'll start with lightweight research/analysis sub-agents.
try:
    from skills_loader import load_skills
    SWARM_TOOLS = load_skills()
except ImportError:
    SWARM_TOOLS = []

logger = logging.getLogger(__name__)

# Try to get API key
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

api_key = os.environ.get("GEMINI_API_KEY")

def execute_sub_agent_task(task_prompt: str, dnid_context: str = "", model_name: str = "gemini-2.5-flash") -> str:
    """
    Spawns a single sub-agent to execute a specific task.
    Supports a 'DNID' (Distributed Network Identity) context string to optionally 
    give the agent a specific persona, role, or ID in the swarm.
    """
    if not api_key:
        return "Error: GEMINI_API_KEY not found."

    client = genai.Client(api_key=api_key)
    
    # Base swarm prompt + optional DNID context
    system_instruction = (
        "You are a focused Sub-Agent in a Swarm. "
        "Your only job is to complete the specific task given to you as accurately and efficiently as possible. "
        "Do not apologize or use conversational filler. Return only the result."
    )
    if dnid_context:
        system_instruction += f"\n[DNID Context]: {dnid_context}"

    try:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.4,
            # tools=SWARM_TOOLS,
        )
        
        logger.info(f"Sub-agent dispatching task to {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=task_prompt,
            config=config
        )
        if hasattr(response, 'text') and response.text:
            return response.text
        return "Sub-agent returned empty result."
        
    except Exception as e:
        logger.error(f"Sub-agent execution failed: {e}")
        return f"Sub-Agent Error: {str(e)}"

def dispatch_swarm(tasks: list[str], shared_context: str = "", max_workers: int = 3) -> dict:
    """
    Dispatches multiple tasks to a swarm of sub-agents in parallel.
    Returns a dictionary mapping task IDs to their results.
    We retain the concept of 'DNID' by assigning each worker a unique identity.
    """
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a future for each task, injecting a mock DNID
        future_to_task = {}
        for idx, task in enumerate(tasks):
            # Generate a pseudo-DNID for the worker
            worker_dnid = f"Worker-{uuid.uuid4().hex[:6]}-Role-{idx+1}"
            context = f"Your Distributed Identity (DNID) is: {worker_dnid}. Shared Mission Context: {shared_context}"
            
            future = executor.submit(execute_sub_agent_task, task, context)
            future_to_task[future] = (worker_dnid, task)
            
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_task):
            worker_dnid, original_task = future_to_task[future]
            try:
                result = future.result(timeout=120)  # 2 min timeout
                results[worker_dnid] = result
                logger.info(f"Swarm worker {worker_dnid} completed task.")
            except Exception as exc:
                logger.error(f"Swarm worker {worker_dnid} generated an exception: {exc}")
                results[worker_dnid] = f"CRITICAL FAILURE: {exc}"
                
    return results

if __name__ == "__main__":
    # Quick test if run directly
    print("Testing Basic Swarm Dispatch...")
    sample_tasks = [
        "Explain the concept of an LLM Swarm in 2 sentences.",
        "Write a python function to calculate fibonacci recursively.",
        "What is the capital of France?"
    ]
    res = dispatch_swarm(sample_tasks, shared_context="You are testing the new Hatchery swarm capabilities.", max_workers=3)
    for worker, output in res.items():
        print(f"\n--- {worker} ---\n{output}")
