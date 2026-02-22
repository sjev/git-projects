from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from git_projects.gitops import GitError, clone_repo, is_dirty, pull_repo, push_repo


def _ok(stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = ""
    return m


def _fail(stderr: str = "fatal: error") -> MagicMock:
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = stderr
    return m


# --- is_dirty ---


def test_is_dirty_returns_true_when_output() -> None:
    with patch("subprocess.run", return_value=_ok(" M file.py\n")) as mock_run:
        assert is_dirty("/repo") is True
    mock_run.assert_called_once_with(
        ["git", "-C", "/repo", "status", "--porcelain"],
        capture_output=True,
        text=True,
    )


def test_is_dirty_returns_false_when_empty() -> None:
    with patch("subprocess.run", return_value=_ok("")) as mock_run:
        assert is_dirty("/repo") is False
    mock_run.assert_called_once()


def test_is_dirty_expands_tilde(tmp_path: Path) -> None:
    with patch("subprocess.run", return_value=_ok("")) as mock_run:
        is_dirty("~/repo")
    args = mock_run.call_args[0][0]
    assert "~" not in args[2]  # expanded path is arg at index 2 (-C <path>)


# --- clone_repo ---


def test_clone_repo_runs_git_clone(tmp_path: Path) -> None:
    target = str(tmp_path / "myrepo")
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        clone_repo("https://example.com/repo.git", target)
    mock_run.assert_called_once_with(
        ["git", "clone", "https://example.com/repo.git", target],
        capture_output=True,
        text=True,
    )


def test_clone_repo_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "myrepo"
    with patch("subprocess.run", return_value=_ok()):
        clone_repo("https://example.com/repo.git", str(target))
    assert target.parent.exists()


def test_clone_repo_raises_git_error_on_failure(tmp_path: Path) -> None:
    target = str(tmp_path / "myrepo")
    with (
        patch("subprocess.run", return_value=_fail("fatal: repository not found")),
        pytest.raises(GitError, match="repository not found"),
    ):
        clone_repo("https://example.com/repo.git", target)


def test_clone_repo_expands_tilde() -> None:
    with (
        patch("subprocess.run", return_value=_ok()) as mock_run,
        patch("pathlib.Path.mkdir"),
    ):
        clone_repo("https://example.com/repo.git", "~/projects/repo")
    args = mock_run.call_args[0][0]
    assert "~" not in args[3]  # expanded path is the last arg


# --- pull_repo ---


def test_pull_repo_runs_git_pull() -> None:
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        pull_repo("/repo")
    mock_run.assert_called_once_with(
        ["git", "-C", "/repo", "pull"],
        capture_output=True,
        text=True,
    )


def test_pull_repo_raises_git_error_on_failure() -> None:
    with (
        patch("subprocess.run", return_value=_fail("merge conflict")),
        pytest.raises(GitError, match="merge conflict"),
    ):
        pull_repo("/repo")


def test_pull_repo_expands_tilde() -> None:
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        pull_repo("~/repo")
    args = mock_run.call_args[0][0]
    assert "~" not in args[2]


# --- push_repo ---


def test_push_repo_runs_git_push() -> None:
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        push_repo("/repo")
    mock_run.assert_called_once_with(
        ["git", "-C", "/repo", "push"],
        capture_output=True,
        text=True,
    )


def test_push_repo_raises_git_error_on_failure() -> None:
    with (
        patch("subprocess.run", return_value=_fail("no upstream")),
        pytest.raises(GitError, match="no upstream"),
    ):
        push_repo("/repo")


def test_push_repo_expands_tilde() -> None:
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        push_repo("~/repo")
    args = mock_run.call_args[0][0]
    assert "~" not in args[2]
