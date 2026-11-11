---
name: sq-benchmark
description: Builds and inspects the model benchmark's fix cases and reports how many a project yields. Qualifies a repository's closing commits as fix cases in sandboxes, shows why a commit qualified or was rejected, and says whether the qualified cases can separate two model configs. Use when the user asks how many fix cases a project gives, why a fix commit was rejected, or wants the benchmark yield report.
---

# sq benchmark

Run `sq benchmark`, appending whatever the user typed after `$sq-benchmark` as arguments, and
display the results.

Subcommands for fix cases: `fix-cases build --set NAME [--repo PATH] [--commit SHA ...] [--keep]` (discover the repository's closing commits, qualify each as a fix case in a sandbox, write the case set, and print the yield report), `fix-cases show COMMIT|CASE_ID [--repo PATH]` (the latest qualification record: environment digest, each hidden test with its verdict and detail, superseded and excluded tests, and the frozen task text), and `yield [--repo PATH ...] [--json]` (qualified and rejected counts per project and pooled, with whether the qualified cases can separate two configs). `fix-cases build` runs installs and test suites and reads issues through `gh`; run it only when the user has asked for it.

Other subcommands: `sandbox REV [--suite] [--node ID ...] [--keep]` and `auth-check --model ALIAS [--model ALIAS ...]`.
