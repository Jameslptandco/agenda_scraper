#!/usr/bin/env bash
# Forge runner: scrape all councils, then push the output up to SharePoint via rclone.
# Cron calls this. The two variables below have sensible defaults for the Forge.
set -euo pipefail
export PATH="$HOME/bin:/usr/local/bin:/usr/bin:/bin:$PATH"     # $HOME/bin so cron finds rclone installed there
cd "$(dirname "$0")"

# ---- Forge settings (override via env in the crontab if needed) ----
export AGENDA_OUTPUT_BASE="${AGENDA_OUTPUT_BASE:-$HOME/AgendaMinutes}"                         # local output dir on the Forge
RCLONE_DEST="${RCLONE_DEST:-sharepoint:07_Products/Second Cut/AgendaMinutes}"                  # path inside the Operations library
# --------------------------------------------------------------------

# Alert on failure: if any step below errors out, email a heads-up. No-op until email_config.json exists.
trap 'printf "The EO council meeting scraper failed at %s on host %s.\nCheck ~/agenda_scraper/run.log on the Forge for details.\n" "$(date "+%F %T")" "$(hostname)" | python3 notify.py "EO council meeting scraper FAILED on the Forge" || true' ERR

mkdir -p "$AGENDA_OUTPUT_BASE"
echo "=== $(date '+%F %T') meeting scraper ==="
python3 council_meetings.py

echo "=== $(date '+%F %T') rclone -> SharePoint ==="
# Two passes, because SharePoint treats PDFs and HTML very differently:
#
# Pass 1 - the PDF archive (the data). --checksum so the ~13 GB of identical files is skipped and
# never re-uploaded. Excludes the small text files, which pass 2 handles.
rclone copy "$AGENDA_OUTPUT_BASE" "$RCLONE_DEST" --checksum --transfers 4 --checkers 8 --tpslimit 10 \
  --exclude "_Digests/**" --exclude "*.html" --exclude "*.csv"
#
# Pass 2 - the regenerable nav files (index.html / *.csv). SharePoint (a) won't let rclone OVERWRITE
# files OneDrive originally made -> delete them first (goes to the recycle bin, recoverable), and
# (b) silently rewrites .html on upload (adds ~215 bytes), which makes rclone think the transfer was
# corrupted and DELETE what it just uploaded. --ignore-size --ignore-checksum tells rclone to accept
# SharePoint's rewrite. The pages still render fine. _Digests is left to run_digest.sh.
rclone delete "$RCLONE_DEST" --filter "- _Digests/**" --filter "+ *.html" --filter "+ *.csv" --filter "- *" || true
rclone copy "$AGENDA_OUTPUT_BASE" "$RCLONE_DEST" \
  --filter "- _Digests/**" --filter "+ *.html" --filter "+ *.csv" --filter "- *" \
  --ignore-size --ignore-checksum --transfers 4 --tpslimit 10
echo "=== $(date '+%F %T') done ==="
