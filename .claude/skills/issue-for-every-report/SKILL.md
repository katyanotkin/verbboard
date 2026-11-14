---
name: issue-for-every-report
description: Use whenever the owner reports a bug, a wrong text, or an idea (pasted feedback, "this is not accurate", "suppose we need X", "plz fix Y"), whenever I notice a defect myself, and before every git commit. Open a GitHub issue first, even if the fix is tiny and shipped in the same turn; link every commit to its issue with #n; close the issue with the commit SHA.
---

# An issue for every report

Owner correction (2026-11-14): the Russian/Spanish/Hebrew About "Install" text was reported as inaccurate and fixed in one commit with no issue, so there was nothing to close or to find later. Same gap as the French subjonctif fix (2026-10-02).

Rules:
- Any reported bug, inaccurate text, missing feature or idea gets a `gh issue create` before or as soon as the cause is known. Pasted feedback, one-line chat reports and defects I find myself all count. Check `gh issue list --search "<keywords>"` first and reuse an open issue instead of duplicating.
- A small fix that ships in the same turn still gets an issue: create it, fix it, put the issue number in the commit message (`#n`), and close it with `gh issue close <n> -c "Shipped in <sha>, verified on stage/prod."` after the stage check (workflow.md Phase 8). Do not use closing keywords for siblings.
- **Every commit is linked to an issue.** Put `#n` in the commit subject or body (e.g. `... (#118)`), one commit per topic where practical; a commit that serves several issues lists each as `#n`. Use a closing keyword (`Fixes #n`) only for the single issue the commit fully resolves, never for siblings or partial work; otherwise close it by hand after stage verification. If a commit has no issue (pure refactor, docs, tooling), say so in the body ("no issue") rather than leaving it ambiguous. Before `git commit`, check the message names the issue; an already-pushed commit cannot be amended, so add a `gh issue comment` with its SHA instead (GitHub auto-links it).
- Ideas and questions the owner raises that are not being built now ("later if...", "something to do later") get an issue labelled as an idea/parked, not only a memory note.
- Follow [[one-issue-per-topic]]: one issue per distinct topic, with the reported wording quoted in the body and the repro (page, language, UI language) when there is one.
- Not issues: pure questions answered in chat, requests for a status or an explanation, and edits to my own in-progress work.
- Say the issue link in the reply, in one line.
