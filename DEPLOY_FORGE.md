# Running the meeting scraper on the Forge (Linux + rclone → SharePoint)

The scraper is pure-Python and already portable — it reads its output location from the `AGENDA_OUTPUT_BASE`
environment variable (falling back to the Windows SharePoint path when that var isn't set). On the Forge you
point that at a local Linux folder, and **rclone** pushes that folder up to SharePoint after each run — doing
the job OneDrive does on your PC.

```
Forge (cron) ──> python3 council_meetings.py ──> /home/you/AgendaMinutes  ──rclone copy──> SharePoint library
                 python3 digest.py           ──>            _Digests       ──rclone copy──>   (dad's view)
```

## 1. One-time setup on the Forge

SSH in over Tailscale, then:

**a. Install the prerequisites** (Debian/Ubuntu shown; the scraper needs only python3 + git, the digest also
needs PyMuPDF, and rclone does the SharePoint sync):

```bash
sudo apt update && sudo apt install -y python3 python3-pip git
curl https://rclone.org/install.sh | sudo bash        # or: sudo apt install rclone
pip3 install --user pymupdf
```

**b. Clone the repo** (same account/place you keep Municipal_Permits is fine):

```bash
git clone https://github.com/Jameslptandco/agenda_scraper.git
cd agenda_scraper
chmod +x run_meetings.sh run_digest.sh
```

**c. Configure rclone for SharePoint.** This is the one interactive step. The Forge is headless, so you
authorise from a machine that has a browser:

```bash
rclone config
#  n) New remote
#  name>  sharepoint
#  Storage>  onedrive         (Microsoft OneDrive — this backend also serves SharePoint libraries)
#  client_id>       (leave blank)
#  client_secret>   (leave blank)
#  region>  global
#  Edit advanced config?  n
#  Use auto config?  n        <-- headless: it prints a command to run on your laptop
```

On your **laptop** (has a browser), run the command it shows — `rclone authorize "onedrive"` — sign in with
your lptandco.com account, then paste the token blob back into the Forge prompt. rclone then asks which drive:

```
#  Your choice>  choose "Type in SharePoint site URL" (or "Search for a SharePoint site")
#  URL>  https://lptandco.sharepoint.com/sites/<yoursite>
#  then pick the document library that contains "LPT Builds - Operations"
#  y) Yes this is OK  ->  q) Quit config
```

Test it and note the path to your AgendaMinutes folder inside the library:

```bash
rclone lsd "sharepoint:LPT Builds - Operations/07_Products/Second Cut"     # should list AgendaMinutes
```

> If sign-in is blocked, your M365 admin may need to grant consent for rclone once (it's a well-known app).

**d. Point the scripts at your paths.** Open `run_meetings.sh` and `run_digest.sh` and set the two variables
at the top:
- `AGENDA_OUTPUT_BASE` — where the Forge writes locally, e.g. `$HOME/AgendaMinutes` (the default is fine).
- `RCLONE_DEST` — the rclone remote:path from step c, e.g.
  `sharepoint:LPT Builds - Operations/07_Products/Second Cut/AgendaMinutes`.

**e. (Optional) alerts.** Copy `email_config.example.json` to `email_config.json` and fill it in for
cancellation alerts + the digest email.

**f. Test once, by hand:**

```bash
./run_meetings.sh        # first run is the big backfill — see notes below
```

Open the SharePoint library afterward and confirm the towns + `index.html` are showing up.

## 2. Schedule it (cron)

`crontab -e`, then — same idea as the permit harvester:

```cron
# meeting scraper: every 6 hours
0 */6 * * * /home/YOU/agenda_scraper/run_meetings.sh >> /home/YOU/agenda_scraper/run.log 2>&1
# keyword digest: Mondays 7am
0 7 * * 1 /home/YOU/agenda_scraper/run_digest.sh >> /home/YOU/agenda_scraper/digest.log 2>&1
```

(Replace `/home/YOU/…` with the real clone path. `run.log`/`digest.log` are git-ignored.)

## 3. First run

The first run backfills ~2 years across 42 councils — 1,500+ PDFs, and the initial `rclone copy` uploads all
of it to SharePoint (potentially a few GB). Expect it to take a while. **Every run after is quick** — the
scraper only fetches new meetings, and `rclone copy` only uploads changed files. Kick the first one off by
hand (step f) rather than waiting on cron, so you can watch it.

## 4. Keeping it updated

When we change the code, you `git push` from your PC (via `save_to_git.bat`) and on the Forge just:

```bash
cd agenda_scraper && git pull
```

## Notes

- The scraper is idempotent and safe to run as often as cron fires. `state.json` / `digest_state.json` are
  the tools' memory (kept local on the Forge; don't delete).
- `rclone copy` never deletes anything already in SharePoint — if you ever want the Forge to *mirror*
  (including removals), switch `copy` to `sync` in the scripts, carefully.
- Running on the Forge and on your PC at the same time would double-write to SharePoint — pick one home for
  it (the Forge is the better one, since it's always on).
