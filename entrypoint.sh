#!/bin/bash
# Cradle entrypoint — always runs the LATEST code from GitHub
# Architecture:
#   /app          = baked-in image code (used as bootstrap only)
#   /app/repo     = git-cloned/pulled code — this is what runs!
# This means 'docker restart' always gets latest GitHub code — no image rebuild needed.

set -e

REPO_URL="https://${GITHUB_PAT}@github.com/${GITHUB_ORG:-agenthatchery}/${GITHUB_REPO:-cradle}.git"
REPO_DIR="/app/repo"
DATA_DIR="${DATA_DIR:-/app/data}"
LOG_DIR="${LOG_DIR:-/app/logs}"

mkdir -p "$DATA_DIR" "$LOG_DIR"

echo "🐣 Cradle entrypoint starting..."
echo "   Repo: ${GITHUB_ORG:-agenthatchery}/${GITHUB_REPO:-cradle}"

# ── Git sync (ALWAYS use /app/repo, never /app) ──
if [ -d "$REPO_DIR/.git" ]; then
    echo "📥 Pulling latest code..."
    cd "$REPO_DIR"
    git pull --ff-only origin main || {
        echo "⚠️ Git pull failed, using existing code in $REPO_DIR"
    }
else
    echo "📥 Cloning repo..."
    git clone "$REPO_URL" "$REPO_DIR" || {
        echo "⚠️ Git clone failed, copying bundled /app as fallback"
        cp -r /app/. "$REPO_DIR/"
    }
    cd "$REPO_DIR"
fi

# ── Install deps from cloned repo ──
echo "📦 Installing requirements..."
pip install --quiet --no-cache-dir -r requirements.txt || true

# ── Run agent (loop for self-restart via exit code 42) ──
while true; do
    echo "🚀 Starting Cradle agent from $REPO_DIR ..."
    PYTHONPATH="$REPO_DIR" python -m cradle.main
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 42 ]; then
        echo "🔄 Self-update requested (exit code 42), pulling new code..."
        git -C "$REPO_DIR" pull --ff-only origin main || true
        pip install --quiet --no-cache-dir -r "$REPO_DIR/requirements.txt" || true
        echo "♻️ Restarting with updated code..."
        sleep 2
    else
        echo "⚠️ Agent exited with code $EXIT_CODE, restarting in 10s..."
        sleep 10
    fi
done
