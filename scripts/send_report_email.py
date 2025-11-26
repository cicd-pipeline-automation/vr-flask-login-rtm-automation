#!/usr/bin/env python3
import os
import smtplib
import re
import xml.etree.ElementTree as ET
from email.message import EmailMessage

# ==============================================================
# PATHS
# ==============================================================
REPORT_DIR        = "report"
VERSION_FILE      = os.path.join(REPORT_DIR, "version.txt")
JUNIT_FILE        = os.path.join(REPORT_DIR, "junit.xml")
CONF_LINK_FILE    = os.path.join(REPORT_DIR, "confluence_url.txt")
RTM_EXEC_KEY_FILE = "rtm_execution_key.txt"
JIRA_LINK_FILE    = "report/jira_url.txt"   # NEW fallback file

# ======================================================
# SMTP / Email Env
# ======================================================
SMTP_HOST  = os.getenv("SMTP_HOST")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "22"))     # 🔥 DEFAULT FIXED TO 22
SMTP_USER  = os.getenv("SMTP_USER")
SMTP_PASS  = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("REPORT_FROM")

def parse_list(raw):
    if not raw:
        return []
    return [x.strip() for x in re.split(r"[;,]", raw) if x.strip()]

TO  = parse_list(os.getenv("REPORT_TO", ""))
CC  = parse_list(os.getenv("REPORT_CC", ""))
BCC = parse_list(os.getenv("REPORT_BCC", ""))

# ======================================================
# HELPERS
# ======================================================
def read_version():
    try:
        if os.path.exists(VERSION_FILE):
            return int(open(VERSION_FILE).read().strip())
    except:
        pass
    return 1


def read_confluence_url():
    if os.path.exists(CONF_LINK_FILE):
        return open(CONF_LINK_FILE).read().strip()
    return ""


# ======================================================
# Jira URL Resolution (fallback-safe)
# ======================================================
def read_jira_url():
    # 1) Direct env override
    if os.getenv("JIRA_ISSUE_URL"):
        return os.getenv("JIRA_ISSUE_URL")

    # 2) RTM execution key
    jira_base = os.getenv("JIRA_URL", "").rstrip("/")
    if jira_base and os.path.exists(RTM_EXEC_KEY_FILE):
        key = open(RTM_EXEC_KEY_FILE).read().strip()
        if key:
            return f"{jira_base}/browse/{key}"

    # 3) File fallback (added)
    if os.path.exists(JIRA_LINK_FILE):
        return open(JIRA_LINK_FILE).read().strip()

    # 4) Nothing available
    return ""


# ======================================================
# Test Summary from junit.xml
# ======================================================
def extract_junit_summary():
    if not os.path.exists(JUNIT_FILE):
        return "UNKNOWN", "⚪ junit.xml not found.", 0, 0, 0, 0

    tree = ET.parse(JUNIT_FILE)
    root = tree.getroot()

    passed = failed = errors = skipped = 0

    for tc in root.iter("testcase"):
        if tc.find("failure") is not None:
            failed += 1
        elif tc.find("error") is not None:
            errors += 1
        elif tc.find("skipped") is not None:
            skipped += 1
        else:
            passed += 1

    total = passed + failed + errors + skipped
    rate  = (passed * 100.0 / total) if total else 0

    status = "PASS" if failed == 0 and errors == 0 else "FAIL"
    emoji  = "✅" if status == "PASS" else "❌"

    summary = (
        f"{emoji} {passed} passed, "
        f"❌ {failed} failed, "
        f"⚠️ {errors} errors, "
        f"⏭ {skipped} skipped — "
        f"Pass rate: {rate:.1f}%"
    )

    return status, summary, passed, failed, errors, skipped


# ======================================================
# SEND EMAIL  (Port=22 Safe Version)
# ======================================================
def send_email(pdf_path, version, status, summary, jira_url, conf_url):
    emoji = "✅" if status == "PASS" else "❌"
    color = "green" if status == "PASS" else "red"

    msg = EmailMessage()
    msg["Subject"] = f"{emoji} Test Result {status} (v{version})"
    msg["From"] = FROM_EMAIL
    msg["To"]   = ", ".join(TO)
    if CC:
        msg["Cc"] = ", ".join(CC)

    all_recipients = TO + CC + BCC

    jira_html = f'<a href="{jira_url}" target="_blank">Open Test Execution</a>' if jira_url else "No Jira URL available."
    conf_html = f'<a href="{conf_url}" target="_blank">View Report in Confluence</a>' if conf_url else "No Confluence URL available."

    # TEXT BODY
    msg.set_content(f"""
Test Status: {status}
Summary: {summary}

Jira Test Execution:
{jira_url or 'N/A'}

Confluence Report:
{conf_url or 'N/A'}

PDF report (v{version}) is attached.

Regards,
QA Automation System
""")

    # HTML BODY
    msg.add_alternative(f"""
<html>
  <body style="font-family: Arial, sans-serif;">
    <h2>{emoji} Test Result: <span style="color:{color};">{status}</span> (v{version})</h2>

    <p><b>Summary:</b> {summary}</p>

    <h3>🔗 Jira Test Execution</h3>
    <p>{jira_html}</p>

    <h3>📄 Confluence Report</h3>
    <p>{conf_html}</p>

    <p>The PDF report is attached.</p>

    <p>Regards,<br><b>QA Automation System</b></p>
  </body>
</html>
""", subtype="html")

    # Attach PDF
    if not os.path.exists(pdf_path):
        raise SystemExit(f"❌ PDF not found: {pdf_path}")

    with open(pdf_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=os.path.basename(pdf_path)
        )

    print(f"📤 Sending email via {SMTP_HOST}:{SMTP_PORT} ...")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:

        # 🔥 Port 22 → NO TLS, NO AUTH
        if SMTP_PORT not in (465, 587):
            print("ℹ Non-TLS SMTP port detected — skipping TLS & login.")
        else:
            try:
                s.starttls()
            except Exception as e:
                print(f"⚠ TLS unavailable: {e}")

            if SMTP_USER and SMTP_PASS:
                try:
                    s.login(SMTP_USER, SMTP_PASS)
                except Exception as e:
                    print(f"⚠ SMTP AUTH skipped: {e}")

        s.send_message(msg, to_addrs=all_recipients)

    print("✅ Email sent successfully.")


# ======================================================
# MAIN
# ======================================================
def main():
    version  = read_version()
    pdf_path = os.path.join(REPORT_DIR, f"test_result_report_v{version}.pdf")

    status, summary, *_ = extract_junit_summary()
    jira_url = read_jira_url()
    conf_url = read_confluence_url()

    send_email(pdf_path, version, status, summary, jira_url, conf_url)


if __name__ == "__main__":
    main()
