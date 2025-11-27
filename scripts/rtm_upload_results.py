#!/usr/bin/env python3
import os, argparse, requests, json, time

def parse_args():
    p = argparse.ArgumentParser(description="Upload test results to RTM Cloud")
    p.add_argument("--archive", required=True)
    p.add_argument("--rtm-base", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--job-url", required=True)
    p.add_argument("--folder-id", required=False)
    return p.parse_args()

def to_adf(text):
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": text}
                ]
            }
        ]
    }

def main():
    args = parse_args()

    token = os.getenv("RTM_API_TOKEN")
    if not token:
        raise SystemExit("❌ Missing RTM_API_TOKEN")

    url = args.rtm_base.rstrip("/") + "/api/v2/automation/import-test-results"
    headers = {"Authorization": f"Bearer {token}"}

    # ===== ADF Fix for Jira Cloud =====
    description_adf = to_adf(
        f"Automated Test Execution triggered by Jenkins pipeline.\nBuild URL: {args.job_url}"
    )
    acceptance_adf = to_adf(
        "Automated Acceptance Criteria satisfied (CI/CD execution)."
    )

    jira_fields = {
        "description": description_adf,
        "customfield_10088": acceptance_adf
    }

    if args.folder_id:
        jira_fields["customfield_10075"] = args.folder_id

    test_execution_fields = {"fields": jira_fields}
    test_execution_fields_str = json.dumps(test_execution_fields)

    print("🚀 Uploading ZIP to RTM...")

    with open(args.archive, "rb") as f:
        files = {"file": f}
        data = {
            "projectKey": args.project,
            "reportType": "JUNIT",
            "jobUrl": args.job_url,
            "testExecutionFields": test_execution_fields_str
        }
        response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code not in (200, 202):
        print("❌ RTM Upload Failed:", response.text)
        return

    task_id = response.text.strip()
    print("📌 RTM Task ID:", task_id)

    status_url = args.rtm_base.rstrip("/") + f"/api/v2/automation/import-status/{task_id}"

    while True:
        r = requests.get(status_url, headers=headers)
        d = r.json()
        print("➡️ Status:", d.get("status"), "Progress:", d.get("progress"))

        if d.get("status") != "IMPORTING":
            break

        time.sleep(2)

    print("🎉 Import result:", json.dumps(d, indent=2))

    te_key = d.get("testExecutionKey")
    if not te_key:
        print("❌ No testExecutionKey returned — Test Execution creation failed")
        return

    with open("rtm_execution_key.txt", "w") as f:
        f.write(te_key)

    print("📝 Saved Test Execution Key:", te_key)


if __name__ == "__main__":
    main()
