#!/usr/bin/env python3
"""
Fetch live GitHub stats for Retsumdk and update README.md dynamically.
Uses REST API + contributions via direct GitHub token auth.
"""

import re
import os
import json
import urllib.request

def get_stats() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    
    # REST API for basic stats
    req = urllib.request.Request(
        "https://api.github.com/users/Retsumdk",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        rest = json.loads(resp.read())
    
    followers = rest.get("followers", 0)
    following = rest.get("following", 0)
    repos = rest.get("public_repos", 0)
    
    # Get total contributions via GraphQL
    query = """
    {
      viewer {
        contributionsCollection {
          totalCommitContributions
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """
    gql_req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(gql_req) as resp:
            gql_data = json.loads(resp.read())
        v = gql_data.get("data", {}).get("viewer", {})
        contributions = v.get("contributionsCollection", {}).get("totalCommitContributions", 0)
        total_contributions = v.get("contributionsCollection", {}).get("contributionCalendar", {}).get("totalContributions", 0)
    except Exception as e:
        print(f"GraphQL error: {e}, falling back to estimate")
        contributions = repos * 6
        total_contributions = repos * 6
    
    return {
        "contributions": contributions,
        "total_contributions": total_contributions,
        "repos": repos,
        "followers": followers,
        "following": following,
    }

def update_readme(stats: dict):
    readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()

    content = re.sub(
        r"!\[Contributions\]\(https://img\.shields\.io/badge/Contributions-\d+-blue[^)]*\)",
        f"![Contributions](https://img.shields.io/badge/Contributions-{stats['total_contributions']}-blue?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Repos\]\(https://img\.shields\.io/badge/Repos-\d+-2ea44f[^)]*\)",
        f"![Repos](https://img.shields.io/badge/Repos-{stats['repos']}-2ea44f?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Followers\]\(https://img\.shields\.io/badge/Followers-\d+-ffc107[^)]*\)",
        f"![Followers](https://img.shields.io/badge/Followers-{stats['followers']}-ffc107?style=flat-square)",
        content
    )
    content = re.sub(
        r"!\[Following\]\(https://img\.shields\.io/badge/Following-\d+-9c27b0[^)]*\)",
        f"![Following](https://img.shields.io/badge/Following-{stats['following']}-9c27b0?style=flat-square)",
        content
    )

    with open(readme_path, "w") as f:
        f.write(content)

    print(f"Updated stats: {stats}")

if __name__ == "__main__":
    stats = get_stats()
    update_readme(stats)