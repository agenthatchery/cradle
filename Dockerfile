FROM python:3.12-slim

# Install Docker CLI (for spawning sub-agent containers), git, curl, jq
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    git \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code (bundled fallback if git clone fails)
COPY . .

# Create directories
RUN mkdir -p /app/data /app/logs /app/repo

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
