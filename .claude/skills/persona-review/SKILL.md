---
name: persona-review
description: Use at the 3-weekly marketing persona review, whenever a persona experiment issue (#135-#139 or later) is closed, and when data or feedback contradicts a persona claim. Keeps docs/marketing/personas.md the single source of truth and writes experiment results back into it.
---

# Persona review

Owner decision (2026-11-24): personas must persist in the repo, never only in a claude.ai artifact, and are reviewed every 3 weeks. Source: `docs/marketing/personas.md`. `docs/marketing/verbboard-personas.html` is a readable copy rebuilt from it (by `writer`), footer "generated from personas.md @ <sha>"; never edited by hand.

## Every 3 weeks (20 minutes)

Google Cloud starts it (issue #142): Cloud Scheduler records a review as due every 3 weeks, you get an email from a Cloud Monitoring alert, and `/admin` and `/admin/reports` show an amber banner. The banner links to `/admin/personas` (issue #143), which shows the stored figures, the personas as last published, how their claims changed between reviews, and the review history. Get the figures from there or with `make persona-review-dry-run`. When the review is finished, press **Mark done** on that page (or run `python -m tools.persona_review_done <date>`) to clear the banner. No email or banner after 3 weeks means the trigger is broken: check `gcloud scheduler jobs describe verbboard-persona-review --location us-east1` and the Cloud Run log for `PERSONA_REVIEW_FAILED`.

1. Open `/admin/reports` for the last 21 days (and compare). Read each persona's signal and the Sign-in attempts card. Note n beside every number.
2. For each claim in `personas.md`: change status only with evidence. `observed` needs a named number with date range and n (about 30 sessions or more), an issue, or a feedback item that has an issue. Otherwise it stays `assumed`.
3. Flag any claim whose "Last checked" is over 60 days old. Refuted claims move to "Retired claims" with one line on what we learned.
4. Update "Last review" and "Next review" (+21 days) at the top of the file, set each persona's "Next test" to its open issue.
5. Rebuild the HTML from the markdown (writer), update the footer sha, commit and push with the issue numbers. Then run `make persona-publish` (it refuses unreadable table rows, so fix a misspelled status first): this stores the snapshot that `/admin/personas` uses to show what changed since the last review. Reword a claim only when it really changed meaning: the page tracks a claim by its text, so a reworded claim shows as removed plus added and loses its history.
6. If a persona never shows in the numbers, propose merging or dropping it to the owner.

Fixed dates outside the cycle: ~2026-12-19 share check (#137), ~2026-12-25 Hebrew UI check (#60 decision).

## When an experiment issue closes

The closing comment uses this form, and the same commit updates the persona claim and cites the issue:

- Hypothesis:
- Number moved (before, after):
- Date range and n:
- Verdict (supported / refuted / inconclusive):
- Persona claim changed (persona, new status):

Metric snapshots live in that comment (paste `build_report()` figures or `make retention` / `tools/retention_cohort.py --json` output), not in Firestore.

## Do not

- Invent numbers or cite a source not in the repo or a console; mark `UNVERIFIED`.
- Regenerate personas with an LLM, build a persona database or dashboard, or add analytics only for personas (add a flag only when an experiment needs it).
- Link issues to a claude.ai artifact. Link `docs/marketing/personas.md`.
