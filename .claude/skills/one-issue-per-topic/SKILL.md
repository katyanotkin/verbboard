---
name: one-issue-per-topic
description: Use whenever creating GitHub issues for leftover or follow-up work. One issue per distinct topic, never a grab-bag; link related issues instead of merging them.
---

# One issue per topic

Owner correction (2026-11-06): issue #95 mixed enclitic-tagging design, Hebrew stored-form data fixes, pending native-speaker answers and unrelated hardening under one title. Different content has different owners, different "done" criteria and different closing moments.

Rules:
- Before `gh issue create`, group the work by topic (decision vs data fix vs waiting-on-human vs code hardening). One issue per group, each with a title that names only its topic.
- A decision ("do we want X?") is its own issue, separate from the implementation it would unlock.
- Work blocked on an outside person (native speakers) is its own issue so it can sit open without hiding actionable work.
- Cross-link with `Related: #n`; never use closing keywords for siblings.
- If the owner asks for "an issue for remaining work", create the set and list the links in one reply.
