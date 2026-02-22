from __future__ import annotations

from typer.testing import CliRunner

from git_projects.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_hello() -> None:
    result = runner.invoke(app, ["hello", "--name", "Ada"])
    assert result.exit_code == 0
    assert "Hello, Ada!" in result.output
