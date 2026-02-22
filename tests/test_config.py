from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from git_projects.config import (
    Config,
    FoundryConfig,
    Project,
    derive_project,
    load_config,
    save_config,
)


def _write_config(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# --- load_config ---


def test_load_config_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """\
clone_root: ~/projects
foundries:
  - name: github
    type: github
    url: https://api.github.com
    token: mytoken
projects:
  - clone_url: https://github.com/user/repo-a.git
    name: repo-a
    path: ~/projects/github.com/user/repo-a
""",
    )
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    config = load_config()

    assert isinstance(config, Config)
    assert config.clone_root == "~/projects"
    assert len(config.foundries) == 1
    foundry = config.foundries[0]
    assert isinstance(foundry, FoundryConfig)
    assert foundry.name == "github"
    assert foundry.token == "mytoken"
    assert len(config.projects) == 1
    assert config.projects[0].name == "repo-a"
    assert config.projects[0].clone_url == "https://github.com/user/repo-a.git"


def test_load_config_empty_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """\
clone_root: ~/projects
foundries:
  - name: github
    type: github
    url: https://api.github.com
    token: ""
projects: []
""",
    )
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    config = load_config()

    assert config.projects == []


def test_load_config_missing_projects_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Config without projects key loads with empty list."""
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """\
clone_root: ~/projects
foundries:
  - name: github
    type: github
    url: https://api.github.com
    token: ""
""",
    )
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    config = load_config()

    assert config.projects == []


def test_load_config_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    with pytest.raises(FileNotFoundError):
        load_config()


# --- save_config ---


def test_save_config_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    original = Config(
        clone_root="~/projects",
        foundries=[
            FoundryConfig(name="github", type="github", url="https://api.github.com", token="tok")
        ],
        projects=[
            Project(
                clone_url="https://github.com/user/repo-a.git",
                name="repo-a",
                path="~/projects/github.com/user/repo-a",
            ),
        ],
    )
    save_config(original)

    loaded = load_config()
    assert loaded.clone_root == original.clone_root
    assert len(loaded.foundries) == 1
    assert loaded.foundries[0].name == "github"
    assert len(loaded.projects) == 1
    assert loaded.projects[0].clone_url == "https://github.com/user/repo-a.git"


def test_save_config_writes_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    save_config(Config(clone_root="~/x", foundries=[], projects=[]))

    data = yaml.safe_load(config_path.read_text())
    assert data["clone_root"] == "~/x"
    assert data["projects"] == []


# --- derive_project ---


def test_derive_project_github() -> None:
    project = derive_project("https://github.com/user/my-repo.git", "~/projects")
    assert project.name == "my-repo"
    assert project.clone_url == "https://github.com/user/my-repo.git"
    assert project.path == "~/projects/github.com/user/my-repo"


def test_derive_project_gitlab() -> None:
    project = derive_project("https://gitlab.com/org/sub/repo.git", "~/projects")
    assert project.name == "repo"
    assert project.path == "~/projects/gitlab.com/org/sub/repo"


def test_derive_project_no_git_suffix() -> None:
    project = derive_project("https://github.com/user/repo", "~/projects")
    assert project.name == "repo"
    assert project.path == "~/projects/github.com/user/repo"
