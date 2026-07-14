#!/usr/bin/env bash
# Forge runner: build the keyword digest from the archive, then push it up to SharePoint.
# Cron calls this (weekly). Uses the same two variables as run_meetings.sh.
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")"

export AGENDA_OUTPUT_BASE="${AGENDA_OUTPUT_BASE:-$HOME/AgendaMinutes}"
RCLONE_DEST="${RCLONE_DEST:-sharepoint:LPT Builds - Operations/07_Products/Second Cut/AgendaMinutes}"

echo "=== $(date '+%F %T') keyword digest ==="
python3 digest.py

echo "=== $(date '+%F %T') rclone -> SharePoint ==="
rclone copy "$AGENDA_OUTPUT_BASE/_Digests" "$RCLONE_DEST/_Digests" --fast-list
echo "=== $(date '+%F %T') done ==="
