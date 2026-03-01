#!/usr/bin/env bash
# setup-lenovo.sh — One-time setup for Lenovo machine
# Usage: bash scripts/setup-lenovo.sh

set -euo pipefail

REPO_DIR="C:/govy/repos/govy-function-current"
CLAUDE_DIR="$REPO_DIR/.claude"

mkdir -p "$CLAUDE_DIR"

cat > "$CLAUDE_DIR/settings.local.json" << 'EOF'
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(git:*)",
      "Bash(ruff check:*)",
      "Bash(ruff format:*)",
      "Bash(curl:*)"
    ]
  },
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd C:/govy/repos/govy-function-current && bash scripts/govy-sync.sh full 2>/dev/null || true",
            "timeout": 60,
            "statusMessage": "Syncing to wip/local..."
          }
        ]
      }
    ]
  }
}
EOF

echo "[setup-lenovo] settings.local.json created at $CLAUDE_DIR/settings.local.json"
echo "[setup-lenovo] Done! Restart Claude Code for hooks to take effect."
