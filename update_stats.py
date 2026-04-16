#!/usr/bin/env python3
"""
Fetch live GitHub stats for Retsumdk and update README.md dynamically.
Covers: contributions, repos, followers, following, stars, forks, languages,
streak, pinned repos, and more.
"""
import re, os, json, urllib.request
from datetime import datetime, timezone
from collections import defaultdict

GH_API = "https://api.github.com"
GRAPHQL_API = "https://api.github.com/graphql"

def gh_get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def gh_graphql(query: str, token: str) -> dict:
    req = urllib.request.Request(
        GRAPHQL_API,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get_stats(token: str) -> dict:
    # REST API - profile + repos
    user = gh_get(f"{GH_API}/users/Retsumdk", token)
    repos_data = gh_get(f"{GH_API}/users/Retsumdk/repos?sort=updated&per_page=100&type=public", token)

    followers = user.get("followers", 0)
    following = user.get("following", 0)
    public_repos = user.get("public_repos", 0)

    total_stars = sum(r.get("stargazers_count", 0) for r in repos_data)
    total_forks = sum(r.get("forks_count", 0) for r in repos_data)

    # Language counts
    langs = defaultdict(int)
    for r in repos_data:
        lang = r.get("language") or "Unknown"
        langs[lang] += 1

    # Top repos by stars + forks
    top_repos = sorted(repos_data, key=lambda r: r.get("stargazers_count", 0) * 2 + r.get("forks_count", 0), reverse=True)[:6]

    # GraphQL - contributions
    gql_query = """
    {
      viewer {
        contributionsCollection {
          totalCommitContributions
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
      user(login: "Retsumdk") {
        contributionsCollection {
          totalCommitContributions
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
    """
    try:
        gql = gh_graphql(gql_query, token)
        cal = gql.get("data", {}).get("user", {}).get("contributionsCollection", {}).get("contributionCalendar", {})
        total_contributions = cal.get("totalContributions", 0)

        # Calculate streak
        weeks = cal.get("weeks", [])
        streak = 0
        longest = 0
        current = 0
        for week in reversed(weeks):
            for day in reversed(week.get("contributionDays", [])):
                if day.get("contributionCount", 0) > 0:
                    streak += 1
                    if streak == 1:
                        current = 1
                else:
                    if current == 1:
                        current = 0
                    longest = max(longest, streak)
                    streak = 0
        longest = max(longest, streak)

        # Build ASCII contribution graph (last 26 weeks)
        weeks_data = weeks[-26:] if len(weeks) > 26 else weeks
        graph_lines = []
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for day_idx in range(7):
            row = f"{days[day_idx]} "
            for week in weeks_data:
                week_days = week.get("contributionDays", [])
                if day_idx < len(week_days):
                    count = week_days[day_idx].get("contributionCount", 0)
                    if count == 0:
                        row += "░"
                    elif count < 3:
                        row += "▁"
                    elif count < 6:
                        row += "▂"
                    elif count < 9:
                        row += "▃"
                    elif count < 12:
                        row += "▄"
                    else:
                        row += "▅"
                else:
                    row += " "
            graph_lines.append(row)
    except Exception as e:
        print(f"GraphQL error: {e}")
        total_contributions = 0
        longest = 0
        current = 0
        graph_lines = []

    # Pinned repos via GraphQL
    pinned_query = """
    {
      user(login: "Retsumdk") {
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes {
            ... on Repository {
              name
              description
              stargazerCount
              forkCount
              primaryLanguage { name }
              url
            }
          }
        }
      }
    }
    """
    pinned_repos = []
    try:
        pinned_gql = gh_graphql(pinned_query, token)
        pinned_repos = pinned_gql.get("data", {}).get("user", {}).get("pinnedItems", {}).get("nodes", [])
    except Exception as e:
        print(f"Pinned query error: {e}")
        pinned_repos = []

    return {
        "contributions": total_contributions,
        "repos": public_repos,
        "followers": followers,
        "following": following,
        "stars": total_stars,
        "forks": total_forks,
        "languages": dict(sorted(langs.items(), key=lambda x: -x[1])),
        "top_repos": top_repos,
        "longest_streak": longest,
        "current_streak": 0,
        "graph_lines": graph_lines,
        "pinned_repos": pinned_repos,
    }

def update_readme(stats: dict):
    readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()

    lang_map = {
        "TypeScript": ("3178C6", "typescript"),
        "Python": ("3776AB", "python"),
        "JavaScript": ("F7DF1E", "javascript"),
        "Go": ("00ADD8", "go"),
        "Shell": ("89E051", "gnu-bash"),
        "HTML": ("E34F26", "html5"),
        "CSS": ("1572B6", "css3"),
        "Rust": ("CE422B", "rust"),
        "Java": ("B07219", "java"),
        "C++": ("F34B7D", "cplusplus"),
        "C": ("555555", "c"),
        "Ruby": ("CC342D", "ruby"),
        "PHP": ("4F5D95", "php"),
        "Swift": ("F05138", "swift"),
        "Kotlin": ("7F52FF", "kotlin"),
        "Dart": ("00B4AB", "dart"),
        "Unknown": ("cccccc", "question"),
    }

    # Language badges
    lang_badges = []
    for lang, count in list(stats["languages"].items())[:8]:
        color, logo = lang_map.get(lang, ("cccccc", "code"))
        lang_badges.append(
            f"![{lang}](https://img.shields.io/badge/{lang}-{count}-{color}?style=flat-square&logo={logo}&logoColor=white)"
        )
    lang_badges_str = "  ".join(lang_badges)
    content = re.sub(
        r"\[comment\]: # LANGUAGE BADGES START.*?\[comment\]: # LANGUAGE BADGES END",
        f"[comment]: # LANGUAGE BADGES START\n{lang_badges_str}\n[comment]: # LANGUAGE BADGES END",
        content, flags=re.DOTALL
    )

    # Stats badges
    replacements = {
        "!\\[Contributions\\].*?\\)": f"![Contributions](https://img.shields.io/badge/Contributions-{stats['contributions']}?style=flat-square)",
        "!\\[Repos\\].*?\\)": f"![Repos](https://img.shields.io/badge/Repos-{stats['repos']}-2ea44f?style=flat-square)",
        "!\\[Stars\\].*?\\)": f"![Stars](https://img.shields.io/badge/Stars-{stats['stars']}-2ea44f?style=flat-square)",
        "!\\[Forks\\].*?\\)": f"![Forks](https://img.shields.io/badge/Forks-{stats['forks']}-2ea44f?style=flat-square)",
        "!\\[Followers\\].*?\\)": f"![Followers](https://img.shields.io/badge/Followers-{stats['followers']}-ffc107?style=flat-square)",
        "!\\[Following\\].*?\\)": f"![Following](https://img.shields.io/badge/Following-{stats['following']}-9c27b0?style=flat-square)",
    }
    for pattern, repl in replacements.items():
        content = re.sub(pattern, repl, content)

    # Contribution graph
    graph_section = ""
    if stats["graph_lines"]:
        graph_lines_str = "\n".join(stats["graph_lines"])
        graph_section = f"""
<details>
<summary>📅 Contribution Graph</summary>

```
{graph_lines_str}
```
_Last 26 weeks · {stats['contributions']} total contributions · 🔥 {stats['longest_streak']} day longest streak_

</details>
"""
    content = re.sub(
        r"\[comment\]: # CONTRIBUTION GRAPH START.*?\[comment\]: # CONTRIBUTION GRAPH END",
        f"[comment]: # CONTRIBUTION GRAPH START{graph_section}[comment]: # CONTRIBUTION GRAPH END",
        content, flags=re.DOTALL
    )

    # Pinned repos table
    if stats["pinned_repos"]:
        rows = []
        for r in stats["pinned_repos"]:
            lang = r.get("primaryLanguage", {}).get("name", "Code") if isinstance(r.get("primaryLanguage"), dict) else (r.get("primaryLanguage") or "Code")
            desc = (r.get("description") or "No description")[:60]
            stars = r.get("stargazerCount", 0)
            forks = r.get("forkCount", 0)
            name = r.get("name", "")
            url = r.get("url", f"https://github.com/Retsumdk/{name}")
            rows.append(f"| [{name}]({url}) | {desc} | ⭐ {stars}&nbsp;🍴 {forks} | `{lang}` |")
        pinned_table = "\n".join(rows)
        content = re.sub(
            r"\| Repository \| Description \|\n\|---\|---\|\n\|.*?\|",
            "| Repository | Description | Stars / Forks | Language |\n|---|---|---|---|\n" + pinned_table + "\n",
            content
        )

    with open(readme_path, "w") as f:
        f.write(content)

    print(f"Updated stats: contributions={stats['contributions']}, repos={stats['repos']}, "
          f"followers={stats['followers']}, stars={stats['stars']}, "
          f"forks={stats['forks']}, languages={list(stats['languages'].keys())[:5]}, "
          f"longest_streak={stats['longest_streak']}")

if __name__ == "__main__":
    token = os.environ.get("GITHUB_TOKEN", "")
    stats = get_stats(token)
    update_readme(stats)
