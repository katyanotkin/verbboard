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

## Phase 7 -- Docs (before considering the task done)

Trigger: the change adds/removes a user-facing feature, a new endpoint or data model, a new test file or test layer, a new language/edition, or otherwise makes something already described in `README.md`, `ARCHITECTURE.md`, `TESTING.md`, or `CLAUDE.md` factually wrong or incomplete.

**A new user-facing feature always means both `CLAUDE.md` (architecture-pattern entry, dense technical bullet) AND `README.md` (the relevant `### <Page> page` feature bullet under "Current behavior") -- check README's feature list for completeness even when nothing in it is factually wrong.** Missing a feature from README's list is exactly the "incomplete" half of this phase's trigger, not a lesser case than a wrong claim. (Learned the hard way 2026-09-05: shipped Verb of the Day + Anki export, updated CLAUDE.md, initially skipped README's Home page / Verbs page bullets entirely -- caught only because the user asked.)

Action:
- Small, isolated staleness (a line, a version number, a moved file path): fix it directly, no agent needed.
- Feature-sized doc updates (new section, multi-file rewrite): dispatch `writer` with the specific facts already verified against the code, same as Phase 3's routing for writing/copy. `writer` has no Write/Edit tools -- it returns full replacement text for you to apply, explicitly instructed not to summarize or truncate. For a new feature, this includes drafting both the CLAUDE.md entry and the README bullet in the same pass -- don't split them across separate asks.

Skip when: the change is a pure internal refactor, test-only, or copy-only edit that makes no doc claim stale.

This phase exists so doc staleness doesn't require the user to notice and ask -- treat it as a standing part of shipping a feature, not an optional cleanup pass.

## Phase 8 -- Close the issue (after stage verification)

Trigger: the change closes or is described as a fix/follow-up for a tracked GitHub issue, has been pushed to `main`, and stage has redeployed (`git push` to `main` auto-deploys stage -- no manual command needed; confirm via `gcloud builds list --project knotmem26 --region us-east1 --limit=1` if timing is unclear).

Action:
- Once the build succeeds and the change is confirmed working on stage (or, for a backend-only change with no live-behavior surface to click through, once the full test suite is green post-push), close the issue with `gh issue close <n>`, referencing the commit SHA.
- If stage verification finds a problem, do not close the issue -- return to implementation and repeat the review/test/verify cycle.
- For a multi-issue push (several commits in one push), verify and close each issue independently -- one commit's stage behavior confirms only that commit's issue, not siblings in the same push.

Skip when: no GitHub issue is associated with the change (e.g. a purely exploratory or user-directed one-off edit with nothing tracked).

This phase exists so a shipped, verified fix doesn't sit open in the tracker waiting for the user to notice and close it themselves.

## Trivial Changes

For trivial one-liners, such as a typo fix or single-constant change:

- Phase 2 (Design) may be skipped.
- Phase 5 (Tests) may be skipped.
- Phase 7 (Docs) may be skipped, unless the one-liner itself makes a doc claim wrong (e.g. renaming something a doc references by name).
- Phase 4 (Review) still applies to code changes.
- Phase 8 (Close the issue) still applies once pushed and stage-verified.
