---
name: design-alternatives-check
description: Use when planning any new storage, endpoint, collection or flow, and whenever the owner suggests an alternative design (e.g. "shouldn't we just extend the users table?"). Forces a check of existing structures and their lifecycle (deletion, export, admin, privacy) before proposing something new.
---

# Design alternatives check

Origin: Plus access requests. I first proposed a new collection; the owner pointed out extending
`users/{uid}` was simpler and made account deletion work for free. The owner was right and had to ask.

## Before proposing new storage or a new surface

1. List existing structures that already hold the same entity (user doc, `user_practice`, session
   docs, feedback). Prefer extending one. A new collection needs a stated reason.
2. Walk the lifecycle for each option: account deletion (`core/account_deletion.py`), privacy page
   text, admin visibility, rate limits, idempotency, security rules, backfill/migration.
3. Prefer the option that needs the fewest new moving parts. Give one recommendation plus the
   runner-up and why it lost, in a few lines.
4. If no email or notification service exists, do not write copy that promises one; check what the
   system can actually do.

## When the owner proposes an alternative

Assess it on the same checklist and answer on merit. Do not remove or revert anything just because
they asked a question. If their option wins, say so plainly and switch; then follow the
`correction-to-skill` skill so the lesson is kept.
