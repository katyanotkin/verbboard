# Agent Workflow

Standard agent invocation order for VerbBoard feature work. Each phase gates the next.

## Phase 1 -- Explore (always first)

Use `Explore` agent before touching any code.

Search for:
- relevant files
- existing patterns
- callers of the function being changed
- related tests

Use **quick** for a targeted lookup; **very thorough** for cross-cutting changes.

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
| Route handlers, `RedirectResponse` assembly, nav-link parameter wiring | `senior-web-engineer` |
| `/api/*` endpoints, fetch calls, Firebase auth flow, cookie usage | `senior-web-engineer` |
| XSS-sensitive HTML assembly (`render.py`, admin JS template literals) | `senior-web-engineer` |
| Backend Python, data model (non-routing) | Inline (main context) |
| Writing, copy, changelog | `writer` |
| Any other code | Inline |

When multiple rules apply, use the most specific matching specialized agent.

## Phase 4 -- Review (after every code change)

Invoke `code-reviewer` after writing or modifying code, before calling `qa-engineer`.

The implementation must be explicitly **approved** by `code-reviewer` before proceeding.

If `code-reviewer` finds issues:

1. Fix the issues in the implementation phase.
2. Invoke `code-reviewer` again.
3. Do not invoke `qa-engineer` until the review passes.

## Phase 5 -- Tests (after reviewer approves)

Invoke `qa-engineer` only after `code-reviewer` has approved.

`qa-engineer` writes or updates relevant tests and runs them.

If tests fail:

1. Return to implementation.
2. Fix the code.
3. Run `code-reviewer` again if the code changed.
4. Re-run `qa-engineer`.

Never treat a failing test as a completed task.

## Phase 6 -- Verify (UI changes)

Use `/verify` to confirm the feature works in the live app.

Required for any UI **golden-path** change.

Do not use `/verify` for purely cosmetic or non-functional UI changes unless needed.

If verification fails, return to implementation and repeat the review/test/verify cycle as appropriate.

## Trivial Changes

For trivial one-liners, such as a typo fix or single-constant change:

- Phase 2 (Design) may be skipped.
- Phase 5 (Tests) may be skipped.
- Phase 4 (Review) still applies to code changes.
