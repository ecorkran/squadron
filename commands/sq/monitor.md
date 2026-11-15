Monitor a running pipeline until it stops, evaluate its reviews, act on the findings that are both valid and important, then save a session summary.

## Input parsing

`$ARGUMENTS` is an optional run id. Nothing else is accepted.

**Usage:**
```
/sq:monitor [run-id]  — watch a pipeline run, then evaluate and respond to its reviews
```

---

## Step 1: Pick the run

If a run id was given, use it and go to Step 2.

Otherwise run:
```bash
sq runs list --json
```

Keep the entries whose `status` is `running` and whose `working_directory` is the current repository's root (`git rev-parse --show-toplevel`).

- Exactly one: use its `run_id`.
- None: say there is no running run in this repository, show the full listing's run ids with their `status`, and stop.
- More than one: list each with `run_id`, `pipeline`, `params`, and `active_step`, ask which one to monitor, and stop.

Tell the user in one line which run you are monitoring: its run id, pipeline, and `params.slice` when present.

## Step 2: Wait for it

Run:
```bash
sq runs wait <run-id> --json
```

A pipeline step can run for hours. If your shell limits how long a command may run, start this one in the background and wait for it to finish. Do not poll the run, re-run the wait, or read run-state files while it waits.

## Step 3: Act on how it ended

The exit code says how the run ended. The JSON on stdout carries `checkpoint` (paused runs), `failure` (failed runs), and `reviews`.

- **0, completed:** go to Step 4.
- **3, paused:** read `checkpoint`.
  - `resets_at` is set: a usage limit stopped the run. Report the reset time in local time and the resume command (`sq run --resume <run-id>`), then go to Step 6.
  - `kind` is `awaits_human`: the implementing agent stopped on something only the Project Manager can decide. Find each `BLOCKED:` line in the slice's task file (the slice index is in the run's `params`). For each, state the decision needed and your recommendation, then go to Step 6. Do not resume the run.
  - `review_file` is set: a review held the run. Evaluate that review as in Step 4 and respond as in Step 5, then report and ask whether to resume. Do not resume on your own.
- **1, failed:** read `failure`. Get the actual error before saying anything about the cause; never guess one. Report it and go to Step 6.
- **Any other exit code:** report the line `sq runs wait` printed on stderr and stop.

## Step 4: Evaluate the reviews

From `reviews`, take the last round of each step (the entry with the highest `round` for that `step`, or the only entry when `round` is null). Read each review file named in `path` (or every file in `paths` for a multi-part review).

For each finding, decide:
- **Valid:** it is true of the current code or document. Check it against the source; do not take the reviewer's word for it.
- **Important:** a real bug, wrong behavior, lost or corrupted data, a security hole, a broken contract with another component, or something a user will hit.

A finding that is not both valid and important is dropped. Give each dropped finding one line saying why.

## Step 5: Respond to valid and important findings

Read the target first: `cf config get git.integration_branch`, or `main` when it is empty. Never infer it from the current branch.

The review's `template` decides what kind of work the response is:
- **Code reviews:** follow the project's fix rule. Write a test that fails for the reason the finding gives, make the change, and run the project's format, lint, typecheck and touched-area tests. If the run merged its slice branch, commit to the target as `fix: {summary}`. If it did not, commit to the slice branch.
- **Document reviews (design, tasks, architecture, slice plan):** edit the document, then commit to the target as `docs: {summary}`.

If a finding is too large to fix now, or it matches an open issue, file a GitHub issue or comment on the existing one, and say which. Never push.

## Step 6: Save a summary

Run `/sq:summary` (in Codex, `$sq-summary`).

## Step 7: Report

Keep it short:
- How the run ended.
- Each finding acted on, with its commit or issue.
- Each dropped finding, one line each.
- What needs the Project Manager, if anything.
