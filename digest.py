#!/usr/bin/env python3
"""
Council-meeting KEYWORD DIGEST - Second Cut LMI.

Companion to council_meetings.py. Reads the AgendaMinutes archive it produces, scans each new
agenda/minutes PDF for economic / labour-market signals (new development, business activity,
hiring, investment, big-dollar items), pulls a bit of context around every hit, and writes a
digest of "leads" (HTML + CSV) for the newsletter. Optional email. Idempotent: only new/changed
documents are reported each run.

Stdlib + PyMuPDF (pip install pymupdf).  Run:  python digest.py
"""
import os, re, csv, json, html, smtplib, urllib.parse
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jnpie\LPT\LPT Builds - Operations\07_Products\Second Cut\AgendaMinutes"
OUT_DIR   = os.path.join(ROOT, "_Digests")
STATE_F   = os.path.join(HERE, "digest_state.json")     # local: which files already scanned
EMAIL_CFG = os.path.join(HERE, "email_config.json")     # reuse the meetings one (holds a password)

SCAN_DAYS  = 120                 # only meetings within this many days (keeps it current + fast)
MAX_PDF_MB = 60                  # skip text-extraction on PDFs bigger than this (the Russell monsters)
MAX_PAGES  = 60                  # only read the first N pages (agenda business is front-loaded)
SCAN_TYPES = ("Agenda", "Minutes")
SNIPPETS_PER_DOC = 4             # cap context snippets shown per document

# --- what counts as a lead. Edit freely; terms are lowercase substrings. ---
KEYWORDS = {
 "Development": ["site plan","plan of subdivision","subdivision","rezoning","zoning by-law amendment",
                 "official plan amendment","development application","development charge","severance",
                 "condominium","site alteration","ground breaking","groundbreaking"],
 "Business":    ["new business","business expansion","grand opening","ribbon cutting","now open",
                 "permanently clos","ceased operations","industrial park","business park",
                 "commercial development","new commercial","warehouse","distribution centre"],
 "Jobs":        ["now hiring","job creation","new jobs","job fair","layoff","workforce",
                 "employment lands","employer","staffing"],
 "Investment":  ["economic development","community improvement plan","funding announcement",
                 "grant application","provincial funding","federal funding","incentive"],
 "Institutional":["hospital","long-term care","long term care","urgent care","family health team","new school"],
}
MONEY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:million|billion)\b|\$\s?\d{1,3}(?:,\d{3}){2,}(?:\.\d{2})?", re.I)

def collapse(s): return re.sub(r"\s+", " ", s).strip()

def parse_meta(path):
    fn = os.path.basename(path)
    m = re.match(r"(\d{4}-\d{2}-\d{2})_(.+)_(Agenda|Minutes)\.pdf$", fn)
    if not m: return None
    town = os.path.basename(os.path.dirname(os.path.dirname(path)))     # .../<town>/<Agenda|Minutes>/<file>
    return {"date": m.group(1), "town": town, "type": m.group(3),
            "meeting": m.group(2).replace("-", " "), "path": path, "file": fn}

def extract_text(path):
    import fitz
    doc = fitz.open(path)
    return "\n".join(doc[i].get_text("text") for i in range(min(len(doc), MAX_PAGES)))

def find_hits(text):
    low = text.lower(); hits = {}
    for cat, terms in KEYWORDS.items():
        for term in terms:
            i = low.find(term)
            if i >= 0:
                snip = collapse(text[max(0, i-60): i+len(term)+70])
                hits.setdefault(cat, {}).setdefault(term.strip(), snip)
    for m in MONEY_RE.finditer(text):
        hits.setdefault("Big $", {}).setdefault(collapse(m.group(0)), collapse(text[max(0, m.start()-55): m.end()+45]))
    return hits

def load(p, d):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return d

# ---- email (optional, reuses the meetings config) ----
def email_cfg():
    c = load(EMAIL_CFG, None)
    return c if c and all(c.get(k) for k in ("smtp_host","smtp_port","username","password","to_addr")) else None
def send_email(cfg, subject, body):
    msg = MIMEText(body, "html"); msg["Subject"]=subject; msg["From"]=cfg.get("from_addr") or cfg["username"]; msg["To"]=cfg["to_addr"]
    with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30) as s:
        s.starttls(); s.login(cfg["username"], cfg["password"])
        s.sendmail(msg["From"], [a.strip() for a in str(cfg["to_addr"]).split(",")], msg.as_string())

# ---- html ----
CATCLR = {"Development":"#1a56c4","Business":"#b26a00","Jobs":"#1e7e34","Investment":"#7a3ea8","Institutional":"#c0392b","Big $":"#2c3e50"}
def esc(s): return html.escape(s or "")
def render(leads, generated, ndocs):
    towns = sorted(set(l["town"] for l in leads))
    cats = {}
    for l in leads:
        for c in l["hits"]: cats[c] = cats.get(c,0)+1
    head = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Council digest {generated}</title>
<style>body{{font-family:Segoe UI,-apple-system,Arial,sans-serif;margin:0;background:#f5f6f8;color:#1f2430}}
.wrap{{max-width:960px;margin:24px auto;padding:0 16px}}h1{{font-size:21px;margin:0 0 2px}}
.sub{{color:#6b7280;font-size:13px;margin-bottom:16px}}
.town{{font-size:16px;font-weight:700;margin:20px 0 8px;color:#1f3a5f;border-bottom:2px solid #e6e9ee;padding-bottom:4px}}
.lead{{background:#fff;border:1px solid #e6e9ee;border-radius:8px;padding:11px 15px;margin-bottom:10px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.lh{{font-size:13.5px;margin-bottom:6px}}.lh a{{color:#1a56c4;text-decoration:none;font-weight:600}}
.chip{{display:inline-block;font-size:11px;font-weight:700;color:#fff;padding:1px 7px;border-radius:10px;margin:0 4px 3px 0}}
.snip{{font-size:12.5px;color:#444;margin:3px 0;padding-left:9px;border-left:3px solid #dfe3e9}}
.hl{{background:#fff3ba;font-weight:600}}</style></head><body><div class="wrap">
<h1>Eastern Ontario councils &mdash; economic-signal digest</h1>
<div class="sub">{generated} &middot; {len(leads)} leads across {len(towns)} municipalities (scanned {ndocs} new documents, last {SCAN_DAYS} days) &middot; """ + \
    " ".join('<span class="chip" style="background:%s">%s %d</span>' % (CATCLR.get(c,"#555"), esc(c), n) for c,n in sorted(cats.items(), key=lambda x:-x[1])) + "</div>"
    body = []
    bytown = {}
    for l in leads: bytown.setdefault(l["town"], []).append(l)
    for town in towns:
        body.append('<div class="town">%s</div>' % esc(town))
        for l in sorted(bytown[town], key=lambda x:x["date"], reverse=True):
            chips = " ".join('<span class="chip" style="background:%s">%s</span>' % (CATCLR.get(c,"#555"), esc(c)) for c in l["hits"])
            snips = []
            for c, terms in l["hits"].items():
                for term, snip in list(terms.items())[:SNIPPETS_PER_DOC]:
                    hs = esc(snip)
                    for t in [term] + [term.title()]:
                        hs = re.sub("("+re.escape(esc(t))+")", r'<span class="hl">\1</span>', hs, flags=re.I, count=1)
                    snips.append('<div class="snip">%s</div>' % hs)
            body.append('<div class="lead"><div class="lh"><a href="%s" target="_blank">%s</a> &middot; %s &middot; %s</div>%s%s</div>' % (
                esc(l["href"]), esc(l["date"]), esc(l["type"]), esc(l["meeting"]), chips, "".join(snips[:SNIPPETS_PER_DOC])))
    return head + "".join(body) + "</div></body></html>"

def run():
    os.makedirs(OUT_DIR, exist_ok=True)
    seen = load(STATE_F, {})            # path -> mtime already scanned
    cutoff = (date.today() - timedelta(days=SCAN_DAYS)).isoformat()
    leads, scanned, skipped_big, newly = [], 0, 0, {}
    for dp, _dn, files in os.walk(ROOT):
        if os.path.basename(dp) not in SCAN_TYPES: continue
        for fn in files:
            if not fn.lower().endswith(".pdf"): continue
            path = os.path.join(dp, fn)
            meta = parse_meta(path)
            if not meta or meta["date"] < cutoff: continue
            mt = os.path.getmtime(path)
            if seen.get(path) == mt: continue                 # already scanned, unchanged
            newly[path] = mt
            if os.path.getsize(path) > MAX_PDF_MB*1024*1024: skipped_big += 1; continue
            try: text = extract_text(path)
            except Exception: continue
            scanned += 1
            hits = find_hits(text)
            if hits:
                meta["hits"] = hits
                meta["href"] = os.path.relpath(path, OUT_DIR).replace(os.sep, "/").replace(" ", "%20")
                leads.append(meta)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not newly:
        print(generated, "no new documents to scan"); return
    html_out = render(leads, generated, scanned)
    with open(os.path.join(OUT_DIR, "digest.html"), "w", encoding="utf-8") as f: f.write(html_out)
    with open(os.path.join(OUT_DIR, "digest-%s.html" % date.today().isoformat()), "w", encoding="utf-8") as f: f.write(html_out)
    with open(os.path.join(OUT_DIR, "leads.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["date","town","type","meeting","categories","terms","file"])
        for l in sorted(leads, key=lambda x:(x["town"], x["date"])):
            terms = "; ".join(t for terms in l["hits"].values() for t in terms)
            w.writerow([l["date"], l["town"], l["type"], l["meeting"], " | ".join(l["hits"].keys()), terms, l["file"]])
    seen.update(newly)
    with open(STATE_F, "w") as f: json.dump(seen, f)
    print("%s  scanned %d new docs, %d leads%s" % (generated, scanned, len(leads),
          (", %d big PDFs skipped" % skipped_big) if skipped_big else ""))
    cfg = email_cfg()
    if cfg and leads:
        try: send_email(cfg, "Council digest: %d economic-signal leads" % len(leads), html_out); print("  emailed digest")
        except Exception as e: print("  email error:", type(e).__name__, e)

if __name__ == "__main__":
    run()
