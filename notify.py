#!/usr/bin/env python3
"""
Send a short alert email using email_config.json - the SAME config file the scraper
(council_meetings.py) and digest (digest.py) already use. run_meetings.sh / run_digest.sh
call this to ping you if a scheduled run fails.

Usage:   echo "body text" | python3 notify.py "Subject line"

It is a silent no-op if email_config.json is missing or incomplete, so it can never
mask the real error that triggered it. email_config.json holds a password and is
git-ignored - it stays local on the Forge and is never synced to SharePoint.
"""
import os, sys, json, smtplib
from email.mime.text import MIMEText

HERE = os.path.dirname(os.path.abspath(__file__))
CFG  = os.path.join(HERE, "email_config.json")
KEYS = ("smtp_host", "smtp_port", "username", "password", "to_addr")


def main():
    subject = sys.argv[1] if len(sys.argv) > 1 else "Alert"
    body = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    try:
        cfg = json.load(open(CFG))
    except Exception:
        print("notify: no email_config.json - skipping alert"); return
    if not all(cfg.get(k) for k in KEYS):
        print("notify: email_config.json incomplete - skipping alert"); return

    msg = MIMEText(body or subject)
    msg["Subject"] = subject
    msg["From"] = cfg.get("from_addr") or cfg["username"]
    msg["To"] = cfg["to_addr"]
    try:
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30) as s:
            s.starttls()
            s.login(cfg["username"], cfg["password"])
            s.sendmail(msg["From"], [a.strip() for a in str(cfg["to_addr"]).split(",")], msg.as_string())
        print("notify: alert sent to", cfg["to_addr"])
    except Exception as e:
        print("notify: send failed:", type(e).__name__, e)


if __name__ == "__main__":
    main()
