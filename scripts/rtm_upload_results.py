#!/usr/bin/env python3
import os
import argparse
import requests
import json
import time


def parse_args():
    p = argparse.ArgumentParser(description="Upload test results to RTM")
    p.add_argument("--archive", required=True, help="ZIP file with test results")
    p.add_argument("--rtm-base", required=True, help="RTM base URL, e.g. https://rtm.example.com")
    p.add_argument("--project", required=True, help="RTM Project Key")
    p.add_argument("--job-url", required=True, help="Jenkins BUILD_URL (must start with http/https)")
    return p.parse_args()


def main():
    args = parse_args()

    token = os.getenv("RTM_API_TOKEN")
    if not token:
        raise SystemExit("❌ Missing RTM_API_TOKEN environment variable")

    if not args.job_url.startswith(("http://", "https://")):
        raise SystemExit("❌ job-url must start with http:// or https://")

    url = f"{args.rtm_base}/api/v2/automation/import-test-results"
    headers = {"Authorization": f"Bearer {token}"}

    print("🚀 Uploading ZIP to RTM...")

    with open(args.archive, "rb") as f:
        files = {"file": f}
        data = {
            "projectKey": args.project,
            "reportType": "JUNIT",
            "jobUrl": args.job_url
        }
        response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code not in (200, 202):
        print("❌ RTM Upload Failed")
        print("Status:", response.status_code)
        print("Response:", response.text)
        return

    task_id = response.text.strip()
    print(f"📌 RTM Task ID: {task_id}")

    # Polling import status
    status_url = f"{args.rtm_base}/api/v2/automation/import-status/{task_id}"

    while True:
        resp = requests.get(status_url, headers=headers)
        data = resp.json()
        print(f"➡️  RTM Status: {data.get('status')} (Progress: {data.get('progress')}%)")

        if data.get("status") != "IMPORTING":
            break
        time.sleep(2)

    print("🎉 Import complete:", json.dumps(data, indent=2))

    # Save test execution key
    test_exec = data.get("testExecutionKey")
    if not test_exec:
        print("⚠ No testExecutionKey returned, cannot write file.")
        return

    with open("rtm_execution_key.txt", "w") as f:
        f.write(test_exec)

    print(f"📝 RTM execution key saved -> rtm_execution_key.txt ({test_exec})")


if __name__ == "__main__":
    main()
