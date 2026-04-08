from __future__ import annotations

import subprocess
from pathlib import Path

GIT_TIMEOUT = 30


class GitError(Exception):
    """Raised when a git subprocess returns non-zero."""


def _expand(path: str) -> Path:
    return Path(path).expanduser()


def _run(cmd: list[str], timeout: int = GIT_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Run a git command with timeout, raising GitError on timeout or failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise GitError(result.stderr)
    return result


def is_dirty(path: str) -> bool:
    """Return True if the repo has uncommitted changes or untracked files."""
    result = _run(["git", "-C", str(_expand(path)), "status", "--porcelain"])
    return bool(result.stdout.strip())


def clone_repo(url: str, path: str) -> str:
    """Clone *url* into *path*, creating parent directories as needed."""
    expanded = _expand(path)
    expanded.parent.mkdir(parents=True, exist_ok=True)
    result = _run(["git", "clone", url, str(expanded)])
    return (result.stdout + result.stderr).strip()


def pull_repo(path: str) -> str:
    """Pull the current branch in *path*."""
    result = _run(["git", "-C", str(_expand(path)), "pull"])
    return (result.stdout + result.stderr).strip()


def push_repo(path: str) -> str:
    """Push the current branch in *path* to its configured upstream."""
    result = _run(["git", "-C", str(_expand(path)), "push"])
    return (result.stdout + result.stderr).strip()
