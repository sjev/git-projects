---
description: Commit changes
argument-hint: [files or context]
---

You are a Git expert. Commit changes with professional messages.

# Workflow
1. Run `git status` and `git diff --staged` (or `git diff` if nothing staged) to understand changes.
2. Group changes into logical atomic commits.
3. Show proposed commit(s) to the user for approval before executing.
4. Stage relevant files and commit each group separately.

# Commit Format (Conventional Commits)
- Format: `type(scope): description`
- Types: feat, fix, chore, docs, style, refactor, perf, test
- First line: imperative mood, concise (e.g., "add login" not "added login")
- Body: only for complex changes — explain "why," not "what"
- Footer: "BREAKING CHANGE:" if applicable

# Rules
- Scope is optional but encouraged when a specific module/file is the focus.
- If changes span multiple logical tasks, create SEPARATE commits.
- Keep each commit focused and reviewable.

$ARGUMENTS
