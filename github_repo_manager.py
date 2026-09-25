#!/usr/bin/env python3
"""Concurrent GitHub repository manager with retries, logging and proxy support."""

from __future__ import annotations

import argparse, json, logging, os, random, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

LOG = logging.getLogger("ai-agent-tools")

def setup_logging(level="INFO", log_file="logs/github-manager.log"):
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(threadName)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    console = logging.StreamHandler(sys.stdout); console.setFormatter(fmt); root.addHandler(console)
    fh = logging.FileHandler(log_file, encoding="utf-8"); fh.setFormatter(fmt); root.addHandler(fh)

def load_config(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data.get("repositories"), list):
        raise ValueError("'repositories' must be a list")
    return data

def session_for(token, proxy=None, api_url="https://api.github.com"):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": os.getenv("GITHUB_API_VERSION", "2022-11-28"),
        "User-Agent": "ai-agent-tools-repo-manager/2.0",
    })
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    s.api_url = api_url.rstrip("/")
    return s

def request_with_retry(session, method, url, retries, backoff, timeout, **kwargs):
    retry_statuses = {408, 429, 500, 502, 503, 504}
    for attempt in range(retries + 1):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
            if response.status_code not in retry_statuses or attempt >= retries:
                return response
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else backoff * (2 ** attempt)
            delay += random.uniform(0, min(0.5, backoff))
            LOG.warning("Retryable HTTP %s; retry %s/%s in %.2fs", response.status_code, attempt + 1, retries, delay)
            time.sleep(delay)
        except requests.RequestException as exc:
            if attempt >= retries:
                raise
            delay = backoff * (2 ** attempt) + random.uniform(0, min(0.5, backoff))
            LOG.warning("Network error; retry %s/%s in %.2fs: %s", attempt + 1, retries, delay, exc)
            time.sleep(delay)
    raise RuntimeError("request failed")

def check_response(response):
    if response.status_code >= 400:
        try: detail = response.json()
        except ValueError: detail = response.text
        raise RuntimeError(f"HTTP {response.status_code}: {detail}")
    return response.json() if response.content else None

class JobManager:
    def __init__(self, workers=4, retries=4, backoff=1.5, timeout=30, proxy=None):
        load_dotenv()
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token: raise ValueError("GITHUB_TOKEN is missing")
        self.api_url = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        self.workers = max(1, min(int(workers), 16))
        self.retries = max(0, int(retries))
        self.backoff = max(0.1, float(backoff))
        self.timeout = max(1, int(timeout))
        self.proxy = proxy or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        self.local = threading.local()

    def session(self):
        if not hasattr(self.local, "session"):
            self.local.session = session_for(self.token, self.proxy, self.api_url)
        return self.local.session

    def create_repository(self, config, item, dry_run=False):
        name = item["name"]; description = item.get("description", "")
        private = bool(item.get("private", False))
        organization = config.get("organization"); owner = organization or config.get("owner")
        if not owner or owner == "YOUR_USERNAME":
            raise ValueError("Set 'owner' or 'organization' in the config first.")
        if dry_run:
            LOG.info("[DRY-RUN] Would create %s (private=%s)", name, private)
            return {"name": name, "status": "dry-run"}

        s = self.session()
        existing_url = f"{self.api_url}/repos/{owner}/{name}"
        response = request_with_retry(s, "GET", existing_url, self.retries, self.backoff, self.timeout)
        if response.status_code == 200:
            LOG.info("[SKIP] %s/%s already exists", owner, name)
            return {"name": name, "status": "exists", "url": response.json().get("html_url")}
        if response.status_code != 404: check_response(response)

        url = f"{self.api_url}/orgs/{organization}/repos" if organization else f"{self.api_url}/user/repos"
        payload = {
            "name": name, "description": description, "private": private,
            "has_issues": bool(item.get("has_issues", True)),
            "has_projects": bool(item.get("has_projects", True)),
            "has_wiki": bool(item.get("has_wiki", True)),
            "auto_init": bool(item.get("auto_init", False)),
        }
        response = request_with_retry(s, "POST", url, self.retries, self.backoff, self.timeout, json=payload)
        result = check_response(response)
        repo_url = result.get("html_url")
        LOG.info("[CREATED] %s", repo_url)
        return {"name": name, "status": "created", "url": repo_url}

    def run_config(self, config, dry_run=False):
        settings = config.get("settings", {})
        workers = max(1, min(int(settings.get("workers", self.workers)), 16))
        results = []
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="repo") as pool:
            futures = {pool.submit(self.create_repository, config, item, dry_run): item for item in config["repositories"]}
            for future in as_completed(futures):
                item = futures[future]
                try: results.append(future.result())
                except Exception as exc:
                    LOG.exception("[ERROR] %s: %s", item.get("name", "<unknown>"), exc)
                    results.append({"name": item.get("name", "<unknown>"), "status": "error", "error": str(exc)})
        counts = {}
        for result in results: counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {"total": len(results), "counts": counts, "results": results}

def main():
    parser = argparse.ArgumentParser(description="Concurrent GitHub repository manager")
    parser.add_argument("--config", default="repos.json"); parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int); parser.add_argument("--retries", type=int)
    parser.add_argument("--backoff", type=float); parser.add_argument("--timeout", type=int)
    parser.add_argument("--proxy"); parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    parser.add_argument("--log-file", default=os.getenv("LOG_FILE", "logs/github-manager.log"))
    args = parser.parse_args()
    setup_logging(args.log_level, args.log_file)
    try:
        config = load_config(args.config); settings = config.get("settings", {})
        manager = JobManager(
            workers=args.workers or int(settings.get("workers", 4)),
            retries=args.retries if args.retries is not None else int(settings.get("retries", 4)),
            backoff=args.backoff if args.backoff is not None else float(settings.get("backoff_seconds", 1.5)),
            timeout=args.timeout if args.timeout is not None else int(settings.get("request_timeout", 30)),
            proxy=args.proxy or settings.get("proxy"))
        summary = manager.run_config(config, dry_run=args.dry_run)
        print(json.dumps(summary, indent=2))
        return 1 if summary["counts"].get("error") else 0
    except Exception as exc:
        LOG.exception("Fatal error: %s", exc); return 2

if __name__ == "__main__": raise SystemExit(main())
