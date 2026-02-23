# Architecture Review: git-projects

| Field        | Value                         |
|-------------|-------------------------------|
| Date        | 2026-02-23                    |
| Reviewer    | Claude Sonnet 4 (Copilot CLI v0.0.414) |
| Commit      | HEAD                          |
| Codebase    | ~1000 LOC source, ~1800 LOC tests, 131 tests passing, 90% coverage |

---

## 1. Maintainability — **8 / 10**

**Strengths:**
- Clean module boundaries: `cli → services → foundry/config/index/gitops`. Each module has a single, well-defined responsibility.
- Small files — the largest source file (`cli.py`) is 287 lines. No file exceeds 300 lines. Easy to navigate.
- Dataclasses over classes: `Config`, `FoundryConfig`, `Project`, `RemoteRepo`, `SyncResult` are plain data with no inheritance hierarchies.
- Functions over methods: business logic lives in module-level functions, not in class methods. This keeps call paths shallow and explicit.
- Consistent code style enforced via `ruff` (100-char lines, import sorting, simplification rules) and `mypy --strict`.

**Weaknesses:**
- Duplicated `_next_url()` across all three foundry clients (github.py, gitea.py, gitlab.py) — identical implementation, should be extracted to `foundry/__init__.py` or a shared utility.
- Duplicated `relative_time()` in `formatting.py` and `_format_age()` in `cli.py` — two functions doing the same job with slightly different output formats. This will cause drift.
- The `if/elif` dispatch in `_fetch_one()` (services.py:35-42) for selecting the right foundry client is a manual registry. Adding a new foundry type requires editing this function.

---

## 2. Extensibility — **7 / 10**

**Strengths:**
- Adding a new foundry is straightforward: create `foundry/newtype.py` with `list_repos(config, clone_url_format) -> list[RemoteRepo]`, add an `elif` branch in `services.py`, done. The contract is clear even without a formal Protocol.
- The `RemoteRepo` dataclass normalizes all foundry outputs — consumers never see GitHub/GitLab/Gitea-specific shapes.
- `projects.json` separation from `config.yaml` was a forward-looking decision — enables portability and sharing without exposing credentials.
- `SyncResult` dataclass and `on_project` callback in `sync_projects()` cleanly separate sync logic from presentation.

**Weaknesses:**
- No `Protocol` / interface for foundry clients. The implicit contract (`list_repos(config, format) -> list[RemoteRepo]`) works today but will become fragile as the number of foundry types grows. A `FoundryClient` Protocol would enable static checking and discovery.
- The foundry dispatch in `_fetch_one()` is a closed `if/elif` chain. A registry pattern (dict mapping `type` → module/function) would make this open for extension.
- `clone_url_format` is stringly typed (`"ssh"` | `"https"`). A `Literal` type or enum would prevent invalid values and improve IDE support.
- Several incomplete features noted in CLAUDE.md (`history`, `export/import`, migration) — the architecture supports them but nothing is stubbed out or planned in code.

---

## 3. Testability — **9 / 10**

**Strengths:**
- 131 tests, 90% overall coverage, 100% on core modules (config, github, gitops, index).
- Functions take explicit dependencies as arguments — `fetch_repos(cfg, foundry_name)`, `sync_projects(projects, on_project)`, `track_project(cfg, name_or_url, path)`. No hidden global state.
- All external I/O is cleanly mockable: `monkeypatch.setattr` for path functions, `patch` for API clients and subprocess calls, `tmp_path` for filesystem tests. No real network or git calls in tests.
- `CliRunner` tests cover the full CLI surface including error paths (missing config, auth failures, ambiguous names).
- Tests follow a consistent pattern: setup → action → assertion, with descriptive names referencing acceptance criteria (e.g., `# AC-08: duplicate rejected`).

**Weaknesses:**
- Gitea and GitLab clients have low coverage (30% and 34%) — only the GitHub client has dedicated tests. Since the three clients share identical structure, this is low-risk but still a gap.
- No integration tests that exercise the real filesystem with actual git repos (e.g., clone → is_dirty → pull cycle). The gitops module is tested via subprocess mocks only.

---

## 4. Robustness & Reliability — **6 / 10**

**Strengths:**
- Error paths are handled at the CLI layer: `FileNotFoundError → "run config init"`, `ValueError → exit 1`, `httpx.HTTPStatusError → friendly message`. User never sees raw tracebacks.
- `sync_projects()` continues processing after individual project errors — one failed clone/pull doesn't abort the batch.
- Dirty repo detection before sync prevents accidental overwrites of uncommitted work.
- Pagination in all foundry clients handles large repo lists correctly.

**Weaknesses:**
- **No input validation on config values.** `clone_root`, `clone_url_format`, `foundry.type` are accepted as-is from YAML. A typo in `clone_url_format: sssh` silently produces wrong clone URLs. No validation on load.
- **No file locking.** `projects.json` and `config.yaml` are read-modify-written without locks. Concurrent CLI invocations could corrupt data.
- **No retry logic** on HTTP requests. A transient network error during `remote fetch` fails the entire operation. httpx timeouts are configured but no retry/backoff.
- **`pushed_at` stored as raw string**, not validated as ISO 8601 on write or load. Malformed timestamps from APIs would propagate silently and fail at display time.
- **`subprocess.run` without timeout** in gitops.py — a hung `git pull` or `git push` will block the process indefinitely.
- **`description` field** accessed as `r.description.lower()` in `search_index()` — if description is `None` (which foundry clients guard against, but index.json could be hand-edited), this raises `AttributeError`.

---

## 5. Clarity — **8 / 10**

**Strengths:**
- Excellent documentation: `README.md` has install, quick start, command table, config examples, and multi-machine setup. `docs/architecture.md` provides a thorough system overview with Mermaid diagrams, decision records, and module boundary specs.
- `CLAUDE.md` serves as effective developer onboarding — commands, architecture summary, code conventions, and known gaps in one page.
- Consistent naming: `load_X() / save_X()` pairs, `get_X_path()` for path discovery, `list_repos()` for foundry clients.
- One-liner docstrings on every public function. Not overdone — just enough context.
- Clear layered architecture: CLI → Services → (Foundry + Config + Index + GitOps). No circular dependencies.

**Weaknesses:**
- `foundry` as a term may confuse newcomers — it's domain jargon for "git hosting platform." A brief glossary in the README or architecture doc would help.
- The `services.py` module name is generic. It's really the orchestration layer — `orchestrator.py` or keeping the current name with a module docstring would clarify its role.
- `docs/features/` directory exists but is empty. Either populate it or remove it to avoid confusion.
- The `user-stories.md` file in docs was not reviewed but its existence alongside the architecture doc suggests planning artifacts that may go stale.

---

## Summary

| KPI                       | Score | Notes |
|--------------------------|-------|-------|
| **Maintainability**      | 8/10  | Clean modules, small files, some duplication to address |
| **Extensibility**        | 7/10  | Good data normalization, needs Protocol + registry pattern for foundries |
| **Testability**          | 9/10  | Strong coverage, excellent mock strategy, minor gaps in gitea/gitlab |
| **Robustness**           | 6/10  | Happy paths solid; validation, retries, locking, and timeouts missing |
| **Clarity**              | 8/10  | Excellent docs and naming, minor terminology and empty-dir issues |
| **Overall**              | **7.6/10** | Well-architected for its size and stage. Main risk is robustness. |

## Priority Recommendations

1. **Add config validation on load** — validate `clone_url_format` values, foundry `type`, non-empty `clone_root`. Fail fast with clear messages.
2. **Extract shared foundry utilities** — move `_next_url()` to `foundry/__init__.py`, consolidate relative-time functions.
3. **Add subprocess timeouts** in gitops.py — `subprocess.run(..., timeout=120)` prevents hangs.
4. **Define a `FoundryClient` Protocol** — formalize the contract, enable mypy to catch foundry client mismatches.
5. **Add Gitea/GitLab test coverage** — even minimal tests matching the GitHub pattern would close the gap cheaply.
