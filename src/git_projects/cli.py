from __future__ import annotations

import importlib.metadata
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import httpx
import typer

from git_projects import config, index
from git_projects.formatting import format_repo
from git_projects.services import fetch_repos, sync_projects, track_project, untrack_project

app = typer.Typer(no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
app.add_typer(config_app, name="config", help="Manage configuration.")


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        print(version("git-proj"))
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Discover, track, and sync git repos across foundries."""


@config_app.command()
def init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing config."),
    ] = False,
) -> None:
    """Create default config file."""
    try:
        path = config.init_config(force=force)
        print(path)
    except config.ConfigExistsError as exc:
        print(exc)
        raise typer.Exit(code=1) from exc


@config_app.command()
def show() -> None:
    """Show config file path and contents."""
    path = config.get_config_path()
    if not path.exists():
        print("No config found. Run 'git-projects config init' first.")
        raise typer.Exit(code=1)
    print(path)
    print(path.read_text(), end="")


def _load_config_or_exit() -> config.Config:
    """Load config or exit with error message."""
    try:
        return config.load_config()
    except FileNotFoundError as exc:
        print("No config found. Run 'git-projects config init' first.")
        raise typer.Exit(code=1) from exc


@app.command()
def fetch(
    foundry_name: Annotated[str | None, typer.Argument(help="Foundry name to fetch from.")] = None,
) -> None:
    """Fetch repos from foundry APIs and save to local index."""
    cfg = _load_config_or_exit()

    sys.stdout.write("Fetching...")
    sys.stdout.flush()

    try:
        repos = fetch_repos(cfg, foundry_name)
    except ValueError as exc:
        sys.stdout.write("\r\033[K")
        print(exc)
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as exc:
        sys.stdout.write("\r\033[K")
        if exc.response.status_code == 401:
            print(f"Error: API returned 401 for foundry '{foundry_name}'. Check your token.")
        else:
            print(f"Error: API returned {exc.response.status_code} for foundry '{foundry_name}'.")
        raise typer.Exit(code=1) from None

    n_foundries = len(cfg.foundries) if foundry_name is None else 1
    summary = typer.style(f"Fetched {len(repos)} repos from {n_foundries} foundries", bold=True)
    print(f"\r\033[K{summary}")


@app.command(name="list")
def list_repos(
    query: Annotated[
        str | None, typer.Argument(help="Filter by name or description substring.")
    ] = None,
) -> None:
    """Show repos from local index. Tracked projects are highlighted with their local path."""
    repos = index.load_index()

    if not repos:
        print("Index is empty. Run 'git-projects fetch' first.")
        raise typer.Exit(code=1)

    repos = index.search_index(repos, query)

    if not repos:
        hint = f" matching '{query}'" if query else ""
        print(f"No repos{hint} in index.")
        return

    # Build lookup of tracked clone_urls → absolute paths
    tracked: dict[str, str] = {}
    try:
        cfg = config.load_config()
        clone_root = str(Path(cfg.clone_root).expanduser())
        for p in config.load_projects():
            tracked[p.clone_url] = str(Path(clone_root) / p.path)
    except FileNotFoundError:
        pass

    summary = typer.style(f"{len(repos)} repos", bold=True)
    print(f"{summary}\n{'─' * 60}")

    for repo in repos:
        print()
        print(format_repo(repo, tracked_path=tracked.get(repo.clone_url)), end="")


@app.command()
def track(
    name_or_url: Annotated[
        str, typer.Argument(help="Repo name (from index) or clone URL to track.")
    ],
    path: Annotated[
        str | None, typer.Option("--path", "-p", help="Override local clone path.")
    ] = None,
) -> None:
    """Add a project to tracking."""
    cfg = _load_config_or_exit()

    try:
        project = track_project(cfg, name_or_url, path)
    except ValueError as exc:
        print(exc)
        raise typer.Exit(code=1) from None

    clone_url_styled = typer.style(project.clone_url, dim=True)
    print(f"Tracking {project.name} → {project.path}\n  {clone_url_styled}")


@app.command()
def untrack(
    name: Annotated[str, typer.Argument(help="Project name to stop tracking.")],
) -> None:
    """Remove a project from tracking."""
    cfg = _load_config_or_exit()

    try:
        untrack_project(cfg, name)
    except ValueError as exc:
        print(exc)
        raise typer.Exit(code=1) from None

    print(f"Untracked {name}")


def _format_age(dt: datetime) -> str:
    """Format a datetime as a human-readable relative age string."""
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = seconds // 3600
    if hours < 48:
        return f"{hours}h ago"
    days = seconds // 86400
    return f"{days}d ago"


@app.command()
def info() -> None:
    """Show app version, config and index locations, and repo counts."""
    try:
        version = importlib.metadata.version("git-proj")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"

    typer.echo(f"git-projects {typer.style(version, bold=True)}")
    typer.echo()

    # Config section
    config_path = config.get_config_path()
    if config_path.exists():
        typer.echo(f"Config    {typer.style(str(config_path), dim=True)}")
    else:
        typer.echo(
            f"Config    {typer.style(str(config_path), dim=True)}  "
            f"{typer.style('(not found)', dim=True)}"
        )

    # Projects section
    projects_path = config.get_projects_path()
    n_tracked = len(config.load_projects())
    if config_path.exists():
        typer.echo(f"Projects  {typer.style(str(projects_path), dim=True)}")
        typer.echo(f"          {typer.style(f'{n_tracked} tracked projects', dim=True)}")

    # Index section
    index_path = index.get_index_path()
    if index_path.exists():
        raw = json.loads(index_path.read_text())
        n_repos = len(raw.get("repos", []))
        updated_at = datetime.fromisoformat(raw["updated_at"])
        age = _format_age(updated_at)
        typer.echo(f"Index     {typer.style(str(index_path), dim=True)}")
        typer.echo(f"          {typer.style(f'{n_repos} repos, updated {age}', dim=True)}")
    else:
        typer.echo(
            f"Index     {typer.style(str(index_path), dim=True)}  "
            f"{typer.style('(not found)', dim=True)}"
        )


@app.command()
def sync(
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Number of parallel workers.", min=1),
    ] = 4,
) -> None:
    """Clone missing repos and pull existing tracked repos."""
    cfg = _load_config_or_exit()
    projects = config.load_projects()

    if not projects:
        print("No projects tracked. Use 'git-projects track <name>' to add one.")
        return

    clone_root = Path(cfg.clone_root).expanduser()
    resolved = [
        config.Project(clone_url=p.clone_url, name=p.name, path=str(clone_root / p.path))
        for p in projects
    ]

    _STATUS_COLOR = {
        "cloned": "cyan",
        "synced": "green",
        "skipped (dirty)": "yellow",
    }

    def _on_project(name: str, status: str, git_ops: list[tuple[str, str]]) -> None:
        color = _STATUS_COLOR.get(status, "red")
        label = typer.style(status, fg=color)
        print(f"  {name}  {label}")
        for cmd, output in git_ops:
            print(typer.style(f"    {cmd}", dim=True))
            if output:
                print(typer.style(f"    {output}", dim=True))

    result = sync_projects(resolved, on_project=_on_project, max_workers=workers)

    summary = (
        f"{len(result.cloned) + len(result.synced)} synced, "
        f"{len(result.skipped)} skipped, "
        f"{len(result.errored)} errors"
    )
    print(f"\n{typer.style(summary, bold=True)}")
