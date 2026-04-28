#!/usr/bin/env python3
"""Fetch analytics and update README with recent visits table + IP addresses."""

import json
import os
import base64
import requests
from datetime import datetime, timedelta

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "Retsumdk/Retsumdk"
API_BASE = "https://api.github.com"
ZO_API = "https://thebookmaster.zo.space/api"

# Fetch profile data from our pixel API
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
def update_readme(content, sha, visitors):
    # Build table — include IP column
    count = len(visitors)
    table = f"\n<details>\n<summary>📊 Recent Visits ({count} total · live)</summary>\n\n"
    table += "| Time | Location | Device | Browser | Source | IP | Duration |\n"
    table += "|------|----------|--------|---------|--------|---|----------|\n"
    
    for v in visitors:
        ts = v.get("time", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = ts[:10]
        else:
            time_str = "Unknown"
        
        country = v.get("country", "??")
        flag = {"US": "🇺🇸", "GB": "🇬🇧", "CA": "🇨🇦", "DE": "🇩🇪", "FR": "🇫🇷", "IN": "🇮🇳", "CN": "🇨🇳", "JP": "🇯🇵", "AU": "🇦🇺", "BR": "🇧🇷"}.get(country, f"{country}")
        loc = f"{flag} {country}"
        device = v.get("device", "Unknown")
        device_icon = "🖥️" if device == "desktop" else "📱"
        browser = v.get("browser", "Unknown")
        source = v.get("referrer", "direct")
        if not source or source == "direct":
            source = "direct"
        elif "github" in source.lower():
            source = "GitHub"
        elif "google" in source.lower():
            source = "Google"
        ip = v.get("ip", "unknown")
        # Mask partial IPs for privacy display
        if ip and ip != "unknown" and len(ip) > 6:
            ip_display = ip[:len(ip)//2] + "***"
        else:
            ip_display = ip
        duration = v.get("duration", "-")
        
        table += f"| {time_str} | {loc} | {device_icon} {device} | {browser} | {source} | `{ip_display}` | {duration} |\n"
    
    table += "\n*Updated automatically via GitHub Actions · [View live dashboard →](https://thebookmaster.zo.space/profile-analytics)*\n</details>\n"
    
    # Replace or insert
    VISITS_START = "<!-- RECENT_VISITS_START -->"
    VISITS_END = "<!-- RECENT_VISITS_END -->"
    import re
    if VISITS_START in content and VISITS_END in content:
        pattern = re.compile(f"{re.escape(VISITS_START)}.*?{re.escape(VISITS_END)}", re.DOTALL)
        content = pattern.sub(table, content)
    else:
        content += f"\n{VISITS_START}\n{table}\n{VISITS_END}\n"
    
    return content

def main():
    analytics = fetch_analytics()
    if not analytics:
        print("Failed to fetch analytics")
        return 0  # Don't fail the workflow for this
    
    content, sha = get_readme()
    if not sha:
        print("Failed to get README")
        return 0
    
    # Use detailed view records (with IP) instead of visitors
    detailed = analytics.get("detailed", [])
    if not detailed:
        # Fall back to visitors list
        detailed = analytics.get("visitors", [])
    
    # Sort by time descending
    visits = sorted(detailed, key=lambda x: x.get("time", ""), reverse=True)[:10]
    
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
        return 0  # Don't fail workflow for this

if __name__ == "__main__":
    exit(main())
