#!/usr/bin/env python3
import os
import sys
import time
import datetime
import json
import re
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

REPORT_DIR   = 'report'
VERSION_FILE = os.path.join(REPORT_DIR, 'version.txt')
BASE_NAME    = 'test_result_report'

auth = HTTPBasicAuth(CONFLUENCE_USER, CONFLUENCE_TOKEN)
headers = {
    "Content-Type": "application/json",
    "X-Atlassian-Token": "no-check"
}


# =============================================================
# Validation
# =============================================================
def validate_env():
    missing = []
    for key, val in {
        "CONFLUENCE_BASE": CONFLUENCE_BASE,
        "CONFLUENCE_USER": CONFLUENCE_USER,
        "CONFLUENCE_TOKEN": CONFLUENCE_TOKEN,
        "CONFLUENCE_SPACE": CONFLUENCE_SPACE
    }.items():
        if not val:
            missing.append(key)

    if missing:
        sys.exit(f"❌ Missing required environment variables: {', '.join(missing)}")

    if "/rest/api" in CONFLUENCE_BASE:
        sys.exit("❌ CONFLUENCE_BASE must NOT contain '/rest/api' — set Wiki base URL only")


# =============================================================
# Read version
# =============================================================
def read_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE) as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return 1
    return 1


# =============================================================
# ✅ Accurate JUnit Summary Extraction (Fix Applied)
# =============================================================
def extract_junit_summary():
    junit_file = os.path.join(REPORT_DIR, "junit.xml")

    if not os.path.exists(junit_file):
        print("⚠️ junit.xml missing → Defaulting summary to 0")
        return 0, 0, 0, 0

    tree = ET.parse(junit_file)
    root = tree.getroot()

    passed = failed = errors = skipped = 0

    for testcase in root.iter("testcase"):
        if testcase.find("failure") is not None:
            failed += 1
        elif testcase.find("error") is not None:
            errors += 1
        elif testcase.find("skipped") is not None:
            skipped += 1
        else:
            passed += 1

    return passed, failed, errors, skipped


# =============================================================
# Build final summary + PASS/FAIL status
# =============================================================
def build_summary():
    passed, failed, errors, skipped = extract_junit_summary()
    total = passed + failed + errors + skipped

    rate = (passed / total * 100) if total else 0.0
    status = "PASS" if failed == 0 and errors == 0 else "FAIL"

    emoji = "✅" if status == "PASS" else "❌"

    summary = (
        f"{emoji} {passed} passed, ❌ {failed} failed, "
        f"⚠️ {errors} errors, ⏭ {skipped} skipped — "
        f"Pass rate: {rate:.1f}%"
    )

    return summary, status


# =============================================================
# Create Confluence Page
# =============================================================
def create_confluence_page(title, html_body):
    url = f"{CONFLUENCE_BASE}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE},
        "body": {
            "storage": {
                "value": html_body,
                "representation": "storage"
            }
        }
    }

    print(f"🌐 Creating Confluence page: {title}")
    res = requests.post(url, headers=headers, json=payload, auth=auth)

    if not res.ok:
        print(f"❌ Failed to create page: HTTP {res.status_code}")
        try:
            print(json.dumps(res.json(), indent=2))
        except:
            print(res.text)
        res.raise_for_status()

    return res.json()["id"]


# =============================================================
# Upload Attachment
# =============================================================
def upload_attachment(page_id, file_path):
    if not os.path.exists(file_path):
        sys.exit(f"❌ Missing attachment: {file_path}")

    file_name = os.path.basename(file_path)
    mime_type = "text/html; charset=utf-8" if file_name.endswith(".html") else "application/pdf"

    url = f"{CONFLUENCE_BASE}/rest/api/content/{page_id}/child/attachment?allowDuplicated=true"
    print(f"📤 Uploading: {file_name}")
    time.sleep(2)

    with open(file_path, "rb") as f:
        files = {"file": (file_name, f, mime_type)}
        res = requests.post(url, files=files, headers={"X-Atlassian-Token": "no-check"}, auth=auth)

    if res.ok:
        print(f"📎 Uploaded: {file_name}")
    else:
        print(f"❌ Upload failed ({res.status_code})")
        print(res.text)
        res.raise_for_status()

    return file_name


# =============================================================
# Get Confluence Page Version
# =============================================================
def get_page_version(page_id):
    url = f"{CONFLUENCE_BASE}/rest/api/content/{page_id}?expand=version"
    res = requests.get(url, auth=auth)
    if not res.ok:
        res.raise_for_status()
    return res.json()["version"]["number"]


# =============================================================
# MAIN
# =============================================================
def main():
    validate_env()

    version = read_version()

    pdf_path  = os.path.join(REPORT_DIR, f"{BASE_NAME}_v{version}.pdf")
    html_path = os.path.join(REPORT_DIR, f"{BASE_NAME}_v{version}.html")

    if not os.path.exists(pdf_path) or not os.path.exists(html_path):
        sys.exit("❌ Missing report files — cannot publish to Confluence.")

    summary, status = build_summary()

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_timestamp = timestamp.replace(":", "-")

    emoji = "✅" if status == "PASS" else "❌"
    color = "green" if status == "PASS" else "red"

    page_title = f"{CONFLUENCE_TITLE} v{version} ({status}) - {safe_timestamp}"

    # Base HTML
    body = f"""
        <h2>{emoji} {CONFLUENCE_TITLE} (v{version})</h2>
        <p><b>Date:</b> {timestamp}</p>
        <p><b>Status:</b> <span style="color:{color}; font-weight:bold;">{status}</span></p>
        <p><b>Summary:</b> {summary}</p>
        <p>Details available in attached PDF/HTML files.</p>
    """

    # Create Page
    page_id = create_confluence_page(page_title, body)

    # Upload Attachments
    pdf_name  = upload_attachment(page_id, pdf_path)
    html_name = upload_attachment(page_id, html_path)

    pdf_link  = f"{CONFLUENCE_BASE}/download/attachments/{page_id}/{pdf_name}?api=v2"
    html_link = f"{CONFLUENCE_BASE}/download/attachments/{page_id}/{html_name}?api=v2"

    updated_body = body + f"""
        <h3>📎 Attachments</h3>
        <p><a href="{html_link}">{html_name}</a></p>
        <p><a href="{pdf_link}">{pdf_name}</a></p>
    """

    # Update page with attachments section
    current_version = get_page_version(page_id)
    update_url = f"{CONFLUENCE_BASE}/rest/api/content/{page_id}"

    update_payload = {
        "id": page_id,
        "type": "page",
        "title": page_title,
        "version": {"number": current_version + 1},
        "body": {"storage": {"value": updated_body, "representation": "storage"}}
    }

    print(f"📝 Updating page {page_id} to v{current_version + 1}...")
    res = requests.put(update_url, headers=headers, json=update_payload, auth=auth)
    if not res.ok:
        print(res.text)
        res.raise_for_status()

    # Final Confluence Page URL
    page_url = f"{CONFLUENCE_BASE}/spaces/{CONFLUENCE_SPACE}/pages/{page_id}"

    print(f"✅ Published v{version} ({status}) → {page_url}")
    print(f"🔗 PDF: {pdf_link}")
    print(f"🔗 HTML: {html_link}")

    # Save page URL for email script
    with open(os.path.join(REPORT_DIR, "confluence_url.txt"), "w") as f:
        f.write(page_url)

    print(f"💾 Saved Confluence URL → {page_url}")


# =============================================================
# Entry
# =============================================================
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
