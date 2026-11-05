---
docType: review
layer: project
reviewType: arch
slice: model-benchmark
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/420-arch.model-benchmark.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 27ee4968f01e6d04a7b1d5db5912e9c565f41bba
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
turns: 14
promptTokens: 548568
cachedTokens: 472998
cacheWriteTokens: 75554
completionTokens: 10649
durationSeconds: 125.9
costUsd: 0.912845
costBasis: provider
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: feasibility
    summary: "The grade can be gamed: the producer can edit the suite the grader runs"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:48"
  - id: F002
    severity: concern
    category: completeness
    summary: "Old tests that the original fix rewrote will count as regressions against a correct replay"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:52-57"
  - id: F003
    severity: concern
    category: feasibility
    summary: "Rule 1 (\"fails on an assertion\") excludes crash fixes"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:53"
  - id: F004
    severity: concern
    category: consistency
    summary: "The `implement` step has its own reviewer, so stopping after it does not remove the reviewer"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:89"
  - id: F005
    severity: concern
    category: completeness
    summary: "The answer can still reach the producer: the sandbox does not hide the answer"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:46"
  - id: F006
    severity: concern
    category: consistency
    summary: "The reference diff is not comparable to replay diffs in pairwise judging"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:91"
  - id: F007
    severity: concern
    category: feasibility
    summary: "\"Spread overlaps\" ignores the pairing that the design itself relies on"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:91"
  - id: F008
    severity: concern
    category: completeness
    summary: "The spend bound is in dispatches, not dollars, and grading and judging are outside any cap"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:115"
  - id: F009
    severity: concern
    category: consistency
    summary: "Qualification goes stale when the environment changes"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:107"
  - id: F010
    severity: concern
    category: feasibility
    summary: "Inline diffs in coarse records will make the store slow to query"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:123"
  - id: F011
    severity: concern
    category: antipattern
    summary: "Too much scope: a new production pipeline and reviewer recall are built alongside the benchmark"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#anticipated-slices"
  - id: F012
    severity: note
    category: dependencies
    summary: "The grading reviewer is used before anything shows it can find defects"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:132-134"
  - id: F013
    severity: note
    category: consistency
    summary: "The first slice is named differently in two places"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:99"
---

# Review: arch — initiative 420

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] The grade can be gamed: the producer can edit the suite the grader runs

The principle "The grader is not the producer" says the grader "reads only the resulting tree" and runs "the full suite, lint and type checks" there (line 89). That tree contains the producer's edits to existing tests, to lint config (`ruff` ignores, `# noqa`) and to pyright settings or `# type: ignore`. If the producer deletes, skips or loosens a failing test, the grader counts zero regressions. Implementation agents are known to do exactly this. The hidden test is protected because it is applied from outside, but the regression signal, the check deltas and every slice-case grade (line 105, where there is no hidden test at all) are not. The design needs to pin the grading inputs: run the start commit's test files and tool config on top of the producer's source, or record every edit to test and config files as its own reported signal. Without one of these, "objective before opinion" does not hold for slice cases.

### [CONCERN] Old tests that the original fix rewrote will count as regressions against a correct replay

Fix commits often change existing tests, because the old expected behavior was the bug. Qualification (line 50) checks that "the original work passes its own grade", and it does, because the original tree carries those updated tests. A replay tree starts from the parent's suite. A correct fix fails the old assertions unless the producer happens to change the same tests, and then it scores a regression. The rule is lopsided: it favors producers who rewrite tests, which is the gaming path in the finding above.

The doc also never says what the "hidden test" is when the fix commit:
- edits an existing test file rather than adding one;
- adds fixtures to a `conftest.py`;
- writes to a path where the producer has already written its own test. The `fix` pipeline writes a failing test first (line 87), and naming conventions make the same path likely, so the overlay needs a defined rule for clashes.

The case record needs an explicit hidden-test set, a list of superseded tests to leave out of the regression count, and an overlay rule.

### [CONCERN] Rule 1 ("fails on an assertion") excludes crash fixes

The rule only tells assertion failures apart from collection and import errors. Many fixes are for crashes. At the parent, the test fails because project code raises (`TypeError`, `KeyError`, or a CLI exit with a traceback), not because an assertion fails. Those tests are legitimate test-first tests that use no names the fix added. The test that matters is whether the failure comes from a missing or renamed project symbol (`ImportError`, `AttributeError` on a project module, a patch target that is not found). Tightening the rule this way recovers cases from a yield the doc already expects to be "a minority" (line 79).

### [CONCERN] The `implement` step has its own reviewer, so stopping after it does not remove the reviewer

The Envisioned State says the replay runs "the `implement` step from `P6`" and leaves the review loop out "because it mixes the reviewer into the producer's result". In `src/squadron/data/pipelines/P6.yaml:16-21` and `implement.yaml:15-20`, the `implement` step itself carries `review: { template: code, model: "{review-model}" }`. `PhaseStepType.expand` (`src/squadron/pipeline/steps/phase.py:282-308`) adds a review action and a checkpoint before the commit, and the commit records that review's verdict.

So a replay of "just the producer step" still sends a review to whatever `review-model` defaults to: `deepseek4-flash` in P6, `minimax` in `implement`. The two pipelines differ, so the doc's "P6 and implement" are not one producer. That review adds cost, adds a dispatch that is not in the stated bound, and leaves a pipeline default in the config identity.

The doc defers how a replay selects the producer step (line 111). That deferral cannot be resolved without deciding whether the step's embedded review is stripped. Stripping it means the replay no longer runs "the same step definition". The architecture should make that decision, and should name which pipeline's step is canonical.

### [CONCERN] The answer can still reach the producer: the sandbox does not hide the answer

"The answer never reaches the producer" is stated as absolute. The only mechanism behind it is a single-commit directory, and Current State (line 80) says that directory is "not an OS jail". From inside it, the producer, with bash or Claude Code's tools, can reach:
- the user's real checkout with full history, including the fix commit;
- `~/.config/squadron/`, where the metrology store holds earlier replay records with other samples' diffs and the reference;
- `gh issue view` with live comments that link the fix;
- the user's Claude Code memory and settings.

The Containment section (lines 109, 144) treats this only as a safety question and defers it to #213. Leakage is a question of whether the results are valid, and this component owns that. At minimum, the design needs a way to detect leaks: scan the producer transcript for reads outside the sandbox and for `git`/`gh` calls against other repos, and mark those runs instead of grading them. It should also run with a scrubbed `HOME` or config directory, and with `gh` credentials removed from the environment.

### [CONCERN] The reference diff is not comparable to replay diffs in pairwise judging

The judge uses "the reference diff as a contestant". Replays stop "at the producer's committed tree", with no close-out, review loop, DEVLOG or merge (line 89). A slice's reference (fork to landing commit, from 403's slice ranges) contains all of those:
- fixes from the review loop;
- task-file check-offs;
- DEVLOG and CHANGELOG entries;
- review files.

So the reference is the producer plus the review loop, judged against bare producers. For fix cases, the reference diff includes the hidden test, which replay diffs never contain. The design needs a rule for normalizing diffs: which paths to drop (DEVLOG, task files, review artifacts, CHANGELOG) and whether the hidden test is shown. Otherwise the reference's Bradley-Terry strength mostly measures these artifacts.

### [CONCERN] "Spread overlaps" ignores the pairing that the design itself relies on

The first design goal makes "the case, not the config, the unit of difficulty". That makes this a paired design: every config runs on the same cases. But the report rule is "a config whose sample spread overlaps another's is shown as not distinguishable". That compares marginal spreads and throws away the pairing.

Case difficulty varies far more than config quality does, so marginal spreads will almost always overlap, and the report will almost never separate two configs. Also, 320's noise floor is a per-category spread of audit scores. It does not carry over to pass/fail outcomes at small n.

The statistic should be a paired per-case difference, for example a paired bootstrap or sign test over cases, with its interval. It should be named in the architecture, because it decides how many samples, and so how much money, a benchmark needs.

### [CONCERN] The spend bound is in dispatches, not dollars, and grading and judging are outside any cap

Design Goals (line 42) promise that "spend is visible before it happens". The mechanism is a bound "on dispatches" plus the 947 cap on each run. An implementation dispatch with tool turns has no fixed cost, so a dispatch count says nothing about dollars. The real upper bound is cases × configs × samples × `max_cost_usd`, plus grading reviews and judge calls, which grow with the square of contestants. The grading reviews and judge calls happen outside any pipeline run, so no cap covers them.

The benchmark needs a cap of its own across the whole run, a stated dollar bound before any dispatch, and a defined behavior when the cap is hit partway through: which records are written, and how the partial set is reported.

### [CONCERN] Qualification goes stale when the environment changes

Environment identity (lockfile hash, tool versions) is part of the grader identity. The doc also says that qualification at the reference commit only catches environment-sensitive tests "if it runs in the same environment the replays use". But qualification happens once, at case creation (line 85), and the case id is built from start commit, task text, hidden test and grader commands (line 61), with no environment in it. A later replay under a newer Python, `uv`, `ruff` or `pyright` can fail at the reference without anyone knowing.

The qualification record should be keyed to the environment identity. A benchmark run should re-qualify a case, or refuse it, when the environment differs.

### [CONCERN] Inline diffs in coarse records will make the store slow to query

Line 63 says the store "reads every file on every query". Each implementation record holds a full diff plus normalized review findings, for every case × config × sample. A modest slice-case benchmark (20 cases × 4 configs × 5 samples, diffs in the hundreds of KB) means tens of MB parsed on every `sq stats` or report call, including queries that have nothing to do with the benchmark.

Deferring sidecar files "if list cost becomes visible" means moving the record format later, after records already exist. Storing diffs as content-addressed sidecar files from the first replay slice is about as cheap as inlining them, and avoids that migration.

### [CONCERN] Too much scope: a new production pipeline and reviewer recall are built alongside the benchmark

The core value is implementation replay graded objectively. Three parts can be cut or moved out:
- **Reviewer recall** (line 93, line 134). Its two central decisions, who writes the defects and how findings are matched to them, are left open (line 121). It shares none of the replay or grader machinery beyond the store. It should be its own initiative, or be deferred until implementation results exist.
- **`sq run fix`** (line 87). This is a new production pipeline. Its only production justification is "useful on its own", while fixes are actually done interactively (line 78). A benchmark of this pipeline measures a prompt with no production history, which runs against the doc's own principle that replays measure what real runs use (line 59). Either justify the pipeline independently, as a 900 or feature item, or replay fix cases with the `implement` step and the issue text as the task.
- **Pairwise judging for fix cases.** The hidden test already gives an objective grade. Pairwise judging should be limited to slice cases, where it is the only quality signal beyond regressions.

### [NOTE] The grading reviewer is used before anything shows it can find defects

The replay-and-grading slice uses "a fixed code-review config" as a scoring signal. Reviewer recall, which would show whether that config finds anything, comes last. Until then, review-finding counts in implementation reports come from an unmeasured instrument. Reports should flag that until recall data exists for the grading config.

### [NOTE] The first slice is named differently in two places

Technical Considerations says "the first slice therefore ends at a yield report". Anticipated Slices lists the effort audit first and calls fix cases the keystone. Use one name for it so the slice plan does not pick up both.

## Responses

- **F001 (fixed):** The grader runs the start commit's suite and tool config against the producer's source. The producer's new tests run as a separate signal. Edits to existing tests or config, and added `# noqa` and `# type: ignore`, are counted and reported.
- **F002 (fixed):** New principle: each case lists its hidden test set (tests the fix added or changed, `conftest.py` fixtures included) and its superseded test set (existing tests the reference changed or deleted). Superseded tests don't count as regressions. The hidden set is laid over the producer's tree at its original paths and wins any clash, and the clash is recorded. Both sets are part of the case id.
- **F003 (fixed):** Rule 1 now rejects only failures from a missing or renamed project symbol. An exception raised by project code qualifies.
- **F004 (fixed):** A replay runs the `implement` step with its own review removed: same prompt, dispatch and commit, but no review and no verdict. `P6` is canonical. `implement.yaml` has the same step with a different review model, which removing the review makes irrelevant.
- **F005 (fixed):** Rewrote the principle. The producer runs with no GitHub credentials, and with squadron's and the agent's config directories pointed away from the user's. The transcript is scanned for reads outside the sandbox and for `git`/`gh` calls against other repos. A run that trips the scan is recorded as leaked and not graded. Leak detection belongs to this initiative, and #213 keeps OS-level safety. Whether auth still works with the redirected config is checked in the replay slice.
- **F006 (fixed):** Before judging, DEVLOG, CHANGELOG, task files, review files and slice docs are dropped from every diff. The reference is reported as a reference line, not ranked as a config. Fix cases aren't judged pairwise (see F011), so the hidden test never reaches the judge.
- **F007 (fixed):** Configs are compared on paired per-case differences with a paired bootstrap interval over cases, and an interval that spans zero means the two can't be told apart. 320's noise floor now applies only to the LLM signals.
- **F008 (fixed):** Before any dispatch, the run states a bound in dollars: cases × configs × samples × `max_cost_usd`, plus estimates for grading and judging. The run has its own cap covering all of that. When the cap is hit, the run stops, keeps every record already written, is marked partial, and reports only cases that finished under every config.
- **F009 (fixed):** The qualification record names the environment it ran in. If a later run's environment differs, the case is qualified again, or dropped with a reason.
- **F010 (fixed):** Diffs are stored in separate files named by content hash from the first replay record. Findings stay inline.
- **F011 (partly fixed):**
  - Pairwise judging is now for slice cases only (fixed).
  - Reviewer recall stays. It is capability (f) of initiative plan entry 15, it comes last, and it is independent of the other slices.
  - `sq run fix` stays. The PM approved it. Replaying fix cases through the `implement` step isn't possible: that step needs a slice with a design and a task file (`set_slice`, plus the `check_decisions` gate for #240), and a fix has neither.
- **F012 (fixed):** New consideration: until recall data exists for the grading reviewer config, reports mark the review-finding columns as coming from an unmeasured reviewer.
- **F013 (fixed):** "The first slice" is now "the fix-cases slice", matching Anticipated Slices.

### Run Digest

- Response length: 12806 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 548568 / 472998 / 75554 / 10649 / not computed
- Duration: 125.9 s
- Cost: $0.91 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
