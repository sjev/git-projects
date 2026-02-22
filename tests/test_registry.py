from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from git_projects.registry import (
    Config,
    FoundryConfig,
    Registry,
    Repo,
    load_config,
    save_registry,
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
""",
    )
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    config = load_config()

    assert isinstance(config, Config)
    assert config.clone_root == "~/projects"
    assert len(config.foundries) == 1
    foundry = config.foundries[0]
    assert isinstance(foundry, FoundryConfig)
    assert foundry.name == "github"
    assert foundry.type == "github"
    assert foundry.url == "https://api.github.com"
    assert foundry.token == "mytoken"


def test_load_config_empty_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    config = load_config()

    assert config.foundries[0].token == ""


def test_load_config_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    with pytest.raises(FileNotFoundError):
        load_config()


# --- save_registry ---


def test_save_registry_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "registry.yaml"
    monkeypatch.setattr("git_projects.registry.get_registry_path", lambda: registry_path)

    repos = [
        Repo(
            name="proj",
            clone_url="https://github.com/user/proj.git",
            foundry="github",
            pushed_at="2026-02-20T10:00:00Z",
            default_branch="main",
            visibility="public",
            description="A project",
        )
    ]
    returned_path = save_registry(Registry(repos=repos))

    assert returned_path == registry_path
    assert registry_path.exists()


def test_save_registry_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-02: Each repo entry contains all required fields."""
    registry_path = tmp_path / "registry.yaml"
    monkeypatch.setattr("git_projects.registry.get_registry_path", lambda: registry_path)

    repo = Repo(
        name="my-proj",
        clone_url="https://github.com/user/my-proj.git",
        foundry="github",
        pushed_at="2026-02-20T10:00:00Z",
        default_branch="main",
        visibility="public",
        description="Cool",
    )
    save_registry(Registry(repos=[repo]))

    data = yaml.safe_load(registry_path.read_text())
    entry = data["repos"][0]
    assert entry["name"] == "my-proj"
    assert entry["clone_url"] == "https://github.com/user/my-proj.git"
    assert entry["foundry"] == "github"
    assert entry["pushed_at"] == "2026-02-20T10:00:00Z"
    assert entry["default_branch"] == "main"
    assert entry["visibility"] == "public"
    assert entry["description"] == "Cool"


def test_save_registry_sorted_newest_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-03: Repos are sorted by pushed_at descending."""
    registry_path = tmp_path / "registry.yaml"
    monkeypatch.setattr("git_projects.registry.get_registry_path", lambda: registry_path)

    repos = [
        Repo("old", "", "github", "2025-01-01T00:00:00Z", "main", "public", ""),
        Repo("new", "", "github", "2026-02-20T00:00:00Z", "main", "public", ""),
        Repo("mid", "", "github", "2025-06-15T00:00:00Z", "main", "public", ""),
    ]
    save_registry(Registry(repos=repos))

    data = yaml.safe_load(registry_path.read_text())
    names = [r["name"] for r in data["repos"]]
    assert names == ["new", "mid", "old"]


def test_save_registry_returns_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "registry.yaml"
    monkeypatch.setattr("git_projects.registry.get_registry_path", lambda: registry_path)

    result = save_registry(Registry(repos=[]))

    assert result == registry_path
