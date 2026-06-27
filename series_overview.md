# VerbBoard: A Series on Product Decisions

VerbBoard is a language learning tool built around verbs. Four languages: English, Russian, Hebrew, Spanish. One assumption: verbs are where language structure lives, and that is where learning should start.

Building it has involved decisions at every layer -- learning design, content strategy, infrastructure, AI. This series documents four of them.

---

**[Every Language Runs on Verbs](#)**

The product philosophy. Why verbs, not vocabulary. Why some effort is a feature, not a bug.

**[From Exposure to Pattern Recognition](#)**

The learning mechanics. How conjugation tables, audio requirements, and guided sessions are designed to close the gap between recognition and internalization.

**[Demand-Driven Language Learning](#)**

How the content library grows. Unknown searches become signals. Signals become a queue. The queue becomes content -- automatically for some languages, manually for others.

**[AI Is Not the Product, It's the Infrastructure](#)**

Four places in the product make AI calls. Three systems, two cloud providers, each choice driven by one specific constraint.

---

Two additional articles cover the technical foundation:

**[VerbBoard Product Architecture](https://www.linkedin.com/pulse/verbboard-product-architecture-katya-notkin-exnze/)**

FastAPI on Cloud Run, server-rendered with Jinja2 templates and minimal JavaScript. Firestore as the single source of truth for verbs, user progress, and analytics. Audio generated on demand and cached in Cloud Storage. A Progressive Web App -- one codebase, installable on Android, no app store. Why simplicity was an active choice, not a constraint.

**[How I Cut Test Count and Improved Confidence](https://www.linkedin.com/pulse/how-i-cut-test-count-improved-confidence-katya-notkin-6qaxc)**

How the automated testing strategy was restructured: three layers with distinct responsibilities, Playwright reserved for browser-only behavior, parallel execution. Why confidence -- not test count -- is the objective.

---

Each piece stands on its own. Together they describe a product where every layer was a decision.

---

#LanguageLearning #EdTech #ProductDevelopment #AI #verbboard
