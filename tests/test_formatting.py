from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from git_projects.formatting import format_repo, relative_time
from git_projects.foundry import RemoteRepo


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


# --- relative_time ---


def _ts(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=30), "just now"),
        (timedelta(seconds=59), "just now"),
        (timedelta(minutes=5), "5 minutes ago"),
        (timedelta(hours=3), "3 hours ago"),
        (timedelta(days=2), "2 days ago"),
        (timedelta(days=90), "3 months ago"),
        (timedelta(days=400), "1 years ago"),
    ],
)
def test_relative_time(delta: timedelta, expected: str) -> None:
    assert relative_time(_ts(delta)) == expected


def test_relative_time_invalid() -> None:
    with pytest.raises(ValueError):
        relative_time("not-a-timestamp")


# --- format_repo ---

_REPO = RemoteRepo(
    name="my-app",
    repo_url="https://github.com/user/my-app",
    clone_url="git@github.com:user/my-app.git",
    pushed_at=_ts(timedelta(days=3)),
    default_branch="main",
    visibility="public",
    description="A web application for managing tasks",
)


def test_format_repo_contains_name_and_urls() -> None:
    out = _strip_ansi(format_repo(_REPO))
    assert "my-app" in out
    assert "https://github.com/user/my-app" in out
    assert "git@github.com:user/my-app.git" in out


def test_format_repo_contains_relative_time() -> None:
    out = format_repo(_REPO)
    assert "3 days ago" in out


def test_format_repo_description_shown_when_short() -> None:
    out = format_repo(_REPO)
    assert "A web application for managing tasks" in out


def test_format_repo_description_truncated_at_60() -> None:
    long_desc = "x" * 65
    repo = RemoteRepo(
        name="r",
        repo_url="https://host.com/r",
        clone_url="git@host.com:r.git",
        pushed_at=_ts(timedelta(days=1)),
        default_branch="main",
        visibility="public",
        description=long_desc,
    )
    out = format_repo(repo)
    assert out.count("x") == 59
    assert "…" in out


def test_format_repo_no_description_line_when_empty() -> None:
    repo = RemoteRepo(
        name="r",
        repo_url="https://example.com/r",
        clone_url="git@example.com:r.git",
        pushed_at=_ts(timedelta(days=1)),
        default_branch="main",
        visibility="public",
        description="",
    )
    lines = [ln for ln in _strip_ansi(format_repo(repo)).splitlines() if ln.strip()]
    assert len(lines) == 3  # name+vis+date, repo_url, clone_url


def test_format_repo_ends_with_newline() -> None:
    assert format_repo(_REPO).endswith("\n")


def test_format_repo_visibility_badge_public() -> None:
    out = _strip_ansi(format_repo(_REPO))
    assert "[public]" in out


def test_format_repo_visibility_badge_private() -> None:
    repo = RemoteRepo(
        name="secret",
        repo_url="https://github.com/user/secret",
        clone_url="git@github.com:user/secret.git",
        pushed_at=_ts(timedelta(days=1)),
        default_branch="main",
        visibility="private",
        description="",
    )
    out = _strip_ansi(format_repo(repo))
    assert "[private]" in out
