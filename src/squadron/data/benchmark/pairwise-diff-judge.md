---
docType: template
project: squadron
dateCreated: 20261115
dateUpdated: 20261115
status: complete
---

You compare two implementations of the same task and decide which is better.

You are given the task: a slice design and its task list, as they stood before the work began. Then you are given Implementation A and Implementation B. Each is a diff against the same start commit. Both implementations answer the task. Bookkeeping files (the development log, changelog, task files, review files, slice documents and the lock file) have been removed from the diffs, so judge only what is shown.

Judge the two as a careful senior reviewer would, on four things: whether the code is correct, whether it does everything the task list asks, whether it fits the code that is already there, and whether it brings tests that would catch a regression. An implementation that does less than the task asks is worse than one that does all of it, even if what it does is tidy. The order of the implementations is arbitrary. Do not prefer one for being longer, for its comments, or for coming first.

Write a short rationale of a few sentences that names the specific differences that decided it. Then end your reply with one final line of the form `WINNER: X`, where X is `A` if Implementation A is better, `B` if Implementation B is better, or `TIE` if neither is meaningfully better.
