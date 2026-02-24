"""Configuration loader — all settings from environment variables."""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMProvider:
    name: str
    api_key: str
    base_url: str
    model: str
    priority: int  # lower = preferred
    max_rpm: int = 60  # requests per minute
    cost_per_1k_tokens: float = 0.0


@dataclass
class Config:
    # ── LLM Providers (loaded in priority order) ──
    llm_providers: list[LLMProvider] = field(default_factory=list)

    # ── Telegram ──
    telegram_bot_token: str = ""
    allowed_telegram_user: str = "@matebenyovszky"

    # ── GitHub ──
    github_pat: str = ""
    github_org: str = "agenthatchery"
    github_repo: str = "cradle"

    # ── AgentPlaybooks ──
    agentplaybooks_key: str = ""
    agentplaybooks_guid: str = ""
    agentplaybooks_playbook_id: str = ""
    agentplaybooks_base_url: str = "https://agentplaybooks.ai/api"

    # ── Supabase ──
    supabase_key: str = ""

    # ── Cradle settings ──
    heartbeat_interval: int = 30
    log_level: str = "INFO"
    data_dir: str = "/app/data"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        cfg = cls()

        # Telegram
        cfg.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        cfg.allowed_telegram_user = os.getenv("ALLOWED_TELEGRAM_USER", "@matebenyovszky")

        # GitHub
        cfg.github_pat = os.getenv("GITHUB_PAT", "")
        cfg.github_org = os.getenv("GITHUB_ORG", "agenthatchery")
        cfg.github_repo = os.getenv("GITHUB_REPO", "cradle")

        # AgentPlaybooks
        cfg.agentplaybooks_key = os.getenv("AGENTPLAYBOOKS_KEY", "")
        cfg.agentplaybooks_guid = os.getenv("AGENTPLAYBOOKS_GUID", "")
        cfg.agentplaybooks_playbook_id = os.getenv("AGENTPLAYBOOKS_PLAYBOOK_ID", "")

        # Supabase
        cfg.supabase_key = os.getenv("SUPABASE_KEY", "")

        # Cradle
        cfg.heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
        cfg.log_level = os.getenv("LOG_LEVEL", "INFO")
        cfg.data_dir = os.getenv("DATA_DIR", "/app/data")

        # Build LLM provider list (priority order)
        providers = []

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            providers.append(LLMProvider(
                name="gemini",
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta",
                model=os.getenv("GEMINI_MODEL", "gemini-3.1-pro"),
                priority=1,
                cost_per_1k_tokens=0.00015,
            ))

        minimax_key = os.getenv("MINIMAX_API_KEY", "")
        if minimax_key:
            providers.append(LLMProvider(
                name="minimax",
                api_key=minimax_key,
                base_url="https://api.minimaxi.chat/v1",
                model="MiniMax-M1",
                priority=2,
                max_rpm=20,  # ~100 req/5h
                cost_per_1k_tokens=0.0,
            ))

        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            providers.append(LLMProvider(
                name="groq",
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.3-70b-versatile",
                priority=3,
                cost_per_1k_tokens=0.0,
            ))

        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            providers.append(LLMProvider(
                name="openrouter",
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                model="meta-llama/llama-3.3-70b-instruct:free",
                priority=4,
                cost_per_1k_tokens=0.0,
            ))

        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            providers.append(LLMProvider(
                name="openai",
                api_key=openai_key,
                base_url="https://api.openai.com/v1",
                model="gpt-4.1-mini",
                priority=5,
                cost_per_1k_tokens=0.0004,
            ))

        providers.sort(key=lambda p: p.priority)
        cfg.llm_providers = providers

        return cfg

    def validate(self) -> list[str]:
        """Return list of warnings about missing configuration."""
        warnings = []
        if not self.llm_providers:
            warnings.append("No LLM providers configured — agent cannot think!")
        if not self.telegram_bot_token:
            warnings.append("No Telegram bot token — no human communication channel")
        if not self.github_pat:
            warnings.append("No GitHub PAT — cannot self-evolve via git")
        return warnings
