#!/usr/bin/env python3
"""
Fetch live GitHub + ecosystem stats for Retsumdk and update README.md dynamically.
Covers: contributions, repos, stars, forks, languages, streaks, top repos,
and live SCIEL/BOLT/AION stats from thebookmaster.zo.space.
"""

import re
import os
import sys
import time
import requests

CLIENT_ID = os.environ.get("CLIENT_ID", "")

def get_stats(token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    repos_url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    user_url = "https://api.github.com/user"

    user_resp = requests.get(user_url, headers=headers, timeout=15)
    user_data = user_resp.json()
    total_repos = user_data.get("total_private_repos", 0) + user_data.get("public_repos", 0)

    repos_resp = requests.get(repos_url, headers=headers, timeout=15)
    repos = repos_resp.json() if repos_resp.status_code == 200 else []

    repos = [r for r in repos if not r.get("private")]

    stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    langs = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1

    top_repos = sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:6]

    # Contribution graph via GraphQL
    query = """query($login: String!) {
        user(login: $login) {
            contributionsCollection {
                contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
            }
            pinnedItems(first: 6, types: REPOSITORY) { nodes { ... on Repository { name url description primaryLanguage { name } stargazerCount forkCount } } }
        }
    }"""
    variables = {"login": "Retsumdk"}
    gql_resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers={**headers, "Content-Type": "application/json"},
        timeout=15
    )
    gql_data = gql_resp.json().get("data", {}).get("user", {})
    pinned_repos = gql_data.get("pinnedItems", {}).get("nodes", [])

    cal = gql_data.get("contributionsCollection", {}).get("contributionCalendar", {})
    total_contributions = cal.get("totalContributions", 0)
    weeks = cal.get("weeks", [])

    graph_lines = []
    longest = 0
    current = 0
    day_count = 0
    for week in weeks:
        for day in week.get("contributionDays", []):
            count = day.get("contributionCount", 0)
            if count > 0:
                longest = max(longest, current)
                current = 1
            else:
                current = 0
            day_count += 1

    for week in weeks[-26:]:
        days = week.get("contributionDays", [])
        intensities = ["░", "▒", "▓", "█"]
        line = "".join(intensities[min(count, 3)] for count in
                     [min(d.get("contributionCount", 0), 4) for d in days])
        if line.replace("░", ""):
            graph_lines.append(line)

    # Zo Space dynamic stats
    zo_stats = {}
    try:
        resp = requests.get(f"https://thebookmaster.zo.space/api/bolt-stats", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            zo_stats["bolt_listings"] = data.get("listings", 0)
            zo_stats["sciel_agents"] = data.get("agents", 0)
    except Exception:
        pass

    try:
        resp2 = requests.get(f"https://thebookmaster.zo.space/api/aion-stats", timeout=10)
        if resp2.status_code == 200:
            data2 = resp2.json()
            zo_stats["aion_agents"] = data2.get("registered_agents", 0)
    except Exception:
        pass

    try:
        resp3 = requests.get(f"https://thebookmaster.zo.space/api/game-routes-count", timeout=10)
        if resp3.status_code == 200:
            zo_stats["routes"] = resp3.json().get("count", 0)
    except Exception:
        pass

    return {
        "contributions": total_contributions,
        "repos": total_repos,
        "stars": stars,
        "forks": total_forks,
        "followers": user_data.get("followers", 0),
        "following": user_data.get("following", 0),
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
    # Profile Views badge — preserve existing URL, don't change it
    if "profile-analytics" not in content:
        content = re.sub(
            r"(!\[Profile Views\]\()[^)]+(\))",
            r'\1https://raw.githubusercontent.com/Retsumdk/profile-analytics/main/cards/total_views.svg\2',
            content
        )

    # ── SECTION 3: Profile tracking pixel — add only if missing ───────────────
    if "<!-- profile-pixels:track -->" not in content:
        # Add right after Profile Views line
        content = re.sub(
            r"(!\[Profile Views\]\(https://raw\.githubusercontent\.com/Retsumdk/profile-analytics/main/cards/total_views\.svg\))\n",
            r"\1\n<!-- profile-pixels:track --><img src=\"https://thebookmaster.zo.space/pixel.gif?u=Retsumdk\" width=\"0\" height=\"0\" style=\"border:none;position:absolute\" alt=\"\">\n",
            content
        )

    # ── SECTION 4: Daily Commits Heatmap ─────────────────────────────────────
    # Always use raw.githubusercontent.com — GitHub renders this in README
    daily_section = (
        "<!-- DAILY COMMITS START -->\n"
        "![](https://raw.githubusercontent.com/Retsumdk/Retsumdk/main/images/heatmap.svg)\n"
        "\n<!-- DAILY COMMITS END -->"
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

    # ── SECTION 7: Achievements — update repo count only, preserve everything else
    content = re.sub(
        r"(\*\*)\d+( repositories\*\* across the SCIEL, BOLT, and PromptForge ecosystems)",
        f"**{stats['repos']}\\2",
        content
    )

    # ── PROTECTED SECTIONS — update_stats.py DOES NOT TOUCH THESE: ───────────
    # ## 🔗 Ecosystem        — NEVER touched
    # ## 🏆 Achievements     — only repo count patched above
    # ## 🧬 Commit DNA        — NEVER touched
    # ## 📊 Live Analytics    — NEVER touched
    # ## 🪐 Reputation Orbit  — NEVER touched
    # 📊 Recent Visits        — NEVER touched

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
    token = os.environ.get("GITHUB_TOKEN", "")
    stats = get_stats(token)
    update_readme(stats)