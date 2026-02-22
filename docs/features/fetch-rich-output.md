# Design: Fetch Rich Output

## Summary

The `fetch` command currently prints a flat list of clone URLs. This feature replaces that output with a formatted section per repository showing name, URL, last-push timestamp (as human-relative time), and description (truncated). The goal is to give the user enough context to decide which repos to `track` without leaving the terminal.

## Scope

- **In scope:**
  - Formatting `fetch` output as one section per repo with name, URL, relative time, and description.
  - Human-relative time rendering from the `pushed_at` ISO timestamp already returned by foundry clients.
  - Truncating long descriptions to a configurable max width.
  - All foundry clients returning the same `RemoteRepo` fields (already the case).
- **Out of scope:**
  - Adding new API fields beyond what `RemoteRepo` already provides.
  - Interactive selection / filtering of repos.
  - Colour or rich-library formatting (plain text only, per architecture constraints).
  - Changing the `RemoteRepo` dataclass or foundry client signatures.

## Acceptance criteria

- AC-01: Running `fetch` prints one visually distinct section per repo containing: name, clone URL, relative time (e.g. "3 days ago"), and description.
- AC-02: Repos are printed in most-recently-pushed-first order (preserved from API response).
- AC-03: Descriptions longer than 60 characters are truncated with an ellipsis (`…`).
- AC-04: Repos with an empty description show no description line (not a blank or placeholder).
- AC-05: The relative-time string uses human-friendly units: "just now", "5 minutes ago", "3 hours ago", "2 days ago", "4 months ago", "1 year ago".
- AC-06: The foundry header line still shows `# foundry-name (N repos)`.
- AC-07: No new third-party dependencies are introduced; relative time is computed with stdlib `datetime`.

## Data model changes

None. `RemoteRepo` already carries `name`, `clone_url`, `pushed_at`, `description`.

## Execution flow

### Happy flow

1. User runs `git-projects fetch [foundry]`.
2. CLI loads config, resolves target foundries.
3. For each foundry, the foundry client returns `list[RemoteRepo]` (unchanged).
4. CLI calls a new formatting function to render each repo as a multi-line section.
5. Output is printed to stdout.

Example output:
```
# github (3 repos)

  my-app
  https://github.com/user/my-app.git
  A web application for managing tasks
  3 days ago

  old-experiment
  https://github.com/user/old-experiment.git
  2 years ago

  utils
  https://github.com/user/utils.git
  Shared utility functions for internal proje…
  6 months ago
```

### Non-happy flow

No change from current behaviour — API errors and missing tokens already handled in `cli.py`.

## API / interface changes

### New function in `cli.py` (private helper)

```python
def _format_repo(repo: RemoteRepo, max_desc: int = 60) -> str:
```
- **Input**: A `RemoteRepo` instance and optional max description length.
- **Validation**: None needed — `RemoteRepo` is already validated by the foundry client.
- **Returns**: A multi-line string block for one repo (name, URL, relative time, optional description). Each line indented with 2 spaces. Trailing blank line included as separator.

### New function in `cli.py` (private helper)

```python
def _relative_time(iso_timestamp: str) -> str:
```
- **Input**: ISO 8601 timestamp string (e.g. `"2024-11-15T10:30:00Z"`).
- **Validation**: Raises `ValueError` on unparseable input (caller already trusts foundry data).
- **Returns**: Human-relative string like `"3 days ago"`, `"2 years ago"`, `"just now"`.

### Modified: `fetch` command in `cli.py`

The print loop changes from:
```python
for repo in repos:
    print(f"  {repo.clone_url}")
```
to:
```python
for repo in repos:
    print(_format_repo(repo))
```

## Affected modules

| Module | Change |
|--------|--------|
| `cli` | Replace the repo print loop in `fetch` with `_format_repo()`. Add `_format_repo()` and `_relative_time()` private helpers. |

No other modules are touched. Foundry clients, config, and data types remain unchanged.

## Implementation notes

- `_relative_time` should parse with `datetime.fromisoformat()` (Python 3.11+ handles the `Z` suffix). Compare against `datetime.now(timezone.utc)`.
- Time thresholds: <60s → "just now", <60m → "N minutes ago", <24h → "N hours ago", <30d → "N days ago", <365d → "N months ago", else → "N years ago".
- Truncation: slice description to `max_desc - 1` chars and append `…` only when the description actually exceeds `max_desc`.
- The architecture doc notes "CLI output: plain text with minimal formatting (no rich/tables unless explicitly requested later)". Sections with indented lines fit this constraint.

## Open questions

None — all decisions resolved in clarification.
