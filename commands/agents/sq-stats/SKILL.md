---
name: sq-stats
description: Reports the tokens, turns, time, and cost that squadron pipeline runs and reviews spent, and compares a slice's planned effort with what happened. Use when the user asks what a run or review cost, how many tokens a step used, how a slice's effort compared with its plan, or which producer model works best.
---

# sq stats

Run `sq stats`, appending whatever the user typed after `$sq-stats` as arguments, and
display the results.

Subcommands: `run <run_id>` (one row per step action, plus totals), `reviews [--slice INDEX]` (one row per standalone review artifact), `runs [--slice INDEX] [--pipeline NAME]` (one row per run), `slice <index>` (planned effort against actual for one slice), `slices [--since YYYYMMDD]` (completed slices grouped by planned effort), and `producers [--phase design|tasks]` (observed results per producer model config). All take `--json`.
