from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from git_projects.cli import _format_age, app
from git_projects.config import DEFAULT_CONFIG, Config, FoundryConfig, Project
from git_projects.foundry import RemoteRepo

runner = CliRunner()


def _ts(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%SZ")


_GH_FOUNDRY = FoundryConfig(name="github", type="github", url="https://api.github.com", token="tok")

_REMOTE_REPOS = [
    RemoteRepo(
        name="proj-a",
        repo_url="https://github.com/user/proj-a",
        clone_url="git@github.com:user/proj-a.git",
        pushed_at="2026-02-20T10:00:00Z",
        default_branch="main",
        visibility="public",
        description="A project",
    ),
    RemoteRepo(
        name="proj-b",
        repo_url="https://github.com/user/proj-b",
        clone_url="git@github.com:user/proj-b.git",
        pushed_at="2025-11-01T08:00:00Z",
        default_branch="main",
        visibility="private",
        description="",
    ),
]

_OLD_REPO = RemoteRepo(
    name="proj-old",
    repo_url="https://github.com/user/proj-old",
    clone_url="git@github.com:user/proj-old.git",
    pushed_at=_ts(timedelta(days=400)),
    default_branch="main",
    visibility="public",
    description="An old experiment",
)


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


# --- remote fetch ---


def test_remote_fetch_happy_path() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.services.index.save_index"),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["remote", "fetch"])

    assert result.exit_code == 0
    assert "Fetched 2 repos from 1 foundries" in result.output


def test_remote_fetch_by_foundry_name() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.services.index.save_index"),
        patch("git_projects.cli.config.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["remote", "fetch", "github"])

    assert result.exit_code == 0
    assert "Fetched 2 repos" in result.output


def test_remote_fetch_unknown_foundry() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["remote", "fetch", "nonexistent"])

    assert result.exit_code == 1
    assert "nonexistent" in result.output


def test_remote_fetch_no_config() -> None:
    with patch("git_projects.cli.config.load_config", side_effect=FileNotFoundError):
        result = runner.invoke(app, ["remote", "fetch"])

    assert result.exit_code == 1
    assert "config init" in result.output


def test_remote_fetch_empty_token() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.services.github.list_repos", side_effect=ValueError("token")),
    ):
        result = runner.invoke(app, ["remote", "fetch"])

    assert result.exit_code == 1
    assert "token" in result.output.lower()


def test_remote_fetch_auth_error() -> None:
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
        result = runner.invoke(app, ["remote", "fetch"])

    assert result.exit_code == 1
    assert "401" in result.output


# --- remote list ---


def test_remote_list_empty_index() -> None:
    with patch("git_projects.cli.index.load_index", return_value=[]):
        result = runner.invoke(app, ["remote", "list"])

    assert result.exit_code == 1
    assert "remote fetch" in result.output


def test_remote_list_shows_repos() -> None:
    with patch("git_projects.cli.index.load_index", return_value=_REMOTE_REPOS):
        result = runner.invoke(app, ["remote", "list"])

    assert result.exit_code == 0
    assert "proj-a" in result.output
    assert "proj-b" in result.output
    assert "https://github.com/user/proj-a" in result.output
    assert "A project" in result.output


def test_remote_list_filters_by_query() -> None:
    with patch("git_projects.cli.index.load_index", return_value=_REMOTE_REPOS):
        result = runner.invoke(app, ["remote", "list", "proj-a"])

    assert result.exit_code == 0
    assert "proj-a" in result.output
    assert "proj-b" not in result.output


def test_remote_list_hides_old_repos_by_default() -> None:
    with patch("git_projects.cli.index.load_index", return_value=[*_REMOTE_REPOS, _OLD_REPO]):
        result = runner.invoke(app, ["remote", "list"])

    assert result.exit_code == 0
    assert "proj-old" not in result.output


def test_remote_list_all_shows_old_repos() -> None:
    with patch("git_projects.cli.index.load_index", return_value=[*_REMOTE_REPOS, _OLD_REPO]):
        result = runner.invoke(app, ["remote", "list", "--all"])

    assert result.exit_code == 0
    assert "proj-old" in result.output


def test_remote_list_most_recent_last() -> None:
    with patch("git_projects.cli.index.load_index", return_value=_REMOTE_REPOS):
        result = runner.invoke(app, ["remote", "list"])

    assert result.exit_code == 0
    assert result.output.index("proj-b") < result.output.index("proj-a")


def test_remote_list_no_results_for_query() -> None:
    with patch("git_projects.cli.index.load_index", return_value=_REMOTE_REPOS):
        result = runner.invoke(app, ["remote", "list", "zzznomatch"])

    assert result.exit_code == 0
    assert "No repos" in result.output


# --- track ---


def test_track_adds_project_by_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["track", "https://github.com/user/repo-a.git"])

    assert result.exit_code == 0
    assert "repo-a" in result.output
    assert "https://github.com/user/repo-a.git" in result.output


def test_track_ssh_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    cfg = Config(clone_root="~/projects", foundries=[])

    with patch("git_projects.cli.config.load_config", return_value=cfg):
        result = runner.invoke(app, ["track", "git@github.com:user/repo-a.git"])

    assert result.exit_code == 0
    assert "repo-a" in result.output
    assert "git@github.com:user/repo-a.git" in result.output


def test_track_by_name_from_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.services.index.load_index", return_value=_REMOTE_REPOS),
    ):
        result = runner.invoke(app, ["track", "proj-a"])

    assert result.exit_code == 0
    assert "proj-a" in result.output


def test_track_by_name_empty_index() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.services.index.load_index", return_value=[]),
    ):
        result = runner.invoke(app, ["track", "proj-a"])

    assert result.exit_code == 1
    assert "remote fetch" in result.output


def test_track_duplicate_rejected() -> None:
    """AC-08: duplicate rejected via load_projects check."""
    cfg = Config(clone_root="~/projects", foundries=[])
    existing = [
        Project(clone_url="https://github.com/user/repo-a.git", name="repo-a", path="repo-a")
    ]

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.services.config.load_projects", return_value=existing),
    ):
        result = runner.invoke(app, ["track", "https://github.com/user/repo-a.git"])

    assert result.exit_code == 1
    assert "Already tracking" in result.output


# --- untrack ---


def test_untrack_removes_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-09: untrack removes project from projects.json."""
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    existing = [
        Project(clone_url="https://github.com/user/repo-a.git", name="repo-a", path="repo-a")
    ]
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.services.config.load_projects", return_value=existing),
        patch("git_projects.services.config.save_projects"),
    ):
        result = runner.invoke(app, ["untrack", "repo-a"])

    assert result.exit_code == 0
    assert "Untracked repo-a" in result.output


def test_untrack_unknown_project() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.services.config.load_projects", return_value=[]),
    ):
        result = runner.invoke(app, ["untrack", "nonexistent"])

    assert result.exit_code == 1
    assert "nonexistent" in result.output


# --- list ---


def test_list_shows_projects() -> None:
    """AC-10: list reads from load_projects and resolves absolute paths."""
    cfg = Config(clone_root="~/projects", foundries=[])
    projects = [
        Project(clone_url="https://github.com/user/repo-a.git", name="repo-a", path="repo-a")
    ]

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.cli.config.load_projects", return_value=projects),
    ):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "repo-a" in result.output
    # path resolved to clone_root / path
    assert "projects/repo-a" in result.output


def test_list_empty() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.cli.config.load_projects", return_value=[]),
    ):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No projects tracked" in result.output


# --- info ---


def test_info_both_files_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-12: info shows projects.json path and tracked project count."""
    config_path = tmp_path / "git-projects" / "config.yaml"
    index_path = tmp_path / "git-projects" / "index.json"
    projects_path = tmp_path / "git-projects" / "projects.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(DEFAULT_CONFIG)

    updated = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    index_data = {"updated_at": updated, "repos": [{"name": "r1"}, {"name": "r2"}]}
    index_path.write_text(json.dumps(index_data))

    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)
    monkeypatch.setattr("git_projects.index.get_index_path", lambda: index_path)

    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert "git-projects" in result.output
    assert str(config_path) in result.output
    assert str(projects_path) in result.output
    assert str(index_path) in result.output
    assert "0 tracked projects" in result.output
    assert "2 repos" in result.output
    assert "2h ago" in result.output


def test_info_config_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    index_path = tmp_path / "git-projects" / "index.json"
    projects_path = tmp_path / "git-projects" / "projects.json"
    config_path.parent.mkdir(parents=True)

    updated = datetime.now(timezone.utc).isoformat()
    index_data = {"updated_at": updated, "repos": [{"name": "r1"}]}
    index_path.write_text(json.dumps(index_data))

    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)
    monkeypatch.setattr("git_projects.index.get_index_path", lambda: index_path)

    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert str(config_path) in result.output
    assert "not found" in result.output
    assert "tracked project" not in result.output


def test_info_index_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    index_path = tmp_path / "git-projects" / "index.json"
    projects_path = tmp_path / "git-projects" / "projects.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(DEFAULT_CONFIG)

    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)
    monkeypatch.setattr("git_projects.index.get_index_path", lambda: index_path)

    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert str(index_path) in result.output
    assert "not found" in result.output
    assert "repos" not in result.output


def test_info_both_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    index_path = tmp_path / "git-projects" / "index.json"
    projects_path = tmp_path / "git-projects" / "projects.json"

    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)
    monkeypatch.setattr("git_projects.index.get_index_path", lambda: index_path)

    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    output = result.output
    assert output.count("not found") == 2
    assert "tracked project" not in output
    assert "repos" not in output


def test_info_version_fallback() -> None:
    """PackageNotFoundError falls back to 'unknown'."""
    from importlib.metadata import PackageNotFoundError

    with patch("git_projects.cli.importlib.metadata.version", side_effect=PackageNotFoundError):
        result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert "unknown" in result.output


def test_format_age_just_now() -> None:
    now = datetime.now(timezone.utc)
    assert _format_age(now) == "just now"


def test_format_age_minutes() -> None:
    dt = datetime.now(timezone.utc) - timedelta(minutes=15)
    assert _format_age(dt) == "15m ago"


def test_format_age_hours() -> None:
    dt = datetime.now(timezone.utc) - timedelta(hours=5)
    assert _format_age(dt) == "5h ago"


def test_format_age_days() -> None:
    dt = datetime.now(timezone.utc) - timedelta(days=3)
    assert _format_age(dt) == "3d ago"


# --- sync command ---

from git_projects.services import SyncResult  # noqa: E402


def _sync_cfg() -> Config:
    return Config(clone_root="~/projects", foundries=[])


_SYNC_PROJECTS = [
    Project(clone_url="https://github.com/u/a.git", name="a", path="a"),
    Project(clone_url="https://github.com/u/b.git", name="b", path="b"),
]


def test_sync_no_projects() -> None:
    """AC-11: sync reads from load_projects."""
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.cli.config.load_config", return_value=cfg),
        patch("git_projects.cli.config.load_projects", return_value=[]),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "No projects tracked" in result.output


def test_sync_calls_sync_projects_with_resolved_paths() -> None:
    """AC-11: sync resolves clone_root / project.path before calling sync_projects."""
    sync_result = SyncResult(cloned=[], synced=["a", "b"], skipped=[], errored=[])

    with (
        patch("git_projects.cli.config.load_config", return_value=_sync_cfg()),
        patch("git_projects.cli.config.load_projects", return_value=_SYNC_PROJECTS),
        patch("git_projects.cli.sync_projects", return_value=sync_result) as mock_sync,
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    mock_sync.assert_called_once()
    passed_projects = mock_sync.call_args[0][0]
    # paths must be absolute (resolved)
    assert all(Path(p.path).is_absolute() for p in passed_projects)
    assert all(p.path.endswith(p.name) for p in passed_projects)


def test_sync_prints_summary_line() -> None:
    sync_result = SyncResult(cloned=["a"], synced=["b"], skipped=["c"], errored=[("d", "fail")])

    with (
        patch("git_projects.cli.config.load_config", return_value=_sync_cfg()),
        patch("git_projects.cli.config.load_projects", return_value=_SYNC_PROJECTS),
        patch("git_projects.cli.sync_projects", return_value=sync_result),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "2 synced" in result.output
    assert "1 skipped" in result.output
    assert "1 errors" in result.output


def test_sync_on_project_callback_is_called() -> None:
    def fake_sync(projects, on_project=None):
        if on_project:
            on_project("a", "synced")
            on_project("b", "skipped (dirty)")
        return SyncResult(synced=["a"], skipped=["b"])

    with (
        patch("git_projects.cli.config.load_config", return_value=_sync_cfg()),
        patch("git_projects.cli.config.load_projects", return_value=_SYNC_PROJECTS),
        patch("git_projects.cli.sync_projects", side_effect=fake_sync),
    ):
        result = runner.invoke(app, ["sync"])

    assert "synced" in result.output
    assert "skipped" in result.output
