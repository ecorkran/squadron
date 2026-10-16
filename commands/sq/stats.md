Run the following command and display the results:

`sq stats $ARGUMENTS`

Subcommands: `run <run_id>` (one row per step action, plus totals), `reviews [--slice INDEX]` (one row per standalone review artifact), `runs [--slice INDEX] [--pipeline NAME]` (one row per run), `slice <index>` (planned effort against actual for one slice), `slices [--since YYYYMMDD]` (completed slices grouped by planned effort), and `producers [--phase design|tasks]` (observed results per producer model config). All take `--json`.
