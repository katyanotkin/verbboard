"""Retain strong references to fire-and-forget asyncio tasks.

asyncio.create_task() only holds a weak reference to the task it returns --
if nothing else references it, the task can be garbage collected mid-flight
with no warning and no trace in a stack dump. core.analytics.session_tracker
already works around this with its own module-level `_pending` set; this is
the same idiom, shared for new call sites instead of re-duplicated per module.

Note this only fixes the Python-level GC risk. It does not by itself protect
a fire-and-forget task from Cloud Run throttling an instance's CPU toward
zero once the request that spawned it returns -- that half of the fix (an
explicit --no-cpu-throttling/--min-instances deploy flag, or moving the work
to a real queue like Cloud Tasks) is a cost/infra decision, not a code change.
"""

from __future__ import annotations

import asyncio

_pending: set[asyncio.Task] = set()


def track(task: asyncio.Task) -> asyncio.Task:
    """Keep `task` referenced until it completes; returns it unchanged."""
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    return task
