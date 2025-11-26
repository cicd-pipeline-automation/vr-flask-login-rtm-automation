#!/usr/bin/env python3
import os
import smtplib
from email.message import EmailMessage
import re

# ==============================================================
# Environment Variables
# ==============================================================
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '25'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')

TO_RAW  = os.getenv('REPORT_TO', '')
CC_RAW  = os.getenv('REPORT_CC', '')
BCC_RAW = os.getenv('REPORT_BCC', '')
FROM_EMAIL = os.getenv('REPORT_FROM')

CONFLUENCE_PAGE_URL_ENV = os.getenv("CONFLUENCE_PAGE_URL", "")
JIRA_EXECUTION_URL_ENV  = os.getenv("JIRA_EXECUTION_URL", "")

CONF_LINK_FILE = "report/confluence_url.txt"
JIRA_LINK_FILE = "report/jira_url.txt"
RTM_KEY_FILE   = "rtm_execution_key.txt"     # <–– auto RTM test execution key

REPORT_DIR   = "report"
VERSION_FILE = os.path.join(REPORT_DIR, "version.txt")
BASE_NAME    = "test_result_report"
PYTEST_LOG   = os.path.join(REPORT_DIR, "pytest_output.txt")


# ==============================================================
# Parse recipient lists
# ==============================================================
def parse_recipients(raw):
    if not raw:
        return []
    parts = re.split(r"[;,]", raw)
    return [p.strip() for p in parts if p.strip()]


# ==============================================================
# Read Confluence URL
# ==============================================================
def read_confluence_url():
    if CONFLUENCE_PAGE_URL_ENV:
        return CONFLUENCE_PAGE_URL_ENV

    if os.path.exists(CONF_LINK_FILE):
        with open(CONF_LINK_FILE, "r") as f:
            return f.read().strip()

    return ""


# ==============================================================
# NEW – Read Jira Execution Key (RT-XX) → auto build Jira URL
# ==============================================================
def read_jira_execution_from_rtm():
    jira_base = os.getenv("JIRA_URL", "").rstrip("/")
    if not jira_base:
        return ""

    if os.path.exists(RTM_KEY_FILE):
        with open(RTM_KEY_FILE, "r") as f:
            rtm_key = f.read().strip()
            if rtm_key:
                return f"{jira_base}/browse/{rtm_key}"

    return ""


# ==============================================================
# Jira URL fallback chain
# ==============================================================
def read_jira_url_fallback():
    # Direct env variable
    if JIRA_EXECUTION_URL_ENV:
        return JIRA_EXECUTION_URL_ENV

    # File fallback
    if os.path.exists(JIRA_LINK_FILE):
        with open(JIRA_LINK_FILE, "r") as f:
            return f.read().strip()

    # Ultimate fallback (your old hardcoded value)
    return ""


# ==============================================================
# Read version
# ==============================================================
def read_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE) as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return 1
    return 1


# ==============================================================
# Extract pytest summary   (unchanged — as per your request)
# ==============================================================
def extract_test_status():
    if not os.path.exists(PYTEST_LOG):
        return "UNKNOWN", "⚪ No pytest_output.txt found."

    with open(PYTEST_LOG, encoding="utf-8", errors="ignore") as f:
        text = f.read()

    passed = failed = errors = skipped = 0
    if m := re.search(r"(\d+)\s+passed", text, re.I):  passed = int(m.group(1))
    if m := re.search(r"(\d+)\s+failed", text, re.I):  failed = int(m.group(1))
    if m := re.search(r"(\d+)\s+errors?", text, re.I): errors = int(m.group(1))
    if m := re.search(r"(\d+)\s+skipped", text, re.I): skipped = int(m.group(1))

    total = passed + failed + errors + skipped
    rate  = (passed / total * 100) if total else 0.0

    status = "PASS" if failed == 0 and errors == 0 else "FAIL"
    emoji  = "✅" if status == "PASS" else "❌"

    summary = (
        f"SUMMARY: {emoji}<br>"
        f"✅ {passed} passed, "
        f"❌ {failed} failed, "
        f"⚠️ {errors} errors, "
        f"⏭ {skipped} skipped — "
        f"Pass rate: {rate:.1f}%"
    )

    return status, summary


# ==============================================================
# Send email (ENHANCED WITH SMTP + JIRA LOGIC)
# ==============================================================
def send_single_email_all(to_list, cc_list, bcc_list,
                          pdf_report_path, version, status, summary,
                          confluence_url, jira_url):

    emoji = "✅" if status == "PASS" else "❌"
    color = "green" if status == "PASS" else "red"

    msg = EmailMessage()
    msg["Subject"] = f"{emoji} Test Result {status} (v{version})"
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(to_list)

    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    all_recipients = to_list + cc_list + bcc_list

    # TEXT email
    msg.set_content(f"""
Test Status: {status}
Summary: {summary}

Confluence Report:
{confluence_url or 'N/A'}

Jira Test Execution:
{jira_url or 'N/A'}

PDF test report (v{version}) is attached.

Regards,
QA Automation System
""")

    # HTML email
    msg.add_alternative(f"""
<html>
<body style="font-family:Arial,sans-serif;">
    <h2>{emoji} Test Result:
        <span style="color:{color}">{status}</span> (v{version})
    </h2>

    <p><b>Summary:</b> {summary}</p>

    <h3>📄 Confluence Report</h3>
    <p>
        {'<a href="' + confluence_url + '" target="_blank">Open in Confluence</a>'
         if confluence_url else 'No Confluence URL available.'}
    </p>

    <h3>📌 Jira Test Execution</h3>
    <p>
        {'<a href="' + jira_url + '" target="_blank">Open Jira Test Execution</a>'
         if jira_url else 'No Jira URL available.'}
    </p>

    <p>The PDF report is attached.</p>

    <p>Regards,<br><b>QA Automation System</b></p>
</body>
</html>
""", subtype="html")

    # Attach PDF
    with open(pdf_report_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=os.path.basename(pdf_report_path)
        )

    print("📤 Sending email...")

    # ------- ⭐ ENHANCED SMTP HANDLING (From send_report_email (1).py) -------
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.ehlo()

        # TLS only if needed
        if SMTP_PORT == 587:
            try:
                s.starttls()
                s.ehlo()
            except Exception as e:
                print(f"⚠️ TLS not supported: {e}")

        # AUTH only when server supports it
        if SMTP_USER and SMTP_PASS:
            try:
                if "auth" in s.esmtp_features:
                    print("🔐 SMTP AUTH supported — logging in")
                    s.login(SMTP_USER, SMTP_PASS)
                else:
                    print("⚠️ SMTP AUTH not supported — skipping login.")
            except Exception as e:
                print(f"⚠️ AUTH error — continuing without login: {e}")

        # Send email
        s.send_message(msg, to_addrs=all_recipients)

    print("✅ Email sent successfully!\n")


# ==============================================================
# Main
# ==============================================================
def main():
    version = read_version()
    pdf_report_path = os.path.join(REPORT_DIR, f"{BASE_NAME}_v{version}.pdf")

    if not os.path.exists(pdf_report_path):
        raise SystemExit(f"❌ PDF not found: {pdf_report_path}")

    status, summary = extract_test_status()
    confluence_url = read_confluence_url()

    jira_url = (
        read_jira_execution_from_rtm()
        or JIRA_EXECUTION_URL_ENV
        or read_jira_url_fallback()
    )

    to_list  = parse_recipients(TO_RAW)
    cc_list  = parse_recipients(CC_RAW)
    bcc_list = parse_recipients(BCC_RAW)

    if not to_list:
        raise SystemExit("❌ REPORT_TO is empty — no email recipients.")

    send_single_email_all(
        to_list, cc_list, bcc_list,
        pdf_report_path, version, status, summary,
        confluence_url, jira_url
    )


# ==============================================================
# Entry
# ==============================================================
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Email failed: {e}")
        raise
