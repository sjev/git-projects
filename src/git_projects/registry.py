from __future__ import annotations

from pathlib import Path

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
