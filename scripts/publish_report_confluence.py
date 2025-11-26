#!/usr/bin/env python3
import os
import sys
import time
import datetime
import json
import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPBasicAuth

# =============================================================
# Environment Variables
# =============================================================
CONFLUENCE_BASE  = os.getenv('CONFLUENCE_BASE', '').rstrip('/')
CONFLUENCE_USER  = os.getenv('CONFLUENCE_USER')
CONFLUENCE_TOKEN = os.getenv('CONFLUENCE_TOKEN')
CONFLUENCE_SPACE = os.getenv('CONFLUENCE_SPACE')
CONFLUENCE_TITLE = os.getenv('CONFLUENCE_TITLE', 'Test Result Report')

REPORT_DIR   = "report"
VERSION_FILE = os.path.join(REPORT_DIR, "version.txt")
BASE_NAME    = "test_result_report"

auth = HTTPBasicAuth(CONFLUENCE_USER, CONFLUENCE_TOKEN)
headers = {"Content-Type": "application/json"}

# =============================================================
# Validate ENV
# =============================================================
def validate_env():
    missing = []
    for k, v in {
        "CONFLUENCE_BASE": CONFLUENCE_BASE,
        "CONFLUENCE_USER": CONFLUENCE_USER,
        "CONFLUENCE_TOKEN": CONFLUENCE_TOKEN,
        "CONFLUENCE_SPACE": CONFLUENCE_SPACE
    }.items():
        if not v:
            missing.append(k)

    if missing:
        sys.exit(f"❌ Missing environment variables: {', '.join(missing)}")

    if "/rest/api" in CONFLUENCE_BASE:
        sys.exit("❌ CONFLUENCE_BASE must be the base wiki URL (without /rest/api)")

# =============================================================
# Read version
# =============================================================
def read_version():
    try:
        return int(open(VERSION_FILE).read().strip())
    except:
        return 1

# =============================================================
# JUnit Summary (Improved)
# =============================================================
def extract_junit_summary():
    junit = os.path.join(REPORT_DIR, "junit.xml")
    if not os.path.exists(junit):
        return 0, 0, 0, 0

    root = ET.parse(junit).getroot()

    passed = failed = errors = skipped = 0

    for suite in root.iter("testsuite"):
        for case in suite.iter("testcase"):
            if case.find("failure") is not None:
                failed += 1
            elif case.find("error") is not None:
                errors += 1
            elif case.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1

    return passed, failed, errors, skipped

# =============================================================
# Build Summary
# =============================================================
def build_summary():
    passed, failed, errors, skipped = extract_junit_summary()
    total = passed + failed + errors + skipped
    rate = (passed / total * 100) if total else 0

    status = "PASS" if failed == 0 and errors == 0 else "FAIL"
    emoji = "✅" if status == "PASS" else "❌"

    summary = (
        f"{emoji} {passed} passed, ❌ {failed} failed, "
        f"⚠️ {errors} errors, ⏭ {skipped} skipped — "
        f"Pass rate: {rate:.1f}%"
    )

    # Save for email script
    with open(os.path.join(REPORT_DIR, "test_summary.txt"), "w") as f:
        f.write(summary)

    return summary, status

# =============================================================
# Create Confluence Page
# =============================================================
def create_page(title, html):
    url = f"{CONFLUENCE_BASE}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE},
        "body": {"storage": {"value": html, "representation": "storage"}}
    }

    r = requests.post(url, auth=auth, headers=headers, json=payload)
    if not r.ok:
        print(r.text)
        r.raise_for_status()

    return r.json()["id"]

# =============================================================
# Upload Attachment (with retry)
# =============================================================
def upload_attachment(page_id, file_path):
    if not os.path.exists(file_path):
        sys.exit(f"❌ Missing file: {file_path}")

    filename = os.path.basename(file_path)
    mime = "text/html" if filename.endswith(".html") else "application/pdf"
    url = f"{CONFLUENCE_BASE}/rest/api/content/{page_id}/child/attachment?allowDuplicated=true"

    for attempt in range(5):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, mime)}
                r = requests.post(url, auth=auth,
                                  files=files,
                                  headers={"X-Atlassian-Token": "no-check"})

            if r.ok:
                print(f"📎 Uploaded {filename}")
                return filename

            print(f"⚠ Retry ({attempt+1}) → Upload failed: {r.status_code}")
            time.sleep(2)

        except Exception as e:
            print(f"⚠ Error: {e}")

    sys.exit(f"❌ FAILED to upload {filename}")

# =============================================================
# MAIN
# =============================================================
def main():
    validate_env()

    version = read_version()
    pdf = os.path.join(REPORT_DIR, f"{BASE_NAME}_v{version}.pdf")
    html = os.path.join(REPORT_DIR, f"{BASE_NAME}_v{version}.html")

    if not (os.path.exists(pdf) and os.path.exists(html)):
        sys.exit("❌ Missing PDF/HTML reports")

    summary, status = build_summary()

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe = timestamp.replace(":", "-")
    emoji = "✅" if status == "PASS" else "❌"

    title = f"{CONFLUENCE_TITLE} v{version} ({status}) - {safe}"

    body = f"""
        <h2>{emoji} {CONFLUENCE_TITLE} (v{version})</h2>
        <p><b>Date:</b> {timestamp}</p>
        <p><b>Status:</b> <span>{status}</span></p>
        <p><b>Summary:</b><br>{summary}</p>
        <p>Reports attached below.</p>
    """

    page_id = create_page(title, body)

    pdf_name = upload_attachment(page_id, pdf)
    html_name = upload_attachment(page_id, html)

    pdf_link = f"{CONFLUENCE_BASE}/download/attachments/{page_id}/{pdf_name}?api=v2"
    html_link = f"{CONFLUENCE_BASE}/download/attachments/{page_id}/{html_name}?api=v2"

    final_html = body + f"""
        <h3>📎 Attachments</h3>
        <p><a href="{html_link}">{html_name}</a></p>
        <p><a href="{pdf_link}">{pdf_name}</a></p>
    """

    # Update page
    version_num = requests.get(
        f"{CONFLUENCE_BASE}/rest/api/content/{page_id}?expand=version",
        auth=auth
    ).json()["version"]["number"]

    update_payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": version_num + 1},
        "body": {"storage": {"value": final_html, "representation": "storage"}}
    }

    requests.put(
        f"{CONFLUENCE_BASE}/rest/api/content/{page_id}",
        auth=auth, headers=headers, json=update_payload
    )

    # Correct Cloud URL (fix)
    page_url = f"{CONFLUENCE_BASE}/wiki/spaces/{CONFLUENCE_SPACE}/pages/{page_id}"

    # Save URL for email script
    with open(os.path.join(REPORT_DIR, "confluence_url.txt"), "w") as f:
        f.write(page_url)

    print(f"✅ Published: {page_url}")

if __name__ == "__main__":
    main()
