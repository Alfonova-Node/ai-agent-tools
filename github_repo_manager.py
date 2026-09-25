#!/usr/bin/env python3
"""Create and manage repositories you are authorized to manage.

This tool intentionally manages repositories, not GitHub user accounts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


def api_request(session, method, url, **kwargs):
    response = session.request(method, url, timeout=30, **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise RuntimeError(f"{method} {url} -> HTTP {response.status_code}: {detail}")
    if not response.content:
        return None
    return response.json()


def repository_url(owner: str, name: str) -> str:
    return f"https://api.github.com/repos/{owner}/{name}"


def create_repository(session, config, item, dry_run=False):
    name = item["name"]
    description = item.get("description", "")
    private = bool(item.get("private", False))
    organization = config.get("organization")
    owner = organization or config.get("owner")

    if not owner or owner == "YOUR_USERNAME":
        raise ValueError("Set 'owner' or 'organization' in repos.json first.")

    if dry_run:
        scope = f"organization '{organization}'" if organization else f"user '{owner}'"
        print(f"[DRY-RUN] Would create {name} in {scope} (private={private})")
        return

    if organization:
        url = f"https://api.github.com/orgs/{organization}/repos"
    else:
        url = "https://api.github.com/user/repos"

    existing = session.get(repository_url(owner, name), timeout=30)
    if existing.status_code == 200:
        print(f"[SKIP] {owner}/{name} already exists")
        return
    if existing.status_code not in (404,):
        raise RuntimeError(
            f"Checking {owner}/{name} failed: HTTP {existing.status_code}: {existing.text}"
        )

    payload = {
        "name": name,
        "description": description,
        "private": private,
        "has_issues": True,
        "has_projects": True,
        "has_wiki": True,
        "auto_init": False,
    }

    result = api_request(session, "POST", url, json=payload)
    print(f"[CREATED] {result['html_url']}")


def main():
    parser = argparse.ArgumentParser(description="Bulk-create GitHub repositories you control.")
    parser.add_argument("--config", default="repos.json", help="Path to repository JSON config")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without creating repositories",
    )
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    api_url = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")

    if not token:
        print("GITHUB_TOKEN is missing. Put it in .env or your environment.", file=sys.stderr)
        return 2

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    repositories = config.get("repositories", [])

    if not isinstance(repositories, list):
        print("'repositories' must be a JSON list.", file=sys.stderr)
        return 2

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-agent-tools-repo-manager",
        }
    )

    # Keep the configured API URL for future enterprise GitHub deployments.
    session.base_url = api_url  # informational; requests uses absolute URLs below.

    failures = 0
    for item in repositories:
        try:
            create_repository(session, config, item, args.dry_run)
        except Exception as exc:
            failures += 1
            print(f"[ERROR] {item.get('name', '<unknown>')}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
