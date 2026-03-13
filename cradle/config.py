
# Default Docker resource limits for sandboxed agents





# Docker Sandbox Resource Limits
# Docker resource limits for spawned agents

# Docker resource limits
DOCKER_CPU_LIMIT = os.environ.get('CRADLE_DOCKER_CPU_LIMIT', '0.5')  # e.g., '0.5' for 50% of one CPU
DOCKER_MEMORY_LIMIT = os.environ.get('CRADLE_DOCKER_MEMORY_LIMIT', '512m') # e.g., '512m', '1g'

DEFAULT_SANDBOX_CPUS = "0.5"  # 0.5 CPU core
DEFAULT_SANDBOX_MEMORY = "512m" # 512 MB
class Config:
    SANDBOX_MEMORY_LIMIT: str = '256m' # Memory limit for sandbox containers (e.g., '256m', '1g')
        SANDBOX_CPU_LIMIT: Optional[str] = None # e.g., '0.5' for 0.5 CPU core
        SANDBOX_MEMORY_LIMIT: Optional[str] = None # e.g., '512m', '1g'
    SANDBOX_CPU_LIMIT: float = 0.5 # CPU limit for sandbox containers (e.g., 0.5 for 50% of one CPU)
    LLM_PROVIDER_PRIORITIES = ['groq', 'gemini-flash', 'openai']
SANDBOX_CPU_LIMIT = os.environ.get('CRADLE_SANDBOX_CPU_LIMIT', '1.0') # e.g., '0.5' for 50% of one CPU, '2.0' for 2 CPUs
SANDBOX_MEMORY_LIMIT = os.environ.get('CRADLE_SANDBOX_MEMORY_LIMIT', '1g') # e.g., '512m', '2g'
DOCKER_CPU_LIMIT = os.environ.get('CRADLE_DOCKER_CPU_LIMIT', '1.0')  # e.g., '0.5' for 50% of one CPU, '2.0' for two CPUs
DOCKER_MEMORY_LIMIT = os.environ.get('CRADLE_DOCKER_MEMORY_LIMIT', '2g') # e.g., '512m', '2g'