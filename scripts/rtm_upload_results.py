#!/usr/bin/env python3
import os
import argparse
import requests
import json
import time

# =========================================================
# Parse Arguments
# =========================================================
def parse_args():
    p = argparse.ArgumentParser(description="Upload JUnit test results to RTM Cloud")
    p.add_argument("--archive", required=True, help="Path to test-results.zip")
    p.add_argument("--rtm-base", required=True, help="Base RTM Cloud URL")
    p.add_argument("--project", required=True, help="RTM Project Key e.g. CR0B")
    p.add_argument("--job-url", required=True, help="Jenkins Build URL")
    p.add_argument("--description", required=True, help="Description for Test Execution")
    p.add_argument("--acceptance", required=True, help="Acceptance Criteria text")
    p.add_argument("--folder-id", required=False, help="RTM Folder ID")
    return p.parse_args()


# =========================================================
# Convert text → Atlassian Document Format
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
# MAIN SCRIPT
# =========================================================
def main():
    args = parse_args()

    token = os.getenv("RTM_API_TOKEN")
    if not token:
        raise SystemExit("❌ Missing RTM_API_TOKEN env variable")

    headers = {"Authorization": f"Bearer {token}"}

    # ------------------ Build RTM Import URL ------------------
    import_url = args.rtm_base.rstrip("/") + "/api/v2/automation/import-test-results"

    # Convert to ADF (Jira Cloud compatible)
    description_adf = to_adf(args.description)
    acceptance_adf = to_adf(args.acceptance)

    jira_fields = {
        "description": description_adf,
        "customfield_10088": acceptance_adf  # Acceptance Criteria
    }

    # NOTE: Do NOT send customfield_10075 (Folder) here!
    # Jira validation blocks it. We move TE later using RTM API.

    test_execution_fields = {"fields": jira_fields}
    test_execution_fields_str = json.dumps(test_execution_fields)

    print("\n🚀 Uploading ZIP to RTM...")

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

    # ------------------ Poll Import Status ------------------
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
        print("❌ No testExecutionKey returned — Jira creation failed")
        return

    print(f"📝 Test Execution Created: {te_key}")

    # Save TE key for next stages
    with open("rtm_execution_key.txt", "w") as f:
        f.write(te_key)

    # =========================================================
    # OPTION 2 — MOVE TEST EXECUTION TO FOLDER (AFTER CREATION)
    # =========================================================
    if args.folder_id:
        move_url = args.rtm_base.rstrip("/") + f"/api/v2/test-execution/{te_key}/move"
        payload = {"folderId": args.folder_id}

        print(f"\n📁 Moving Test Execution to folder {args.folder_id} ...")
        move_res = requests.post(move_url, headers=headers, json=payload)

        if move_res.status_code == 200:
            print("✅ Folder move successful!")
        else:
            print("⚠️ Folder move failed:")
            print(move_res.text)

    print("\n✅ Completed successfully.")


# =========================================================
# ENTRY POINT
# =========================================================
if __name__ == "__main__":
    main()
