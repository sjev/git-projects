# type: ignore
import os

from invoke import task


@task
def venv(c):
    """Sync dependencies."""
    c.run("uv sync --group dev")


@task
def format(c):
    """Format code."""
    c.run("uv run ruff format src tests")


@task
def lint(c):
    """Run linters."""
    c.run("uv run ruff check src tests")
    c.run("uv run ruff format --check src tests")
    c.run("uv run mypy src")


@task
def test(c):
    """Run tests with coverage."""
    c.run("uv run pytest --cov=src --cov-report=term-missing")


@task
def clean(c):
    """Preview files to delete (safe mode)."""
    c.run("git clean -nfdx")
    if input("Delete? [y/N] ").lower() == "y":
        c.run("git clean -fdx")


@task(help={"part": "Version part to bump: major, minor, or patch"})
def bump(c, part="patch"):
    """Bump project version."""
    c.run(f"uv run bump-my-version bump {part}")

@task
def publish(c):
    """Publish package to PyPI."""

    # get token
    token = os.getenv("PYPI_TOKEN")
    if not token:
        print("PYPI_TOKEN environment variable not set.")
        return

    c.run("uv build")
    c.run(f"uv publish --token {token}")
