from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RemoteRepo:
    name: str
    repo_url: str
    clone_url: str
    pushed_at: str
    default_branch: str
    visibility: str
    description: str
