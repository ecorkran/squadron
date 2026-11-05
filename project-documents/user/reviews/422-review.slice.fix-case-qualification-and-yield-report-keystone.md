---
docType: review
layer: project
reviewType: slice
slice: fix-case-qualification-and-yield-report-keystone
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
effort: high
turns: 8
promptTokens: 567309
cachedTokens: 452900
cacheWriteTokens: 114397
completionTokens: 9935
durationSeconds: 82.5
costUsd: 0.653151
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: concern
    category: internal-consistency
    summary: "Reuse check needs the parent environment digest, so \"no sandbox on rebuild\" cannot hold"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#Data Flow (steps 4, D10) and #Success Criteria"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "Reference qualification runs in a different environment from the one replays are graded in"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#D10, #Data Flow step 4"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "The reference is never checked against lint and typecheck grader commands"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#D11"
  - id: F004
    severity: concern
    category: under-specification
    summary: "Commits that close several issues are not specified"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#D1, #Database / Storage Schema, #Verification Walkthrough step 1"
  - id: F005
    severity: concern
    category: integration
    summary: "How a `FixCaseAdapter` is selected is undefined"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#Patterns and Conventions, #D13, #API Contracts"
  - id: F006
    severity: concern
    category: requirements-coverage
    summary: "The \"separable\" verdict is optimistic by the slice's own account, yet it decides initiative order"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#D12"
  - id: F007
    severity: note
    category: under-specification
    summary: "Rejection vocabulary is scattered across decisions"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#D1, #D3, #D5, #D6, #D8, #D13"
  - id: F008
    severity: note
    category: performance
    summary: "Qualification runtime has no stated bound"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#Risk Assessment"
  - id: F009
    severity: pass
    category: architecture-alignment
    summary: "Scope and layering match the architecture and slice plan"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md#Technical Scope"
---

# Review: slice — slice 422

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Reuse check needs the parent environment digest, so "no sandbox on rebuild" cannot hold

D10 keys a qualification record on the parent `EnvironmentIdentity` digest. Under 421 D6 that digest includes `interpreter_version`, read from `.venv/bin/python --version`. The digest therefore exists only after the install has run.

Data Flow step 4 builds both sandboxes and then checks for a reusable record. The Success Criteria and Walkthrough step 4 require that a second `build` "dispatches no sandbox for reused candidates" and finishes "without building sandboxes". As designed, those two cannot both be true.

Rewrite the reuse lookup so a cheap probe can decide it before any install. One option is to match on `(project_id, commit, rule_version)` plus the digest components that can be computed without an install: lockfile hash, scrub spec, platform. Only the full digest would then require a sandbox. Alternatively, drop the no-sandbox criterion and accept an install per candidate on rebuild. The cost matters, because squadron alone has about 50 candidates.

### [CONCERN] Reference qualification runs in a different environment from the one replays are graded in

The architecture says qualification at the reference "only [works] if it runs in the same environment the replays use". It also says a case enters the set only if the original work passes its own grade in the sandbox environment. The slice builds a second sandbox at the reference, resolved from the reference's own lockfile. D10 records the reference environment but leaves it out of the key, and says "the grade runs in the start environment".

If a fix changed `uv.lock` or its dependencies, then `fails_at_reference` and the repeat/exclusion runs are measured in an environment no replay will see. A case can qualify while the reference code cannot pass in the start environment. The slice has no rule for when the parent and reference digests differ.

This design also costs two installs per candidate. Qualify the reference code inside the parent-environment sandbox instead, by applying the reference's tree files over it. That matches the grading environment, removes the second sandbox, and makes a dependency-changing fix fail visibly. If the two-sandbox design stays, add a rule for digest mismatch, such as rejecting with a named reason.

### [CONCERN] The reference is never checked against lint and typecheck grader commands

The architecture's principle is "A case enters the set only if the original work passes its own grade". The grade includes lint and type checks. D11 records the `lint` and `typecheck` grader commands in the case but says "This slice does not run lint or typecheck." A case whose reference fails `ruff` or `pyright` under the start commit's tool config therefore qualifies here. 425 would only find the failure at its "reference fix graded like a replay passes" check, after cases are in a set and 424 may have replayed them.

Run the recorded grader commands once at the reference during qualification, and reject with a named reason on failure. This is one run per surviving candidate, after the suite repeats. If it is deliberately deferred, say so and name the 425 behavior that drops such cases, so the yield report does not overstate qualified count.

### [CONCERN] Commits that close several issues are not specified

D1 matches `closing keyword + #n` and the record id is keyed by commit. `FixQualification.issue_ref` is a single `str | None`, and `task_text` is built from one issue. The Walkthrough allows "commits that close several issues, which can be checked with `fix-cases show`". But the record cannot hold more than one, and no rejection reason covers it. The criterion "records equal closing commits" has no defined behavior for this case.

Choose one: a `multiple_issues_closed` rejection, which is the lightest option and consistent with `multiple_closing_commits`, or define the task text as the concatenation. Also say what happens when a commit names the same issue twice.

### [CONCERN] How a `FixCaseAdapter` is selected is undefined

`FixCaseAdapter` is a separate protocol with no `claims` method. It is registered "by `SourceLanguage` in `benchmark/registry.py`". D13 says the adapter "comes from 421's `claims`", and also that when no adapter claims a repo, each candidate is rejected with `no_fix_case_adapter`.

421 makes `default_registry()` the only importer of concrete adapters and has `BenchmarkAdapter.claims` pick the language. The slice does not state the chain: `BenchmarkAdapter.claims` → `SourceLanguage` → fix-case registry lookup. It also does not say who runs that lookup, or what a language with a `BenchmarkAdapter` but no `FixCaseAdapter` produces. That last case is the exact one `no_fix_case_adapter` exists for. Specify the lookup in one sentence. Also state that `PythonFixCaseAdapter` reaches `run_suite` through the registry rather than importing `PythonBenchmarkAdapter`, so the dependency direction holds.

### [CONCERN] The "separable" verdict is optimistic by the slice's own account, yet it decides initiative order

The architecture ties the yield answer to "the paired statistic", a bootstrap over per-case values. The slice uses an analytic bound that assumes a constant true difference across cases. It says that case-to-case variation in the true difference raises the real variance. So MDD is a lower bound: "not separable" is reliable, but "separable" is not established.

The report prints a binary `separable | not separable`, and that verdict decides whether 423 → 424 → 425 stands. Label the positive result as necessary but not sufficient, for example "n is enough only if per-case differences are homogeneous". That is a wording change, with no added mechanism. Rewording to a necessary-condition check also keeps 425's measured bootstrap as the real answer.

### [NOTE] Rejection vocabulary is scattered across decisions

D1 calls its rejection set closed. The full `CandidateRejection` and `TestRejection` members appear in D1, D3, D5, D6, D8, D9 and D13. `boundary_undecidable` is used at both candidate and test level. `collection_failed` is a candidate reason, and `collection_error` is a `FailureKind`. List both enums once, with the level each member applies at. The report groups by these values, and the Success Criteria require every candidate to land in one.

### [NOTE] Qualification runtime has no stated bound

No LLM spend is involved, so the architecture's cost cap does not apply. But each surviving candidate runs the full suite `qualification_repeats` times plus installs, and the slice only names this as a risk. The timeouts come from 421's config keys. Consider stating an expected wall-time order of magnitude for squadron's roughly 50 candidates. That would let the Verification Walkthrough run be planned.

### [PASS] Scope and layering match the architecture and slice plan

The slice delivers what the plan assigns to 422:
- discovery and frozen issue text
- per-node hidden and superseded sets, including added `conftest.py` fixtures
- all three fairness checks with undecidable results excluded
- repeats feeding `excluded_tests`
- environment-keyed records and re-qualification
- the yield report

It defers injection, leak scan, replay and the bootstrap to 424 and 425. It keeps `benchmark/` depending on `metrology/` and `replay/`, not the reverse. It adds nothing beyond a deferred `pool` command and explicitly leaves that out. The failure paths (issue fetch, suite timeout, resolver crash) all record `harness_error` rather than blaming the case.

### Run Digest

- Response length: 9134 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 567309 / 452900 / 114397 / 9935 / not computed
- Duration: 82.5 s
- Cost: $0.65 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Responses

- **F001 (fixed):** Correct, the digest needs the install. Took the cut: the no-sandbox claim is dropped, and a rebuild now installs once per candidate but skips collection and every test run (D10, Success Criteria, Walkthrough step 4).
- **F002 (fixed):** Correct. The reference sandbox is gone: one parent sandbox switches between parent, reference and parent-plus-overlay file states (D4), so every check runs in the replay environment. A fix that changes the lockfile is rejected as `changes_lockfile`.
- **F003 (declined):** 425 reports lint and type checks as totals against the start-tree baseline, not as a pass condition, so a reference with lint or type errors does not fail its grade. D11 now says so.
- **F004 (fixed):** Added `multiple_issues_closed` to D1; the same issue named twice counts once. Walkthrough step 1 updated.
- **F005 (fixed):** D13 now states the chain: 421's registry `claims` gives the language, which selects the `FixCaseAdapter` in the same `registry.py`; `qualify` runs suites through the `BenchmarkAdapter`. Either lookup missing gives `no_fix_case_adapter`.
- **F006 (fixed):** The answer is now "enough cases | not enough", and the report says "enough" holds only if per-case differences are similar.
- **F007 (fixed):** Both enums are listed once under Patterns and Conventions with their level. Listing them exposed an unhandled environment-resolution failure, now `environment_unresolved`.
- **F008 (declined):** Wall time depends on each project's suite, and no measurement exists yet; a stated figure would be a guess.
- **Cross-slice (421):** 421 no longer creates `/sq:benchmark`; 422 now creates `commands/sq/benchmark.md` (Technical Scope, Component Structure).
- **Cross-slice (423):** The issue renderer takes an optional cutoff; with none it renders everything and skips the edited-after-fix check, for 423's live fetch (D2, `issue_freeze`).
