# Design: Gitea Foundry

## Summary

Adds a Gitea foundry client (`foundry/gitea.py`) that implements the same
`list_repos(config: FoundryConfig) -> list[RemoteRepo]` interface as the
existing GitHub client. Also updates `services.py` to dispatch to the new
client when a foundry entry has `type: gitea`. This lets users run
`git-projects fetch` against any self-hosted Gitea instance already listed in
their `config.yaml`.

## Scope

- In scope:
  - `src/git_projects/foundry/gitea.py` with `list_repos` and a private
    `_next_url` pagination helper (duplicated from `github.py`)
  - `services.py`: add `elif foundry_config.type == "gitea"` dispatch branch
    with the same recency-filter logic used for GitHub
- Out of scope:
  - GitLab foundry (separate feature)
  - Changes to `config.py`, `cli.py`, or `formatting.py`
  - Support for Gitea OAuth2 flows — token-based auth only
  - Fetching organisations' repos — accessible-to-user repos only

## Acceptance criteria

  AC-01: `list_repos` returns a non-empty `list[RemoteRepo]` when the Gitea
         API responds with at least one repo page.
  AC-02: `list_repos` follows pagination: when the response `Link` header
         contains a `rel="next"` URL, a second request is made; results from
         all pages are combined.
  AC-03: Every `RemoteRepo` has `pushed_at` populated from the Gitea response
         `updated` field (ISO 8601 UTC string).
  AC-04: `visibility` is `"private"` when `private == true` in the response,
         `"public"` otherwise.
  AC-05: A `null` Gitea `description` is normalised to `""`.
  AC-06: `list_repos` raises `ValueError("Gitea token is not set.")` when
         `config.token` is empty or `None`.
  AC-07: HTTP errors (4xx/5xx) from the Gitea API propagate as
         `httpx.HTTPStatusError` without being swallowed.
  AC-08: `fetch_repos` in `services.py` returns results for a foundry with
         `type: gitea`; unknown types are silently skipped (existing behaviour
         preserved).

## Data model changes

None. `RemoteRepo` already covers all fields; `FoundryConfig.type` already
accepts arbitrary strings.

## Execution flow

### Happy flow

1. User runs `git-projects fetch my-gitea` (or `fetch` with no argument).
2. `cli.py` calls `services.fetch_repos(cfg, "my-gitea")`.
3. `services.py` iterates foundries, finds `type == "gitea"`, calls
   `gitea.list_repos(foundry_config)`.
4. `gitea.list_repos` builds `Authorization: Bearer <token>` headers.
5. First GET to `{config.url}/api/v1/user/repos?limit=50&page=1`.
6. Converts each JSON item to `RemoteRepo`; reads `Link` header.
7. If `Link` contains `rel="next"`, fetches the next page; repeats until no
   next link.
8. Returns full `list[RemoteRepo]` to `services.py`.
9. `services.py` applies the 180-day recency filter (unless `show_all=True`)
   and returns `{foundry_name: [repos]}`.
10. `cli.py` formats and prints the repos.

### Non-happy flow

**Missing token**:
- `gitea.list_repos` checks `config.token` before creating the HTTP client.
- Raises `ValueError("Gitea token is not set.")`.
- `services.py` does not catch this; it propagates to `cli.py`, which prints
  the error and exits with a non-zero code (same path as the GitHub token
  error).

## API / interface changes

### New: `src/git_projects/foundry/gitea.py`

```python
def list_repos(config: FoundryConfig) -> list[RemoteRepo]: ...
```

- **Input validation**: raises `ValueError` if `config.token` is falsy.
- **HTTP**: GET `{config.url}/api/v1/user/repos?limit=50&page={n}`.
  - Headers: `Authorization: Bearer {token}`, `Accept: application/json`,
    `User-Agent: git-projects/0.1`.
  - Pagination via `Link` response header (`rel="next"`), identical pattern to
    `github.py`.
- **Field mapping** (Gitea JSON → `RemoteRepo`):

  | Gitea field      | RemoteRepo field  | Notes                            |
  |------------------|-------------------|----------------------------------|
  | `name`           | `name`            | direct                           |
  | `clone_url`      | `clone_url`       | direct                           |
  | `updated`        | `pushed_at`       | ISO 8601 UTC string              |
  | `default_branch` | `default_branch`  | direct                           |
  | `private` (bool) | `visibility`      | `True` → `"private"`, else `"public"` |
  | `description`    | `description`     | `None` → `""`                   |

- **Returns**: `list[RemoteRepo]`, may be empty if user has no repos.
- **Errors**: `httpx.HTTPStatusError` on 4xx/5xx; `ValueError` on missing
  token.

### Modified: `src/git_projects/services.py`

Add an `elif` branch in `fetch_repos` after the existing `github` branch:

```python
elif foundry_config.type == "gitea":
    repos = gitea.list_repos(foundry_config)
    if not show_all:
        repos = [
            r
            for r in repos
            if datetime.fromisoformat(r.pushed_at.replace("Z", "+00:00")) >= cutoff
        ]
    result[foundry_config.name] = repos
```

Import `gitea` alongside the existing `github` import at the top of the file.

## Affected modules

| Module | Change |
|--------|--------|
| `foundry/gitea.py` | **New** — full Gitea API client |
| `services.py` | **Modified** — add `elif type == "gitea"` dispatch + import |
| `foundry/__init__.py` | None |
| `config.py` | None |
| `cli.py` | None |

## Implementation notes

- The `_next_url` helper is duplicated from `github.py` into `gitea.py`. Both
  parse the RFC 5988 `Link` header identically. Moving it to
  `foundry/__init__.py` is a valid DRY improvement but is out of scope here.
- Gitea endpoint `/api/v1/user/repos` returns repos the authenticated user
  owns **or has access to** (covers owner + member + collaborator), matching
  the chosen "all accessible repos" scope.
- The `updated` timestamp is UTC; no timezone conversion needed — format is
  compatible with the recency-filter `datetime.fromisoformat` call already
  used for GitHub (the `.replace("Z", "+00:00")` pattern works for both).
- Some Gitea instances (1.15+) include a `visibility` string field
  (`"public"` / `"limited"` / `"private"`). We do **not** use it — mapping
  from `private: bool` is simpler and works across all versions.
- `limit=50` keeps response sizes reasonable; Gitea's default max is 50.

## Open questions

None — all scope and field-mapping decisions resolved above.
