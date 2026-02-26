import json
import os
import time
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

class LLMAuditor:
    def __init__(self, log_path: str):
        self.log_path = log_path

    def analyze(self) -> dict:
        """Analyze the audit logs and return performance metrics."""
        if not os.path.exists(self.log_path):
            return {"error": f"Log file not found: {self.log_path}"}

        stats = defaultdict(lambda: {
            "total_calls": 0,
            "success_rate": 0,
            "avg_latency_ms": 0,
            "total_cost_usd": 0.0,
            "errors": defaultdict(int),
            "successes": 0,
            "latencies": []
        })

        try:
            with open(self.log_path, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        p = entry["provider"]
                        stats[p]["total_calls"] += 1
                        if entry.get("success"):
                            stats[p]["successes"] += 1
                            stats[p]["latencies"].append(entry.get("latency_ms", 0))
                            stats[p]["total_cost_usd"] += entry.get("cost_usd", 0.0)
                        else:
                            error = entry.get("error", "unknown")
                            stats[p]["errors"][error] += 1
                    except Exception:
                        continue
        except Exception as e:
            return {"error": f"Failed to read logs: {e}"}

        results = {}
        for provider, data in stats.items():
            total = data["total_calls"]
            successes = data["successes"]
            latencies = data["latencies"]
            
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            success_rate = (successes / total) * 100 if total > 0 else 0
            
            results[provider] = {
                "total_calls": total,
                "success_rate": round(success_rate, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "total_cost_usd": round(data["total_cost_usd"], 4),
                "most_common_errors": dict(sorted(data["errors"].items(), key=lambda x: x[1], reverse=True)[:3])
            }

        return results

    def generate_report(self) -> str:
        """Generate a human-readable performance report."""
        results = self.analyze()
        if "error" in results:
            return f"❌ Audit Failed: {results['error']}"

        lines = [
            "📈 LLM Provider Performance Audit Report",
            f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "------------------------------------------"
        ]

        if not results:
            lines.append("No audit data found yet.")
            return "\n".join(lines)

        # Sort by success rate then latency
        sorted_providers = sorted(results.items(), key=lambda x: (x[1]["success_rate"], -x[1]["avg_latency_ms"]), reverse=True)

        for provider, data in sorted_providers:
            lines.append(f"\n[{provider.upper()}]")
            lines.append(f"  - Success Rate: {data['success_rate']}%")
            lines.append(f"  - Avg Latency: {data['avg_latency_ms']}ms")
            lines.append(f"  - Total Calls: {data['total_calls']}")
            lines.append(f"  - Total Cost:  ${data['total_cost_usd']:.4f}")
            if data["most_common_errors"]:
                lines.append(f"  - Top Errors:  {data['most_common_errors']}")

        lines.append("\n💡 Optimization Advice:")
        if sorted_providers:
            best = sorted_providers[0][0]
            lines.append(f"  - '{best}' is performing best. Consider moving it to priority 1.")
            
        return "\n".join(lines)

if __name__ == "__main__":
    # Test run
    import sys
    log_file = sys.argv[1] if len(sys.argv) > 1 else "/app/data/llm_audit.jsonl"
    auditor = LLMAuditor(log_file)
    print(auditor.generate_report())
