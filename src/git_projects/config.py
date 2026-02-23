from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml
from platformdirs import user_data_path

DEFAULT_CONFIG = """\
clone_root: ~/projects    # where repos get cloned
clone_url_format: ssh     # "https" or "ssh"
foundries:
  - name: github
    type: github
    token: ""              # paste your token here
  # - name: my-gitlab
  #   type: gitlab
  #   token: ""
  # - name: my-gitea
  #   type: gitea
  #   url: https://gitea.example.com
  #   token: ""
"""

_SSH_RE = re.compile(r"^git@[^:]+:(.+)$")


@dataclass
class FoundryConfig:
    name: str
    type: str
    token: str
    url: str | None = None


@dataclass
class Project:
    clone_url: str
    name: str
    path: str


@dataclass
class Config:
    clone_root: str
    foundries: list[FoundryConfig]
    clone_url_format: str = "ssh"


class ConfigExistsError(Exception):
    """Raised when config.yaml already exists and force=False."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Config already exists at {path}. Use --force to overwrite.")
        self.path = path


def get_config_path() -> Path:
    """Return the absolute path to config.yaml (may not exist yet)."""
    return user_data_path("git-projects") / "config.yaml"


def init_config(*, force: bool = False) -> Path:
    """Create default config.yaml and return its path."""
    config_path = get_config_path()
    if config_path.exists() and not force:
        raise ConfigExistsError(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG)
    return config_path


def load_config() -> Config:
    """Load and parse config.yaml."""
    config_path = get_config_path()
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    raw = yaml.safe_load(config_path.read_text())
    foundries = [
        FoundryConfig(
            name=str(f["name"]),
            type=str(f["type"]),
            token=str(f.get("token", "")),
            url=f.get("url") or None,
        )
        for f in raw.get("foundries", [])
    ]
    return Config(
        clone_root=str(raw.get("clone_root", "")),
        foundries=foundries,
        clone_url_format=str(raw.get("clone_url_format", "ssh")),
    )


def save_config(config: Config) -> Path:
    """Write config to config.yaml and return its path."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "clone_root": config.clone_root,
        "clone_url_format": config.clone_url_format,
        "foundries": [
            {
                k: v
                for k, v in {"name": f.name, "type": f.type, "token": f.token, "url": f.url}.items()
                if v is not None
            }
            for f in config.foundries
        ],
    }
    config_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    return config_path


def get_projects_path() -> Path:
    """Return the absolute path to projects.json (may not exist yet)."""
    return user_data_path("git-projects") / "projects.json"


def load_projects() -> list[Project]:
    """Load tracked projects from projects.json. Returns [] if file missing."""
    projects_path = get_projects_path()
    if not projects_path.exists():
        return []
    raw = json.loads(projects_path.read_text())
    return [
        Project(
            clone_url=str(p["clone_url"]),
            name=str(p["name"]),
            path=str(p["path"]),
        )
        for p in raw
    ]


def save_projects(projects: list[Project]) -> Path:
    """Write projects list to projects.json and return its path."""
    projects_path = get_projects_path()
    projects_path.parent.mkdir(parents=True, exist_ok=True)
    projects_path.write_text(
        json.dumps(
            [{"clone_url": p.clone_url, "name": p.name, "path": p.path} for p in projects],
            indent=2,
        )
    )
    return projects_path


def derive_project(clone_url: str) -> Project:
    """Derive project name and relative path from a clone URL (HTTPS or SSH SCP-style)."""
    m = _SSH_RE.match(clone_url)
    path_part = m.group(1) if m else urlparse(clone_url).path
    name = path_part.strip("/").removesuffix(".git").split("/")[-1]
    return Project(clone_url=clone_url, name=name, path=name)
