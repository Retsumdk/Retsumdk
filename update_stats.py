#!/usr/bin/env python3
"""
Fetch live GitHub + ecosystem stats for Retsumdk and update README.md dynamically.
Covers: contributions, repos, stars, forks, languages, streaks, top repos,
and live SCIEL/BOLT/AION stats from thebookmaster.zo.space.

Uses requests with GITHUB_TOKEN for all GitHub API calls.
Falls back to gh CLI for user/repo counts if requests fail.
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

def gh_fallback(cmd: list[str]) -> str:
    """Run a gh CLI command, return stdout. Only use as fallback."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""

def gh_graphql(query: str, variables: dict = None) -> dict:
    """Run a GraphQL query via gh api."""
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={query}",
    ]
    if variables:
        for k, v in variables.items():
            cmd += ["-f", f"{k}={v}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def gh_rest(endpoint: str) -> dict:
    """Run a REST GET via gh api."""
    result = subprocess.run(
        ["gh", "api", f"repos/Retsumdk/Retsumdk/{endpoint}"],
        capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)

def gh_user() -> dict:
    """Get current user info via gh api."""
    result = subprocess.run(
        ["gh", "api", "user"],
        capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)

def gh_list_repos() -> list:
    """List all repos (public + private) for Retsumdk."""
    result = subprocess.run(
        ["gh", "api", "user/repos", "--paginate", "--jq", ".[] | {name, private, stargazers_count, forks_count, language, description}"],
        capture_output=True, text=True, check=True
    )
    repos = []
    for line in result.stdout.strip().split("\n"):
        if line:
            repos.append(json.loads(line))
    return repos

def get_stats() -> dict:
    # ── Primary: requests-based GitHub API ──────────────────────────────────
    user_data = {}
    repos_data = []

    try:
        user_resp = requests.get("https://api.github.com/user", headers=GH_HEADERS, timeout=15)
        if user_resp.status_code == 200:
            user_data = user_resp.json()
    except Exception as e:
        print(f"[WARNING] requests.get /user failed: {e}", file=sys.stderr)

    try:
        repos_resp = requests.get(
            "https://api.github.com/user/repos?per_page=100&sort=updated",
            headers=GH_HEADERS, timeout=15
        )
        if repos_resp.status_code == 200:
            repos_data = repos_resp.json()
    except Exception as e:
        print(f"[WARNING] requests.get /user/repos failed: {e}", file=sys.stderr)

    # ── Fallback: gh CLI if requests returned empty data ───────────────────
    if not user_data or not repos_data:
        print("[INFO] Falling back to gh CLI for GitHub API calls", file=sys.stderr)
        gh_user_out = gh_fallback(["gh", "api", "user"])
        if gh_user_out:
            try:
                user_data = json.loads(gh_user_out)
            except Exception:
                pass

        if not repos_data:
            gh_repos_out = gh_fallback([
                "gh", "api", "user/repos", "--paginate", "--jq",
                ".[] | {name, private, stargazers_count, forks_count, language, description}"
            ])
            for line in gh_repos_out.strip().split("\n"):
                if line:
                    try:
                        repos_data.append(json.loads(line))
                    except Exception:
                        pass

    public_repos = user_data.get("public_repos", 0)
    total_private_repos = user_data.get("total_private_repos", 0)
    total_repos = public_repos + total_private_repos
    followers = user_data.get("followers", 0)
    following = user_data.get("following", 0)

    # Filter out private repos from stars/forks count
    public_only = [r for r in repos_data if not r.get("private")]
    stars = sum(r.get("stargazers_count", 0) for r in public_only)
    total_forks = sum(r.get("forks_count", 0) for r in public_only)

    langs = {}
    for r in repos_data:
        lang = r.get("language")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1

    top_repos = sorted(repos_data, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:6]

    # Contribution graph via GraphQL
    gql_query = """query($login: String!) {
        user(login: $login) {
            contributionsCollection {
                contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
            }
            pinnedItems(first: 6, types: REPOSITORY) { nodes { ... on Repository { name url description primaryLanguage { name } stargazerCount forkCount } } }
        }
    }"""
    gql_result = gh_graphql(gql_query, {"login": "Retsumdk"})
    gql_data = gql_result.get("data", {}).get("user", {})
    pinned_repos = gql_data.get("pinnedItems", {}).get("nodes", [])

    cal = gql_data.get("contributionsCollection", {}).get("contributionCalendar", {})
    total_contributions = cal.get("totalContributions", 0)
    weeks = cal.get("weeks", [])
    graph_lines = []
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
        import requests as _req
        resp = _req.get("https://thebookmaster.zo.space/api/bolt-stats", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            zo_stats["bolt_listings"] = data.get("listings", 0)
            zo_stats["sciel_agents"] = data.get("agents", 0)
    except Exception:
        pass

    try:
        import requests as _req2
        resp2 = _req2.get("https://thebookmaster.zo.space/api/aion-stats", timeout=10)
        if resp2.status_code == 200:
            data2 = resp2.json()
            zo_stats["aion_agents"] = data2.get("registered_agents", 0)
    except Exception:
        pass

    try:
        import requests as _req3
        resp3 = _req3.get("https://thebookmaster.zo.space/api/game-routes-count", timeout=10)
        if resp3.status_code == 200:
            zo_stats["routes"] = resp3.json().get("count", 0)
    except Exception:
        pass

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
    stats = get_stats()
    update_readme(stats)