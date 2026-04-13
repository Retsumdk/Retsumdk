#!/usr/bin/env python3
"""
Fetch live GitHub stats for Retsumdk and update README.md dynamically.
Uses GitHub GraphQL API directly with GITHUB_TOKEN.
"""

import subprocess
import re
import os
import json
import urllib.request

def get_stats() -> dict:
    token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
    
    query = """
    {
      viewer {
        contributionsCollection {
          totalCommitContributions
          contributionCalendar {
            totalContributions
          }
        }
        repositories(first: 100, isArchived: false, ownerAffiliations: OWNER) {
          totalCount
        }
        followers {
          totalCount
        }
        following {
          totalCount
        }
      }
    }
    """
    
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    
    v = data.get("data", {}).get("viewer", {})
    return {
        "contributions": v.get("contributionsCollection", {}).get("totalCommitContributions", 0),
        "total_contributions": v.get("contributionsCollection", {}).get("contributionCalendar", {}).get("totalContributions", 0),
        "repos": v.get("repositories", {}).get("totalCount", 0),
        "followers": v.get("followers", {}).get("totalCount", 0),
        "following": v.get("following", {}).get("totalCount", 0),
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