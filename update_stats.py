#!/usr/bin/env python3
"""
Fetch live GitHub stats for Retsumdk and update README.md dynamically.
Covers: contributions, repos, followers, following, stars, forks, languages.
"""
import re, os, json, urllib.request
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

def get_profile_stats(token: str) -> dict:
    user = gh_get(f"{GH_API}/users/Retsumdk", token)
    return {
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "public_repos": user.get("public_repos", 0),
        "public_gists": user.get("public_gists", 0),
    }

def get_contributions(token: str) -> int:
    query = """
    {
      viewer {
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """
    req = urllib.request.Request(
        GRAPHQL_API,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except Exception as e:
        print(f"GraphQL error: {e}")
        return 0

def get_repo_stats(token: str) -> dict:
    repos = gh_get(f"{GH_API}/users/Retsumdk/repos?sort=updated&per_page=100&type=public", token)
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    langs = defaultdict(int)
    for r in repos:
        lang = r.get("language")
        if lang:
            langs[lang] += 1
    top_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:6]
    top_repo_lines = []
    for r in top_repos:
        stars = r.get("stargazers_count", 0)
        forks = r.get("forks_count", 0)
        name = r.get("name", "")
        desc = r.get("description", "") or ""
        lang = r.get("language", "Code") or "Code"
        lang_color = LANG_COLORS.get(lang, "grey")
        top_repo_lines.append(
            f"| [{name}](https://github.com/Retsumdk/{name}) | "
            f"{desc[:70]} | "
            f"⭐ {stars}&nbsp;🍴 {forks} | "
            f"`{lang}` |"
        )
    return {
        "total_stars": total_stars,
        "total_forks": total_forks,
        "languages": dict(sorted(langs.items(), key=lambda x: x[1], reverse=True)),
        "top_repo_lines": top_repo_lines,
    }

LANG_COLORS = {
    "TypeScript": "3178C6",
    "Python": "3776AB",
    "JavaScript": "F7DF1E",
    "Go": "00ADD8",
    "Rust": "DEA584",
    "Java": "B07219",
    "C#": "178600",
    "C++": "F34B7D",
    "C": "555555",
    "Ruby": "CC342D",
    "PHP": "4F5D95",
    "Swift": "F05138",
    "Kotlin": "A97BFF",
    "Shell": "89E051",
    "HTML": "E34C26",
    "CSS": "563D7C",
    "Vue": "41B883",
    "Scala": "C22D40",
    "Elixir": "6E4A7E",
    "Haskell": "5E5086",
}

LANG_BADGE_COLORS = {
    "TypeScript": "3178C6",
    "Python": "3776AB",
    "JavaScript": "F7DF1E",
    "Go": "00ADD8",
    "Rust": "DEA584",
    "Java": "B07219",
    "C#": "178600",
    "C++": "F34B7D",
    "Ruby": "CC342D",
    "PHP": "4F5D95",
    "Swift": "F05138",
    "Kotlin": "A97BFF",
    "Shell": "89E051",
    "Scala": "C22D40",
}

def build_language_badges(languages: dict) -> str:
    badges = []
    for lang, count in list(languages.items())[:8]:
        color = LANG_BADGE_COLORS.get(lang, "808080")
        badges.append(
            f"![{lang}](https://img.shields.io/badge/{lang.replace('+','%2B')}-{count}-{color}?style=flat-square&logo={lang.lower().replace('+','%2B')}&logoColor=white)"
        )
    return "  ".join(badges)

def update_readme(stats: dict, profile: dict, contributions: int, repo_stats: dict):
    readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()

    def repl(label, value, color=None):
        pat = rf"(!\[{re.escape(label)}\]\(https://img\.shields\.io/badge/{re.escape(label)}-)(\d+)(-[^\)]+\))"
        repl_with = f"![{label}](https://img.shields.io/badge/{label}-{value}"
        if color:
            repl_with += f"-{color}"
        repl_with += f"?style=flat-square)"
        return re.sub(pat, repl_with, content)

    content = repl("Contributions", stats.get("total_contributions", contributions))
    content = repl("Repos", profile["public_repos"])
    content = repl("Stars", repo_stats["total_stars"], "2ea44f")
    content = repl("Forks", repo_stats["total_forks"], "2ea44f")
    content = repl("Followers", profile["followers"], "ffc107")
    content = repl("Following", profile["following"], "9c27b0")

    lang_badges = build_language_badges(repo_stats["languages"])
    content = re.sub(
        r"(\[comment\]: # LANGUAGE BADGES START[\s\S]*?\[comment\]: # LANGUAGE BADGES END)",
        f"[comment]: # LANGUAGE BADGES START\n{lang_badges}\n[comment]: # LANGUAGE BADGES END",
        content
    )

    top_table = "| Repository | Description | Stars / Forks | Language |\n|---|---|---|---|\n" + "\n".join(repo_stats["top_repo_lines"])
    content = re.sub(
        r"(\| Repository \| Description \| Stars / Forks \| Language \|\n\|---\|---\|---\|---\|\n)([\s\S]*?)(?=\n## |\n---)",
        top_table + "\n",
        content
    )

    with open(readme_path, "w") as f:
        f.write(content)

    print(f"Stats updated:")
    print(f"  Contributions: {contributions}")
    print(f"  Public Repos:   {profile['public_repos']}")
    print(f"  Followers:     {profile['followers']}")
    print(f"  Following:     {profile['following']}")
    print(f"  Total Stars:   {repo_stats['total_stars']}")
    print(f"  Total Forks:   {repo_stats['total_forks']}")
    print(f"  Languages:     {list(repo_stats['languages'].keys())[:5]}")

if __name__ == "__main__":
    token = os.environ.get("GITHUB_TOKEN", "")
    profile = get_profile_stats(token)
    contributions = get_contributions(token)
    repo_stats = get_repo_stats(token)
    stats = {
        "total_contributions": contributions,
        "profile": profile,
        "repo_stats": repo_stats,
    }
    update_readme(stats, profile, contributions, repo_stats)
