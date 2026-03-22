from typing import Optional

# Default Docker resource limits for sandboxed agents





# Docker Sandbox Resource Limits
# Docker resource limits for spawned agents

# Docker resource limits
DOCKER_CPU_LIMIT = os.environ.get('CRADLE_DOCKER_CPU_LIMIT', '0.5')  # e.g., '0.5' for 50% of one CPU
DOCKER_MEMORY_LIMIT = os.environ.get('CRADLE_DOCKER_MEMORY_LIMIT', '512m') # e.g., '512m', '1g'

DEFAULT_SANDBOX_CPUS = "0.5"  # 0.5 CPU core
DEFAULT_SANDBOX_MEMORY = "512m" # 512 MB
class Config:
    provider_priority: list[str] = ["groq", "gemini-2.5-flash", "openai",]
    # Docker Resource Limits
    docker_cpu_limit: Optional[float] = None # e.g., 0.5 for 50% of one CPU
    docker_memory_limit: Optional[str] = None # e.g., '512m', '1g'

    LLM_PROVIDER_PRIORITY: list[str] = ['groq', 'openai', 'gemini-1.5-flash']
    SANDBOX_MEMORY_LIMIT: str = '256m' # Memory limit for sandbox containers (e.g., '256m', '1g')
        SANDBOX_CPU_LIMIT: Optional[str] = None # e.g., '0.5' for 0.5 CPU core
        SANDBOX_MEMORY_LIMIT: Optional[str] = None # e.g., '512m', '1g'
    SANDBOX_CPU_LIMIT: float = 0.5 # CPU limit for sandbox containers (e.g., 0.5 for 50% of one CPU)
    LLM_PROVIDER_PRIORITIES = ['groq', 'gemini-flash', 'openai']
    'groq',    'gemini-2.5-flash',    'openai',PROVIDERS = ['groq', 'gemini-flash', 'openai']

# Sandbox Resource Limits
SANDBOX_DEFAULT_CPU_LIMIT = "1.0"  # Docker --cpus value (e.g., "0.5" or "1.0")
SANDBOX_DEFAULT_MEMORY_LIMIT = "512m" # Docker --memory value (e.g., "256m" or "1g")