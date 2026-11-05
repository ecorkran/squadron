---
docType: review
layer: project
reviewType: slice
slice: slice-cases
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/426-slice.slice-cases.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: high
turns: 9
promptTokens: 488105
cachedTokens: 418617
cacheWriteTokens: 69476
completionTokens: 7659
durationSeconds: 63.5
costUsd: 0.443839
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "D8 and D17 depend on upstream states that the 424 and 425 designs already settle"
    location: "project-documents/user/slices/426-slice.slice-cases.md#d8--the-slice-case-runner-invokes-producer-only-p6"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The new I/O paths are only partly covered by failure-mode handling"
    location: "project-documents/user/slices/426-slice.slice-cases.md#d9--cf-registration-inside-the-scrubbed-home"
  - id: F003
    severity: concern
    category: proportionality
    summary: "The design is heavier than the slice plan entry needs"
    location: "project-documents/user/slices/426-slice.slice-cases.md#technical-scope"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "The reference is `tip_sha`, not the landing commit"
    location: "project-documents/user/slices/426-slice.slice-cases.md#d2--landing-and-reference-selection"
  - id: F005
    severity: note
    category: containment
    summary: "`with_tools((\"cf\",))` widens the containment boundary for slice-case producers"
    location: "project-documents/user/slices/426-slice.slice-cases.md#d9--cf-registration-inside-the-scrubbed-home"
  - id: F006
    severity: pass
    category: nfr
    summary: "Spend, cap and bound for judging match the architecture"
    location: "project-documents/user/slices/426-slice.slice-cases.md#d16--caps-bound-and-resume-for-judging"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Objective-first reporting, separate tables and the over-size rule follow the architecture"
    location: "project-documents/user/slices/426-slice.slice-cases.md#d17--report-tables-per-case-kind-and-the-pairwise-section"
---

# Review: slice — slice 426

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D8 and D17 depend on upstream states that the 424 and 425 designs already settle

D8 says 424's `replay_one` will call the runner's `requalify`, and adds "If 424 lands calling 422 directly, this slice moves that call into `FixCaseRunner.requalify`." The 424 design is already written. It calls `qualification_for` / `qualify_candidate` directly (424 lines 136 and 407), and its `CaseKindRunner` has no `requalify` method. So the "if" branch is the real case. This slice therefore changes 424's protocol, `FixCaseRunner` and the call site in `replay_one`. The claim that `bench_runner.py` "is still not edited" is unlikely to hold.

D17 has the same pattern for 425's `paired_stats`: "If 425 exposes only the pass-fraction form, this slice extracts that core." 425 describes a per-case pass-fraction reduction with a bootstrap, so the extraction is probably needed.

Conditional edits to unimplemented slices are hidden dependencies. Fix this in one of two ways:
- Amend 424 and 425 so they expose `CaseKindRunner.requalify` and a difference-vector interval. Then 426 only consumes them.
- State in 426 that it edits those files, and list them under Integration Points.

### [CONCERN] The new I/O paths are only partly covered by failure-mode handling

The judge path is covered well: failed calls are left unrecorded and logged, the run cap is enforced, and `metrology.judge_timeout_s` bounds each call. Three new paths have no stated handling:
- **`CfRegistration.register` failing at replay time.** Its steps are `cf init`, `cf config set` and `cf set arch`. The doc does not say whether a failure or timeout is a harness absence that drops the case or a config failure charged to the producer. The two give opposite outcomes under "absent is not zero." Only the build-time spike is mentioned.
- **The reference diff read from `--repo` at judge or grade time.** The checkout may be missing `tip_sha`, for example after a gc or a different clone. The judge's "refuse: --repo missing" covers a missing path, not a missing commit. The case outcome and the observable signal are unspecified.
- **Git subprocesses in discovery and qualification.** `git ls-tree`, `rev-list` and `diff` can hang or fail. D6 covers sandbox and suite failures, not these.

Each path needs a named outcome, a WARNING+ log, and a test that asserts the signal.

### [CONCERN] The design is heavier than the slice plan entry needs

The plan entry asks for case building, a runner, normalization, an over-size rule, the judge and the report tables. The design adds the following, and none of it is needed to meet that entry:
- **`SliceCaseAdapter`** (D7) is a second protocol with one implementer, registered twice. A later slice-only language adapter is not a current need. Reuse `FixCaseAdapter` now and split it when a second language needs the narrower contract.
- **`slice-cases show`** and a matching `/sq:benchmark` mirror. `build` already prints a per-candidate line and `replay-show` exists. Defer `show`.
- **`--slice N`, `--case` and `--judge ALIAS` selection.** These are debug and convenience flags with no requirement behind them. Cut them unless the walkthrough needs them. Step 3 uses `--case` on `run`, which is 424's flag, not this slice's.
- **`DiffJudgment`** doubles as a case-level absence record. It has a mix of nullable pair fields plus `absence` and `absence_detail`, and nothing enforces which combinations are valid. A separate small `JudgeCaseAbsence` record is simpler, or the absence could be derived at report time.
- **Upstream edit footprint.** The slice touches 177 (`judging.py`, `ReplaySandbox`, `start_point.py`), 421 (`ScrubbedEnvironment`), 422 (yield report), 424 and 425. That footprint is large for effort 3/5. The first concern above reduces some of it.

None of the plan-assigned scope (build, normalization, over-size rule, reference line) is dropped.

### [NOTE] The reference is `tip_sha`, not the landing commit

The slice plan says "the landing commit is the reference". D2 uses `tip_sha`, because `fork..after` on a merge landing includes unrelated work that reached the target while the branch was open. The reasoning is sound and matches the architecture's intent that the reference be the slice's own work. Record this deviation in the plan or architecture text so the documents agree.

### [NOTE] `with_tools(("cf",))` widens the containment boundary for slice-case producers

The architecture's scrubbed `PATH` leaves out the user's tool installs. D9 adds `cf` for slice-case producers only. The design justifies this: fix-case producers and suite runs never get it, and the tool links are not part of the environment identity. The leak scan's known-path list, however, is not said to cover the `cf` install location or anything cf reads. 424 owns the scan, so check the list when implementing the spike.

### [PASS] Spend, cap and bound for judging match the architecture

The bound prints before any dispatch. It includes one call of overshoot, the cap is checked between calls, and records are kept at the cap with exit 2. Pair counts are limited to cross-config pairs plus reference pairs, which controls the quadratic growth the architecture warns about. Resume is a lookup by record id.

### [PASS] Objective-first reporting, separate tables and the over-size rule follow the architecture

- **Reporting:** slice cases get their own tables. The pairwise section never adjusts the objective grade, and there is no composite. The reference is a reference line, and the ranking verdict comes from the paired interval, not the strengths.
- **Over-size rule (D14):** it names a rule, excludes the whole case, counts it, and avoids truncation. This resolves the architecture's open "diffs above the judge's context" item and keeps the config case mix consistent.
- **Absence rules (D15):** they separate config absences (forfeit) from harness absences (drop the case), as the architecture requires.
- **Case boundaries:** no hidden set, and no slice tests used as hidden tests.

### Run Digest

- Response length: 7070 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 488105 / 418617 / 69476 / 7659 / not computed
- Duration: 63.5 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Responses

- **F001 (fixed):** Confirmed: 424 calls `qualification_for` / `qualify_candidate` directly and 425 bootstraps `d(c)` inside one function. D8 and D17 now state as decided that this slice adds `CaseKindRunner.requalify`, changes the call in `replay_one`, and extracts the difference-vector interval, and Integration Points lists the 424 and 425 files it edits.
- **F002 (fixed):** A failed cf step is now a harness absence logged at ERROR (D9), failed `git` calls in discovery and qualification are `harness_error` (D6), and a `tip_sha` missing from `--repo` makes `judge` refuse naming the case and sha. One success criterion covers a test for each signal.
- **F003 (fixed):** Cut `SliceCaseAdapter` (slice cases use 422's adapter), `slice-cases show`, `--slice`, `judge --case` and `report --judge`. `DiffJudgment` now holds only pairs; harness-absent cases are counted at report time and over-size cases get a small `OverSizeCase` record. Walkthrough step 3's `--case` is 424's existing `run` flag and stays.
- **F004 (noted):** D2 already records why the reference is `tip_sha`. The plan's wording ("the landing commit") belongs to the slice plan, which this response does not edit; flagged for the plan owner.
- **F005 (fixed):** The D9 spike now also checks that 424's leak-scan path list covers the cf install location and anything cf reads outside the scrubbed home.
