#!/bin/bash
set -euo pipefail

# Only run in Claude Code remote environment
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "Installing Python dependencies..."
pip install -r "$CLAUDE_PROJECT_DIR/requirements.txt" --quiet

echo "Pulling latest code from GitHub..."
cd "$CLAUDE_PROJECT_DIR"
git pull origin master --ff-only || echo "Git pull skipped (no remote changes or not configured)"

echo "Session setup complete."
