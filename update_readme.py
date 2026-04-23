#!/usr/bin/env python3
"""Fetch analytics and update README with recent visits table."""

import json
import os
import base64
import requests
from datetime import datetime, timedelta

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "Retsumdk/Retsumdk"
API_BASE = "https://api.github.com"
ZO_API = "https://thebookmaster.zo.space/api"

# Fetch profile data from our API
def fetch_analytics():
    try:
        resp = requests.get(f"{ZO_API}/profile-views", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

# Get current README
def get_readme():
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    resp = requests.get(f"{API_BASE}/repos/{REPO}/contents/README.md", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]
    return None, None

# Update README with visits table
def update_readme(content, sha, visits):
    # Find markers
    VISITS_START = "<!-- RECENT_VISITS_START -->"
    VISITS_END = "<!-- RECENT_VISITS_END -->"
    
    # Build table
    table = f"\n<details>\n<summary>📊 Recent Visits ({len(visits)} total)</summary>\n\n"
    table += "| Time | Location | Device | Browser | Source | Duration |\n"
    table += "|------|----------|--------|---------|--------|----------|\n"
    
    for v in visits:
        ts = v.get("timestamp", "")
        if ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            time_str = dt.strftime("%b %d %H:%M")
        else:
            time_str = "Unknown"
        loc = f"{v.get('country', '??')} {v.get('city', '')}"
        device = v.get("device", "Unknown")
        browser = v.get("browser", "Unknown")
        source = v.get("source", "direct")
        duration = v.get("duration", "-")
        table += f"| {time_str} | {loc} | {device} | {browser} | {source} | {duration} |\n"
    
    table += "\n*Updated automatically via GitHub Actions*</details>\n"
    
    # Replace or insert
    if VISITS_START in content and VISITS_END in content:
        import re
        pattern = re.compile(f"{re.escape(VISITS_START)}.*?{re.escape(VISITS_END)}", re.DOTALL)
        content = pattern.sub(table, content)
    else:
        # Insert before the cards section or at end
        content += f"\n{VISITS_START}\n{table}\n{VISITS_END}\n"
    
    return content

def main():
    analytics = fetch_analytics()
    if not analytics:
        print("Failed to fetch analytics")
        return 1
    
    content, sha = get_readme()
    if not sha:
        print("Failed to get README")
        return 1
    
    # Get recent visits
    detailed = analytics.get("detailed", [])
    visits = sorted(detailed, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
    
    new_content = update_readme(content, sha, visits)
    
    # Commit
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = {"message": "📊 Auto-update recent visits table", "content": base64.b64encode(new_content.encode()).decode(), "sha": sha}
    resp = requests.put(f"{API_BASE}/repos/{REPO}/contents/README.md", headers=headers, json=data)
    
    if resp.status_code == 200:
        print(f"✅ Updated README with {len(visits)} visits")
        return 0
    else:
        print(f"❌ Failed: {resp.status_code} {resp.text}")
        return 1

if __name__ == "__main__":
    exit(main())
