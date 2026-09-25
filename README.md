# AI Agent Tools

Practical Python toolkit for managing GitHub repositories you are authorized to manage.

## Features

- Local Web UI
- Parallel repository operations with configurable workers
- Retry with exponential backoff and Retry-After handling
- Console and file logging
- Optional single HTTP(S) proxy
- Dry-run mode
- Existing-repository detection
- JSON job summaries

GitHub's REST API supports repository creation for authenticated users and organizations when the account/token has sufficient permissions. GitHub also documents rate limits and API best practices. citeturn0search7turn0search8

> This project manages repositories, not GitHub user accounts. It does not automate account farming, bypass email verification, rotate proxies to evade rate limits, or circumvent anti-abuse controls.

## Install

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env

Set GITHUB_TOKEN in .env. Prefer a fine-grained token with only the permissions required for your workflow. citeturn0search7

## CLI

Dry run:

    python github_repo_manager.py --config repos.json --dry-run

Real run:

    python github_repo_manager.py --config repos.json --workers 4 --retries 4

Optional single proxy:

    python github_repo_manager.py --proxy http://127.0.0.1:8080

The proxy is a normal transport option. Do not use proxy rotation to evade GitHub limits or abuse controls.

## Web UI

Start it with:

    ./run_web.sh

Open http://127.0.0.1:8080.

The UI accepts repository JSON, worker count, retry count, optional proxy, and dry-run mode. The GitHub token stays in the server environment and is not entered into the browser.

For a VPS, keep the UI on localhost and expose it through an authenticated reverse proxy/TLS layer rather than exposing Flask's development server directly.

## Logging

Default file: logs/github-manager.log

Set LOG_LEVEL and LOG_FILE in .env to change logging.

## Configuration

See config.example.json for workers, retries, backoff, timeout, proxy and repository settings.

The tool parallelizes independent repository operations only. It does not parallelize conflicting file-content writes; GitHub documents that concurrent content updates can conflict. citeturn0search4

## Security

- Never commit .env or real tokens.
- Keep concurrency moderate because GitHub API usage is rate-limited. citeturn0search8
- Use a fine-grained token with minimum permissions.
- Keep the Web UI behind authentication if exposed beyond localhost.
