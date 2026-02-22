from __future__ import annotations

from typing import Annotated

import httpx
import typer

from git_projects import config
from git_projects.foundry import github

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
) -> None:
    """Fetch and print available repos from foundry APIs."""
    cfg = _load_config_or_exit()

    foundries = cfg.foundries
    if foundry_name:
        foundries = [f for f in foundries if f.name == foundry_name]
        if not foundries:
            print(f"No foundry named '{foundry_name}' in config.")
            raise typer.Exit(code=1)

    for foundry_config in foundries:
        if foundry_config.type == "github":
            try:
                repos = github.list_repos(foundry_config)
            except ValueError:
                print(
                    f"Error: GitHub token is not set for foundry '{foundry_config.name}'. "
                    "Edit config.yaml to add your token."
                )
                raise typer.Exit(code=1) from None
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    print(
                        f"Error: GitHub API returned 401 for foundry '{foundry_config.name}'. "
                        "Check your token."
                    )
                else:
                    print(f"Error: GitHub API returned {exc.response.status_code}.")
                raise typer.Exit(code=1) from None

            print(f"# {foundry_config.name} ({len(repos)} repos)")
            for repo in repos:
                print(f"  {repo.clone_url}")


@app.command()
def track(
    clone_url: Annotated[str, typer.Argument(help="Clone URL of the repo to track.")],
) -> None:
    """Add a project to tracking."""
    cfg = _load_config_or_exit()

    if any(p.clone_url == clone_url for p in cfg.projects):
        print(f"Already tracking: {clone_url}")
        raise typer.Exit(code=1)

    project = config.derive_project(clone_url, cfg.clone_root)
    cfg.projects.append(project)
    config.save_config(cfg)
    print(f"Tracking {project.name} → {project.path}")


@app.command()
def untrack(
    name: Annotated[str, typer.Argument(help="Project name to stop tracking.")],
) -> None:
    """Remove a project from tracking."""
    cfg = _load_config_or_exit()

    before = len(cfg.projects)
    cfg.projects = [p for p in cfg.projects if p.name != name]
    if len(cfg.projects) == before:
        print(f"No project named '{name}' found.")
        raise typer.Exit(code=1)

    config.save_config(cfg)
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
