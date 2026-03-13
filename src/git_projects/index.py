from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_data_path

from git_projects.foundry import RemoteRepo


def get_index_path() -> Path:
    """Return the absolute path to index.json (may not exist yet)."""
    return user_data_path("git-projects") / "index.json"


def save_index(repos: list[RemoteRepo]) -> Path:
    """Write repos to index.json and return its path."""
    path = get_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "repos": [
            {
                "name": r.name,
                "repo_url": r.repo_url,
                "clone_url": r.clone_url,
                "pushed_at": r.pushed_at,
                "default_branch": r.default_branch,
                "visibility": r.visibility,
                "description": r.description,
            }
            for r in repos
        ],
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def load_index() -> list[RemoteRepo]:
    """Load repos from index.json. Returns empty list if index does not exist."""
    path = get_index_path()
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [
        RemoteRepo(
            name=r["name"],
            repo_url=r["repo_url"],
            clone_url=r["clone_url"],
            pushed_at=r["pushed_at"],
            default_branch=r["default_branch"],
            visibility=r["visibility"],
            description=r["description"],
        )
        for r in raw.get("repos", [])
    ]


def search_index(
    repos: list[RemoteRepo],
    query: str | None = None,
) -> list[RemoteRepo]:
    """Filter repos by optional name/description query."""
    result = repos
    if query:
        q = query.lower()
        result = [
            r for r in result if q in r.name.lower() or q in r.slug or q in r.description.lower()
        ]
    return sorted(result, key=lambda r: r.pushed_at)
