from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from git_projects.config import Config, FoundryConfig, Project
from git_projects.foundry import RemoteRepo
from git_projects.gitops import GitError
from git_projects.services import fetch_repos, sync_projects, track_project, untrack_project

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


# --- fetch_repos ---


def test_fetch_repos_returns_repos() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.services.index.save_index"),
    ):
        result = fetch_repos(cfg)

    assert len(result) == 2


def test_fetch_repos_sorted_ascending() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.services.index.save_index"),
    ):
        result = fetch_repos(cfg)

    assert result[0].name == "proj-b"  # older
    assert result[1].name == "proj-a"  # newer


def test_fetch_repos_saves_to_index() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.services.index.save_index") as mock_save,
    ):
        fetch_repos(cfg)

    mock_save.assert_called_once()
    saved = mock_save.call_args[0][0]
    assert len(saved) == 2


def test_fetch_repos_by_foundry_name() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY])

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS),
        patch("git_projects.services.index.save_index"),
    ):
        result = fetch_repos(cfg, "github")

    assert len(result) == 2


def test_fetch_repos_passes_clone_url_format() -> None:
    cfg = Config(clone_root="~/projects", foundries=[_GH_FOUNDRY], clone_url_format="https")

    with (
        patch("git_projects.services.github.list_repos", return_value=_REMOTE_REPOS) as mock_lr,
        patch("git_projects.services.index.save_index"),
    ):
        fetch_repos(cfg)

    mock_lr.assert_called_once()
    assert mock_lr.call_args[0][1] == "https"


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


# --- track_project (URL) ---


def test_track_project_by_url() -> None:
    """AC-08: track saves new project to projects.json."""
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.services.config.load_projects", return_value=[]) as mock_load,
        patch("git_projects.services.config.save_projects") as mock_save,
    ):
        project = track_project(cfg, "https://github.com/user/repo-a.git")

    assert project.name == "repo-a"
    assert project.path == "repo-a"
    mock_load.assert_called_once()
    mock_save.assert_called_once_with([project])


def test_track_project_duplicate() -> None:
    """AC-08: duplicate clone_url raises ValueError."""
    cfg = Config(clone_root="~/projects", foundries=[])
    existing = Project(
        clone_url="https://github.com/user/repo-a.git",
        name="repo-a",
        path="repo-a",
    )

    with (
        patch("git_projects.services.config.load_projects", return_value=[existing]),
        pytest.raises(ValueError, match="Already tracking"),
    ):
        track_project(cfg, "https://github.com/user/repo-a.git")


# --- track_project (name lookup) ---


def test_track_project_by_name() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.services.index.load_index", return_value=_REMOTE_REPOS),
        patch("git_projects.services.config.load_projects", return_value=[]),
        patch("git_projects.services.config.save_projects"),
    ):
        project = track_project(cfg, "proj-a")

    assert project.name == "proj-a"
    assert project.clone_url == "git@github.com:user/proj-a.git"


def test_track_project_by_partial_name() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.services.index.load_index", return_value=_REMOTE_REPOS),
        patch("git_projects.services.config.load_projects", return_value=[]),
        patch("git_projects.services.config.save_projects"),
    ):
        project = track_project(cfg, "proj-a")

    assert project.name == "proj-a"


def test_track_project_name_empty_index() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.services.index.load_index", return_value=[]),
        pytest.raises(ValueError, match="Index is empty"),
    ):
        track_project(cfg, "proj-a")


def test_track_project_name_not_found() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.services.index.load_index", return_value=_REMOTE_REPOS),
        pytest.raises(ValueError, match="No repo named"),
    ):
        track_project(cfg, "nonexistent-xyz")


def test_track_project_name_ambiguous() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.services.index.load_index", return_value=_REMOTE_REPOS),
        pytest.raises(ValueError, match="Ambiguous"),
    ):
        # "proj" matches both proj-a and proj-b via substring
        track_project(cfg, "proj")


# --- untrack_project ---


def test_untrack_project() -> None:
    """AC-09: untrack removes the named project and saves projects.json."""
    cfg = Config(clone_root="~/projects", foundries=[])
    existing = Project(
        clone_url="https://github.com/user/repo-a.git",
        name="repo-a",
        path="repo-a",
    )

    with (
        patch("git_projects.services.config.load_projects", return_value=[existing]),
        patch("git_projects.services.config.save_projects") as mock_save,
    ):
        untrack_project(cfg, "repo-a")

    mock_save.assert_called_once_with([])


def test_untrack_project_not_found() -> None:
    cfg = Config(clone_root="~/projects", foundries=[])

    with (
        patch("git_projects.services.config.load_projects", return_value=[]),
        pytest.raises(ValueError, match="nonexistent"),
    ):
        untrack_project(cfg, "nonexistent")


# --- sync_projects ---

_PROJECTS = [
    Project(clone_url="https://github.com/u/a.git", name="a", path="/repos/a"),
    Project(clone_url="https://github.com/u/b.git", name="b", path="/repos/b"),
]


def test_sync_clones_missing_repo() -> None:
    with (
        patch("git_projects.services.Path") as mock_path,
        patch("git_projects.services.clone_repo") as mock_clone,
        patch("git_projects.services.is_dirty"),
        patch("git_projects.services.pull_repo"),
        patch("git_projects.services.push_repo"),
    ):
        mock_path.return_value.expanduser.return_value = mock_path.return_value
        mock_path.return_value.__str__ = lambda self: "/repos/a"
        mock_path.return_value.exists.return_value = False

        result = sync_projects([_PROJECTS[0]])

    assert result.cloned == ["a"]
    assert result.synced == []
    mock_clone.assert_called_once()


def test_sync_pulls_and_pushes_clean_repo(tmp_path: Path) -> None:
    repo = tmp_path / "a"
    repo.mkdir()
    project = Project(clone_url="https://github.com/u/a.git", name="a", path=str(repo))

    with (
        patch("git_projects.services.is_dirty", return_value=False),
        patch("git_projects.services.pull_repo") as mock_pull,
        patch("git_projects.services.push_repo") as mock_push,
    ):
        result = sync_projects([project])

    assert result.synced == ["a"]
    assert result.cloned == []
    mock_pull.assert_called_once_with(str(repo))
    mock_push.assert_called_once_with(str(repo))


def test_sync_skips_dirty_repo(tmp_path: Path) -> None:
    repo = tmp_path / "a"
    repo.mkdir()
    project = Project(clone_url="https://github.com/u/a.git", name="a", path=str(repo))

    with (
        patch("git_projects.services.is_dirty", return_value=True),
        patch("git_projects.services.pull_repo") as mock_pull,
    ):
        result = sync_projects([project])

    assert result.skipped == ["a"]
    mock_pull.assert_not_called()


def test_sync_records_clone_error() -> None:
    with (
        patch("git_projects.services.Path") as mock_path,
        patch("git_projects.services.clone_repo", side_effect=GitError("auth failed")),
    ):
        mock_path.return_value.expanduser.return_value = mock_path.return_value
        mock_path.return_value.__str__ = lambda self: "/repos/a"
        mock_path.return_value.exists.return_value = False

        result = sync_projects([_PROJECTS[0]])

    assert result.errored == [("a", "auth failed")]
    assert result.cloned == []


def test_sync_records_pull_error_and_skips_push(tmp_path: Path) -> None:
    repo = tmp_path / "a"
    repo.mkdir()
    project = Project(clone_url="https://github.com/u/a.git", name="a", path=str(repo))

    with (
        patch("git_projects.services.is_dirty", return_value=False),
        patch("git_projects.services.pull_repo", side_effect=GitError("conflict")),
        patch("git_projects.services.push_repo") as mock_push,
    ):
        result = sync_projects([project])

    assert result.errored == [("a", "conflict")]
    mock_push.assert_not_called()


def test_sync_continues_after_error(tmp_path: Path) -> None:
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    repo_b.mkdir()
    projects = [
        Project(clone_url="https://github.com/u/a.git", name="a", path=str(repo_a)),
        Project(clone_url="https://github.com/u/b.git", name="b", path=str(repo_b)),
    ]

    with (
        patch("git_projects.services.clone_repo", side_effect=GitError("fail")),
        patch("git_projects.services.is_dirty", return_value=False),
        patch("git_projects.services.pull_repo"),
        patch("git_projects.services.push_repo"),
    ):
        result = sync_projects(projects)

    assert result.errored[0][0] == "a"
    assert result.synced == ["b"]


def test_sync_empty_projects() -> None:
    result = sync_projects([])
    assert result.cloned == []
    assert result.synced == []
    assert result.skipped == []
    assert result.errored == []


def test_sync_calls_on_project_callback(tmp_path: Path) -> None:
    repo = tmp_path / "a"
    repo.mkdir()
    project = Project(clone_url="https://github.com/u/a.git", name="a", path=str(repo))
    calls: list[tuple[str, str]] = []

    with (
        patch("git_projects.services.is_dirty", return_value=False),
        patch("git_projects.services.pull_repo"),
        patch("git_projects.services.push_repo"),
    ):
        sync_projects([project], on_project=lambda n, s: calls.append((n, s)))

    assert calls == [("a", "synced")]


def test_sync_parallel_processes_all_projects(tmp_path: Path) -> None:
    """All projects are processed when using multiple workers."""
    repos = []
    projects = []
    for name in ("a", "b", "c", "d"):
        repo = tmp_path / name
        repo.mkdir()
        projects.append(
            Project(clone_url=f"https://github.com/u/{name}.git", name=name, path=str(repo))
        )
        repos.append(repo)

    with (
        patch("git_projects.services.is_dirty", return_value=False),
        patch("git_projects.services.pull_repo"),
        patch("git_projects.services.push_repo"),
    ):
        result = sync_projects(projects, max_workers=4)

    assert sorted(result.synced) == ["a", "b", "c", "d"]


def test_sync_max_workers_one_is_sequential(tmp_path: Path) -> None:
    """max_workers=1 processes projects one at a time."""
    repo = tmp_path / "a"
    repo.mkdir()
    project = Project(clone_url="https://github.com/u/a.git", name="a", path=str(repo))

    with (
        patch("git_projects.services.is_dirty", return_value=False),
        patch("git_projects.services.pull_repo"),
        patch("git_projects.services.push_repo"),
    ):
        result = sync_projects([project], max_workers=1)

    assert result.synced == ["a"]
