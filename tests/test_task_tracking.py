"""Tests for core/task_tracking.py's track().

track() keeps a strong reference to a fire-and-forget asyncio.Task in a
module-level set (core.task_tracking._pending) so it can't be garbage
collected mid-flight, and removes it once the task completes.

Runs the async assertions in a worker-thread event loop (asyncio.run via
ThreadPoolExecutor), matching the pattern in tests/test_audio.py /
tests/test_call_claude.py, since Playwright e2e tests can leave a running
asyncio loop in the main thread.
"""

from __future__ import annotations

import asyncio
import concurrent.futures

import core.task_tracking as task_tracking
from core.task_tracking import track


def _run_async(coro):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def test_track_adds_task_and_removes_it_on_completion() -> None:
    async def _scenario() -> None:
        task = asyncio.create_task(asyncio.sleep(0))
        returned = track(task)

        # track() must return the exact same task object it was given.
        assert returned is task

        assert task in task_tracking._pending

        await task
        # add_done_callback fires via call_soon -- give the loop one tick
        # so the discard callback actually runs before we assert.
        await asyncio.sleep(0)

        assert task not in task_tracking._pending

    _run_async(_scenario())
