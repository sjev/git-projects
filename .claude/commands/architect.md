---
description: Create architectural overview
argument-hint: [files or context]
---

You are a senior software architect. Before designing anything, identify what
you don't know. Ask me up to 5 clarifying questions — prioritize questions
that would change the architecture. Wait for my answers before proceeding.

the project documentation is in `docs` folder.
For context, use `docs/user-stories.md` file if available.


Once you have enough context, produce a project architecture document `docs/architecture.md` with these sections:

# Architecture: [Project Name]

## Problem and context
What problem this solves and for whom.

## Goals and non-goals
Numbered goals with measurable criteria. Explicit non-goals.

## System overview
One paragraph. Then a Mermaid component diagram showing the major
components, their responsibilities, and how they communicate.

## Technology stack
| Component | Technology | Version | Rationale |

## Module boundaries
For each module: what it owns, its public interface, and what it must NOT
do. Communication patterns between modules (sync/async, events, RPC).

## Key architectural decisions
For each significant decision:
- **Decision:** What was chosen
- **Alternatives considered:** What else was evaluated
- **Rationale:** Why this option

## Constraints and conventions
Tech stack rules, naming conventions, forbidden libraries, coding patterns
to follow project-wide.

## Open questions
Unresolved items that will be decided at feature-design time.

---
Rules:
- Keep the document as short as reasonably possible
- Mermaid diagrams only (no images)
- Be specific — version numbers, concrete patterns, not "we will use best practices"
- Flag every assumption with [ASSUMPTION]

# Input
$ARGUMENTS
