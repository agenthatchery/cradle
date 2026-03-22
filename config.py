from typing import Optional
from dataclasses import dataclass, field
import os
import logging

logger = logging.getLogger(__name__)

# Default Docker resource limits for sandboxed agents





# Docker Sandbox Resource Limits
# Docker resource limits for spawned agents

# Docker resource limits
DOCKER_CPU_LIMIT = os.environ.get('CRADLE_DOCKER_CPU_LIMIT', '0.5')  # e.g., '0.5' for 50% of one CPU
DOCKER_MEMORY_LIMIT = os.environ.get('CRADLE_DOCKER_MEMORY_LIMIT', '512m') # e.g., '512m', '1g'

DEFAULT_SANDBOX_CPUS = "0.5"  # 0.5 CPU core
DEFAULT_SANDBOX_MEMORY = "512m" # 512 MB
@dataclass
class LLMProviderConfig:
    name: str
    model: str
    priority: int

class Config:
    def __init__(self):
        self.agentplaybooks_key = os.environ.get("AGENTPLAYBOOKS_KEY")
        self.agentplaybooks_guid = os.environ.get("AGENTPLAYBOOKS_GUID")
        self.agentplaybooks_playbook_id = os.environ.get("AGENTPLAYBOOKS_PLAYBOOK_ID")
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.minimax_api_key = os.environ.get("MINIMAX_API_KEY")
        self.minimax_base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
        self.github_pat = os.environ.get("GITHUB_PAT")

        self.github_org = os.environ.get("GITHUB_ORG", "agenthatchery")
        self.github_repo = os.environ.get("GITHUB_REPO", "cradle")

        self.data_dir = os.environ.get("DATA_DIR", "/app/data")
        self.heartbeat_interval = int(os.environ.get("HEARTBEAT_INTERVAL", "60"))
        self.docker_cpu_limit = os.environ.get("CRADLE_DOCKER_CPU_LIMIT", "0.5")
        self.docker_memory_limit = os.environ.get("CRADLE_DOCKER_MEMORY_LIMIT", "512m")
        
        # Default LLM Providers (Minimax prioritized)
        self.llm_providers = [
            LLMProviderConfig(name="minimax", model="minimax-m2.7", priority=0),
            LLMProviderConfig(name="gemini", model="gemini-2.0-flash", priority=1),
            LLMProviderConfig(name="openai", model="gpt-4o", priority=2),
        ]


    @classmethod
    def from_env(cls):
        return cls()

    def validate(self) -> list[str]:
        """Simple validation check for required configuration."""
        warnings = []
        if not self.telegram_bot_token:
            warnings.append("TELEGRAM_BOT_TOKEN is missing")
        if not self.openai_api_key and not self.gemini_api_key and not self.minimax_api_key:
            warnings.append("No LLM API keys provided (OpenAI, Gemini, or Minimax)")
        return warnings





# Sandbox Resource Limits
SANDBOX_DEFAULT_CPU_LIMIT = "1.0"  # Docker --cpus value (e.g., "0.5" or "1.0")
SANDBOX_DEFAULT_MEMORY_LIMIT = "512m" # Docker --memory value (e.g., "256m" or "1g")