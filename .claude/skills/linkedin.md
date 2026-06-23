# /linkedin — LinkedIn Post or Article Draft

Draft LinkedIn content in the established VerbBoard voice. Pass a topic, theme, or context as args. If no args, defaults to recent shipped changes.

## Step 0 — Determine the format

Ask (or infer from the args) which format is needed:

**Post** (short-form, feed): line breaks do the work, minimal formatting, punchy sentences. Bullets only for short concrete lists. No bold mid-paragraph.

**Article** (long-form, Pulse): bullets and bold are desired and expected. Paragraphs can develop a point over 2-4 sentences.

If unclear, ask before proceeding.

## Step 1 — Gather context

Use the args as the topic. Also run:

```bash
git log --oneline -20
```

If the topic is about a specific feature or code change, read the relevant files to get accurate facts (counts, file names, specific behavior). Do not invent numbers or describe behavior from memory.

If the topic is about testing, also run:

```bash
PYTHONPATH=. pytest --collect-only -q 2>/dev/null | tail -3
```

to get the current test count.

## Step 2 — Identify the angle and post type

Before writing, decide two things:

**Post type (for posts only):**
- Format A (product update): use `***Feature Name***` headers, close with `--` current questions
- Format B (decision/reasoning): use numbered list, close with "Curious how others think about decisions like these."

**Angle:** one sentence -- what is the non-obvious thing the reader will learn or feel by the end? That is the spine. Everything else is support.

Good angles:
- A counterintuitive decision ("I deleted 200 tests and confidence went up")
- A constraint that forced a better design
- A product philosophy revealed by a real tradeoff
- A lesson that only becomes visible in production

Weak angles:
- "Here is a feature I shipped" (pure changelog)
- "Here are N tips about X" (listicle)

## Step 3 — Invoke the writer agent

Hand off to the **writer** agent with:
- Format (post or article) and post type (A or B) if a post
- The angle (one sentence)
- All facts gathered in Step 1
- Any specific phrasing or examples the user provided

The writer agent handles tone, style rules, and formatting. Do not apply formatting yourself before handing off.

## Step 4 — Output

Present the draft. State the format and angle chosen at the top so the user can redirect if needed. Do not ask placement questions -- if a new section is needed, insert it at the most logical spot and note the choice inline.
