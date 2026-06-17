# /changelog — Changelog Entry Draft

Draft a changelog entry for recent shipped work. Pass a version number or tag as an optional arg (e.g. `/changelog v1.4`). Defaults to commits since the last git tag.

## Step 1 — Identify the range

```bash
# Last tag
git describe --tags --abbrev=0 2>/dev/null || echo "no tags"

# Commits since last tag (or last 20 if no tags)
git log $(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline 2>/dev/null || git log --oneline -20
```

If a version arg was passed, use that tag as the lower bound instead.

## Step 2 — Understand what changed

Group commits by category:

- **Features**: new user-facing capability
- **Fixes**: bug fixes, regressions, incorrect behavior
- **Infrastructure**: deploys, CI, GCP config, Cloud Run, secrets
- **Internals**: refactors, test changes, dependency updates with no user impact

For each Feature and Fix commit, read the relevant changed files to understand what actually changed. Do not describe behavior from commit messages alone -- they can be terse or misleading.

```bash
git show --stat <commit-sha>
```

## Step 3 — Invoke the writer agent

Hand off to the **writer** agent with:
- Date range and version (if known)
- Grouped list of changes with accurate descriptions from Step 2
- Any commits to omit (pure infra/internal with no user impact)

Ask the writer agent to produce a changelog entry in this format:

```
## [version or date]

**Features**
- [user-facing description, one line each]

**Fixes**
- [what was broken and what it does now]

**Infrastructure** (optional, only if notable)
- [one-liners]
```

Feature lines: lead with the user benefit, not the technical mechanism.
Fix lines: state what was wrong, then what it does now.

## Step 4 — Output

Present the draft. Flag any commits that were ambiguous and state the assumption made.
