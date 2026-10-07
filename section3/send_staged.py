print(">>> send_staged.py loaded")
import json, os, shutil, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime

GMAIL_USER = os.environ.get("GMAIL_USER", "elijahfessy01@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
STAGING_DIR = "archive/staging/section3"
EMAIL_HTML_PATH = os.path.join(STAGING_DIR, "email.html")
METADATA_PATH = os.path.join(STAGING_DIR, "metadata.json")
SENT_ROOT = "archive/sent"

def load_json(p):
    with open(p, "r", encoding="utf-8") as f: return json.load(f)
def load_html(p):
    with open(p, "r", encoding="utf-8") as f: return f.read()
def attach_chart(msg, c):
    if not os.path.exists(c["file"]): return False
    with open(c["file"], "rb") as f: img = MIMEImage(f.read(), _subtype="png")
    img.add_header("Content-ID", "<" + c["cid"] + ">")
    img.add_header("Content-Disposition", "inline", filename=os.path.basename(c["file"]))
    msg.attach(img)
    print(">>> attached: " + c["cid"])
    return True
def main():
    print(">>> main block entered")
    metadata = load_json(METADATA_PATH)
    html_body = load_html(EMAIL_HTML_PATH)
    subject = metadata.get("subject", "Liquidity Brief")
    recipients = metadata.get("recipients", [])
    charts = metadata.get("charts", [])
    print(">>> subject: " + subject)
    print(">>> recipients: " + str(recipients))
    print(">>> charts: " + str(len(charts)))
    msg = MIMEMultipart("related")
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg_alt = MIMEMultipart("alternative")
    msg.attach(msg_alt)
    msg_alt.attach(MIMEText(html_body, "html"))
    for c in charts:
        attach_chart(msg, c)
    print(">>> connecting smtp.gmail.com:465")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.sendmail(GMAIL_USER, recipients, msg.as_string())
        print(">>> sent to " + str(recipients))
    today = datetime.now().strftime("%Y-%m-%d")
    dest = os.path.join(SENT_ROOT, today + "-section3")
    os.makedirs(SENT_ROOT, exist_ok=True)
    if os.path.exists(dest): shutil.rmtree(dest)
    shutil.move(STAGING_DIR, dest)
    os.makedirs(STAGING_DIR, exist_ok=True)
    os.makedirs(os.path.join(STAGING_DIR, "charts"), exist_ok=True)
    print(">>> archived to " + dest)
    print(">>> DONE")

if __name__ == "__main__":
    main()
