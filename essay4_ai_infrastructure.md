# AI Is Not the Product, It's the Infrastructure

VerbBoard makes AI calls in four places. Three systems, two cloud providers, one constraint driving each choice.

---

**Cross-language search**

A user studying Russian types "to run" in English. Vertex AI Gemini (`gemini-2.5-flash-lite`) translates the query to a Russian lemma. That lemma goes to Firestore. The user gets a redirect.

This is on the hot path. Flash-lite is fast enough to run inline with the HTTP request. A heavier model adds latency without improving the output for a single-verb translation.

(Gemini occasionally returns "correr." with trailing punctuation. The code tries each token individually rather than cleaning the response.)

**Verb generation**

Generation follows two paths. For English and Spanish, a search miss triggers automatic generation via Gemini (`gemini-2.5-flash`) -- conjugation table, example sentences, morphological annotations -- promoted to the live database without a manual step.

For Russian and Hebrew, generation is admin-triggered and goes to Anthropic Claude (`claude-sonnet-4-6`). Hebrew needs binyan and shoresh derivation. Russian needs correct aspect pairing. Output goes to a candidate for review before promotion.

Hebrew gets 4096 max tokens; every other language 2048.

**Prompt caching**

Every Claude call passes the system prompt with `cache_control: {"type": "ephemeral"}`. Anthropic caches it server-side for 5 minutes. Cache hit: system prompt tokens at ~10% of normal price, latency down roughly 50%.

Prompts are split by language -- each gets the shared intro plus a language-specific section. When translation was added, the first pass combined generation and translation in one prompt. Output quality degraded. Splitting them into separate tasks fixed it. Smaller prompt, higher cache hit probability, better output.

One wrinkle: Haiku requires 2048 tokens minimum to cache. The English prompt is 400-600 tokens, so English calls don't cache. Harmless -- Haiku's speed advantage covers the gap anyway.

**Example translation**

When the learner's interface language differs from the study language, VerbBoard generates inline translations on request. Claude for Hebrew, Gemini for everything else.

Hebrew nikud, script direction, and morphology get better results from Claude. For other languages, Gemini is fast and sufficient.

Translations are stored in Firestore once generated -- not re-fetched on page load.

---

```
Cross-language search:
English query → Gemini translation → Firestore lookup → match found → verb board
                                                       → no match in verbs store → demand signal → queue

Example translation:
page request → language check → Claude or Gemini → Firestore cache → rendered page
```

---

Three AI systems, four call sites, two cloud providers. Each choice made independently, from one concrete constraint.

No AI strategy. Just the right tool at each site.

The calls are not what the product does. They're what makes it feasible at this scale -- one engineer, no linguistics team, demand-driven content expansion across four languages.

---

#AI #AnthropicClaude #Gemini #VertexAI #LLM #EdTech #ProductDevelopment #verbboard
