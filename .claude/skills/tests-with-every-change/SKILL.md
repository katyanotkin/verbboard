---
name: tests-with-every-change
description: Use whenever code is added or modified (feature, fix, tool, script, tagger rule, route, JS). Requires automated tests in tests/ in the same change, delegated to qa-engineer after code-reviewer approves, and checked again before commit/push or any QA plan.
---

# Automated tests with every change

Origin: 2026-11-03. `tools/apply_resolved_labels.py`, the Russian tagger rules and several label-ordering
behaviors were pushed with no tests; the owner had to ask for the gaps to be covered. workflow.md
Phase 5 already says to invoke qa-engineer, but I treated tools, data passes and "small" rule tweaks as exempt.

## Steps

1. For every behavior added or changed, name the test that covers it before calling the work done.
   New or changed: function, rule, route, API field, JS module, CLI tool, i18n-driven behavior.
2. Only these are exempt: copy-only edits, pure refactors already covered by tests, docs. One-off data
   passes still need tests for the tool that performs them (use `fake_db`).
3. After `code-reviewer` approves, brief `qa-engineer` with: the changed files, the agreed behavior
   list (see `agreed-design-brief`), and "no production code changes; report bugs". Ask it to
   report which behaviors are covered by which tests.
4. All automated tests live in `tests/` (unit, `tests/e2e` for browser). Never tests in scratch dirs.
5. Run the full suite before commit. A failing test means the task is not done.
6. A manual QA plan marks each item automated / gap / manual; gaps go to qa-engineer, not the owner.
   Live-data checks that cannot run against Firestore in tests stay manual and are labeled so.
7. Final report states the tests added by name. If none were added, say why.
