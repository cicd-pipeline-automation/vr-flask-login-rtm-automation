#!/usr/bin/env python3
import os
import argparse
import requests


def attach_file(jira_base, jira_user, jira_token, issue_key, file_path):
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False

    print(f"📎 Uploading attachment → {os.path.basename(file_path)}")

    url = f"{jira_base}/rest/api/3/issue/{issue_key}/attachments"
    headers = {"X-Atlassian-Token": "no-check"}

    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        r = requests.post(url, headers=headers, auth=(jira_user, jira_token), files=files)

    if r.status_code in (200, 201):
        print(f"✅ Uploaded: {os.path.basename(file_path)}")
        return True

    print(f"❌ Upload failed ({r.status_code}) → {r.text}")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--html", required=True)
    args = parser.parse_args()

    jira_base = os.getenv("JIRA_URL")
    jira_user = os.getenv("JIRA_USER")
    jira_token = os.getenv("JIRA_API_TOKEN")

    if not (jira_base and jira_user and jira_token):
        raise SystemExit("❌ Missing Jira environment variables")

    # Load RTM Execution Key from file
    if not os.path.exists("rtm_execution_key.txt"):
        raise SystemExit("❌ Missing rtm_execution_key.txt — RTM upload step failed")

    with open("rtm_execution_key.txt", "r") as f:
        issue_key = f.read().strip()

    print(f"🚀 Attaching reports to: {issue_key}")

    attach_file(jira_base, jira_user, jira_token, issue_key, args.pdf)
    attach_file(jira_base, jira_user, jira_token, issue_key, args.html)


if __name__ == "__main__":
    main()
