from __future__ import annotations

import re
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

    @property
    def slug(self) -> str:
        """URL-safe identifier derived from name: lowercase, non-alphanumeric runs → hyphens."""
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
