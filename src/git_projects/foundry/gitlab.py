from __future__ import annotations

import re

import httpx

from git_projects.config import FoundryConfig
from git_projects.foundry import RemoteRepo

_USER_AGENT = "git-projects/0.1"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
_DEFAULT_URL = "https://gitlab.com"


def list_repos(config: FoundryConfig) -> list[RemoteRepo]:
    """Fetch all owned repos from the GitLab API with pagination."""
    if not config.token:
        raise ValueError("GitLab token is not set.")

    headers = {
        "Authorization": f"Bearer {config.token}",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
    }
    base_url = (config.url or _DEFAULT_URL).rstrip("/")
    url: str | None = (
        f"{base_url}/api/v4/projects?owned=true&order_by=last_activity_at&sort=desc&per_page=100"
    )
    repos: list[RemoteRepo] = []

    with httpx.Client(headers=headers, timeout=_TIMEOUT) as client:
        while url:
            response = client.get(url)
            response.raise_for_status()
            for item in response.json():
                repos.append(
                    RemoteRepo(
                        name=item["name"],
                        clone_url=item["ssh_url_to_repo"],
                        pushed_at=item["last_activity_at"],
                        default_branch=item.get("default_branch") or "",
                        visibility=item["visibility"],
                        description=item["description"] or "",
                    )
                )
            url = _next_url(response.headers.get("Link", ""))

    return repos


def _next_url(link_header: str) -> str | None:
    """Parse the 'next' URL from a Link response header."""
    for part in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="next"', part.strip())
        if match:
            return match.group(1)
    return None
