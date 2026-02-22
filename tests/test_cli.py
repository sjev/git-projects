from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_projects.cli import app
from git_projects.registry import DEFAULT_CONFIG

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip()


# AC-09: bare `config` shows help listing init and show
def test_config_no_subcommand_shows_help() -> None:
    result = runner.invoke(app, ["config"])
    # Typer exits with code 2 (Click "missing command") when no_args_is_help=True on sub-apps
    assert result.exit_code in {0, 2}
    assert "init" in result.output
    assert "show" in result.output


# AC-01, AC-02, AC-03, AC-06: first-time init creates dir + file, prints path
def test_config_init_creates_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0
    assert config_path.exists()
    assert config_path.parent.is_dir()
    assert str(config_path) in result.output
    assert config_path.read_text() == DEFAULT_CONFIG


# AC-04: init when config exists exits 1 without modifying the file
def test_config_init_refuses_if_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    original = "existing content"
    config_path.write_text(original)
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert config_path.read_text() == original  # file untouched


# AC-05: init --force overwrites existing config and prints path
def test_config_init_force_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("old content")
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "init", "--force"])

    assert result.exit_code == 0
    assert str(config_path) in result.output
    assert config_path.read_text() == DEFAULT_CONFIG


# AC-07: show prints path on first line then file contents
def test_config_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(DEFAULT_CONFIG)
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == str(config_path)
    assert DEFAULT_CONFIG.strip() in result.output


# AC-08: show with no config exits 1 and tells user to run init
def test_config_show_no_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "git-projects" / "config.yaml"
    monkeypatch.setattr("git_projects.registry.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    assert "config init" in result.output
