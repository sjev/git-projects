---
description: Review code as a software architect and score on 5 KPIs.
argument-hint: [files or context]
---

# Task
Review this codebase as a software architect. Score each aspect 0–10.

## KPIs

1. **Maintainability:** How easily can the system be debugged, modified, or understood?
   - *Metrics:* Modularity, Cohesion, Coupling, Readability, Simplicity.
2. **Extensibility:** How easily can new features be added without major refactoring?
   - *Metrics:* Separation of Concerns, Dependency Injection, Use of Interfaces (Protocols).
3. **Testability:** How easily can components be tested in isolation and as a whole?
   - *Metrics:* Use of Pure Functions, Mocking, Dependency Inversion.
4. **Robustness & Reliability:** How well does the system handle edge cases, errors, and real-world conditions?
   - *Metrics:* State Management, Predictability, Fault Tolerance.
5. **Clarity:** How quickly can a new developer understand the system's design and purpose?
   - *Metrics:* Documentation, Consistent Naming, Clear Abstractions.

## Output
Report findings in `docs/review.md` with:
- A header table with review date, reviewer model/version, and codebase stats (LOC, test count, coverage).
- ALWAYS include your model/version information.
- One section per KPI: score, strengths (bullets), weaknesses (bullets).
- A summary table with all scores and an overall average.
- A "Priority Recommendations" section with the top 5 actionable improvements.

Rules:
- Run the test suite first to verify baseline health and gather coverage stats.
- Be specific — cite `file:line` or `file:function` when pointing out issues.
- No filler — every bullet must be actionable or informative.
- If `$ARGUMENTS` includes specific files or areas, prioritize those.

# Input
$ARGUMENTS
