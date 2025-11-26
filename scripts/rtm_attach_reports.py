#!/usr/bin/env python3
import os
import argparse
import requests
from requests.auth import HTTPBasicAuth
import time

# =========================================================
# Environment Variables
# =========================================================
JIRA_URL       = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_USER      = os.getenv("JIRA_USER")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not JIRA_URL:
    raise SystemExit("❌ Missing JIRA_URL environment variable.")
if not JIRA_USER:
    raise SystemExit("❌ Missing JIRA_USER environment variable.")
if not JIRA_API_TOKEN:
    raise SystemExit("❌ Missing JIRA_API_TOKEN environment variable.")

auth = HTTPBasicAuth(JIRA_USER, JIRA_API_TOKEN)

# =========================================================
# Arguments
# =========================================================
parser = argparse.ArgumentParser(description="Attach PDF/HTML reports to Jira Test Execution")

parser.add_argument("--issue-key", required=True, help="RTM Test Execution Key such as RT-105")
parser.add_argument("--pdf", required=True, help="Path to PDF report")
parser.add_argument("--html", required=True, help="Path to HTML report")

args = parser.parse_args()

issue_key = args.issue_key
pdf_path  = args.pdf
html_path = args.html

# =========================================================
# Helper: Determine correct MIME type
# =========================================================
def detect_mime(file_path):
    if file_path.endswith(".pdf"):
        return "application/pdf"
    if file_path.endswith(".html") or file_path.endswith(".htm"):
        return "text/html"
    return "application/octet-stream"

# =========================================================
# Upload with retry logic
# =========================================================
def attach_file(issue_key, file_path):
    if not os.path.exists(file_path):
        raise SystemExit(f"❌ File not found: {file_path}")

    filename = os.path.basename(file_path)
    mime_type = detect_mime(file_path)

    url = f"{JIRA_URL}/rest/api/2/issue/{issue_key}/attachments"

    headers = {"X-Atlassian-Token": "no-check"}

    print(f"\n📎 Uploading '{filename}' → {issue_key} ({mime_type})")
    print(f"🔗 {url}")

    for attempt in range(1, 4):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, mime_type)}
                res = requests.post(url, auth=auth, headers=headers, files=files)

            if res.status_code in (200, 201):
                print(f"✅ Attached successfully: {filename}")
                return

            print(f"⚠️ Attempt {attempt} failed: HTTP {res.status_code}")
            print(res.text)

        except Exception as e:
            print(f"⚠️ Upload exception (attempt {attempt}): {e}")

        time.sleep(2)

    raise SystemExit(f"❌ Failed to upload {filename} after 3 attempts.")

# =========================================================
# MAIN FLOW
# =========================================================
print(f"🔗 Jira Issue: {issue_key}")

# Save the current execution key for email script usage
with open("rtm_execution_key.txt", "w") as f:
    f.write(issue_key)

attach_file(issue_key, pdf_path)
attach_file(issue_key, html_path)

print("\n🎉 All attachments uploaded successfully.")
