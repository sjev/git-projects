# Design: Split projects into separate projects.json

## Summary

Move project tracking data out of `config.yaml` into a dedicated `projects.json` file. This aligns with the three-file storage design in the architecture doc (`config.yaml` for settings/credentials, `projects.json` for portable project list, `index.json` for cached repo metadata). This is a clean break — no migration of existing data. The `Config` dataclass loses its `projects` field, and all project I/O goes through new `load_projects()` / `save_projects()` functions. `derive_project()` is fixed to store paths relative to `clone_root` instead of absolute.

## Scope

- In scope:
  - Remove `projects` from `Config` dataclass and `config.yaml` I/O
  - Remove `projects: []` from `DEFAULT_CONFIG` template
  - Add `get_projects_path()`, `load_projects()`, `save_projects()` to `config` module
  - Fix `derive_project()` to return path relative to `clone_root` (just the name, not `clone_root/name`)
  - Update `services.py` to use `load_projects()` / `save_projects()` instead of `cfg.projects` + `save_config()`
  - Update `cli.py` to load projects separately from config
  - Update all tests

- Out of scope:
  - Migrating existing `config.yaml` files that contain `projects` data
  - Export/import commands (not yet implemented, will use new functions directly)
  - Any changes to `index.py` or foundry clients

## Acceptance criteria

- AC-01: `Config` dataclass has no `projects` field.
- AC-02: `DEFAULT_CONFIG` does not contain `projects`.
- AC-03: `save_config()` does not write a `projects` key to `config.yaml`.
- AC-04: `load_projects()` returns `list[Project]` from `$XDG_DATA_HOME/git-projects/projects.json`. Returns empty list if file does not exist.
- AC-05: `save_projects(projects)` writes `list[Project]` as JSON to `$XDG_DATA_HOME/git-projects/projects.json`.
- AC-06: `projects.json` format matches the architecture doc: `[{"clone_url": "...", "name": "...", "path": "..."}]`.
- AC-07: `derive_project(clone_url)` returns a `Project` with `path` set to the repo name only (e.g., `"my-repo"`), not an absolute or `clone_root`-prefixed path.
- AC-08: `track` command saves to `projects.json` (not `config.yaml`).
- AC-09: `untrack` command removes from `projects.json` (not `config.yaml`).
- AC-10: `list` command reads from `projects.json`.
- AC-11: `sync` command reads from `projects.json` and resolves paths via `clone_root / project.path`.
- AC-12: `info` command shows project count from `projects.json`.
- AC-13: All existing tests pass (updated for new structure).

## Data model changes

**Before:**
```
Config
  clone_root: str
  clone_url_format: str
  foundries: list[FoundryConfig]
  projects: list[Project]          ← REMOVED
```

**After:**
```
Config
  clone_root: str
  clone_url_format: str
  foundries: list[FoundryConfig]
```

`Project` dataclass is unchanged, but `path` field semantics change: stores path **relative to `clone_root`** (e.g., `"my-repo"`) instead of absolute (e.g., `"~/projects/my-repo"`).

**Storage:**
```
$XDG_DATA_HOME/git-projects/
├── config.yaml      # clone_root, clone_url_format, foundries (no projects key)
├── projects.json    # [{"clone_url": "...", "name": "...", "path": "..."}]
└── index.json       # cached repo metadata
```

## Execution flow

### Happy flow

1. User runs `git-projects track https://github.com/user/my-repo.git`
2. CLI calls `config.load_config()` → gets `Config` (no projects)
3. CLI (via `services.track_project()`) calls `config.load_projects()` → gets `list[Project]` from `projects.json`
4. `derive_project("https://github.com/user/my-repo.git")` returns `Project(name="my-repo", path="my-repo", clone_url="...")`
5. Project appended to list, `config.save_projects(projects)` writes `projects.json`
6. CLI prints confirmation

### Non-happy flow

1. User runs `git-projects list` before any project is tracked
2. CLI calls `config.load_projects()` → `projects.json` does not exist → returns `[]`
3. CLI prints "No projects tracked"

## API / interface changes

### `config` module — new functions

```python
def get_projects_path() -> Path:
    """Return the absolute path to projects.json."""
    # Returns user_data_path("git-projects") / "projects.json"

def load_projects() -> list[Project]:
    """Load tracked projects from projects.json. Returns [] if file missing."""

def save_projects(projects: list[Project]) -> Path:
    """Write projects list to projects.json. Returns the file path."""
```

- `load_projects()`: no validation beyond JSON parse; returns empty list for missing file.
- `save_projects()`: creates parent directory if needed; overwrites file atomically.

### `config` module — modified functions

```python
def derive_project(clone_url: str) -> Project:
    """Derive project name and relative path from a clone URL."""
    # No longer takes clone_root parameter
    # path = name (just the repo name, relative to clone_root)
```

- `load_config()` — no longer reads `projects` key; `Config` has no `projects` field.
- `save_config()` — no longer writes `projects` key.

### `services` module — modified functions

```python
def track_project(cfg: Config, name_or_url: str, path: str | None = None) -> Project:
    # Loads/saves via load_projects()/save_projects() instead of cfg.projects/save_config()

def untrack_project(cfg: Config, name: str) -> None:
    # Loads/saves via load_projects()/save_projects() instead of cfg.projects/save_config()
```

### `cli` module — modified commands

- `list_projects()`: calls `config.load_projects()` instead of `cfg.projects`
- `sync()`: calls `config.load_projects()`, resolves paths via `Path(cfg.clone_root).expanduser() / project.path`
- `info()`: calls `config.load_projects()` for project count, shows `projects.json` path
- `track()` / `untrack()`: no changes needed (delegates to services)

## Affected modules

| Module | Change |
|--------|--------|
| `config.py` | Remove `projects` from `Config`, `DEFAULT_CONFIG`, `load_config`, `save_config`. Add `get_projects_path()`, `load_projects()`, `save_projects()`. Fix `derive_project()` signature and path logic. |
| `services.py` | `track_project` and `untrack_project` use `load_projects()`/`save_projects()` instead of `cfg.projects`/`save_config()`. |
| `cli.py` | `list_projects`, `sync`, `info` load projects via `config.load_projects()`. `sync` resolves relative paths at runtime. |
| `tests/test_config.py` | Update all tests: remove `projects` from Config construction, add tests for `load_projects`/`save_projects`, fix `derive_project` assertions. |
| `tests/test_services.py` | Mock `load_projects`/`save_projects` instead of `save_config` for track/untrack. Remove `projects` from `Config()` calls. |
| `tests/test_cli.py` | Mock `load_projects` for list/sync/info. Remove `projects` from `Config()` calls. |

## Implementation notes

- `save_projects()` should use `json.dumps(indent=2)` for readability, matching the architecture doc example.
- `load_projects()` returns `[]` for missing file — no error, no auto-creation. The file only gets created on first `track`.
- `sync_projects()` in `services.py` currently uses `project.path` directly as an absolute path. After this change, the CLI layer must resolve `clone_root / project.path` before passing to `sync_projects()`, or `sync_projects()` must accept `clone_root` to resolve paths internally. Prefer: CLI resolves paths before calling `sync_projects()`.
- `derive_project()` drops the `clone_root` parameter entirely — the path is always just the name extracted from the URL.
- The `track_project` service function still needs `cfg` for `clone_root` (used when `--path` is not provided and the caller wants to check existence), but no longer mutates `cfg.projects`.

## Open questions

None — scope is clear.
