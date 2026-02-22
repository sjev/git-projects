from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from git_projects.cli import app
from git_projects.foundry import RemoteRepo
from git_projects.registry import Config, FoundryConfig

runner = CliRunner()

_GH_FOUNDRY = FoundryConfig(name="github", type="github", url="https://api.github.com", token="tok")

_REMOTE_REPOS = [
    RemoteRepo(
        name="proj-a",
        clone_url="https://github.com/user/proj-a.git",
        pushed_at="2026-02-20T10:00:00Z",
        default_branch="main",
        visibility="public",
        description="A project",
    ),
    RemoteRepo(
        name="proj-b",
        clone_url="https://github.com/user/proj-b.git",
        pushed_at="2025-11-01T08:00:00Z",
        default_branch="main",
        visibility="private",
        description="",
    ),
]


# AC-01, AC-08: happy path — syncs repos and prints summary
def test_sync_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "registry.yaml"
    monkeypatch.setattr("git_projects.registry.get_registry_path", lambda: registry_path)

    config = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.cli.registry.load_config", return_value=config),
        patch("git_projects.cli.github.list_repos", return_value=_REMOTE_REPOS),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "Synced 2 repos from github" in result.output
    assert registry_path.exists()


# AC-05: no config file → exit 1, tells user to run config init
def test_sync_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("git_projects.cli.registry.load_config", side_effect=FileNotFoundError):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 1
    assert "config init" in result.output


# AC-06: empty token → exit 1, tells user to edit config
def test_sync_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.cli.registry.load_config", return_value=config),
        patch("git_projects.cli.github.list_repos", side_effect=ValueError("token")),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 1
    assert "token" in result.output.lower()


# AC-07: 401 from API → exit 1, tells user to check token
def test_sync_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])
    request = httpx.Request("GET", "https://api.github.com/user/repos")
    response = httpx.Response(401)
    response.request = request

    with (
        patch("git_projects.cli.registry.load_config", return_value=config),
        patch(
            "git_projects.cli.github.list_repos",
            side_effect=httpx.HTTPStatusError("401", request=request, response=response),
        ),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 1
    assert "401" in result.output
