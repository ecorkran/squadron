---
name: sq-replay
description: Compares producer model configs on a past slice by regenerating its design or task breakdown in a sandbox under each config, judging the first drafts pairwise, and reporting quality, cost, time and failure rate. Use when the user asks which model or effort writes the best slice designs or task breakdowns, wants to replay a slice under different models, or wants the replay report.
---

# sq replay

Run `sq replay`, appending whatever the user typed after `$sq-replay` as arguments, and
display the results.

Subcommands: `run --phase design|tasks --slice INDEX --config ALIAS [--config ALIAS ...] --reviewer ALIAS --max-revisions N [--yes]` (regenerate a past slice design or task breakdown under each producer config, in a sandbox), `judge --phase design|tasks --slice INDEX --judge ALIAS [--yes]` (compare the first drafts pairwise, in both orders), and `report [--phase design|tasks] [--judge ALIAS] [--json]` (one table per phase, reviewer and judge). `run` and `judge` make real model calls and print their call bound before asking to confirm; pass `--yes` only when the user has already agreed to the cost.
