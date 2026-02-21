"""
Intelligent Multi-Model Router for Cradle (v3)
=================================================
5 providers, 20+ models, 3 tiers, automatic fallback chains.

Providers: Gemini (Google), OpenAI, MiniMax, Groq (free), OpenRouter (free)

Tiers:
  STRATEGIST — Complex planning, architecture, critical user interactions
  WORKHORSE  — Routine tasks, autonomous ticks, tool calls  
  SCOUT      — Research, simple queries, ultimate fallback
"""

import os
import json
import time
import logging
import urllib.request

logger = logging.getLogger(__name__)

MODELS = {
    # === TIER 1: STRATEGIST ===
    "gemini-3.1-pro": {
        "tier": "strategist", "provider": "gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro:generateContent",
        "cost_input": 1.25, "cost_output": 10.0, "rpm": 5, "quality": 95,
    },
    "minimax-m2.5": {
        "tier": "strategist", "provider": "minimax",
        "endpoint": "https://api.minimax.io/v1/text/chatcompletion_v2",
        "model_id": "MiniMax-M2.5",
        "cost_input": 0.30, "cost_output": 1.10, "rpm": 20, "quality": 88,
        "note": "Coding plan key, ~100 req/5h. 80% SWE-Bench. USE AS SECOND FALLBACK.",
    },
    "gemini-2.5-pro": {
        "tier": "strategist", "provider": "gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
        "cost_input": 1.25, "cost_output": 10.0, "rpm": 5, "quality": 90,
    },
    "openai-gpt5-mini": {
        "tier": "strategist", "provider": "openai",
        "model_id": "gpt-5-mini",
        "cost_input": 0.25, "cost_output": 2.0, "rpm": 60, "quality": 85,
    },
    "or-deepseek-r1": {
        "tier": "strategist", "provider": "openrouter",
        "model_id": "deepseek/deepseek-r1-0528:free",
        "cost_input": 0, "cost_output": 0, "rpm": 20, "rpd": 1000, "quality": 87,
    },
    "or-qwen3-coder": {
        "tier": "strategist", "provider": "openrouter",
        "model_id": "qwen/qwen3-coder:free",
        "cost_input": 0, "cost_output": 0, "rpm": 20, "rpd": 1000, "quality": 85,
    },

    # === TIER 2: WORKHORSE ===
    "gemini-2.5-flash": {
        "tier": "workhorse", "provider": "gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "cost_input": 0.30, "cost_output": 2.50, "rpm": 10, "quality": 75,
    },
    "minimax-m2.5-wh": {
        "tier": "workhorse", "provider": "minimax",
        "endpoint": "https://api.minimax.io/v1/text/chatcompletion_v2",
        "model_id": "MiniMax-M2.5",
        "cost_input": 0.30, "cost_output": 1.10, "rpm": 20, "quality": 88,
        "note": "Same model, second fallback in workhorse chain too.",
    },
    "openai-gpt5-nano": {
        "tier": "workhorse", "provider": "openai",
        "model_id": "gpt-5-nano",
        "cost_input": 0.05, "cost_output": 0.40, "rpm": 200, "quality": 65,
    },
    "openai-gpt4.1-nano": {
        "tier": "workhorse", "provider": "openai",
        "model_id": "gpt-4.1-nano",
        "cost_input": 0.10, "cost_output": 0.40, "rpm": 200, "quality": 60,
    },
    "groq-kimi-k2": {
        "tier": "workhorse", "provider": "groq",
        "model_id": "moonshotai/kimi-k2-instruct",
        "cost_input": 0, "cost_output": 0, "rpm": 30, "rpd": 1000, "quality": 74,
    },
    "groq-llama-3.3-70b": {
        "tier": "workhorse", "provider": "groq",
        "model_id": "llama-3.3-70b-versatile",
        "cost_input": 0, "cost_output": 0, "rpm": 30, "rpd": 1000, "quality": 72,
    },
    "or-hermes-405b": {
        "tier": "workhorse", "provider": "openrouter",
        "model_id": "nousresearch/hermes-3-llama-3.1-405b:free",
        "cost_input": 0, "cost_output": 0, "rpm": 20, "rpd": 1000, "quality": 73,
    },

    # === TIER 3: SCOUT ===
    "groq-llama4-scout": {
        "tier": "scout", "provider": "groq",
        "model_id": "meta-llama/llama-4-scout-17b-16e-instruct",
        "cost_input": 0, "cost_output": 0, "rpm": 30, "rpd": 14400, "quality": 60,
    },
    "groq-llama-8b": {
        "tier": "scout", "provider": "groq",
        "model_id": "llama-3.1-8b-instant",
        "cost_input": 0, "cost_output": 0, "rpm": 30, "rpd": 14400, "quality": 55,
    },
    "openai-gpt4.1-nano-scout": {
        "tier": "scout", "provider": "openai",
        "model_id": "gpt-4.1-nano",
        "cost_input": 0.10, "cost_output": 0.40, "rpm": 200, "quality": 60,
    },
    "or-qwen3-next-80b": {
        "tier": "scout", "provider": "openrouter",
        "model_id": "qwen/qwen3-next-80b-a3b-instruct:free",
        "cost_input": 0, "cost_output": 0, "rpm": 20, "rpd": 1000, "quality": 65,
    },
    "or-free-auto": {
        "tier": "scout", "provider": "openrouter",
        "model_id": "openrouter/auto",
        "cost_input": 0, "cost_output": 0, "rpm": 20, "rpd": 1000, "quality": 50,
    },
}

# MiniMax is ALWAYS second fallback (user request: coding plan, best value)
FALLBACK_CHAINS = {
    "strategist": [
        "gemini-3.1-pro", "minimax-m2.5",       # Primary + second fallback
        "gemini-2.5-pro", "openai-gpt5-mini",
        "or-deepseek-r1", "or-qwen3-coder",
        "gemini-2.5-flash",
    ],
    "workhorse": [
        "gemini-2.5-flash", "minimax-m2.5-wh",  # Primary + second fallback
        "openai-gpt5-nano", "openai-gpt4.1-nano",
        "groq-kimi-k2", "groq-llama-3.3-70b",
        "or-hermes-405b",
    ],
    "scout": [
        "groq-llama4-scout", "groq-llama-8b",
        "openai-gpt4.1-nano-scout",
        "or-qwen3-next-80b", "or-free-auto",
    ],
}

_request_counts = {}

def _check_rate_limit(model_name):
    model = MODELS[model_name]
    now = time.time()
    today = time.strftime("%Y-%m-%d")
    if model_name not in _request_counts:
        _request_counts[model_name] = {"minute": now, "count": 0, "day_count": 0, "day": today}
    s = _request_counts[model_name]
    if now - s["minute"] > 60:
        s["minute"] = now
        s["count"] = 0
    if s["day"] != today:
        s["day"] = today
        s["day_count"] = 0
    if s["count"] >= model.get("rpm", 999):
        return False
    if "rpd" in model and s["day_count"] >= model["rpd"]:
        return False
    return True

def _record_request(model_name):
    if model_name not in _request_counts:
        _request_counts[model_name] = {"minute": time.time(), "count": 0, "day_count": 0, "day": time.strftime("%Y-%m-%d")}
    _request_counts[model_name]["count"] += 1
    _request_counts[model_name]["day_count"] += 1

def _get_api_key(provider):
    return {
        "gemini": os.environ.get("GEMINI_API_KEY", ""),
        "openai": os.environ.get("OPENAI_API_KEY", ""),
        "groq": os.environ.get("GROQ_API_KEY", ""),
        "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
        "minimax": os.environ.get("MINIMAX_API_KEY", ""),
    }.get(provider, "")

def _call_gemini(model_name, system_prompt, user_prompt):
    api_key = _get_api_key("gemini")
    url = f"{MODELS[model_name]['endpoint']}?key={api_key}"
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"]

def _call_openai_compatible(model_name, system_prompt, user_prompt):
    model = MODELS[model_name]
    provider = model["provider"]
    api_key = _get_api_key(provider)
    endpoint = model.get("endpoint", {
        "openai": "https://api.openai.com/v1/chat/completions",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        "minimax": "https://api.minimax.io/v1/text/chatcompletion_v2",
    }.get(provider, ""))
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/agenthatchery/cradle"
        headers["X-Title"] = "Cradle Agent"
    payload = json.dumps({
        "model": model.get("model_id", model_name),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }).encode()
    req = urllib.request.Request(endpoint, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]

def route_request(tier, system_prompt, user_prompt, max_retries=2):
    chain = FALLBACK_CHAINS.get(tier, FALLBACK_CHAINS["workhorse"])
    for model_name in chain:
        model = MODELS[model_name]
        api_key = _get_api_key(model["provider"])
        if not api_key:
            continue
        if not _check_rate_limit(model_name):
            logger.warning(f"Skipping {model_name}: rate limited")
            continue
        for attempt in range(max_retries):
            try:
                logger.info(f"[{model_name}] Calling (attempt {attempt+1})...")
                _record_request(model_name)
                if model["provider"] == "gemini":
                    response = _call_gemini(model_name, system_prompt, user_prompt)
                else:
                    response = _call_openai_compatible(model_name, system_prompt, user_prompt)
                logger.info(f"[{model_name}] Success ({len(response)} chars)")
                return response, model_name
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "rate" in error_str.lower():
                    logger.warning(f"[{model_name}] Rate limited. Instantly falling back to next provider...")
                    break
                else:
                    logger.error(f"[{model_name}] Error: {error_str}")
                    break
    return "All models in the fallback chain failed.", "none"

def get_model_status():
    lines = ["=== Model Router v3 — 5 Providers, 20+ Models ==="]
    for tier in ["strategist", "workhorse", "scout"]:
        lines.append(f"\n[{tier.upper()}]")
        for name in FALLBACK_CHAINS[tier]:
            model = MODELS[name]
            api_key = _get_api_key(model["provider"])
            key_ok = "✅" if api_key else "❌"
            cost = f"${model['cost_input']}/M" if model['cost_input'] > 0 else "FREE"
            state = _request_counts.get(name, {})
            used = f"used {state.get('day_count', 0)}/{model.get('rpd', '∞')} today" if state else "unused"
            lines.append(f"  {key_ok} {name:30s} [{model['provider']:>10s}] {cost:>8s}  Q={model['quality']}  {used}")
    return "\n".join(lines)
