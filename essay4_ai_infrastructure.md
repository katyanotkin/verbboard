# AI Isn't the Product. It's the Infrastructure.

VerbBoard makes AI calls in four different places.

Three workflows. Two model providers. One principle driving every choice.

**Use the model that best fits the constraint.**

## Cross-Language Search

A learner studying Russian types *"to run"* in English.

Vertex AI Gemini (currently `gemini-2.5-flash-lite`) translates the query into a Russian lemma, which is then used to search Firestore.

This sits directly on the search path, so latency matters more than model sophistication. A lightweight model is fast enough to run inline with the HTTP request without making search feel slow.

One practical detail: Gemini occasionally returns extra punctuation or formatting. Rather than assuming the response is clean, VerbBoard uses a tiered lookup strategy: direct lookup, candidate-word lookup, and finally a fuzzy search over the cached verb index.

## Verb Generation

Generation follows two different workflows.

For English and Spanish, a missing verb triggers automatic generation using Gemini (`gemini-2.5-flash`). Generation quality gradually became reliable enough that I removed the manual review step. After validation, generated verbs go directly into the live database.

For Russian and Hebrew, generation is initiated by an administrator and handled by Anthropic Claude (`claude-sonnet-4-6`).

Those languages still benefit from human review. Russian aspect pairing requires linguistic judgment. Hebrew requires correct *binyan* and *shoresh* derivation. Generated content is reviewed as a candidate before promotion to the live database.

Regardless of language, the generated output follows the same structure: conjugation tables, example sentences, morphological annotations, and normalized search indexes.

## Prompt Caching

One interesting lesson came from adding translations.

My first attempt expanded the generation prompt to include translation.

Output quality became noticeably worse. Increasing the maximum token limit didn't solve the problem.

Separating generation and translation into independent prompts did.

Smaller prompts proved easier for the models to follow, improved output quality, and increased Anthropic prompt-cache efficiency.

Every Claude generation call sends its system prompt using `cache_control: {"type": "ephemeral"}`. Anthropic caches the prompt for five minutes, reducing both latency and token cost on cache hits.

The prompts are also split by language so each cache entry remains small and language-specific. Since Claude is currently used only for Russian and Hebrew generation, prompt caching primarily benefits those workflows.

## Example Translation

When the learner's interface language differs from the study language, VerbBoard can generate inline translations on demand.

Hebrew example translations go through Claude. Example translations for the remaining languages use Gemini.

Hebrew morphology, *nikud*, and right-to-left text consistently produce better results with Claude. For the remaining languages, Gemini provides an excellent balance between quality, speed, and cost.

Translations are generated on demand, stored in Firestore, and reused rather than regenerated on subsequent page loads.

## Putting It Together

**Cross-language search**

`English query → Gemini translation → Firestore lookup → verb board`

`                                                        ↘ no match → demand signal`

**Generation**

**English / Spanish**

`Demand signal → validation → Gemini generation → live`

**Russian / Hebrew**

`Demand signal → Claude generation → candidate → review → live`

**Example translation**

`Page request → language check → AI translation → Firestore cache → rendered page`

## One Strategy, Not One Model

Looking at the architecture, it might seem like there isn't a single AI strategy.

There is.

Every AI call exists because the constraints are different.

Search optimizes for latency.

Generation optimizes for output quality.

Translation balances language quality, speed, and cost.

Prompt caching reduces latency and operating cost.

There is no single "best" language model.

There are only models that best fit a particular problem.

AI isn't the product.

It's the infrastructure that makes a demand-driven language-learning product possible for one engineer, without a linguistics team, across four study languages.

---

#AI #AnthropicClaude #Gemini #VertexAI #LLM #EdTech #ProductDevelopment #verbboard
