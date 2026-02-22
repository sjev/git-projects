from __future__ import annotations

from typing import Annotated

import httpx
import typer

from git_projects import registry
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
        path = registry.init_config(force=force)
        print(path)
    except registry.ConfigExistsError as exc:
        print(exc)
        raise typer.Exit(code=1) from exc


@config_app.command()
def show() -> None:
    """Show config file path and contents."""
    path = registry.get_config_path()
    if not path.exists():
        print("No config found. Run 'git-projects config init' first.")
        raise typer.Exit(code=1)
    print(path)
    print(path.read_text(), end="")


@app.command()
def sync() -> None:
    """Fetch repos from configured foundries and update the registry."""
    try:
        config = registry.load_config()
    except FileNotFoundError as exc:
        print("No config found. Run 'git-projects config init' first.")
        raise typer.Exit(code=1) from exc

    gh_foundries = [f for f in config.foundries if f.type == "github"]
    total = 0

    for foundry_config in gh_foundries:
        try:
            remote_repos = github.list_repos(foundry_config)
        except ValueError as exc:
            print(
                f"Error: GitHub token is not set for foundry '{foundry_config.name}'. "
                "Edit config.yaml to add your token."
            )
            raise typer.Exit(code=1) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                print(
                    f"Error: GitHub API returned 401 for foundry '{foundry_config.name}'. "
                    "Check your token."
                )
            else:
                print(f"Error: GitHub API returned {exc.response.status_code}.")
            raise typer.Exit(code=1) from exc

        repos = [
            registry.Repo(
                name=r.name,
                clone_url=r.clone_url,
                foundry=foundry_config.name,
                pushed_at=r.pushed_at,
                default_branch=r.default_branch,
                visibility=r.visibility,
                description=r.description,
            )
            for r in remote_repos
        ]
        total += len(repos)
        reg = registry.Registry(repos=repos)
        registry.save_registry(reg)
        print(f"Synced {len(repos)} repos from {foundry_config.name}")
