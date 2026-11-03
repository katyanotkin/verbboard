---
name: correction-to-skill
description: Use whenever the owner points out a missed request, a misunderstanding, behavior they did not agree to, or suggests a better design than mine. Records the lesson as a project skill (checked into git), not as a memory file, so it persists and improves future work.
---

# Turn corrections into skills

Owner instruction (2026-11-03): corrections, misunderstandings and alternative designs become skills,
not Claude memory. Goal: persistent use and self-improvement.

## Steps

1. Fix the problem first and confirm it.
2. Name the root cause in one line: what I assumed, skipped or copied.
3. Look in `.claude/skills/` for the skill that should have prevented it
   (`request-ledger`, `agreed-design-brief`, `design-alternatives-check`, others).
   - Exists: add the missing step or example to that skill (small edit, keep it short).
   - None fits: create `.claude/skills/<kebab-name>/SKILL.md` with frontmatter `name` and a
     `description` that says when to trigger. Body: origin in one line, then numbered steps.
4. Do not write a feedback/project memory for this. Memory stays for user facts and project
   state that are not process rules.
5. Tell the owner in one line which skill changed. Commit the skill with the fix when the owner
   asks for commits.
