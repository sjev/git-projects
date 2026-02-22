# Design: Sync Command

## Summary

Implements the `sync` command, which iterates over all tracked projects and
brings them up to date locally. For each project: if the repo directory does
not exist, it clones from the configured `clone_url`; if it exists, it pulls
the current branch and then pushes to the remote. Repos with a dirty working
tree are skipped with a warning. Processing is sequential.

## Scope

- In scope:
  - New module `src/git_projects/gitops.py` with `clone_repo`, `pull_repo`,
    `push_repo`, and `is_dirty` functions that shell out to `git`
  - New service function `sync_projects` in `services.py` that orchestrates
    clone/pull/push per project
  - Wire the existing `sync` CLI command in `cli.py` to call `sync_projects`
  - ANSI-colored per-project status output (cloned, pulled, pushed, skipped, error)
- Out of scope:
  - Concurrent/parallel sync
  - `git stash` or auto-merge conflict resolution
  - `--dry-run` or `--clone-only` flags (can be added later)
  - `get_log` / history integration (separate feature)

## Acceptance criteria

  AC-01: When a tracked project's path does not exist on disk, `sync` clones
         it from `clone_url` into that path.
  AC-02: When a tracked project's path exists and the working tree is clean,
         `sync` runs `git pull` on the currently checked-out branch.
  AC-03: After a successful pull, `sync` runs `git push` on the currently
         checked-out branch.
  AC-04: When a tracked project's path exists but the working tree is dirty
         (uncommitted changes or untracked files in the index), `sync` skips
         that project and prints a warning.
  AC-05: When `git clone`, `git pull`, or `git push` fails (non-zero exit),
         the error is reported for that project and `sync` continues to the
         next project.
  AC-06: `sync` with no tracked projects prints a message and exits cleanly.
  AC-07: After `sync` completes, a summary line shows counts (e.g.
         "3 synced, 1 skipped, 0 errors").
  AC-08: `clone_repo` expands `~` in the target path before passing to `git`.
  AC-09: `pull_repo` and `push_repo` operate on whatever branch is currently
         checked out (no explicit branch argument).

## Data model changes

None. `Project` already has `clone_url`, `name`, and `path` — all fields
needed by gitops.

## Execution flow

### Happy flow

1. User runs `git-projects sync`.
2. `cli.py` loads config via `_load_config_or_exit()`, calls
   `sync_projects(cfg.projects, on_project=callback)`.
3. `sync_projects` iterates projects sequentially. For each project:
   a. Expand `~` in `project.path`.
   b. If path does not exist → `clone_repo(project.clone_url, path)` →
      report "cloned".
   c. If path exists and `is_dirty(path)` → report "skipped (dirty)" →
      continue.
   d. If path exists and clean → `pull_repo(path)` → `push_repo(path)` →
      report "synced".
4. After all projects, print summary line.

### Non-happy flow

**git pull fails (e.g. merge conflict on remote changes)**:
- `pull_repo` raises `GitError` with the stderr output.
- `sync_projects` catches it, records the project as errored, reports the
  error message, and continues to the next project.
- `push_repo` is not called for that project.
- The summary line increments the error count.

## API / interface changes

### New: `src/git_projects/gitops.py`

```python
class GitError(Exception):
    """Raised when a git subprocess returns non-zero."""

def clone_repo(url: str, path: str) -> None: ...
```
- Runs `git clone <url> <expanded_path>`.
- Raises `GitError` on non-zero exit code.

```python
def pull_repo(path: str) -> None: ...
```
- Runs `git -C <expanded_path> pull`.
- Raises `GitError` on non-zero exit code.

```python
def push_repo(path: str) -> None: ...
```
- Runs `git -C <expanded_path> push`.
- Raises `GitError` on non-zero exit code.

```python
def is_dirty(path: str) -> bool: ...
```
- Runs `git -C <expanded_path> status --porcelain`.
- Returns `True` if stdout is non-empty.

All functions expand `~` via `Path(path).expanduser()` before invoking git.

### New: `src/git_projects/services.py`

```python
@dataclass
class SyncResult:
    cloned: list[str]
    synced: list[str]
    skipped: list[str]
    errored: list[tuple[str, str]]  # (name, error_message)

def sync_projects(
    projects: list[Project],
    on_project: Callable[[str, str], None] | None = None,
) -> SyncResult: ...
```
- `on_project(name, status_message)` callback for per-project live output.
- Returns `SyncResult` for the summary.

### Modified: `src/git_projects/cli.py`

The existing `sync` command body is replaced to call `sync_projects` and
print colored per-project output via the `on_project` callback, then print
the summary line.

## Affected modules

| Module        | Change                                                        |
|---------------|---------------------------------------------------------------|
| `gitops.py`   | **New** — `clone_repo`, `pull_repo`, `push_repo`, `is_dirty`, `GitError` |
| `services.py` | **Modified** — add `sync_projects` function + `SyncResult`    |
| `cli.py`      | **Modified** — wire `sync` command to `sync_projects`         |
| `config.py`   | None                                                          |
| `foundry/`    | None                                                          |

## Implementation notes

- Use `subprocess.run` with `capture_output=True`, `text=True`. Check
  `returncode != 0` and raise `GitError(stderr)`.
- `git clone` creates the target directory; the parent must exist. Use
  `Path(path).parent.mkdir(parents=True, exist_ok=True)` before cloning.
- `is_dirty` uses `git status --porcelain` which is stable and
  machine-parseable. Any non-empty output means dirty.
- `git push` with no arguments pushes the current branch to its configured
  upstream. If no upstream is set, git will error — this is reported as
  a sync error for that project, which is the correct behavior (the user
  needs to set upstream manually).
- All git commands inherit the user's git config (credentials, SSH keys,
  etc.) since we shell out directly.
- The `on_project` callback pattern matches `on_foundry_start` in
  `fetch_repos`.

## Open questions

None.
