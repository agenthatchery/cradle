
# Default Docker resource limits for sandboxed agents
DEFAULT_SANDBOX_CPUS = "0.5"  # 0.5 CPU core
DEFAULT_SANDBOX_MEMORY = "512m" # 512 MB


class Config:
    SANDBOX_MEMORY_LIMIT: str = '256m' # Memory limit for sandbox containers (e.g., '256m', '1g')

    SANDBOX_CPU_LIMIT: float = 0.5 # CPU limit for sandbox containers (e.g., 0.5 for 50% of one CPU)
    LLM_PROVIDER_PRIORITIES = ["groq", "gemini-flash", "openai"]
