#!/usr/bin/env python3
import os
import argparse
import requests
import json
import time

# =========================================================
# Parse CLI Arguments
# =========================================================
def parse_args():
    p = argparse.ArgumentParser(description="Upload JUnit test results to RTM Cloud")

    p.add_argument("--archive", required=True, help="test-results.zip")
    p.add_argument("--rtm-base", required=True, help="RTM Cloud Base URL")
    p.add_argument("--project", required=True, help="RTM Project Key (Example: CR0B)")
    p.add_argument("--job-url", required=True, help="Jenkins Build URL")
    p.add_argument("--description", required=True, help="Test Execution Description")
    p.add_argument("--acceptance", required=True, help="Acceptance Criteria")
    p.add_argument("--folder-id", required=False, help="RTM Folder ID")

    return p.parse_args()


# =========================================================
# Convert Text → Atlassian Document Format (ADF)
# =========================================================
def to_adf(text):
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}]
            }
        ]
    }


# =========================================================
# Main Function
# =========================================================
def main():
    args = parse_args()

    # RTM API Token from Jenkins Credentials
    token = os.getenv("RTM_API_TOKEN")
    if not token:
        raise SystemExit("❌ Missing RTM_API_TOKEN environment variable")

    headers = {"Authorization": f"Bearer {token}"}

    # ========== 1) RTM Import Endpoint ==========
    import_url = args.rtm_base.rstrip("/") + "/api/v2/automation/import-test-results"

    description_adf = to_adf(args.description)
    acceptance_adf  = to_adf(args.acceptance)

    jira_fields = {
        "description": description_adf,
        "customfield_10088": acceptance_adf     # Acceptance Criteria
    }

    # ❗ DO NOT include folder here — Jira screen validation blocks it.

    test_execution_fields = {"fields": jira_fields}
    test_execution_fields_str = json.dumps(test_execution_fields)

    # -------------------------------------------------------
    print("\n🚀 Uploading ZIP to RTM...")
    # -------------------------------------------------------

    with open(args.archive, "rb") as f:
        files = {"file": f}
        data = {
            "projectKey": args.project,
            "reportType": "JUNIT",
            "jobUrl": args.job_url,
            "testExecutionFields": test_execution_fields_str
        }

        response = requests.post(import_url, headers=headers, files=files, data=data)

    if response.status_code not in (200, 202):
        print("❌ RTM Upload Failed:")
        print(response.text)
        return

    task_id = response.text.strip()
    print(f"📌 RTM Task ID: {task_id}")

    # ========== 2) POLL RTM IMPORT STATUS ==========
    status_url = args.rtm_base.rstrip("/") + f"/api/v2/automation/import-status/{task_id}"

    while True:
        r = requests.get(status_url, headers=headers)
        d = r.json()
        print(f"➡️ Status: {d.get('status')} Progress: {d.get('progress')}")

        if d.get("status") != "IMPORTING":
            break

        time.sleep(2)

    print("\n🎉 Import result:")
    print(json.dumps(d, indent=2))

    te_key = d.get("testExecutionKey")
    if not te_key:
        print("❌ No testExecutionKey returned — Jira TE creation failed.")
        return

    print(f"📝 Test Execution Created: {te_key}")

    # Save TE key for next Jenkins stages
    with open("rtm_execution_key.txt", "w") as f:
        f.write(te_key)

    # =========================================================
    # 3) UPDATE RTM FOLDER (Correct Cloud Endpoint)
    # =========================================================
    if args.folder_id:
        patch_url = args.rtm_base.rstrip("/") + f"/api/v1/test-executions/{te_key}"
        payload = {"folderId": args.folder_id}

        print(f"\n📁 Updating Test Execution folder to {args.folder_id} ...")
        move_res = requests.patch(
            patch_url,
            headers={**headers, "Content-Type": "application/json"},
            json=payload
        )

        if move_res.status_code in (200, 204):
            print("✅ Folder update successful!")
        else:
            print("⚠️ Folder update failed:")
            print(move_res.status_code, move_res.text)

    print("\n✅ Completed successfully.")


# =========================================================
# Entry Point
# =========================================================
if __name__ == "__main__":
    main()
