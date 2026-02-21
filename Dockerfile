FROM python:3.11-slim

# Install git, docker CLI, and curl
RUN apt-get update && \
    apt-get install -y git docker.io curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Explicitly upgrade docker to the latest version
RUN pip install --no-cache-dir --upgrade docker
RUN playwright install chromium --with-deps 2>/dev/null || echo "Playwright install skipped"

# Copy source code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1

# Health check: verify python can import agent without errors
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import agent" || exit 1

CMD ["python", "-u", "cradle.py"]
