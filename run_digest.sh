#!/usr/bin/env bash
# Forge runner: build the keyword digest from the archive, then push it up to SharePoint.
# Cron calls this (weekly). Same settings as run_meetings.sh.
set -euo pipefail
export PATH="$HOME/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")"

export AGENDA_OUTPUT_BASE="${AGENDA_OUTPUT_BASE:-$HOME/AgendaMinutes}"
RCLONE_DEST="${RCLONE_DEST:-sharepoint:07_Products/Second Cut/AgendaMinutes}"

echo "=== $(date '+%F %T') keyword digest ==="
python3 digest.py

echo "=== $(date '+%F %T') rclone -> SharePoint ==="
# The digest is HTML + CSV only. Same SharePoint quirks as run_meetings.sh pass 2: delete the stale
# copies first (can't overwrite OneDrive-made files), then upload with --ignore-size/--ignore-checksum
# so rclone accepts SharePoint's silent HTML rewrite instead of erroring and deleting the upload.
rclone delete "$RCLONE_DEST/_Digests" --include "*.html" --include "*.csv" || true
rclone copy "$AGENDA_OUTPUT_BASE/_Digests" "$RCLONE_DEST/_Digests" --ignore-size --ignore-checksum --tpslimit 10
echo "=== $(date '+%F %T') done ==="
