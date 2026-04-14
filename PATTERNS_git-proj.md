# Project Overview

This is a small, `src`-layout Python CLI application packaged as an installable tool. Architecturally it follows a thin-command-layer, function-oriented core: Typer handles argument parsing and UX, service functions orchestrate workflows, and focused modules own persistence, external API access, formatting, and subprocess-based system integration.

# Repository Structure

Core code lives under `src/git_projects/`. `cli.py` is the entry point and command registry, `services.py` is the orchestration layer, `config.py` and `index.py` own local file-backed state, `gitops.py` wraps `git` subprocess calls, `formatting.py` contains terminal presentation helpers, and `foundry/` contains one adapter module per external backend plus a shared normalized dataclass. This is a strong boundary between interface, orchestration, adapters, persistence, and presentation.

Top-level tooling and configuration are kept separate from core code. `pyproject.toml` owns packaging, dependencies, tool configuration, and CLI entry points. `tasks.py` is the developer task runner. `uv.lock` is the reproducibility artifact. `docs/` contains architecture and requirements documents rather than runtime code. `dist/` is build output, not source of truth.

Tests live in `tests/` and are organized by production module (`test_cli.py`, `test_config.py`, `test_services.py`, and so on). The structure mirrors the package, which makes ownership obvious and keeps tests close to module boundaries rather than grouped by test style.

# Configuration Pattern

Configuration is local-file based and stored under the XDG user data directory via `platformdirs.user_data_path("git-projects")`. The project deliberately splits state across three files: `config.yaml` for user-edited settings and secrets, `projects.json` for portable tracked-state, and `index.json` for ephemeral cache data. This separation prevents secrets from leaking into machine-portable artifacts and keeps each file’s purpose narrow.

Loading is explicit and function-based. `load_config()`, `load_projects()`, and `load_index()` parse files into dataclasses or normalized records. Defaults are encoded in code and in the default config template: for example `clone_url_format` falls back to `"ssh"` when absent. Missing optional state files return empty collections where that keeps the workflow smooth (`projects.json`, `index.json`), while missing required configuration raises immediately (`config.yaml`).

Overrides are intentionally minimal. The main control plane is the config file, with CLI arguments used for per-command behavior rather than long-term settings. Environment variables are not the primary configuration channel except for release publishing in developer tooling. The philosophy is local-first and human-editable rather than strict 12-factor configuration.

# CLI Design

The CLI uses Typer with one root app and one nested sub-app for grouped configuration commands. Commands are flat and task-oriented: `config init`, `config show`, plus top-level operational commands. Each command is a thin wrapper that parses arguments and options, loads required state, calls service or module functions, and translates exceptions into user-facing messages and exit codes.

Arguments and options are declared with `typing.Annotated` and `typer.Argument` / `typer.Option`, keeping signatures explicit and self-documenting. There is a single eager `--version` callback at the app level. Command handlers avoid inline workflow logic; instead they call `fetch_repos()`, `track_project()`, `sync_projects()`, and similar functions. This keeps CLI concerns separate from executable behavior and makes core logic testable without invoking the terminal.

# Logging & Observability

There is no conventional logging subsystem in this project. Observability is command-oriented: the CLI prints concise progress lines, summaries, and actionable error messages directly to stdout, with styling via `typer.style()` and `typer.echo()`. For a CLI-first utility, this is a deliberate choice that avoids configuring log handlers, files, or structured log pipelines.

Progress reporting is pushed up from the core through callbacks such as `on_foundry` and `on_project`. The service layer reports events, and the CLI decides how to render them. Verbosity is therefore implicit in command behavior rather than controlled through global log levels or debug flags. Exit codes are part of the observability contract: user-correctable failures become non-zero exits with short messages.

# Automation & Tooling

Developer automation is task-runner based. `tasks.py` defines Invoke tasks for environment sync, formatting, linting, tests, cleaning, version bumping, and publishing. The task definitions are intentionally small wrappers around ecosystem commands rather than custom Python build logic.

The daily workflow is centered on `uv` plus Invoke: `uv sync --group dev` to provision the environment, `inv format` to apply formatting, `inv lint` to run Ruff and mypy, and `inv test` to run pytest with coverage. Formatting is also a prerequisite of linting, which encodes the author’s preference that code should be normalized before static checks run.

Build and release tooling also follow the same pattern: `uv build` for packaging, `bump-my-version` for version changes, and `uv publish` for distribution. This keeps everything scriptable from the shell and makes automation reproducible both locally and in CI.

# Dependency & Environment Management

The project uses modern `pyproject.toml` packaging with `uv_build` as the backend and `uv` as the environment and lockfile manager. Runtime dependencies and dev dependencies are separated via `[dependency-groups]`, and the repository includes `uv.lock` to pin a reproducible environment.

Python compatibility is declared once in packaging metadata (`requires-python = ">=3.11"`) and echoed in tool configuration (`mypy` and Ruff both target 3.11 semantics). The expected workflow is an isolated virtual environment managed by `uv sync`, not ad hoc global installs. Reproducibility comes from the combination of declarative metadata, a lockfile, and shell-friendly bootstrap commands documented in the repository.

# Testing Strategy

Tests are first-class and organized as a direct mirror of the production modules. The suite uses pytest, with CLI tests exercising the Typer app through `typer.testing.CliRunner` and lower-level module tests exercising functions directly. This split reinforces the boundary between the CLI shell and the reusable core.

The dominant test style is lightweight unit testing with `unittest.mock.patch`, `pytest.MonkeyPatch`, and `tmp_path`. File-backed modules are tested through temporary paths and monkeypatched path helpers, while orchestration code is tested by patching adapters and subprocess wrappers. That keeps tests fast, deterministic, and independent of live network or git state.

Testing is run through `inv test`, which wraps `pytest --cov=src --cov-report=term-missing`. Coverage is therefore part of the default workflow rather than an optional extra, which signals that tests are part of normal development, not a secondary afterthought.

# Code Style & Conventions

The package uses `src/` layout, snake_case modules, and one responsibility-focused module per concern. The code strongly prefers top-level functions plus dataclasses over service objects or framework-heavy abstractions. Small value objects such as `Config`, `Project`, `FoundryConfig`, `RemoteRepo`, and `SyncResult` are dataclasses; behavior lives in standalone functions.

Repeated conventions are clear. Side effects are isolated in dedicated modules (`gitops`, `config`, `index`, backend adapters). Errors are surfaced explicitly with narrow custom exceptions where useful (`ConfigExistsError`, `GitError`) and plain `ValueError` for user-correctable conditions. The CLI catches those exceptions at the boundary and maps them to terminal output and exit codes. Missing optional data generally returns empty lists instead of inventing placeholder objects.

Formatting is standardized with Ruff, typing is strict via mypy, and the project uses modern typing syntax (`X | Y`, `Annotated`). Comments are sparse. The code aims to be readable enough that helper names and module boundaries carry most of the explanation.

# Architectural Patterns

`Thin CLI, fat core` is the dominant pattern. `cli.py` mostly parses input, loads state, calls core functions, and renders output. Workflow logic lives in `services.py` and supporting modules.

`Functional core, imperative shell` also shows up clearly. Dataclasses represent state, functions transform or coordinate it, and imperative side effects are isolated to the shell-facing edges: file IO, HTTP calls, git subprocesses, and terminal output.

`Explicit module ownership` is another strong pattern. Each module owns one kind of responsibility and is explicit about what it does not do: config does not call APIs, adapters do not mutate config, git wrappers do not know about CLI behavior. This makes boundaries easy to preserve in new projects.

`Adapter package with normalized records` appears in `foundry/`. Each backend module implements the same `list_repos(config, clone_url_format)` shape and returns a shared `RemoteRepo` dataclass. That is a lightweight plugin pattern without a formal plugin framework.

`File-backed state split by lifecycle` is a reusable storage pattern. Durable secrets/config, portable user state, and ephemeral cache data are stored separately. This is simpler than a database while still giving clean lifecycle boundaries.

`Callback-based progress reporting` is a notable convention. Service functions accept callbacks for progress events, which lets the core remain presentation-agnostic while still supporting rich CLI feedback.

`Coarse-grained concurrency over synchronous adapters` is used in orchestration. Backend and git operations remain simple synchronous functions, but `ThreadPoolExecutor` is used at the service layer to parallelize independent work. This avoids introducing async complexity into the whole codebase.

# What Should Be Reused in a Template

The most reusable pattern is the overall layering: `cli.py` as a thin interface, `services.py` as orchestration, dedicated modules for persistence, presentation, and external-system adapters, and dataclasses as shared records. This structure scales well for small and medium Python tools without introducing unnecessary classes or frameworks.

Also worth reusing is the `src/` layout plus mirrored test layout, because it makes module ownership, packaging, and test coverage straightforward. Pair that with strict type checking, Ruff-driven formatting/linting, and a task runner that exposes the small set of daily developer commands.

The XDG file-storage pattern is broadly reusable for local-first CLIs. Splitting config, portable state, and cache into separate files is cleaner than dumping everything into one YAML file and usually sufficient for tools that do not need a database.

The adapter pattern in `foundry/` is a strong template choice for any project that integrates multiple external backends. Keep one module per backend, normalize external data into a shared internal record, and let the service layer orchestrate across them.

The callback-based status reporting pattern is also worth keeping. It preserves testability and keeps core code independent from the terminal, while still enabling responsive CLI output.

Finally, the author’s preferred workflow is worth copying almost verbatim: `uv` for environment and lockfile management, `pyproject.toml` as the single tooling manifest, Invoke as a thin task layer, pytest for tests, Ruff for formatting and linting, mypy in strict mode, and minimal operational dependencies beyond the standard library and a few focused third-party packages.
