from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from git_projects.formatting import format_repo, relative_time
from git_projects.foundry import RemoteRepo

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
    clone_url="https://github.com/user/my-app.git",
    pushed_at=_ts(timedelta(days=3)),
    default_branch="main",
    visibility="public",
    description="A web application for managing tasks",
)


def test_format_repo_contains_name_and_url() -> None:
    out = format_repo(_REPO)
    assert "  my-app\n" in out
    assert "  https://github.com/user/my-app.git\n" in out


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
        clone_url="u",
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
        clone_url="u",
        pushed_at=_ts(timedelta(days=1)),
        default_branch="main",
        visibility="public",
        description="",
    )
    lines = [ln for ln in format_repo(repo).splitlines() if ln.strip()]
    assert len(lines) == 3  # name, url, time — no description line


def test_format_repo_ends_with_newline() -> None:
    assert format_repo(_REPO).endswith("\n")
