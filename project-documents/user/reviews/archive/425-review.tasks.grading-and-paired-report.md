---
docType: review
layer: project
reviewType: tasks
slice: grading-and-paired-report
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/425-tasks.grading-and-paired-report.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 9afa9d2adffecdcef3a3a16d16b79495c8dd80ac
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: xhigh
turns: 9
promptTokens: 402843
cachedTokens: 243975
cacheWriteTokens: 158860
completionTokens: 74193
durationSeconds: 317.6
costUsd: 0.343971
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion has a task, and every GradeAbsence is asserted"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:476"
  - id: F002
    severity: pass
    category: process
    summary: "Test-with pattern, checkboxes and commit markers are sound"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:55"
  - id: F003
    severity: concern
    category: identity
    summary: "The reviewer's rules hash varies per case, but the identity is one value per benchmark"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:181"
  - id: F004
    severity: concern
    category: contract
    summary: "`inject_hidden` cannot compute the conftest import diff with the signature it names"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:163"
  - id: F005
    severity: concern
    category: correctness
    summary: "Task 34 can store an estimate with no pairs"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:272"
  - id: F006
    severity: concern
    category: process
    summary: "Design corrections wait until Task 45"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:263"
  - id: F007
    severity: concern
    category: commit-cadence
    summary: "Walkthrough fixes have no commit point and land in a mixed final commit"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:346"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Task 35's SIGKILL test goes beyond the criteria and repeats Task 34"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:277"
  - id: F009
    severity: concern
    category: granularity
    summary: "Tasks 8 and 36 each bundle several reviewable units"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:101"
  - id: F010
    severity: concern
    category: coverage
    summary: "No task builds the report extension point that 426 needs"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:282"
  - id: F011
    severity: concern
    category: test-coverage
    summary: "The regression skip rule has no test, while the hidden-side rule does"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:221"
  - id: F012
    severity: concern
    category: correctness
    summary: "The bootstrap seed can make reports irreproducible"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:246"
  - id: F013
    severity: note
    category: clarity
    summary: "`normalize_result_categories` returns nothing"
    location: "src/squadron/review/categories.py:57"
  - id: F014
    severity: note
    category: clarity
    summary: "Task 16's subprocess pytest is underspecified"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:164"
  - id: F015
    severity: note
    category: clarity
    summary: "Task 31's cases-needed formula and zero-variance case are unspecified"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:253"
  - id: F016
    severity: note
    category: clarity
    summary: "Reference planning assumes one environment digest per case"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:260"
  - id: F017
    severity: note
    category: clarity
    summary: "Task 13 contains review-history wording"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:144"
  - id: F018
    severity: note
    category: sequencing
    summary: "Task 5's gate and the frontmatter omit some upstream names"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:84"
  - id: F019
    severity: note
    category: docs-consistency
    summary: "A stale 424 sentence is outside Task 45's cleanup"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:398"
  - id: F020
    severity: note
    category: granularity
    summary: "Task 43 is too small for its own task"
    location: "project-documents/user/tasks/425-tasks.grading-and-paired-report.md:326"
---

# Review: tasks — slice 425

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion has a task, and every GradeAbsence is asserted

Each functional, technical and integration criterion maps to a task. Examples: edit counting in Tasks 13–15 and 27, reinstall in Tasks 13 and 24, clashes in Tasks 16–17, caps and resume in Tasks 32–34, the paired bootstrap in Task 30, the estimate in Tasks 31, 34 and 42, and `review_flag` in Task 36. All eleven D16 values are asserted with their class in Tasks 23–25 and 28. The D1 order matches Tasks 24–26, and walkthrough steps 1–7 are Task 44. The design restates no NFR that needs a load test. Task 45's plan to delete the design sentences that say the architecture and 424 need changes is correct: both already state a separate grading cap (420 architecture line 42; 424 slice line 258).

### [PASS] Test-with pattern, checkboxes and commit markers are sound

Every implementation task carries its tests. Each item and sub-item has a checkbox, and every `**Commit**:` line is plain text. Markers sit at working points. Several tasks (7, 14, 16, 22, 23, 25, 28, 33, 34, 36–38) share the next marker, which the rules allow. Task 44 is the exception (finding 5).

### [CONCERN] The reviewer's rules hash varies per case, but the identity is one value per benchmark

D7 reads the review's rules from the sandbox tree, which is the start commit's rules (design line 208). D10 makes `GraderIdentity`, which holds the `ReviewerRef` and its `rules_hash`, one value for the whole benchmark (line 240). The Data Flow resolves the reviewer once, before any sandbox exists (line 106). Start commits differ between cases, so their rules directories can differ too. Task 19 takes `rules_dir` without saying which tree, so the identity could record one tree's rules while the reviews read another's. Decide whether the rules are pinned to one commit for the benchmark or hashed per case and kept out of the benchmark-level identity. Then state the choice in Task 19 and in the design.

### [CONCERN] `inject_hidden` cannot compute the conftest import diff with the signature it names

Task 16 writes the reference's conftest imports "minus the start's", but the signature takes only `(tree, case, reference)`. The other adapter methods that need the start tree take `start: TreeReader`, so this one has no way to read the start's conftest. Add a `start: TreeReader` parameter to the protocol and to Task 16, and update the design's API at line 335 to match.

### [CONCERN] Task 34 can store an estimate with no pairs

Task 34 writes one estimate whenever there are two configs and k ≥ 2. D15 (design line 284) also requires at least `MIN_PAIRED_CASES` included cases, and Task 31 returns an empty tuple below that. As written, a three-case run stores a `SampleSizeEstimate` with no pairs, and `sq benchmark yield` would then show a "measured" line with nothing behind it. Gate the write on a non-empty result, and add a test at four cases.

### [CONCERN] Design corrections wait until Task 45

The task file's Context Summary lists gaps the design still contains. D13's row key (line 263) contradicts the 420 identity that the design's own Prerequisites cite (line 58). `measure_snapshot` lacks a `files` parameter (line 254). The `GradeResult` shapes in D2 and D10, the empty-selection rule and the review timeout default are also out of date. The tasks follow corrections the design does not state, for most of the branch, and 426 and 427 read this design. Correct the design now in one docs commit before Task 2, which matches the planning cadence, and remove the design edit from Task 45. Also add `tree_reader.py`, `grade_budget.py` and `grade_plan.py` to the design's component list, since the tasks create them.

### [CONCERN] Walkthrough fixes have no commit point and land in a mixed final commit

Task 44 has no `**Commit**:` marker, so defects found in the walkthrough wait for Task 45. They then go into one `feat: complete grading and paired report slice` commit, together with the full-suite fixes, the design rewrite and the DEVLOG. That mixes code, planning documents and fixes that were only tested together at the end. Give Task 44 a marker per fix group, using `fix:` or `feat:` as applicable, and make the design and DEVLOG update its own docs commit.

### [CONCERN] Task 35's SIGKILL test goes beyond the criteria and repeats Task 34

No criterion names SIGKILL. Task 34 already tests, with a double, that an interrupted grade writes no record and that the rerun grades it. A real-process kill adds subprocess timing and a dependence on the orphan sweep, for the same observable. Fold the sweep check into Task 34, or make the kill a manual step in Task 44. Drop the standalone task and its commit.

### [CONCERN] Tasks 8 and 36 each bundle several reviewable units

Task 8 reshapes `GradeResult` (`hidden_total`, `hidden_passed`, `hidden_failures`, the id-map sidecar, `ReviewSummary`), adds two caps and a validator over five lists and `detail`, adds four record models, wires `MetrologyRecord`, and carries a 16 KB size test. Task 36 holds several inclusion and grouping rules (row identity, the prompt split, grader-identity scoping, case inclusion, `review_flag`) and about ten test assertions. Split Task 8 into the result shape with caps and `passed`, and the record types with `MetrologyRecord` wiring. Split Task 36 into rows and identity, and case inclusion and counts. Each part keeps its own tests.

### [CONCERN] No task builds the report extension point that 426 needs

The design requires 426 to add its report table without editing `grade_runner.py` (Integration Requirements, design line 501), and says 426 adds a slice-case table beside the fix-case one (line 464). Tasks 36–38 define only fix-case sections, and no test checks that a second case kind can be added. Add a case-kind grouping or registration point to `bench_report`, with a test that a second kind's table renders beside the first.

### [CONCERN] The regression skip rule has no test, while the hidden-side rule does

D2 (design line 166) says `skipped` and `xfailed` are not regressions, yet a hidden `skipped` is not a pass. Task 26 implements the regression rule, but its test list omits it. Task 8's truth table covers only the hidden side. The asymmetry is easy to invert, so add a Task 26 test: skipped and xfailed regression ids count zero, and `not_run` counts as a regression.

### [CONCERN] The bootstrap seed can make reports irreproducible

D14 says the seed is derived from the benchmark id and the pair "so a report is reproducible" (design line 278). Task 30 says only "derived from". An implementer who uses Python's built-in `hash()` gets per-process salting, so the same report would change between runs. Specify a sha256 of the benchmark id and pair names, and add a test that pins the seed for one known pair.

### [NOTE] `normalize_result_categories` returns nothing

It is typed `-> None` and mutates `result`. Task 20 reads as if it returns the normalized result. Say that it mutates, and build the findings from the mutated result.

### [NOTE] Task 16's subprocess pytest is underspecified

"The tmp repo's start venv-free interpreter" does not say what runs pytest or from which directory. Name the interpreter (for example `sys.executable -m pytest`) and the working directory.

### [NOTE] Task 31's cases-needed formula and zero-variance case are unspecified

The task gives MDD(n, k) but not its inverse for cases needed, the rounding, or the value to return when σ²_b + σ²_w/k is zero. Identical samples reach that zero and would divide by zero. Specify the inversion, the ceiling, and the zero-variance value.

### [NOTE] Reference planning assumes one environment digest per case

Task 32 uses "the replays' environment digest", and design line 108 uses the same singular. If a case's replays disagree because the environment changed mid-run, neither says which digest the reference is graded under. Decide and state it.

### [NOTE] Task 13 contains review-history wording

"Rules the first pass left untested" refers to a review pass the implementer cannot see. Reword it as a plain test list.

### [NOTE] Task 5's gate and the frontmatter omit some upstream names

The gate checks names from 420, 300, 421, 422 and 424. It does not check 400's `CodeReviewFinding` or `resolve_files`, which Tasks 20 and 25 use, or 320's `FloorStat`, which Task 21 uses. The frontmatter lists 421, 422 and 424, while the design's Prerequisites also name 300, 320, 400 and 420. Add the missing names to both.

### [NOTE] A stale 424 sentence is outside Task 45's cleanup

It still says `bench_plan` arithmetic is "which 425 extends with grading terms". D9 gives grading its own bound. Add this line to Task 45's amendment list. Line 258 of the same file is already correct.

### [NOTE] Task 43 is too small for its own task

It edits one markdown file. Merge it into Task 41, which owns the same CLI surface, and drop one commit.

### Run Digest

- Response length: 11660 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 402843 / 243975 / 158860 / 74193 / not computed
- Duration: 317.6 s
- Cost: $0.34 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 20
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 20
- Finding-shaped matches — surviving validation: 20
