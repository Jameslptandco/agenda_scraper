# Eastern Ontario Council Agendas & Minutes — scraper + cancellation watcher

`council_meetings.py` pulls **Regular + Special *council* meeting** agendas and minutes for Cornwall
**and all eight Prescott-Russell eScribe municipalities** in one run, saves them to a per-town folder on
SharePoint, builds a click-through `index.html` per town, and watches for cancelled/rescheduled meetings.

> This **supersedes `cornwall_meetings.py`** (Cornwall is now just the first town in the list). Schedule
> `council_meetings.py` instead; you can delete the old `cornwall_meetings.py` once you're happy.

## Towns covered

Cornwall, The Nation, East Hawkesbury, Alfred-Plantagenet, Clarence-Rockland, Champlain, Casselman,
Hawkesbury, Prescott-Russell (UCPR — the county council), and **Russell Township**.

All except Russell run on the **eScribe** platform. **Russell** is on **CivicWeb**, a different system, so
it uses a separate code path (see "Russell / CivicWeb" below) — but it lands in the same per-town folder
structure with the same click-through index, so from your side it behaves identically.

**What each town actually publishes differs**, and the tool handles all of it: it downloads the **PDF**
where a town posts one, and **links the online (web) version** where a town only publishes the document as
a web page (no PDF). So nothing is lost — a web-only agenda still shows up in the index as an "Agenda
(online)" link that opens the eScribe page. Rough picture at build time (Jul 2026):

| Town | Council mtgs | Agenda | Minutes |
|---|---|---|---|
| The Nation | ~26 | PDF | PDF |
| East Hawkesbury | ~14 | PDF | PDF |
| Alfred-Plantagenet | ~19 | PDF | web-only |
| Clarence-Rockland | ~16 | web-only | PDF (EN+FR) |
| Cornwall | ~27 | PDF | PDF |
| Champlain / Casselman / UCPR | ~15-17 | mostly web-only | mostly web-only |

The web-only towns still appear in their index with online links; if you want their documents as saved PDFs,
the standing-email route (see `../../Municipal_Permits/CLERK_EMAILS.md` for the same towns) is the fallback.

## Run it

    python council_meetings.py

Pure Python standard library — no installs. Idempotent, so run it as often as you like (it only downloads
what's new).

## Council-meeting filter

Not every town labels its council meeting the same way — some say "Regular Council Meeting", others just
"Regular Meeting". The tool keeps meeting types matching **regular/special meeting** or **council/conseil**
and drops committees, public/planning/zoning meetings, closed sessions, etc. To also capture those, loosen
`EXC_RE` near the top of the script. Bilingual towns (EN/FR) are handled — the tool prefers the **English**
copy of each document and falls back to French.

## Cancellation / reschedule alerts

eScribe doesn't flag a cancelled meeting — it just drops it from the calendar. The tool remembers each
town's upcoming council meetings and, when a future one **disappears** (cancelled) or its date **changes**
(rescheduled), it logs the change to `cancellations.csv` (at the top of the SharePoint AgendaMinutes folder)
and — if email is set up — **emails an alert**. It won't false-alarm on a transient empty/broken feed.

### Set up the email alert (optional)

1. Copy `email_config.example.json` to `email_config.json`.
2. Fill in a sending account + recipient. For **Gmail** use an **App Password** (Google Account → Security →
   2-Step Verification → App passwords), not your normal password.
3. Keep `email_config.json` private — it holds a password. It stays local (never synced to SharePoint) and
   is git-ignored. Until it exists, cancellations are still logged to `cancellations.csv`; they just aren't emailed.

## Schedule it (a few times a day)

Cancellations often land a day or two before a meeting, so run it every ~6 hours.

**Easiest (Windows):** double-click **`setup_schedule.bat`** in this folder. It creates the every-6-hours
task for you and offers to run it once to test. If it reports access denied, right-click it → *Run as
administrator*.

**Or by hand (Windows Task Scheduler)** — one command in an admin Command Prompt:

    schtasks /create /tn "EO_CouncilMeetings" /sc hourly /mo 6 /tr "python C:\Users\jnpie\Documents\new\cornwall_meetings\council_meetings.py"

(If you already made a "CornwallMeetings" task pointing at the old script, delete it:
`schtasks /delete /tn "CornwallMeetings" /f`, then create the one above.)

**Linux / cron:**

    0 */6 * * * cd /path/to/cornwall_meetings && python3 council_meetings.py >> run.log 2>&1

## Output

Written to SharePoint under
`C:\Users\jnpie\LPT\LPT Builds - Operations\07_Products\Second Cut\AgendaMinutes\`, which OneDrive syncs up.
**Cornwall sits at the top level; the nine Prescott-Russell towns are grouped under a `Prescott-Russell\`
folder**, each town keeping its own Agenda/Minutes/index:

    AgendaMinutes\
      Cornwall\              Agenda\  Minutes\  index.html  index.csv
      Prescott-Russell\
        The Nation\          Agenda\  Minutes\  index.html  index.csv
        Russell\             Agenda\  Minutes\  index.html  index.csv
        Clarence-Rockland\   ... (and Champlain, Casselman, Hawkesbury,
        East Hawkesbury\         Alfred-Plantagenet, UCPR (County Council))
      cancellations.csv

- `…\<Town>\index.html` — **open this to browse that town.** A table of meetings; click **Agenda** /
  **Minutes** and the PDF opens (or the online version, for web-only towns).
- `…\<Town>\Agenda\` and `\Minutes\` — the downloaded PDFs, split into two folders.
- `…\<Town>\index.csv` — the same rows as a spreadsheet.
- `AgendaMinutes\cancellations.csv` — every cancellation/reschedule detected across all towns, timestamped.

`state.json` (the watcher's memory) and `email_config.json` (holds a password) stay **local** next to the
script, deliberately out of SharePoint. To change the grouping, edit each town's `group` in `MUNICIPALITIES`
near the top of the script (Cornwall has none, so it stays top-level); change the root via `OUTPUT_BASE`.

> First run of `council_meetings.py`: it builds its own per-town memory, so Cornwall re-downloads its PDFs
> once (harmless — same files). If you ran an earlier version that wrote the PR towns flat (e.g.
> `AgendaMinutes\The Nation\`), those old flat folders are now superseded by `AgendaMinutes\Prescott-Russell\…`
> and can be deleted. Deleting the old `state.json` first gives a clean start.

## Russell / CivicWeb

Russell publishes on CivicWeb, which has no meeting calendar API — instead it's a document library with
`Published Agendas → Council Meetings → <year>` and `Published Minutes → Council Meetings → <year>` folders.
The tool walks those year folders (the two most recent by default — `CIVICWEB_YEARS` near the top) and
pulls the **English PDF** copy of each Regular/Special Council meeting's agenda and minutes (Russell posts
each in English + French × PDF + HTML; the tool takes the English PDF). Two things to know:

- **No cancellation alerts for Russell** — CivicWeb only shows documents after they're published, with no
  forward schedule to compare against, so the watcher doesn't apply to it. The other nine towns still get alerts.
- **Russell's agenda PDFs are large** (the full council package — tens of MB each). `CIVICWEB_YEARS = 2`
  keeps the first-run download sane; raise it to backfill further, but expect a few hundred MB to sync.

## Notes

- Free to run — public eScribe **and** CivicWeb data, no paid services.
- eScribe endpoints were confirmed live for all nine portals; the filtering / English-preference /
  PDF-vs-web / download / cancellation logic was validated on synthetic feeds. The first real scheduled run
  on your machine is the live smoke test — check each town's `index.html` after it runs.
