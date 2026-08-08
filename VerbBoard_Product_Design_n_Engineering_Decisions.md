# VerbBoard: Product, Design & Engineering Decisions

[VerbBoard](https://verbboard.com) is a language-learning product built around verbs. It currently supports English, Russian, Hebrew, and Spanish.

The product starts with a simple premise: **language is a system of patterns, and verbs are where many of those patterns become visible.** That premise drives the learning experience, the content model, and the way the product grows.

I built VerbBoard end to end, making decisions across product strategy, learning design, content, AI, architecture, and engineering.

This overview documents those decisions and where the product is going next.

## Product & Learning

**[Every Language Runs on Verbs](https://www.linkedin.com/pulse/every-language-runs-verbs-katya-notkin-2qnec)**

The product thesis. Why VerbBoard starts with verbs rather than general vocabulary, and why conjugation tables, examples, and audio are designed to make language patterns visible. The article also explains a deliberate product choice: leaving some work for the learner rather than optimizing everything for convenience.

**[Learning Through Pattern Recognition](https://www.linkedin.com/pulse/learning-through-pattern-recognition-katya-notkin-mwtzf)**

The learning design. Why recognition comes before production, and how conjugation tables, audio, contextual examples, repeated exposure, and guided practice work together to build familiarity with verb forms.

## Product & Content Strategy

**[Demand-Driven Content](https://www.linkedin.com/pulse/demand-driven-content-katya-notkin-gdtic)**

How the content library grows from actual product usage. Missing searches become demand signals; validated signals enter a generation pipeline; different languages follow different levels of automation and human review.

## AI & Product Architecture

**[AI Is Not the Product, It's the Infrastructure](https://www.linkedin.com/pulse/ai-product-its-infrastructure-katya-notkin-quogc)**

How AI is used as infrastructure rather than as the product itself. Different models and providers are used for cross-language search, verb generation, and translation, with choices driven by latency, cost, linguistic complexity, and operational simplicity.

**[VerbBoard Product Architecture](https://www.linkedin.com/pulse/verbboard-product-architecture-katya-notkin-exnze)**

The technical architecture behind the product. FastAPI, server-rendered Jinja2, Firestore, Cloud Run, Cloud Storage, AI services, and a Progressive Web App. The architecture grew from product requirements: make languages easy to add, generate missing content on demand, and keep operational complexity low.

## Engineering Practice

**[How I Cut Test Count and Improved Confidence](https://www.linkedin.com/pulse/how-i-cut-test-count-improved-confidence-katya-notkin-6qaxc)**

A case study in engineering judgment. The automated test suite was reduced by clarifying the responsibilities of unit, integration, and browser tests, while parallel execution improved feedback speed. The objective was not more tests, but greater confidence at lower maintenance cost.

## What's Next

The foundation is now in place. The next phase is expanding the product while keeping its core approach focused.

**Free PWA**

Publish VerbBoard as a free Progressive Web App on Google Play.

**Premium edition — TBD**

I'm evaluating whether a one-time purchase or a subscription makes the most sense, balancing learner experience with the long-term sustainability of the product.

Potential premium capabilities include:

- More supported languages.
- Spaced repetition.
- AI-generated example sentences for verb forms that don't yet have examples.
- A related-words feature to help learners expand vocabulary naturally.

The roadmap will evolve as I learn more from building and from users.

---

Together, these articles and the roadmap describe how VerbBoard was conceived, designed, and built: from the learning model and product strategy through AI integration, architecture, engineering practice, and the next stage of product development.

The common thread is deliberate decision-making: **start with the user problem, make the constraint explicit, choose the simplest approach that works, and build the system around the product rather than the other way around.**
