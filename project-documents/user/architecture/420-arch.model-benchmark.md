---
docType: architecture
archIndex: 420
component: model-benchmark
initiative: model-benchmark
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [140, 300, 320, 400]
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
---

# Architecture: Model Benchmark

## Overview

Squadron can say which producer config writes better slice designs and task breakdowns (slice 177: `sq replay`). It cannot say which config writes better code, which reviewer config catches more defects, or what effort level buys. Implementation was left out of replay because it needs the code built and tested in the sandbox, so `sq stats producers` has no implementation rows. Model choice for P6 and for code review is set by habit.

This component answers "does model X at effort Y do this job as well as model Z, and at what cost?" for implementation and review, using the project's own history as the benchmark. It has five capabilities:

- **Effort as a measured variable.** Every dispatch path sends effort when the alias carries it, and every run records the effort actually sent, or records that none was sent.
- **A fixed, versioned case set.** Cases drawn from completed work: fix commits first (the parent commit plus the issue text), completed slices second (the fork commit plus the slice design and task file).
- **Implementation replay.** A case is run per config in a history-free sandbox, and the result is graded by running the tests and checks there.
- **Scoring with repeated samples.** Objective signals first (hidden test, regressions, lint, type checks, 400 snapshot deltas), then normalized code-review findings, then the existing pairwise judge over slice-case diffs. Cost, turns and wall time sit beside them. Each config runs several times per case, and configs are compared on paired per-case differences.
- **Reviewer recall.** Known defects are planted in real diffs, and each reviewer config is scored on how many it finds.

**Scope.** The case record and case qualification, the implementation replay runner, the grader, the reviewer-recall harness, the new metrology record types, and the reports. Replay's start-point and sandbox machinery (177), the metrology store (320), snapshots and normalized review findings (400), and the pairwise judge with Bradley-Terry aggregation (177) are reused, not rebuilt.

**Motivation.** Implementation and code review are where most of the money goes. Choosing their models by impression costs real money in one direction and quality in the other, and the data to decide properly is already in git.

## Design Goals

- **Compare configs on identical work.** Every config sees the same start commit, the same task text and the same environment. The case, not the config, is the unit of difficulty.

- **Objective before opinion.** A case's pass or fail comes from tests and tools that give the same answer every time. LLM signals (review findings, pairwise preference) are reported beside them with their own noise floors, never folded into them.

- **Cases come from real history.** Any cf project with fix commits or merged slices can be benchmarked on itself, with no curated dataset.

- **Results stay comparable over time.** A result names the case set version, the config (model, profile, effort sent, and the alias's `tool_use` and `max_output_tokens`; the alias name is for display only), the grader identity and the prompt identity, so a report compares only results that match, and flags the rest.

- **Spend is visible before it happens.** A benchmark run states its upper bound in dollars before any dispatch and stops at its own cap. Grading and judging run as separate commands with their own caps, so a benchmark's total is bounded by the sum of those caps.

## Architectural Principles

- **The answer stays out of reach, and a run that reaches for it is not graded.** A replay runs in 177's history-free sandbox: one commit, no refs to later history. The hidden test, the original fix and the original diff stay outside the sandbox until grading. Issue text is frozen into the case when it is created, so a later comment that describes the fix cannot leak in. The sandbox is a directory, not a jail, so leakage is this component's problem, not only #213's: the producer runs without GitHub credentials and with squadron's and the agent's config directories pointed away from the user's (no store, no memory). Its `PATH` puts the sandbox's own environment first and leaves out the user's tool installs, so a squadron case cannot run the installed, later `sq`. The producer transcript is scanned for reads of known leak paths (the user's checkout, installed site-packages, the package manager's cache, the store) and for `git` or `gh` calls against other repos. A run that trips the scan is recorded as leaked and not graded. Scanning cannot see file access inside scripts the model writes, so a clean run is recorded as "no leak detected", never as "not leaked".

- **The grader is not the producer, and the producer cannot change the grade.** The producer may run tests while it works. The grade comes from a separate step that runs after the producer finishes, in a fresh sandbox rebuilt from the start commit plus the producer's diff, with its own commands. It takes the producer's source, but the regression suite and the tool config come from the start commit, not the producer's tree. Tool config is restored by section, not by file, because one file often holds both: in `pyproject.toml` the `[tool.*]` tables (and any standalone `ruff.toml` or `pyrightconfig.json`) come from the start commit, while dependency and entry-point tables come from the producer. If the producer changed dependencies or the lockfile, the grader reinstalls and the run records that it did; the grader identity still names the start environment. The producer's own new tests run as a separate, reported signal. Edits the producer makes to existing tests or tool config, and inline suppressions it adds (`# noqa`, `# type: ignore`), are counted and reported, never silently honored. A producer's claim that tests pass is never evidence.

- **A case is qualified mechanically before it counts.** No case needs a person to look at it. A case enters the set only if the original work passes its own grade in the sandbox environment, and, for a fix case, its hidden test passes the fairness rule below. A case that fails qualification is recorded with the reason and excluded, never quietly kept. A qualification record names the environment identity it ran under; a benchmark run re-qualifies a case whose environment identity differs, and drops it with that reason if it no longer qualifies. The rules are written once per language adapter; nothing is maintained per project.

- **A hidden test must be fair to a different correct fix.** A fix test qualifies only if all three hold:
  1. **Test-first.** At the parent it fails, and the failure does not come from a missing or renamed project symbol: no collection error, no `ImportError`, no `AttributeError` on a project module, no patch target that is not found. Those mean it uses names the fix added. A failed assertion, or an exception raised by project code (the crash the fix cures), qualifies.
  2. **Packaging boundary only.** It reaches project code only through what the project's packaging metadata already declares, as it stood at the parent: entry points and public exports (`[project.scripts]` and `__all__` in Python; `bin`, `exports` and `main` in `package.json`). For a CLI tool that means driving the CLI.
  3. **No patching project code.** Patching what lies outside the project (network, subprocess, model SDK, clock) is allowed. Patching the project's own code ties the test to where the original fix put its logic.

  A project whose packaging declares nothing usable yields no fix cases and still yields slice cases.

- **A case names its test sets explicitly, test by test.** The reference's diff against the start sorts every test it touched into two lists of individual tests (pytest node ids in Python), not files, because a fix usually adds one test function to an existing file. The **hidden set** is the tests a fix added or changed, plus fixtures it added to a `conftest.py`; a slice case has none. The **superseded set** is the existing tests the reference changed or deleted, because the old expectation was the bug or the old behavior went away. Superseded tests are left out of the regression count, so a correct replay is not charged for failing an assertion the reference also dropped. The language adapter injects the hidden tests and fixtures into the producer's tree without removing anything the producer wrote; a name clash with a producer test is recorded and the hidden test is renamed, not overwritten.

- **Replays run the production pipelines.** What is benchmarked is the prompt and step a real run uses, not a prompt that exists only for the benchmark. A replay runs a production pipeline's producer step and stops at the committed tree.

- **Cases are immutable and versioned.** A case is identified by its content (start commit, task text, hidden and superseded test sets, grader commands). Changing any of those makes a new case. A case set is a named, versioned list of case ids, and every result references the case and the set version it was run under.

- **Extend 320's store, don't fork it.** Cases, implementation replays, grades and reviewer-recall results are new record types in the metrology store, added the way 177 and 400 added theirs: optional sibling payloads, no migration, keyed on `ProjectId`. Records stay coarse, one per case run, because the store reads every file on every query. Diffs are stored as content-addressed sidecar files from the first replay record onward and referenced by hash, so the record format never has to move them later.

- **Absent is not zero.** A run with no grade records why, and the reason decides how it counts. A failure the config caused (the producer crashed, hit its cost cap, or committed nothing) is a fail for that config. A failure the harness caused (the environment did not resolve, the grader timed out, a leak was detected) drops that case from every config's comparison, so no config is charged or credited for it. Reports count both kinds. Effort that was not sent is recorded as not sent, not as the alias's value.

- **Breakdown, not a score.** Pass rate, regressions, check deltas, review findings, pairwise strength, cost, turns and time are reported side by side with n and paired intervals. No weighted composite is computed, which is 400's rule applied here.

- **Measure, never gate.** Benchmark results inform which aliases the PM configures. No pipeline reads them to pick a model or pass a step.

## Current State

- **Replay (177).** `sq replay run/judge/report` regenerates a slice design or task breakdown per config in a history-free sandbox under `~/.config/squadron/replays/`, registered as a temporary cf project, and runs `P4` or `P5` as an `sq run` subprocess. It records `producer_replay` and `pairwise_judgment` records, and reports Bradley-Terry strength, rounds-to-accept, cost and time. Design and tasks only: nothing in the sandbox installs dependencies or runs tests.
- **Observed stats (176).** `sq stats producers` reports per-config outcomes from runs that already happened. Each config saw different slices, so difficulty is a confound. No implementation rows.
- **Effort.** Effort lives only on `models.toml` aliases. The SDK pipeline session sends it since 0.24.19 (#216). One-shot runners record what they sent (`effort_sent`). Whether every dispatch path sends it, and records it, has not been checked as a whole.
- **Static measurement (400).** Complete. Snapshots of any commit (length, lint, types, complexity, duplication, coverage), code-review findings normalized to the audit vocabulary and ingested, durable slice-range records (fork and landing commits), and rollup reports.
- **Noise floor (320, 323).** Repeated audit runs give a per-category noise floor that before/after deltas are reported against.
- **Implementation pipelines.** `P6` and `implement` run the implementation step, a task close-out, a code-review loop, a DEVLOG step and a merge. They need a slice with a design and task file. Fixes are done interactively, so there is no fix pipeline to replay.
- **Fix tests in squadron's history.** Of 51 commits marked `Fixes #`, 46 add tests. A rough grep finds mocking or monkeypatching in 23 of those and private-looking names in 37. Most fix tests are tied to how the original fix was written, so the fairness rule will keep a minority of them.
- **Containment.** The bash tool on OpenAI-compatible models can reach anything the user can (#213). Claude SDK sessions use Claude Code's own tool controls. A replay sandbox is a separate directory, not an OS jail.
- **Cost cap (947).** `pipeline.max_cost_usd` bounds one pipeline run.

## Envisioned State

A case set is built from a project's history. Fix cases come from commits that close an issue and add a test: the parent is the start, the issue text is the task, and the test added by the fix is hidden. Slice cases come from 400's slice-range records: the fork commit is the start, the design and task file at the fork are the task, and the landing commit is the reference. Every candidate is qualified in a sandbox before it joins the set, and fix candidates are checked against the fairness rule. The set is versioned, and qualification records explain every case that was dropped, so the yield per project and per reason is a report, not a guess.

A new production pipeline, `sq run fix <issue>`, implements a fix from an issue following the guide's fix rule: a failing test, the change, the gates, a commit. It is useful on its own, and it is what fix cases replay. Fix-case results therefore measure this pipeline's prompt, not the interactive way fixes are made today. The `implement` step cannot stand in for it: it needs a slice with a design and task file, and a fix has neither.

A benchmark run takes a case set, a list of configs and a sample count. For each case, config and sample, it opens a sandbox at the start commit, resolves the environment, and runs the producer step of the production pipeline for that case kind: the `implement` step from `P6` for a slice case, with its usual phase 6 prompt, and the `fix` pipeline for a fix case. `P6` is canonical; `implement.yaml` carries the same step and differs only in its review model. The replay stops at the producer's committed tree: no task close-out, no review loop, no DEVLOG, no merge, no summary. The review is left out because it mixes the reviewer into the producer's result, and that includes the review the `implement` step carries on itself (`review: { template: code, ... }`, which expands to a review and a checkpoint before the commit). A replay runs the step with its embedded review stripped: same prompt, same dispatch, same commit, no review action and no verdict on the commit. Review happens once, in grading, under a fixed config. It then hands the tree to the grader. The grader applies the hidden set (fix cases), runs the start commit's suite minus the superseded set and the producer's new tests as separate signals, runs lint and type checks under the start commit's tool config, takes a 400 snapshot, and runs a fixed code-review config whose findings are normalized the same way 400 ingests them. One record per case run holds the producer outcome, the grade, usage, a reference to the diff and the identities that make it comparable.

For slice cases, the pairwise judge from 177 compares diffs from the same case, with the reference diff as a contestant, and Bradley-Terry ranks configs across cases. Fix cases are not judged pairwise: the hidden test already gives them an objective grade. Every diff the judge sees is normalized first: DEVLOG, CHANGELOG, task files, review files and slice documents are dropped. The reference still includes whatever its own review loop fixed, so it is reported as a reference line, not ranked as a config.

Reports put the objective grade first, then review findings and pairwise strength, with cost, turns and time beside them, all per config with n. Configs run on the same cases, so two configs are compared on paired per-case differences: each config's samples on a case reduce to one value (the pass fraction for the objective grade), and the paired bootstrap interval is taken over cases; a pair whose interval spans zero is shown as not distinguishable, not ranked. 320's noise floor applies to the LLM signals (review finding counts), not to pass rates.

Reviewer recall runs separately. A planted-defect case is a real diff with known defects injected. Each reviewer config reviews it several times, and its findings are matched to the planted defects to give recall, plus the count of findings that matched nothing.

Effort is part of every config's identity as sent, so "sonnet at high" and "sonnet at xhigh" are two rows only when the effort really differed on the wire.

## Technical Considerations

- **Fix-case yield.** The plan rules out a slice's own tests as hidden tests because they are coupled to that implementation. Most fix tests are coupled the same way: the test for the 0.24.20 summary fix (commit ebd45f3f) patches an internal function by its module path, and the #291 test mocks the pipeline. The fairness rule excludes those, so squadron alone may yield few fix cases. The fix-cases slice therefore ends at a yield report. If yield is too low, fix cases are pooled from other cf projects' history, or the benchmark leans on slice cases. That choice is made on measured yield.

- **Checking the fairness rule.** Each rule needs a language-specific check: reading entry points and exports from packaging metadata at the parent, tracing which project names a test reaches, telling a patch of project code from a patch of a dependency, and telling an assertion failure from a collection or import error. Re-exports and dynamic imports blur the boundary trace. Where a check cannot decide, the case is excluded with that reason, never admitted.

- **Rejected: perturbation checks.** Renaming private symbols in the fix and checking whether the hidden test survives catches tests that use private names, but not tests tied to where the fix lives, such as a test that calls a public helper directly when a different correct fix puts the logic elsewhere. The boundary rule catches both.

- **Grading slice cases.** With no hidden test, a slice case is graded on regressions in the existing suite, check and snapshot deltas, review findings and the pairwise judge against the reference diff. That is weaker evidence than a fix case, and reports have to keep the two case kinds in separate tables.

- **The environment.** Grading needs dependencies installed in the sandbox, which means network access and running the project's install step on code from history. A lockfile that no longer resolves disqualifies the case. Environment identity (lockfile hash, tool versions) is part of the grader identity. Tests that read the developer's environment (refs, timezone, default branch) give different results in a sandbox; qualification at the reference commit catches them, but only if it runs in the same environment the replays use.

- **Containment.** A replay runs model-written code and installs dependencies. It runs at the same trust level as `P6` does today, in a throwaway directory instead of the real repo. OS sandboxing for safety is #213's problem; if #213 lands, replays should use it. Leak detection and the scrubbed producer environment (see principles) are this component's, because they decide whether a result is valid. Whether the agent's auth still works with its config directory redirected is checked in the fix-cases slice, which builds the sandbox environment, so a no surfaces before replay is built on it. Redirecting also drops user-level instructions, and the sandbox carries the project's instruction files as of the start commit, so prompt identity records the instruction files in effect.

- **Stopping a production pipeline at the producer step.** Replays must run the same `implement` step and prompt as `P6`, and the same `fix` pipeline as production, without forking copies that drift. Pipelines today are standalone YAML with no way to reference another pipeline's step, and no run mode stops after a step, so this needs a new executor capability: a `sq run` producer-only mode that runs only the pipeline's producer step (`implement` in `P6`), without its embedded review, commits, and stops. The flag's name and how it reports the stop are slice details; a copied step or prompt is not an option.

- **The fix pipeline in a sandbox.** In production, `sq run fix` commits to the target. In a replay the target is the sandbox's own branch, and the pipeline must not need GitHub access: the frozen issue text is passed in rather than fetched.

- **Cost.** One benchmark is cases × configs × samples implementation runs, each with tool turns, plus a grading review each, plus pairwise judge calls on slice cases that grow with the square of contestants per case. A benchmark refuses to start unless a per-pipeline cap (`pipeline.max_cost_usd`, which defaults to no cap) and a run-level cap are both set. Before any dispatch the run states a dollar bound: replays at cases × configs × samples × the per-pipeline cap, and states that bound before any dispatch. Grading and judging are separate commands, each with its own cap and a bound estimated from observed costs of those calls in the store; the benchmark's total is the sum of the caps. The run-level cap is checked between dispatches, so a pipeline already running can overshoot it by up to one per-pipeline cap; the stated bound includes that. When the cap is hit, it stops dispatching, keeps every record already written, marks the run partial, and reports only cases that completed under every config. Fix cases first because they are the cheapest objective unit.

- **Sample count.** Implementation runs vary more than design drafts. The paired statistic sets how many samples and cases it takes to separate two configs, and so what a benchmark costs. That number is not known until measured; the replay slice measures it on a small run before any large one.

- **The grading reviewer is unmeasured until reviewer recall runs.** Replay and grading use a fixed code-review config before anything shows that config finds defects. Until recall data exists for the grading config, reports flag the review-finding columns as coming from an unmeasured reviewer.

- **Diffs for the judge.** Implementation diffs can be far larger than a slice design. The judge compares diffs within one case, with the task text. Diffs above the judge's context need a stated rule (excluded and counted, or judged on a bounded view), not silent truncation.

- **Planting defects.** Planted defects need ground truth: where the defect is, what kind it is (in 402's category vocabulary), and that it really breaks something, ideally shown by a test that fails. Who writes the defects (hand, mutation tool, or an LLM with verification) and how a finding is matched to a defect (file and line window plus category, or a judge call) are open slice decisions. A loose matcher inflates recall; a strict one deflates it.

- **Record size and count.** Diffs live in content-addressed sidecar files from the start, so records stay small. Normalized review findings stay inline; they are short. 400's coarse-record rule still holds.

## Anticipated Slices

Exploratory. The fix-case path is the keystone: it is the cheapest objective unit and proves the sandbox, environment and grader.

- **Effort audit across dispatch paths.** Every path sends the alias's effort or records that it could not, and every usage record carries effort sent. Small, and a precondition for effort rows meaning anything.
- **Fix cases and qualification (keystone).** Case record, candidate discovery from fix commits, frozen issue text, sandbox environment resolution (including whether agent auth survives the redirected config directory), qualification including the fairness rule for Python, versioned case sets, and the yield report. Qualification runs the reference grade and the parent's test-first check several times; tests that disagree go on a per-case exclusion list that is part of the case's content identity. The yield report states whether the qualified count can separate two configs under the paired statistic, and that answer decides whether fix cases are pooled across projects or slice cases move ahead of fix-case replay.
- **Fix pipeline.** `sq run fix <issue>` as a production pipeline, runnable in a sandbox with frozen issue text.
- **Implementation replay and grading.** The `sq run` producer-only mode, running the producer step of `P6` and `fix` in the sandbox, the scrubbed producer environment and leak scan, the grader (hidden set, pinned suite and tool config, checks, snapshot, fixed review), repeated samples, the replay record with diff sidecars, the run-level dollar cap, and the paired report. Resume: a rerun of the same benchmark skips (case, config, sample) runs that already have records, detects orphaned sandboxes, and marks an interrupted run as such.
- **Slice cases.** Cases from 400 slice ranges, grading without a hidden test, diff normalization, pairwise judging over diffs with the reference as a reference line.
- **Reviewer recall.** Planted-defect cases, the matching rule, and a recall report per reviewer config.

## Non-Goals

- **No public or general-purpose benchmark.** Cases come from the project's own history.
- **No curated input and expected-output datasets.** 300's non-goal stands. The exception is planted-defect cases (427, 428, 429): the planted defect is the ground truth, by design.
- **No slice tests as hidden tests.** They are coupled to the original implementation.
- **No per-case human review, and no per-project boundary declaration.** Qualification is mechanical and reads only what projects already maintain.
- **No automatic model selection.** Results inform the PM's alias configuration; nothing reads them at run time.
- **No composite score.**
- **No OS sandbox.** That is #213.
- **No concurrent replays.** Configs and samples run one after another, as in 177 (#146 covers concurrency).

## Related Work

- **Initiative 140 (Pipeline Foundation)**: slices 176 and 177 provide observed producer stats, replay start points, the history-free sandbox, the subprocess runner, the pairwise judge, Bradley-Terry aggregation and prompt identity. See [177-slice.producer-replay-and-pairwise-judging.md](../slices/177-slice.producer-replay-and-pairwise-judging.md) and [140-arch.pipeline-foundation.md](140-arch.pipeline-foundation.md).
- **Initiative 300 (LLM-as-Judge Scoring)**: the code review template and judge conventions the grader reuses. Gating stays there. See [300-arch.eval-actions-llm-as-judge-scoring.md](300-arch.eval-actions-llm-as-judge-scoring.md).
- **Initiative 320 (Judge Calibration & Quality Metrology)**: the store, `ProjectId`, and the noise-floor method. See [320-arch.judge-calibration-quality-metrology.md](320-arch.judge-calibration-quality-metrology.md).
- **Initiative 400 (Code Quality Measurement)**: snapshots of any commit, normalized review findings and slice-range records. See [400-arch.code-quality-measurement.md](400-arch.code-quality-measurement.md).
- **Slice 947**: the `pipeline.max_cost_usd` cap each implementation run executes under.
- **Issues**: [#216](https://github.com/ecorkran/squadron/issues/216) (effort on the SDK session path, fixed in 0.24.19), [#213](https://github.com/ecorkran/squadron/issues/213) (OS sandbox for the bash tool), [#146](https://github.com/ecorkran/squadron/issues/146) (concurrency), [#210](https://github.com/ecorkran/squadron/issues/210) (producer effectiveness, origin of replay).
- **Initiative plan**: [001-initiative-plan.squadron.md](../project-guides/001-initiative-plan.squadron.md), entry 15.
