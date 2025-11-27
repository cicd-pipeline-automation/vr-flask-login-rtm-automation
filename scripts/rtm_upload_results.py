#!/usr/bin/env python3
import os, argparse, requests, json, time

def parse_args():
    p = argparse.ArgumentParser(description="Upload test results to RTM Cloud")
    p.add_argument("--archive", required=True)
    p.add_argument("--rtm-base", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--job-url", required=True)
    p.add_argument("--folder-id", required=False,
                   help="RTM Test Execution Folder ID (optional)")
    return p.parse_args()

def main():
    args = parse_args()
    token = os.getenv("RTM_API_TOKEN")
    if not token:
        raise SystemExit("Missing RTM_API_TOKEN env var")

    url = args.rtm_base.rstrip("/") + "/api/v2/automation/import-test-results"
    headers = {"Authorization": f"Bearer {token}"}

    # Create testExecutionFields payload
    jira_fields = {
        "description": f"Automated Test Execution from Jenkins build: {args.job_url}",
        "customfield_10088": "Automated Acceptance Criteria satisfied via CI/CD"
    }
    if args.folder_id:
        jira_fields["customfield_10075"] = args.folder_id

    test_exec_fields = {"fields": jira_fields}
    test_exec_fields_str = json.dumps(test_exec_fields)

    with open(args.archive, "rb") as f:
        files = {"file": f}
        data = {
            "projectKey": args.project,
            "reportType": "JUNIT",
            "jobUrl": args.job_url,
            "testExecutionFields": test_exec_fields_str
        }
        resp = requests.post(url, headers=headers, files=files, data=data)

    if resp.status_code not in (200, 202):
        print("RTM Upload Failed:", resp.status_code, resp.text)
        return

    task_id = resp.text.strip()
    print("RTM Task ID:", task_id)

    status_url = args.rtm_base.rstrip("/") + f"/api/v2/automation/import-status/{task_id}"
    while True:
        r = requests.get(status_url, headers=headers)
        d = r.json()
        print("Status:", d.get("status"), "Progress:", d.get("progress"))
        if d.get("status") != "IMPORTING":
            break
        time.sleep(2)

    print("Import result:", json.dumps(d, indent=2))
    te_key = d.get("testExecutionKey")
    if not te_key:
        print("ERROR: No testExecutionKey returned — Test Execution creation failed")
        return

    with open("rtm_execution_key.txt", "w") as out:
        out.write(te_key)
    print("Saved Test Execution Key:", te_key)

if __name__ == "__main__":
    main()
