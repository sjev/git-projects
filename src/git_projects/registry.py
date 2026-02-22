from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
"""


@dataclass
class FoundryConfig:
    name: str
    type: str
    url: str
    token: str


@dataclass
class Config:
    clone_root: str
    foundries: list[FoundryConfig]


@dataclass
class Repo:
    name: str
    clone_url: str
    foundry: str
    pushed_at: str
    default_branch: str
    visibility: str
    description: str


@dataclass
class Registry:
    repos: list[Repo]


class ConfigExistsError(Exception):
    """Raised when config.yaml already exists and force=False."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Config already exists at {path}. Use --force to overwrite.")
        self.path = path


def get_config_path() -> Path:
    """Return the absolute path to config.yaml (may not exist yet)."""
    return user_data_path("git-projects") / "config.yaml"


def get_registry_path() -> Path:
    """Return the absolute path to registry.yaml (may not exist yet)."""
    return user_data_path("git-projects") / "registry.yaml"


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
    return Config(clone_root=str(raw.get("clone_root", "")), foundries=foundries)


def save_registry(registry: Registry) -> Path:
    """Write registry to registry.yaml sorted by pushed_at descending and return its path."""
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_repos = sorted(registry.repos, key=lambda r: r.pushed_at, reverse=True)
    data = {
        "repos": [
            {
                "name": repo.name,
                "clone_url": repo.clone_url,
                "foundry": repo.foundry,
                "pushed_at": repo.pushed_at,
                "default_branch": repo.default_branch,
                "visibility": repo.visibility,
                "description": repo.description,
            }
            for repo in sorted_repos
        ]
    }
    registry_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    return registry_path
