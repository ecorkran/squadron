Run the following command and display the results:

`sq benchmark $ARGUMENTS`

Subcommands for fix cases: `fix-cases build --set NAME [--repo PATH] [--commit SHA ...] [--keep]` (discover the repository's closing commits, qualify each as a fix case in a sandbox, write the case set, and print the yield report), `fix-cases show COMMIT|CASE_ID [--repo PATH]` (the latest qualification record: environment digest, each hidden test with its verdict and detail, superseded and excluded tests, and the frozen task text), and `yield [--repo PATH ...] [--json]` (qualified and rejected counts per project and pooled, with whether the qualified cases can separate two configs). `fix-cases build` runs installs and test suites and reads issues through `gh`; run it only when the user has asked for it.

Replay subcommands: `run --set NAME --model ALIAS [--model ALIAS ...] --max-cost USD [--set-version N] [--samples K] [--max-cost-per-replay USD] [--case CASE_ID ...] [--retry-harness] [--keep] [--repo PATH]` (run the producer on each case of a set under each model, print the stated cost bound first, then one line per replay and a summary; exit 0 complete, 2 partial at the run cap, 1 refused or stopped) and `replay-show RECORD_ID [--diff] [--repo PATH]` (a stored replay record, or with `--diff` its stored diff exactly).

Other subcommands: `sandbox REV [--suite] [--node ID ...] [--keep]` and `auth-check --model ALIAS [--model ALIAS ...]`.
