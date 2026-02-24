from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from git_projects import config, index
from git_projects.config import Config, Project
from git_projects.foundry import RemoteRepo, gitea, github, gitlab
from git_projects.gitops import GitError, clone_repo, is_dirty, pull_repo, push_repo


def fetch_repos(
    cfg: Config,
    foundry_name: str | None = None,
) -> list[RemoteRepo]:
    """Fetch repos from configured foundries concurrently, save to local index.

    Returns all repos sorted by pushed_at ascending (oldest first).
    Raises ValueError if foundry_name is given but not found.
    Lets httpx.HTTPStatusError and ValueError (missing token) propagate.
    """
    foundries = cfg.foundries
    if foundry_name:
        foundries = [f for f in foundries if f.name == foundry_name]
        if not foundries:
            raise ValueError(f"No foundry named '{foundry_name}' in config.")

    lock = threading.Lock()
    all_repos: list[RemoteRepo] = []

    def _fetch_one(fc: config.FoundryConfig) -> None:
        if fc.type == "github":
            list_fn = github.list_repos
        elif fc.type == "gitlab":
            list_fn = gitlab.list_repos
        elif fc.type == "gitea":
            list_fn = gitea.list_repos
        else:
            return
        repos = list_fn(fc, cfg.clone_url_format)
        with lock:
            all_repos.extend(repos)

    with ThreadPoolExecutor(max_workers=max(1, len(foundries))) as executor:
        futures = [executor.submit(_fetch_one, fc) for fc in foundries]
        for future in as_completed(futures):
            future.result()  # re-raise any API or token errors

    all_repos.sort(key=lambda r: r.pushed_at)
    index.save_index(all_repos)
    return all_repos


def _is_url(s: str) -> bool:
    """Return True if s looks like a clone URL rather than a repo name."""
    return "://" in s or s.startswith("git@")


def track_project(cfg: Config, name_or_url: str, path: str | None = None) -> Project:
    """Add a project to tracking and save config.

    Accepts a clone URL (HTTPS/SSH) or a repo name looked up in the local index.
    Raises ValueError if already tracked, name not found, or name is ambiguous.
    """
    if _is_url(name_or_url):
        clone_url = name_or_url
    else:
        repos = index.load_index()
        if not repos:
            raise ValueError("Index is empty. Run 'git-projects remote fetch' first.")
        exact = [r for r in repos if r.name == name_or_url]
        if len(exact) == 1:
            clone_url = exact[0].clone_url
        elif len(exact) > 1:
            urls = ", ".join(r.clone_url for r in exact)
            raise ValueError(f"Ambiguous: '{name_or_url}' matches multiple repos: {urls}")
        else:
            partial = [r for r in repos if name_or_url.lower() in r.name.lower()]
            if len(partial) == 1:
                clone_url = partial[0].clone_url
            elif len(partial) > 1:
                names = ", ".join(r.name for r in partial)
                raise ValueError(f"Ambiguous: '{name_or_url}' matches: {names}. Be more specific.")
            else:
                raise ValueError(
                    f"No repo named '{name_or_url}' in index."
                    " Run 'git-projects remote list' to browse."
                )

    projects = config.load_projects()
    if any(p.clone_url == clone_url for p in projects):
        raise ValueError(f"Already tracking: {clone_url}")

    if path is not None:
        parsed_name = clone_url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]
        project = Project(clone_url=clone_url, name=parsed_name, path=path)
    else:
        project = config.derive_project(clone_url)
    config.save_projects([*projects, project])
    return project


def untrack_project(cfg: Config, name: str) -> None:
    """Remove a project from tracking and save projects.json.

    Raises ValueError if not found.
    """
    projects = config.load_projects()
    filtered = [p for p in projects if p.name != name]
    if len(filtered) == len(projects):
        raise ValueError(f"No project named '{name}' found.")
    config.save_projects(filtered)


@dataclass
class SyncResult:
    cloned: list[str] = field(default_factory=list)
    synced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errored: list[tuple[str, str]] = field(default_factory=list)


def sync_projects(
    projects: list[Project],
    on_project: Callable[[str, str], None] | None = None,
    max_workers: int = 4,
) -> SyncResult:
    """Clone missing repos and pull+push existing ones, in parallel.

    Calls on_project(name, status_message) for each project as it is processed.
    Dirty repos are skipped; git errors are recorded and processing continues.
    """
    result = SyncResult()
    lock = threading.Lock()

    def _sync_one(project: Project) -> None:
        expanded = str(Path(project.path).expanduser())

        if not Path(expanded).exists():
            try:
                clone_repo(project.clone_url, project.path)
                with lock:
                    result.cloned.append(project.name)
                    if on_project:
                        on_project(project.name, "cloned")
            except GitError as exc:
                with lock:
                    result.errored.append((project.name, str(exc)))
                    if on_project:
                        on_project(project.name, f"error: {exc}")
            return

        if is_dirty(project.path):
            with lock:
                result.skipped.append(project.name)
                if on_project:
                    on_project(project.name, "skipped (dirty)")
            return

        try:
            pull_repo(project.path)
            push_repo(project.path)
            with lock:
                result.synced.append(project.name)
                if on_project:
                    on_project(project.name, "synced")
        except GitError as exc:
            with lock:
                result.errored.append((project.name, str(exc)))
                if on_project:
                    on_project(project.name, f"error: {exc}")

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = [executor.submit(_sync_one, p) for p in projects]
        for future in as_completed(futures):
            future.result()

    return result
