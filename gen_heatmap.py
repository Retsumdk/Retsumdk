#!/usr/bin/env python3
"""
Generate heatmap SVG for the last 7 days of commits grouped by day-of-week and hour.
Fetches real commit data from the GitHub GraphQL API using GITHUB_TOKEN.
"""
import os, sys, json, urllib.request
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


def fetch_commit_data(token: str) -> dict:
    """Fetch commits from the last 7 days, grouped by weekday and hour."""
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    gql_query = f"""
    {{
      viewer {{
        contributionsCollection(to: "{seven_days_ago}") {{
          commitContributionsByRepository(maxRepositories: 100) {{
            contributions {{
              commitCount
              occurredAt
            }}
          }}
        }}
      }}
    }}
    """

    try:
        result = gh_graphql(gql_query, token)
        collections = (result.get("data", {})
                       .get("viewer", {})
                       .get("contributionsCollection", {})
                       .get("commitContributionsByRepository", []))
    except Exception as e:
        print(f"GraphQL error: {e}")
        return None

    # grid[weekday][hour] = count
    grid = [[0]*24 for _ in range(7)]
    total = 0

    for repo in collections:
        for contrib in repo.get("contributions", []):
            count = contrib.get("commitCount", 0)
            occurred_at = contrib.get("occurredAt", "")
            if not occurred_at or count == 0:
                continue

            dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            weekday = dt.weekday()  # 0=Mon .. 6=Sun
            hour = dt.hour
            grid[weekday][hour] += count
            total += count

    return {"grid": grid, "total": total}


def generate_svg(grid, total):
    DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    max_val = max(max(row) for row in grid) if total > 0 else 1
    CELL = 18; GAP = 4; PAD_L = 52; PAD_T = 36; LABEL_GAP = 10
    cols = 24; rows = 7
    grid_w = cols*(CELL+GAP)
    W = PAD_L + grid_w + 24
    H = PAD_T + rows*(CELL+GAP) + LABEL_GAP + 24

    def col(v):
        if v == 0: return '#161b22'
        p = v / max_val
        if p <= 0.25: return '#0e4429'
        if p <= 0.5:  return '#006d32'
        if p <= 0.75: return '#26a641'
        return '#39d353'

    def cell_font(v):
        return 'font-size="9" fill="#c9d1d9" font-family="-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif"'

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%">
<rect width="100%" height="100%" fill="#0d1117"/>
<text x="4" y="18" font-size="13" font-weight="600" fill="#c9d1d9" font-family="-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif">Daily commits by hour</text>
<text x="4" y="32" font-size="10" fill="#6e7681" font-family="-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif">{total} commits · last 7 days</text>
'''
    for i, day in enumerate(DAYS):
        y = PAD_T + i*(CELL+GAP) + CELL//2 + 5
        svg += f'<text x="{PAD_L-LABEL_GAP}" y="{y}" font-size="11" text-anchor="end" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif">{day}</text>\n'

    for h in [0, 6, 12, 18]:
        x = PAD_L + h*(CELL+GAP) + CELL//2
        svg += f'<text x="{x}" y="{PAD_T+rows*(CELL+GAP)+LABEL_GAP+14}" font-size="10" text-anchor="middle" fill="#6e7681" font-family="-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif">{h}:00</text>\n'

    for i in range(rows):
        for h in range(cols):
            v = grid[i][h]
            x = PAD_L + h*(CELL+GAP)
            y = PAD_T + i*(CELL+GAP)
            fill = col(v)
            svg += f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3" fill="{fill}"/>\n'
            if v > 0:
                txt_x = x + CELL//2
                txt_y = y + CELL//2 + 4
                svg += f'<text x="{txt_x}" y="{txt_y}" text-anchor="middle" {cell_font(v)}>{v}</text>\n'

    lx = PAD_L + grid_w - 60
    ly = PAD_T + rows*(CELL+GAP) + LABEL_GAP + 12
    svg += f'<text x="{lx-2}" y="{ly}" font-size="10" fill="#6e7681" font-family="-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif">Less</text>\n'
    COLS = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']
    for k in range(5):
        svg += f'<rect x="{lx+28+k*14}" y="{ly-10}" width="11" height="11" rx="2" fill="{COLS[k]}"/>\n'
    svg += f'<text x="{lx+100}" y="{ly}" font-size="10" fill="#6e7681" font-family="-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif">More</text>\n'
    svg += '</svg>'
    return svg


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    data = fetch_commit_data(token)

    if data is None:
        # Fallback: try fetching contribution calendar instead
        print("Warning: using placeholder data (API unreachable)")
        grid = [[0]*24 for _ in range(7)]
        total = 0
    else:
        grid = data["grid"]
        total = data["total"]

    svg = generate_svg(grid, total)
    with open('/tmp/heatmap.svg', 'w') as f:
        f.write(svg)
    print(f"Done: {len(svg)} bytes, total={total}, max={max(max(row) for row in grid) if total > 0 else 0}")


if __name__ == "__main__":
    main()