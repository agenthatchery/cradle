# 🐣 Cradle — Self-Evolving Agent System

A self-evolving, self-updating agentic system running in Docker. Capable of spawning sub-agents in isolated containers, learning from experience, and continuously improving itself.

## Architecture

```
┌─────────────────────────────────────┐
│         Cradle Container            │
│                                     │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ Heartbeat│──│ Telegram Bot     │ │
│  │ (30s)    │  │ (@matebenyovszky)│ │
│  └────┬─────┘  └──────────────────┘ │
│       │                             │
│  ┌────┴─────┐  ┌──────────────────┐ │
│  │Task Engn │──│ LLM Router       │ │
│  │ (ReAct)  │  │ Gemini→MM→Groq   │ │
│  └────┬─────┘  └──────────────────┘ │
│       │                             │
│  ┌────┴─────┐  ┌──────────────────┐ │
│  │ Sandbox  │  │ Self-Evolution   │ │
│  │ (Docker) │  │ (GitHub CI/CD)   │ │
│  └──────────┘  └──────────────────┘ │
│                                     │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ Memory   │  │ GitHub Client    │ │
│  │ (APB.ai) │  │ (agenthatchery)  │ │
│  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────┘
```

## Quick Start

```bash
# Clone
git clone https://github.com/agenthatchery/cradle.git
cd cradle

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
docker-compose up -d

# Check logs
docker-compose logs -f
```

## Commands (Telegram)

- `/start` — Initialize bot
- `/status` — System health
- `/task <description>` — Submit a task
- `/cost` — LLM usage stats
- `/evolve` — Trigger self-improvement

Or just send a free-text message — it becomes a task.

## Self-Evolution

The agent can improve its own code:
1. Analyzes current source with Gemini 3.1 Pro
2. Generates improvement proposal
3. Tests in Docker sandbox
4. Pushes to GitHub branch → merges
5. Restarts with updated code

## License

MIT
