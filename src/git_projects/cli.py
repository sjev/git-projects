from __future__ import annotations

from typing import Annotated

import httpx
import typer

from git_projects import config
from git_projects.formatting import format_repo
from git_projects.services import fetch_repos, track_project, untrack_project

app = typer.Typer(no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
app.add_typer(config_app, name="config", help="Manage configuration.")


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        print(version("git-projects"))
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version and exit.", callback=_version_callback),
    ] = False,
) -> None:
    """History of git projects"""


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
    show_all: Annotated[
        bool, typer.Option("--show-all", help="Show all repos, not just recent ones.")
    ] = False,
) -> None:
    """Fetch and print available repos from foundry APIs."""
    cfg = _load_config_or_exit()

    try:
        repos_by_foundry = fetch_repos(cfg, foundry_name, show_all=show_all)
    except ValueError as exc:
        print(exc)
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            print(f"Error: API returned 401 for foundry '{foundry_name}'. Check your token.")
        else:
            print(f"Error: API returned {exc.response.status_code} for foundry '{foundry_name}'.")
        raise typer.Exit(code=1) from None

    for name, repos in repos_by_foundry.items():
        print(60 * "-")
        print(f"# {name} ({len(repos)} repos)")
        print(60 * "-")

        for repo in repos:
            print()
            print(format_repo(repo), end="")


@app.command()
def track(
    clone_url: Annotated[str, typer.Argument(help="Clone URL of the repo to track.")],
) -> None:
    """Add a project to tracking."""
    cfg = _load_config_or_exit()

    try:
        project = track_project(cfg, clone_url)
    except ValueError as exc:
        print(exc)
        raise typer.Exit(code=1) from None

    print(f"Tracking {project.name} → {project.path}")


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


@app.command(name="list")
def list_projects() -> None:
    """Show tracked projects."""
    cfg = _load_config_or_exit()

    if not cfg.projects:
        print("No projects tracked. Use 'git-projects track <clone_url>' to add one.")
        return

    for project in cfg.projects:
        print(f"{project.name}  {project.path}")


@app.command()
def sync() -> None:
    """Clone missing repos and pull existing tracked repos."""
    cfg = _load_config_or_exit()

    if not cfg.projects:
        print("No projects tracked. Use 'git-projects track <clone_url>' to add one.")
        return

    for project in cfg.projects:
        print(f"Sync: {project.name} → {project.path}")
        # TODO: clone if missing, pull if exists (requires gitops module)
