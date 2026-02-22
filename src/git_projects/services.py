from __future__ import annotations

from datetime import datetime, timedelta, timezone

from git_projects import config
from git_projects.config import Config, Project
from git_projects.foundry import RemoteRepo, gitea, github, gitlab

RECENT_CUTOFF = timedelta(days=180)


def fetch_repos(
    cfg: Config,
    foundry_name: str | None = None,
    *,
    show_all: bool = False,
) -> dict[str, list[RemoteRepo]]:
    """Fetch repos from configured foundries.

    Returns a mapping of foundry name to list of repos.
    Raises ValueError if foundry_name is given but not found.
    Lets httpx.HTTPStatusError and ValueError (missing token) propagate.
    """
    foundries = cfg.foundries
    if foundry_name:
        foundries = [f for f in foundries if f.name == foundry_name]
        if not foundries:
            raise ValueError(f"No foundry named '{foundry_name}' in config.")

    cutoff = datetime.now(timezone.utc) - RECENT_CUTOFF
    result: dict[str, list[RemoteRepo]] = {}

    for foundry_config in foundries:
        if foundry_config.type == "github":
            repos = github.list_repos(foundry_config)
        elif foundry_config.type == "gitea":
            repos = gitea.list_repos(foundry_config)
        elif foundry_config.type == "gitlab":
            repos = gitlab.list_repos(foundry_config)
        else:
            continue

        if not show_all:
            repos = [
                r
                for r in repos
                if datetime.fromisoformat(r.pushed_at.replace("Z", "+00:00")) >= cutoff
            ]

        repos.sort(key=lambda r: r.pushed_at, reverse=True)
        result[foundry_config.name] = repos

    return result


def track_project(cfg: Config, clone_url: str) -> Project:
    """Add a project to tracking and save config.

    Raises ValueError if already tracked.
    """
    if any(p.clone_url == clone_url for p in cfg.projects):
        raise ValueError(f"Already tracking: {clone_url}")

    project = config.derive_project(clone_url, cfg.clone_root)
    cfg.projects.append(project)
    config.save_config(cfg)
    return project


def untrack_project(cfg: Config, name: str) -> None:
    """Remove a project from tracking and save config.

    Raises ValueError if not found.
    """
    before = len(cfg.projects)
    cfg.projects = [p for p in cfg.projects if p.name != name]
    if len(cfg.projects) == before:
        raise ValueError(f"No project named '{name}' found.")

    config.save_config(cfg)
