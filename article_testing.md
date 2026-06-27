# How I Cut Test Count and Improved Confidence

I've been reworking VerbBoard's automated testing strategy.

Before the restructure, VerbBoard had nearly 600 automated tests.

Like many growing products, the suite evolved incrementally. New features brought new tests. Bug fixes brought additional tests. Over time, the number kept growing.

What didn't scale was signal quality.

Some tests protected critical learner workflows. Others validated implementation details rather than behavior. Some failures represented real regressions. Others added maintenance cost without increasing confidence.

## Testing at the right layer

The biggest change was clarifying the responsibility of each testing layer.

- Unit tests verify business logic.
- Integration tests verify application behavior across components, APIs, authentication, and routing.
- Browser tests verify the experience users actually see.

Each layer has a different purpose. Mixing responsibilities creates redundant coverage and unnecessary maintenance cost. Once those boundaries are clear, overlap becomes easier to identify and remove.

## Where Playwright adds value

VerbBoard uses Playwright for end-to-end validation in a real Chromium environment.

The goal is not to re-test application logic, but to verify behavior at the point where the system becomes user-facing.

This matters because some behaviors only exist once code runs in a real browser. These are not implementation details. They are user-facing behavior.

That distinction is important. Browser tests are significantly more expensive than unit or integration tests in terms of runtime, complexity, and maintenance overhead.

For that reason, they are treated as a constrained resource and used only where they materially increase confidence in what a user will actually experience.

In practice, this includes persistence of user preferences across sessions, client-side state transitions driven by JavaScript, and multi-step workflows that span navigation or reloads.

Everything else is validated earlier in the stack.

## Faster feedback loops

Alongside restructuring the suite, I invested in execution speed.

Unit tests now run in parallel across available CPU cores using pytest-xdist. Browser tests run in parallel Playwright workers, with each worker receiving its own browser instance and application environment.

This reduced waiting time without compromising isolation or reliability.

That may sound like an implementation detail, but it directly affects product development.

When feedback arrives faster, regressions surface earlier and iteration cycles tighten. The goal is to release changes quickly without introducing risk.

## What changed

The most obvious outcome was a reduction in test count.

The more important outcomes were improved clarity, faster feedback cycles, and greater confidence in the release process.

Each testing layer now has a clearly defined responsibility. Failures are easier to diagnose, execution times are shorter, and test results provide a more accurate signal of product health.

Deployments are now gated by a smaller but more effective validation process.

## Confidence is the objective

Engineering work often drifts toward metrics that are easy to measure: test counts, coverage percentages, and build statistics.

Those metrics have value, but they are not outcomes.

The outcome is confidence.

Confidence that changes can be shipped safely and quickly. Confidence that critical user workflows remain intact. Confidence that the system behaves predictably as it evolves.

Viewed through that lens, the goal is not to maximize the number of tests. The goal is to maximize confidence relative to maintenance and execution cost.
