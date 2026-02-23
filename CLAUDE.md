# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**git-projects** is a CLI tool that discovers, tracks, and syncs Git repositories across multiple foundries (GitHub, GitLab, Gitea). Local-first, config-driven, no daemon.

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
                           Foundry Clients (GitHub, GitLab, Gitea)
                                    ↓
                           Index (JSON cache) ← → GitOps (git subprocess)
```

- **cli.py** — typer commands: `config init/show`, `remote fetch/list`, `track`, `untrack`, `list`, `sync`, `info`
- **config.py** — YAML config r/w + JSON project list r/w, dataclasses (`Config`, `FoundryConfig`, `Project`), path via `platformdirs`
- **services.py** — business logic: `fetch_repos()`, `track_project()`, `untrack_project()`, `sync_projects()`
- **index.py** — local index of remote repos: `save_index()`, `load_index()`, `search_index()`
- **gitops.py** — git subprocess wrappers: `clone_repo()`, `pull_repo()`, `push_repo()`, `is_dirty()`
- **foundry/github.py**, **foundry/gitea.py**, **foundry/gitlab.py** — API clients with Link-header pagination
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
