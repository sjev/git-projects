# Design: `info` Command

## Summary

`git-projects info` prints a snapshot of the tool's runtime state in one shot:
app version, paths to `config.yaml` and `index.json`, number of tracked projects,
and the size and freshness of the local index. It requires no network access and
never modifies any file. Its primary use is quick orientation — confirming the
install is working, locating config files, and knowing whether the index needs
a refresh.

## Scope

- **In scope**
  - New top-level `info` command in `cli.py`.
  - Read version via `importlib.metadata.version("git-projects")`.
  - Resolve config path via `config.get_config_path()`.
  - Resolve index path via `index.get_index_path()`.
  - Report whether each file exists.
  - Load `config.yaml` (if present) to count tracked projects.
  - Load `index.json` (if present) to count fetched repos and read `updated_at`.
  - Format index age as a human-readable relative string (`Xh ago`, `Xd ago`, `just now`).
  - Always exits 0 (even when files are missing).

- **Out of scope**
  - Modifying any file.
  - Fetching from foundry APIs.
  - Showing config contents (that belongs to `config show`).
  - Any machine-readable output format (JSON, etc.).

## Acceptance criteria

```
AC-01  `git-projects info` exits 0.
AC-02  Output contains the app version string (e.g. "0.1.0").
AC-03  Output contains the absolute path to config.yaml.
AC-04  Output contains the absolute path to index.json.
AC-05  When config.yaml exists, output contains the count of tracked projects.
AC-06  When config.yaml does not exist, output contains "not found" next to the
       config path and does NOT show a tracked-project count.
AC-07  When index.json exists, output contains the count of repos in the index.
AC-08  When index.json exists, output contains a human-readable age string
       derived from the `updated_at` timestamp (e.g. "2h ago").
AC-09  When index.json does not exist, output contains "not found" next to the
       index path and does NOT show a repo count or age.
AC-10  `info` does not call any foundry API and does not modify any file.
```

## Data model changes

None. This feature reads existing data structures — `Config` (for
`cfg.projects`) and the raw `index.json` JSON (for `repos` and `updated_at`).
No new fields or files are introduced.

## Execution flow

### Happy flow

1. CLI invokes `info()`.
2. Read version: `importlib.metadata.version("git-projects")`.
3. Resolve `config_path = config.get_config_path()`.
4. If `config_path.exists()`:
   - Load config via `config.load_config()`.
   - `n_tracked = len(cfg.projects)`.
5. Resolve `index_path = index.get_index_path()`.
6. If `index_path.exists()`:
   - Load raw JSON (`json.loads(index_path.read_text())`).
   - `n_repos = len(raw["repos"])`.
   - Parse `updated_at` and compute age relative to `datetime.now(utc)`.
7. Print formatted output.

### Non-happy flow

If either file does not exist, the corresponding section shows the path with
`(not found)` and omits count/age lines. The command always exits 0 — missing
files are normal before first `config init` or `remote fetch`.

Example when neither file exists:
```
git-projects 0.1.0

Config    /home/user/.local/share/git-projects/config.yaml  (not found)
Index     /home/user/.local/share/git-projects/index.json   (not found)
```

## API / interface changes

### `cli.info()` (new command)

```python
@app.command()
def info() -> None:
    """Show app version, config and index locations, and repo counts."""
```

- **Inputs**: None (no arguments or options).
- **Output**: Prints to stdout; always exits 0.
- **Dependencies**:
  - `importlib.metadata.version("git-projects")` — may raise
    `PackageNotFoundError` (only in editable installs without metadata;
    handle by falling back to `"unknown"`).
  - `config.get_config_path() -> Path` — already exists, no change.
  - `config.load_config() -> Config` — already exists; only called if file exists.
  - `index.get_index_path() -> Path` — already exists, no change.
  - Raw `json.loads` on `index_path.read_text()` for `updated_at` and repo count
    (avoids `load_index()` which discards `updated_at`).

### `index.get_index_path()` — no change to signature

Already public. Used here directly for the first time outside of `index.py` itself.

## Affected modules

| Module | Change |
|--------|--------|
| `cli.py` | Add `info` command function. Import `importlib.metadata`. |
| `config.py` | No change — `get_config_path()` already public. |
| `index.py` | No change — `get_index_path()` already public. |

No new modules, no new dependencies.

## Implementation notes

- **Age formatting**: Use stdlib `datetime` only. Define a small private helper
  `_format_age(dt: datetime) -> str` inside `cli.py`:
  - `< 1 min` → `"just now"`
  - `< 60 min` → `"Xm ago"`
  - `< 48 h` → `"Xh ago"`
  - Otherwise → `"Xd ago"`
- **`updated_at` timezone**: The field is written as `datetime.now(utc).isoformat()`
  (offset-aware). Parse with `datetime.fromisoformat(updated_at)` — no
  `.replace("Z", "+00:00")` needed.
- **`PackageNotFoundError`**: Wrap `importlib.metadata.version(...)` in a
  `try/except importlib.metadata.PackageNotFoundError` and fall back to
  `"unknown"`.
- **Output style**: Use `typer.style(..., bold=True)` for labels and the version
  string. Use dim styling for paths and counts, consistent with existing commands.
- **Architecture note**: `info` accesses `index_path.read_text()` directly rather
  than through `load_index()` because `load_index()` does not expose `updated_at`.
  This is acceptable — `info` is read-only and does not need the full
  `list[RemoteRepo]` return type. If `updated_at` is needed elsewhere later,
  consider extending `index.py`'s public interface.

## Open questions

None — all scope and behavior questions resolved before design.
