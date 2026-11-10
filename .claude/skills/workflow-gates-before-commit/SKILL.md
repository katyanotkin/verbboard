---
name: workflow-gates-before-commit
description: Use whenever the owner says "commit", "push" or "commit & push" (or a goal implies shipping). workflow.md gates (code-reviewer, qa-engineer, docs/writer, /verify for UI) must be done first; a direct commit instruction does not waive them.
---

Origin (2026-11-09): owner said "commit & push" after the pt-BR work; I committed and pushed
without code-reviewer, qa-engineer or writer having run. Owner: the workflow is a must.

1. Before `git commit`, check which workflow.md phases have run for this change: code-reviewer
   APPROVED, qa-engineer (tests written and green), docs via writer (CLAUDE.md and README), and
   /verify for UI golden-path changes.
2. If any gate is pending, run it first. Do not commit "to save time" and review afterwards.
3. If the owner insists on skipping a gate, they must say so explicitly; otherwise a plain
   "commit & push" means "ship once the gates pass".
4. A push to main auto-deploys stage, so treat push as the final step after the gates.
