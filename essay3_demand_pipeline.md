# Demand-Driven Content

One question kept coming up while I was building VerbBoard:

**How should a language-learning product decide what to teach next?**

VerbBoard started with a curated set of high-frequency verbs.

That was only the starting point.

Rather than deciding myself what should be added next, I wanted the product to learn from its users.

When someone searches for a verb that doesn't exist, VerbBoard predictably returns "No results."
It also records a **demand signal**.

The system logs what was searched, in which language, and how often the same search occurs. Repeated searches strengthen the signal. Over time, those searches become evidence of what learners actually need rather than what I assume they need.


`user search → match found → learn page`

`user search → no match → demand signal → generation pipeline → published content`

The content library grows from real usage.

## Not Every Search Becomes Content

Every search is recorded.

Not every search is generated.

People mistype. Paste random characters. Search for things that aren't verbs.

Those searches still have value as usage data, but they shouldn't consume AI resources.

Before generation begins, VerbBoard performs a plausibility check to determine whether the query looks like a real verb. Only then does it enter the generation pipeline.

The queue remains a record of demand.

Generation remains selective.

## Trust Changes the Workflow

One interesting thing happened over time.

I stopped reviewing every generated verb.
As the generation pipeline matured, output quality for English and Spanish became reliable enough that I removed the manual review step.

`user demand → validation → AI generation → live`

Russian and Hebrew are different.

Russian aspect pairs often require linguistic judgment. Hebrew verbs depend on correctly identifying the *binyan* and root. Those languages still benefit from human review before publication.

`user demand → admin review → AI generation → candidate preview → promotion → live`

What started as a safety measure gradually became a measure of confidence in the generation pipeline.

## Extending the Demand Pipeline

Demand signals don't stop at the verb level.

Every conjugated form on a VerbBoard links directly to an example sentence when one already exists.

If a particular form has no matching example yet, that absence becomes another demand signal. The system already knows exactly which conjugated form is missing an example.

Today, the learner simply sees that no example exists for that particular form.

One possible next step is to let learners generate the missing example on demand, together with its translation, and save it so it becomes available to everyone who encounters the same gap.

That would extend the same demand-driven philosophy from missing verbs to individual conjugated forms.

## A Product That Learns

Searches for verbs that don't exist don't disappear.

They become input into the product itself.

Every demand signal helps shape what gets generated, reviewed, and eventually published.

The content library doesn't expand according to a fixed roadmap.

It grows in response to what learners actually look for. Every missing search helps identify what should be added next.

As more people use VerbBoard, they don't just use the product - they help grow it.

---

#ProductDevelopment #LanguageLearning #LearningDesign #EdTech #AI #FeedbackLoop #DemandDriven #verbboard
