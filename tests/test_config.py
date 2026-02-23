from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from git_projects.config import (
    DEFAULT_CONFIG,
    Config,
    FoundryConfig,
    Project,
    derive_project,
    get_projects_path,
    load_config,
    load_projects,
    save_config,
    save_projects,
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
clone_url_format: https
foundries:
  - name: github
    type: github
    url: https://api.github.com
    token: mytoken
""",
    )
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    config = load_config()

    assert isinstance(config, Config)
    assert config.clone_root == "~/projects"
    assert config.clone_url_format == "https"
    assert len(config.foundries) == 1
    foundry = config.foundries[0]
    assert isinstance(foundry, FoundryConfig)
    assert foundry.name == "github"
    assert foundry.token == "mytoken"


def test_load_config_clone_url_format_defaults_to_ssh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """clone_url_format absent → defaults to 'ssh'."""
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, "clone_root: ~/projects\nfoundries: []\n")
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    config = load_config()

    assert config.clone_url_format == "ssh"


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
    )
    save_config(original)

    loaded = load_config()
    assert loaded.clone_root == original.clone_root
    assert len(loaded.foundries) == 1
    assert loaded.foundries[0].name == "github"


def test_save_config_writes_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.config.get_config_path", lambda: config_path)

    save_config(Config(clone_root="~/x", foundries=[]))

    data = yaml.safe_load(config_path.read_text())
    assert data["clone_root"] == "~/x"
    assert data["clone_url_format"] == "ssh"
    assert "projects" not in data  # AC-03: no projects key written


def test_default_config_contains_clone_url_format() -> None:
    """AC-02: DEFAULT_CONFIG template includes clone_url_format: ssh."""
    assert "clone_url_format: ssh" in DEFAULT_CONFIG


def test_default_config_has_no_projects_key() -> None:
    """AC-02: DEFAULT_CONFIG does not contain a projects key."""
    data = yaml.safe_load(DEFAULT_CONFIG)
    assert "projects" not in data


# --- load_projects / save_projects ---


def test_load_projects_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-04: returns empty list when projects.json does not exist."""
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: tmp_path / "projects.json")

    result = load_projects()

    assert result == []


def test_load_projects_returns_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-04: parses projects.json into list[Project]."""
    projects_path = tmp_path / "projects.json"
    projects_path.write_text(
        json.dumps([{"clone_url": "https://github.com/u/repo.git", "name": "repo", "path": "repo"}])
    )
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    result = load_projects()

    assert len(result) == 1
    assert result[0].name == "repo"
    assert result[0].path == "repo"
    assert result[0].clone_url == "https://github.com/u/repo.git"


def test_save_projects_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-05: save then load returns the same list."""
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    projects = [
        Project(clone_url="https://github.com/u/a.git", name="a", path="a"),
        Project(clone_url="https://github.com/u/b.git", name="b", path="b"),
    ]
    save_projects(projects)
    loaded = load_projects()

    assert len(loaded) == 2
    assert loaded[0].name == "a"
    assert loaded[1].name == "b"


def test_save_projects_creates_parent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-05: save_projects creates parent directories if needed."""
    projects_path = tmp_path / "nested" / "dir" / "projects.json"
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    returned = save_projects([])

    assert projects_path.exists()
    assert returned == projects_path


def test_save_projects_json_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-06: projects.json uses the expected field names and indent=2."""
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr("git_projects.config.get_projects_path", lambda: projects_path)

    save_projects(
        [Project(clone_url="https://github.com/user/repo-a.git", name="repo-a", path="repo-a")]
    )

    data = json.loads(projects_path.read_text())
    assert data == [
        {"clone_url": "https://github.com/user/repo-a.git", "name": "repo-a", "path": "repo-a"}
    ]
    # indent=2 — file should contain newlines
    assert "\n" in projects_path.read_text()


def test_get_projects_path_returns_path() -> None:
    """get_projects_path returns a Path ending in projects.json."""
    p = get_projects_path()
    assert isinstance(p, Path)
    assert p.name == "projects.json"


# --- derive_project ---


def test_derive_project_github() -> None:
    """AC-07: HTTPS URL — path equals name only."""
    project = derive_project("https://github.com/user/my-repo.git")
    assert project.name == "my-repo"
    assert project.clone_url == "https://github.com/user/my-repo.git"
    assert project.path == "my-repo"


def test_derive_project_gitlab() -> None:
    """AC-07: nested path — last segment only."""
    project = derive_project("https://gitlab.com/org/sub/repo.git")
    assert project.name == "repo"
    assert project.path == "repo"


def test_derive_project_no_git_suffix() -> None:
    project = derive_project("https://github.com/user/repo")
    assert project.name == "repo"
    assert project.path == "repo"


def test_derive_project_ssh_scp_style() -> None:
    """AC-07: SCP-style SSH URL correctly extracts name; path == name."""
    project = derive_project("git@github.com:user/my-repo.git")
    assert project.name == "my-repo"
    assert project.clone_url == "git@github.com:user/my-repo.git"
    assert project.path == "my-repo"


def test_derive_project_ssh_nested_path() -> None:
    """AC-07: SSH URL with org/repo extracts last segment."""
    project = derive_project("git@gitea.host:org/sub/repo.git")
    assert project.name == "repo"
    assert project.path == "repo"
