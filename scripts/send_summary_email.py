"""
Emails the run-summary text file(s) a scraper run produced.

Reads Gmail SMTP credentials and the recipient from environment variables
(kept out of the repo -- in CI these come from GitHub Secrets):
    GMAIL_USER          the Gmail address to send from
    GMAIL_APP_PASSWORD  an app password for that account (not the real password)
    EMAIL_TO            recipient address (defaults to GMAIL_USER if unset)

Usage:
    python scripts/send_summary_email.py path/to/summary1.txt [path/to/summary2.txt ...]
"""

import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path


def build_email_body(summary_paths: list[Path]) -> str:
    parts = []
    for path in summary_paths:
        if not path.exists():
            parts.append(f"[missing summary file: {path}]")
            continue
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def send_email(subject: str, body: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    email_to = os.environ.get("EMAIL_TO", gmail_user)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = email_to

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, [email_to], msg.as_string())


def main():
    if len(sys.argv) < 2:
        print("Usage: send_summary_email.py <summary_file> [<summary_file> ...]", file=sys.stderr)
        sys.exit(1)

    summary_paths = [Path(p) for p in sys.argv[1:]]
    body = build_email_body(summary_paths)
    date_str = datetime.now(timezone.utc).strftime("%d-%m-%Y")
    subject = f"Zameen scraper run summary -- {date_str}"

    send_email(subject, body)
    print(f"Summary email sent to {os.environ.get('EMAIL_TO', os.environ.get('GMAIL_USER'))}")


if __name__ == "__main__":
    main()
