---
name: agreed-design-brief
description: Use before delegating to any implementing or reviewing agent, and before building from a design the owner approved. Copies the agreed design into the brief as a checklist, separates "agreed" from "my addition", and stops sibling-feature behavior from leaking in.
---

# Brief from the agreed design

Origin: 2026-11-02. Inline "Fill in the blank" shipped with translation forced open on answering. The
agreed design said translation was independent. I copied the rule from `/practice/fill` into the
agent brief, the reviewer only checked code against my brief, and the owner found it on stage.

## Steps

1. Write two lists before any delegation or coding:
   - AGREED: each decision the owner stated or approved, in their words.
   - MY ADDITIONS: anything I am choosing that they did not state (including behavior borrowed from a
     similar feature).
2. Tell the owner about every item in MY ADDITIONS before building. A QA plan is too late.
3. Paste the AGREED list verbatim into the implementer brief and into the `code-reviewer` brief as a
   checklist the reviewer must tick against the diff, not only against my brief.
4. User-visible copy (banners, help hints, i18n) may describe only AGREED behavior.
5. In the final report, say which items were additions and that the owner approved them.
