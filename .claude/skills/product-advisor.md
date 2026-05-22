# /product-advisor — VerbBoard Product Advisor

Pull live usage data from Firestore, analyze it, and produce a structured product advisory: conclusions from current data, gaps in what is being tracked, and prioritized product suggestions.

## Step 1 — Pull analytics data

Run this Python script and capture the output:

```bash
PYTHONPATH=. python - <<'EOF'
import json
from datetime import UTC, datetime, timedelta
from collections import Counter
from core.storage.firestore_db import get_db

db = get_db()
cutoff = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%d")

# --- analytics_daily ---
by_page, by_device, by_language, by_ui_lang = Counter(), Counter(), Counter(), Counter()
for doc in db.collection("analytics_daily").where("date", ">=", cutoff).stream():
    d = doc.to_dict() or {}
    n = int(d.get("count") or 0)
    by_page[d.get("page") or "unknown"] += n
    by_device[d.get("device_type") or "unknown"] += n
    by_language[d.get("language") or "none"] += n
    by_ui_lang[d.get("ui_lang") or "none"] += n

# --- demand signals (unprocessed clusters) ---
from core.settings import load_settings
s = load_settings()
labels = []
for doc in db.collection(s.verb_signal_labels_collection).stream():
    d = doc.to_dict() or {}
    if not d.get("hidden"):
        labels.append({
            "label": d.get("label") or d.get("query") or "?",
            "language": d.get("language", ""),
            "count": d.get("count", 1),
            "status": d.get("status", ""),
        })
labels.sort(key=lambda x: -x["count"])

# --- recent feedback (last 60 days) ---
from datetime import UTC, datetime, timedelta
cutoff_dt = datetime.now(UTC) - timedelta(days=60)
feedback = []
for doc in (db.collection("feedback")
            .where("created_at", ">=", cutoff_dt)
            .order_by("created_at", direction="DESCENDING")
            .limit(40)
            .stream()):
    d = doc.to_dict() or {}
    if not d.get("hidden"):
        feedback.append({
            "text": (d.get("text") or "")[:120],
            "device": d.get("device_type", ""),
            "created_at": str(d.get("created_at", ""))[:10],
        })

print(json.dumps({
    "by_page": dict(by_page.most_common()),
    "by_device": dict(by_device.most_common()),
    "by_language": dict(by_language.most_common()),
    "by_ui_lang": dict(by_ui_lang.most_common()),
    "demand_labels": labels[:30],
    "feedback": feedback,
}, indent=2))
EOF
```

## Step 2 — Analyze

Using the JSON output, reason through each section. Think about:

**Funnel**
- Compute home -> verbs -> learn conversion rates (views at each step / home views).
- If learn/home < 30%, that is a significant drop-off worth investigating.
- Does feedback page volume suggest users hit problems?

**Audience**
- Device mix: is mobile share high enough to warrant mobile-specific UX investment?
- Language studied: which languages dominate? Are any languages with demand signals not yet covered?
- UI language: does the UI language distribution match the studied language distribution? Mismatches suggest international users studying a non-native language.

**Demand signals**
- Which verb clusters have the highest count and are still unprocessed?
- Which languages show the most unmet demand?
- Cross-reference with `by_language` to see if high-demand signal languages are also high-traffic -- strong signal to prioritize.

**Feedback themes**
- Group feedback by topic (UX friction, missing content, bugs, praise).
- Note any device-specific complaints.

## Step 3 — Identify tracking gaps

Evaluate what is NOT currently tracked and suggest what to add next. Consider:

- **Session depth**: how many pages does a user visit per session? Currently unknown -- would need a session ID cookie and session document in Firestore.
- **Return visits**: are users coming back? No user identity on anonymous visits -- could use a stable anonymous ID cookie.
- **Practice loop completion rate**: do users who start practice finish it? `user_practice` has badges but no abandonment signal.
- **Audio play rate on learn page**: how many users actually play audio vs just browse? Currently no event for this.
- **Search-to-result rate**: what fraction of searches find a verb? Already logged as demand signals but not cross-referenced with successful searches.
- **Time on learn page**: proxy for engagement -- not currently tracked.

For each gap: note what it would reveal and how hard it would be to instrument (cookie = easy, server event = medium, client beacon = medium).

## Step 4 — Produce the report

Output a structured report with these sections:

### Usage snapshot (last 60 days)
Table of all four dimensions with counts and percentages.

### Funnel analysis
Conversion rates home -> verbs -> learn -> feedback. Flag drop-offs.

### Audience profile
Who is using VerbBoard: dominant device, dominant language pair (studied + UI).

### Demand gaps
Top unmet demand signals by language. Flag any that are high-count AND high-traffic language.

### Tracking gaps (prioritized)
Ranked list of what to instrument next, with effort estimate (low/medium/high) and what decision it would unlock.

### Product priorities
3-5 concrete suggestions ranked by expected impact, grounded in the data. Be specific: "add X because Y% of users are on mobile and Z friction point appears in feedback" rather than vague recommendations.
