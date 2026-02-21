#!/bin/bash
# Cradle Watchdog Supervisor with Git Auto-Rollback
# Ensures the Cradle agent is ALWAYS running. If it crashes, it auto-restarts.
# After 3 crashes: rebuilds Docker image.
# After 5 crashes: git rollback to last known good commit.
# Usage: nohup bash /root/cradle/watchdog.sh &

CONTAINER_NAME="cradle"
CHECK_INTERVAL=30
MAX_FAILURES_REBUILD=3
MAX_FAILURES_ROLLBACK=5
CRADLE_DIR="/root/cradle"
failure_count=0

echo "[Watchdog] Starting Cradle Watchdog Supervisor (v2 with git rollback)..."

# Save current commit as "known good" on startup
cd "$CRADLE_DIR"
LAST_GOOD_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "")
echo "[Watchdog] Last known good commit: $LAST_GOOD_COMMIT"

while true; do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null)

    if [ "$STATUS" != "running" ]; then
        echo "[Watchdog] $(date) - Container NOT running (status: $STATUS). Restarting..."
        failure_count=$((failure_count + 1))

        # LEVEL 1: After MAX_FAILURES_REBUILD, rebuild Docker image
        if [ "$failure_count" -ge "$MAX_FAILURES_ROLLBACK" ] && [ -n "$LAST_GOOD_COMMIT" ]; then
            # LEVEL 2: After MAX_FAILURES_ROLLBACK, git rollback
            echo "[Watchdog] $(date) - $failure_count failures! Rolling back to $LAST_GOOD_COMMIT..."
            cd "$CRADLE_DIR"
            git stash 2>/dev/null
            git checkout "$LAST_GOOD_COMMIT" -- . 2>/dev/null
            git stash pop 2>/dev/null
            echo "[Watchdog] Rolled back. Rebuilding image..."
            docker build -t cradle-agent . 2>&1 | tail -3
            failure_count=0
        elif [ "$failure_count" -ge "$MAX_FAILURES_REBUILD" ]; then
            echo "[Watchdog] $(date) - $MAX_FAILURES_REBUILD failures! Rebuilding Docker image..."
            cd "$CRADLE_DIR"
            docker build -t cradle-agent . 2>&1 | tail -3
            failure_count=0
        fi

        # Stop zombie and restart
        docker rm -f "$CONTAINER_NAME" 2>/dev/null
        docker run -d \
            --name "$CONTAINER_NAME" \
            --restart=unless-stopped \
            --env-file "$CRADLE_DIR/.env" \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$CRADLE_DIR:/app" \
            cradle-agent

        echo "[Watchdog] $(date) - Container restarted (failure count: $failure_count)."
        sleep 10
    else
        if [ "$failure_count" -gt 0 ]; then
            echo "[Watchdog] $(date) - Container recovered. Resetting failure count."
            # Update known good commit when container is stable
            cd "$CRADLE_DIR"
            NEW_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "")
            if [ -n "$NEW_COMMIT" ] && [ "$NEW_COMMIT" != "$LAST_GOOD_COMMIT" ]; then
                LAST_GOOD_COMMIT="$NEW_COMMIT"
                echo "[Watchdog] Updated known good commit: $LAST_GOOD_COMMIT"
            fi
            failure_count=0
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
