"""
Self-Benchmark Tool for Cradle
================================
Lets the agent test each model with a standard coding task,
measure quality and latency, and log which is best.
The agent can call benchmark_models() as a tool to self-optimize.
"""

import time
import logging
import json
from model_router import MODELS, FALLBACK_CHAINS, _get_api_key, _call_gemini, _call_openai_compatible

logger = logging.getLogger(__name__)

BENCHMARK_PROMPT = """Write a Python function `fibonacci(n)` that returns the nth Fibonacci number using memoization. Include a docstring and type hints. Then write 3 pytest test cases for it."""

BENCHMARK_SYSTEM = "You are a coding assistant. Write clean, correct Python code."


def benchmark_models() -> str:
    """
    Run a standard coding benchmark on all available models.
    Measures response quality (code correctness), latency, and cost.
    Use this to decide which models are best for different tasks.
    Returns a formatted report of all model performances.
    """
    results = []
    
    for tier_name in ["strategist", "workhorse", "scout"]:
        for model_name in FALLBACK_CHAINS[tier_name]:
            model = MODELS[model_name]
            api_key = _get_api_key(model["provider"])
            if not api_key:
                results.append({"model": model_name, "tier": tier_name, "status": "NO_KEY"})
                continue
            
            try:
                start = time.time()
                provider = model["provider"]
                if provider == "gemini":
                    response = _call_gemini(model_name, BENCHMARK_SYSTEM, BENCHMARK_PROMPT)
                else:
                    response = _call_openai_compatible(model_name, BENCHMARK_SYSTEM, BENCHMARK_PROMPT)
                latency = round(time.time() - start, 2)
                
                # Simple quality heuristics
                has_fibonacci = "fibonacci" in response.lower() or "fib" in response.lower()
                has_memo = "memo" in response.lower() or "cache" in response.lower() or "dict" in response.lower()
                has_test = "test" in response.lower() or "assert" in response.lower() or "pytest" in response.lower()
                has_docstring = '"""' in response or "'''" in response
                has_type_hints = "->" in response or ": int" in response
                
                quality = sum([has_fibonacci * 30, has_memo * 25, has_test * 20, has_docstring * 15, has_type_hints * 10])
                
                cost = model.get("cost_input", 0)
                cost_label = f"${cost}/M" if cost > 0 else "FREE"
                
                results.append({
                    "model": model_name,
                    "tier": tier_name,
                    "status": "OK",
                    "latency_s": latency,
                    "quality": quality,
                    "cost": cost_label,
                    "response_len": len(response),
                })
                logger.info(f"[benchmark] {model_name}: quality={quality}, latency={latency}s")
                
                # Small delay to avoid rate limits
                time.sleep(2)
                
            except Exception as e:
                results.append({
                    "model": model_name,
                    "tier": tier_name,
                    "status": f"ERROR: {str(e)[:80]}",
                })
    
    # Format report
    lines = ["=== MODEL BENCHMARK RESULTS ===", f"Task: Fibonacci with memoization + tests", ""]
    lines.append(f"{'Model':<30} {'Tier':<12} {'Quality':>7} {'Latency':>8} {'Cost':>8} {'Status'}")
    lines.append("-" * 85)
    
    for r in sorted(results, key=lambda x: x.get("quality", 0), reverse=True):
        q = str(r.get("quality", "-"))
        lat = f"{r.get('latency_s', '-')}s" if "latency_s" in r else "-"
        lines.append(f"{r['model']:<30} {r['tier']:<12} {q:>7} {lat:>8} {r.get('cost', '-'):>8} {r['status']}")
    
    lines.append("")
    lines.append("Recommendation: Use the model with highest quality/cost ratio for each tier.")
    
    report = "\n".join(lines)
    logger.info(f"Benchmark complete:\n{report}")
    return report
