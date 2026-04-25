#!/usr/bin/env python3
"""Fetch analytics and update README with recent visits table."""

import json, os, base64, re, requests
from datetime import datetime

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "Retsumdk/Retsumdk"
API_BASE = "https://api.github.com"
ZO_API = "https://thebookmaster.zo.space/api/profile-views"

def fetch_analytics():
    try:
        resp = requests.get(ZO_API, headers={"User-Agent": "GitHub-Actions"}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def get_readme():
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    resp = requests.get(f"{API_BASE}/repos/{REPO}/contents/README.md", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]
    return None, None

def update_readme(content, sha, visits):
    VISITS_START = "<!-- RECENT_VISITS_START -->"
    VISITS_END = "<!-- RECENT_VISITS_END -->"

    table = f"\n<details>\n<summary>📊 Recent Visits ({len(visits)} total)</summary>\n\n"
    table += "| Time | Location | IP | Device | Browser | Source | Duration |\n"
    table += "|------|----------|-----|--------|---------|--------|----------|\n"

    for v in visits:
        ts = v.get("time", "")
        if ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            time_str = dt.strftime("%m-%d %H:%M")
        else:
            time_str = "??-?? ??:??"

        country = v.get("country", "??")
        city = v.get("city", "")
        loc = f"🇺🇸 {country} {city}".strip()
        ip = v.get("ip", "-")
        device = v.get("device", "Unknown")
        browser = v.get("browser", "Unknown")
        referrer = v.get("referrer", "direct")
        duration = v.get("duration", "-")
        table += f"| {time_str} | {loc} | `{ip}` | {device} | {browser} | {referrer} | {duration} |\n"

    table += "\n*Updated automatically via GitHub Actions · [View live dashboard →](https://thebookmaster.zo.space/profile-analytics)*</details>\n"

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
        return 1

    content, sha = get_readme()
    if not sha:
        print("Failed to get README")
        return 1

    detailed = analytics.get("detailed", [])
    visits = sorted(detailed, key=lambda x: x.get("time", ""), reverse=True)[:10]

    new_content = update_readme(content, sha, visits)

    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = {"message": "📊 Add IP column to recent visits table", "content": base64.b64encode(new_content.encode()).decode(), "sha": sha}
    resp = requests.put(f"{API_BASE}/repos/{REPO}/contents/README.md", headers=headers, json=data)

    if resp.status_code == 200:
        print(f"✅ Updated README with {len(visits)} visits (incl. IP)")
        return 0
    else:
        print(f"❌ Failed: {resp.status_code} {resp.text}")
        return 1

if __name__ == "__main__":
    exit(main())
