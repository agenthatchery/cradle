#!/bin/bash
# Cradle entrypoint — self-updating loop
# 1. If repo exists locally, git pull. Otherwise git clone.
# 2. Install requirements
# 3. Run the agent
# 4. If agent exits with code 42, pull new code and restart
# 5. Otherwise, just restart (docker restart policy handles crashes)

set -e

REPO_URL="https://${GITHUB_PAT}@github.com/${GITHUB_ORG:-agenthatchery}/${GITHUB_REPO:-cradle}.git"
APP_DIR="/app/repo"
DATA_DIR="${DATA_DIR:-/app/data}"
LOG_DIR="${LOG_DIR:-/app/logs}"

mkdir -p "$DATA_DIR" "$LOG_DIR"

echo "🐣 Cradle entrypoint starting..."
echo "   Repo: ${GITHUB_ORG:-agenthatchery}/${GITHUB_REPO:-cradle}"

# ── Git sync ──
if [ -d "$APP_DIR/.git" ]; then
    echo "📥 Pulling latest code..."
    cd "$APP_DIR"
    git pull --ff-only origin main 2>/dev/null || {
        echo "⚠️ Git pull failed, using existing code"
    }
else
    echo "📥 Cloning repo..."
    git clone "$REPO_URL" "$APP_DIR" 2>/dev/null || {
        echo "⚠️ Git clone failed, using bundled code"
        APP_DIR="/app"
    }
fi

cd "$APP_DIR"

# ── Install deps ──
if [ -f requirements.txt ]; then
    echo "📦 Installing requirements..."
    pip install --quiet --no-cache-dir -r requirements.txt 2>/dev/null || true
fi

# ── Run agent (loop for self-restart) ──
while true; do
    echo "🚀 Starting Cradle agent..."
    PYTHONPATH="$APP_DIR" python -m cradle.main
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 42 ]; then
        echo "🔄 Self-update requested (exit code 42), pulling new code..."
        git pull --ff-only origin main 2>/dev/null || true
        pip install --quiet --no-cache-dir -r requirements.txt 2>/dev/null || true
        echo "♻️ Restarting with updated code..."
        sleep 2
    else
        echo "⚠️ Agent exited with code $EXIT_CODE, restarting in 10s..."
        sleep 10
    fi
done
