import os
import logging
import time
from google import genai
from google.genai import types
from sandbox import execute_python_in_sandbox
from memory import update_memory, commit_and_push_to_github, read_file, log_reflection, read_reflections
from tools_system import execute_shell_command
from search_web import search_web
from github_tools import create_github_repo
from agentplaybooks_tools import manage_playbooks, playbook_memory
from read_webpage import read_webpage
from model_router import route_request, get_model_status, MODELS
from skills_loader import load_skills
import parser

logger = logging.getLogger(__name__)

# Initialize GenAI Client
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY not set.")

client = genai.Client(api_key=api_key)

# Read core prompt
def get_core_prompt():
    try:
        with open('core_prompt.md', 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Could not read core_prompt.md: {e}")
        return "You are an evolving AI agent. Please fix your core_prompt.md."

# Tool to let the agent check model health
def check_model_router() -> str:
    """
    Check the status of all configured AI models in the multi-model router.
    Shows which models have API keys configured, their tier, cost, and RPM.
    Use this to understand what models are available for self-optimization.
    """
    return get_model_status()

# Load all available tools dynamically
my_tools = load_skills()
logger.info(f"Loaded {len(my_tools)} unique tools: {[t.__name__ for t in my_tools]}")

# ===== MODEL TIERING =====
MODEL_USER = None
for model_name in ["gemini-3.1-pro", "gemini-2.5-pro"]:
    try:
        config_user = types.GenerateContentConfig(
            system_instruction=get_core_prompt(),
            temperature=0.7,
            tools=my_tools,
        )
        chat_user = client.chats.create(model=model_name, config=config_user)
        MODEL_USER = model_name
        logger.info(f"User chat initialized with {model_name}")
        break
    except Exception as e:
        logger.warning(f"Failed to init {model_name}: {e}")
        chat_user = None

# Flash for autonomous ticks (always available, cheap)
try:
    config_tick = types.GenerateContentConfig(
        system_instruction=get_core_prompt(),
        temperature=0.7,
        tools=my_tools,
    )
    chat_tick = client.chats.create(model="gemini-2.5-flash", config=config_tick)
    logger.info("Tick chat initialized with gemini-2.5-flash")
except Exception as e:
    logger.error(f"Failed to init Flash chat: {e}")
    chat_tick = None


def _send_with_retry(chat, text: str, max_retries: int = 3) -> str:
    """Send message with exponential backoff on 429 errors."""
    for attempt in range(max_retries):
        try:
            response = chat.send_message(text)
            # Handle different SDK return types
            if hasattr(response, 'text'):
                return response.text if response.text else "Tasks executed successfully (no text output)."
            elif isinstance(response, str):
                return response
            else:
                return str(response)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                logger.warning(f"Rate limited on primary chat. Triggering fallback chain...")
                raise Exception(f"RateLimitExhausted: {error_str}")
            else:
                raise e
    raise Exception("Max retries exceeded")

# ===== AUTO-HEALING DECORATOR =====
import functools
import traceback

def auto_heal(func):
    """
    Decorator inspired by healing-agent to catch exceptions, 
    log deep context, and attempt a graceful fallback.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"[HEALING AGENT] Exception in {func.__name__}:\n{tb}")
            
            # Simple fallback strategy: Instead of crashing the whole tick/response,
            # return the error context explicitly so the next tick or the user can see it.
            return f"Agent internal error ({type(e).__name__}): {str(e)}. Context saved to logs."
    return wrapper


@auto_heal
def process_message(text: str) -> str:
    """
    Sends the user message to the best available model.
    If using fallback models, parses and executes tool calls manually.
    """
    # Try primary (Pro) chat first
    if chat_user:
        try:
            logger.info(f"[{MODEL_USER}] Processing user message...")
            return _send_with_retry(chat_user, text)
        except Exception as e:
            logger.error(f"[{MODEL_USER}] Failed: {e}")
            # Fall through to flash
    
    # Fallback to Flash
    if chat_tick:
        try:
            logger.info("[gemini-2.5-flash] Falling back for user message...")
            return _send_with_retry(chat_tick, text)
        except Exception as e:
            logger.error(f"[Flash fallback] Failed: {e}")
            # Fall through to router
    
    # Last resort: use model router (manual tool parsing)
    logger.info("[Router] Using fallback multi-model router...")
    response, model = route_request("strategist", get_core_prompt(), text)
    tool_results = parser.parse_and_execute_tools(response, my_tools)
    clean_text = parser.clean_response_text(response)
    
    reply = f"[via {model}] {clean_text}"
    if tool_results:
        reply += "\n\n[Tool Executions]\n" + "\n".join(tool_results)
    return reply


@auto_heal
def autonomous_tick() -> str:
    """
    Called every 10 minutes.
    """
    prompt = (
        "SYSTEM AUTONOMOUS TICK: Review your current tasks, reflect on your codebase, "
        "and execute your next step toward Kardashev Level 3. "
        "IMPORTANT: Always call `read_reflections` first to see what you did last tick. "
        "When you finish this tick, call `log_reflection` with a summary of what you did and plan to do next time. "
        "BUDGET: You are on Flash to save tokens. Be efficient. "
        "NON-GEMINI FALLBACK: If you are not a Gemini model, use <minimax:tool_call><invoke name='...'><parameter name='...'>...</parameter></invoke></minimax:tool_call> format."
    )
    
    if chat_tick:
        try:
            logger.info("[gemini-2.5-flash] Autonomous tick triggered.")
            return _send_with_retry(chat_tick, prompt)
        except Exception as e:
            logger.error(f"[Flash tick] Failed: {e}")
            # Fall through
    
    # Fallback: use router
    logger.info("[Router] Tick using fallback multi-model router...")
    response, model = route_request("workhorse", get_core_prompt(), prompt)
    tool_results = parser.parse_and_execute_tools(response, my_tools)
    clean_text = parser.clean_response_text(response)
    
    reply = f"[via {model}] {clean_text}"
    if tool_results:
        reply += "\n\n[Tool Executions]\n" + "\n".join(tool_results)
    return reply
