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

logger = logging.getLogger(__name__)

# Initialize GenAI Client (for the SDK-based chat with automatic function calling)
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

# Load all available tools dynamically from base and skills/ directory
my_tools = load_skills()

# ===== MODEL TIERING (via Google GenAI SDK for automatic function calling) =====
# The SDK handles the tool-calling loop automatically.
# We use FLASH for autonomous ticks (cheap) and PRO for user messages (quality).
# Gemini 3.1 Pro is the latest (Feb 19, 2026) — try it first with fallback to 2.5.
# For non-Gemini models, the router is used via route_request() in process_message_simple().

# Try Gemini 3.1 Pro first, fall back to 2.5 Pro for user chat
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
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait_time = min(60, (2 ** attempt) * 10)
                logger.warning(f"Rate limited (attempt {attempt+1}/{max_retries}). Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e
    return f"Rate limited after {max_retries} retries. Will try again next tick."


def process_message(text: str) -> str:
    """
    Sends the user message to the best available model (Gemini 3.1 Pro → 2.5 Pro → Flash).
    Uses the GenAI SDK with automatic function calling for tool usage.
    """
    # Try primary (Pro) chat first
    if chat_user:
        try:
            logger.info(f"[{MODEL_USER}] Processing user message...")
            return _send_with_retry(chat_user, text)
        except Exception as e:
            logger.error(f"[{MODEL_USER}] Failed: {e}")
    
    # Fallback to Flash
    if chat_tick:
        try:
            logger.info("[gemini-2.5-flash] Falling back for user message...")
            return _send_with_retry(chat_tick, text)
        except Exception as e:
            logger.error(f"[Flash fallback] Failed: {e}")
    
    # Last resort: use model router (no tool calling, but still responds)
    try:
        response, model = route_request("strategist", get_core_prompt(), text)
        return f"[via {model}] {response}"
    except Exception as e:
        return f"All models failed: {e}"


def autonomous_tick() -> str:
    """
    Called every 10 minutes. Uses Flash model (cheaper, faster, higher rate limit).
    Falls back through the model router if Flash is unavailable.
    """
    if chat_tick:
        try:
            logger.info("[gemini-2.5-flash] Autonomous tick triggered.")
            prompt = (
                "SYSTEM AUTONOMOUS TICK: Review your current tasks, reflect on your codebase, "
                "and execute your next step toward Kardashev Level 3. "
                "IMPORTANT: Always call `read_reflections` first to see what you did last tick. "
                "When you finish this tick, call `log_reflection` with a summary of what you did and plan to do next time. "
                "BUDGET: You are on Flash to save tokens. Be efficient. "
                "TIP: Call `check_model_router` to see which models are available."
            )
            return _send_with_retry(chat_tick, prompt)
        except Exception as e:
            logger.error(f"[Flash tick] Failed: {e}")
    
    # Fallback: use router for a simple tick
    try:
        response, model = route_request("workhorse", get_core_prompt(),
            "Autonomous tick: Read reflections, assess status, plan next step. Be brief.")
        return f"[via {model}] {response}"
    except Exception as e:
        return f"Tick failed: {e}"
