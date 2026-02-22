from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from git_projects.cli import app
from git_projects.config import DEFAULT_CONFIG, Config, FoundryConfig, Project
from git_projects.foundry import RemoteRepo

runner = CliRunner()


def _ts(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%SZ")


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

_OLD_REPO = RemoteRepo(
    name="proj-old",
    clone_url="https://github.com/user/proj-old.git",
    pushed_at=_ts(timedelta(days=400)),
    default_branch="main",
    visibility="public",
    description="An old experiment",
)

_REMOTE_REPOS_WITH_OLD = [*_REMOTE_REPOS, _OLD_REPO]


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip()


# --- config commands ---


def test_config_no_subcommand_shows_help() -> None:
    result = runner.invoke(app, ["config"])
    assert result.exit_code in {0, 2}
    assert "init" in result.output
    assert "show" in result.output


def test_config_init_creates_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0
    assert config_path.exists()
    assert str(config_path) in result.output
    assert config_path.read_text() == DEFAULT_CONFIG


def test_config_init_refuses_if_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    original = "existing content"
    config_path.write_text(original)
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert config_path.read_text() == original


def test_config_init_force_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("old content")
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "init", "--force"])

    assert result.exit_code == 0
    assert config_path.read_text() == DEFAULT_CONFIG


def test_config_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(DEFAULT_CONFIG)
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == str(config_path)


def test_config_show_no_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    assert "config init" in result.output


# --- fetch ---


def test_fetch_happy_path() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 0
    assert "Fetched 2 repos from 1 foundries" in result.output
    assert "proj-a" in result.output
    assert "https://github.com/user/proj-a.git" in result.output
    assert "A project" in result.output
    assert "ago" in result.output


def test_fetch_most_recent_last() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 0
    # proj-b (2025-11) should appear before proj-a (2026-02) — oldest first
    assert result.output.index("proj-b") < result.output.index("proj-a")


def test_fetch_filters_old_repos_by_default() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS_WITH_OLD),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 0
    assert "Fetched 2 repos from 1 foundries" in result.output
    assert "proj-old" not in result.output


def test_fetch_show_all_includes_old_repos() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS_WITH_OLD),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["fetch", "--show-all"])

    assert result.exit_code == 0
    assert "Fetched 3 repos from 1 foundries" in result.output
    assert "proj-old" in result.output


def test_fetch_no_description_line_for_empty_description() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["fetch"])

    # proj-b has empty description — should only have name line + url line (2 lines)
    lines = result.output.splitlines()
    proj_b_idx = next(i for i, ln in enumerate(lines) if "proj-b" in ln)
    assert "github.com/user/proj-b" in lines[proj_b_idx + 1]
    # Next non-blank line should NOT be a description — it should be the next repo or end
    next_content = lines[proj_b_idx + 2].strip() if proj_b_idx + 2 < len(lines) else ""
    assert next_content == "" or "proj-" in next_content


def test_fetch_by_foundry_name() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["fetch", "github"])

    assert result.exit_code == 0
    assert "proj-a" in result.output


def test_fetch_unknown_foundry() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["fetch", "nonexistent"])

    assert result.exit_code == 1
    assert "nonexistent" in result.output


def test_fetch_no_config() -> None:
    with patch("git_projects.cli.config.load_config", side_effect=FileNotFoundError):
        result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 1
    assert "config init" in result.output


def test_fetch_empty_token() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.services.github.list_repos", side_effect=ValueError("token")),
    ):
        result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 1
    assert "token" in result.output.lower()


def test_fetch_auth_error() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])
    request = httpx.Request("GET", "https://api.github.com/user/repos")
    response = httpx.Response(401)
    response.request = request

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch(
            "git_projects.services.github.list_repos",
            side_effect=httpx.HTTPStatusError("401", request=request, response=response),
        ),
    ):
        result = runner.invoke(app, ["fetch"])

    assert result.exit_code == 1
    assert "401" in result.output


# --- track ---


def test_track_adds_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY], projects=[])

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["track", "https://github.com/user/repo-a.git"])

    assert result.exit_code == 0
    assert "repo-a" in result.output


def test_track_duplicate_rejected() -> None:
    cfg = Config(
        clone_root="~/projects",
        foundries=[],
        projects=[
            Project(
                clone_url="https://github.com/user/repo-a.git",
                name="repo-a",
                path="~/projects/github.com/user/repo-a",
            )
        ],
    )

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["track", "https://github.com/user/repo-a.git"])

    assert result.exit_code == 1
    assert "Already tracking" in result.output


# --- untrack ---


def test_untrack_removes_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    cfg = Config(
        clone_root="~/projects",
        foundries=[],
        projects=[
            Project(
                clone_url="https://github.com/user/repo-a.git",
                name="repo-a",
                path="~/projects/github.com/user/repo-a",
            )
        ],
    )

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["untrack", "repo-a"])

    assert result.exit_code == 0
    assert "Untracked repo-a" in result.output


def test_untrack_unknown_project() -> None:
    cfg = Config(clone_root="~/projects", foundries=[], projects=[])

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["untrack", "nonexistent"])

    assert result.exit_code == 1
    assert "nonexistent" in result.output


# --- list ---


def test_list_shows_projects() -> None:
    cfg = Config(
        clone_root="~/projects",
        foundries=[],
        projects=[
            Project(
                clone_url="https://github.com/user/repo-a.git",
                name="repo-a",
                path="~/projects/github.com/user/repo-a",
            )
        ],
    )

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "repo-a" in result.output
    assert "~/projects/github.com/user/repo-a" in result.output


def test_list_empty() -> None:
    cfg = Config(clone_root="~/projects", foundries=[], projects=[])

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No projects tracked" in result.output
