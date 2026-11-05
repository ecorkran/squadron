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
reviewedSha: 694f2e7e474c1fb5d3a596b22112917d464f806e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
turns: 11
promptTokens: 508122
cachedTokens: 422759
cacheWriteTokens: 85347
completionTokens: 9921
durationSeconds: 111.8
costUsd: 0.966581
costBasis: provider
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: feasibility
    summary: "Restoring tool config from the start commit also reverts the producer's dependency changes"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#architectural-principles"
  - id: F002
    severity: concern
    category: completeness
    summary: "No pipeline mechanism exists to run \"only the producer step, with its embedded review stripped\""
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#technical-considerations"
  - id: F003
    severity: concern
    category: completeness
    summary: "The global `sq` install and its site-packages give the producer the answer"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#architectural-principles"
  - id: F004
    severity: concern
    category: completeness
    summary: "How ungraded and failed runs enter paired comparisons is undefined, and excluding them biases results toward flaky configs"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#envisioned-state"
  - id: F005
    severity: concern
    category: feasibility
    summary: "Hidden-set application is file-level, but fixes add test functions to existing files"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#architectural-principles"
  - id: F006
    severity: concern
    category: feasibility
    summary: "The fix-case keystone is unlikely to have the statistical power the design depends on, and the fallback needs work the document doesn't schedule"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#technical-considerations"
  - id: F007
    severity: concern
    category: antipattern
    summary: "A new production `sq run fix` pipeline is built mainly so the benchmark has something to replay"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#envisioned-state"
  - id: F008
    severity: concern
    category: completeness
    summary: "The dollar bound is undefined when `pipeline.max_cost_usd` is unset, and the run-level cap can overshoot by one full pipeline"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#technical-considerations"
  - id: F009
    severity: concern
    category: completeness
    summary: "Sequential multi-hour runs have no resume semantics"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#non-goals"
  - id: F010
    severity: concern
    category: completeness
    summary: "Qualification runs once and does not detect flaky tests"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#architectural-principles"
  - id: F011
    severity: note
    category: consistency
    summary: "Redirecting the agent config directory changes the effective prompt versus production"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#technical-considerations"
  - id: F012
    severity: note
    category: other
    summary: "Grading uses review findings before the reviewer-recall slice measures that reviewer"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md#anticipated-slices"
---

# Review: arch — initiative 420

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Restoring tool config from the start commit also reverts the producer's dependency changes

The grader principle says "the regression suite and the tool config (lint and type-check settings) come from the start commit, not the producer's tree." In squadron, and in most uv/Python projects, the tool config is not its own file. `pyproject.toml` holds `dependencies` (line 21), `[project.scripts]` (line 48), `[tool.ruff]` (line 77) and `[tool.pyright]` (line 95) together. If the grader restores `pyproject.toml` from the start commit, it removes any dependency or entry point the producer added, and a correct slice that adds a library then fails on import. If it keeps the producer's `pyproject.toml`, the producer can loosen ruff or pyright settings, which the principle is meant to stop.

The environment has a related gap. The Envisioned State resolves the environment when the sandbox opens, before the producer runs. Nothing says whether the grader reinstalls when the producer changes the lockfile. If it does, environment identity becomes different for each run, which conflicts with "Environment identity ... is part of the grader identity." If it doesn't, the new imports fail. The document needs a rule that works on sections, not files: take the `[tool.*]` tables from the start commit and the dependency tables from the producer, then reinstall. It also needs to say how the grader identity records a lockfile the producer changed.

### [CONCERN] No pipeline mechanism exists to run "only the producer step, with its embedded review stripped"

"Stopping a production pipeline at the producer step" calls this a slice decision: either "a packaged replay pipeline built from the same step definition" or "a run mode that ends after it." The pipeline loader has neither feature. Pipelines are standalone YAML files with no step-reference, include or extends mechanism; `executor.py` has none. The `implement` step in `P6.yaml:16-21` carries `review: { template: code, model: "{review-model}" }` inline. To strip that review without copying the step, the executor needs a new capability: either step overrides when a step is referenced from another pipeline, or a run-time flag that disables a step's embedded review and stops after step N. That work changes the executor and the pipeline schema. Every replay depends on it, so it is an architecture decision, not a slice detail. The "no drift" principle cannot hold until it is decided. Name the mechanism here and put it in the Implementation replay slice.

### [CONCERN] The global `sq` install and its site-packages give the producer the answer

The leak model covers GitHub credentials, squadron and agent config directories, reads outside the sandbox, and `git`/`gh` calls. When the project being benchmarked is squadron itself, which is the first planned case set, the producer's shell has `sq` on `PATH`. That binary resolves to the user's current install, and its installed package source contains the later fix. A producer that runs `sq ...` to reproduce a bug, or reads the source through `python -c "import squadron; print(squadron.__file__)"`, gets the future code. Neither action is a `git`/`gh` call. The second only shows up as a read outside the sandbox if the scanner can parse paths out of arbitrary bash and Python. The uv cache and the real repo, at a known path, are also readable.

Detecting reads from the transcript only works for structured tool calls (SDK Read/Glob). It cannot see file access from inside scripts the model writes. The document should require three things: the sandbox venv's bin first on a `PATH` that excludes the user's tool installs, an explicit list of known leak paths, and a statement that transcript scanning is best effort for bash-tool providers. Without that, a "not leaked" record is a stronger claim than the evidence supports.

### [CONCERN] How ungraded and failed runs enter paired comparisons is undefined, and excluding them biases results toward flaky configs

"Absent is not zero" says a run with no grade "records why" and that reports "count these separately." Paired per-case differences need a value for every (case, config) cell. The document mixes failures caused by the config (the producer crashed, hit `max_cost_usd`, or committed nothing) with failures caused by the harness (the environment did not resolve, the grader timed out, a leak was detected). Leaving config-caused failures out of pass rate rewards configs that fail loudly. The cost section adds a separate rule: when the cap is hit, the run "reports only cases that completed under every config." Whether a leaked or ungraded sample counts as "completed" is never said. The document should split absences into those attributable to the config, which count as a fail, and those attributable to the harness, which drop the case from every config's pairing. It should also say how multiple samples are reduced to one value per case before the bootstrap.

### [CONCERN] Hidden-set application is file-level, but fixes add test functions to existing files

"The hidden set is applied over the producer's tree at its original paths and wins any clash." Fix commits usually add a test function to an existing `tests/test_x.py`. The reference's whole file then contains (a) the hidden test, (b) any changes that file received from the fix, and (c) none of the tests the producer, which the fix pipeline requires to write a failing test first, added to the same file. Overwriting the whole file silently deletes the producer's new tests. "Recorded as a clash" turns into the normal case, not an exception. It also deletes the signal "the producer's own new tests run as a separate signal." Hidden tests should be applied by node id: append or inject the hidden test functions and conftest fixtures, or put them in a separate file the grader owns. The superseded set needs node-level granularity for the same reason.

### [CONCERN] The fix-case keystone is unlikely to have the statistical power the design depends on, and the fallback needs work the document doesn't schedule

Current State counts 46 fix commits with tests, 23 with mocking and 37 with private-looking names. Add the test-first and packaging-boundary rules, and the "exclude when undecidable" stance on re-exports and dynamic imports, and a single-digit yield is plausible. With binary pass/fail on fewer than about 10 cases, a paired bootstrap interval will span zero for almost any pair of configs. The keystone would then prove the machinery but answer nothing. The stated fallback, "pooled from other cf projects' history," has costs the document leaves out:

- Other projects may not be Python, and only the Python adapter is planned.
- Records are keyed on `ProjectId`, so pooled reports need a cross-project query.
- Each project's environment resolution and qualification has to run.

Either put a minimum-case power target in the fix-cases slice's exit criteria, or move slice cases forward so the benchmark has a usable second source.

### [CONCERN] A new production `sq run fix` pipeline is built mainly so the benchmark has something to replay

Current State says "Fixes are done interactively, so there is no fix pipeline to replay." The design adds a production pipeline anyway, with its own slice, so that "Replays run the production pipelines" holds for fix cases. Nobody uses that pipeline today. Benchmarking it measures model × a new, unproven prompt, not the workflow that actually produces fixes, so the principle's purpose ("what is benchmarked is the prompt and step a real run uses") isn't met. It is also a scope addition that the initiative plan's entry 15 does not list. Options: keep fix cases but say plainly that they measure the new `fix` pipeline, not how fixes are made today; or drive fix cases through the existing `implement` step with the issue text as its task, and defer `sq run fix` until there is demand for it outside the benchmark.

### [CONCERN] The dollar bound is undefined when `pipeline.max_cost_usd` is unset, and the run-level cap can overshoot by one full pipeline

The pre-dispatch bound is "cases × configs × samples × `pipeline.max_cost_usd`." `config/keys.py:22` states "unset means no cap." With the key unset, the formula has no value, and the design goal "Spend is visible before it happens" fails silently. Per the project's no-silent-fallback rule, the benchmark should refuse to start without a per-run cap (its own setting or the global key) rather than invent one.

The run-level cap is also only checked between dispatches. A running P6 subprocess stops only at its own per-pipeline cap, so actual spend can exceed the run cap by up to one `max_cost_usd`. Grading reviews and judge calls need their own estimate inputs; "plus estimates" doesn't name where those come from.

### [CONCERN] Sequential multi-hour runs have no resume semantics

"No concurrent replays." Implementation replays plus install plus grading take tens of minutes each. A modest run of 20 cases × 3 configs × 3 samples is 180 runs, which is likely more than 50 hours of wall time. The document defines partial runs only for cap exhaustion. It doesn't say what happens after a crash, a sleeping laptop, or Ctrl-C: whether `sq` can continue a run by skipping (case, config, sample) tuples that already have records, how an orphaned sandbox is detected, and how a half-written run is marked. Because each record is coarse and written per case run, resuming is cheap to design now and expensive to retrofit. It belongs in the replay slice's scope.

### [CONCERN] Qualification runs once and does not detect flaky tests

Design Goals rely on "tests and tools that give the same answer every time." Qualification is described as a single pass of the reference's grade, plus the test-first check at the parent. A flaky test in the regression suite or the hidden set will then show up as config noise or a false regression, and the paired statistic will treat it as signal. Qualification should run the reference grade several times, plus the hidden test at the parent for test-first. Tests that disagree should go into a per-case exclusion list that is part of the case's content identity.

### [NOTE] Redirecting the agent config directory changes the effective prompt versus production

The scrubbed environment points the agent's config directory away from the user's, which drops user-level instructions such as `~/.claude/CLAUDE.md`. The sandbox also carries the project `CLAUDE.md` as it stood at the start commit, not the current one. That is reasonable, but it partly contradicts "same prompt, same dispatch" as production. Prompt identity should record the instruction files that were in effect. Whether auth survives the redirect is load-bearing for the whole SDK path. It's deferred to the replay slice, so a negative answer there would force a containment redesign late.

### [NOTE] Grading uses review findings before the reviewer-recall slice measures that reviewer

The document already flags review-finding columns as "unmeasured." Since Reviewer recall is the last slice, every report before it carries a column that nobody can interpret. Moving recall earlier, or leaving the grading review out until recall exists, would cut grading cost and remove that caveat. This is optional.

## Responses

- **F001 (fixed):** Tool config is restored by section, not by file: the `[tool.*]` tables (and a standalone `ruff.toml` or `pyrightconfig.json`) come from the start commit, and the dependency and entry-point tables come from the producer. If the producer changed dependencies, the grader reinstalls and the run records that it did. The grader identity still names the start environment.
- **F002 (fixed):** Confirmed: no pipeline can reference another's steps, and no run mode stops early. The doc now names the mechanism, a `sq run` producer-only mode that runs only the producer step without its embedded review, commits, and stops. It is in the replay slice.
- **F003 (fixed):** The producer's `PATH` puts the sandbox's environment first and leaves out the user's tool installs. Known leak paths are listed: the checkout, site-packages, the package manager's cache, the store. A clean run is recorded as "no leak detected", because scanning can't see file access inside scripts the model writes.
- **F004 (fixed):** A failure the config caused counts as a fail. A failure the harness caused drops the case from every config's comparison. Each config's samples on a case reduce to a pass fraction before the bootstrap.
- **F005 (fixed):** The hidden and superseded sets are lists of individual tests (node ids), not files. Hidden tests are injected without removing anything the producer wrote. On a name clash the hidden test is renamed and the clash is recorded.
- **F006 (fixed, in slice scope):** The yield report now says whether the qualified count can separate two configs. That answer decides between pooling cases across projects and moving slice cases ahead.
- **F007 (partly fixed):** One sentence added: fix-case results measure the new pipeline's prompt, not how fixes are made today, and the `implement` step can't stand in because it needs a slice. The rest is declined, as last round; the PM approved `sq run fix`.
- **F008 (fixed):** The benchmark refuses to start without both a per-pipeline cap and a run-level cap. Grading and judging estimates come from observed costs in the store. The stated bound includes the one-pipeline overshoot.
- **F009 (fixed, in slice scope):** Resume added to the replay slice: skip runs that already have records, detect orphaned sandboxes, mark interrupted runs.
- **F010 (fixed, in slice scope):** Qualification runs several times. Tests that disagree go on a per-case exclusion list that is part of the case's content identity.
- **F011 (fixed):** Prompt identity records the instruction files in effect. The auth check moved to the fix-cases slice, so a no shows up before replay is built.
- **F012 (declined):** Optional. Reports already flag the review-finding columns until recall exists.

### Run Digest

- Response length: 12801 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 508122 / 422759 / 85347 / 9921 / not computed
- Duration: 111.8 s
- Cost: $0.97 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
