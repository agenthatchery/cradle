#!/bin/bash
# Enforces trunk-based development. Auto-commits directly to main.
# Replaces previous agent scripts that created endless branches.

cd /app || exit 1

# Ensure we are on main
git checkout main 2>/dev/null || git checkout -b main
git pull --rebase origin main

# Check for changes
if [[ -z $(git status -s) ]]; then
  echo "No changes to commit."
  exit 0
fi

git add -A
git commit -m "auto: self-improvement cycle $(date +%Y-%m-%d %H:%M)"
git push origin main
