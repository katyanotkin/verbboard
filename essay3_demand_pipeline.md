# Demand-Driven Language Learning

When a user searches for a verb that doesn't exist, it's logged.

Not as a failed search. As a demand signal: what was searched, in what language, how many times. Repeated searches for the same term add to the count. The queue accumulates evidence of what the database is missing.

Not every signal turns into content. Garbage queries -- random characters, inputs that aren't words -- still get logged. What they don't get is generation: a plausibility check runs before a query ever reaches the model, filtering noise out of the pipeline rather than out of the queue.

---

I used to review every generated verb manually before it went live. English and Spanish don't go through that anymore.

When a search finds no match in those languages, a quick check confirms it looks like a real verb, then generation triggers automatically and goes straight to live. No manual step.

This wasn't a design decision from day one. It's trust I built up with the output over time. English verb forms are regular. The generation quality turned out reliable enough that I stopped reviewing candidates before they went live. Spanish followed.

Russian and Hebrew still go through manual review. Russian aspect pairing requires judgment -- every verb has a perfective and imperfective form, and the pairing isn't mechanical. Hebrew needs binyan and root derivation. Both are worth a pass before content reaches learners.

---

Generated output follows the same structure regardless of path: full conjugation table, example sentences in the target language, morphological annotations (aspect pairs, binyan, root), normalized search index.

For Russian and Hebrew, candidates preview on the live interface before promotion. The admin sees exactly what the learner would see -- board, examples, audio. Corrections happen at the candidate stage.

```
user search → match found → verb board
            → no match in verbs store → demand signal → queue → content generation → preview → publication

Content generation:
EN / ES:  user demand → auto-validation (verb vs. garbage) → auto-generation → live
RU / HE:  user demand → admin review → Claude generation → candidate → preview → promotion → live
```

The content library grows from evidence of actual demand. Users searching for verbs that don't exist aren't hitting a wall. They're defining what gets built next.

That granularity already reaches below the verb level. Each conjugation form has a button that jumps to its matching example, when one is already on the page. No match, and the miss gets logged the same way a missing verb does -- one more signal in the same queue, just scoped to a single form instead of the whole word.

---

There's a second way that kind of gap could get filled: not queued, but generated on the spot. A learner selects a form with no example yet, generation runs right there via Claude or Gemini, and the result is saved so it's never regenerated for the next learner who hits the same form. A natural candidate for a premium feature: instant generation instead of the queue.

---

#LanguageLearning #EdTech #ProductDevelopment #DemandDriven #verbboard
