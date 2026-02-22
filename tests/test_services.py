from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from git_projects.config import Config, FoundryConfig, Project
from git_projects.foundry import RemoteRepo
from git_projects.services import fetch_repos, track_project, untrack_project

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
    pushed_at="2025-01-01T00:00:00Z",
    default_branch="main",
    visibility="public",
    description="An old experiment",
)


# --- fetch_repos ---


def test_fetch_repos_returns_repos() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS):
        result = fetch_repos(cfg)

    assert "github" in result
    assert len(result["github"]) == 2


def test_fetch_repos_filters_old_by_default() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with patch("git_projects.services.github.list_repos", return_value=[*_REMOTE_REPOS, _OLD_REPO]):
        result = fetch_repos(cfg)

    names = [r.name for r in result["github"]]
    assert "proj-old" not in names


def test_fetch_repos_show_all_includes_old() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with patch("git_projects.services.github.list_repos", return_value=[*_REMOTE_REPOS, _OLD_REPO]):
        result = fetch_repos(cfg, show_all=True)

    names = [r.name for r in result["github"]]
    assert "proj-old" in names


def test_fetch_repos_by_foundry_name() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS):
        result = fetch_repos(cfg, "github")

    assert "github" in result


def test_fetch_repos_unknown_foundry() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with pytest.raises(ValueError, match="nonexistent"):
        fetch_repos(cfg, "nonexistent")


def test_fetch_repos_missing_token() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", side_effect=ValueError("token")),
        pytest.raises(ValueError, match="token"),
    ):
        fetch_repos(cfg)


# --- track_project ---


def test_track_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    cfg = Config(clone_root="~/projects", foundries=[], projects=[])
    project = track_project(cfg, "https://github.com/user/repo-a.git")

    assert project.name == "repo-a"
    assert len(cfg.projects) == 1


def test_track_project_duplicate() -> None:
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

    with pytest.raises(ValueError, match="Already tracking"):
        track_project(cfg, "https://github.com/user/repo-a.git")


# --- untrack_project ---


def test_untrack_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    untrack_project(cfg, "repo-a")
    assert len(cfg.projects) == 0


def test_untrack_project_not_found() -> None:
    cfg = Config(clone_root="~/projects", foundries=[], projects=[])

    with pytest.raises(ValueError, match="nonexistent"):
        untrack_project(cfg, "nonexistent")
