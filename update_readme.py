#!/usr/bin/env python3
"""Clean up duplicate visits tables from the README and replace with a proper marker-wrapped version."""

import json
import os
import base64
import urllib.request
import urllib.error
import re as re_module
from datetime import datetime

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "Retsumdk/Retsumdk"
API_BASE = "https://api.github.com"
ZO_API = "https://thebookmaster.zo.space/api"

COUNTRY_EMOJI = {
    "US": "🇺🇸", "CA": "🇨🇦", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
    "JP": "🇯🇵", "AU": "🇦🇺", "IN": "🇮🇳", "BR": "🇧🇷", "SG": "🇸🇬",
    "NL": "🇳🇱", "SE": "🇸🇪", "NO": "🇳🇴", "DK": "🇩🇰", "FI": "🇫🇮",
    "PL": "🇵🇱", "IT": "🇮🇹", "ES": "🇪🇸", "MX": "🇲🇽", "KR": "🇰🇷",
    "CN": "🇨🇳", "RU": "🇷🇺", "ZA": "🇿🇦", "AE": "🇦🇪", "??": "🌍",
}


def fetch_analytics():
    try:
        req = urllib.request.Request(
            f"{ZO_API}/profile-views",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"Failed to fetch analytics: {e}")
        return None


def get_readme():
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    req = urllib.request.Request(
        f"{API_BASE}/repos/{REPO}/contents/README.md",
        headers=headers
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def parse_iso(ts: str):
    if not ts:
        return None
    try:
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def build_visits_table(visitors, detailed, max_rows=10):
    rows = []
    for v in visitors:
        ts = v.get("time") or v.get("lastSeen")
        dt = parse_iso(ts) if ts else None
        time_str = dt.strftime("%m-%d %H:%M") if dt else "Unknown"
        country = v.get("country", "??")
        city = (v.get("city") or "").strip()
        location = f"{country}" + (f" {city}" if city else "")
        device = v.get("device", "Unknown")
        browser = v.get("browser", "Unknown")
        source = v.get("source", "direct")
        duration = v.get("duration", "-")
        ip = v.get("ip", "-")
        rows.append({"_dt": dt, "time": time_str, "location": location,
                     "device": device, "browser": browser, "source": source,
                     "duration": duration, "ip": ip})

    if not rows:
        for v in detailed:
            ts = v.get("time")
            dt = parse_iso(ts) if ts else None
            time_str = dt.strftime("%m-%d %H:%M") if dt else "Unknown"
            country = v.get("country", "??")
            device = v.get("device", "Unknown")
            browser = v.get("browser", "Unknown")
            source = v.get("referrer", "direct")
            duration = v.get("duration", "-")
            ip = v.get("ip", "-")
            rows.append({"_dt": dt, "time": time_str, "location": country,
                         "device": device, "browser": browser, "source": source,
                         "duration": duration, "ip": ip})

    rows.sort(key=lambda r: r["_dt"] or datetime.min, reverse=True)
    rows = rows[:max_rows]

    total = len(visitors) + len(detailed)
    lines = []
    lines.append(f"\n<!-- RECENT_VISITS_START -->\n<details>")
    lines.append(f"<summary>📊 Recent Visits ({total} total · live)</summary>\n")
    lines.append("| Time | Location | Device | Browser | Source | Duration | IP |")
    lines.append("|------|----------|--------|---------|--------|----------|-----|")
    for r in rows:
        flag = COUNTRY_EMOJI.get(r["location"][:2] if r["location"] else "??", "🌍")
        loc = f"{flag} {r['location']}"
        dev_icon = "🖥️" if r["device"] == "desktop" else "📱"
        lines.append(
            f"| {r['time']} | {loc} | {dev_icon} {r['device']} | {r['browser']} | "
            f"{r['source']} | {r['duration']} | {r['ip']} |"
        )
    lines.append("\n*Updated automatically via GitHub Actions · [View live dashboard →](https://thebookmaster.zo.space/profile-analytics)*")
    lines.append("</details>\n<!-- RECENT_VISITS_END -->\n")
    return "\n".join(lines)


def clean_and_replace(content, visits_table):
    # Remove ALL duplicate <details> blocks containing "Recent Visits" that are NOT wrapped in markers
    # Pattern: standalone <details> blocks (not inside RECENT_VISITS markers)
    # These appear as duplicates between line 124-142 and 145-163 in the README

    # First, remove the RECENT_VISITS markers section if it exists (dirty state)
    marker_pat = re_module.compile(
        re_module.escape("<!-- RECENT_VISITS_START -->") + r".*?" + re_module.escape("<!-- RECENT_VISITS_END -->"),
        re_module.DOTALL
    )
    content = marker_pat.sub("", content)

    # Remove standalone duplicate <details> blocks (lines 124-142 and 145-163)
    # Match <details> that has "Recent Visits" in its <summary> and is NOT preceded by RECENT_VISITS_START
    # We remove these by matching them specifically
    dup_pat = re_module.compile(
        r"\s*<details>\s*\n<summary>📊 Recent Visits.*?</details>",
        re_module.DOTALL
    )
    content = dup_pat.sub("", content)

    # Now append the proper marker-wrapped table at the end
    content = content.rstrip() + "\n" + visits_table

    return content


def commit_readme(content, sha):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    payload = json.dumps({
        "message": "📊 Auto-update recent visits table [fix duplicates]",
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    }).encode()

    req = urllib.request.Request(
        f"{API_BASE}/repos/{REPO}/contents/README.md",
        data=payload,
        headers=headers,
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"✅ README cleaned and updated")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ HTTP {e.code}: {body}")
        return False


def main():
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set")
        return 1

    analytics = fetch_analytics()
    if not analytics:
        print("❌ Could not fetch analytics from zo.space")
        return 1

    visitors = analytics.get("visitors", [])
    detailed = analytics.get("detailed", [])

    print(f"Fetched {len(visitors)} visitors, {len(detailed)} detailed records")

    content, sha = get_readme()
    if not sha:
        print("❌ Could not read current README")
        return 1

    visits_table = build_visits_table(visitors, detailed, max_rows=10)
    new_content = clean_and_replace(content, visits_table)

    if commit_readme(new_content, sha):
        return 0
    return 1


if __name__ == "__main__":
    exit(main())
