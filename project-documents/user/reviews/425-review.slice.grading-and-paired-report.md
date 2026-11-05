---
docType: review
layer: project
reviewType: slice
slice: grading-and-paired-report
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/425-slice.grading-and-paired-report.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 350276
cachedTokens: 247002
cacheWriteTokens: 103266
completionTokens: 8946
durationSeconds: 73.9
costUsd: 0.557533
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Grader identity embeds a per-case environment digest but is used as one benchmark-level key"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md#D10 — Grader identity and record ids"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure modes of the new I/O paths are only partly enumerated"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md#D16 — Absence classes in grading"
  - id: F003
    severity: concern
    category: architectural-alignment
    summary: "Grading spend leaves the run-level cap the architecture describes"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md#D9 — Caps, bound and resume for grading"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Parts of the design can be cut or deferred"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md#D8 — Reference grade, baseline and review noise floor"
  - id: F005
    severity: note
    category: architectural-alignment
    summary: "Grading rebuilds a fresh sandbox rather than reusing \"the same sandbox\""
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md#D1 — The grade order inside one sandbox"
  - id: F006
    severity: pass
    category: architectural-alignment
    summary: "Layering, dependency direction and integration points"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md#Architecture"
---

# Review: slice — slice 425

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Grader identity embeds a per-case environment digest but is used as one benchmark-level key

`GraderIdentity` contains `environment_digest` (the start environment digest, line 237). Each case has its own start commit, lockfile and `EnvironmentIdentity`. 422 keys qualification on a per-case parent environment, so the digest differs between cases. Several places then treat the identity as one value for the whole benchmark:
- The plan step "references to grade = cases with no ReferenceGrade under this grader identity" (Data Flow) runs before any sandbox is built. The digest isn't known at that point.
- D13 says the report reads "one grader identity at a time" and takes `--grader DIGEST`. The sample report header shows one digest.
- `SampleSizeEstimate.grader_digest` is a single value per benchmark.

Taken literally, a 10-case benchmark yields 10 distinct digests, and "latest identity" would select one case.

The doc needs to say how the identity splits into a per-case part (environment digest) and a benchmark-level part (`grader_version`, reviewer, floor runs). It also needs to say where the planner gets the environment digest before building sandboxes, for example from the case's qualification record. Without that, the architecture's "a report compares only results that match, and flags the rest" can't be met.

### [CONCERN] Failure modes of the new I/O paths are only partly enumerated

The slice adds I/O paths for review calls, `uv sync`, snapshot tooling, `git show` and `git apply`. D16 covers suite timeouts, suite errors and reinstall failure. The gaps that leave a requirement unmet:
- **Review call hang or timeout.** D7 handles a raise or an `UNKNOWN` verdict and sets no timeout. Per the failure-mode criterion, a hung review stalls the whole grade run, and the run-level cap is only checked between reviews.
- **Partial reference floor.** The reference runs `review_floor_runs` reviews. The doc doesn't say what happens if run 2 of 3 fails, or if the cap is hit between floor runs. Options are no record, a floor from fewer runs, or `review_failed`. A floor built from fewer runs would feed `is_within_floor` silently.
- **Unpriced review cost.** D9 refuses to start without a per-review figure. It doesn't say how a review returning `cost_usd=None` counts toward the cap check. If it counts as zero, the cap is silently undercounted.
- **Snapshot or tool crash or timeout.** D12 covers a tool mismatch and an absent measurement. It doesn't cover `measure_snapshot` raising or hanging.
- **Missing reference commit.** `TreeReader` and injection read the reference with `git show` in the user's checkout. A missing or garbage-collected `reference_sha`, or a failed `git diff` for the reference subject, has no `GradeAbsence`.
- **Process kill mid-grade.** 424 detects orphaned sandboxes. This slice only says sandboxes are removed after each grade. It names no handling for an interrupted grade or a stale `.grade.lock`.

Each needs an explicit class (harness unless the config caused it), an observable signal, and a test. D16 currently says every absence is produced by a test double, but its table lacks these rows.

### [CONCERN] Grading spend leaves the run-level cap the architecture describes

The architecture's goal is "Spend is visible before it happens … a run states its upper bound … which covers grading and judging as well as the replays." Its Cost section says the run-level cap "covers all of it." 424 (line 258) also says "425 extends the bound with grading costs."

D9 makes grading a separate command with its own cap. Integration Points then calls 424's statement "met by `grade`'s own bound." That is a departure from the architecture and from 424's contract, not a way of meeting them. Two caps now bound one benchmark, and no step states the whole-benchmark total.

The separate command has real reasons: regrading under a new reviewer, and separate lock scopes. Keep it, but do one of these:
- Record the departure as an explicit amendment to the architecture goal.
- Have `sq benchmark run` print a grading-cost estimate line beside its replay bound, so the whole-benchmark figure is visible before any spend.

### [CONCERN] Parts of the design can be cut or deferred

Specific cuts:
- **Per-severity review floors.** `review_floor_by_severity` is computed and stored on `ReferenceGrade`. The report's pair comparison (D13 §4) uses "difference in mean findings … beyond the case's floor", which is the total only. Nothing reads the per-severity floors, so drop them until a report consumes them.
- **Multiple grader identities in one report.** The `--grader DIGEST` selector, the "latest identity" rule and the list of the others are cut-able once the identity issue above is settled. A single grader identity per report is enough for the first run.
- **Per-case review floor from 3 runs on every case.** Floor runs multiply review spend by 3 on all references, and the walkthrough runs on five cases. The doc should justify why a per-case floor is needed rather than a single pooled floor. If it stays, the 3 × figure should be the first thing the bound shows.
- **`snapshots` and `nodes` sidecar kinds and the `ContentSidecars` generalization.** This is needed here. Keep it to what 425 uses and drop "ContentSidecars for normalized judge diffs" from the 426 provides list, since the `diffs` kind already exists.

None of these changes the plan-assigned scope. The plan's items are all present, and the 4/5 effort estimate is plausible. Trimming them lowers the surface area that touches 320, 400 and 422.

### [NOTE] Grading rebuilds a fresh sandbox rather than reusing "the same sandbox"

The architecture and slice plan say the grader runs "in the same sandbox." D1 rebuilds from `start_sha` plus the stored diff and adds an environment-digest equality check (`environment_changed`). 424 line 401 states the same rebuild, so the two slices agree, and the digest check keeps the property that matters (replay and grade share an environment). No action is needed beyond keeping the wording consistent with the architecture.

### [PASS] Layering, dependency direction and integration points

- `paired_stats` is pure.
- `grade_runner` reaches language details only through the `GradingAdapter` registry.
- The reviewer is reached only through `grade_review`.
- Metrology owns the record types, and `benchmark/` consumes them.
- The seams to 426 and 427 are concrete: `grade_one` with an empty hidden set, and the single `review_flag` function.
- The measured-variance estimate replaces 422's analytic bound as the architecture requires.
- The doc restates the tool-config restoration, edit counting, and absence-class rules from the architecture without contradicting them. It has a sound basis for no composite score, for pass fractions reduced per case, and for paired bootstrap over cases.

### Run Digest

- Response length: 8185 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 350276 / 247002 / 103266 / 8946 / not computed
- Duration: 73.9 s
- Cost: $0.56 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Responses

- **F001 (fixed):** `GraderIdentity` now holds only benchmark-level fields (grader version, reviewer, floor runs). Each grade record stores its own `environment_digest`, tied to the replay's by D1's check, and the planner reads the digest from the case's replay records; the reference record id includes it.
- **F002 (fixed):** Review calls run under `benchmark.review_timeout_s` and a timeout is `review_failed`; any failed floor run fails the reference, and a cap hit between floor runs writes no record. Unpriced reviews count at the per-review figure; `snapshot_failed` and `reference_unreadable` are added to D16; a killed grade writes no record and the lock and orphan sweep follow 424.
- **F003 (fixed):** D9 now states this as a departure: total spend is the run cap plus each grade cap. The architecture's cost section and 424's "425 extends the bound" sentence need the matching amendment, which is outside this doc.
- **F004 (fixed in part):** Dropped per-severity floors, `--grader` and multi-identity selection, and the 426 `ContentSidecars` item. Declined pooling the floor: review noise scales with the diff, so a pooled floor misjudges small and large cases, and the bound already shows references × floor runs first.
- **F005 (noted):** D1 already states the rebuild and the digest check, in agreement with 424. No change.
