#!/usr/bin/env python3
"""
repo_health.py

Small CLI tool to check a GitHub repository for common "health" files:
README, LICENSE, CI workflow (GitHub Actions), CODE_OF_CONDUCT, CONTRIBUTING,
ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE.

Usage:
    python repo_health.py owner/repo
Examples:
    python repo_health.py tensorflow/tensorflow
    python repo_health.py psf/requests --format json

Notes:
    - Works for public repositories.
    - For rate limits or private repos you may add a GITHUB_TOKEN env var (optional).
    - Minimal dependencies: tries to use requests; falls back to urllib.
"""

from __future__ import annotations
import os
import sys
import json
import argparse
from typing import Dict, Any, Optional, List

# Try to import requests; if unavailable, we'll fall back to urllib
try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    import urllib.request as _urllib
    import urllib.error as _urllib_err
    _HAS_REQUESTS = False

GITHUB_API = "https://api.github.com"

DEFAULT_TARGETS = [
    {"path": "README.md", "label": "README"},
    {"path": "README", "label": "README (no ext)"},
    {"path": "LICENSE", "label": "LICENSE"},
    {"path": "LICENSE.md", "label": "LICENSE (md)"},
    {"path": ".github/CONTRIBUTING.md", "label": "CONTRIBUTING (.github)"},
    {"path": "CONTRIBUTING.md", "label": "CONTRIBUTING"},
    {"path": ".github/CODE_OF_CONDUCT.md", "label": "CODE_OF_CONDUCT (.github)"},
    {"path": "CODE_OF_CONDUCT.md", "label": "CODE_OF_CONDUCT"},
    {"path": ".github/ISSUE_TEMPLATE/bug_report.md", "label": "ISSUE_TEMPLATE (bug_report)"},
    {"path": ".github/ISSUE_TEMPLATE", "label": "ISSUE_TEMPLATE (dir)"},
    {"path": ".github/pull_request_template.md", "label": "PULL_REQUEST_TEMPLATE (.github)"},
    {"path": "pull_request_template.md", "label": "PULL_REQUEST_TEMPLATE"},
    {"path": ".github/workflows", "label": "GitHub Actions (workflows)"},
    {"path": ".travis.yml", "label": "Travis CI config"},
    {"path": "azure-pipelines.yml", "label": "Azure Pipelines"},
]


def get_headers() -> Dict[str, str]:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def fetch_github_api(path: str) -> Optional[Dict[str, Any]]:
    """
    Fetch from GitHub API. Return parsed JSON or None on failure.
    """
    url = f"{GITHUB_API}{path}"
    headers = get_headers()
    if _HAS_REQUESTS:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception:
            return None
    else:
        try:
            req = _urllib.Request(url, headers=headers)
            with _urllib.urlopen(req, timeout=10) as resp:
                data = resp.read()
                return json.loads(data.decode("utf-8"))
        except Exception:
            return None


def check_path_exists(owner: str, repo: str, path: str) -> bool:
    """
    Use the "contents" endpoint to check for file/directory existence:
    GET /repos/{owner}/{repo}/contents/{path}
    """
    api_path = f"/repos/{owner}/{repo}/contents/{path}"
    resp = fetch_github_api(api_path)
    return resp is not None


def check_repo(owner_repo: str, extra_paths: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Main checker: returns dict with results.
    """
    if "/" not in owner_repo:
        raise ValueError("Specify repository as owner/repo")
    owner, repo = owner_repo.split("/", 1)
    checks = (DEFAULT_TARGETS + (extra_paths or []))
    results = {"repo": f"{owner}/{repo}", "checked": [], "found": [], "missing": []}

    # First check the repo exists
    repo_api = f"/repos/{owner}/{repo}"
    repo_meta = fetch_github_api(repo_api)
    if not repo_meta:
        results["error"] = f"Repository {owner}/{repo} not found or API unavailable."
        return results

    results["description"] = repo_meta.get("description")
    results["private"] = repo_meta.get("private", False)
    results["archived"] = repo_meta.get("archived", False)
    results["stargazers_count"] = repo_meta.get("stargazers_count", 0)
    results["forks_count"] = repo_meta.get("forks_count", 0)

    for t in checks:
        path = t["path"]
        label = t.get("label", path)
        exists = check_path_exists(owner, repo, path)
        results["checked"].append({"path": path, "label": label, "exists": exists})
        if exists:
            results["found"].append(label)
        else:
            results["missing"].append(label)

    # Quick suggestions
    suggestions = []
    if "CONTRIBUTING" not in " ".join(results["found"]).upper():
        suggestions.append("Add CONTRIBUTING.md to explain contribution process.")
    if "CODE_OF_CONDUCT" not in " ".join(results["found"]).upper():
        suggestions.append("Add a Code of Conduct to welcome contributors.")
    if not any("GitHub Actions" in f for f in results["found"]):
        suggestions.append("Add CI workflows (e.g., GitHub Actions) to run tests on PRs.")
    if "LICENSE" not in " ".join(results["found"]).upper():
        suggestions.append("Add a LICENSE file so others know how they can use your code.")

    results["suggestions"] = suggestions
    return results


def pretty_print(res: Dict[str, Any]) -> None:
    print("=" * 60)
    print(f"Repository: {res.get('repo')}")
    if res.get("description"):
        print(f"Description: {res['description']}")
    print(f"Private: {res.get('private')}, Archived: {res.get('archived')}")
    print(f"Stars: {res.get('stargazers_count')}, Forks: {res.get('forks_count')}")
    print("-" * 60)
    print("Found:")
    for f in res.get("found", []):
        print(f"   {f}")
    print("\nMissing:")
    for m in res.get("missing", []):
        print(f"   {m}")
    if res.get("suggestions"):
        print("\nSuggestions:")
        for s in res["suggestions"]:
            print(f"  * {s}")
    if res.get("error"):
        print("\nERROR:", res["error"])
    print("=" * 60)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check GitHub repo for health files.")
    parser.add_argument("repo", help="Repository in owner/repo format")
    parser.add_argument("--format", choices=["pretty", "json"], default="pretty", help="Output format")
    parser.add_argument("--extra", nargs="*", help="Extra paths to check (relative paths)", default=[])
    args = parser.parse_args(argv)

    extra = [{"path": p, "label": p} for p in args.extra] if args.extra else None
    try:
        result = check_repo(args.repo, extra_paths=extra)
    except ValueError as e:
        print("Error:", e, file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        pretty_print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
