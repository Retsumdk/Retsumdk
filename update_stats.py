#!/usr/bin/env python3
"""
Fetch live GitHub + ecosystem stats for Retsumdk and update README.md dynamically.
Covers: contributions, repos, stars, forks, languages, streaks, top repos,
and live SCIEL/BOLT/AION stats from thebookmaster.zo.space.

Strategy: gh CLI for user/repos (most reliable), requests for GraphQL + Zo Space.
"""

import re
import os
import sys
import json
import subprocess
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

def gh(cmd: list[str], check: bool = False) -> str:
    """Run gh CLI, return stdout. Returns '' on failure or check=False."""
    env = os.environ.copy()
    env["GITHUB_TOKEN"] = GITHUB_TOKEN
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        print(f"[WARNING] gh command failed (code={result.returncode}): {' '.join(cmd)} — {result.stderr[:200]}", file=sys.stderr)
        return ""
    return result.stdout

def get_user_data() -> dict:
    """Fetch user data via gh CLI (most reliable in all environments)."""
    out = gh(["gh", "api", "user"])
    if out:
        try:
            return json.loads(out)
        except Exception:
            pass
    return {}

def get_repos_data() -> list:
    """Fetch all repos via gh CLI — avoid jq pipe which can silently fail in GA."""
    repos = []
    page = 1
    while True:
        out = gh(["gh", "api", f"user/repos?page={page}&per_page=100&sort=updated"])
        if not out:
            break
        try:
            batch = json.loads(out)
            if not isinstance(batch, list) or not batch:
                break
            for r in batch:
                repos.append({
                    "name": r.get("name"),
                    "private": r.get("private"),
                    "stargazers_count": r.get("stargazers_count", 0),
                    "forks_count": r.get("forks_count", 0),
                    "language": r.get("language"),
                    "description": r.get("description"),
                })
            if len(batch) < 100:
                break
            page += 1
        except Exception:
            break
    return repos

def get_contributions_data() -> dict:
    """Fetch contributions via GraphQL (gh CLI or requests)."""
    gql = """query($login: String!) {
        user(login: $login) {
            contributionsCollection {
                contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
            }
            pinnedItems(first: 6, types: REPOSITORY) { nodes { ... on Repository { name url description primaryLanguage { name } stargazerCount forkCount } } }
        }
    }"""
    # Try gh CLI first (most reliable)
    out = gh(["gh", "api", "graphql", "-f", f"query={gql}", "-f", "login=Retsumdk"])
    if out:
        try:
            return json.loads(out)
        except Exception:
            pass
    # Fallback to requests
    try:
        resp = requests.post(
            "https://api.github.com/graphql",
            json={"query": gql, "variables": {"login": "Retsumdk"}},
            headers={**GH_HEADERS, "Content-Type": "application/json"},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[WARNING] GraphQL via requests failed: {e}", file=sys.stderr)
    return {}

def get_stats() -> dict:
    user_data = get_user_data()
    repos_data = get_repos_data()

    if not user_data:
        print("[WARNING] Could not fetch user data from gh CLI — repos will be 0!", file=sys.stderr)
    if not repos_data:
        print("[WARNING] Could not fetch repos from gh CLI — repos will be 0!", file=sys.stderr)

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

    gql_result = get_contributions_data()
    gql_data = gql_result.get("data", {}).get("user", {})
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

    # Zo Space dynamic stats
    zo_stats = {}
    try:
        resp = requests.get("https://thebookmaster.zo.space/api/bolt-stats", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            zo_stats["bolt_listings"] = data.get("listings", 0)
            zo_stats["sciel_agents"] = data.get("agents", 0)
    except Exception:
        pass
    try:
        resp2 = requests.get("https://thebookmaster.zo.space/api/aion-stats", timeout=10)
        if resp2.status_code == 200:
            zo_stats["aion_agents"] = resp2.json().get("registered_agents", 0)
    except Exception:
        pass
    try:
        resp3 = requests.get("https://thebookmaster.zo.space/api/game-routes-count", timeout=10)
        if resp3.status_code == 200:
            zo_stats["routes"] = resp3.json().get("count", 0)
    except Exception:
        pass

    print(
        f"[DEBUG] user_data={bool(user_data)}, repos_data={len(repos_data)}, "
        f"repos={total_repos}, stars={stars}, followers={followers}",
        file=sys.stderr
    )

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
