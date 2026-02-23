# Architecture: git-projects

## Problem and context

A developer working across multiple git foundries (GitHub, GitLab, self-hosted Gitea) loses track of what they worked on and where. There is no unified view of recent activity across all repositories. This tool provides a local-first CLI that discovers repos via APIs, tracks them locally, and generates activity summaries from git history.

## Goals and non-goals

### Goals

1. Discover repos from GitHub, GitLab, and Gitea APIs — list available repos on demand.
2. Let the user explicitly select which repos to track via config.
3. Clone and sync tracked repos locally at a configured base path.
4. Provide project list and history views from local git log.
5. Config file (`config.yaml`), project list (`projects.json`), and local index (`index.json`) under `XDG_DATA_HOME/git-projects/`.
6. Export/import tracked projects as portable JSON for multi-machine workflows.

### Non-goals

- No web UI or daemon process.
- No direct API-based commit/PR fetching — all history comes from local git log.
- No support for non-git VCS.
- No automatic scheduled runs (user runs manually or via cron).
- No auto-tracking heuristics — user explicitly picks repos.

## System overview

The tool is a local CLI application. `remote fetch` calls foundry APIs concurrently, saves results to a local index (`index.json`), and prints a summary. `remote list` reads the index and filters by query/recency — no network required. `track` accepts a repo name (looked up from the index) or a direct clone URL. `sync` clones missing and pulls existing tracked repos. `list` and `history` read from local state and git repos. `export` and `import` transfer the project list between machines as portable JSON.

```mermaid
graph LR
    CLI[CLI - typer]
    CLI --> Config[Config Module]
    CLI --> Index[Index Module]
    CLI --> GitOps[Git Operations]
    CLI --> History[History Builder]

    Config -- reads/writes --> YAML[(config.yaml<br>XDG_DATA_HOME)]
    Config -- reads/writes --> ProjJSON[(projects.json<br>XDG_DATA_HOME)]
    Index -- reads/writes --> JSON[(index.json<br>XDG_DATA_HOME)]
    GitOps -- clone/pull/log --> LocalRepos[(Local repos on disk)]
    History -- reads --> LocalRepos
    History -- reads --> Config

    CLI --> Foundry[Foundry Clients]
    Foundry --> GH[GitHub API]
    Foundry --> GL[GitLab API]
    Foundry --> GT[Gitea API]
```

## Technology stack

| Component | Technology | Version | Rationale |
|---|---|---|---|
| Language | Python | 3.12+ | Already chosen in pyproject.toml |
| CLI framework | typer | 0.12+ | Already chosen in pyproject.toml |
| HTTP client | httpx | latest | Async-capable, clean API, lighter than requests |
| Git operations | subprocess (git) | — | Avoids heavy deps like GitPython; shell out to `git` directly |
| Data storage | YAML via PyYAML | latest | Human-readable, editable config; no DB overhead |
| XDG paths | platformdirs | latest | Cross-platform XDG_DATA_HOME resolution |
| Date handling | stdlib datetime | — | No need for arrow/pendulum |

## CLI commands

| Command | Description |
|---|---|
| `config init` | Create default config file |
| `config show` | Show config file path and contents |
| `remote fetch [foundry]` | Fetch repos from foundry APIs concurrently, save to local index |
| `remote list [query] [--all]` | Show repos from local index; optional name/description filter; `--all` disables 180-day cutoff |
| `track <name\|url> [--path <dir>]` | Add a project — name looked up in index, or direct clone URL |
| `untrack <name>` | Remove a project from projects.json |
| `list` | Show tracked projects |
| `sync` | Clone missing repos, pull existing tracked repos |
| `history [name]` | Git log summaries for tracked projects |
| `export [file]` | Export tracked projects to JSON (stdout or file) |
| `import <file>` | Import projects from JSON, skip duplicates with warning |

### Workflow

```
remote fetch            → hit APIs, save all repos to local index
remote list [query]     → browse index (fast, no network)
track <name>            → add by name from index
sync                    → clone & pull all tracked projects
list                    → see what you're tracking
history [name]          → see recent git activity
untrack <name>          → stop tracking a project
export [file]           → export projects as portable JSON
import <file>           → import projects, then sync
```

## Module boundaries

### `cli` — Command-line interface
- **Owns**: Argument parsing, output formatting, subcommand dispatch.
- **Public interface**: `app` (typer instance) with commands: `config` (group: `init`, `show`), `remote` (group: `fetch`, `list`), `track`, `untrack`, `list`, `sync`, `history`, `export`, `import`.
- **Must NOT**: Contain business logic, call git directly, or manage state.

### `config` — Configuration and project tracking
- **Owns**: Reading/writing `config.yaml` (settings + credentials) and `projects.json` (tracked project list).
- **Public interface**: `load_config() -> Config`, `save_config(Config)`, `init_config() -> Path`, `load_projects() -> list[Project]`, `save_projects(list[Project])`, `add_project(clone_url) -> Project`, `remove_project(name) -> bool`, `export_projects(path | None)`, `import_projects(path) -> ImportResult`.
- **Data types**:
  - `FoundryConfig`: `name`, `type`, `url`, `token`.
  - `Project`: `clone_url`, `name`, `path` (relative to `clone_root`).
  - `Config`: `clone_root`, `foundries: list[FoundryConfig]`, `clone_url_format: str` (`"ssh"` | `"https"`, default `"ssh"`).
  - `ImportResult`: `added: list[str]`, `skipped: list[str]`.
- **Must NOT**: Call APIs or run git commands.
- **Storage layout**:
  ```
  $XDG_DATA_HOME/git-projects/
  ├── config.yaml      # foundries, clone_root, clone_url_format (credentials)
  ├── projects.json    # tracked projects (portable, no secrets)
  └── index.json       # cached repo list from last remote fetch
  ```
- **Default config.yaml created by `init`**:
  ```yaml
  clone_root: ~/projects    # where repos get cloned
  clone_url_format: ssh     # "https" or "ssh"
  foundries:
    - name: github
      type: github
      token: ""              # paste your token here
    # - name: my-gitlab
    #   type: gitlab
    #   token: ""
    # - name: my-gitea
    #   type: gitea
    #   url: https://gitea.example.com
    #   token: ""
  ```
- **Example projects.json**:
  ```json
  [
    {
      "clone_url": "https://github.com/user/repo-a.git",
      "name": "repo-a",
      "path": "repo-a"
    },
    {
      "clone_url": "https://gitlab.com/user/repo-b.git",
      "name": "repo-b",
      "path": "repo-b"
    }
  ]
  ```
- **Path derivation**: Project `path` is stored **relative to `clone_root`** (e.g. `"repo-a"`, not `"~/projects/repo-a"`). Resolved to an absolute path at runtime via `clone_root / path`. When `track` is called with a clone URL, `name` is extracted from the URL (last path segment without `.git`), and `path` defaults to `name`. Both HTTPS (`https://host/user/repo.git`) and SCP-style SSH (`git@host:user/repo.git`) URLs are supported. Pass `--path <dir>` to override the relative path. When called with a name (no `://` or `git@`), the clone URL is resolved from the local index.
- **Export/import**: `export` writes `projects.json` content to stdout or a file path. `import` reads a JSON file, merges into `projects.json`, and skips duplicates (matched by `clone_url`) with a warning per skipped project.

### `index` — Local repo index
- **Owns**: Reading/writing `index.json`, filtering and sorting cached repo metadata.
- **Public interface**: `save_index(repos: list[RemoteRepo]) -> Path`, `load_index() -> list[RemoteRepo]`, `search_index(repos, query, max_age_days) -> list[RemoteRepo]`.
- **Storage**: `$XDG_DATA_HOME/git-projects/index.json` — JSON array of all repos from the last `remote fetch`.
- **Must NOT**: Call APIs, modify config, or run git commands.

### `foundry` — API clients for repo discovery
- **Owns**: Listing repos from GitHub, GitLab, Gitea APIs. Returns normalized repo metadata.
- **Structure**: Package with one submodule per API type (`foundry/github.py`, `foundry/gitlab.py`, `foundry/gitea.py`). Each submodule exposes the same function signature.
- **Public interface**: Each submodule exposes `list_repos(config: FoundryConfig, clone_url_format: str = "ssh") -> list[RemoteRepo]`.
- **Shared types**: `RemoteRepo` dataclass defined in `foundry/__init__.py` — fields: `name`, `repo_url` (browser URL, always HTTPS), `clone_url` (HTTPS or SSH per `clone_url_format`), `pushed_at`, `default_branch`, `visibility`, `description`.
- **Must NOT**: Clone repos, modify config, or read git history.

### `gitops` — Local git operations
- **Owns**: Cloning repos, pulling updates, reading git log.
- **Public interface**: `clone_repo(url, path)`, `pull_repo(path)`, `get_log(path, since: date | None) -> list[Commit]`.
- **Must NOT**: Call foundry APIs or write to config.

### `history` — History and changelog generation
- **Owns**: Aggregating commits into summaries, grouping by project/date, formatting output.
- **Public interface**: `build_project_list(projects) -> str`, `build_brief_history(projects) -> str`, `build_detailed_history(project) -> str`.
- **Must NOT**: Call git or APIs directly — receives data from gitops.

### Communication patterns

All communication is **synchronous function calls**. No events, no message queues. The CLI orchestrates:
1. `config init`: config (create default config, print path)
2. `config show`: config (load config, print path + content)
3. `remote fetch`: foundry (concurrent API calls) → index (save all repos) → print summary
4. `remote list`: index (load + filter) → print repos
5. `track`: index (name lookup, optional) → config (add project to projects.json)
6. `untrack`: config (remove project from projects.json)
7. `list`: config (load projects, print)
8. `sync`: config (load projects) → gitops (clone missing, pull existing)
9. `history`: config (load projects) → gitops (log) → history (format)
10. `export`: config (load projects) → write JSON to stdout or file
11. `import`: read JSON file → config (merge into projects.json, skip duplicates with warning)

## Key architectural decisions

### Decision: Three-file storage — config.yaml, projects.json, index.json
- **Alternatives considered**: Single config file with everything, two files (config + index).
- **Rationale**: `config.yaml` holds credentials and settings — hand-editable, never shared. `projects.json` holds the tracked project list — machine-managed, portable, no secrets. `index.json` is an ephemeral cache of API data. This separation means `export`/`import` can transfer `projects.json` between machines without leaking tokens. Project paths are stored relative to `clone_root`, so the same `projects.json` works on machines with different directory layouts.

### Decision: Shell out to `git` instead of using GitPython/pygit2
- **Alternatives considered**: GitPython, pygit2, dulwich.
- **Rationale**: Zero additional binary deps, `git` is always available, parsing `git log` output is straightforward for our use case. Keeps the dependency tree minimal.

### Decision: YAML config instead of SQLite
- **Alternatives considered**: SQLite, TinyDB, JSON files.
- **Rationale**: YAML is human-readable and hand-editable — users can add/remove projects directly in the file. The dataset is small. No query complexity warrants a database.

### Decision: httpx instead of requests
- **Alternatives considered**: requests, urllib3.
- **Rationale**: Modern API, better typing, HTTP/2 support. Can go async later if needed without changing the client library.

### Decision: One foundry client per API type, not per instance
- **Alternatives considered**: Separate client classes per foundry instance.
- **Rationale**: GitHub, GitLab, and Gitea each have one API shape. Multiple instances (e.g., two Gitea servers) use the same client with different base URLs. Keeps the client count to three.

### Decision: Explicit tracking instead of auto-track heuristics
- **Alternatives considered**: Auto-track repos modified in last 6 months, track all by default.
- **Rationale**: Auto-tracking filled the registry with repos the user didn't care about. Explicit `track`/`untrack` gives the user full control. `fetch` lets them browse what's available before choosing.

## Constraints and conventions

- Python 3.12+, type hints everywhere (PEP 604 style).
- Lint with `ruff check --fix`, format with `ruff format`.
- All API tokens read from config YAML — never hardcoded. Env var override not needed initially.
- `git log` output parsed with `--format` flags, not regex on default output.
- No classes where a function + dataclass will do.
- Use `dataclasses` or plain dicts for internal data; no Pydantic [ASSUMPTION: validation complexity stays low].
- CLI output: ANSI-colored terminal output via `typer.style()` (bold names, colored visibility badges, dimmed secondary info). No rich/tables.

## Open questions

1. **Changelog quality**: Raw commit messages may be noisy. Should we group by date only, or attempt to deduplicate/summarize? Defer to implementation — start with date-grouped commit lists, improve later.
2. ~~**Auth flow**~~: Resolved — `init` creates config with GitHub placeholder; user edits YAML to add tokens and foundries.
3. **Clone depth**: Should `clone` use `--depth 1` or full clone? Full clone gives complete history but uses more disk. [ASSUMPTION: full clone for complete history.]
