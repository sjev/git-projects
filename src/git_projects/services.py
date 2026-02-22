from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from git_projects import config
from git_projects.config import Config, Project
from git_projects.foundry import RemoteRepo, gitea, github, gitlab
from git_projects.gitops import GitError, clone_repo, is_dirty, pull_repo, push_repo

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

        repos = list_repos(foundry_config, cfg.clone_url_format)

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


@dataclass
class SyncResult:
    cloned: list[str] = field(default_factory=list)
    synced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errored: list[tuple[str, str]] = field(default_factory=list)


def sync_projects(
    projects: list[Project],
    on_project: Callable[[str, str], None] | None = None,
) -> SyncResult:
    """Clone missing repos and pull+push existing ones.

    Calls on_project(name, status_message) for each project as it is processed.
    Dirty repos are skipped; git errors are recorded and processing continues.
    """
    result = SyncResult()

    for project in projects:
        expanded = str(Path(project.path).expanduser())

        if not Path(expanded).exists():
            try:
                clone_repo(project.clone_url, project.path)
                result.cloned.append(project.name)
                if on_project:
                    on_project(project.name, "cloned")
            except GitError as exc:
                result.errored.append((project.name, str(exc)))
                if on_project:
                    on_project(project.name, f"error: {exc}")
            continue

        if is_dirty(project.path):
            result.skipped.append(project.name)
            if on_project:
                on_project(project.name, "skipped (dirty)")
            continue

        try:
            pull_repo(project.path)
            push_repo(project.path)
            result.synced.append(project.name)
            if on_project:
                on_project(project.name, "synced")
        except GitError as exc:
            result.errored.append((project.name, str(exc)))
            if on_project:
                on_project(project.name, f"error: {exc}")

    return result
