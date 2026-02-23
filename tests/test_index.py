from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from git_projects.foundry import RemoteRepo
from git_projects.index import load_index, save_index, search_index


def _ts(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%SZ")


_REPOS = [
    RemoteRepo(
        name="proj-a",
        repo_url="https://github.com/user/proj-a",
        clone_url="git@github.com:user/proj-a.git",
        pushed_at=_ts(timedelta(days=10)),
        default_branch="main",
        visibility="public",
        description="Alpha project",
    ),
    RemoteRepo(
        name="proj-b",
        repo_url="https://github.com/user/proj-b",
        clone_url="git@github.com:user/proj-b.git",
        pushed_at=_ts(timedelta(days=90)),
        default_branch="main",
        visibility="private",
        description="Beta project",
    ),
    RemoteRepo(
        name="old-thing",
        repo_url="https://github.com/user/old-thing",
        clone_url="git@github.com:user/old-thing.git",
        pushed_at=_ts(timedelta(days=400)),
        default_branch="main",
        visibility="public",
        description="Ancient experiment",
    ),
]


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    index_path = tmp_path / "index.json"
    monkeypatch.setattr("git_projects.index.get_index_path", lambda: index_path)

    save_index(_REPOS)
    loaded = load_index()

    assert len(loaded) == 3
    assert loaded[0].name == "proj-a"
    assert loaded[0].clone_url == "git@github.com:user/proj-a.git"
    assert loaded[2].name == "old-thing"


def test_load_index_returns_empty_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("git_projects.index.get_index_path", lambda: tmp_path / "nonexistent.json")
    assert load_index() == []


def test_search_index_no_filter() -> None:
    result = search_index(_REPOS, max_age_days=None)
    assert len(result) == 3


def test_search_index_filters_by_query_name() -> None:
    result = search_index(_REPOS, "proj-a", max_age_days=None)
    assert len(result) == 1
    assert result[0].name == "proj-a"


def test_search_index_filters_by_query_description() -> None:
    result = search_index(_REPOS, "ancient", max_age_days=None)
    assert len(result) == 1
    assert result[0].name == "old-thing"


def test_search_index_query_is_case_insensitive() -> None:
    result = search_index(_REPOS, "ALPHA", max_age_days=None)
    assert len(result) == 1
    assert result[0].name == "proj-a"


def test_search_index_filters_by_age() -> None:
    result = search_index(_REPOS, max_age_days=180)
    names = [r.name for r in result]
    assert "proj-a" in names
    assert "proj-b" in names
    assert "old-thing" not in names


def test_search_index_age_none_shows_all() -> None:
    result = search_index(_REPOS, max_age_days=None)
    assert len(result) == 3


def test_search_index_combined_query_and_age() -> None:
    result = search_index(_REPOS, "proj", max_age_days=180)
    names = [r.name for r in result]
    assert "proj-a" in names
    assert "proj-b" in names
    assert "old-thing" not in names
