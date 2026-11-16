---
docType: review
layer: project
reviewType: slice
slice: real-bug-review-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/430-slice.real-bug-review-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 8d341b4a4714711b4b4cf73ee700e45f10ad2a8f
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 617726
cachedTokens: 487183
cacheWriteTokens: 130529
completionTokens: 77483
durationSeconds: 355.9
costUsd: 0.237123
costBasis: provider
runId: run-20261116-p4-de696884
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: identity
    summary: "Config identity includes the alias and the configured effort"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:244"
  - id: F002
    severity: concern
    category: records
    summary: "One record per reviewer per run, presented as the architecture's coarse-record rule"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:249"
  - id: F003
    severity: concern
    category: cost-bound
    summary: "The stated bound is an estimate, and plan-billed calls are uncapped"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:309-311"
  - id: F004
    severity: concern
    category: failure-modes
    summary: "Auth and environment failures are scored as configuration misses"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:292-301"
  - id: F005
    severity: concern
    category: timeouts
    summary: "Timeouts are under-specified, and the fetch timeout contradicts the sandbox it wraps"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:284"
  - id: F006
    severity: concern
    category: scoring
    summary: "Undecided comb decisions are scored as misses, which D3 forbids"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:296"
  - id: F007
    severity: concern
    category: failure-modes
    summary: "I/O paths without a failure-mode table: import, case loader, store writes"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:316-322"
  - id: F008
    severity: concern
    category: data-provenance
    summary: "Bug locations are curated ground truth, against the architecture's non-goal"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:161"
  - id: F009
    severity: concern
    category: architecture
    summary: "History-free sandbox: a deliberate departure from the architecture that needs its own decision"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:280-286"
  - id: F010
    severity: concern
    category: proportionality
    summary: "Proportionality: the design is heavier than its effort rating, and the live grader is the cut"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:252-257"
  - id: F011
    severity: concern
    category: scope
    summary: "The first live recipe is deferred out of the slice's acceptance"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:366-370"
  - id: F012
    severity: note
    category: data
    summary: "The hand-run file count does not reproduce 723"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:43"
  - id: F013
    severity: note
    category: integration
    summary: "The leak scan's behavior when there is no transcript source is unspecified"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:273-276"
  - id: F014
    severity: note
    category: scope
    summary: "Squadron cases read squadron's own history, and the 17-case load needs host remotes"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:191"
  - id: F015
    severity: note
    category: integration
    summary: "The 432 extension point is not named in the case or stage model"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:438"
  - id: F016
    severity: pass
    category: architecture
    summary: "Record and layering choices follow the architecture"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:104-125"
  - id: F017
    severity: pass
    category: integration
    summary: "Reused interfaces exist with the signatures the design uses"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:262-272"
---

# Review: slice — slice 430

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Config identity includes the alias and the configured effort

D4 defines `config_key` as a hash of alias, model, profile, configured effort, template hash, `tool_use` and `max_output_tokens`. The architecture's identity list (420-arch, line 44) is model, profile, effort sent, `tool_use` and `max_output_tokens`, and says "the alias name is for display only." The plan's 420 criterion (420-slices, line 33) says two runs that differ only in the alias's effort label but send the same effort count as one config. 425's `ReviewerRef.reviewer_key` leaves the alias out on purpose, and the design says it takes its fields from `ReviewerRef` and does not change it. As written, a renamed alias or a changed effort label splits rows the architecture calls comparable. Drop the alias from the hash, key on effort sent, keep the alias as display only, and state exactly which fields differ from `reviewer_key`.

### [CONCERN] One record per reviewer per run, presented as the architecture's coarse-record rule

The architecture says "Records stay coarse, one per case run, because the store reads every file on every query" (420-arch, line 69). D4 says it keys one record per case run and reviewer "as the architecture's coarse-record rule asks," and the import writes 723 records. That is finer than the rule. Either key the record per case run, holding each reviewer's review and combs, or state the deviation, its reason, and that it needs the PM's acceptance as an architecture change.

### [CONCERN] The stated bound is an estimate, and plan-billed calls are uncapped

The per-call bound is the largest observed cost for that config. The architecture requires an upper bound stated before any dispatch, with the run-level cap checked between dispatches and the one-call overshoot included in the stated bound (420-arch, lines 46 and 123). The reused budget checks the cap before each call, so one call can cross it. The design gives no bound formula, so the printed bound may leave out that overshoot. Also, `plan`-billed calls count as $0 (line 310). A Codex-heavy recipe then has no dollar cap, and the design lists its call count but nothing stops it. Add the overshoot term to the formula, say the figure is an estimate if it is one, and decide whether plan-billed calls need a call-count cap.

### [CONCERN] Auth and environment failures are scored as configuration misses

D8 counts a review call that "crashes" as `config_failure`, a miss for that config (line 294). The architecture says a config-caused failure is a fail, but a harness-caused failure, such as an environment that does not resolve, drops the case from every config (420-arch, line 71). D6 passes the scrubbed environment only the alias profile's credentials (line 262). A missing or rejected credential, a wrong `sq` path, or a missing sandbox would therefore be recorded as the reviewer missing a bug. The design has no preflight. Require 421's auth check to pass for each provider before `run` starts, and classify setup and credential errors as `harness_failure`, keeping `config_failure` for model and output errors.

### [CONCERN] Timeouts are under-specified, and the fetch timeout contradicts the sandbox it wraps

Three gaps. (a) Line 284 says both git commands run under `benchmark.recall_fetch_timeout_s`, but the git commands run through `HistoryFreeSandbox`'s command helper, which bounds each command at a fixed 120 seconds. Either bypass that helper for these commands and say so, or the config key does nothing. (b) D8 names no timeout for comb or grade calls (`_stage`); only `review_timeout_s` is named, and only for reviews. (c) `benchmark.review_timeout_s` is unset by default, and 425 checks it for `None` before it plans. State whether `run` refuses without it, as 425 does. The `rev-list` count in the source repo also has no timeout.

### [CONCERN] Undecided comb decisions are scored as misses, which D3 forbids

D3 says undecided is not a miss: recall is a range, with the lower bound counting undecided candidates as misses and the upper bound as hits (lines 216-219). D8 says a comb's `UNDECIDED` findings are "Not kept" (line 296), which removes them from every recipe that uses the comb. The report only prints a count. For fan-out, a bug reached only through an undecided finding counts as missed in both bounds. A stage-two comb also loses its input. Apply the same range to comb decisions, and say how an undecided stage-one decision affects stage two.

### [CONCERN] I/O paths without a failure-mode table: import, case loader, store writes

The review rule requires each new I/O path to name its failure modes and their observable signal. D8 covers stage calls and the fetch. It does not cover malformed or unreadable hand-run JSON, a grade reference to a finding index that does not exist, a case file that fails validation partway through a set, a store lock held by a dead process, or a crash after a paid call completes but before its run record is written (line 248). That last case means resume repeats a paid call, and "keeps every record already written" does not address it. D10 covers only a missing case record. Give each of these an outcome and a log level, with a test.

### [CONCERN] Bug locations are curated ground truth, against the architecture's non-goal

The architecture rules out curated expected-output datasets. Real-bug cases are "records of history... the ground truth is a fix commit or issue" (420-arch, line 150). D1 requires hand-written per-bug file lists, and D3's decided-miss rule (step 4, line 213) uses them to reject findings without a person. So the file lists decide results. Either derive default locations mechanically from the files the fix commit changed and record each hand addition with its reason, or state that the lists are a reviewed input and amend the non-goal. The gate-versus-import test only catches gaps in the hits that were imported.

### [CONCERN] History-free sandbox: a deliberate departure from the architecture that needs its own decision

The architecture says the replay sandbox holds "one commit, no refs to later history" (420-arch, line 50), and says recall runs "in a history-free sandbox at the diff's head" (line 101). D7 holds head plus its ancestry back to base. The mechanism is sound: ancestors of head cannot contain a later fix, and the wrapper's HEAD is head itself, so the base diff works. But the architecture's own wording forbids this, and the design calls it an extension. Route it to the PM as an architecture amendment, as with the 20261115 amendment, before implementation. Or choose a smaller alternative that holds only base and head.

### [CONCERN] Proportionality: the design is heavier than its effort rating, and the live grader is the cut

The plan rates 430 at 3/5 effort (420-slices, item 11). The design is 567 lines, with 14 modules, two templates, seven CLI commands plus a hidden one, four record types, twelve decisions, and two import formats with cross-pass merge rules. The plan asks for graded-real share, and the imported grading passes supply it. The live `grade` command, the `recall-grade` template, the grader's module, agent label writes, the grade bound and cap, and `label --grade` go beyond the plan's wording. Cut them and defer to a follow-on slice. The report keeps imported grades, and walkthrough step 6 goes with them.

### [CONCERN] The first live recipe is deferred out of the slice's acceptance

The plan's 430 criteria include "The first recipe measured live is haiku-xhigh and sol..." (420-slices, line 165). The design makes it walkthrough step 7, run by the PM after the slice, and its own criterion (line 467) is that `run` prints a bound. The architecture's rule that no task needs hours (420-arch, line 34) is a fair reason to defer. But this slice then does not meet the plan criterion, and the design does not say whether a PM-run measurement counts toward it. Record it as an explicit change to the plan, or confirm the deferral.

### [NOTE] The hand-run file count does not reproduce 723

Recursive glob counts of the three folders give 27 + 267 + 574 = 868 JSON files. Excluding the `judge/` and `precision/` subfolders (about 30 in grid2 and about 88 in grid3 by my manual count) leaves roughly 750 top-level files. I could not account for the difference, and these are glob counts without Bash, so they may be off. Confirm the number from the import's dry run before it becomes an acceptance figure, and state how 723 was counted.

### [NOTE] The leak scan's behavior when there is no transcript source is unspecified

D6 calls the leak scan for every call, then gives `confined` to profiles with no transcript source. The source function returns nothing for those profiles, but the scan takes a source, not an optional one. State that the scan is skipped and the verdict is `confined` when the source is absent, and that the verdict does not depend on an unhandled `None`.

### [NOTE] Squadron cases read squadron's own history, and the 17-case load needs host remotes

`cases add` reads each repo's distribution name at head (line 191), so walkthrough step 1 reads squadron's own history for the squadron cases. The plan rule says no task runs against squadron's own history (420-slices, line 155). Either write `distribution` into the squadron case files, which D1 already allows, or confirm the read is acceptable. Separately, `cases add` refuses a repo with no code-host remote (line 272). The plan requires all 17 cases to load, and the design does not confirm that every repo has a remote. I did not check that.

### [NOTE] The 432 extension point is not named in the case or stage model

`RealBugCase` fixes repo, base and head, and D6 hard-codes the `sq review code` command. The design says 432 can add a `document` kind without changing scoring or the recipe model, which is achievable only if the case model and the stage command are selected by kind through a named seam. Name that seam now so 432 does not reopen the runner.

### [PASS] Record and layering choices follow the architecture

The new records are sibling payloads on the 320 store with no migration, keyed on `ProjectId` with deterministic ids (lines 422-433). Scoring is pure, services are injected, and the design adds no dependencies. This matches the store-extension principle (420-arch, line 69).

### [PASS] Reused interfaces exist with the signatures the design uses

`build_leak_rules` takes exactly the inputs D6 lists. `ReviewBudget` exposes the before and after checks. `EXIT_CAP_REACHED` is 2. `TemplateOutput.DECISIONS` disables the recovery turn, as D8 relies on. `sq review code` accepts `--no-save` and `--output-path`. `paired_stats` exports `compare_pair` and `pair_seed`. `ReviewerRef` has `reviewer_key`. `HistoryFreeSandbox` builds its HEAD at the start commit, so D7's fetch extends that history and does not replace it.

### Run Digest

- Response length: 13985 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 617726 / 487183 / 130529 / 77483 / not computed
- Duration: 355.9 s
- Cost: $0.24 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17

## Resolution

- **Config identity includes alias and configured effort:** changed. D4's `config_key` now hashes model, profile, template_hash, `tool_use` and `max_output_tokens`. The alias is display only, and effort enters identity only as effort sent. The difference from `reviewer_key` is stated. Configured effort appears only in the pending-call `entry_key`, which is not identity.
- **One record per reviewer per run:** changed. There is now one `recall_run` record per (case, run), holding every reviewer's review and combs. The import writes 51 of them.
- **Bound is an estimate; plan-billed calls uncapped:** changed. D9 gives the formula: the sum of per-call figures plus one per-call overshoot. It is labelled "estimate" when the figures come from observed costs. A new `--max-plan-calls` is required when plan-billed calls are pending, and the run stops at it with exit 2.
- **Auth and environment failures scored as misses:** changed. D6 adds 421's `run_auth_check` as a preflight that refuses the run. D8 adds a classification rule: setup failures, and a subprocess that writes no output file, are `harness_failure`. Model and output failures are `config_failure`.
- **Timeouts under-specified; fetch timeout vs sandbox helper:** changed. D7's own git commands, including `rev-list`, run through the injected `ProcessRunner` under `benchmark.recall_fetch_timeout_s`. The sandbox's fixed 120 s bound applies only to its own one-commit build. `_stage` uses `benchmark.review_timeout_s`, and `run` refuses when that key is unset, as 425 does.
- **Undecided comb decisions scored as misses:** changed. D3's recall range now covers `UNDECIDED` comb decisions: DROP in the lower bound, KEEP in the upper. A finding stage one left undecided is not sent to stage two and stays undecided in the chain's output. Paired intervals exclude cases with anything undecided.
- **I/O paths without failure modes:** changed. D8 has a second table covering `cases add` validation (all files checked, nothing written on any failure), git failure, malformed import files, grade refs with no finding, live and dead store locks, and `write_record` failure. A crash after a paid call is handled by deterministic output files in `recall-out/`, which resume ingests. Each mode has a log level and a test.
- **Bug locations are curated ground truth:** changed. D1 derives locations from the files the proof commits changed, with no filtering. Hand additions go in `extra_locations`, each with a reason.
- **History-free sandbox departure:** routed to the PM. D7 is now `pending-pm`, with a proposed architecture amendment line. It records why the smaller base-and-head-only sandbox fails: `--diff` rewrites a bare ref to `<base>...HEAD`, which needs a merge base.
- **Proportionality, cut the live grader:** changed. Removed the `grade` command, the `recall-grade` template, the grader module, agent label records and `label --grade`. Real share comes from the imported passes. Deferred to #340.
- **First live recipe deferred out of acceptance:** routed to the PM. D11 is now `pending-pm`, with the proposed plan wording. The plan entry will be updated once the PM confirms.
- **723 count does not reproduce:** clarified. The count is `find -maxdepth 1 -name '*.json'`: 27 + 210 + 486 = 723. The `judge/` and `precision/` subfolders are excluded. The method is now stated in the Overview.
- **Leak scan with no transcript source:** changed. D6 now says the scan is not called when there is no source and the verdict is `confined`, so the scan is never handed an absent source.
- **Squadron history reads and host remotes:** changed and routed to the PM. `distribution` and `host_repo` are now written in every case file, so `cases add` reads no `pyproject.toml` and no remotes; all six repos were checked to have `origin`. Deriving locations still reads four squadron commits' file lists, so D13 asks the PM to confirm that, and states the fallback if not.
- **432 extension point not named:** changed. New D14 adds the `RecallKind` protocol and registry (`validate`, `open_sandbox`, `review_argv`), with `CodeKind` as the only implementation, and an integration test with a stub kind.
- **Record and layering choices follow the architecture (pass):** no change.
- **Reused interfaces exist (pass):** no change.
