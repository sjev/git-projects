# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --group dev       # install dependencies
inv lint                  # ruff check + format check + mypy
inv test                  # pytest with coverage
inv format                # auto-format with ruff

uv run pytest tests/test_cli.py::test_name -s   # run a single test
```

After any code change: run `inv lint` then `inv test`.

## Architecture

CLI tool (`gpr`) that discovers, tracks, and syncs git repos across GitHub, GitLab, and Gitea.

**Entry point**: `src/git_projects/cli.py` — typer app, commands: `config init/show`, `fetch`, `list`, `track`, `untrack`, `sync`.

**Data flow**:
- `fetch` → foundry API clients → `index.save_index()` (caches to `index.json`)
- `list` → `index.load_index()` + `config.load_projects()` → `formatting.py`
- `track` → index lookup by name/slug → `config.add_project()`
- `sync` → `config.load_projects()` → `gitops.clone_repo()` / `gitops.pull_repo()`

**Storage** (`$XDG_DATA_HOME/git-projects/`):
- `config.yaml` — foundry credentials + `clone_root` + `clone_url_format` (ssh|https)
- `projects.json` — tracked projects (no secrets, portable)
- `index.json` — ephemeral API cache from last `fetch`

**Key modules**:
- `foundry/` — one submodule per API type (`github.py`, `gitlab.py`, `gitea.py`), each exposes `list_repos(config, clone_url_format) -> list[RemoteRepo]`
- `foundry/__init__.py` — shared `RemoteRepo` dataclass with computed `slug` property
- `config.py` — `Config`, `FoundryConfig`, `Project` dataclasses; reads/writes yaml + json
- `index.py` — `save_index`, `load_index`, `search_index`
- `services.py` — orchestration logic called by CLI commands
- `formatting.py` — ANSI terminal output via `typer.style()` (no rich/tables)
- `gitops.py` — shells out to `git` for clone/pull

**Conventions**:
- No classes where function + dataclass suffices; no Pydantic
- Project `path` stored relative to `clone_root`, resolved at runtime
- `track` lookup order: exact name → exact slug → partial name → partial slug
- Strict mypy; PEP 604 union syntax (`X | Y`)

## Docs

- `docs/architecture.md` — authoritative design document and module boundaries
- `docs/user-stories.md` — user requirements
