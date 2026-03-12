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

    # ── Google Custom Search (for web_search skill) ──
    google_cse_key: str = ""
    google_cse_id: str = ""

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

        # Google Custom Search
        cfg.google_cse_key = os.getenv("GOOGLE_CSE_KEY", "")
        cfg.google_cse_id = os.getenv("GOOGLE_CSE_ID", "")

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
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                priority=1,
                cost_per_1k_tokens=0.00015,
            ))
            # Premium model for strategic/planning tasks (preferred_provider="gemini-pro")
            providers.append(LLMProvider(
                name="gemini-pro",
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta",
                model="gemini-3.1-pro-preview",
                priority=10,  # only used when explicitly requested
                cost_per_1k_tokens=0.005,
            ))

# Docker Sandbox Resource Limits
SANDBOX_CPU_LIMIT = None  # e.g., '1.0' for 1 CPU, '0.5' for 0.5 CPU. Set to None for no limit.
SANDBOX_MEMORY_LIMIT = None # e.g., '512m' for 512MB, '1g' for 1GB. Set to None for no limit.

        minimax_key = os.getenv("MINIMAX_API_KEY", "")
DOCKER_CPU_LIMIT = '1.0' # 1 CPU core
DOCKER_MEMORY_LIMIT = '2g' # 2 GB memory
