"""
Sends a one-off plain-text email -- used for the "run started" ping, as a
lighter-weight sibling to send_summary_email.py which is specifically for
the end-of-run summary files. Same Gmail SMTP credentials/env vars.

Usage:
    python scripts/send_notification.py "<subject>" "<body>"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from send_summary_email import send_email  # noqa: E402


def main():
    if len(sys.argv) != 3:
        print("Usage: send_notification.py <subject> <body>", file=sys.stderr)
        sys.exit(1)

    subject, body = sys.argv[1], sys.argv[2]
    send_email(subject, body)
    print("Notification email sent.")


if __name__ == "__main__":
    main()
