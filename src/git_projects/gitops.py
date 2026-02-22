from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git subprocess returns non-zero."""


def _expand(path: str) -> Path:
    return Path(path).expanduser()


def is_dirty(path: str) -> bool:
    """Return True if the repo has uncommitted changes or untracked files."""
    result = subprocess.run(
        ["git", "-C", str(_expand(path)), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def clone_repo(url: str, path: str) -> None:
    """Clone *url* into *path*, creating parent directories as needed."""
    expanded = _expand(path)
    expanded.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", url, str(expanded)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(result.stderr)


def pull_repo(path: str) -> None:
    """Pull the current branch in *path*."""
    result = subprocess.run(
        ["git", "-C", str(_expand(path)), "pull"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(result.stderr)


def push_repo(path: str) -> None:
    """Push the current branch in *path* to its configured upstream."""
    result = subprocess.run(
        ["git", "-C", str(_expand(path)), "push"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(result.stderr)
