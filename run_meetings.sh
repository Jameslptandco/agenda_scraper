#!/usr/bin/env bash
# Forge runner: scrape all councils, then push the output up to SharePoint via rclone.
# Cron calls this. Edit the two variables below once for your Forge.
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")"

# ---- edit these two for your Forge ----
export AGENDA_OUTPUT_BASE="${AGENDA_OUTPUT_BASE:-$HOME/AgendaMinutes}"                                    # local output dir on the Forge
RCLONE_DEST="${RCLONE_DEST:-sharepoint:LPT Builds - Operations/07_Products/Second Cut/AgendaMinutes}"     # rclone remote:path (the SharePoint library)
# ---------------------------------------

mkdir -p "$AGENDA_OUTPUT_BASE"
echo "=== $(date '+%F %T') meeting scraper ==="
python3 council_meetings.py

echo "=== $(date '+%F %T') rclone -> SharePoint ==="
# copy (not sync): uploads new/changed files, never deletes anything already in SharePoint
rclone copy "$AGENDA_OUTPUT_BASE" "$RCLONE_DEST" --fast-list --transfers 8 --checkers 16
echo "=== $(date '+%F %T') done ==="
