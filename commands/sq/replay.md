Run the following command and display the results:

`sq replay $ARGUMENTS`

Subcommands: `run --phase design|tasks --slice INDEX --config ALIAS [--config ALIAS ...] --reviewer ALIAS --max-revisions N [--yes]` (regenerate a past slice design or task breakdown under each producer config, in a sandbox), `judge --phase design|tasks --slice INDEX --judge ALIAS [--yes]` (compare the first drafts pairwise, in both orders), and `report [--phase design|tasks] [--judge ALIAS] [--json]` (one table per phase, reviewer and judge). `run` and `judge` make real model calls and print their call bound before asking to confirm; pass `--yes` only when the user has already agreed to the cost.
