"""GitHub Pull Request URL detection and resolution."""

import json
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

from grv.constants import (
    ERR_GH_NOT_FOUND,
    ERR_INVALID_PR_URL,
    ERR_PR_PARSE_FAILED,
    GH_PR_JSON_FIELDS,
    GITHUB_HOST,
    GITHUB_PR_PATH_PATTERN,
    GITHUB_REPO_URL_FMT,
)


@dataclass
class PRInfo:
    """Information resolved from a GitHub PR."""

    repo_url: str
    branch: str


def is_pr_url(url: str) -> bool:
    """Check if a URL is a GitHub PR URL."""
    # Handle schemeless URLs
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.netloc != GITHUB_HOST:
        return False

    return bool(re.match(GITHUB_PR_PATH_PATTERN, parsed.path))


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL into (owner, repo, pr_number)."""
    # Handle schemeless URLs
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    match = re.match(GITHUB_PR_PATH_PATTERN, parsed.path)

    if not match:
        raise ValueError(ERR_INVALID_PR_URL)

    owner, repo, pr_num = match.groups()
    return owner, repo, int(pr_num)


def resolve_pr(url: str) -> PRInfo:
    """Resolve a PR URL to repo URL and branch name using gh CLI."""
    # Normalize URL for gh CLI
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Strip fragment if present
    url = url.split("#")[0]

    cmd = ["gh", "pr", "view", url, "--json", GH_PR_JSON_FIELDS]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(ERR_GH_NOT_FOUND) from exc

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    try:
        data = json.loads(result.stdout)
        owner = data["headRepositoryOwner"]["login"]
        repo = data["headRepository"]["name"]
        repo_url = GITHUB_REPO_URL_FMT.format(owner=owner, repo=repo)
        branch = data["headRefName"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(ERR_PR_PARSE_FAILED) from exc

    return PRInfo(repo_url=repo_url, branch=branch)
