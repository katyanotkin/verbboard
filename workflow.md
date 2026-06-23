# Agent Workflow

Standard agent invocation order for VerbBoard feature work. Each phase gates the next.

## Phase 1 -- Explore (always first)

Use `Explore` agent before touching any code. Search for relevant files, existing patterns, callers of the function being changed. Quick for a targeted lookup; very thorough for cross-cutting changes.

Skip only when the file and line are already known and the change is isolated.

## Phase 2 -- Design (before writing code)

| Trigger | Agent |
|---|---|
| Cross-cutting state, shared functions, infra changes | `senior-architect` |
| New feature with multi-file scope | `Plan` |
| Small, self-contained change | Skip -- proceed inline |

Never start implementation until design is settled.

## Phase 3 -- Implement

| Task type | Agent or inline |
|---|---|
| UI layout, CSS, interaction | `ui-ux-engineer` |
| Route handlers, RedirectResponse assembly, nav-link param wiring | `senior-web-engineer` |
| `/api/*` endpoints, fetch calls, Firebase auth flow, cookie usage | `senior-web-engineer` |
| XSS-sensitive HTML assembly (render.py, admin JS template literals) | `senior-web-engineer` |
| Backend Python, data model (non-routing) | Inline (main context) |
| Writing/copy/changelog | `writer` |
| Any other code | Inline |

## Phase 4 -- Review (after every code change)

`code-reviewer` -- always invoke after writing or modifying code, before calling qa-engineer.

## Phase 5 -- Tests (after reviewer approves)

`qa-engineer` -- writes or updates tests. Invoke only after code-reviewer has approved. Never write tests before the reviewer runs.

## Phase 6 -- Verify (optional, UI changes)

Use `/verify` skill to confirm the feature works in the live app. Required for any UI golden-path change.

---

Trivial one-liners (typo fix, single-constant change): phases 2 and 5 may be skipped.
