# /linkedin — LinkedIn Article Draft

Draft a LinkedIn article in the established VerbBoard voice. Pass a topic, a theme, or paste grep/log output as context. If no args, defaults to recent shipped changes.

## Step 1 — Gather context

If args were passed, use them as the topic. Also run:

```bash
git log --oneline -20
```

If the topic is about a specific feature or code change, read the relevant files to get accurate facts (counts, file names, specific behavior). Do not invent numbers or describe behavior from memory.

If the topic is about testing, also run:

```bash
PYTHONPATH=. pytest --collect-only -q 2>/dev/null | tail -3
```

to get the current test count.

## Step 2 — Identify the angle

Before writing, state in one sentence: what is the non-obvious thing the reader will learn or feel by the end? That is the spine of the article. Everything else is support.

Good angles:
- A counterintuitive decision ("I deleted 200 tests and confidence went up")
- A constraint that forced a better design
- A user behavior that changed how the product was built
- A lesson that only becomes visible in production

Weak angles:
- "Here is a feature I shipped" (pure changelog)
- "Here are N tips about X" (listicle)

## Step 3 — Invoke the writer agent

Hand off to the **writer** agent with:
- The angle (one sentence)
- All facts gathered in Step 1
- Any specific phrasing or examples the user provided

The writer agent handles format, tone, and LinkedIn style rules. Do not apply formatting yourself.

## Step 4 — Output

Present the draft. Note the angle you chose at the top so the user can redirect it if needed. Do not ask placement questions -- if a new section is needed, insert it at the most logical spot and note the choice inline.
