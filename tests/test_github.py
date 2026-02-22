from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from git_projects.config import FoundryConfig
from git_projects.foundry import RemoteRepo
from git_projects.foundry.github import _next_url, list_repos

FOUNDRY = FoundryConfig(name="github", type="github", url="https://api.github.com", token="tok")

_REPO_1 = {
    "name": "proj-a",
    "clone_url": "https://github.com/user/proj-a.git",
    "pushed_at": "2026-02-20T10:00:00Z",
    "default_branch": "main",
    "visibility": "public",
    "description": "First project",
}
_REPO_2 = {
    "name": "proj-b",
    "clone_url": "https://github.com/user/proj-b.git",
    "pushed_at": "2025-11-01T08:00:00Z",
    "default_branch": "main",
    "visibility": "private",
    "description": None,
}


_DUMMY_REQUEST = httpx.Request("GET", "https://api.github.com/user/repos")


def _make_response(
    data: list[dict[str, object]],
    *,
    link: str = "",
    status: int = 200,
) -> httpx.Response:
    response = httpx.Response(
        status_code=status,
        headers={"Link": link} if link else {},
        content=json.dumps(data).encode(),
    )
    response.request = _DUMMY_REQUEST
    return response


# --- _next_url ---


def test_next_url_present() -> None:
    header = '<https://api.github.com/user/repos?page=2>; rel="next", <https://api.github.com/user/repos?page=5>; rel="last"'
    assert _next_url(header) == "https://api.github.com/user/repos?page=2"


def test_next_url_absent() -> None:
    header = '<https://api.github.com/user/repos?page=1>; rel="first"'
    assert _next_url(header) is None


def test_next_url_empty() -> None:
    assert _next_url("") is None


# --- list_repos ---


def test_list_repos_empty_token_raises() -> None:
    """AC-06: empty token raises ValueError before any HTTP call."""
    foundry = FoundryConfig(name="github", type="github", url="https://api.github.com", token="")
    with pytest.raises(ValueError, match="token"):
        list_repos(foundry)


def test_list_repos_happy_path() -> None:
    """AC-01, AC-09, AC-10: returns repos with correct fields."""
    mock_response = _make_response([_REPO_1, _REPO_2])

    with patch("git_projects.foundry.github.httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        repos = list_repos(FOUNDRY)

    assert len(repos) == 2
    assert all(isinstance(r, RemoteRepo) for r in repos)

    a = repos[0]
    assert a.name == "proj-a"
    assert a.clone_url == "https://github.com/user/proj-a.git"  # AC-09
    assert a.pushed_at == "2026-02-20T10:00:00Z"
    assert a.default_branch == "main"
    assert a.visibility == "public"
    assert a.description == "First project"

    b = repos[1]
    assert b.description == ""  # AC-10: null → ""


def test_list_repos_pagination() -> None:
    """AC-04: follows pagination Link headers until exhausted."""
    page1 = _make_response(
        [_REPO_1],
        link='<https://api.github.com/user/repos?page=2>; rel="next"',
    )
    page2 = _make_response([_REPO_2])

    with patch("git_projects.foundry.github.httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = [page1, page2]

        repos = list_repos(FOUNDRY)

    assert len(repos) == 2
    assert mock_client.get.call_count == 2


def test_list_repos_auth_error_raises() -> None:
    """AC-07: 401 from API raises HTTPStatusError."""
    mock_response = _make_response([], status=401)

    with patch("git_projects.foundry.github.httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            list_repos(FOUNDRY)
