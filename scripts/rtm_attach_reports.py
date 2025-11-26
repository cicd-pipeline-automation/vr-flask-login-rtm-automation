#!/usr/bin/env python3
import os
import argparse
import requests
from requests.auth import HTTPBasicAuth

# =========================================================
# Environment Variables
# =========================================================
JIRA_URL       = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_USER      = os.getenv("JIRA_USER")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not JIRA_URL or not JIRA_USER or not JIRA_API_TOKEN:
    raise SystemExit("❌ Missing required Jira environment variables.")

auth = HTTPBasicAuth(JIRA_USER, JIRA_API_TOKEN)

# =========================================================
# Arguments
# =========================================================
parser = argparse.ArgumentParser()
parser.add_argument("--issueKey", required=True, help="RTM Test Execution Key such as RT-98")
parser.add_argument("--pdf", required=True, help="Path to PDF Report")
parser.add_argument("--html", required=True, help="Path to HTML Report")
args = parser.parse_args()

issue_key = args.issueKey
pdf_path  = args.pdf
html_path = args.html

# =========================================================
# Attach file helper
# =========================================================
def attach_file(issue_key, file_path):
    if not os.path.exists(file_path):
        raise SystemExit(f"❌ File not found: {file_path}")

    url = f"{JIRA_URL}/rest/api/2/issue/{issue_key}/attachments"
    filename = os.path.basename(file_path)

    print(f"📎 Attaching '{filename}' → Jira issue {issue_key}")

    with open(file_path, "rb") as f:
        files = {
            "file": (filename, f, "application/octet-stream")
        }

        headers = {"X-Atlassian-Token": "no-check"}

        res = requests.post(url, auth=auth, headers=headers, files=files)

        if res.status_code not in (200, 201):
            print(f"❌ Failed to attach {filename}: HTTP {res.status_code}")
            print(res.text)
            res.raise_for_status()

    print(f"✅ Attached: {filename}")

# =========================================================
# MAIN FLOW
# =========================================================
print(f"🔗 Jira Issue: {issue_key}")

# Save issue key for send_report_email.py
with open("rtm_execution_key.txt", "w") as f:
    f.write(issue_key)

attach_file(issue_key, pdf_path)
attach_file(issue_key, html_path)

print("🎉 All attachments uploaded successfully.")
