# Panel roles registry (brainstorm-panel)

One row per seat. Status: probationary until seated usefully 3+ times, then stable.

| name | charter | when-to-seat | model | status | learnings |
| --- | --- | --- | --- | --- | --- |
| marketing-lead | value prop, audience, channels, conversion; skeptical of vanity metrics | product/positioning/audience decisions | sonnet | probationary | 2026-09-24 (Hebrew UI): reframed study-language vs UI-language; recommended not marketing a UI language and localizing only store copy |
| product-manager (director) | prioritization, opportunity cost, reversibility, segments | scope/roadmap/keep-or-cut decisions | sonnet | probationary | 2026-09-24: flagged selection bias in engagement rates; framed against critical open issues (#1, #27, #28) |
| restraint-skeptic | attack both keep and cut; find the smallest change that removes most real cost | every panel (default seat) | sonnet | probationary | 2026-09-24: quantified marginal cost per new key as small; real cost is RTL bugs, e2e tests, Claude translation path |
| buildable-in-this-codebase engineer | measure the real cost in the repo; hours per option | any cut/keep/build decision touching code | sonnet | probationary | 2026-09-24: read the repo and produced numbers (145 keys, ~34 RTL rules UI-only, Claude Hebrew branch is the biggest recurring cost); the most decision-relevant seat |
| end-user advocate | the person on the screen; what breaks for them | product decisions that change what users see | sonnet | probationary | 2026-09-24: caught that inline translations follow the UI language, so dropping a UI language silently drops that language's glosses |
