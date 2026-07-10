#!/usr/bin/env python3
"""
Eastern Ontario council agenda + minutes scraper + cancellation watcher (eScribe).
Covers Cornwall + the Prescott-Russell municipalities in one run. For each town it pulls the
Regular + Special *council* meeting agendas and minutes: downloads the PDF where the town posts one,
and links the online version where the town only publishes HTML. Saves to a per-town SharePoint
folder (Agenda/ + Minutes/ + index.html), and emails on detected cancellations/reschedules.
Stdlib only. Idempotent. Run a few times a day on a schedule.
"""
import json, os, csv, re, html, smtplib, urllib.request, urllib.parse
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_BASE = r"C:\Users\jnpie\LPT\LPT Builds - Operations\07_Products\Second Cut\AgendaMinutes"
STATE_F   = os.path.join(HERE, "state.json")          # local (watcher memory)
EMAIL_CFG = os.path.join(HERE, "email_config.json")   # local (holds a password - keep OUT of SharePoint)

# (SharePoint subfolder name, eScribe subdomain)
MUNICIPALITIES = [
    {"name":"Cornwall",              "platform":"escribe",  "sub":"pub-cornwall"},
    {"name":"The Nation",            "platform":"escribe",  "sub":"pub-thenation",          "group":"Prescott-Russell"},
    {"name":"East Hawkesbury",       "platform":"escribe",  "sub":"pub-easthawkesbury",     "group":"Prescott-Russell"},
    {"name":"Alfred-Plantagenet",    "platform":"escribe",  "sub":"pub-alfred-plantagenet", "group":"Prescott-Russell"},
    {"name":"Clarence-Rockland",     "platform":"escribe",  "sub":"cr-pub",                 "group":"Prescott-Russell"},
    {"name":"Champlain",             "platform":"escribe",  "sub":"pub-champlain",          "group":"Prescott-Russell"},
    {"name":"Casselman",             "platform":"escribe",  "sub":"pub-casselman",          "group":"Prescott-Russell"},
    {"name":"Hawkesbury",            "platform":"escribe",  "sub":"pub-hawkesbury",         "group":"Prescott-Russell"},
    {"name":"UCPR (County Council)", "platform":"escribe",  "sub":"pub-ucpr",               "group":"Prescott-Russell"},
    {"name":"Russell",               "platform":"civicweb", "host":"russell.civicweb.net",
     "agenda_folder":42032, "minutes_folder":42034,                                         "group":"Prescott-Russell"},
]

LOOKBACK_DAYS, LOOKAHEAD_DAYS = 240, 45
INC_RE = re.compile(r"council|conseil|regular meeting|special meeting|r.union ordinaire|s.ance ordinaire", re.I)
EXC_RE = re.compile(r"committee|comit|closed|huis|public|planning|zoning|variance|advisory|consultation|engagement|statutory|budget|library|management|standing|inaugural", re.I)
AGENDA_RE  = re.compile(r"agenda|ordre du jour", re.I)
MINUTES_RE = re.compile(r"minute|proc.s|postminutes", re.I)
VERIFY_URL = "https://www.prescott-russell.on.ca/"

HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
           "Accept":"*/*", "Accept-Language":"en-CA,en;q=0.9"}

def fetch_meetings(base, start, end, timeout=60):
    api = base + "/MeetingsCalendarView.aspx/GetCalendarMeetings"
    body = json.dumps({"calendarStartDate": start.strftime("%Y-%m-%dT00:00:00"),
                       "calendarEndDate":   end.strftime("%Y-%m-%dT00:00:00")}).encode()
    req = urllib.request.Request(api, data=body,
        headers={**HEADERS, "Content-Type":"application/json", "X-Requested-With":"XMLHttpRequest", "Referer": base+"/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8")).get("d", []) or []

def get_bytes(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r: return r.read()

def parse_start(m):
    for fmt in ("%Y/%m/%d %H:%M:%S","%Y-%m-%d %H:%M:%S","%Y/%m/%d","%Y-%m-%d"):
        try: return datetime.strptime((m.get("StartDate") or "").strip(), fmt)
        except ValueError: pass
    return None

def is_council(m):
    t = m.get("MeetingType","") or ""
    return bool(INC_RE.search(t)) and not EXC_RE.search(t)

def pick_doc(m, type_re, base):
    """Best matching doc, preferring English PDF > any PDF > English HTML > any HTML. Returns (url, is_pdf)."""
    cands = [d for d in (m.get("MeetingDocumentLink") or [])
             if type_re.search((d.get("Type","") or "") + " " + (d.get("Title","") or ""))]
    if not cands: return (None, False)
    def score(d):
        is_pdf = str(d.get("Format","")).lower().endswith("pdf")
        title = (d.get("Title","") or "").lower(); lang = (d.get("LanguageCode","") or "").lower()
        fr = ("ordre du jour" in title) or ("verbal" in title) or ("proc" in title and "s" in title and "pdf" not in title) or ("fr" in lang and "en" not in lang)
        return (2 if is_pdf else 0) + (0 if fr else 1)
    best = max(cands, key=score)
    return (urllib.parse.urljoin(base + "/", (best.get("Url") or "").strip()),
            str(best.get("Format","")).lower().endswith("pdf"))

def safe(s):   return re.sub(r"[^A-Za-z0-9]+","-", s or "").strip("-")
def folder(s): return re.sub(r"[^A-Za-z0-9 ()-]+","", s or "").strip()
def muni_dir(muni):
    g = (muni.get("group") or "").strip()
    return os.path.join(OUTPUT_BASE, folder(g), folder(muni["name"])) if g else os.path.join(OUTPUT_BASE, folder(muni["name"]))

# ---------- email ----------
def load_email_config():
    if not os.path.exists(EMAIL_CFG): return None
    try:
        c=json.load(open(EMAIL_CFG)); return c if all(c.get(k) for k in ("smtp_host","smtp_port","username","password","to_addr")) else None
    except Exception: return None
def send_email(cfg, subject, body):
    msg=MIMEText(body); msg["Subject"]=subject; msg["From"]=cfg.get("from_addr") or cfg["username"]; msg["To"]=cfg["to_addr"]
    try:
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30) as s:
            s.starttls(); s.login(cfg["username"], cfg["password"])
            s.sendmail(msg["From"], [a.strip() for a in str(cfg["to_addr"]).split(",")], msg.as_string())
        return True
    except Exception as e: print("   email error:", type(e).__name__, e); return False

# ---------- html index ----------
HTML_TOP='''<!DOCTYPE html><html><head><meta charset="utf-8"><title>__MUNI__ - Agendas & Minutes</title>
<style>body{font-family:Segoe UI,-apple-system,Arial,sans-serif;margin:0;background:#f5f6f8;color:#1f2430}
.wrap{max-width:940px;margin:24px auto;padding:0 16px}h1{font-size:20px;margin:0 0 2px}
.sub{color:#6b7280;font-size:13px;margin-bottom:16px}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
th,td{text-align:left;padding:11px 16px;border-bottom:1px solid #eef0f3;font-size:14px}th{background:#1f3a5f;color:#fff;font-weight:600}
tr:last-child td{border-bottom:none}tr:hover td{background:#f0f6ff}td.dt{white-space:nowrap;color:#374151}
a.doc{display:inline-block;padding:5px 12px;border-radius:5px;text-decoration:none;font-weight:600;font-size:13px}
a.agenda{background:#e7effe;color:#1a56c4}a.minutes{background:#e6f4ea;color:#1e7e34}
a.online{background:#fff4e5;color:#b26a00}.pending{color:#9aa1ab;font-style:italic;font-size:13px}.na{color:#c3c7cd}</style>
</head><body><div class="wrap"><h1>__MUNI__ &ndash; Council Agendas &amp; Minutes</h1>
<div class="sub">Regular &amp; Special council meetings &middot; __N__ meetings &middot; updated __TS__ &middot; click to open (green/blue = downloaded PDF, orange = view online)</div>
<table><tr><th>Date</th><th>Meeting</th><th>Agenda</th><th>Minutes</th></tr>
'''
HTML_BOT='''</table><div class="sub" style="margin-top:12px">"pending" minutes appear once approved at the next meeting. "online" links open the eScribe web version (that town only posts that document as a web page, not a PDF).</div></div></body></html>'''

def _cell(val, cls, label):
    if not val: return '<span class="pending">pending</span>' if cls=="minutes" else '<span class="na">-</span>'
    kind, ref = val.split("|", 1)
    if kind == "pdf":    return '<a class="doc %s" target="_blank" href="%s">%s</a>' % (cls, ref, label)
    return '<a class="doc online" target="_blank" href="%s">%s (online)</a>' % (ref, label)

def write_html_index(muni, out_dir, rows):
    trs = ['<tr><td class="dt">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        r["date"], r["meeting_type"], _cell(r.get("agenda"),"agenda","Agenda"), _cell(r.get("minutes"),"minutes","Minutes")) for r in rows]
    html = HTML_TOP.replace("__MUNI__", muni).replace("__TS__", datetime.now().strftime("%Y-%m-%d %H:%M")).replace("__N__", str(len(rows))) + "\n".join(trs) + HTML_BOT
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f: f.write(html)

# ---------- per-municipality ----------
def process_escribe(muni, state, log, _fetch, _get):
    name = muni["name"]; sub = muni["sub"]
    base = "https://%s.escribemeetings.com" % sub
    out_dir = muni_dir(muni)
    dirs = {"Agenda": os.path.join(out_dir,"Agenda"), "Minutes": os.path.join(out_dir,"Minutes")}
    for d in dirs.values(): os.makedirs(d, exist_ok=True)
    ms = state.setdefault(name, {"done":[], "upcoming":{}, "alerted":[], "last_count":0})
    done, prev_up, alerted = set(ms["done"]), ms["upcoming"], set(ms["alerted"])
    today = date.today()
    try:
        meetings = _fetch(base, today-timedelta(days=LOOKBACK_DAYS), today+timedelta(days=LOOKAHEAD_DAYS))
    except Exception as e:
        log.append("%-22s fetch FAILED (%s)" % (name, type(e).__name__)); return []
    council = [m for m in meetings if is_council(m)]
    cur_up, cur_ids = {}, set()
    for m in council:
        dt = parse_start(m)
        if not dt: continue
        cur_ids.add(m["ID"])
        if dt.date() >= today: cur_up[m["ID"]] = {"date": dt.strftime("%Y-%m-%d"), "type": m.get("MeetingType","")}
    events = []
    healthy = len(council) > 0 and (ms["last_count"]==0 or len(council) >= ms["last_count"]*0.5)
    if healthy and prev_up:
        for mid, info in prev_up.items():
            try: md = datetime.strptime(info["date"], "%Y-%m-%d").date()
            except Exception: md = today
            if mid not in cur_ids:
                if md >= today-timedelta(days=1) and mid not in alerted:
                    events.append({"event":"CANCELLED","muni":name,"meeting_type":info.get("type",""),"meeting_date":info["date"]}); alerted.add(mid)
            elif mid in cur_up and cur_up[mid]["date"] != info["date"] and (mid+cur_up[mid]["date"]) not in alerted:
                events.append({"event":"RESCHEDULED","muni":name,"meeting_type":info.get("type",""),"meeting_date":info["date"],"new_date":cur_up[mid]["date"]}); alerted.add(mid+cur_up[mid]["date"])
    rows, ndl = [], 0
    for m in council:
        dt = parse_start(m); ymd = dt.strftime("%Y-%m-%d") if dt else "unknown"
        rec = {"date": ymd, "meeting_type": m.get("MeetingType","")}
        for label, type_re in (("Agenda", AGENDA_RE), ("Minutes", MINUTES_RE)):
            url, is_pdf = pick_doc(m, type_re, base)
            if not url: continue
            if is_pdf:
                fname = "%s_%s_%s.pdf" % (ymd, safe(m.get("MeetingType","")), label); fpath = os.path.join(dirs[label], fname)
                if url in done and os.path.exists(fpath): rec[label.lower()] = "pdf|%s/%s" % (label, fname); continue
                try:
                    blob = _get(url)
                    if blob[:4] == b"%PDF":
                        with open(fpath,"wb") as f: f.write(blob)
                        rec[label.lower()] = "pdf|%s/%s" % (label, fname); done.add(url); ndl += 1
                    else: rec[label.lower()] = "web|%s" % url
                except Exception: rec[label.lower()] = "web|%s" % url
            else:
                rec[label.lower()] = "web|%s" % url   # HTML-only -> online link
        rows.append(rec)
    rows.sort(key=lambda r: r["date"], reverse=True)
    write_html_index(name, out_dir, rows)
    with open(os.path.join(out_dir, "index.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date","meeting_type","agenda","minutes"])
        for r in rows: w.writerow([r["date"], r["meeting_type"], r.get("agenda",""), r.get("minutes","")])
    ms["done"] = sorted(done); ms["alerted"] = sorted(alerted)
    if healthy: ms["upcoming"] = cur_up; ms["last_count"] = len(council)
    log.append("%-22s council=%-3d new PDFs=%-3d" % (name, len(council), ndl))
    return events

# ---------- CivicWeb (Russell) ----------
CW_ROW_RE = re.compile(r'class="document-list-view-documents"[^>]*?data-id="(\d+)"[^>]*?data-type="(folder|document)"[^>]*?data-title="([^"]*)"')
CIVICWEB_YEARS = 2   # walk this many most-recent year folders per document tree

def _cw_html(host, folder_id, _get):
    return _get("https://%s/filepro/documents/%s" % (host, folder_id)).decode("utf-8", "replace")

def _cw_years(host, root, _get):
    out = {}
    for did, typ, title in CW_ROW_RE.findall(_cw_html(host, root, _get)):
        t = html.unescape(title).strip()
        if typ == "folder" and re.fullmatch(r"\d{4}", t): out[int(t)] = did
    return out

def _cw_docs(host, fid, _get):
    return [(did, html.unescape(title)) for did, typ, title in CW_ROW_RE.findall(_cw_html(host, fid, _get)) if typ == "document"]

def process_civicweb(muni, state, log, _get):
    name = muni["name"]; host = muni["host"]
    out_dir = muni_dir(muni)
    dirs = {"Agenda": os.path.join(out_dir, "Agenda"), "Minutes": os.path.join(out_dir, "Minutes")}
    for d in dirs.values(): os.makedirs(d, exist_ok=True)
    ms = state.setdefault(name, {"done": []}); done = set(ms.get("done", []))
    by_key = {}; ndl = 0
    for label, root in (("Agenda", muni["agenda_folder"]), ("Minutes", muni["minutes_folder"])):
        try: years = _cw_years(host, root, _get)
        except Exception as e:
            log.append("%-22s %s fetch FAILED (%s)" % (name, label, type(e).__name__)); continue
        for y in sorted(years, reverse=True)[:CIVICWEB_YEARS]:
            try: docs = _cw_docs(host, years[y], _get)
            except Exception: continue
            for did, title in docs:
                if not re.search(r"council", title, re.I): continue     # English council meetings (excludes FR "conseil")
                if not title.rstrip().endswith("Pdf"): continue          # prefer the PDF copy over Html
                md = re.search(r"(\d{4}-\d{2}-\d{2})", title)
                if not md: continue
                ymd = md.group(1); mtype = title.split(" - ")[0].strip()
                rec = by_key.setdefault((ymd, mtype), {"date": ymd, "meeting_type": mtype})
                if rec.get(label.lower()): continue
                url = "https://%s/document/%s" % (host, did)
                fname = "%s_%s_%s.pdf" % (ymd, safe(mtype), label)
                fpath = os.path.join(dirs[label], fname)
                if url in done and os.path.exists(fpath): rec[label.lower()] = "pdf|%s/%s" % (label, fname); continue
                try:
                    blob = _get(url)
                    if blob[:4] == b"%PDF":
                        with open(fpath, "wb") as f: f.write(blob)
                        rec[label.lower()] = "pdf|%s/%s" % (label, fname); done.add(url); ndl += 1
                    else: rec[label.lower()] = "web|%s" % url
                except Exception: pass
    rows = sorted(by_key.values(), key=lambda r: r["date"], reverse=True)
    write_html_index(name, out_dir, rows)
    with open(os.path.join(out_dir, "index.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date","meeting_type","agenda","minutes"])
        for r in rows: w.writerow([r["date"], r["meeting_type"], r.get("agenda",""), r.get("minutes","")])
    ms["done"] = sorted(done)
    log.append("%-22s meetings=%-3d new PDFs=%-3d" % (name, len(rows), ndl))
    return []

def process_muni(muni, state, log, _fetch, _get):
    if muni.get("platform") == "civicweb": return process_civicweb(muni, state, log, _get)
    return process_escribe(muni, state, log, _fetch, _get)

def run(_fetch=fetch_meetings, _get=get_bytes):
    state = json.load(open(STATE_F)) if os.path.exists(STATE_F) else {}
    log, all_events = [], []
    for muni in MUNICIPALITIES:
        all_events += process_muni(muni, state, log, _fetch, _get)
    if all_events:
        cfg = load_email_config()
        lines = ["Heads up - Eastern Ontario council meeting change(s) detected:", ""]
        for e in all_events:
            if e["event"]=="CANCELLED": lines.append("  - CANCELLED: %s %s (%s) is no longer on the calendar." % (e["muni"], e["meeting_type"], e["meeting_date"]))
            else: lines.append("  - RESCHEDULED: %s %s moved from %s to %s." % (e["muni"], e["meeting_type"], e["meeting_date"], e.get("new_date","?")))
        lines += ["", "(The tool re-ran and updated its files.)", "- EO council meeting watcher"]
        subj = "Council meetings: %d change(s) detected" % len(all_events)
        if cfg: print("   " + ("emailed alert" if send_email(cfg, subj, "\n".join(lines)) else "EMAIL FAILED"))
        else:   print("   ** %d cancellation/reschedule detected (no email_config.json yet) **" % len(all_events))
        for e in all_events: print("     ", e["event"], e["muni"], e["meeting_type"], e["meeting_date"])
        clog = os.path.join(OUTPUT_BASE, "cancellations.csv")
        try:
            newf = not os.path.exists(clog)
            with open(clog, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if newf: w.writerow(["detected_at","event","municipality","meeting_type","meeting_date","new_date"])
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                for e in all_events: w.writerow([ts, e["event"], e["muni"], e["meeting_type"], e["meeting_date"], e.get("new_date","")])
        except Exception as ex: print("   cancellations.csv write error:", ex)
    json.dump(state, open(STATE_F, "w"), indent=1)
    print("%s  |  %d municipalities" % (datetime.now().strftime("%Y-%m-%d %H:%M"), len(MUNICIPALITIES)))
    for l in log: print("  ", l)

if __name__ == "__main__":
    run()
