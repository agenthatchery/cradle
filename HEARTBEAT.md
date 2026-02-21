# HEARTBEAT.md — Proactive Task Checklist

This file is checked every autonomous tick. For each item, decide if action is needed NOW.
Only act on items that are due or critical. Skip items that were recently handled.

## Every Tick (10 minutes)
- [ ] Read reflections — what did I do last tick?
- [ ] Check container health: `execute_shell_command("docker ps --format '{{.Names}} {{.Status}}'")`
- [ ] Check if researcher-agent is running and producing findings

## Every Hour
- [ ] Review researcher findings: `execute_shell_command("tail -20 /app/researcher-agent/findings.log 2>/dev/null || docker logs researcher-agent --tail 10")`
- [ ] Check API cost status: `check_model_router()` — are we hitting rate limits?
- [ ] Look for new operator messages in Telegram that may have been missed

## Every 6 Hours  
- [ ] Self-benchmark: `benchmark_models()` — are models still performing well?
- [ ] Search for new capabilities: `search_mcp_servers("trending")` — any new useful tools?
- [ ] Research cheaper models: `search_web("cheapest LLM API 2026")`

## Daily
- [ ] Push a git commit summarizing today's progress (branch, not main)
- [ ] Write a daily summary reflection
- [ ] Check GitHub for any issues or PRs on agenthatchery repos

## Weekly
- [ ] Full benchmark of all models — update which ones are best per tier
- [ ] Review and clean up old reflections (archive >100 entries)
- [ ] Check for new OpenClaw/agent framework updates
- [ ] Review and update soul.md if learnings warrant it (with reflection first!)

## Operator-Requested (check if pending)
- [ ] AgentPlaybooks.ai API key integration (awaiting key)
- [ ] Any specific research or development tasks from Telegram
