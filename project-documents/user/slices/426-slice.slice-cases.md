---
docType: slice-design
slice: slice-cases
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [421, 422, 424, 425]
interfaces: []
dateCreated: 20261104
dateUpdated: 20261105
status: not_started
---

# Slice Design: Slice Cases

## Overview

This slice adds the second case kind, built from completed slices, and judges their implementations against each other. It adds four layers:

1. **Slice-case building** (`sq benchmark slice-cases build`). Candidates come from 403's `slice_ranges` record. The start is the fork commit, the task is the slice design and task file as they stood at the fork, and the reference is the slice branch's tip. The superseded set comes from 422's closure-digest test sets, and the exclusion list from 422's repeated reference runs. Slice cases have no hidden set. Every candidate gets a qualification record with its outcome and, when rejected, the reason.
2. **The slice-case runner.** A `CaseKindRunner` for `slice` that registers the sandbox as a cf project inside the scrubbed home and runs producer-only `P6` (424).
3. **Pairwise judging over diffs** (`sq benchmark judge`). Each diff is normalized first: DEVLOG, CHANGELOG, task files, review files, slice documents and the lockfile are dropped. 177's judge then compares sample-matched replays across configs, and each replay against the reference diff. A case whose largest judge prompt exceeds a configured size is not judged and is counted, so nothing is ever truncated.
4. **Report tables.** `sq benchmark report` shows slice cases in their own tables, separate from fix cases: the objective grade (no regressions), checks, review findings and cost from 425, plus a pairwise section with Bradley-Terry strength, a paired interval per pair of configs, and the reference as a reference line.

## Value

Developer value. Most P6 spend goes to full-slice implementation, and fix cases cannot measure it. Slice cases benchmark that work on the project's own merged slices, with the same sandbox, environment, grader and caps as fix cases.

Slice cases are weaker evidence than fix cases, since there is no hidden test. Keeping them in separate tables, and reporting the pairwise judge beside the objective grade rather than folding it in, keeps that difference visible. If 422's yield report shows too few fix cases, slice cases are the fallback the slice plan names.

## Technical Scope

**Included**

- `SliceQualification` records, `SliceCandidateRejection`, and slice-case qualification over 403's landings (D1–D6).
- `CfRegistration`, extracted from `ReplaySandbox`, and run under the scrubbed environment for slice cases (D9).
- `SliceCaseRunner`, registered on 424's `CaseKindRunner` seam, invoking producer-only `P6` (D8, D10).
- Diff normalization for the judge (D11).
- The diff judge: a packaged prompt, sample-matched pairing, forfeits, the over-size rule, the `DiffJudgment` and `OverSizeCase` records, caps, bound and resume (D12–D16).
- Report: a table set per case kind, and the pairwise section for slice cases (D17).
- Slice-case rows in 422's `sq benchmark yield`.
- CLI `sq benchmark slice-cases build` and `sq benchmark judge`, with matching `/sq:benchmark` subcommands.
- No edits to 424 or 425: 424 provides `CaseKindRunner.requalify` (D8), and 425 provides `bootstrap_mean_interval` (D17).

**Excluded**

- Pairwise judging of fix cases. The hidden test grades them objectively (architecture).
- Slices that landed more than once, or whose branch merged the target in. They are rejected and counted (D2), not spliced.
- Reviewer recall (427). The review columns keep 425's unmeasured-reviewer flag.
- Languages other than Python (slice plan Future Work 1).
- A judged bounded view of oversized diffs (D14).

## Dependencies

### Prerequisites

- **421:** `BenchmarkCase` with `CaseKind.SLICE`, `CaseSet`, `BenchmarkRecordStore`, `BenchmarkSandbox`, `HistoryFreeSandbox`, `EnvironmentIdentity`, `ScrubbedEnvironment`, `run_suite` and the adapter registry.
- **422:** `test_sets` (closure-digest sorting), the repeat-and-exclude step, `benchmark.qualification_repeats`, the Python adapter's `is_test_side`, `collect` and `grader_commands`, the yield report and its separability bound.
- **424:** producer-only mode on `sq run`, the `CaseKindRunner` seam, `ImplementationReplay`, `replay_one`, the benchmark runner, the leak scan and the benchmark lock.
- **425:** `grade_one`, `GradingAdapter`, `ContentSidecars`, `paired_stats`, `bench_report`, and the grade-command pattern for caps, bound and resume.
- **403 (initiative 400):** `SliceRanges` / `SliceLanding` in the store (`get_slice_ranges`), recorded by `sq metrology slice-ranges`.
- **177:** `parse_verdict`, `combine`, the one-shot judge dispatcher (`one_shot_judge_dispatcher`), `bradley_terry.fit`, and `ReplaySandbox`'s cf registration.
- **External:** `cf` on the harness's `PATH`.

### Interfaces Required

- `plan_file_for(index, root)` (`stats/planning_docs.py`), to find the slice's initiative at the fork.
- The design and task path patterns in `replay/start_point.py` (`_KINDS`), made public so slice cases find the same files 177 does.
- `JudgeRef`, `JudgeCall`, `PairOutcome` (`metrology/replay_models.py`).
- `metrology.judge_timeout_s`, the judge call bound 177 already reads.
- `ProcessRunner`, for `git show`, `git ls-tree`, `git rev-list` and `git diff` in the user's checkout.

## Architecture

### Component Structure

```
src/squadron/
  benchmark/
    slice_discovery.py        SliceRanges -> SliceCandidate list, discovery rejections
    slice_task.py             design + task file at the fork -> task_text
    slice_qualify.py          per-candidate pipeline, writes SliceQualification
    slice_case_build.py       orchestrates discovery -> qualify -> cases -> case set
    slice_runner.py           SliceCaseRunner (CaseKindRunner for CaseKind.SLICE)
    diff_normalize.py         normalize(diff bytes) -> NormalizedDiff
    diff_judge.py             contestants, pairing, forfeits, size check, judge loop
    diff_judge_runner.py      plan, bound, cap, lock, resume
    bench_report.py           + per-kind tables; pairwise section for slice cases
    yield_report.py           + slice-case rows
  replay/
    cf_registration.py        CfRegistration (extracted from ReplaySandbox)
    sandbox.py                ReplaySandbox composes CfRegistration
    judging.py                judge_pair extracted (shared with diff_judge)
    start_point.py            artifact patterns made public
  metrology/
    benchmark_models.py       + SliceQualification, SliceCandidateRejection,
                                DiffJudgment, OverSizeCase
    benchmark_store.py        + slice qualification and diff judgment records
  data/benchmark/
    pairwise-diff-judge.md    judge prompt for implementation diffs
  cli/commands/
    benchmark_slice.py        `slice-cases build`, `judge`
commands/sq/benchmark.md      + the same subcommands
```

`slice_case_build` and `slice_qualify` reach the language only through 422's adapter registry. `diff_judge` is pure apart from the injected dispatcher and store. Each module stays under 300 lines.

### Data Flow

**Building slice cases:**

```
sq benchmark slice-cases build --set slices [--repo PATH]
  get_slice_ranges(project_id) → none: refuse, name `sq metrology slice-ranges`
  for slice index in record:
     discovery checks (D2): one landing, no merges on the branch
     task text at fork (D3): design + task file, slice plan present
     reference diff fork..tip: only judge-dropped paths → no_code_change
     sandboxes at fork and tip → EnvironmentIdentity (key: fork digest)
        existing record with same key and rule version → skip
     collect both (adapter) → test_sets → superseded (hidden candidates ignored)
     full suite at tip × qualification_repeats → excluded_tests
     regression selection empty → no_regression_signal
     write BenchmarkCase(kind=slice) + SliceQualification
  write_case_set(--set, qualified ids); print slice-case yield rows
```

**Replaying a slice case** (inside 424's `replay_one`):

```
BenchmarkSandbox(fork_sha) → EnvironmentIdentity
SliceCaseRunner.requalify(case, env)          slice_qualification_for, else qualify again
SliceCaseRunner.invoke:
   env = ScrubbedEnvironment(grant=profile).with_tools(("cf",))
   CfRegistration(env).register(tree, name=<sandbox id>, branch, slice index)
   <installed sq> run P6 <index> -m <alias> --producer-only --max-cost <cap> --run-id <rid>
      cwd=tree, env=env
→ 424 reads run state, diffs start..HEAD → sidecar, scans transcript, writes ImplementationReplay
```

**Grading** is 425's `grade_one`, unchanged. The hidden set is empty, so a slice case passes when the regression run has no failing node.

**Judging a benchmark:**

```
sq benchmark judge bench-3f9c… --max-cost 8
  load BenchmarkRun, slice cases in its set, replays
  resolve judge (benchmark.judge_model or --judge-model) → JudgeRef(diff prompt hash)
  refuse: missing run cap | no judge | no per-call cost figure | --repo missing for a case's project
          | a case's tip_sha missing from --repo (names case and sha)
  per case:
     any replay with a harness absence → case not judged (counted at report time)
     contestants: committed replays + reference (start..tip from the user's checkout)
     normalize every diff → sidecar (diffs kind)
     pairs (D13): sample-matched cross-config pairs + each replay vs reference
     forfeits: pairs with an absent side → recorded with no call
     largest pair prompt > benchmark.judge_max_prompt_chars → case over_size (counted)
  print bound ─── nothing dispatched before this line
  for pair needing calls: cap check → judge_pair (two orders) → DiffJudgment
  print summary
```

### State Management

- **Store records** (persistent): one `slice_qualification` per (project, slice, landing, fork environment digest), one `benchmark_case` per qualified slice (421's record), one `diff_judgment` per (benchmark, case, pair, judge), and one `over_size_case` per (benchmark, case, judge). All are optional sibling payloads on `MetrologyRecord`. No migration.
- **Sidecars:** normalized diffs in 425's `ContentSidecars("diffs")`, referenced by sha256 from each judgment.
- **Sandboxes** (transient): 421's directories. For slice-case replays the cf project lives in the scrubbed home's cf registry, so removing the home removes it. Nothing is added to the user's cf registry.
- **Judge lock:** `<benchmark root>/<benchmark_id>.judge.lock`, the same process lock 424 and 425 use, separate from their locks.

## Technical Decisions

### D1 — Candidates come from the `slice_ranges` record only
Status: decided
- `build` reads `get_slice_ranges(project_id)`. Each slice index in the record is a candidate. No record refuses the build, naming `sq metrology slice-ranges`. A slice 403 could not resolve is not in the record, and 403's own command reports why.
- Rejected: re-resolving landings here. 403 stores landings because reflogs expire. A second resolver would drift from it.

### D2 — Landing and reference selection
Status: decided
- The start is the landing's `fork_sha`. The reference is the landing's `tip_sha`, not `after_sha`. On a merge landing, `fork..after` also contains whatever reached the target while the branch was open. `fork..tip` is the slice's own work.
- Discovery rejections (`SliceCandidateRejection`):
  - `multiple_landings`: the slice has more than one landing. A follow-up landing means the first did not finish the work. Splicing is rejected for now, as 422 does for `multiple_closing_commits`, and the count shows whether it is worth adding.
  - `branch_contains_merges`: `git rev-list --merges fork..tip` is non-empty. A merge of the target into the branch puts unrelated work in the reference diff.

### D3 — Task text is the design and task file at the fork
Status: decided
- The design and task files are found at `fork_sha` with `git ls-tree`, using `start_point.py`'s patterns (`{DOCS_ROOT}/user/slices/{index}-slice.*.md` and `{DOCS_ROOT}/user/tasks/{index}-tasks.*.md`). Those patterns become public and are defined once.
- `task_text` is each file's content, in the order design then tasks (task files sorted by name), each preceded by a line `## File: <path>`. Content is verbatim, frontmatter included. This string is part of the case id (421 D1).
- Rejections: `no_design_at_fork`, `no_tasks_at_fork`, and `no_slice_plan_at_fork` when `plan_file_for` finds no plan listing the index at the fork. P6 needs all three, and cf registration needs the plan (D9).
- The tree at `fork_sha` is what the producer reads through cf. `task_text` records it in the case and feeds the judge's task section. It is not passed to the producer separately.

### D4 — No-code slices are rejected
Status: decided
- If every path in `fork..tip` is one that diff normalization drops (D11), the candidate is rejected with `no_code_change`. A planning-only or documentation-only slice gives the grader and the judge nothing to compare.
- The check runs before any sandbox, using `git diff --name-status` in the user's checkout.

### D5 — Test sets and exclusions reuse 422
Status: decided
- Both sandboxes are collected through the adapter's `collect` (closure digests), and 422's `test_sets` sorts the nodes. For a slice case:
  - **superseded:** nodes only at the fork, and nodes at both with different digests;
  - **hidden:** always empty. Nodes only at the tip are the slice's own tests, which the architecture rules out as hidden tests. They are ignored.
- The full suite runs `benchmark.qualification_repeats` times at the tip. Nodes whose outcome differs across runs go on `excluded_tests` as `flaky`, and nodes that fail every run go on it as `fails_at_reference`, as 422 D9 does. The reasons are kept on the qualification record.
- If the regression selection (fork nodes − superseded − excluded) is empty, the candidate is rejected with `no_regression_signal`. A case with nothing to regress gives the grade no information.
- Data and support changes in the tests are not rejected. 422 rejects them because hidden tests depend on them. A slice case has no hidden tests, and the grader restores existing test-side files before the regression run (425 D1).

### D6 — Qualification records, reuse and re-qualification
Status: decided
- `SliceQualification` holds `project_id`, `slice_index`, `slice_name`, `landing_after_sha`, `fork_sha`, `tip_sha`, `rule_version` (`SLICE_RULE_VERSION`, an int constant in `slice_qualify.py`, bumped when any check changes), `start_environment` and `reference_environment` (or `None` when rejected before sandboxes), `repeats`, `outcome` (422's `QualificationOutcome`), `case_id`, `rejection`, `detail`, `excluded_with_reasons` and `created_at`.
- Record id: `slicequal-<sha256(project_id.value)[:12]>-<slice_index>-<landing_after_sha[:12]>-<fork env digest[:12] or "pre">`. A newer result under the same key overwrites it.
- Reuse and re-qualification follow 422 D10: `build` skips a candidate whose record matches the fork environment digest and rule version, unless the outcome is `harness_error`. `slice_qualification_for(case, environment)` returns a record only when the key and rule version match. Otherwise `qualify_slice_candidate` runs again.
- Harness failures (timeouts, `SuiteRunError`, sandbox errors, and a failed or timed-out `git` call in discovery or qualification) are logged at ERROR and recorded as `harness_error`. They are never counted as a rejection that blames the slice.
- `CaseProvenance` carries `source_ref = "slice:<index>@<landing_after_sha>"` and the slice name. It is not part of the case id.

### D7 — Slice cases use 422's adapter
Status: decided
- Slice-case building calls only `is_test_side`, `collect` and `grader_commands` on 422's `FixCaseAdapter`, through 422's registry. No new protocol and no 422 code changes.
- A narrower protocol waits until a language needs slice cases without fix cases.

### D8 — The slice-case runner invokes producer-only `P6`
Status: decided
- `SliceCaseRunner` is registered for `CaseKind.SLICE` on 424's `CaseKindRunner` seam. It runs the installed `sq` by absolute path (resolved once at harness start, as 424 D5 does):

  `sq run P6 <slice_index> -m <alias> --producer-only --max-cost <per-replay cap> --run-id <replay record id>`

  with `cwd=<tree>` and the producer environment from D9. The replay record's `pipeline` is `P6` and its `producer_step` is `implement`.
- The diff is `start_sha..HEAD`, read by 424, whatever branch the producer left checked out. The phase 6 prompt may tell the agent to create the slice branch, and that is harmless.
- **Re-qualification routes by kind.** 424's `replay_one` calls `runner.requalify(case, environment)` from the `CaseKindRunner` seam. `SliceCaseRunner.requalify` calls `slice_qualification_for` and otherwise `qualify_slice_candidate`.
- A case set with slice cases now plans instead of refusing (424 D5).

### D9 — cf registration inside the scrubbed home
Status: decided
- P6's `implement` step runs cf-ops (`set_slice`, `set_phase`, `build_context`), so the tree must be a registered cf project. The producer runs with `HOME=<id>.home` (421 D7), so cf reads its registry from the scrubbed home. Registration therefore runs under the producer's environment, not the harness's.
- `CfRegistration(runner, env)` is extracted from `ReplaySandbox._register_with_cf`: `cf init --lite --no-ide --name <name>`, `cf config set git.integration_branch <branch>`, then `cf set arch <initiative>` (the initiative from `plan_file_for` at the start commit). `ReplaySandbox` composes it with the harness environment and keeps its behavior and tests. `SliceCaseRunner` uses it with the scrubbed environment.
- A failed or timed-out cf step is a harness absence (424 D10), logged at ERROR with the step and its stderr. The producer never ran, so it is not charged to the config.
- Removal: the registry is inside the scrubbed home, so removing the home removes the project. The slice-case runner calls no `cf project rm`, and the user's cf registry is never touched.
- `cf` is not on the scrubbed `PATH` (421's `HARNESS_TOOL_ALLOWLIST` is `git` and `uv`). `ScrubbedEnvironment.with_tools(tools)` returns a copy whose `<id>.home/bin` also links each named tool as resolved on the harness's `PATH`. The slice runner asks for `("cf",)`, a constant in `slice_runner.py`. Suite runs and fix-case producers never get it. The tool links are not part of `EnvironmentIdentity`, which describes the installed project, so the grade sandbox's digest still matches the replay's (425 D1). cf's version is already part of prompt identity (177's `PromptIdentity.cf_version`).
- Implementation step 1 is a spike. It confirms that cf registers, sets the slice and builds context under a scrubbed home, and that 424's leak-scan path list covers the cf install location and anything cf reads outside the home. A no is written as `BLOCKED:` in the task file for the PM, the same way 421's auth spike works.

### D10 — Grading slice cases
Status: decided
- Slice cases go through 425's `grade_one` and `grade_runner` unchanged. The hidden step selects nothing, so a subject passes when no selected regression node fails. The producer-new signal, checks, edits, suppressions, snapshot and review are recorded as for fix cases.
- The reference grade runs on `start..tip`. A tip that fails its own grade is dropped with 425's `reference_failed_grade`, as for fix cases.
- Pass rate is a weak signal on slice cases, since most replays that keep the suite green pass. The report shows it anyway, beside the pairwise section, because "the producer broke existing behavior" is the one objective fact a slice case gives.

### D11 — Diff normalization for the judge
Status: decided
- `normalize(diff: bytes) -> NormalizedDiff(text, dropped_paths, binary_paths)` is a pure function in `diff_normalize.py`. It splits the diff on `diff --git` headers and keeps each file section unless both its old and new paths are dropped. A rename with one side kept is kept.
- Dropped paths, defined once as constants in `diff_normalize.py`:
  - `DEVLOG.md` and `CHANGELOG.md` at the repository root;
  - everything under `{DOCS_ROOT}/user/tasks/`, `{DOCS_ROOT}/user/reviews/` and `{DOCS_ROOT}/user/slices/`;
  - `uv.lock`. This one is beyond the slice plan's list. It is machine-generated, often thousands of lines, and the intent is already visible in `pyproject.toml`.
- A binary file section is replaced by one line, `Binary file <path> changed`. Base85 patch data says nothing to a judge.
- A diff that normalizes to nothing is shown to the judge as `(no changes outside dropped paths)`. That contestant still competes.
- The normalized text is stored with `ContentSidecars("diffs")`, and each judgment carries its sha256, so a judgment can be checked against exactly what the judge saw.
- Normalization is for the judge only. Grading uses the full diff.

### D12 — The diff judge reuses 177's core with its own prompt
Status: decided
- `data/benchmark/pairwise-diff-judge.md` frames the pair as two implementations of the same task, given as diffs against the same start commit, and asks which better implements the design and task file: correctness, completeness against the tasks, fit with the existing code, and tests. It ends with 177's `WINNER: A|B|TIE` line, so `parse_verdict` reads it unchanged. Its sha256 is the `JudgeRef.prompt_hash`, so these judgments never mix with 177's.
- The prompt body is the packaged prompt, `## Task` with the case's `task_text`, then `## Implementation A` and `## Implementation B` with the normalized diffs.
- 177's per-pair loop (`_call`, `_judge_pair`: two orders, bounded calls, a failed pair left unrecorded) is extracted from `judging.py` as `judge_pair(prompt_a_first, prompt_b_first, dispatcher, timeout_s, label) -> tuple[JudgeReply, JudgeReply] | None`. `judge_replay_set` and `diff_judge` both call it. 177's tests pass unchanged.
- Dispatch is `one_shot_judge_dispatcher(alias)`, text only with no tools, so the judge cannot read the user's checkout. Outcomes come from `combine`.
- The judge alias is `benchmark.judge_model`, declared in `config/keys.py` with no default, or `--judge-model`. With neither, `judge` refuses and names both. The timeout is 177's `metrology.judge_timeout_s`.

### D13 — Contestants and pairing
Status: decided
- **Contestants** per case: each replay of the case in the benchmark, plus the reference (`reference:<tip_sha>`).
- **Pairs:**
  - for each pair of configs and each sample number s, config A's sample s against config B's sample s;
  - each replay against the reference.
- With C configs and k samples, that is `k·C(C−1)/2 + k·C` pairs per case. Two configs at k = 3 give 9 pairs and 18 calls. Pairs within one config are not judged, because the ranking is per config and a config against itself carries no information about it.
- Rejected: every pair of contestants. With two configs at k = 3 that is 21 pairs, more than twice the calls, for comparisons the ranking does not use.

### D14 — Over-size rule: the case is not judged, and it is counted
Status: decided
- Before any call, `diff_judge` builds every pair prompt for the case. If the longest exceeds `benchmark.judge_max_prompt_chars` (declared in `config/keys.py`, default 400 000 characters, about 100k tokens at four characters per token), the case is not judged. It is recorded as `over_size` with the longest prompt's length and the contestant that produced it.
- The whole case is excluded, not only the oversized contestant. Dropping one diff would leave its config judged only on smaller cases, and the configs that write larger diffs would be ranked on a different case mix.
- The report counts over-size cases and prints the limit in effect. Raising the key and rerunning `judge` judges them.
- No truncation anywhere. Rejected: a bounded view (file list plus selected hunks). Which hunks to show is itself a judgment that could favor one config, and the slice plan allows either rule.

### D15 — Absences in judging
Status: decided
- **Harness absences drop the case.** A case with any replay carrying a harness absence (424 D10) is not judged, and the report counts it under that reason. A case dropped at grading (425's harness absences, `reference_failed_grade`) is excluded from the pairwise section at report time, as 425 D13 does for the objective grade.
- **Config absences forfeit.** In a pair where one side is a replay with a config absence (`no_commit`, `blocked`, `cost_cap`, `producer_failed`), the other side wins without a judge call. The judgment is recorded with `forfeit=True` and no calls. If both sides are absent, the pair is recorded as a forfeit `TIE`. This applies "absent is not zero" to the judge: committing nothing is a loss, not a missing data point.
- **Failed calls** leave the pair unrecorded, logged at ERROR, so a rerun retries it (177 D5). They are counted in the summary.
- Harness-absent cases are counted at report time from the replay records. No judge record is written for them.
- An over-size case is written as an `OverSizeCase` record, so the report counts it. It is replaced when the limit changes.

### D16 — Caps, bound and resume for judging
Status: decided
- `judge` follows 425 D9: `--max-cost USD` is required. The per-call figure is the largest observed judge-call cost among stored `DiffJudgment`s with the same judge alias, or `--judge-cost USD`. With neither, it refuses and names the flag. The bound prints before the first call:

```
judge bench-3f9c…  judge gpt-judge (openai-oauth)  limit 400000 chars
slice cases 8: 6 to judge · 1 over size · 1 harness-absent
pairs 54 (6 forfeits) → 96 calls × $0.04 (max observed) = $3.84, capped at run cap $8.00
       + one call of overshoot $0.04 → at most $3.88
```

- The cap is checked before each call. Hitting it stops judging, keeps every record, and exits 2.
- Record ids:
  - pair: `diffjudge-<benchmark_id[6:18]>-<case_id[5:17]>-<sha256(sorted refs, judge prompt hash, judge alias)[:12]>`
  - over-size case: `oversize-<benchmark_id[6:18]>-<case_id[5:17]>-<sha256(judge prompt hash, judge alias)[:8]>`
- Resume is a lookup by id. A recorded pair is never judged again under the same judge.

### D17 — Report: tables per case kind, and the pairwise section
Status: decided
- `bench_report` groups included cases by `CaseKind` and renders 425's sections once per kind, under a `fix cases` or `slice cases` heading. Fix-case output is unchanged. In slice tables the hidden column is omitted, and the pass column is headed `no regressions`.
- Slice cases add a **pairwise** section after the review findings, for the latest judge, with any others listed:
  - Per config: Bradley-Terry strength from `bradley_terry.fit`, pooled over included cases, with wins, losses, ties, inconsistent, invalid and forfeits, and n judged pairs. Contestants in the fit are config row keys (425 D13) and `reference`. A strength with no finite value shows 177's reason.
  - The reference is a separate line marked `reference`, never ranked.
  - Per pair of configs: per case, A's win share `w(c)` over that case's sample-matched pairs (a win counts 1, a tie 0.5; inconsistent and invalid pairs are left out). The paired difference `d(c) = 2·w(c) − 1` goes through 425's paired bootstrap, giving `A ahead`, `B ahead`, `not distinguishable` or `too few cases`. The ranking verdict comes from this interval, not from the strengths.
  - Counts: cases judged, over size (with the limit), harness-absent, and failed pairs pending.
- The interval comes from 425's `bootstrap_mean_interval(values, seed)` (425 D14), called on the vector of `d(c)`. No change to 425.
- No composite is computed. The pairwise section never adjusts the objective grade, and the "no composite field" test covers the new section.

### Technology Choices

- No new dependencies.

### Patterns and Conventions

- `SliceCandidateRejection` (`multiple_landings`, `branch_contains_merges`, `no_design_at_fork`, `no_tasks_at_fork`, `no_slice_plan_at_fork`, `no_code_change`, `no_regression_signal`) is a `StrEnum` in `benchmark_models.py`. 424's `CaseDrop.reason` widens to accept `SliceCandidateRejection`. Reports group by values, never by message text.
- Every collaborator of `slice_qualify`, `slice_runner` and `diff_judge_runner` is injected (sandbox factory, adapter registry, cf registration, invoker, dispatcher, store, clock). Tests run no model, no cf and no git outside fixtures.

## Implementation Details

### API Contracts

```python
def normalize(diff: bytes) -> NormalizedDiff: ...

class CfRegistration:
    def __init__(self, runner: ProcessRunner, env: Mapping[str, str] | None) -> None: ...
    def register(self, tree: Path, name: str, branch: str, slice_index: int) -> None: ...
```

**`sq benchmark slice-cases build --set NAME [--repo PATH] [--keep]`**

One line per candidate (`slice 403 qualified case-… (412 regression nodes, 3 superseded, 1 excluded)` or the rejection reason), then the slice-case yield rows for this project. Exit 0 when the build finished, whatever the yield. Exit 1 when no `slice_ranges` record exists or a harness failure stops the build.

**`sq benchmark judge BENCHMARK_ID --max-cost USD [--judge-model ALIAS] [--judge-cost USD] [--repo PATH …]`**

Output: the bound, one line per pair (`case-… opus s1 vs sol s1: A` or `forfeit B`), then a summary. Exit 0 complete, 2 run cap reached, 1 refusal or harness stop. `--repo` is needed to read reference diffs from the user's checkout, as in 425.

**`sq benchmark report BENCHMARK_ID [--grader DIGEST] [--json]`**

```
slice cases                         n   k  no regressions  regr  new tests  config absences
  opus  (sdk, effort high)          6   3       0.89          3   88/92      cost_cap 1
  sol   (openai-oauth, effort med)  6   3       0.78          6   61/70      no_commit 1
  reference                         6   –       1.00          0    –
…
pairwise (judge gpt-judge, prompt 4b1d…)   strength   W   L   T  inc  inv  forfeit  pairs
  opus                                      1.42     11   5   2   0    0     1      18+
  sol                                       0.70      5  11   2   0    0     1      18+
  reference                                 1.18     (reference line, not ranked)
  opus vs sol   d +0.33  [−0.05, +0.67]  not distinguishable   (n=6 cases)
judged 6 · over size 1 (limit 400000 chars) · harness-absent 1 · pending 0
```

`/sq:benchmark` mirrors `slice-cases build` and `judge` with the same arguments and output.

### Database / Storage Schema

```python
class SliceQualification(BaseModel, frozen=True):
    project_id: ProjectId
    slice_index: int
    slice_name: str
    landing_after_sha: str
    fork_sha: str
    tip_sha: str
    rule_version: int
    start_environment: EnvironmentIdentity | None
    reference_environment: EnvironmentIdentity | None
    repeats: int
    outcome: QualificationOutcome            # 422's: qualified | rejected | harness_error
    case_id: str | None
    rejection: SliceCandidateRejection | None
    detail: str
    excluded_with_reasons: tuple[tuple[str, TestRejection], ...]
    created_at: datetime

class DiffJudgment(BaseModel, frozen=True):
    benchmark_id: str
    case_id: str
    judge: JudgeRef                          # prompt_hash of pairwise-diff-judge.md
    a: str                                   # replay record id or "reference:<sha>"
    b: str
    a_diff: str | None                       # normalized diff sidecar sha256; None for an absent side
    b_diff: str | None
    forfeit: bool
    first_call: JudgeCall | None             # None on a forfeit
    second_call: JudgeCall | None
    outcome: PairOutcome | None
    first_usage: UsageRecord | None
    second_usage: UsageRecord | None
    max_prompt_chars: int                    # the limit in effect
    created_at: datetime

class OverSizeCase(BaseModel, frozen=True):
    benchmark_id: str
    case_id: str
    judge: JudgeRef
    longest_prompt_chars: int
    longest_contestant: str
    max_prompt_chars: int                    # the limit in effect
    created_at: datetime
```

`MetrologyRecord` gains `slice_qualification`, `diff_judgment` and `over_size_case` with `RECORD_TYPE_*` constants. `BenchmarkRecordStore` gains `write_slice_qualification`, `get_slice_qualification(project_id, index, after_sha, env_digest)`, `list_slice_qualifications(project_id=None)`, `write_diff_judgment`, `diff_judgments_for(benchmark_id, judge_alias=None)`, `write_over_size_case`, `over_size_cases_for(benchmark_id, judge_alias=None)`. A judgment stays under 4 KB: diffs are sidecars, and calls keep only 177's raw tails.

## Integration Points

### Provides to Other Slices

- Slice cases and slice-case sets, usable by any later benchmark work, including 427 if planted defects are drawn from slice diffs.
- `normalize` for any consumer that shows implementation diffs to a model.
- `CfRegistration` for any sandbox that needs a cf project under a given environment.
- `judge_pair`, shared by 177's design and task judging and the diff judge.

### Consumes from Other Slices

- **403:** the `slice_ranges` record, read only. A slice resolved after a build is picked up by the next build.
- **421:** used as specified. The one addition is `ScrubbedEnvironment.with_tools`, which leaves the default tool list and `SCRUB_SPEC_VERSION` unchanged, so fix-case qualifications stay valid.
- **422:** `test_sets`, the repeat step, `QualificationOutcome`, `TestRejection` and the Python adapter, all unchanged. The yield report gains slice-case rows.
- **424:** the `CaseKindRunner` seam and producer-only `P6`. This slice adds `SliceCaseRunner` against that seam (D8) and widens `CaseDrop.reason`.
- **425:** `grade_one` and `grade_runner` unchanged. `bench_report` gains the per-kind grouping and the pairwise section. The pairwise verdicts call 425's `bootstrap_mean_interval` (D17).
- **177:** the judge core with `judge_pair` extracted, `bradley_terry.fit`, and `ReplaySandbox` composing `CfRegistration`. 177's tests pass unchanged.

## Success Criteria

### Functional Requirements

- `sq benchmark slice-cases build --set slices` on squadron reads its `slice_ranges` record, writes a `SliceQualification` for every slice index in it, and writes a case for each qualified slice. Every rejected slice has a `SliceCandidateRejection` or `harness_error` with detail. None is silently dropped.
- A qualified slice case has `start_sha = fork_sha`, `reference_sha = tip_sha`, a `task_text` holding the design and task file as of the fork, an empty hidden set, a superseded set from closure digests, and an exclusion list from the repeats.
- Fixture slices produce each rejection: two landings, a merge on the branch, no task file at the fork, a docs-only slice, and an empty regression selection.
- `sq benchmark run` on a set with slice cases replays them through `sq run P6 <index> --producer-only` in a scrubbed sandbox registered with cf in the scrubbed home. The user's cf project list is the same before and after.
- `sq benchmark grade` grades slice cases. `sq benchmark report` shows them in tables separate from fix cases.
- The judge sees only normalized diffs. A test diff containing DEVLOG, CHANGELOG, task, review, slice-document and `uv.lock` changes, a rename and a binary file normalizes to the code changes, the kept rename and a binary marker line.
- The reference appears in the pairwise section as a reference line with no rank.
- A case whose longest pair prompt exceeds `benchmark.judge_max_prompt_chars` is not judged, is recorded as `over_size`, and is counted in the report with the limit. No prompt is ever truncated.
- A config-absent replay forfeits its pairs without a judge call. A case with a harness-absent replay is not judged.
- Each new failure path has a test that asserts its signal: a failing cf step gives a harness absence with an ERROR log, a failing `git` call in qualification gives `harness_error`, and a `tip_sha` missing from `--repo` makes `judge` refuse naming the case and sha.
- `judge` without `--max-cost`, without a judge alias, or without a per-call figure refuses and names what is missing. The bound prints before the first call. Hitting the cap exits 2 and keeps every record. A rerun skips judged pairs.

### Technical Requirements

- `ruff format`, `ruff check` and `pyright` (zero errors) are clean.
- `normalize` is tested on a real squadron slice diff (a landed slice's `fork..tip`, with its DEVLOG, task file and review files) as well as synthetic sections.
- Qualification fixtures come from squadron's real `slice_ranges` landings for at least one merge landing and one fast-forward landing.
- `tests/replay/` passes unchanged after `judge_pair` and `CfRegistration` are extracted. `tests/benchmark/` passes unchanged except where D8 routes re-qualification and D17 extracts the interval.
- The pairwise reduction has hand-computed tests: a case with wins, ties and an inconsistent pair, and a pair of configs whose interval spans zero.

### Integration Requirements

- A case set mixing fix and slice cases runs, grades, judges and reports, with each kind in its own tables.
- 422's yield report shows slice-case rows beside fix-case rows for the same project.

### Verification Walkthrough

These are draft commands. `slice-cases build` and `judge` do not exist until this slice is implemented. The steps need `sq benchmark auth-check` yes answers for the aliases used, `benchmark.grading_review_model` and `benchmark.judge_model` set, and caps as in 424 and 425.

1. **Record landings.** `sq metrology slice-ranges <indices>` for squadron's merged slices (for example the 400-initiative slices). The output lists each landing with fork and tip.

2. **Build slice cases.**
   ```bash
   sq benchmark slice-cases build --set slices
   sq benchmark yield
   ```
   One line per slice: qualified with regression, superseded and excluded counts, or a rejection reason. `yield` shows slice-case rows beside fix-case rows.

3. **Replay one case under two configs.**
   ```bash
   cf project list > /tmp/cf-before.txt
   sq benchmark run --set slices --model opus --model sol --samples 1 \
     --max-cost 20 --max-cost-per-replay 8 --case <case-id>
   cf project list | diff /tmp/cf-before.txt -
   sq benchmark replay-show <record-id> --diff
   ```
   Two replay lines show `committed`, the leak verdict and cost. The cf project list is unchanged. The record shows `pipeline P6`, `producer_step implement`, and a diff against the fork commit.

4. **Grade.** `sq benchmark grade <bench-id> --max-cost 5 --review-cost 0.25`. The reference line for the case prints `pass`, and each replay prints pass or fail with its regression count.

5. **Judge.**
   ```bash
   sq benchmark judge <bench-id> --max-cost 3 --judge-cost 0.05
   ```
   The bound prints first, with the limit and pair count (1 cross-config pair and 2 reference pairs for two configs at k = 1). Each pair prints its outcome.

6. **Report.** `sq benchmark report <bench-id>`. A `slice cases` table appears separately from any fix-case table, then the pairwise section with strengths, the reference line marked as not ranked, the pair verdict (`too few cases (1)` at this size), and the count line.

7. **Over-size rule.** Set `benchmark.judge_max_prompt_chars` below the case's prompt length (`sq config set benchmark.judge_max_prompt_chars 1000`) and rerun step 5 on a fresh benchmark id (another `--samples` value). The case is reported `over_size` with its length, no judge call is made, and the report counts it. Unset the key afterwards.

8. **Normalization.** `uv run pytest tests/benchmark/test_diff_normalize.py -v` runs the real-slice fixture: DEVLOG, task file and review files are gone, and code files remain.

## Risk Assessment

### Technical Risks

- **cf under a scrubbed home.** Whether cf registers a project, finds the guide and builds phase 6 context with `HOME` redirected has not been checked. cf may also read something from the user's real config that the scrub removes.
- **Slice-case yield.** Older slices may predate task files at the fork, have merged the target into their branch, or lack `uv.lock` at the fork. The qualified count may be small.

### Mitigation Strategies

- The D9 spike runs first, and a no stops the slice with a `BLOCKED:` line before anything is built on it.
- Every rejection is counted by reason in the yield rows, so the PM sees which rule costs the most cases. `multiple_landings` and `branch_contains_merges` are the candidates to relax if they dominate.

## Implementation Notes

### Development Approach

1. **cf spike.** In a 421 scrubbed sandbox at a squadron fork commit, register with cf under the scrubbed home and run `sq run P6 <index> --producer-only --dry-run`. Record the answer in the DEVLOG.
2. Extract `CfRegistration` and `judge_pair`, and make `start_point.py`'s patterns public, with 177's tests passing.
3. Records, enums and store methods.
4. `slice_discovery`, `slice_task` and the no-code check against fixture repositories, then `slice_qualify` and `slice_case_build` with injected doubles. Then a live build on squadron.
5. `SliceCaseRunner`, `with_tools` and re-qualification routing. Live replay of one case (walkthrough step 3).
6. `normalize` with the real-slice fixture.
7. `diff_judge` and `diff_judge_runner`: pairing, forfeits, over-size, bound, cap, resume.
8. Report grouping and the pairwise section, the yield rows, the CLI and the slash command. Run walkthrough steps 1–8 on squadron.

Effort: 3/5.

### Special Considerations

- The producer sees the guide and instruction files as of the fork, and the current installed cf and squadron. That matches 424's split: the pipeline under test is today's, the code under change is the start commit's. Prompt identity records cf and guide versions.
- The reference diff includes whatever the original slice's review loop fixed, while replays run with no review. This is why the reference is a reference line and is never ranked (architecture).
- Slice-case task text can run to tens of KB, and it is repeated in every judge prompt for the case. That is the main reason pair prompts reach the over-size limit, and the bound accounts for it through the observed per-call cost.
