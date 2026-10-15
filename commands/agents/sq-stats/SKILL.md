---
name: sq-stats
description: Reports the tokens, turns, time, and cost that squadron pipeline runs and reviews spent. Use when the user asks what a run or review cost, how many tokens a step used, or wants usage for a slice's reviews.
---

# sq stats

Run `sq stats`, appending whatever the user typed after `$sq-stats` as arguments, and
display the results.

Subcommands: `run <run_id>` (one row per step action, plus totals) and `reviews [--slice INDEX]`
(one row per standalone review artifact). Both take `--json`.
