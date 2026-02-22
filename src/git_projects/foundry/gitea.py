from __future__ import annotations

import re

import httpx

from git_projects.config import FoundryConfig
from git_projects.foundry import RemoteRepo

_USER_AGENT = "git-projects/0.1"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)


def list_repos(config: FoundryConfig, clone_url_format: str = "ssh") -> list[RemoteRepo]:
    """Fetch all accessible repos from the Gitea API with pagination."""
    if not config.token:
        raise ValueError("Gitea token is not set.")
    if not config.url:
        raise ValueError("Gitea url is not set.")

    headers = {
        "Authorization": f"token {config.token}",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
    }
    base_url = config.url.rstrip("/")
    url: str | None = f"{base_url}/api/v1/user/repos?limit=50&page=1"
    repos: list[RemoteRepo] = []

    with httpx.Client(headers=headers, timeout=_TIMEOUT) as client:
        while url:
            response = client.get(url)
            response.raise_for_status()
            for item in response.json():
                repos.append(
                    RemoteRepo(
                        name=item["name"],
                        repo_url=item["html_url"],
                        clone_url=item["ssh_url"]
                        if clone_url_format == "ssh"
                        else item["clone_url"],
                        pushed_at=item["updated_at"],
                        default_branch=item["default_branch"],
                        visibility="private" if item["private"] else "public",
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
