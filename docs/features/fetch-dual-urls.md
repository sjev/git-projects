# Design: Dual URLs in fetch output

## Summary

The `fetch` command currently shows only the HTTPS clone URL for each repo.
This feature adds a browser URL (`repo_url`) always shown as a web link, and
makes the clone URL format (HTTPS or SSH) configurable via a global
`clone_url_format` setting in `config.yaml`. Format selection happens at fetch
time inside the foundry clients, so `RemoteRepo` carries exactly two URL
fields. The `track` command is updated to correctly parse SSH-format URLs when
deriving a project name and path.

## Scope

- In scope:
  - Replace `RemoteRepo.clone_url` with two fields: `repo_url` (browser URL)
    and `clone_url` (HTTPS or SSH, chosen by `clone_url_format`)
  - Add global `clone_url_format: https | ssh` to `Config` and `DEFAULT_CONFIG`
    (default: `ssh`)
  - Pass `clone_url_format` into foundry `list_repos()` so clients populate
    `clone_url` with the right URL at construction time
  - Update `format_repo()` to show both `repo_url` and `clone_url`
  - Update `derive_project()` in `config.py` to handle SCP-style SSH URLs
    (`git@host:user/repo.git`) in addition to HTTPS URLs
  - Update `track` CLI command to display the stored clone URL in output

- Out of scope:
  - GitLab foundry (not yet implemented)
  - Per-foundry `clone_url_format` override
  - Changing the field name `clone_url` on `Project` (stored as-is from input)
  - Validating that the provided clone URL actually resolves

## Acceptance criteria

  AC-01: `config.yaml` accepts a top-level `clone_url_format` field with
         values `https` or `ssh`. When absent, defaults to `ssh`.
  AC-02: `config init` generates a config with `clone_url_format: ssh` in
         the default template.
  AC-03: `fetch` output for each repo shows `repo_url` (browser URL) on a
         dedicated line, visually distinct from the clone URL.
  AC-04: When `clone_url_format: ssh`, `fetch` shows the SSH clone URL in
         `clone_url` (e.g. `git@github.com:user/repo.git`).
  AC-05: When `clone_url_format: https`, `fetch` shows the HTTPS clone URL in
         `clone_url` (e.g. `https://github.com/user/repo.git`).
  AC-06: `track git@github.com:user/repo.git` correctly derives the project
         name as `repo` and path as `{clone_root}/repo`.
  AC-07: `track https://github.com/user/repo.git` continues to work as before.
  AC-08: `RemoteRepo.repo_url` is always the browser URL regardless of
         `clone_url_format`.

## Data model changes

### `foundry/__init__.py` — `RemoteRepo`

Replace the single `clone_url` field with two fields:

```python
@dataclass
class RemoteRepo:
    name: str
    repo_url: str    # browser URL (always https, e.g. https://github.com/user/repo)
    clone_url: str   # clone URL — HTTPS or SSH depending on clone_url_format
    pushed_at: str
    default_branch: str
    visibility: str
    description: str
```

### `config.py` — `Config`

Add one field:

```python
@dataclass
class Config:
    clone_root: str
    foundries: list[FoundryConfig]
    projects: list[Project] = field(default_factory=list)
    clone_url_format: str = "ssh"   # "https" | "ssh"
```

No schema migration needed — `load_config()` uses `.get()` with a default.

## Execution flow

### Happy flow

1. User runs `git-projects fetch`.
2. `cli.py` loads config (now includes `clone_url_format`).
3. `fetch_repos()` in `services.py` passes `cfg.clone_url_format` to each
   foundry client's `list_repos()`.
4. Each foundry client populates `repo_url` from the API's `html_url` and
   `clone_url` from either `clone_url` (HTTPS) or `ssh_url` (SSH) based on
   the format argument.
5. `cli.py` calls `format_repo(repo)` for each repo.
6. `format_repo` renders:
   - Line 1: `name [visibility] ... date` (unchanged)
   - Line 2: `  <repo_url>` (dim) — browser URL
   - Line 3: `  <clone_url>` (dim) — clone URL in configured format
   - Line 4: description if present (unchanged)

### Non-happy flow

**User has `clone_url_format: ssh` but pastes an HTTPS URL into `track`:**
- `derive_project` receives an HTTPS URL and parses it correctly as before.
- No error — `derive_project` handles both formats regardless of config.

## API / interface changes

### Modified: `src/git_projects/foundry/__init__.py`

```python
@dataclass
class RemoteRepo:
    name: str
    repo_url: str
    clone_url: str
    pushed_at: str
    default_branch: str
    visibility: str
    description: str
```

### Modified: `src/git_projects/foundry/github.py`

Signature change:
```python
def list_repos(config: FoundryConfig, clone_url_format: str = "ssh") -> list[RemoteRepo]:
```

Construction change:
```python
RemoteRepo(
    name=item["name"],
    repo_url=item["html_url"],
    clone_url=item["ssh_url"] if clone_url_format == "ssh" else item["clone_url"],
    pushed_at=item["pushed_at"],
    default_branch=item["default_branch"],
    visibility=item["visibility"],
    description=item["description"] or "",
)
```

### Modified: `src/git_projects/foundry/gitea.py`

Signature change:
```python
def list_repos(config: FoundryConfig, clone_url_format: str = "ssh") -> list[RemoteRepo]:
```

Construction change:
```python
RemoteRepo(
    name=item["name"],
    repo_url=item["html_url"],
    clone_url=item["ssh_url"] if clone_url_format == "ssh" else item["clone_url"],
    pushed_at=item["updated_at"],
    default_branch=item["default_branch"],
    visibility="private" if item["private"] else "public",
    description=item["description"] or "",
)
```

### Modified: `src/git_projects/services.py`

`fetch_repos()` passes `clone_url_format` to each client:
```python
def fetch_repos(
    config: Config,
    foundry_name: str | None = None,
    *,
    show_all: bool = False,
    on_foundry_start: Callable[[str], None] | None = None,
) -> list[RemoteRepo]:
```

Inside, each `list_repos` call becomes:
```python
list_repos(foundry_cfg, config.clone_url_format)
```

### Modified: `src/git_projects/formatting.py`

```python
def format_repo(repo: RemoteRepo, width: int = 60, max_desc: int = 60) -> str:
    """Return an indented multi-line block describing one remote repo."""
```

- No `clone_url_format` parameter — format was already applied at fetch time.
- Renders `repo.repo_url` and `repo.clone_url` on separate dimmed lines.

### Modified: `src/git_projects/config.py`

```python
@dataclass
class Config:
    clone_root: str
    foundries: list[FoundryConfig]
    projects: list[Project] = field(default_factory=list)
    clone_url_format: str = "ssh"
```

`load_config()` change:
```python
return Config(
    clone_root=str(raw.get("clone_root", "")),
    foundries=foundries,
    projects=projects,
    clone_url_format=str(raw.get("clone_url_format", "ssh")),
)
```

`DEFAULT_CONFIG` gains:
```yaml
clone_url_format: ssh     # "https" or "ssh"
```

`derive_project()` updated to handle SSH SCP-style URLs:
```python
import re

_SSH_RE = re.compile(r"^git@[^:]+:(.+)$")

def derive_project(clone_url: str, clone_root: str) -> Project:
    """Derive project name and path from a clone URL (HTTPS or SSH)."""
    m = _SSH_RE.match(clone_url)
    if m:
        path_part = m.group(1)
    else:
        path_part = urlparse(clone_url).path
    name = path_part.strip("/").removesuffix(".git").split("/")[-1]
    local_path = str(Path(clone_root) / name)
    return Project(clone_url=clone_url, name=name, path=local_path)
```

### Modified: `src/git_projects/cli.py`

`fetch` command no longer passes format to `format_repo`:
```python
print(format_repo(repo), end="")
```

No other changes to `cli.py`.

## Affected modules

| Module                   | Change                                                              |
|--------------------------|---------------------------------------------------------------------|
| `foundry/__init__.py`    | **Modified** — replace `clone_url` with `repo_url` + `clone_url`  |
| `foundry/github.py`      | **Modified** — add `clone_url_format` param, populate `repo_url`  |
| `foundry/gitea.py`       | **Modified** — add `clone_url_format` param, populate `repo_url`  |
| `services.py`            | **Modified** — pass `config.clone_url_format` to `list_repos()`   |
| `config.py`              | **Modified** — add `clone_url_format` to `Config`, update `DEFAULT_CONFIG`, `load_config`, `derive_project` |
| `formatting.py`          | **Modified** — render `repo_url` and `clone_url` on separate lines |
| `cli.py`                 | **Modified** — drop `clone_url_format` arg from `format_repo` call |
| `gitops.py`              | None                                                                |

## Implementation notes

- Both GitHub and Gitea REST APIs return `html_url`, `ssh_url`, and `clone_url`
  as first-class fields with identical JSON key names — confirmed against the
  Gitea Go SDK source (`repo.go`) and GitHub API docs.
- The `_SSH_RE` regex in `derive_project` handles the SCP-style format used
  by all major git hosts (`git@github.com:user/repo.git`). Standard
  `ssh://git@host/user/repo.git` URLs are handled by `urlparse` unchanged.
- `clone_url_format` is applied once at fetch time inside the foundry client.
  Downstream code (`formatting.py`, `cli.py`) is format-agnostic.
- Existing tests that construct `RemoteRepo` directly will need `clone_url`
  replaced with `repo_url` + `clone_url` (two fields, both required).

## Open questions

None.
