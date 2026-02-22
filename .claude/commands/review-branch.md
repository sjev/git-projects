---
description: Compare current branch to main and review for cohesion, coupling, complexity, and duplication.
argument-hint: [files or context]
---

# Task
Compare the current branch against `main`.

## 1) Context
Run:
- `git diff main...HEAD`

## 2) Review criteria (only flag issues)
- **Cohesion:** unclear responsibilities, “god objects”, scattered logic.
- **Coupling:** unnecessary deps, leaky abstractions, hard-to-test integration.
- **Complexity:** deep nesting, many branches, overly long functions.
- **Duplication:** copy/paste logic, near-duplicates, missing shared utilities.

## 3) Output
- Start with 1–2 bullets: **What changed** (high level).
- Then **max 10 bullets** with actionable improvements.
- IMPORTANT: separate improvements in two sections: Critial: these issues may cause problems later. Suggestions: less important items regarding SOLID software design.
- Each bullet must include: `file:line` (or `file:function`) + what to change + why.
- If `$ARGUMENTS` includes `path=...`, prioritize that area first.
- No compliments; improvements only.

# Input
$ARGUMENTS
