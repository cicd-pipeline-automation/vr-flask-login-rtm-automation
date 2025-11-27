#!/usr/bin/env python3
import os
import argparse
import requests
import json
import time


def parse_args():
    p = argparse.ArgumentParser(description="Upload test results to RTM")
    p.add_argument("--archive", required=True)
    p.add_argument("--rtm-base", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--job-url", required=True)

    # Folder ID (optional)
    p.add_argument("--folder-id", required=False)
    return p.parse_args()


def main():
    args = parse_args()

    token = os.getenv("RTM_API_TOKEN")
    if not token:
        raise SystemExit("❌ Missing RTM_API_TOKEN")

    url = f"{args.rtm_base}/api/v1/automation/import-test-results"   # 👈 Use v1 for your RTM
    headers = {"Authorization": f"Bearer {token}"}

    print("🚀 Uploading ZIP to RTM...")

    # ===========================================
    # FIX → RTM v1 requires testExecutionFields
    # ===========================================
    jira_fields = {
        "description": (
            "Automated Test Execution created by Jenkins pipeline.\n"
            f"Build URL: {args.job_url}"
        ),
        "customfield_10088": (
            "Automated Acceptance Criteria satisfied (CI/CD execution)."
        )
    }

    # Add Test Execution Folder (optional)
    if args.folder_id:
        jira_fields["customfield_10075"] = args.folder_id

    test_execution_fields_json = json.dumps(jira_fields)

    with open(args.archive, "rb") as f:
        files = {"file": f}

        data = {
            "projectKey": args.project,
            "reportType": "JUNIT",
            "jobUrl": args.job_url,
            "testExecutionFields": test_execution_fields_json   # 👈 KEY FIX
        }

        response = requests.post(url, headers=headers, files=files, data=data)

    # Server side check
    if response.status_code not in (200, 202):
        print("❌ RTM Upload Failed:", response.text)
        return

    task_id = response.text.strip()
    print(f"📌 RTM Task ID: {task_id}")

    # Poll import
    status_url = f"{args.rtm_base}/api/v1/automation/import-status/{task_id}"

    while True:
        resp = requests.get(status_url, headers=headers)
        data = resp.json()

        print(f"➡️ RTM Status: {data.get('status')} (Progress: {data.get('progress')})")

        if data.get("status") != "IMPORTING":
            break

        time.sleep(2)

    print("🎉 Import complete:", json.dumps(data, indent=2))

    test_exec = data.get("testExecutionKey")
    if not test_exec:
        print("⚠ Test Execution creation failed.")
        return

    # Save TE key
    with open("rtm_execution_key.txt", "w") as f:
        f.write(test_exec)

    print(f"📝 Saved Test Execution Key → {test_exec}")


if __name__ == "__main__":
    main()
