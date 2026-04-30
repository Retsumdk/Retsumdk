#!/usr/bin/env python3
"""
Fetch live GitHub + ecosystem stats for Retsumdk and update README.md dynamically.
Covers: contributions, repos, stars, forks, languages, streaks, top repos,
and live SCIEL/BOLT/AION stats from thebookmaster.zo.space.

Uses gh CLI for all GitHub API calls to avoid token/requests issues in CI.
"""

import re
import os
import sys
import json
import time
import requests
import subprocess

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _fetch_user_via_requests() -> dict:
    resp = requests.get("https://api.github.com/user", headers=HEADERS, timeout=15)
    return resp.json() if resp.status_code == 200 else {}


def _fetch_repos_via_requests() -> list:
    resp = requests.get(
        "https://api.github.com/user/repos?per_page=100&sort=updated",
        headers=HEADERS, timeout=15
    )
    return resp.json() if resp.status_code == 200 else []


def get_stats() -> dict:
    # ── User data: try requests first, fall back to JSON file ─────────────
    user_data = {}
    if GITHUB_TOKEN:
        try:
            user_data = _fetch_user_via_requests()
        except Exception as e:
            print(f"[WARNING] requests /user failed: {e}", file=sys.stderr)

    if not user_data or "login" not in user_data:
        try:
            with open("/tmp/gh_user.json") as f:
                raw = json.load(f)
            # users/Retsumdk returns a different structure than /user
            # Extract what we need from either format
            user_data = {
                "login": raw.get("login", ""),
                "public_repos": raw.get("public_repos", 0),
                "total_private_repos": raw.get("total_private_repos", 0),
                "followers": raw.get("followers", 0),
                "following": raw.get("following", 0),
            }
            print("[DEBUG] user_data loaded from /tmp/gh_user.json", file=sys.stderr)
        except Exception:
            pass

    # ── Repos data: try requests first, fall back to JSON file ────────────
    repos_data = []
    if GITHUB_TOKEN:
        try:
            repos_data = _fetch_repos_via_requests()
        except Exception as e:
            print(f"[WARNING] requests /user/repos failed: {e}", file=sys.stderr)

    if not repos_data:
        try:
            with open("/tmp/gh_repos.json") as f:
                repos_data = json.load(f)
            print(f"[DEBUG] repos_data ({len(repos_data)} repos) loaded from /tmp/gh_repos.json", file=sys.stderr)
        except Exception:
            pass

    public_repos = user_data.get("public_repos", 0)
    total_private_repos = user_data.get("total_private_repos", 0)
    total_repos = public_repos + total_private_repos
    followers = user_data.get("followers", 0)
    following = user_data.get("following", 0)

    public_only = [r for r in repos_data if not r.get("private")]
    stars = sum(r.get("stargazers_count", 0) for r in public_only)
    total_forks = sum(r.get("forks_count", 0) for r in public_only)

    langs = {}
    for r in repos_data:
        lang = r.get("language")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1

    top_repos = sorted(repos_data, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:6]

    # ── Contribution graph via GraphQL ───────────────────────────────────
    gql_data = {}
    if GITHUB_TOKEN:
        gql_query = """query($login: String!) {
            user(login: $login) {
                contributionsCollection {
                    contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
                }
                pinnedItems(first: 6, types: REPOSITORY) { nodes { ... on Repository { name url description primaryLanguage { name } stargazerCount forkCount } } }
            }
        }"""
        try:
            gql_resp = requests.post(
                "https://api.github.com/graphql",
                json={"query": gql_query, "variables": {"login": "Retsumdk"}},
                headers={**HEADERS, "Content-Type": "application/json"},
                timeout=15
            )
            gql_data = gql_resp.json().get("data", {}).get("user", {})
        except Exception as e:
            print(f"[WARNING] GraphQL failed: {e}", file=sys.stderr)

    if not gql_data:
        try:
            with open("/tmp/gh_graphql.json") as f:
                gql_data = json.load(f).get("data", {}).get("user", {})
            print("[DEBUG] gql_data loaded from /tmp/gh_graphql.json", file=sys.stderr)
        except Exception:
            pass

    pinned_repos = gql_data.get("pinnedItems", {}).get("nodes", [])

    cal = gql_data.get("contributionsCollection", {}).get("contributionCalendar", {})
    total_contributions = cal.get("totalContributions", 0)
    weeks = cal.get("weeks", [])

    longest = 0
    current = 0
    for week in weeks:
        for day in week.get("contributionDays", []):
            count = day.get("contributionCount", 0)
            if count > 0:
                longest = max(longest, current)
                current = 1
            else:
                current = 0

    graph_lines = []
    for week in weeks[-26:]:
        days = week.get("contributionDays", [])
        intensities = ["░", "▒", "▓", "█"]
        line = "".join(intensities[min(count, 3)] for count in
                     [min(d.get("contributionCount", 0), 4) for d in days])
        if line.replace("░", ""):
            graph_lines.append(line)

    # ── Zo Space stats ────────────────────────────────────────────────────
    zo_stats = {}
    for url, keys in [
        ("https://thebookmaster.zo.space/api/bolt-stats", ["bolt_listings", "sciel_agents"]),
        ("https://thebookmaster.zo.space/api/aion-stats", ["aion_agents"]),
        ("https://thebookmaster.zo.space/api/game-routes-count", ["routes"]),
    ]:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for k in keys:
                    if k in data:
                        zo_stats[k] = data[k]
        except Exception:
            pass

    print(f"[DEBUG] repos={total_repos} ({public_repos} public + {total_private_repos} private), "
          f"stars={stars}, followers={followers}, contributions={total_contributions}", file=sys.stderr)

    return {
        "contributions": total_contributions,
        "repos": total_repos,
        "stars": stars,
        "forks": total_forks,
        "followers": followers,
        "following": following,
        "languages": langs,
        "top_repos": top_repos,
        "longest_streak": longest,
        "current_streak": current,
        "graph_lines": graph_lines,
        "pinned_repos": pinned_repos,
        **zo_stats,
    }


def update_readme(stats: dict):
    """
    Updates ALL dynamic sections of README.md while PRESERVING all protected static sections.
    Protected sections (never touched by this function):
      - ## 🔗 Ecosystem
      - ## 🏆 Achievements  (only repo count updated)
      - ## 🧬 Commit DNA
      - ## 📊 Live Analytics Dashboard
      - ## 🪐 Reputation Orbit
      - <details> Recent Visits
    """
    readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()

    # ── SECTION 1: Language Badges ────────────────────────────────────────────
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
        "Unknown": ("cccccc", "question"),
    }
    lang_badges = []
    for lang, count in list(stats.get("languages", {}).items())[:8]:
        color, logo = lang_map.get(lang, ("cccccc", "code"))
        lang_badges.append(
            f"![{lang}](https://img.shields.io/badge/{lang}-{count}-{color}?style=flat-square&logo={logo}&logoColor=white)"
        )
    lang_badges_str = "  ".join(lang_badges)
    content = re.sub(
        r"(?:\[comment\]: # LANGUAGE BADGES START|<!-- LANGUAGE BADGES START -->)\n.*?(?:\[comment\]: # LANGUAGE BADGES END|<!-- LANGUAGE BADGES END -->)",
        f"<!-- LANGUAGE BADGES START -->\n{lang_badges_str}\n<!-- LANGUAGE BADGES END -->",
        content, flags=re.DOTALL
    )

    # ── SECTION 2: Stats Badges ───────────────────────────────────────────────
    content = re.sub(
        r"!\[Contributions\]\(https://img\.shields\.io/badge/Contributions-\d[^)]*\)",
        f"![Contributions](https://img.shields.io/badge/Contributions-{stats['contributions']}?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Repos\]\(https://img\.shields\.io/badge/Repos-\d[^)]*\)",
        f"![Repos](https://img.shields.io/badge/Repos-{stats['repos']}-2ea44f?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Stars\]\(https://img\.shields\.io/badge/Stars-\d[^)]*\)",
        f"![Stars](https://img.shields.io/badge/Stars-{stats['stars']}-2ea44f?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Forks\]\(https://img\.shields\.io/badge/Forks-\d[^)]*\)",
        f"![Forks](https://img.shields.io/badge/Forks-{stats['forks']}-2ea44f?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Followers\]\([^)]+\)",
        f"![Followers](https://img.shields.io/badge/Followers-{stats['followers']}-ffc107?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Following\]\([^)]+\)",
        f"![Following](https://img.shields.io/badge/Following-{stats['following']}-9c27b0?style=flat-square)",
        content
    )
    if "profile-analytics" not in content:
        content = re.sub(
            r"(!\[Profile Views\]\()[^)]+(\))",
            r'\1https://raw.githubusercontent.com/Retsumdk/profile-analytics/main/cards/total_views.svg\2',
            content
        )

    # ── SECTION 3: Profile tracking pixel ───────────────────────────────────
    if "<!-- profile-pixels:track -->" not in content:
        content = re.sub(
            r"(!\[Profile Views\]\(https://raw\.githubusercontent\.com/Retsumdk/profile-analytics/main/cards/total_views\.svg\))\n",
            r"\1\n<!-- profile-pixels:track --><img src=\"https://thebookmaster.zo.space/pixel.gif?u=Retsumdk\" width=\"0\" height=\"0\" style=\"border:none;position:absolute\" alt=\"\">\n",
            content
        )

    # ── SECTION 4: Daily Commits Heatmap ─────────────────────────────────────
    # HEATMAP URL IS LOCKED — only update_stats.py writes this section
    # URL is hardcoded to raw.githubusercontent.com — never zo.pub
    # Pattern matches the LOCKED marker to ensure no other script can corrupt it
    ts = str(int(time.time()))
    daily_section = (
        "<!-- DAILY COMMITS START -->\n"
        "<!-- HEATMAP LOCKED: Do not edit this line. Route: raw.githubusercontent.com only -->\n"
        f"![](https://raw.githubusercontent.com/Retsumdk/Retsumdk/main/images/heatmap.svg?v={ts})\n"
        "<!-- DAILY COMMITS END -->"
    )
    content = re.sub(
        r"<!-- DAILY COMMITS START -->.*?<!-- DAILY COMMITS END -->",
        daily_section,
        content, flags=re.DOTALL
    )

    # ── SECTION 5: Top Repos Table ────────────────────────────────────────────
    if stats.get("pinned_repos"):
        repo_rows = stats["pinned_repos"]
    else:
        repo_rows = stats.get("top_repos", [])

    if repo_rows:
        rows = []
        for r in repo_rows:
            if stats.get("pinned_repos"):
                lang_name = "Code"
                lang_field = r.get("primaryLanguage")
                if isinstance(lang_field, dict):
                    lang_name = lang_field.get("name", "Code")
                elif lang_field:
                    lang_name = str(lang_field)
                desc = (r.get("description") or "No description")[:60]
                stars = r.get("stargazerCount", 0)
                forks = r.get("forkCount", 0)
                name = r.get("name", "")
                url = r.get("url", f"https://github.com/Retsumdk/{name}")
            else:
                lang_name = (r.get("language") or "Code")
                desc = (r.get("description") or "No description")[:60]
                stars = r.get("stargazers_count", 0)
                forks = r.get("forks_count", 0)
                name = r.get("name", "")
                url = f"https://github.com/Retsumdk/{name}"
            rows.append(f"| [{name}]({url}) | {desc} | ⭐ {stars}&nbsp;🍴 {forks} | `{lang_name}` |")
        repos_table = "\n".join(rows)
        content = re.sub(
            r"\| Repository \| Description \| Stars / Forks \| Language \|\n\|---+---+---+---+\n.*?(?=\n## |\n\[comment\]|\n\n<details>)",
            "| Repository | Description | Stars / Forks | Language |\n|---|---|---|---|---|\n" + repos_table + "\n",
            content, flags=re.DOTALL
        )

    # ── SECTION 6: Currently Building ────────────────────────────────────────
    sciel_link = "[SCIEL Multi-Agent System](https://github.com/Retsumdk/agents)"
    bolt_link = "[BOLT Marketplace](https://github.com/Retsumdk/market)"
    game_engine_link = "[Game Engine](https://github.com/Retsumdk/game-engine)"
    aion_link = "[AION Blockchain](https://github.com/Retsumdk/aion-blockchain)"
    promptforge_link = "[PromptForge](https://github.com/Retsumdk/prompt-version-control)"

    sciel = f"**{sciel_link}**"
    if stats.get("sciel_agents"):
        sciel += f" — **{stats['sciel_agents']} active agents**"

    bolt = f"**{bolt_link}**"
    if stats.get("bolt_listings"):
        bolt += f" — **{stats['bolt_listings']} listings**"

    game = f"**{game_engine_link}**"
    routes = stats.get("routes")
    game_desc = "Three.js game engine with playable games"
    if routes:
        game_desc = f"Three.js game engine with {routes} routes and playable games"
    game += f" — {game_desc}"

    aion = f"**{aion_link}**"
    if stats.get("aion_agents"):
        aion += f" — **{stats['aion_agents']} registered agents**"

    building_lines = "\n".join([
        f"- {sciel} — Autonomous agents that collaborate, delegate, and self-improve",
        f"- {bolt} — Agent marketplace for buying and selling AI capabilities",
        f"- {game}",
        f"- {aion} — Layer 1 blockchain for AI agent economies",
        f"- **{promptforge_link}** — Professional prompt engineering and versioning tools",
    ])
    content = re.sub(
        r"(\[comment\]: # CURRENTLY BUILDING START\n).*?(\n\[comment\]: # CURRENTLY BUILDING END\n)",
        f"\\1{building_lines}\n\\2",
        content, flags=re.DOTALL
    )

    # ── SECTION 7: Achievements — update repo count only ───────────────────
    content = re.sub(
        r"(\*\*)\d+( repositories\*\* across the SCIEL, BOLT, and PromptForge ecosystems)",
        f"**{stats['repos']}\\2",
        content
    )

    with open(readme_path, "w") as f:
        f.write(content)

    print(
        f"Updated: contributions={stats['contributions']}, repos={stats['repos']}, "
        f"followers={stats['followers']}, stars={stats['stars']}, "
        f"forks={stats['forks']}, longest_streak={stats.get('longest_streak')}, "
        f"sciel_agents={stats.get('sciel_agents')}, "
        f"bolt_listings={stats.get('bolt_listings')}, "
        f"aion_agents={stats.get('aion_agents')}"
    )


if __name__ == "__main__":
    stats = get_stats()
    update_readme(stats)
