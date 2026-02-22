from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml
from platformdirs import user_data_path

DEFAULT_CONFIG = """\
clone_root: ~/projects    # where repos get cloned
foundries:
  - name: github
    type: github
    url: https://api.github.com
    token: ""              # paste your token here
  # - name: my-gitlab
  #   type: gitlab
  #   url: https://gitlab.com
  #   token: ""
  # - name: my-gitea
  #   type: gitea
  #   url: https://gitea.example.com
  #   token: ""
projects: []
"""


@dataclass
class FoundryConfig:
    name: str
    type: str
    url: str
    token: str


@dataclass
class Project:
    clone_url: str
    name: str
    path: str


@dataclass
class Config:
    clone_root: str
    foundries: list[FoundryConfig]
    projects: list[Project] = field(default_factory=list)


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
            url=str(f["url"]),
            token=str(f.get("token", "")),
        )
        for f in raw.get("foundries", [])
    ]
    projects = [
        Project(
            clone_url=str(p["clone_url"]),
            name=str(p["name"]),
            path=str(p["path"]),
        )
        for p in raw.get("projects", []) or []
    ]
    return Config(
        clone_root=str(raw.get("clone_root", "")),
        foundries=foundries,
        projects=projects,
    )


def save_config(config: Config) -> Path:
    """Write config to config.yaml and return its path."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "clone_root": config.clone_root,
        "foundries": [
            {"name": f.name, "type": f.type, "url": f.url, "token": f.token}
            for f in config.foundries
        ],
        "projects": [
            {"clone_url": p.clone_url, "name": p.name, "path": p.path} for p in config.projects
        ],
    }
    config_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    return config_path


def derive_project(clone_url: str, clone_root: str) -> Project:
    """Derive project name and path from a clone URL."""
    parsed = urlparse(clone_url)
    path_parts = parsed.path.strip("/").removesuffix(".git").split("/")
    name = path_parts[-1]
    hostname = parsed.hostname or "unknown"
    local_path = str(Path(clone_root) / hostname / "/".join(path_parts))
    return Project(clone_url=clone_url, name=name, path=local_path)
