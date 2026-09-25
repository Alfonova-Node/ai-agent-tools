# AI Agent Tools

A small Python toolkit for legitimate GitHub automation and AI-agent workflows.

## Features

- Create multiple repositories under a GitHub account or organization you control.
- Configure repository visibility and initialization.
- Read repository configuration from JSON/YAML-like data.
- Dry-run mode before making changes.
- Optional per-repository descriptions.
- Uses the official GitHub REST API.

> This project is intended for managing repositories you legitimately control. It does not create or automate large numbers of GitHub user accounts, bypass email verification, or evade GitHub anti-abuse controls.

## Quick start

### 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Copy `.env.example` to `.env` and set a GitHub token with the minimum permissions required for the repositories you manage.

```bash
cp .env.example .env
```

### 3. Define repositories

Edit `repos.json`:

```json
{
  "owner": "YOUR_USERNAME",
  "organization": null,
  "repositories": [
    {
      "name": "agent-project-01",
      "description": "AI agent project",
      "private": false
    },
    {
      "name": "agent-project-02",
      "description": "Automation project",
      "private": true
    }
  ]
}
```

### 4. Dry run

```bash
python github_repo_manager.py --config repos.json --dry-run
```

### 5. Create repositories

```bash
python github_repo_manager.py --config repos.json
```

The script skips repositories that already exist.

## Notes

Use a fine-grained GitHub token and grant only the repository/account permissions needed for your own workflow. Never commit `.env` or a real token.
