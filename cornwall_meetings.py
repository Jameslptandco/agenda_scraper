#!/usr/bin/env python3
"""
Cornwall council agenda + minutes scraper + CANCELLATION WATCHER (eScribe).

Each run it:
  1) pulls Regular + Special Meeting of Council agendas and minutes (PDFs) and updates an index;
  2) watches for CANCELLED / RESCHEDULED council meetings and (optionally) emails an alert.

eScribe does NOT flag cancellations - a cancelled meeting is simply removed from the calendar.
So detection is by diff: we remember the upcoming council meetings and alert when one that was
scheduled for a future date disappears (cancelled) or its date changes (rescheduled).

Run it a few times a day on a schedule. Stdlib only. Idempotent.
"""
import json, os, csv, re, smtplib, urllib.request, urllib.parse
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta

BASE = "https://pub-cornwall.escribemeetings.com"
API  = BASE + "/MeetingsCalendarView.aspx/GetCalendarMeetings"
HERE = os.path.dirname(os.path.abspath(__file__))
# --- Outputs (PDFs + index + csv) go to the company SharePoint (OneDrive-synced) folder ---
OUTPUT_DIR = r"C:\Users\jnpie\LPT\LPT Builds - Operations\07_Products\Second Cut\AgendaMinutes\Cornwall"
AGENDA_DIR  = os.path.join(OUTPUT_DIR, "Agenda")
MINUTES_DIR = os.path.join(OUTPUT_DIR, "Minutes")
INDEX_F  = os.path.join(OUTPUT_DIR, "cornwall_council_index.csv")
CANCEL_F = os.path.join(OUTPUT_DIR, "cancellations.csv")
STATE_F   = os.path.join(HERE, "state.json")           # local only (the watcher's memory)
EMAIL_CFG = os.path.join(HERE, "email_config.json")    # local only (holds a password - keep OUT of SharePoint)
COUNCIL_URL = "https://www.cornwall.ca/en/government-council/council-and-committees/council-meetings/"

LOOKBACK_DAYS, LOOKAHEAD_DAYS = 240, 45
COUNCIL_RE = re.compile(r"council", re.I)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
           "Accept": "*/*", "Accept-Language": "en-CA,en;q=0.9", "Referer": BASE + "/"}

# ---------------- eScribe fetch ----------------
def post_json(url, payload, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={**HEADERS, "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8"))

def get_bytes(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r: return r.read()

def fetch_meetings(start, end):
    return post_json(API, {"calendarStartDate": start.strftime("%Y-%m-%dT00:00:00"),
                           "calendarEndDate":   end.strftime("%Y-%m-%dT00:00:00")}).get("d", []) or []

def parse_start(m):
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d"):
        try: return datetime.strptime((m.get("StartDate") or "").strip(), fmt)
        except ValueError: pass
    return None

AGENDA_RE  = re.compile(r"agenda", re.I)
MINUTES_RE = re.compile(r"minute", re.I)   # matches Type "Minutes" AND Cornwall's "PostMinutes"

def pick_pdf(m, type_re):
    for d in (m.get("MeetingDocumentLink") or []):
        if type_re.search((d.get("Type","") or "") + " " + (d.get("Title","") or "")) and str(d.get("Format","")).lower().endswith("pdf"):
            u=(d.get("Url") or "").strip()
            if u: return urllib.parse.urljoin(BASE + "/", u)
    return None

def safe(s): return re.sub(r"[^A-Za-z0-9]+","-", s or "").strip("-")

# ---------------- email alert (optional) ----------------
def load_email_config():
    if not os.path.exists(EMAIL_CFG): return None
    try:
        c = json.load(open(EMAIL_CFG))
        return c if all(c.get(k) for k in ("smtp_host","smtp_port","username","password","to_addr")) else None
    except Exception: return None

def send_email(cfg, subject, body):
    msg = MIMEText(body); msg["Subject"]=subject
    msg["From"]=cfg.get("from_addr") or cfg["username"]; msg["To"]=cfg["to_addr"]
    try:
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30) as s:
            s.starttls(); s.login(cfg["username"], cfg["password"])
            s.sendmail(msg["From"], [a.strip() for a in str(cfg["to_addr"]).split(",")], msg.as_string())
        return True
    except Exception as e:
        print("   email error:", type(e).__name__, e); return False

def compose_alert(events):
    L=["Heads up - a change to a Cornwall City Council meeting was just detected:", ""]
    for e in events:
        if e["event"]=="CANCELLED":
            L.append(f"  - CANCELLED: {e['meeting_type']} scheduled for {e['meeting_date']} is no longer on the calendar.")
        else:
            L.append(f"  - RESCHEDULED: {e['meeting_type']} moved from {e['meeting_date']} to {e.get('new_date','?')}.")
    L += ["", "(The agenda/minutes tool has re-run and updated its files.)",
          "Verify: " + COUNCIL_URL, "", "- Cornwall meeting watcher"]
    return f"Cornwall Council: {events[0]['event'].lower()} detected ({events[0]['meeting_date']})", "\n".join(L)

# ---------------- main ----------------
HTML_F = os.path.join(OUTPUT_DIR, "index.html")
HTML_TOP = '''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Cornwall Council - Agendas & Minutes</title>
<style>
body{font-family:Segoe UI,-apple-system,Arial,sans-serif;margin:0;background:#f5f6f8;color:#1f2430}
.wrap{max-width:920px;margin:24px auto;padding:0 16px}
h1{font-size:20px;margin:0 0 2px}
.sub{color:#6b7280;font-size:13px;margin-bottom:16px}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
th,td{text-align:left;padding:11px 16px;border-bottom:1px solid #eef0f3;font-size:14px}
th{background:#1f3a5f;color:#fff;font-weight:600}
tr:last-child td{border-bottom:none}
tr:hover td{background:#f0f6ff}
td.dt{white-space:nowrap;font-variant-numeric:tabular-nums;color:#374151}
a.doc{display:inline-block;padding:5px 12px;border-radius:5px;text-decoration:none;font-weight:600;font-size:13px}
a.agenda{background:#e7effe;color:#1a56c4} a.agenda:hover{background:#d4e3fd}
a.minutes{background:#e6f4ea;color:#1e7e34} a.minutes:hover{background:#d3edda}
.pending{color:#9aa1ab;font-style:italic;font-size:13px} .na{color:#c3c7cd}
</style></head><body><div class="wrap">
<h1>City of Cornwall &ndash; Council Agendas &amp; Minutes</h1>
<div class="sub">Regular &amp; Special Meetings of Council &middot; __N__ meetings &middot; updated __TS__ &middot; click <b>Agenda</b> or <b>Minutes</b> to open the PDF</div>
<table><tr><th>Date</th><th>Meeting</th><th>Agenda</th><th>Minutes</th></tr>
'''
HTML_BOT = '''</table>
<div class="sub" style="margin-top:12px">Recent meetings show &ldquo;pending&rdquo; minutes until they&rsquo;re approved at the next meeting &ndash; the scheduled runs fill them in automatically.</div>
</div></body></html>'''

def write_html_index(rows_sorted):
    def acell(fn): return ('<a class="doc agenda" target="_blank" href="Agenda/%s">Agenda</a>' % fn) if fn else '<span class="na">-</span>'
    def mcell(fn): return ('<a class="doc minutes" target="_blank" href="Minutes/%s">Minutes</a>' % fn) if fn else '<span class="pending">pending</span>'
    trs=[]
    for r in rows_sorted:
        trs.append('<tr><td class="dt">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            r.get("date",""), r.get("meeting_type",""), acell(r.get("agenda_pdf") or ""), mcell(r.get("minutes_pdf") or "")))
    html = HTML_TOP.replace("__TS__", datetime.now().strftime("%Y-%m-%d %H:%M")).replace("__N__", str(len(rows_sorted))) + "\n".join(trs) + HTML_BOT
    with open(HTML_F, "w", encoding="utf-8") as f: f.write(html)

# ---------------- main ----------------
def run(_fetch=fetch_meetings, _get=get_bytes, _send=send_email):
    os.makedirs(AGENDA_DIR, exist_ok=True); os.makedirs(MINUTES_DIR, exist_ok=True)
    state = json.load(open(STATE_F)) if os.path.exists(STATE_F) else {}
    done, prev_up, alerted = set(state.get("done",[])), state.get("upcoming",{}), set(state.get("alerted",[]))
    rows = {}
    if os.path.exists(INDEX_F):
        for r in csv.DictReader(open(INDEX_F, encoding="utf-8")): rows[r["meeting_id"]]=r
    today = date.today()
    meetings = _fetch(today - timedelta(days=LOOKBACK_DAYS), today + timedelta(days=LOOKAHEAD_DAYS))
    council = [m for m in meetings if COUNCIL_RE.search(m.get("MeetingType","") or "")]

    # ---- detect cancellations / reschedules ----
    cur_up, cur_ids = {}, set()
    for m in council:
        dt = parse_start(m)
        if not dt: continue
        cur_ids.add(m["ID"])
        if dt.date() >= today:
            cur_up[m["ID"]] = {"date": dt.strftime("%Y-%m-%d"), "type": m.get("MeetingType","")}
    prev_count = state.get("last_council_count", 0)
    feed_healthy = len(council) > 0 and (prev_count == 0 or len(council) >= prev_count*0.5)
    events = []
    if feed_healthy and prev_up:
        for mid, info in prev_up.items():
            try: mdate = datetime.strptime(info["date"], "%Y-%m-%d").date()
            except Exception: mdate = today
            if mid not in cur_ids:                                    # vanished from calendar
                if mdate >= today - timedelta(days=1) and mid not in alerted:
                    events.append({"event":"CANCELLED","meeting_type":info.get("type",""),"meeting_date":info["date"],"meeting_id":mid}); alerted.add(mid)
            elif mid in cur_up and cur_up[mid]["date"] != info["date"]:  # date moved
                k = mid + cur_up[mid]["date"]
                if k not in alerted:
                    events.append({"event":"RESCHEDULED","meeting_type":info.get("type",""),"meeting_date":info["date"],"new_date":cur_up[mid]["date"],"meeting_id":mid}); alerted.add(k)

    # ---- download agendas + minutes ----
    log=[]
    for m in council:
        dt=parse_start(m); ymd=dt.strftime("%Y-%m-%d") if dt else "unknown"; mid=m.get("ID") or ymd
        rec=rows.get(mid) or {"meeting_id":mid,"date":ymd,"meeting_type":m.get("MeetingType",""),"meeting_name":m.get("MeetingName",""),"agenda_pdf":"","minutes_pdf":"","agenda_url":"","minutes_url":""}
        rec["date"],rec["meeting_type"]=ymd,m.get("MeetingType","")
        for label, type_re in (("Agenda", AGENDA_RE), ("Minutes", MINUTES_RE)):
            key=label.lower(); url=pick_pdf(m, type_re)
            if not url: continue
            rec[f"{key}_url"]=url; fname=f"{ymd}_{safe(m.get('MeetingType','Council'))}_{label}.pdf"; fpath=os.path.join(AGENDA_DIR if label=="Agenda" else MINUTES_DIR, fname)
            if url in done and os.path.exists(fpath): rec[f"{key}_pdf"]=fname; continue
            try:
                blob=_get(url)
                if blob[:4]==b"%PDF":
                    open(fpath,"wb").write(blob); rec[f"{key}_pdf"]=fname; done.add(url); log.append(f"{ymd} {label}")
                else: log.append(f"non-pdf {ymd} {label}")
            except Exception as e: log.append(f"FAIL {ymd} {label}: {type(e).__name__}")
        rows[mid]=rec

    # ---- act on events: log + email ----
    if events:
        new = not os.path.exists(CANCEL_F) or os.path.getsize(CANCEL_F)==0
        with open(CANCEL_F,"a",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            if new: w.writerow(["detected","event","meeting_type","meeting_date","new_date","meeting_id"])
            for e in events: w.writerow([datetime.now().isoformat(timespec="seconds"),e["event"],e["meeting_type"],e["meeting_date"],e.get("new_date",""),e["meeting_id"]])
        cfg=load_email_config()
        if cfg:
            subj,body=compose_alert(events); ok=_send(cfg,subj,body)
            print(("   emailed alert OK" if ok else "   EMAIL FAILED - see cancellations.csv") + f" ({len(events)} event(s))")
        else:
            print(f"   ** {len(events)} CANCELLATION/RESCHEDULE detected - no email_config.json yet, logged to cancellations.csv **")
        for e in events: print("     ", e["event"], e["meeting_type"], e["meeting_date"], "->", e.get("new_date","(off calendar)"))

    # ---- write index + state ----
    cols=["date","meeting_type","meeting_name","agenda_pdf","minutes_pdf","meeting_id","agenda_url","minutes_url"]
    out=sorted(rows.values(), key=lambda r:r.get("date",""), reverse=True)
    with open(INDEX_F,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore"); w.writeheader(); w.writerows(out)
    write_html_index(out)
    state["done"]=sorted(done); state["alerted"]=sorted(alerted)
    if feed_healthy:
        state["upcoming"]=cur_up; state["last_council_count"]=len(council)
    json.dump(state, open(STATE_F,"w"), indent=1)
    print(f"{datetime.now():%Y-%m-%d %H:%M}  council in window:{len(council)}  new downloads:{len(log)}  index:{len(out)}  events:{len(events)}")

if __name__ == "__main__":
    run()
