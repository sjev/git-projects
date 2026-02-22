from __future__ import annotations

import re

import httpx

from git_projects.foundry import RemoteRepo
from git_projects.registry import FoundryConfig

_USER_AGENT = "git-projects/0.1"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)


def list_repos(config: FoundryConfig) -> list[RemoteRepo]:
    """Fetch all owned repos from the GitHub API with pagination."""
    if not config.token:
        raise ValueError("GitHub token is not set.")

    headers = {
        "Authorization": f"Bearer {config.token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": _USER_AGENT,
    }
    url: str | None = (
        f"{config.url}/user/repos?affiliation=owner&sort=pushed&direction=desc&per_page=100"
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
                        clone_url=item["clone_url"],
                        pushed_at=item["pushed_at"],
                        default_branch=item["default_branch"],
                        visibility=item["visibility"],
                        description=item["description"] or "",
                    )
                )
            url = _next_url(response.headers.get("Link", ""))

    return repos


def _next_url(link_header: str) -> str | None:
    """Parse the 'next' URL from a GitHub Link response header."""
    for part in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="next"', part.strip())
        if match:
            return match.group(1)
    return None
