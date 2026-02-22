from __future__ import annotations

from collections.abc import Callable
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
    on_foundry_start: Callable[[str], None] | None = None,
) -> list[RemoteRepo]:
    """Fetch repos from configured foundries.

    Returns a flat list of repos sorted by pushed_at ascending (oldest first).
    Raises ValueError if foundry_name is given but not found.
    Lets httpx.HTTPStatusError and ValueError (missing token) propagate.
    """
    foundries = cfg.foundries
    if foundry_name:
        foundries = [f for f in foundries if f.name == foundry_name]
        if not foundries:
            raise ValueError(f"No foundry named '{foundry_name}' in config.")

    cutoff = datetime.now(timezone.utc) - RECENT_CUTOFF
    all_repos: list[RemoteRepo] = []

    for foundry_config in foundries:
        if foundry_config.type == "github":
            list_repos = github.list_repos
        elif foundry_config.type == "gitea":
            list_repos = gitea.list_repos
        elif foundry_config.type == "gitlab":
            list_repos = gitlab.list_repos
        else:
            continue

        if on_foundry_start:
            on_foundry_start(foundry_config.name)

        repos = list_repos(foundry_config)

        if not show_all:
            repos = [
                r
                for r in repos
                if datetime.fromisoformat(r.pushed_at.replace("Z", "+00:00")) >= cutoff
            ]

        all_repos.extend(repos)

    all_repos.sort(key=lambda r: r.pushed_at)
    return all_repos


def track_project(cfg: Config, clone_url: str, path: str | None = None) -> Project:
    """Add a project to tracking and save config.

    Raises ValueError if already tracked.
    """
    if any(p.clone_url == clone_url for p in cfg.projects):
        raise ValueError(f"Already tracking: {clone_url}")

    if path is not None:
        parsed_name = clone_url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]
        project = Project(clone_url=clone_url, name=parsed_name, path=path)
    else:
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
