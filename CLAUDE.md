# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**git-projects** is a CLI tool that provides a unified history view across multiple Git foundries (GitHub, GitLab, Gitea). Local-first, config-driven, no daemon.

## Commands

```bash
uv run invoke lint      # ruff check + ruff format --check + mypy
uv run invoke format    # ruff format src tests
uv run invoke test      # pytest with coverage
uv run invoke venv      # uv sync --group dev
uv run invoke clean     # git clean preview

# Run a single test
uv run pytest tests/test_config.py -v
uv run pytest tests/test_cli.py::test_fetch_github -v
```

## Architecture

```
CLI (typer) → Config (YAML) → Services (orchestration)
                                    ↓
                           Foundry Clients (GitHub, Gitea)
```

- **cli.py** — typer commands: `config init/show`, `fetch`, `track`, `untrack`, `list`, `sync`, `history`, `export`, `import`
- **config.py** — YAML config r/w + JSON project list r/w, dataclasses (`Config`, `FoundryConfig`, `Project`), path via `platformdirs`
- **services.py** — business logic: `fetch_repos()`, `track_project()`, `untrack_project()`, `export_projects()`, `import_projects()`
- **foundry/github.py**, **foundry/gitea.py** — API clients with Link-header pagination
- **foundry/__init__.py** — shared `RemoteRepo` dataclass
- **formatting.py** — ANSI terminal output via `typer.style()`

Storage at `$XDG_DATA_HOME/git-projects/`:
- `config.yaml` — settings + foundry credentials (never shared)
- `projects.json` — tracked projects with paths relative to `clone_root` (portable, no secrets)
- `index.json` — ephemeral cache of remote repo metadata

## Design Decisions

- Shell out to git (not GitPython)
- YAML config (not SQLite) — human-readable, hand-editable; projects in separate JSON (portable, no secrets)
- httpx (not requests) — modern, typed, HTTP/2
- Dataclasses + functions (no classes where unnecessary, no Pydantic)
- ANSI colors via typer (no rich, no tables)
- Explicit tracking only (no auto-track heuristics)

## Code Conventions

- Python 3.12+, full type hints (PEP 604)
- ruff format (100-char lines), ruff check, mypy strict on `src/`
- One-liner docstrings for non-trivial functions
- Tests use `pytest` + `monkeypatch`, `httpx` mocks (no external API calls), `tmp_path` for file I/O, `typer.testing.CliRunner` for CLI tests

## Incomplete Features

- `sync` command — needs a `gitops` module for clone/pull operations
- `history` command — declared but not implemented
- `export` / `import` commands — not yet implemented
- **Migration**: existing `config.yaml` with `projects: []` needs migration to split `projects.json`
