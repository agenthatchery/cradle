
# Existing config values (if any)

# Docker resource limits for sandbox
SANDBOX_CPU_LIMIT = "1.0"  # e.g., "0.5" for 50% CPU, "1.0" for 100% CPU
SANDBOX_MEMORY_LIMIT = "512m" # e.g., "256m", "1g"

# Other config values...

# Docker resource limits for spawned containers
DOCKER_CPU_LIMIT = os.getenv('CRADLE_DOCKER_CPU_LIMIT', '0.5')  # e.g., '0.5' for 50% of one CPU core
DOCKER_MEMORY_LIMIT = os.getenv('CRADLE_DOCKER_MEMORY_LIMIT', '512m') # e.g., '512m' for 512 megabytes
