# Eastern Ontario Council Agendas & Minutes — scraper + cancellation watcher

`council_meetings.py` pulls **Regular + Special *council* meeting** agendas and minutes for **42 Eastern
Ontario municipalities** — Cornwall, Ottawa, Kingston, Prescott-Russell, SD&G, the Bay of Quinte,
Leeds & Grenville, Lanark, and Renfrew — in one run, saves them to a per-town folder on SharePoint, builds a
click-through `index.html` per town, and watches for cancelled/rescheduled meetings.

> This **supersedes `cornwall_meetings.py`** (Cornwall is now just the first town in the list). Schedule
> `council_meetings.py` instead; you can delete the old `cornwall_meetings.py` once you're happy.

## Towns covered

- **Cornwall**, **Ottawa**, **Kingston** (top-level standalone cities; for the big cities the tool takes
  *City Council* only, skipping their many committees, boards and commissions)
- **Lanark** group (3): Carleton Place, Smiths Falls, Perth
- **Renfrew** group (1): Renfrew
- **Prescott-Russell** group (9): The Nation, East Hawkesbury, Alfred-Plantagenet, Clarence-Rockland,
  Champlain, Casselman, Hawkesbury, UCPR (county council), Russell Township
- **SDG** group (7): South Stormont, North Stormont, South Dundas, North Dundas, South Glengarry, SDG Counties,
  North Glengarry
- **Quinte** group (11): Belleville, Quinte West, Prince Edward County, Tweed, Loyalist, Greater Napanee,
  Stone Mills, Addington Highlands, Deseronto, Hastings County, Lennox-Addington County
- **Leeds-Grenville** group (8): Brockville, Prescott, North Grenville, Rideau Lakes, Augusta,
  Edwardsburgh-Cardinal, Leeds & the Thousand Islands, United Counties (L&G)

Most towns run on **eScribe** or **CivicWeb** (the tool auto-handles both — see "CivicWeb towns" below).
**North Glengarry** is the exception: it self-hosts its agenda PDFs on its own website, so it uses a third
**`webpage`** path (see "North Glengarry / webpage" below). All land in the same per-town folder structure
with the same click-through index.

**Not included** — **Gananoque** self-hosts to an S3 bucket (a page-scraper could be added the same way as
North Glengarry if wanted, or use the email route). A handful of very small townships also have no clean
portal we could find (Elizabethtown-Kitley, Merrickville-Wolford, Athens, Centre Hastings, Stirling-Rawdon,
and some small Hastings townships) — low priority given their size.

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
**Cornwall sits at the top level; the other towns are grouped by region** (`Prescott-Russell\`, `Quinte\`),
each town keeping its own Agenda/Minutes/index:

    AgendaMinutes\
      Cornwall\                 Agenda\  Minutes\  index.html  index.csv
      Prescott-Russell\
        The Nation\  Russell\  Clarence-Rockland\  ...  (9 towns, each with
                                                          Agenda\ Minutes\ index.html)
      SDG\
        South Stormont\  North Stormont\  South Dundas\  ...  (6 towns)
      Quinte\
        Belleville\  Quinte West\  Prince Edward County\  ...  (9 towns)
      Leeds-Grenville\
        Brockville\  Prescott\  North Grenville\  ...  (5 towns)
      cancellations.csv

- `AgendaMinutes\index.html` — **the front door.** One page linking all 42 towns grouped by region;
  click a town to open its agendas/minutes. Regenerated on every run.
- `…\<Town>\index.html` — **that town's page.** A table of meetings; click **Agenda** /
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

## CivicWeb towns (Russell, Belleville, Quinte West, Prince Edward County)

These four publish on CivicWeb, which has no meeting calendar API — it's a document library of
`… → Council → <year>` folders. The tool walks the year folders (the two most recent by default —
`CIVICWEB_YEARS` near the top) and pulls the **PDF** copy of each Regular/Special council agenda and
minutes. CivicWeb sites vary in layout, and the tool handles the variations seen across these four:

- **Date formats differ** — Russell uses `2026-06-22`; Belleville, Quinte West and PEC use `22 Jun 2026`.
- **Some nest an extra level** — Quinte West files each meeting in its own subfolder (`year → meeting → docs`)
  and Stone Mills files by month (`year → month → docs`); the tool descends into those automatically.
  Belleville, Loyalist, Greater Napanee and Russell keep the PDFs flat in the year folder.
- **PEC combines** agendas and minutes in one folder and tells them apart by the document title; the tool
  splits them into the Agenda/ and Minutes/ folders accordingly.
- **Bilingual / HTML copies** — where a town posts English + French or PDF + HTML, the tool takes the
  English PDF.

Two things to know about all four CivicWeb towns:

- **No cancellation alerts** — CivicWeb only shows documents after they're published, with no forward
  schedule to compare against, so the watcher doesn't apply. The nine eScribe towns still get alerts.
- **Agenda PDFs are large** (the full council package — tens of MB each). `CIVICWEB_YEARS = 2` keeps the
  first-run download sane; raise it to backfill further, but expect a few hundred MB to sync.
- **Size cap:** any single PDF larger than `MAX_PDF_MB` (default 150) is **linked online instead of
  downloaded** — it shows as an "(online)" link in that town's index. This mainly affects Russell, whose
  agenda packages run 200–300 MB. Raise/lower `MAX_PDF_MB` near the top of the script to taste.

## North Glengarry / webpage

North Glengarry has no meeting portal — it posts agenda/minutes PDFs (`/media/…`) directly on its
[Council Meeting Information page](https://www.northglengarry.ca/government/council-meeting-information/).
The `webpage` platform reads that page top-to-bottom, tracks the current meeting date (a heading), and
attaches each Agenda/Minutes link that follows to it. Live-checked against the real page: it finds ~36
council meetings for the last two years (agendas + minutes). Two caveats:

- **More fragile than the portal towns.** It depends on the page's HTML layout; if the Township redesigns
  that page, the parser may need a tweak. The eScribe/CivicWeb towns are far more stable.
- **No cancellation alerts** (same as the CivicWeb towns — no forward schedule to compare against).

To point it at a different self-hosted town later (e.g. Gananoque), copy the North Glengarry entry in
`MUNICIPALITIES`, change `base`/`listing_url`, and confirm that town lists Agenda/Minutes links the same way.

## Keyword digest (`digest.py`) — turning the archive into leads

`digest.py` is a companion that reads the AgendaMinutes archive this tool builds and scans each **new**
agenda/minutes PDF for economic / labour-market signals — new development, business activity, hiring,
investment, and big-dollar items — then writes a **digest of leads** for the newsletter.

    python digest.py

Output goes to `AgendaMinutes\_Digests\`: `digest.html` (open this — leads grouped by town, each with the
matched terms, a snippet of context, and a click-through to the source PDF), a dated copy, and `leads.csv`.
It's incremental — it remembers what it's scanned (`digest_state.json`, local) and only reports new
documents each run, so it works as a **weekly digest**. If `email_config.json` is set up (same file the
meeting watcher uses), it emails the digest too.

- **Tune it at the top of the script:** `KEYWORDS` (the terms, grouped by category — edit freely),
  `SCAN_DAYS` (how far back, default 120), `SCAN_TYPES` (agendas, minutes, or both), `MAX_PDF_MB` (skips the
  giant Russell agendas), `MAX_PAGES` (how deep to read each agenda).
- Needs PyMuPDF (`pip install pymupdf`) to read the PDFs — the same reader the permit harvester uses.
- Sanity-checked live: a scan of 60 recent **minutes** surfaced **48 leads across 25 towns** (e.g. Cornwall
  "subdivision; new business; job creation; $2.5M", Belleville "industrial park; economic development").

## Notes

- Free to run — public eScribe, CivicWeb **and** self-hosted municipal pages, no paid services.
- eScribe endpoints were confirmed live for all nine portals; the filtering / English-preference /
  PDF-vs-web / download / cancellation logic was validated on synthetic feeds. The first real scheduled run
  on your machine is the live smoke test — check each town's `index.html` after it runs.
