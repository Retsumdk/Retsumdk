#!/usr/bin/env python3
"""
Generate daily commits bar chart SVG for the last 7 days.
Fetches real commit data from GitHub GraphQL contributionCalendar API.
"""
import os, json, urllib.request
from datetime import datetime, timezone, timedelta

GH_GRAPHQL = "https://api.github.com/graphql"

def gh_graphql(query: str, token: str) -> dict:
    req = urllib.request.Request(
        GH_GRAPHQL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def fetch_daily_commits(token: str) -> dict:
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    gql_query = """
    {
      user(login: "Retsumdk") {
        contributionsCollection(from: "%s", to: "%s") {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                weekday
              }
            }
          }
        }
      }
    }
    """ % (seven_days_ago.isoformat(), now.isoformat())
    result = gh_graphql(gql_query, token)
    cal = (result.get("data", {})
            .get("user", {})
            .get("contributionsCollection", {})
            .get("contributionCalendar", {}))
    all_days = []
    for week in cal.get("weeks", []):
        for day in week.get("contributionDays", []):
            all_days.append({
                "date": day["date"],
                "count": day.get("contributionCount", 0),
                "weekday": day.get("weekday", 0),
            })
    all_days.sort(key=lambda d: d["date"])
    last_7 = all_days[-7:]
    return {"days": last_7, "total": sum(d["count"] for d in last_7)}

def generate_svg(data: dict) -> str:
    days = data["days"]
    total = data["total"]
    DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    counts = [d["count"] for d in days]
    labels = [DAY_NAMES[d["weekday"]] for d in days]
    max_val = max(counts) if counts and max(counts) > 0 else 1
    BAR_W = 60; BAR_GAP = 12; PAD_L = 10; PAD_B = 50; PAD_T = 50
    W = PAD_L + len(counts) * (BAR_W + BAR_GAP) + PAD_L
    H = PAD_T + 200 + PAD_B + 36
    BAR_MAX_H = 200
    def bar_color(v):
        if v == 0: return "#161b22"
        p = v / max_val
        if p <= 0.25: return "#0e4429"
        if p <= 0.5:  return "#006d32"
        if p <= 0.75: return "#26a641"
        return "#39d353"
    def font():
        return "font-family=\"-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif\""
    svg = f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%">\n'
    svg += f'<rect width="100%" height="100%" fill="#0d1117"/>\n'
    svg += f'<text x="{PAD_L}" y="20" font-size="14" font-weight="600" fill="#c9d1d9" {font()}>Daily commits</text>\n'
    svg += f'<text x="{PAD_L}" y="38" font-size="11" fill="#6e7681" {font()}>{total} commits · last 7 days</text>\n'
    for i, (label, count) in enumerate(zip(labels, counts)):
        x = PAD_L + i * (BAR_W + BAR_GAP)
        bar_h = int((count / max_val) * BAR_MAX_H) if count > 0 else 0
        bar_y = PAD_T + BAR_MAX_H - bar_h
        fill = bar_color(count)
        svg += f'<rect x="{x}" y="{bar_y}" width="{BAR_W}" height="{bar_h}" rx="6" fill="{fill}"/>\n'
        if bar_h >= 20:
            svg += f'<text x="{x + BAR_W//2}" y="{bar_y + 18}" text-anchor="middle" font-size="11" font-weight="600" fill="#c9d1d9" {font()}>{count}</text>\n'
        svg += f'<text x="{x + BAR_W//2}" y="{PAD_T + BAR_MAX_H + 16}" text-anchor="middle" font-size="12" fill="#8b949e" {font()}>{count}</text>\n'
        svg += f'<text x="{x + BAR_W//2}" y="{PAD_T + BAR_MAX_H + 34}" text-anchor="middle" font-size="11" fill="#6e7681" {font()}>{label}</text>\n'
    lx = PAD_L; ly = PAD_T + BAR_MAX_H + 56
    svg += f'<text x="{lx}" y="{ly}" font-size="10" fill="#6e7681" {font()}>Less</text>\n'
    for k, c in enumerate(["#161b22","#0e4429","#006d32","#26a641","#39d353"]):
        svg += f'<rect x="{lx+30+k*16}" y="{ly-10}" width="13" height="13" rx="2" fill="{c}"/>\n'
    svg += f'<text x="{lx+30+5*16+6}" y="{ly}" font-size="10" fill="#6e7681" {font()}>More</text>\n'
    svg += '</svg>'
    return svg

def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    data = fetch_daily_commits(token)
    print(f"Days: {[(d['date'], d['count']) for d in data['days']]}, total={data['total']}")
    svg = generate_svg(data)
    with open("/tmp/heatmap.svg", "w") as f:
        f.write(svg)
    print(f"Written {len(svg)} bytes")

if __name__ == "__main__":
    main()
