print(">>> send_staged.py loaded")

import json
import os
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime

print(">>> imports done")

GMAIL_USER = os.environ.get("GMAIL_USER", "elijahfessy01@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

STAGING_DIR = "archive/staging/section1"
EMAIL_HTML_PATH = os.path.join(STAGING_DIR, "email.html")
METADATA_PATH = os.path.join(STAGING_DIR, "metadata.json")
SENT_ROOT = "archive/sent"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def load_json(path):
    if not os.path.exists(path):
        print(">>> ERROR: " + path + " not found.")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_html(path):
    if not os.path.exists(path):
        print(">>> ERROR: " + path + " not found.")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def attach_chart(msg, chart_info):
    """Attach a PNG as inline CID image."""
    file_path = chart_info.get("file")
    cid = chart_info.get("cid")
    if not file_path or not cid:
        return False
    if not os.path.exists(file_path):
        print(">>> WARN: chart file not found: " + file_path)
        return False
    with open(file_path, "rb") as f:
        img = MIMEImage(f.read(), _subtype="png")
    img.add_header("Content-ID", "<" + cid + ">")
    img.add_header("Content-Disposition", "inline",
                   filename=os.path.basename(file_path))
    msg.attach(img)
    print(">>> attached chart: " + cid + " (" + os.path.basename(file_path) + ")")
    return True


def send_email(subject, recipients, html_body, charts):
    if not GMAIL_APP_PASSWORD:
        print(">>> ERROR: GMAIL_APP_PASSWORD not set.")
        return False

    msg = MIMEMultipart("related")
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    # Attach HTML body
    msg_alt = MIMEMultipart("alternative")
    msg.attach(msg_alt)
    msg_alt.attach(MIMEText(html_body, "html"))

    # Attach chart PNGs as CID-referenced images
    for chart in charts:
        attach_chart(msg, chart)

    print(">>> connecting to " + SMTP_HOST + ":" + str(SMTP_PORT))
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            print(">>> SSL connection started")
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            print(">>> login successful")
            server.sendmail(GMAIL_USER, recipients, msg.as_string())
            print(">>> email sent to: " + str(recipients))
        return True
    except Exception as e:
        print(">>> SMTP error: " + str(e))
        return False


def archive_sent():
    today = datetime.now().strftime("%Y-%m-%d")
    dest = os.path.join(SENT_ROOT, today + "-section1")
    os.makedirs(SENT_ROOT, exist_ok=True)

    if os.path.exists(dest):
        shutil.rmtree(dest)

    shutil.move(STAGING_DIR, dest)
    print(">>> archived sent files to " + dest)

    os.makedirs(STAGING_DIR, exist_ok=True)
    os.makedirs(os.path.join(STAGING_DIR, "charts"), exist_ok=True)
    print(">>> staging folder recreated")
    return dest


def main():
    print(">>> main block entered")

    metadata = load_json(METADATA_PATH)
    if not metadata:
        raise SystemExit(1)

    html_body = load_html(EMAIL_HTML_PATH)
    if not html_body:
        raise SystemExit(1)

    subject = metadata.get("subject", "Macro Brief")
    recipients = metadata.get("recipients", [])
    charts = metadata.get("charts", [])

    if not recipients:
        print(">>> ERROR: no recipients in metadata.")
        raise SystemExit(1)

    print(">>> subject: " + subject)
    print(">>> recipients: " + str(recipients))
    print(">>> charts to attach: " + str(len(charts)))

    sent = send_email(subject, recipients, html_body, charts)

    if sent:
        archive_sent()
        print(">>> DONE - email delivered and archived")
    else:
        print(">>> FAILED - email not sent, staging kept intact")


if __name__ == "__main__":
    main()
