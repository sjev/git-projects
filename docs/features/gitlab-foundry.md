# Design: GitLab Foundry

## Summary

Adds a GitLab foundry client (`foundry/gitlab.py`) that implements the same
`list_repos(config: FoundryConfig) -> list[RemoteRepo]` interface as the
existing GitHub and Gitea clients. Also updates `services.py` to dispatch to
the new client when a foundry entry has `type: gitlab`. This lets users run
`git-projects fetch` against GitLab.com or any self-hosted GitLab instance
already listed in their `config.yaml`.

## Scope

- In scope:
  - `src/git_projects/foundry/gitlab.py` with `list_repos` and a private
    `_next_url` pagination helper (same pattern as `github.py` and `gitea.py`)
  - `services.py`: add `elif foundry_config.type == "gitlab"` dispatch branch
    and import `gitlab` alongside the existing imports
- Out of scope:
  - Changes to `config.py`, `cli.py`, or `formatting.py`
  - OAuth2 / OIDC auth flows — personal access token only
  - Group or organisation repos — owned repos only
  - GitLab sub-groups

## Acceptance criteria

  AC-01: `list_repos` returns a non-empty `list[RemoteRepo]` when the GitLab
         API responds with at least one repo page.
  AC-02: `list_repos` follows pagination: when the response `Link` header
         contains a `rel="next"` URL, a second request is made; results from
         all pages are combined.
  AC-03: `RemoteRepo.clone_url` is populated from `ssh_url_to_repo`.
  AC-04: `RemoteRepo.pushed_at` is populated from `last_activity_at`
         (ISO 8601 UTC string).
  AC-05: `RemoteRepo.visibility` contains the GitLab value verbatim
         (`"public"`, `"internal"`, or `"private"`).
  AC-06: A `null` GitLab `description` is normalised to `""`.
  AC-07: `list_repos` raises `ValueError("GitLab token is not set.")` when
         `config.token` is empty or `None`.
  AC-08: HTTP errors (4xx/5xx) from the GitLab API propagate as
         `httpx.HTTPStatusError` without being swallowed.
  AC-09: `fetch_repos` in `services.py` returns results for a foundry with
         `type: gitlab`; unknown types continue to be silently skipped.

## Data model changes

None. `RemoteRepo` already covers all required fields; `FoundryConfig.type`
already accepts arbitrary strings.

## Execution flow

### Happy flow

1. User runs `git-projects fetch my-gitlab` (or `fetch` with no argument).
2. `cli.py` calls `services.fetch_repos(cfg, "my-gitlab")`.
3. `services.py` iterates foundries, finds `type == "gitlab"`, calls
   `gitlab.list_repos(foundry_config)`.
4. `gitlab.list_repos` raises `ValueError` if `config.token` is falsy,
   otherwise builds `Authorization: Bearer <token>` headers.
5. First GET to `{config.url}/api/v4/projects?owned=true&order_by=last_activity_at&sort=desc&per_page=100`.
6. Converts each JSON item to `RemoteRepo`; reads `Link` header.
7. If `Link` contains `rel="next"`, fetches the next page; repeats until no
   next link.
8. Returns full `list[RemoteRepo]` to `services.py`.
9. `services.py` applies the 180-day recency filter (unless `show_all=True`)
   and returns `{foundry_name: [repos]}`.
10. `cli.py` formats and prints the repos.

### Non-happy flow

**Missing token**:
- `gitlab.list_repos` checks `config.token` before creating the HTTP client.
- Raises `ValueError("GitLab token is not set.")`.
- `services.py` does not catch this; it propagates to `cli.py`, which prints
  the error and exits with a non-zero code (same path as GitHub/Gitea token
  errors).

## API / interface changes

### New: `src/git_projects/foundry/gitlab.py`

```python
def list_repos(config: FoundryConfig) -> list[RemoteRepo]: ...
```

- **Input validation**: raises `ValueError` if `config.token` is falsy.
- **HTTP**: GET `{base_url}/api/v4/projects?owned=true&order_by=last_activity_at&sort=desc&per_page=100`
  where `base_url = (config.url or _DEFAULT_URL).rstrip("/")` and
  `_DEFAULT_URL = "https://gitlab.com"`.
  - Headers: `Authorization: Bearer {token}`, `Accept: application/json`,
    `User-Agent: git-projects/0.1`.
  - Pagination via `Link` response header (`rel="next"`), identical pattern to
    `github.py` and `gitea.py`.
- **Field mapping** (GitLab JSON → `RemoteRepo`):

  | GitLab field          | RemoteRepo field  | Notes                               |
  |-----------------------|-------------------|-------------------------------------|
  | `name`                | `name`            | direct                              |
  | `ssh_url_to_repo`     | `clone_url`       | SSH clone URL                       |
  | `last_activity_at`    | `pushed_at`       | ISO 8601 UTC string                 |
  | `default_branch`      | `default_branch`  | direct                              |
  | `visibility`          | `visibility`      | verbatim: `"public"` / `"internal"` / `"private"` |
  | `description`         | `description`     | `None` → `""`                      |

- **Returns**: `list[RemoteRepo]`, may be empty if user owns no repos.
- **Errors**: `httpx.HTTPStatusError` on 4xx/5xx; `ValueError` on missing token.

### Modified: `src/git_projects/services.py`

Add an `elif` branch in `fetch_repos` after the existing `gitea` branch:

```python
elif foundry_config.type == "gitlab":
    repos = gitlab.list_repos(foundry_config)
```

Add `gitlab` to the existing foundry import:

```python
from git_projects.foundry import RemoteRepo, gitea, github, gitlab
```

## Affected modules

| Module               | Change                                              |
|----------------------|-----------------------------------------------------|
| `foundry/gitlab.py`  | **New** — full GitLab API client                    |
| `services.py`        | **Modified** — add `elif type == "gitlab"` dispatch + import |
| `foundry/__init__.py`| None                                                |
| `config.py`          | None                                                |
| `cli.py`             | None                                                |

## Implementation notes

- The `_next_url` helper is duplicated from `github.py` / `gitea.py` into
  `gitlab.py`. All three parse the RFC 5988 `Link` header identically. Sharing
  it via `foundry/__init__.py` is a valid DRY improvement but is out of scope.
- The recency filter in `services.py` uses
  `datetime.fromisoformat(r.pushed_at.replace("Z", "+00:00"))`. GitLab's
  `last_activity_at` is in ISO 8601 UTC with a `Z` suffix; this pattern
  already handles it correctly.
- GitLab `default_branch` can be `None` for empty repositories. Map `None`
  to `""` (same defensive handling as `description`).
- `per_page=100` is GitLab's maximum for this endpoint.
- The `config.url` for GitLab.com should be `https://gitlab.com`; the API
  path `/api/v4/` is appended by the client, not expected in the config URL.
- `Authorization: Bearer` works for both personal access tokens and OAuth2
  tokens on GitLab 13.0+. The legacy `PRIVATE-TOKEN` header is not used.

## Open questions

None — all scope and field-mapping decisions resolved above.
