# VerbBoard Product Architecture

VerbBoard's architecture evolved from a simple requirement:

Make it easy to add a new language, generate missing content on demand, and keep operational complexity low.

That goal drove almost every technical decision.

## Server-Rendered by Design

VerbBoard uses FastAPI with Jinja2 templates and a small amount of vanilla JavaScript.

For VerbBoard a server-rendered architecture offered several advantages:

- Faster iteration with a single codebase
- No client/server API duplication
- Simpler deployment pipeline
- Lower maintenance burden
- Excellent performance for mostly content-oriented pages

Most pages are rendered on the server and delivered as complete HTML. JavaScript is used only where it provides clear value, such as practice sessions, progress tracking, filtering, and PWA features.

The result is an application that behaves like a modern web app while remaining relatively easy to understand and maintain.

## A Single Source of Truth

Verb data, user progress, analytics, and content-generation workflows all live in Firestore.

One architectural principle has been to avoid introducing additional databases unless absolutely necessary.

This keeps data flows straightforward:

- Verbs live in Firestore
- User progress lives in Firestore
- Search demand signals live in Firestore
- Candidate verbs live in Firestore

When a user searches for a verb that does not yet exist, that search becomes a signal. Those signals feed directly into the content-generation pipeline and help determine what should be added next.

The database therefore serves not only as storage but also as a product feedback mechanism.

## Audio Generation as a Cache Problem

VerbBoard generates pronunciation audio on demand.

Instead of pre-generating audio for every possible form across every language, audio is treated as a caching problem:

1. User requests a form.
2. Text-to-speech generates audio if it does not exist.
3. Audio is stored in Google Cloud Storage.
4. Future requests are served directly from storage.

This dramatically reduces upfront generation costs while ensuring that frequently accessed content becomes effectively permanent.

Additionally, there is a CLI script to identify and pre-load missing audio to reduce end-user frustration.

## Stateless Infrastructure

The application runs on Cloud Run.

Each container instance is intentionally stateless:

- No local persistence
- No local caches that must survive restarts
- No session storage on the server

Because state lives in managed services, Cloud Run can scale instances up and down automatically without operational overhead.

This has kept deployment and infrastructure management remarkably simple.

## Authentication Without Building Authentication

User authentication is handled by Firebase Auth.

Rather than implementing account creation, password management, password resets, email verification, and account security internally, VerbBoard delegates those responsibilities to Google's identity platform.

This allows development effort to remain focused on language learning rather than identity management.

## AI as Infrastructure, Not as the Product

AI is integrated throughout VerbBoard, but deliberately in narrow, well-defined roles.

Content generation follows two paths depending on language. For English and Spanish, a missing verb triggers automatic generation via Gemini -- the verb is generated, validated, and promoted to the live database without a manual review step. For Russian and Hebrew, Claude generates a candidate that goes through admin review and preview before promotion. The split reflects the difference in morphological complexity: English and Spanish forms are regular enough to trust automatically; Russian aspect pairing and Hebrew binyan derivation benefit from a human pass.

Beyond generation, Claude and Gemini handle example translation and cross-language search.

The AI models are not the primary product.

They function as infrastructure that helps maintain and expand a structured language-learning system. AI accelerates content creation and discovery, while the application remains centered on curated verb data and learning workflows.

## Progressive Web App (PWA) Instead of Native Apps

Another deliberate choice was to build a Progressive Web App rather than separate iOS and Android applications.

Users can install VerbBoard directly to their home screen and use it much like a native application.

This approach preserves:

- A single codebase
- A single deployment process
- Consistent behavior across platforms
- Faster feature delivery

For a small product team, those advantages outweigh the benefits of maintaining separate native applications.

And for a team of me, myself and I, our team not being an expert in app development, this is the safest choice.

## Architecture in One Sentence

VerbBoard is a server-rendered FastAPI application running on Cloud Run, using Firestore as its single source of truth, Cloud Storage as an audio cache, Firebase for identity, and AI services as supporting infrastructure for content generation and cross-language discovery.

The guiding principle is simple: keep the system understandable, keep operational complexity low, and spend engineering effort on language learning features rather than platform maintenance.
