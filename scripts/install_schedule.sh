#!/bin/bash
# Installs the daily ingest job as a macOS launchd user agent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python3"
PLIST_NAME="com.marketstocks.ingest.plist"
DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

mkdir -p "$HOME/Library/LaunchAgents"

sed \
  -e "s#__VENV_PYTHON__#$VENV_PYTHON#g" \
  -e "s#__PROJECT_ROOT__#$PROJECT_ROOT#g" \
  "$SCRIPT_DIR/$PLIST_NAME" > "$DEST"

launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"

echo "Installed and loaded $DEST"
echo "Runs ingest.py Mon-Fri at 18:00 (machine local time)."
echo "Check status with: launchctl list | grep marketstocks"
echo "Logs: $PROJECT_ROOT/data/launchd.out.log and launchd.err.log"
